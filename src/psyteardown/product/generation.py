"""Bounded, local-first Web source generation for the Product Studio slice."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.models import (
    GENERATION_DEFAULT_MAX_COST_UNITS,
    GENERATION_DEFAULT_MAX_DURATION_SECONDS,
    GENERATION_JOB_VERSION,
    GENERATION_MODEL_PROVIDER,
    GENERATION_MODEL_SOURCE_PATHS,
    GENERATION_SAVED_SOURCE_PROVIDER,
    GENERATION_SAVED_SOURCE_VERSION,
    GENERATION_MODEL_VERSION,
    GenerationBudget,
    GenerationManifest,
    GeneratedFile,
    ModelCallRecord,
    ProductGenerationJob,
    model_generation_budget,
    WebProductGenerationContract,
    WEB_OUTPUT_PATHS,
    WEB_TEMPLATE_ID,
    WEB_TEMPLATE_VERSION,
)
from psyteardown.product.repositories import ProductRepositoryError
from psyteardown.product.source_model import (
    SOURCE_MODEL_GATE_VERSION,
    SOURCE_MODEL_WORKSPACE_VERSION,
    SOURCE_MODEL_SYSTEM,
    ProductSourceModel,
    SourceModelError,
    build_source_prompt,
    check_model_source,
    contract_browser_test,
    parse_source_reply,
    timed_generate,
)


class ProductGenerationJobRepository(Protocol):
    def save_generation_job(
        self, job: ProductGenerationJob, *, expected_revision: int | None
    ) -> ProductGenerationJob: ...

    def get_generation_job(self, job_id: str) -> ProductGenerationJob | None: ...

    def get_generation_job_revision(self, job_id: str, revision_id: str) -> ProductGenerationJob | None: ...

    def list_generation_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductGenerationJob]: ...

    def get_current(self, object_type: str, object_id: str): ...

    def get_revision(self, object_type: str, revision_id: str): ...


class InMemoryProductGenerationJobRepository:
    """Revisioned in-memory adapter used by generation tests."""

    def __init__(self) -> None:
        self._revisions: dict[str, dict[int, ProductGenerationJob]] = defaultdict(dict)
        self._current: dict[str, int] = {}
        self._objects: dict[tuple[str, str], object] = {}

    def attach_product_repository(self, repository: object) -> None:
        self._product_repository = repository

    def save_generation_job(
        self, job: ProductGenerationJob, *, expected_revision: int | None
    ) -> ProductGenerationJob:
        current = self.get_generation_job(job.job_id)
        _validate_generation_job_revision(current, job, expected_revision)
        self._revisions[job.job_id][job.meta.revision] = job
        self._current[job.job_id] = job.meta.revision
        return job

    def get_generation_job(self, job_id: str) -> ProductGenerationJob | None:
        revision = self._current.get(job_id)
        return self._revisions[job_id].get(revision) if revision else None

    def get_generation_job_revision(self, job_id: str, revision_id: str) -> ProductGenerationJob | None:
        for value in self._revisions.get(job_id, {}).values():
            if value.revision_id == revision_id:
                return value
        return None

    def list_generation_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductGenerationJob]:
        values = [self.get_generation_job(job_id) for job_id in self._current]
        return sorted(
            [
                value
                for value in values
                if value is not None
                and (project_id is None or value.project_id == project_id)
            ],
            key=lambda item: (item.meta.created_at, item.job_id),
        )

    def get_current(self, object_type: str, object_id: str):
        repository = getattr(self, "_product_repository", None)
        if repository is None:
            return None
        return repository.get_current(object_type, object_id)

    def get_revision(self, object_type: str, revision_id: str):
        repository = getattr(self, "_product_repository", None)
        if repository is None:
            return None
        return repository.get_revision(object_type, revision_id)


class _BudgetExceeded(RuntimeError):
    pass


class _SandboxViolation(RuntimeError):
    pass


class _StaleInput(RuntimeError):
    pass


class _ModelAttemptFailed(RuntimeError):
    def __init__(self, record: ModelCallRecord, error_code: str, error_summary: str) -> None:
        super().__init__(error_summary)
        self.record = record
        self.error_code = error_code
        self.error_summary = error_summary


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_FORBIDDEN_NAMES = {".env", ".git", "id_rsa", "id_ed25519", "credentials.json"}


class ProductGenerationJobService:
    """Materialize a confirmed B2 contract without executing generated code."""

    def __init__(
        self,
        application,
        job_repository: ProductGenerationJobRepository,
        *,
        workspace_root: Path | str = Path("output/product-studio/workspaces"),
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
        source_model: ProductSourceModel | None = None,
        transcript_root: Path | str | None = None,
    ) -> None:
        self.application = application
        self.source_model = source_model
        self.job_repository = job_repository
        if hasattr(job_repository, "attach_product_repository"):
            job_repository.attach_product_repository(application.repository)
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._root = self.workspace_root.resolve()
        # Model transcripts live beside, never inside, job workspaces so they
        # are not part of the manifest or of any delivery bundle.
        self.transcript_root = Path(transcript_root) if transcript_root else self.workspace_root.parent / "model-calls"
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")

    def create_job(
        self,
        *,
        project_id: str,
        actor: str,
        reason: str,
        budget: GenerationBudget | None = None,
        source: Literal["template", "model"] = "template",
    ) -> ProductGenerationJob:
        view = self.application.get_project_view(project_id)
        if view.project.status != "active":
            raise DomainStateError("product project must be active for generation jobs")
        contract = view.web_generation_contract
        if contract is None or contract.status != "confirmed":
            raise DomainStateError(
                "a human-confirmed Web generation contract is required before source generation"
            )
        if source == "model":
            if self.source_model is None:
                raise DomainStateError("model source generation requires a configured source model provider")
            selected_budget = budget or model_generation_budget()
        else:
            selected_budget = budget or GenerationBudget()
            if (
                selected_budget.max_cost_units > GENERATION_DEFAULT_MAX_COST_UNITS
                or selected_budget.max_duration_seconds > GENERATION_DEFAULT_MAX_DURATION_SECONDS
            ):
                raise DomainStateError("template generation budget exceeds the template limits")
        dependency = DependencyRef(
            object_type="web_generation_contract",
            object_id=contract.web_generation_contract_id,
            revision=contract.meta.revision,
        )
        fingerprint = _fingerprint(project_id, dependency, selected_budget, source=source)
        # A model draft is non-deterministic and each explicit request spends
        # budget, so only an unfinished model job is reused.
        reusable_statuses = {"queued", "running", "paused"} if source == "model" else {"queued", "running", "paused", "succeeded"}
        reusable = next(
            (
                item
                for item in reversed(self.job_repository.list_generation_jobs(project_id=project_id))
                if item.fingerprint == fingerprint
                and item.status in reusable_statuses
            ),
            None,
        )
        if reusable:
            return reusable
        job_id = self._id("generation-job")
        workspace_path = f"{_safe_segment(project_id)}/{_safe_segment(job_id)}"
        job = ProductGenerationJob(
            job_id=job_id,
            revision_id=f"{job_id}.r1",
            meta=RevisionMeta(
                revision=1,
                created_at=self._now(),
                created_by=actor,
                reason=reason,
            ),
            project_id=project_id,
            input_dependencies=(dependency,),
            web_generation_contract_revision_id=contract.revision_id,
            workspace_id=job_id,
            workspace_relative_path=workspace_path,
            budget=selected_budget,
            fingerprint=fingerprint,
            **(
                {"provider": GENERATION_MODEL_PROVIDER, "provider_version": GENERATION_MODEL_VERSION, "materialization_kind": "model"}
                if source == "model"
                else {}
            ),
        )
        return self.job_repository.save_generation_job(job, expected_revision=None)

    def create_saved_source_job(
        self,
        *,
        project_id: str,
        source_job_id: str,
        actor: str,
        reason: str,
    ) -> ProductGenerationJob:
        """Enqueue a fresh B3 lineage from a locally retained, revalidated source.

        This does not mutate the source generation/job/workspace and does not
        call the provider. The child run regenerates current platform-owned
        files/tests and creates a new manifest/workspace pinned to the source
        generation revision and response hash.
        """
        view = self.application.get_project_view(project_id)
        if view.project.status != "active":
            raise DomainStateError("product project must be active for generation jobs")
        source = self.job_repository.get_generation_job(source_job_id)
        if source is None or source.project_id != project_id:
            raise DomainStateError("saved source generation job is unavailable for this project")
        if source.status != "succeeded" or source.materialization_kind != "model":
            raise DomainStateError("a succeeded model-source generation job is required")
        if not source.model_calls:
            raise DomainStateError("saved model source provenance is unavailable")
        source_call = source.model_calls[-1]
        if not source_call.static_gate_revalidated or source_call.static_gate_version != SOURCE_MODEL_GATE_VERSION:
            raise DomainStateError("saved model source must pass the current local static gate first")
        if source_call.response_sha256 is None:
            raise DomainStateError("saved model response hash is unavailable")
        if not self._inputs_are_current(source):
            raise DomainStateError("saved model source is pinned to an outdated Web contract; create a new model draft")
        source_workspace = self._workspace_path(source)
        source_manifest = self._read_manifest(source_workspace)
        if source_manifest is None or source_manifest != source.manifest:
            raise DomainStateError("saved model source workspace failed manifest integrity checks")
        source_files = {
            path: (source_workspace / path).read_text(encoding="utf-8")
            for path in GENERATION_MODEL_SOURCE_PATHS
        }
        contract = self._contract_for(source)
        issues = check_model_source(source_files, contract)
        if issues:
            raise DomainStateError("saved model source no longer passes the current local static gate")
        if not self._saved_transcript_matches_source(source, source_call, contract, source_files):
            raise DomainStateError("saved model source transcript does not match the manifest-pinned files")

        dependency = source.input_dependencies[0]
        fingerprint_payload = {
            "project_id": project_id,
            "contract_revision_id": source.web_generation_contract_revision_id,
            "source_job_id": source.job_id,
            "source_job_revision_id": source.revision_id,
            "source_response_sha256": source_call.response_sha256,
            "static_gate_version": SOURCE_MODEL_GATE_VERSION,
            "workspace_version": SOURCE_MODEL_WORKSPACE_VERSION,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = next(
            (
                item for item in reversed(self.job_repository.list_generation_jobs(project_id=project_id))
                if item.fingerprint == fingerprint and item.status in {"queued", "running", "paused", "succeeded"}
            ),
            None,
        )
        if existing:
            return existing
        job_id = self._id("generation-job")
        job = ProductGenerationJob(
            job_id=job_id,
            revision_id=f"{job_id}.r1",
            meta=RevisionMeta(
                revision=1,
                created_at=self._now(),
                created_by=actor,
                reason=reason,
            ),
            project_id=project_id,
            input_dependencies=(dependency,),
            web_generation_contract_revision_id=source.web_generation_contract_revision_id,
            workspace_id=job_id,
            workspace_relative_path=f"{_safe_segment(project_id)}/{_safe_segment(job_id)}",
            budget=GenerationBudget(),
            fingerprint=fingerprint,
            provider=GENERATION_SAVED_SOURCE_PROVIDER,
            provider_version=GENERATION_SAVED_SOURCE_VERSION,
            materialization_kind="saved_model",
            source_generation_job_id=source.job_id,
            source_generation_job_revision_id=source.revision_id,
            source_response_sha256=source_call.response_sha256,
            static_gate_version=SOURCE_MODEL_GATE_VERSION,
        )
        return self.job_repository.save_generation_job(job, expected_revision=None)

    def get_job(self, project_id: str, job_id: str) -> ProductGenerationJob:
        job = self.job_repository.get_generation_job(job_id)
        if job is None:
            raise DomainStateError(f"unknown product generation job: {job_id}")
        if job.project_id != project_id:
            raise DomainStateError(
                f"product generation job belongs to project {job.project_id}, not {project_id}"
            )
        return job

    def list_jobs(self, project_id: str) -> tuple[ProductGenerationJob, ...]:
        self.application.get_project_view(project_id)
        return tuple(self.job_repository.list_generation_jobs(project_id=project_id))

    def run_job(self, project_id: str, job_id: str, *, actor: str) -> ProductGenerationJob:
        job = self.get_job(project_id, job_id)
        if job.status == "succeeded":
            return job
        if job.status == "paused":
            raise DomainStateError("paused generation job must be resumed before it can run")
        if job.status not in {"queued", "running"}:
            raise DomainStateError(f"product generation job cannot run from status {job.status}")
        reconciled = self._reconcile_workspace(job, actor=actor)
        if reconciled is not None:
            return reconciled
        if not self._inputs_are_current(job):
            return self._transition(
                job,
                status="stale_input",
                actor=actor,
                reason="confirmed generation input revision changed",
            )
        if job.attempt >= job.budget.max_attempts or job.consumed_cost_units >= job.budget.max_cost_units:
            return self._transition(
                job,
                status="budget_exhausted",
                actor=actor,
                reason="generation budget exhausted",
                error_code="budget_exhausted",
                error_summary="The generation budget was exhausted before another attempt.",
            )
        started = time.monotonic()
        running = self._transition(
            job,
            status="running",
            actor=actor,
            reason="generation worker claimed job",
            attempt=job.attempt + 1,
            checkpoint_step="prepare",
            consumed_cost_units=job.consumed_cost_units + (0 if job.materialization_kind == "saved_model" else 1),
        )
        try:
            contract = self._contract_for(running)
            running = self._transition(
                running,
                status="running",
                actor=actor,
                reason="generation inputs prepared",
                checkpoint_step="generate",
            )
            files = self._render_files(contract)
            if running.materialization_kind == "model":
                files, record = self._model_files(running, contract, files)
                running = self._transition(
                    running,
                    status="running",
                    actor=actor,
                    reason="model source accepted by static gate",
                    checkpoint_step="generate",
                    model_calls=(*running.model_calls, record),
                )
            elif running.materialization_kind == "saved_model":
                files.update(self._saved_source_files(running, contract))
                # The rejected provider transcript contains only App.tsx/CSS;
                # all platform-owned files, especially the current derived test,
                # must come from the fixed renderer rather than its generic
                # template placeholder.
                files["tests/generated-contract.spec.ts"] = contract_browser_test(contract)
            elapsed = time.monotonic() - started
            self._check_budget(running.budget, files, elapsed)
            if not self._inputs_are_current(running):
                raise _StaleInput("confirmed generation input revision changed")
            running = self._transition(
                running,
                status="running",
                actor=actor,
                reason="template files rendered",
                checkpoint_step="validate",
                consumed_files=len(files),
                consumed_bytes=sum(len(content.encode("utf-8")) for _, content in files.items()),
                consumed_duration_seconds=elapsed,
            )
            manifest = self._write_workspace(running, files)
            elapsed = time.monotonic() - started
            self._check_budget(running.budget, files, elapsed)
            if not self._inputs_are_current(running):
                workspace = self._workspace_path(running)
                if workspace.exists():
                    shutil.rmtree(workspace)
                raise _StaleInput("confirmed generation input revision changed")
        except _StaleInput:
            workspace = self._workspace_path(running)
            if workspace.exists():
                shutil.rmtree(workspace)
            return self._transition(
                running,
                status="stale_input",
                actor=actor,
                reason="confirmed generation input revision changed before commit",
                consumed_duration_seconds=time.monotonic() - started,
            )
        except _BudgetExceeded:
            workspace = self._workspace_path(running)
            if workspace.exists():
                shutil.rmtree(workspace)
            return self._transition(
                running,
                status="budget_exhausted",
                actor=actor,
                reason="generation exceeded its local budget",
                error_code="budget_exhausted",
                error_summary="The generated workspace exceeded the configured local budget.",
                consumed_duration_seconds=time.monotonic() - started,
            )
        except _ModelAttemptFailed as failure:
            return self._transition(
                running,
                status="failed",
                actor=actor,
                reason="model source attempt did not pass",
                error_code=failure.error_code,
                error_summary=failure.error_summary,
                model_calls=(*running.model_calls, failure.record),
                consumed_duration_seconds=time.monotonic() - started,
            )
        except _SandboxViolation:
            return self._transition(
                running,
                status="failed",
                actor=actor,
                reason="generation sandbox policy rejected output",
                error_code="sandbox_violation",
                error_summary="The generated workspace did not satisfy the local sandbox policy.",
                consumed_duration_seconds=time.monotonic() - started,
            )
        except ProductRepositoryError:
            raise
        except Exception:
            return self._transition(
                running,
                status="failed",
                actor=actor,
                reason="template generation failed",
                error_code="generation_failed",
                error_summary="The deterministic template could not be materialized.",
                consumed_duration_seconds=time.monotonic() - started,
            )
        return self._transition(
            running,
            status="succeeded",
            actor=actor,
            reason="model workspace materialized" if running.materialization_kind == "model" else "template workspace materialized",
            checkpoint_step="validate",
            consumed_duration_seconds=elapsed,
            manifest=manifest,
        )

    def pause_job(self, project_id: str, job_id: str, *, actor: str) -> ProductGenerationJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"queued", "running"}:
            raise DomainStateError("only queued or running generation jobs can be paused")
        return self._transition(job, status="paused", actor=actor, reason="generation paused by user")

    def resume_job(self, project_id: str, job_id: str, *, actor: str) -> ProductGenerationJob:
        job = self.get_job(project_id, job_id)
        if job.status != "paused":
            raise DomainStateError("only paused generation jobs can be resumed")
        if not self._inputs_are_current(job):
            return self._transition(job, status="stale_input", actor=actor, reason="confirmed generation input revision changed")
        return self._transition(job, status="queued", actor=actor, reason="generation resumed by user")

    def cancel_job(self, project_id: str, job_id: str, *, actor: str) -> ProductGenerationJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"queued", "running", "paused"}:
            raise DomainStateError("only active generation jobs can be cancelled")
        return self._transition(job, status="cancelled", actor=actor, reason="generation cancelled by user")

    def revalidate_saved_model_draft(
        self, project_id: str, job_id: str, *, actor: str
    ) -> ProductGenerationJob:
        """Re-run the current local gate and fixed renderer without a provider call.

        Rejected source can be recovered from its saved response. A successful
        model workspace can also be refreshed into a new revision-pinned path,
        so updated platform-owned tests/templates never overwrite an older
        workspace or spend another provider call.
        """
        job = self.get_job(project_id, job_id)
        recovering_rejection = job.status == "failed" and job.error_code == "model_output_rejected"
        if not recovering_rejection:
            raise DomainStateError("only a model draft rejected by the static gate can be revalidated")
        if job.materialization_kind != "model" or not job.model_calls:
            raise DomainStateError("the generation job has no saved model draft")
        record = job.model_calls[-1]
        if record.outcome not in {"accepted", "rejected"} or record.response_sha256 is None:
            raise DomainStateError("the latest model attempt has no complete saved response to revalidate")
        if recovering_rejection and record.outcome != "rejected":
            raise DomainStateError("the failed generation job does not contain a rejected model response")
        if not self._inputs_are_current(job):
            return self._transition(
                job,
                status="stale_input",
                actor=actor,
                reason="saved model draft input is no longer current",
                error_code="stale_input",
                error_summary="The confirmed Web contract changed; create a new source-generation job.",
                manifest=None,
            )

        path = self.transcript_path(job, record.attempt)
        if path.is_symlink() or not path.is_file():
            raise DomainStateError("the locally saved model transcript is unavailable")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DomainStateError("the locally saved model transcript could not be read") from exc
        if (
            payload.get("job_id") != job.job_id
            or payload.get("attempt") != record.attempt
            or payload.get("web_generation_contract_revision_id") != job.web_generation_contract_revision_id
            or payload.get("provider") != record.provider
            or payload.get("response_model") not in {None, record.model}
            or payload.get("sent_object_types") != ["web_generation_contract"]
        ):
            raise DomainStateError("the saved model transcript does not match this pinned generation job")
        prompt, system, response = payload.get("prompt"), payload.get("system"), payload.get("response")
        if not isinstance(prompt, str) or not isinstance(system, str) or not isinstance(response, str):
            raise DomainStateError("the saved model transcript has no complete response to revalidate")
        request_sha = hashlib.sha256(f"{system}\n\n{prompt}".encode("utf-8")).hexdigest()
        response_sha = hashlib.sha256(response.encode("utf-8")).hexdigest()
        if request_sha != record.request_sha256 or response_sha != record.response_sha256:
            raise DomainStateError("the saved model response failed its transcript integrity check")

        old_audit = payload.get("gate_revalidation")
        provider_gate = payload.get("provider_gate", payload.get("gate"))
        if isinstance(old_audit, dict) and isinstance(old_audit.get("previous_gate"), dict):
            provider_gate = old_audit["previous_gate"]
        contract = self._contract_for(job)
        files, issues = parse_source_reply(response, truncated=bool(payload.get("truncated", False)))
        if not issues:
            issues = check_model_source(files, contract)
        if issues:
            payload["gate_revalidation"] = {
                "gate_version": SOURCE_MODEL_GATE_VERSION,
                "accepted": False,
                "reasons": issues,
                "checked_by": actor,
                "checked_at": self._now().isoformat(),
            }
            self._write_transcript(record.transcript_path, payload)
            raise DomainStateError(
                f"The saved model draft still fails the current static gate ({len(issues)} issue(s)); "
                "no provider call was made."
            )

        output = self._render_files(contract)
        output.update(files)
        output["tests/generated-contract.spec.ts"] = contract_browser_test(contract)
        try:
            self._check_budget(job.budget, output, 0)
        except _BudgetExceeded as exc:
            raise DomainStateError("the regenerated saved-draft workspace exceeds its pinned budget") from exc

        target_relative = job.workspace_relative_path
        candidate = job.model_copy(update={"workspace_relative_path": target_relative})
        target_workspace = self._workspace_path(candidate)
        expected_files = tuple(
            GeneratedFile(
                path=relative,
                byte_count=len(content.encode("utf-8")),
                sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
            for relative, content in sorted(output.items())
        )
        if target_workspace.exists():
            manifest = self._read_manifest(target_workspace)
            if manifest is None or manifest.files != expected_files:
                raise DomainStateError("the saved-draft refresh path is occupied by different workspace contents")
        else:
            manifest = self._write_workspace(candidate, output)

        # Correct legacy metadata only from the locally retained old audit: the
        # provider outcome remains rejected while current local validation is
        # recorded separately and versioned.
        original_reasons = record.rejection_reasons
        if isinstance(provider_gate, dict) and provider_gate.get("accepted") is False:
            reasons = provider_gate.get("reasons", ())
            if isinstance(reasons, list):
                original_reasons = tuple(str(item) for item in reasons)
        provider_outcome = "rejected" if isinstance(provider_gate, dict) and provider_gate.get("accepted") is False else record.outcome
        revalidated_record = record.model_copy(
            update={
                "outcome": provider_outcome,
                "rejection_reasons": original_reasons,
                "static_gate_revalidated": True,
                "static_gate_version": SOURCE_MODEL_GATE_VERSION,
            }
        )
        calls = (*job.model_calls[:-1], revalidated_record)
        audits = payload.get("gate_revalidations", [])
        if not isinstance(audits, list):
            audits = []
        if isinstance(old_audit, dict):
            audits = [*audits, old_audit]
        payload["gate_revalidations"] = [
            *audits,
            {
                "gate_version": SOURCE_MODEL_GATE_VERSION,
                "accepted": True,
                "workspace_refresh": False,
                "checked_by": actor,
                "checked_at": self._now().isoformat(),
            },
        ]
        payload.pop("gate_revalidation", None)
        payload["provider_gate"] = provider_gate if isinstance(provider_gate, dict) else {"accepted": record.outcome == "accepted", "reasons": list(record.rejection_reasons)}
        payload["static_gate_version"] = SOURCE_MODEL_GATE_VERSION
        payload["gate"] = {"accepted": True, "reasons": []}
        self._write_transcript(record.transcript_path, payload)

        # One current-revision transition: the new manifest/path is committed
        # atomically in the job ledger; the prior job revision still points to
        # its old immutable workspace and existing B4 execution.
        return self._transition(
            job,
            status="succeeded",
            actor=actor,
            reason=(
                "saved rejected model source passed corrected local static gate"
            ),
            model_calls=calls,
            workspace_relative_path=target_relative,
            manifest=manifest,
            checkpoint_step="validate",
            consumed_files=len(manifest.files),
            consumed_bytes=manifest.total_bytes,
            error_code=None,
            error_summary=None,
        )

    def retry_job(self, project_id: str, job_id: str, *, actor: str) -> ProductGenerationJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"failed", "stale_input"}:
            raise DomainStateError("only failed or stale generation jobs can be retried")
        if not self._inputs_are_current(job):
            raise DomainStateError("generation job inputs are no longer current; create a new job")
        if job.attempt >= job.budget.max_attempts or job.consumed_cost_units >= job.budget.max_cost_units:
            return self._transition(
                job,
                status="budget_exhausted",
                actor=actor,
                reason="generation retry exceeds budget",
                error_code="budget_exhausted",
                error_summary="The generation retry budget was exhausted.",
            )
        return self._transition(job, status="queued", actor=actor, reason="generation retry requested")

    def _contract_for(self, job: ProductGenerationJob) -> WebProductGenerationContract:
        value = self.job_repository.get_revision(
            "web_generation_contract", job.web_generation_contract_revision_id
        )
        if not isinstance(value, WebProductGenerationContract):
            raise DomainStateError("pinned Web generation contract is unavailable")
        return value

    def _inputs_are_current(self, job: ProductGenerationJob) -> bool:
        dependency = job.input_dependencies[0]
        current = self.job_repository.get_current(dependency.object_type, dependency.object_id)
        if not (
            isinstance(current, WebProductGenerationContract)
            and current.meta.revision == dependency.revision
            and current.status == "confirmed"
        ):
            return False
        # A contract is itself pinned to thesis/outcome revisions.  Treat a
        # transitive upstream change as stale even when the contract aggregate
        # has not yet been amended, so a generation job cannot materialize an
        # obsolete realization after an upstream decision changes.
        for upstream in current.dependencies:
            upstream_current = self.job_repository.get_current(
                upstream.object_type, upstream.object_id
            )
            if upstream_current is None or upstream_current.meta.revision != upstream.revision:
                return False
            if upstream.object_type == "product_thesis":
                if getattr(upstream_current, "status", None) not in {"exploring", "selected"}:
                    return False
            elif getattr(upstream_current, "status", None) != "confirmed":
                return False
        return True

    def _render_files(self, contract: WebProductGenerationContract) -> dict[str, str]:
        if contract.template_id != WEB_TEMPLATE_ID or contract.template_version != WEB_TEMPLATE_VERSION:
            raise _SandboxViolation("unsupported template")
        if tuple(contract.output_paths) != WEB_OUTPUT_PATHS:
            raise _SandboxViolation("unsupported output layout")
        payload = {
            "app_title": contract.app_title,
            "screens": [item.model_dump(mode="json") for item in contract.screens],
            "tasks": [item.model_dump(mode="json") for item in contract.tasks],
            "primary_flow_task_ids": list(contract.primary_flow_task_ids),
            "states": [item.model_dump(mode="json") for item in contract.states],
            "content_slots": [item.model_dump(mode="json") for item in contract.content_slots],
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        escaped_title = json.dumps(contract.app_title, ensure_ascii=False)
        app = """
import {useState} from "react";
import "./styles.css";

const contract = __CONTRACT__ as const;
const appTitle = __TITLE__ as const;
const firstScreen = contract.screens[0];
const setupScreenId = contract.screens.find((screen) => screen.screen_id.endsWith("-setup-screen"))?.screen_id ?? firstScreen?.screen_id ?? "";
const compareScreenId = contract.screens.find((screen) => screen.screen_id.endsWith("-comparison-screen"))?.screen_id ?? setupScreenId;
const reviewScreenId = contract.screens.find((screen) => screen.screen_id.endsWith("-review-screen"))?.screen_id ?? compareScreenId;
const primaryFlow = contract.primary_flow_task_ids;
const slotText = (suffix: string, fallback: string) => {
  const slot = contract.content_slots.find((item) => item.slot_id.endsWith(suffix));
  return slot?.fallback_text ?? fallback;
};
const slotId = (suffix: string) => contract.content_slots.find((item) => item.slot_id.endsWith(suffix))?.slot_id;
const taskId = (suffix: string) => contract.tasks.find((item) => item.task_id.endsWith(suffix))?.task_id ?? "";
const saveTaskId = taskId("-save-brief");

type StateKind = "ready" | "loading" | "empty" | "error" | "success" | "paused" | "stopped";
type OptionKey = "a" | "b";
type OptionRecord = { key: OptionKey; name: string; standards: string; facts: string; concerns: string };
type DecisionBrief = {
  decisionQuestion: string;
  context: string;
  deadline: string;
  options: OptionRecord[];
  leaning: string;
  nextQuestion: string;
};

const initialBrief = (): DecisionBrief => ({
  decisionQuestion: "",
  context: "",
  deadline: "",
  options: [
    { key: "a", name: slotText("-option-a", "选项 A"), standards: "", facts: "", concerns: "" },
    { key: "b", name: slotText("-option-b", "选项 B"), standards: "", facts: "", concerns: "" },
  ],
  leaning: "",
  nextQuestion: "",
});

export default function App() {
  const [activeScreen, setActiveScreen] = useState<string>(setupScreenId);
  const [state, setState] = useState<StateKind>("ready");
  const [flowStep, setFlowStep] = useState(0);
  const [brief, setBrief] = useState<DecisionBrief>(initialBrief);
  const [message, setMessage] = useState("");

  function updateBrief(field: "decisionQuestion" | "context" | "deadline" | "leaning" | "nextQuestion", value: string) {
    setBrief((current) => ({ ...current, [field]: value }));
  }

  function updateOption(key: OptionKey, field: keyof Omit<OptionRecord, "key">, value: string) {
    setBrief((current) => ({
      ...current,
      options: current.options.map((option) => option.key === key ? { ...option, [field]: value } : option),
    }));
  }

  function completeTask(task: string) {
    setState("success");
    const index = primaryFlow.findIndex((item) => item === task);
    if (index >= 0) setFlowStep((current) => Math.max(current, index + 1));
  }

  function stop() {
    setState("stopped");
    setMessage("");
  }

  function recover() {
    setState("ready");
    setMessage("");
  }

  function exportBrief() {
    const payload = {
      schema_version: "decision-brief.v1",
      app_title: appTitle,
      exported_at: new Date().toISOString(),
      ...brief,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "decision-brief.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("已下载本地 JSON 简报；之后可以用导入功能重新打开。");
    completeTask(saveTaskId);
  }

  function importBrief(file: File | undefined) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as Partial<DecisionBrief>;
        if (!Array.isArray(parsed.options) || parsed.options.length < 2) throw new Error("至少需要两个选项");
        const options = parsed.options.slice(0, 2).map((option, index) => ({
          key: index === 0 ? "a" as const : "b" as const,
          name: String(option.name ?? `选项 ${index === 0 ? "A" : "B"}`),
          standards: String(option.standards ?? ""),
          facts: String(option.facts ?? ""),
          concerns: String(option.concerns ?? ""),
        }));
        setBrief({
          decisionQuestion: String(parsed.decisionQuestion ?? ""),
          context: String(parsed.context ?? ""),
          deadline: String(parsed.deadline ?? ""),
          options,
          leaning: String(parsed.leaning ?? ""),
          nextQuestion: String(parsed.nextQuestion ?? ""),
        });
        setMessage("已重新打开本地 JSON 简报；请核对后继续编辑。");
        setFlowStep(primaryFlow.length);
        setState("success");
      } catch {
        setMessage("无法打开这份文件；请使用本产品导出的 decision-brief.json。");
        setState("error");
      }
    };
    reader.onerror = () => {
      setMessage("文件读取失败；原有简报内容没有改变。");
      setState("error");
    };
    reader.readAsText(file);
  }

  function runTask(task: string) {
    if (task.endsWith("-setup-stop") || task.endsWith("-stop-recover") || task.endsWith("-review-stop")) {
      stop();
    } else if (task.endsWith("-save-brief")) {
      exportBrief();
    } else {
      completeTask(task);
    }
  }

  const activeTaskIds: readonly string[] = contract.screens.find((screen) => screen.screen_id === activeScreen)?.task_ids ?? [];
  const activeTasks = contract.tasks.filter((task) => activeTaskIds.includes(task.task_id));
  const nextTask = primaryFlow[flowStep];
  const nextTaskGoal = contract.tasks.find((task) => task.task_id === nextTask)?.goal ?? "可以继续整理这份简报";

  return (
    <main className="app" aria-labelledby="app-title">
      <h1 id="app-title">{appTitle}</h1>
      <nav className="nav" aria-label="页面导航">
        {contract.screens.map((screen) => (
          <button type="button" data-screen-link={screen.screen_id} className={activeScreen === screen.screen_id ? "nav-btn active" : "nav-btn"} onClick={() => setActiveScreen(screen.screen_id)} key={screen.screen_id}>
            {screen.title}
          </button>
        ))}
      </nav>
      <p role="status" aria-live="polite" data-state-kind={state} className="status">
        {state === "success" ? (message || "本地简报已更新；决定仍由你自己做。") : state === "stopped" ? "流程已停止，控制权已恢复。" : state === "error" ? (message || "本地流程出了问题，请重试或停止。") : state === "empty" ? "还没有记录你的判断。" : state === "paused" ? "流程已暂停，可以继续或停止。" : "准备就绪：先写清楚决定，再比较选项。"}
      </p>
      {state !== "ready" ? <button type="button" data-recovery="true" className="recovery" onClick={recover}>回到就绪状态</button> : null}
      <section data-screen-id={activeScreen} className="screen">
        <h2>{contract.screens.find((screen) => screen.screen_id === activeScreen)?.title ?? "决策简报"}</h2>
        <p data-slot-id={slotId("-title")} className="slot-title">{slotText("-title", appTitle)}</p>
        <p data-slot-id={slotId("-goal")} className="slot">{slotText("-goal", "把一个近期决定整理成可保存、可重开的简报。")} </p>
        <p className="local-note">这是本地决策简报：未导出的内容只存在当前页面；导出 JSON 后可以在之后重新打开，不会上传任何内容。</p>
        <div className="flow" data-primary-flow-step={flowStep}>
          <h3>主要任务</h3>
          <ol className="flow-list">
            {primaryFlow.map((flowTask, index) => {
              const task = contract.tasks.find((item) => item.task_id === flowTask);
              return <li className={flowStep > index ? "done" : ""} key={flowTask}>{task?.goal ?? flowTask}</li>;
            })}
          </ol>
          <p className="next-action">当前下一步：{nextTaskGoal}</p>
        </div>

        {activeScreen === setupScreenId ? (
          <div className="setup-grid">
            <label><span data-slot-id={slotId("-decision-question")}>{slotText("-decision-question", "这次要做什么决定？")}</span><textarea value={brief.decisionQuestion} onChange={(event) => updateBrief("decisionQuestion", event.target.value)} aria-label="这次要做什么决定" placeholder="例如：本周要选哪个方案？" /></label>
            <label><span data-slot-id={slotId("-context")}>{slotText("-context", "背景和约束")}</span><textarea value={brief.context} onChange={(event) => updateBrief("context", event.target.value)} aria-label="背景和约束" placeholder="只写会改变选择的背景和限制" /></label>
            <label><span data-slot-id={slotId("-deadline")}>{slotText("-deadline", "什么时候需要回看？")}</span><input value={brief.deadline} onChange={(event) => updateBrief("deadline", event.target.value)} aria-label="什么时候需要回看" placeholder="例如：周五下午" /></label>
          </div>
        ) : null}

        {activeScreen === compareScreenId ? (
          <>
            <div className="comparison-grid" aria-label="选项对比">
              {brief.options.map((option) => {
                const label = `选项 ${option.key.toUpperCase()}`;
                return (
                  <article className="option-card" data-option-key={option.key} key={option.key}>
                    <label><span data-slot-id={slotId(`-option-${option.key}`)}>{label}名称</span><input value={option.name} onChange={(event) => updateOption(option.key, "name", event.target.value)} aria-label={`${label}名称`} /></label>
                    <label><span data-slot-id={slotId("-criteria")}>{slotText("-criteria", "决策标准")}</span><textarea value={option.standards} onChange={(event) => updateOption(option.key, "standards", event.target.value)} aria-label={`${label}决策标准`} placeholder="例如：时间、成本、可逆性" /></label>
                    <label><span data-slot-id={slotId("-facts")}>{slotText("-facts", "已知信息")}</span><textarea value={option.facts} onChange={(event) => updateOption(option.key, "facts", event.target.value)} aria-label={`${label}已知信息`} placeholder="只写目前知道的内容" /></label>
                    <label><span data-slot-id={slotId("-concerns")}>{slotText("-concerns", "顾虑")}</span><textarea value={option.concerns} onChange={(event) => updateOption(option.key, "concerns", event.target.value)} aria-label={`${label}顾虑`} placeholder="把担心的地方单独写出来" /></label>
                  </article>
                );
              })}
            </div>
          </>
        ) : null}

        {activeScreen === reviewScreenId ? (
          <div className="review-card">
            <h3>决策简报预览</h3>
            <dl className="brief-meta"><div><dt>这次要做什么决定</dt><dd>{brief.decisionQuestion || "未记录"}</dd></div><div><dt>背景和约束</dt><dd>{brief.context || "未记录"}</dd></div><div><dt>回看时间</dt><dd>{brief.deadline || "未记录"}</dd></div></dl>
            <div className="comparison-grid" aria-label="对比摘要">
              {brief.options.map((option) => (
                <article className="option-card" key={option.key}>
                  <h4>{option.name || `选项 ${option.key.toUpperCase()}`}</h4>
                  <p><strong>{slotText("-criteria", "决策标准")}：</strong>{option.standards || "未记录"}</p>
                  <p><strong>{slotText("-facts", "已知信息")}：</strong>{option.facts || "未记录"}</p>
                  <p><strong>{slotText("-concerns", "顾虑")}：</strong>{option.concerns || "未记录"}</p>
                </article>
              ))}
            </div>
            <label><span data-slot-id={slotId("-decision")}>{slotText("-decision", "我的当前倾向（不是工具推荐）")}</span><textarea value={brief.leaning} onChange={(event) => updateBrief("leaning", event.target.value)} aria-label="我的当前倾向（不是工具推荐）" placeholder="由你记录，不是系统推荐" /></label>
            <label><span data-slot-id={slotId("-next-question")}>{slotText("-next-question", "下一步需要核实的问题")}</span><textarea value={brief.nextQuestion} onChange={(event) => updateBrief("nextQuestion", event.target.value)} aria-label="下一步需要核实的问题" placeholder="哪些信息还缺失，应该如何核实？" /></label>
            <p data-slot-id={slotId("-save")} className="save-copy">{slotText("-save", "下载 JSON 保存；刷新页面不会自动保留未导出的内容。")}</p>
            <div className="brief-actions">
              <button type="button" data-export-brief="true" className="button-primary" onClick={exportBrief}>导出决策简报</button>
              <label className="file-picker"><span>导入已有 JSON 简报</span><input type="file" accept="application/json,.json" onChange={(event) => { importBrief(event.target.files?.[0]); event.currentTarget.value = ""; }} /></label>
            </div>
            <p data-save-status="true" className="save-status">{message || "导出后可在下一次打开时重新载入。"}</p>
            <p data-slot-id={slotId("-unknown")} className="unknown">{slotText("-unknown", "仍待确认：这些记录是否足以支持真实情境中的选择。")}</p>
          </div>
        ) : null}

        <div className="tasks">
          {activeTasks.map((task) => <button type="button" data-task-id={task.task_id} className="task-btn" onClick={() => runTask(task.task_id)} key={task.task_id}>{task.goal}</button>)}
        </div>
        <p data-slot-id={slotId("-error")} className={state === "error" ? "error-copy" : "recovery-hint"}>{state === "error" ? slotText("-error", "本地流程出了问题。请重试或停止。") : "如遇错误，你可以重试或随时停止。"}</p>
      </section>
    </main>
  );
}
""".replace("__CONTRACT__", serialized).replace("__TITLE__", escaped_title)

        fixture = json.dumps(
            {
                "source": "local_fixture",
                "schema_version": "decision-brief.v1",
                "items": [
                    {"id": "option-a", "label": "Option A", "notes": {"decision_standard": [], "known_fact": [], "concern": []}},
                    {"id": "option-b", "label": "Option B", "notes": {"decision_standard": [], "known_fact": [], "concern": []}},
                ],
                "categories": ["decision_standard", "known_fact", "concern", "next_question"],
                "persistence": "explicit_json_export_import_only",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        package_json = json.dumps(
            {
                "private": True,
                "type": "module",
                "scripts": {"build": "tsc -b && vite build", "preview": "vite preview", "test:e2e": "playwright test"},
                "dependencies": {"react": "19.1.1", "react-dom": "19.1.1"},
                "devDependencies": {
                    "@playwright/test": "1.55.1",
                    "@axe-core/playwright": "4.13.0",
                    "@types/react": "19.1.16",
                    "@types/react-dom": "19.1.9",
                    "@vitejs/plugin-react": "5.0.4",
                    "@testing-library/react": "16.3.0",
                    "typescript": "5.9.3",
                    "vite": "7.1.9",
                    "vitest": "5.0.1",
                },
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        index_html = "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" /><title>Product Studio output</title></head><body><div id=\"root\"></div><script type=\"module\" src=\"/src/main.tsx\"></script></body></html>\n"
        tsconfig = json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "useDefineForClassFields": True,
                    "lib": ["ES2022", "DOM", "DOM.Iterable"],
                    "allowJs": False,
                    "skipLibCheck": True,
                    "esModuleInterop": True,
                    "allowSyntheticDefaultImports": True,
                    "strict": True,
                    "forceConsistentCasingInFileNames": True,
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "noEmit": True,
                    "jsx": "react-jsx",
                },
                "include": ["src"],
            },
            indent=2,
        ) + "\n"
        vite_config = "import {defineConfig} from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({plugins: [react()]});\n"
        playwright_config = (
            "import {defineConfig} from '@playwright/test';\n"
            "export default defineConfig({use: {baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:4173'}, "
            "testDir: './tests', reporter: 'list'});\n"
        )
        test = contract_browser_test(contract)
        return {
            "package.json": package_json,
            "index.html": index_html,
            "tsconfig.json": tsconfig,
            "vite.config.ts": vite_config,
            "playwright.config.ts": playwright_config,
            "src/main.tsx": 'import {StrictMode} from "react";\nimport {createRoot} from "react-dom/client";\nimport App from "./App";\nimport "./styles.css";\n\ncreateRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);\n',
            "src/App.tsx": app,
            "src/styles.css": "body { font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f6f7fb; } .app { max-width: 1100px; margin: 0 auto; } button { margin-right: .5rem; cursor: pointer; } .nav, .tasks, .brief-actions { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1rem 0; } .nav-btn, .task-btn, .recovery, .button-primary { padding: .55rem .8rem; border: 1px solid #b9c1d0; border-radius: .45rem; background: white; } .button-primary { background: #172033; color: white; } .nav-btn.active { background: #172033; color: white; } .status, .next-action, .unknown, .save-status { padding: .7rem .9rem; border-radius: .45rem; background: #eef2ff; } .comparison-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; } .setup-grid { display: grid; gap: 1rem; max-width: 760px; } .option-card, .review-card { display: grid; gap: .65rem; padding: 1rem; border: 1px solid #d4d9e4; border-radius: .6rem; background: white; } .brief-meta { display: grid; gap: .7rem; margin: 0; } .brief-meta div { padding: .65rem; border-left: 3px solid #6574cd; background: #f7f8ff; } dt { font-weight: 700; } dd { margin: .25rem 0 0; } label { display: grid; gap: .35rem; font-weight: 600; } input, textarea { width: 100%; box-sizing: border-box; padding: .55rem; border: 1px solid #b9c1d0; border-radius: .35rem; font: inherit; } input[type=file] { padding: .4rem; background: #fff; } textarea { min-height: 4rem; resize: vertical; } .flow { margin: 1rem 0; } .flow-list .done { text-decoration: line-through; color: #465163; } .error-copy { color: #7f1d1d; } .local-note, .recovery-hint, .save-copy { color: #465163; } @media (max-width: 760px) { .comparison-grid { grid-template-columns: 1fr; } }\n",
            "tests/generated-contract.spec.ts": test,
            "public/fixture.json": fixture,
        }

    def _saved_transcript_matches_source(
        self, source: ProductGenerationJob, record: ModelCallRecord,
        contract: WebProductGenerationContract, files: dict[str, str],
    ) -> bool:
        if not source.model_calls or source.model_calls[-1] != record:
            return False
        try:
            path = self.transcript_path(source, record.attempt)
            if path.is_symlink() or not path.is_file():
                return False
            payload = json.loads(path.read_text(encoding="utf-8"))
            response = payload.get("response")
            prompt = payload.get("prompt")
            system = payload.get("system")
            audits = payload.get("gate_revalidations", [])
            has_current_local_acceptance = any(
                isinstance(item, dict)
                and item.get("accepted") is True
                and item.get("gate_version") == record.static_gate_version
                for item in audits
            ) if isinstance(audits, list) else False
            if (
                not isinstance(response, str)
                or not isinstance(prompt, str)
                or not isinstance(system, str)
                or not record.static_gate_revalidated
                or record.static_gate_version != SOURCE_MODEL_GATE_VERSION
                or not has_current_local_acceptance
            ):
                return False
            if payload.get("job_id") != source.job_id or payload.get("attempt") != record.attempt:
                return False
            if payload.get("web_generation_contract_revision_id") != contract.revision_id:
                return False
            if hashlib.sha256(response.encode("utf-8")).hexdigest() != record.response_sha256:
                return False
            expected, parse_issues = parse_source_reply(response, truncated=bool(payload.get("truncated", False)))
            if parse_issues or expected != files:
                return False
            return not check_model_source(expected, contract)
        except (DomainStateError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False

    def _saved_source_files(
        self, job: ProductGenerationJob, contract: WebProductGenerationContract
    ) -> dict[str, str]:
        if not job.source_generation_job_id or not job.source_generation_job_revision_id:
            raise _SandboxViolation("saved-source job lineage is incomplete")
        if not job.source_response_sha256 or job.static_gate_version != SOURCE_MODEL_GATE_VERSION:
            raise _SandboxViolation("saved-source job provenance is incomplete or stale")
        source = self.job_repository.get_generation_job_revision(
            job.source_generation_job_id, job.source_generation_job_revision_id
        )
        if (
            source is None or source.project_id != job.project_id or source.status != "succeeded"
            or source.materialization_kind != "model" or source.web_generation_contract_revision_id != contract.revision_id
            or not source.model_calls
        ):
            raise _StaleInput("pinned saved-source generation revision is unavailable")
        record = source.model_calls[-1]
        if (
            record.response_sha256 != job.source_response_sha256
            or not record.static_gate_revalidated
            or record.static_gate_version != job.static_gate_version
        ):
            raise _SandboxViolation("saved source no longer matches its pinned gate provenance")
        source_manifest = self._read_manifest(self._workspace_path(source))
        if source_manifest is None or source_manifest != source.manifest:
            raise _SandboxViolation("saved-source parent workspace failed manifest integrity checks")
        source_workspace = self._workspace_path(source)
        source_files = {
            path: (source_workspace / path).read_text(encoding="utf-8")
            for path in GENERATION_MODEL_SOURCE_PATHS
        }
        if check_model_source(source_files, contract):
            raise _SandboxViolation("saved model source failed current static validation")
        if not self._saved_transcript_matches_source(source, record, contract, source_files):
            raise _SandboxViolation("saved source transcript does not match the parent workspace files")
        return source_files

    def _model_files(
        self, job: ProductGenerationJob, contract: WebProductGenerationContract, template: dict[str, str]
    ) -> tuple[dict[str, str], ModelCallRecord]:
        """One model call: send only the contract, keep the transcript, gate the reply."""
        model = self.source_model
        if model is None:
            raise DomainStateError("model source generation requires a configured source model provider")
        attempt = len(job.model_calls) + 1
        previous = job.model_calls[-1].rejection_reasons if job.model_calls else ()
        prompt = build_source_prompt(contract, previous)
        request_sha = hashlib.sha256(f"{SOURCE_MODEL_SYSTEM}\n\n{prompt}".encode("utf-8")).hexdigest()
        relative = "/".join((_safe_segment(job.project_id), _safe_segment(job.job_id), f"attempt-{attempt}.json"))
        transcript = {
            "job_id": job.job_id,
            "attempt": attempt,
            "provider": model.name,
            "model": model.model,
            "sent_object_types": ["web_generation_contract"],
            "web_generation_contract_revision_id": contract.revision_id,
            "system": SOURCE_MODEL_SYSTEM,
            "prompt": prompt,
            "static_gate_version": SOURCE_MODEL_GATE_VERSION,
            "workspace_renderer_version": SOURCE_MODEL_WORKSPACE_VERSION,
        }
        base = {
            "attempt": attempt,
            "provider": model.name,
            "request_sha256": request_sha,
            "transcript_path": relative,
        }
        started = time.monotonic()
        try:
            reply, duration = timed_generate(model, system=SOURCE_MODEL_SYSTEM, prompt=prompt)
        except SourceModelError as exc:
            transcript["error"] = str(exc)
            self._write_transcript(relative, transcript)
            record = ModelCallRecord(**base, model=model.model, outcome="failed", duration_seconds=time.monotonic() - started)
            raise _ModelAttemptFailed(record, "model_call_failed", f"The model call failed: {exc}.") from exc
        response_sha = hashlib.sha256(reply.text.encode("utf-8")).hexdigest()
        transcript.update(
            response=reply.text,
            response_model=reply.model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            truncated=reply.truncated,
        )
        files, reasons = parse_source_reply(reply.text, truncated=reply.truncated)
        if not reasons:
            reasons = check_model_source(files, contract)
        transcript["gate"] = {"accepted": not reasons, "reasons": reasons}
        self._write_transcript(relative, transcript)
        record = ModelCallRecord(
            **base,
            model=reply.model or model.model,
            outcome="rejected" if reasons else "accepted",
            response_sha256=response_sha,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            duration_seconds=duration,
            rejection_reasons=tuple(reason[:200] for reason in reasons[:20]),
        )
        if reasons:
            summary = f"The model draft was rejected by the static gate ({len(reasons)} issue(s)): {reasons[0]}."
            raise _ModelAttemptFailed(record, "model_output_rejected", summary[:240])
        merged = dict(template)
        merged.update(files)
        # The model never writes its own checks: B4 runs a contract-derived test.
        merged["tests/generated-contract.spec.ts"] = contract_browser_test(contract)
        return merged, record

    def _write_transcript(self, relative: str, payload: dict) -> None:
        target = self.transcript_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def transcript_path(self, job: ProductGenerationJob, attempt: int) -> Path:
        record = next((item for item in job.model_calls if item.attempt == attempt), None)
        if record is None:
            raise DomainStateError(f"unknown model call attempt: {attempt}")
        root = self.transcript_root.resolve()
        candidate = (root / record.transcript_path).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise DomainStateError("model transcript path is outside the configured transcript root") from exc
        return candidate

    def _write_workspace(self, job: ProductGenerationJob, files: dict[str, str]) -> GenerationManifest:
        final = self._workspace_path(job)
        if final.exists():
            existing = self._read_manifest(final)
            if existing is not None:
                return existing
            raise _SandboxViolation("workspace already exists without a valid manifest")
        final.parent.mkdir(parents=True, exist_ok=True)
        if any(parent.is_symlink() for parent in (final.parent, self._root)):
            raise _SandboxViolation("workspace path contains a symlink")
        temporary = Path(tempfile.mkdtemp(prefix=f".{_safe_segment(job.job_id)}-", dir=self._root))
        try:
            for relative, content in files.items():
                self._validate_relative_path(relative)
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
            generated = tuple(
                GeneratedFile(
                    path=relative,
                    byte_count=len(content.encode("utf-8")),
                    sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
                for relative, content in sorted(files.items())
            )
            manifest = GenerationManifest(
                files=generated,
                total_bytes=sum(item.byte_count for item in generated),
            )
            (temporary / "generation-manifest.json").write_text(
                manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            temporary.rename(final)
            return manifest
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

    def _read_manifest(self, workspace: Path) -> GenerationManifest | None:
        path = workspace / "generation-manifest.json"
        try:
            if not path.is_file() or path.is_symlink():
                return None
            manifest = GenerationManifest.model_validate_json(path.read_text(encoding="utf-8"))
            self._assert_contained(workspace.resolve())
            for item in manifest.files:
                self._validate_relative_path(item.path)
                target = (workspace / item.path).resolve(strict=False)
                self._assert_contained(target)
                if not target.is_file() or target.is_symlink():
                    return None
                payload = target.read_bytes()
                if len(payload) != item.byte_count:
                    return None
                if hashlib.sha256(payload).hexdigest() != item.sha256:
                    return None
            return manifest
        except Exception:
            return None

    def _reconcile_workspace(self, job: ProductGenerationJob, *, actor: str) -> ProductGenerationJob | None:
        manifest = self._read_manifest(self._workspace_path(job))
        if manifest is None:
            return None
        if not self._inputs_are_current(job):
            return self._transition(job, status="stale_input", actor=actor, reason="confirmed generation input revision changed")
        return self._transition(
            job,
            status="succeeded",
            actor=actor,
            reason="reconciled previously materialized workspace",
            checkpoint_step="validate",
            manifest=manifest,
            consumed_files=len(manifest.files),
            consumed_bytes=manifest.total_bytes,
        )

    def _workspace_path(self, job: ProductGenerationJob) -> Path:
        candidate = (self._root / job.workspace_relative_path).resolve(strict=False)
        self._assert_contained(candidate)
        return candidate

    def _validate_relative_path(self, relative: str) -> None:
        path = relative.replace("\\", "/")
        if path.startswith("/") or ".." in path.split("/") or any(part in _FORBIDDEN_NAMES for part in path.split("/")):
            raise _SandboxViolation("generated path is not allowed")
        if not path or path.endswith("/"):
            raise _SandboxViolation("generated path is empty")

    def _assert_contained(self, candidate: Path) -> None:
        try:
            common = os.path.commonpath((str(self._root), str(candidate)))
        except ValueError as exc:
            raise _SandboxViolation("workspace path is outside the configured root") from exc
        if common != str(self._root):
            raise _SandboxViolation("workspace path is outside the configured root")

    def _check_budget(self, budget: GenerationBudget, files: dict[str, str], elapsed: float) -> None:
        total = sum(len(content.encode("utf-8")) for content in files.values())
        if len(files) > budget.max_files or total > budget.max_bytes or elapsed > budget.max_duration_seconds:
            raise _BudgetExceeded("generation budget exceeded")

    def _transition(self, current: ProductGenerationJob, *, status: str, actor: str, reason: str, **updates) -> ProductGenerationJob:
        revision = current.meta.revision + 1
        updated = current.model_copy(
            update={
                **updates,
                "revision_id": f"{current.job_id}.r{revision}",
                "meta": RevisionMeta(
                    revision=revision,
                    parent_revision_id=current.revision_id,
                    created_at=self._now(),
                    created_by=actor,
                    reason=reason,
                ),
                "status": status,
                "error_code": updates.get("error_code", None),
                "error_summary": updates.get("error_summary", None),
            }
        )
        return self.job_repository.save_generation_job(updated, expected_revision=current.meta.revision)

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("id_factory returned an empty identifier")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ProductGenerationJobService clock must be timezone-aware")
        return value


def _safe_segment(value: str) -> str:
    if _SAFE_SEGMENT.fullmatch(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"id-{digest}"


def _fingerprint(project_id: str, dependency: DependencyRef, budget: GenerationBudget, *, source: str = "template") -> str:
    payload = {
        "project_id": project_id,
        "dependency": dependency.model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
        "provider": GENERATION_MODEL_PROVIDER if source == "model" else "deterministic_template",
        "version": GENERATION_MODEL_VERSION if source == "model" else GENERATION_JOB_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_generation_job_revision(
    current: ProductGenerationJob | None,
    value: ProductGenerationJob,
    expected_revision: int | None,
) -> None:
    if current is None:
        if expected_revision is not None or value.meta.revision != 1:
            raise ProductRepositoryError("generation job first revision conflict")
        return
    if expected_revision != current.meta.revision:
        raise ProductRepositoryError(
            f"revision conflict: expected {expected_revision}, current {current.meta.revision}"
        )
    if value.meta.revision != current.meta.revision + 1:
        raise ProductRepositoryError("generation job revisions must increase by one")
    if value.meta.parent_revision_id != current.revision_id:
        raise ProductRepositoryError("generation job revision must reference current parent")
