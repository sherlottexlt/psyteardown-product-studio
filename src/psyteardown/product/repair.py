"""B5 bounded repair loop for failed Product Studio executions.

Repair is intentionally a separate capability from both source generation and
execution.  A planner sees only a safe failure summary, and an applied repair
creates a new immutable generation lineage before a fresh execution job runs.
The original workspace is never edited in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.execution import (
    ProductExecutionJobRepository,
    ProductExecutionJobService,
)
from psyteardown.product.generation import ProductGenerationJobRepository
from psyteardown.product.models import (
    GeneratedFile,
    GenerationManifest,
    ProductExecutionJob,
    ProductGenerationJob,
    ProductRepairJob,
    RepairAttempt,
    RepairBudget,
    RepairPatch,
    REPAIR_JOB_VERSION,
)
from psyteardown.product.repositories import ProductRepositoryError


class ProductRepairJobRepository(Protocol):
    def save_repair_job(
        self, job: ProductRepairJob, *, expected_revision: int | None
    ) -> ProductRepairJob: ...

    def get_repair_job(self, job_id: str) -> ProductRepairJob | None: ...

    def list_repair_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductRepairJob]: ...


class InMemoryProductRepairJobRepository:
    """Revisioned repair adapter used by domain tests and local preview."""

    def __init__(self) -> None:
        self._revisions: dict[str, dict[int, ProductRepairJob]] = defaultdict(dict)
        self._current: dict[str, int] = {}

    def save_repair_job(
        self, job: ProductRepairJob, *, expected_revision: int | None
    ) -> ProductRepairJob:
        current = self.get_repair_job(job.job_id)
        _validate_repair_job_revision(current, job, expected_revision)
        self._revisions[job.job_id][job.meta.revision] = job
        self._current[job.job_id] = job.meta.revision
        return job

    def get_repair_job(self, job_id: str) -> ProductRepairJob | None:
        revision = self._current.get(job_id)
        return self._revisions[job_id].get(revision) if revision else None

    def list_repair_jobs(self, *, project_id: str | None = None) -> list[ProductRepairJob]:
        values = [self.get_repair_job(job_id) for job_id in self._current]
        return sorted(
            [
                value
                for value in values
                if value is not None
                and (project_id is None or value.project_id == project_id)
            ],
            key=lambda item: (item.meta.created_at, item.job_id),
        )


@dataclass(frozen=True)
class RepairFailureContext:
    """The only failure information exposed to a planner."""

    failure_step: str
    failure_code: str
    failure_summary: str
    execution_job_revision_id: str
    generation_job_revision_id: str


@dataclass(frozen=True)
class RepairPlan:
    diagnosis: str
    patches: tuple[RepairPatch, ...] = ()


class RepairPlanner(Protocol):
    def plan(
        self, context: RepairFailureContext, *, workspace: Path, manifest: GenerationManifest
    ) -> RepairPlan: ...


class DeterministicRepairPlanner:
    """Known, conservative repairs for the checked-in React template.

    The planner deliberately declines unknown failures.  It never edits tests,
    package scripts, lockfiles, or dependency declarations.
    """

    def plan(
        self, context: RepairFailureContext, *, workspace: Path, manifest: GenerationManifest
    ) -> RepairPlan:
        app_path = workspace / "src" / "App.tsx"
        if not app_path.is_file() or app_path.is_symlink():
            return RepairPlan("No allowlisted source file is available for this failure.")
        raw = app_path.read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        # B4 launches preview and browser together; a browser-side failure is
        # therefore reported at the `run` checkpoint until the step summary is
        # persisted.  Treat both checkpoints as the browser validation phase.
        if context.failure_step in {"run", "browser"} and context.failure_code in {"command_failed", "browser_failed", "axe_failed"}:
            search = '<p role="status" data-state-kind='
            if search in raw and 'aria-live="polite"' not in raw:
                return RepairPlan(
                    "Add a polite live-region announcement to the generated status state.",
                    (
                        RepairPatch(
                            path="src/App.tsx",
                            expected_sha256=digest,
                            search=search,
                            replace='<p role="status" aria-live="polite" data-state-kind=',
                            rationale="Make status changes discoverable without increasing intervention intensity.",
                        ),
                    ),
                )
        if context.failure_step == "build" and context.failure_code == "command_failed":
            search = "useState<'ready' | 'success' | 'stopped'>('ready')"
            if search in raw:
                return RepairPlan(
                    "Restore the template error state required by the deterministic browser contract.",
                    (
                        RepairPatch(
                            path="src/App.tsx",
                            expected_sha256=digest,
                            search=search,
                            replace="useState<'ready' | 'success' | 'stopped' | 'error'>('ready')",
                            rationale="Keep the generated state union aligned with the fixed contract checks.",
                        ),
                    ),
                )
        return RepairPlan("No deterministic allowlisted repair is known for this failure.")


_REPAIRABLE_PATHS = {"src/App.tsx", "src/styles.css"}


class ProductRepairJobService:
    """Create a child workspace and execute only validated repair patches."""

    def __init__(
        self,
        application,
        job_repository: ProductRepairJobRepository,
        generation_repository: ProductGenerationJobRepository,
        execution_repository: ProductExecutionJobRepository,
        execution_service: ProductExecutionJobService,
        *,
        workspace_root: Path | str = Path("output/product-studio/workspaces"),
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
        planner: RepairPlanner | None = None,
    ) -> None:
        self.application = application
        self.job_repository = job_repository
        self.generation_repository = generation_repository
        self.execution_repository = execution_repository
        self.execution_service = execution_service
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._root = self.workspace_root.resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")
        self.planner = planner or DeterministicRepairPlanner()

    def create_job(
        self,
        *,
        project_id: str,
        execution_job_id: str,
        actor: str,
        reason: str,
        budget: RepairBudget | None = None,
    ) -> ProductRepairJob:
        self.application.get_project_view(project_id)
        execution = self.execution_repository.get_execution_job(execution_job_id)
        self._check_execution(project_id, execution)
        assert execution is not None
        selected_budget = budget or RepairBudget()
        dependency = DependencyRef(
            object_type="product_execution_job",
            object_id=execution.job_id,
            revision=execution.meta.revision,
        )
        fingerprint = _fingerprint(project_id, dependency, selected_budget)
        reusable = next(
            (
                item
                for item in reversed(self.job_repository.list_repair_jobs(project_id=project_id))
                if item.fingerprint == fingerprint
                and item.status in {
                    "queued",
                    "running",
                    "succeeded",
                    "failed",
                    "stale_input",
                    "budget_exhausted",
                }
            ),
            None,
        )
        if reusable:
            return reusable
        job_id = self._id("repair-job")
        job = ProductRepairJob(
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
            execution_job_id=execution.job_id,
            execution_job_revision_id=execution.revision_id,
            generation_job_id=execution.generation_job_id,
            generation_job_revision_id=execution.generation_job_revision_id,
            budget=selected_budget,
            fingerprint=fingerprint,
        )
        return self.job_repository.save_repair_job(job, expected_revision=None)

    def get_job(self, project_id: str, job_id: str) -> ProductRepairJob:
        job = self.job_repository.get_repair_job(job_id)
        if job is None:
            raise DomainStateError(f"unknown product repair job: {job_id}")
        if job.project_id != project_id:
            raise DomainStateError(f"product repair job belongs to project {job.project_id}, not {project_id}")
        return job

    def list_jobs(self, project_id: str) -> tuple[ProductRepairJob, ...]:
        self.application.get_project_view(project_id)
        return tuple(self.job_repository.list_repair_jobs(project_id=project_id))

    def run_job(self, project_id: str, job_id: str, *, actor: str) -> ProductRepairJob:
        job = self.get_job(project_id, job_id)
        if job.status == "succeeded":
            return job
        if job.status != "queued":
            raise DomainStateError(f"product repair job cannot run from status {job.status}")
        if job.attempt >= job.budget.max_attempts or job.consumed_cost_units >= job.budget.max_cost_units:
            return self._transition(
                job,
                status="budget_exhausted",
                actor=actor,
                reason="repair budget exhausted",
                error_code="budget_exhausted",
                error_summary="The repair budget was exhausted before another attempt.",
            )
        execution = self.execution_repository.get_execution_job(job.execution_job_id)
        try:
            self._check_execution(project_id, execution)
        except DomainStateError:
            return self._transition(
                job,
                status="stale_input",
                actor=actor,
                reason="failed execution revision is no longer available",
                error_code="stale_input",
                error_summary="The repair input execution revision is no longer the current failed result.",
            )
        assert execution is not None
        if execution.meta.revision != job.input_dependencies[0].revision:
            return self._transition(
                job,
                status="stale_input",
                actor=actor,
                reason="failed execution revision changed",
                error_code="stale_input",
                error_summary="The failed execution changed after this repair was queued.",
            )
        generation = self.generation_repository.get_generation_job(execution.generation_job_id)
        if generation is None or generation.meta.revision != execution.input_dependencies[0].revision:
            return self._transition(
                job,
                status="stale_input",
                actor=actor,
                reason="source generation revision changed",
                error_code="stale_input",
                error_summary="The source generation revision is no longer the pinned input.",
            )
        workspace = self._workspace_path(execution.workspace_relative_path)
        try:
            self.execution_service._validate_workspace(workspace, generation)
            manifest = generation.manifest
            if manifest is None:
                raise DomainStateError("source generation has no manifest")
        except DomainStateError:
            return self._finish_unsupported(
                job,
                actor=actor,
                attempt_number=job.attempt + 1,
                failure_step=_failure_step(execution),
                failure_code="sandbox_violation",
                diagnosis="The source workspace failed integrity validation before repair.",
                error_code="sandbox_violation",
                error_summary="The repair source workspace failed execution integrity checks.",
            )

        running = self._transition(
            job,
            status="running",
            actor=actor,
            reason="repair worker claimed job",
            attempt=job.attempt + 1,
            consumed_cost_units=job.consumed_cost_units + 1,
        )
        attempt_number = running.attempt
        context = RepairFailureContext(
            failure_step=_failure_step(execution),
            failure_code=execution.error_code or "unknown_failure",
            failure_summary=execution.error_summary or "The execution failed without a safe summary.",
            execution_job_revision_id=execution.revision_id,
            generation_job_revision_id=generation.revision_id,
        )
        try:
            plan = self.planner.plan(context, workspace=workspace, manifest=manifest)
            self._validate_plan(plan, manifest, workspace, running.budget)
            if not plan.patches:
                return self._finish_attempt(
                    running,
                    actor=actor,
                    attempt_number=attempt_number,
                    context=context,
                    diagnosis=plan.diagnosis,
                    patches=(),
                    status="unsupported",
                    error_code="unsupported_failure",
                    error_summary="No deterministic allowlisted repair is available for this failure.",
                    final_status="failed",
                )
            repair_generation = self._materialize_repair_generation(
                running, generation, manifest, plan, actor=actor, attempt_number=attempt_number
            )
            repair_execution = self.execution_service.create_job(
                project_id=project_id,
                generation_job_id=repair_generation.job_id,
                actor=actor,
                reason="Validate B5 repaired workspace",
            )
            checked = self.execution_service.run_job(project_id, repair_execution.job_id, actor=actor)
            if checked.status == "succeeded":
                return self._finish_attempt(
                    running,
                    actor=actor,
                    attempt_number=attempt_number,
                    context=context,
                    diagnosis=plan.diagnosis,
                    patches=plan.patches,
                    status="verified",
                    output_generation_job_id=repair_generation.job_id,
                    output_execution_job_id=checked.job_id,
                    final_status="succeeded",
                    latest_generation_job_id=repair_generation.job_id,
                    latest_execution_job_id=checked.job_id,
                )
            return self._finish_attempt(
                running,
                actor=actor,
                attempt_number=attempt_number,
                context=context,
                diagnosis=plan.diagnosis,
                patches=plan.patches,
                status="failed",
                output_generation_job_id=repair_generation.job_id,
                output_execution_job_id=checked.job_id,
                error_code="repair_validation_failed",
                error_summary="The repaired workspace did not pass the bounded execution checks.",
            )
        except (ProductRepositoryError, DomainStateError):
            raise
        except RepairValidationError as exc:
            return self._finish_attempt(
                running,
                actor=actor,
                attempt_number=attempt_number,
                context=context,
                diagnosis=exc.diagnosis,
                patches=exc.patches,
                status="failed",
                error_code=exc.code,
                error_summary=exc.summary,
            )
        except Exception:
            return self._finish_attempt(
                running,
                actor=actor,
                attempt_number=attempt_number,
                context=context,
                diagnosis="The repair planner or materializer failed safely.",
                patches=(),
                status="failed",
                error_code="repair_failed",
                error_summary="The repair attempt could not be applied safely.",
            )

    def retry_job(self, project_id: str, job_id: str, *, actor: str) -> ProductRepairJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"failed", "stale_input", "budget_exhausted"}:
            raise DomainStateError("only failed repair jobs can be retried")
        if any(
            item.status == "unsupported" or item.error_code == "unsupported_failure"
            for item in job.attempts
        ):
            raise DomainStateError(
                "the deterministic planner has no allowlisted patch for this failure; "
                "do not retry the same repair job"
            )
        if job.attempt >= job.budget.max_attempts or job.consumed_cost_units >= job.budget.max_cost_units:
            return self._transition(
                job,
                status="budget_exhausted",
                actor=actor,
                reason="repair retry exceeds budget",
                error_code="budget_exhausted",
                error_summary="The repair retry budget was exhausted.",
            )
        return self._transition(job, status="queued", actor=actor, reason="repair retry requested")

    def cancel_job(self, project_id: str, job_id: str, *, actor: str) -> ProductRepairJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"queued", "running"}:
            raise DomainStateError("only active repair jobs can be cancelled")
        return self._transition(job, status="cancelled", actor=actor, reason="repair cancelled by user")

    def _check_execution(self, project_id: str, execution: ProductExecutionJob | None) -> None:
        if execution is None:
            raise DomainStateError("unknown product execution job")
        if execution.project_id != project_id:
            raise DomainStateError("product execution job belongs to another project")
        if execution.status not in {"failed", "budget_exhausted"}:
            raise DomainStateError("a failed execution job is required before repair")
        if execution.error_code is None:
            raise DomainStateError("failed execution has no safe diagnostic")

    def _workspace_path(self, relative: str) -> Path:
        candidate = (self._root / relative).resolve(strict=False)
        try:
            if os.path.commonpath((str(self._root), str(candidate))) != str(self._root):
                raise ValueError
        except ValueError as exc:
            raise DomainStateError("repair workspace is outside the configured root") from exc
        return candidate

    def _validate_plan(
        self,
        plan: RepairPlan,
        manifest: GenerationManifest,
        workspace: Path,
        budget: RepairBudget,
    ) -> None:
        if len(plan.diagnosis) > 240 or not plan.diagnosis:
            raise RepairValidationError("repair_failed", "Repair diagnosis is missing or too long.", diagnosis="Invalid repair diagnosis.")
        if len(plan.patches) > budget.max_patches:
            raise RepairValidationError("patch_limit", "The repair proposed too many file changes.", diagnosis="Repair patch count exceeded the budget.")
        declared = {item.path: item for item in manifest.files}
        total_patch_bytes = sum(len(item.search.encode()) + len(item.replace.encode()) for item in plan.patches)
        if total_patch_bytes > budget.max_patch_bytes:
            raise RepairValidationError("patch_limit", "The repair patch exceeded its byte budget.", diagnosis="Repair patch bytes exceeded the budget.")
        for patch in plan.patches:
            normalized = patch.path.replace("\\", "/")
            if normalized != patch.path or normalized not in _REPAIRABLE_PATHS or normalized not in declared:
                raise RepairValidationError("patch_path_denied", "The repair path is not allowlisted.", diagnosis="Repair targeted a non-source path.", patches=plan.patches)
            target = workspace / normalized
            if target.is_symlink() or not target.is_file():
                raise RepairValidationError("patch_path_denied", "The repair source file is unavailable.", diagnosis="Repair source file was not a regular file.", patches=plan.patches)
            raw = target.read_bytes()
            if hashlib.sha256(raw).hexdigest() != patch.expected_sha256:
                raise RepairValidationError("patch_stale", "The repair source hash no longer matches.", diagnosis="Repair patch was based on a stale file revision.", patches=plan.patches)
            text = raw.decode("utf-8")
            if text.count(patch.search) != 1:
                raise RepairValidationError("patch_ambiguous", "The repair search text was not unique.", diagnosis="Repair search text was missing or ambiguous.", patches=plan.patches)

    def _materialize_repair_generation(
        self,
        job: ProductRepairJob,
        source: ProductGenerationJob,
        manifest: GenerationManifest,
        plan: RepairPlan,
        *,
        actor: str,
        attempt_number: int,
    ) -> ProductGenerationJob:
        source_workspace = self._workspace_path(source.workspace_relative_path)
        output_job_id = self._id("generation-repair")
        relative = "/".join(("repairs", _safe_segment(job.project_id), _safe_segment(job.job_id), f"attempt-{attempt_number}", _safe_segment(output_job_id)))
        final = self._workspace_path(relative)
        if final.exists():
            raise RepairValidationError("workspace_exists", "The repair workspace already exists.", diagnosis="Repair workspace collision.")
        temporary = Path(tempfile.mkdtemp(prefix=f".{_safe_segment(output_job_id)}-", dir=self._root))
        try:
            for item in manifest.files:
                source_path = source_workspace / item.path
                if source_path.is_symlink() or not source_path.is_file():
                    raise RepairValidationError("sandbox_violation", "The repair source contains an invalid file.", diagnosis="Repair source integrity check failed.")
                target = temporary / item.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source_path.read_bytes())
            for patch in plan.patches:
                target = temporary / patch.path
                text = target.read_text(encoding="utf-8")
                target.write_text(text.replace(patch.search, patch.replace, 1), encoding="utf-8", newline="\n")
            generated = tuple(
                GeneratedFile(
                    path=item.path,
                    byte_count=(temporary / item.path).stat().st_size,
                    sha256=hashlib.sha256((temporary / item.path).read_bytes()).hexdigest(),
                )
                for item in manifest.files
            )
            repaired_manifest = GenerationManifest(
                files=generated,
                total_bytes=sum(item.byte_count for item in generated),
            )
            (temporary / "generation-manifest.json").write_text(
                repaired_manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        try:
            repair_generation = ProductGenerationJob(
                job_id=output_job_id,
                revision_id=f"{output_job_id}.r1",
                meta=RevisionMeta(
                    revision=1,
                    created_at=self._now(),
                    created_by=actor,
                    reason="B5 allowlisted repair materialized",
                ),
                project_id=job.project_id,
                provider="deterministic_repair",
                provider_version=REPAIR_JOB_VERSION,
                input_dependencies=source.input_dependencies,
                web_generation_contract_revision_id=source.web_generation_contract_revision_id,
                workspace_id=output_job_id,
                workspace_relative_path=relative,
                budget=source.budget,
                sandbox=source.sandbox,
                fingerprint=_repair_generation_fingerprint(job, source, attempt_number),
                materialization_kind="repair",
                parent_generation_job_id=source.job_id,
                repair_job_id=job.job_id,
                attempt=1,
                checkpoint_step="validate",
                consumed_files=len(repaired_manifest.files),
                consumed_bytes=repaired_manifest.total_bytes,
                consumed_cost_units=1,
                manifest=repaired_manifest,
                status="succeeded",
            )
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        try:
            final.parent.mkdir(parents=True, exist_ok=True)
            temporary.rename(final)
            return self.generation_repository.save_generation_job(
                repair_generation, expected_revision=None
            )
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            if final.exists():
                shutil.rmtree(final)
            raise

    def _finish_unsupported(
        self,
        job: ProductRepairJob,
        *,
        actor: str,
        attempt_number: int,
        failure_step: str,
        failure_code: str,
        diagnosis: str,
        error_code: str,
        error_summary: str,
    ) -> ProductRepairJob:
        running = self._transition(job, status="running", actor=actor, reason="repair worker claimed job", attempt=attempt_number, consumed_cost_units=job.consumed_cost_units + 1)
        context = RepairFailureContext(failure_step=failure_step, failure_code=failure_code, failure_summary=error_summary, execution_job_revision_id=job.execution_job_revision_id, generation_job_revision_id=job.generation_job_revision_id)
        return self._finish_attempt(running, actor=actor, attempt_number=attempt_number, context=context, diagnosis=diagnosis, patches=(), status="failed", error_code=error_code, error_summary=error_summary)

    def _finish_attempt(
        self,
        current: ProductRepairJob,
        *,
        actor: str,
        attempt_number: int,
        context: RepairFailureContext,
        diagnosis: str,
        patches: Sequence[RepairPatch],
        status: str,
        error_code: str | None = None,
        error_summary: str | None = None,
        output_generation_job_id: str | None = None,
        output_execution_job_id: str | None = None,
        final_status: str | None = None,
        latest_generation_job_id: str | None = None,
        latest_execution_job_id: str | None = None,
    ) -> ProductRepairJob:
        attempt = RepairAttempt(
            attempt=attempt_number,
            execution_job_revision_id=context.execution_job_revision_id,
            failure_step=context.failure_step,  # type: ignore[arg-type]
            failure_code=context.failure_code,
            diagnosis=diagnosis,
            patches=tuple(patches),
            status=status,  # type: ignore[arg-type]
            cost_units=1,
            output_generation_job_id=output_generation_job_id,
            output_execution_job_id=output_execution_job_id,
            error_code=error_code,
            error_summary=error_summary,
        )
        attempts = (*current.attempts, attempt)
        resolved_status = final_status or ("budget_exhausted" if current.attempt >= current.budget.max_attempts or current.consumed_cost_units >= current.budget.max_cost_units else "failed")
        return self._transition(
            current,
            status=resolved_status,
            actor=actor,
            reason="repair attempt verified" if resolved_status == "succeeded" else "repair attempt completed",
            attempts=attempts,
            latest_generation_job_id=latest_generation_job_id or output_generation_job_id,
            latest_execution_job_id=latest_execution_job_id or output_execution_job_id,
            error_code=None if resolved_status == "succeeded" else (error_code or "repair_failed"),
            error_summary=None if resolved_status == "succeeded" else (error_summary or "The repair attempt did not complete."),
        )

    def _transition(self, current: ProductRepairJob, *, status: str, actor: str, reason: str, **updates) -> ProductRepairJob:
        revision = current.meta.revision + 1
        values = {
            **updates,
            "status": status,
            "revision_id": f"{current.job_id}.r{revision}",
            "meta": RevisionMeta(
                revision=revision,
                parent_revision_id=current.revision_id,
                created_at=self._now(),
                created_by=actor,
                reason=reason,
            ),
        }
        if status not in {"failed", "budget_exhausted", "stale_input"}:
            values.setdefault("error_code", None)
            values.setdefault("error_summary", None)
        return self.job_repository.save_repair_job(current.model_copy(update=values), expected_revision=current.meta.revision)

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("repair identifier cannot be empty")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("repair clock must be timezone-aware")
        return value


class RepairValidationError(RuntimeError):
    def __init__(
        self,
        code: str,
        summary: str,
        *,
        diagnosis: str,
        patches: Sequence[RepairPatch] = (),
    ) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.diagnosis = diagnosis
        self.patches = tuple(patches)


def _failure_step(execution: ProductExecutionJob) -> str:
    for step in execution.steps:
        if step.status == "failed":
            return step.name
    return execution.checkpoint_step or "browser"


def _safe_segment(value: str) -> str:
    if value and all(char.isalnum() or char in "._-" for char in value) and len(value) <= 80:
        return value
    return "id-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _fingerprint(project_id: str, dependency: DependencyRef, budget: RepairBudget) -> str:
    payload = {
        "project_id": project_id,
        "dependency": dependency.model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
        "provider": "deterministic_repair",
        "version": REPAIR_JOB_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _repair_generation_fingerprint(job: ProductRepairJob, source: ProductGenerationJob, attempt: int) -> str:
    payload = {
        "repair_job": job.job_id,
        "repair_revision": job.revision_id,
        "source_generation": source.revision_id,
        "attempt": attempt,
        "provider": REPAIR_JOB_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_repair_job_revision(
    current: ProductRepairJob | None,
    value: ProductRepairJob,
    expected_revision: int | None,
) -> None:
    if current is None:
        if expected_revision is not None or value.meta.revision != 1:
            raise ProductRepositoryError("repair job first revision conflict")
        return
    if expected_revision != current.meta.revision:
        raise ProductRepositoryError(
            f"revision conflict: expected {expected_revision}, current {current.meta.revision}"
        )
    if value.meta.revision != current.meta.revision + 1 or value.meta.parent_revision_id != current.revision_id:
        raise ProductRepositoryError("repair job revisions must increase by one and reference current parent")
