"""Persistent proposal jobs and worker-compatible execution service."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import ValidationError

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.commands import (
    SubmitOutcomeContractProposal,
    SubmitProblemModelProposal,
    SubmitProductIntentProposal,
    SubmitProductThesisProposal,
    SubmitWebProductGenerationContractProposal,
)
from psyteardown.product.models import (
    OutcomeContract,
    PreviewFeedback,
    ProblemModel,
    ProductIntent,
    ProductProposalJob,
    ProductThesis,
    WebProductGenerationContract,
    PRODUCT_INTENT_MAX_INPUT_CHARS,
)
from psyteardown.product.providers import (
    DeterministicFakeProductContractProvider,
    ProductContractProposalProvider,
)
from psyteardown.product.repositories import ProductRepositoryError
from psyteardown.product.service import ProductApplicationService


class ProductJobRepository(Protocol):
    def save_job(
        self, job: ProductProposalJob, *, expected_revision: int | None
    ) -> ProductProposalJob: ...

    def get_job(self, job_id: str) -> ProductProposalJob | None: ...

    def list_jobs(self, *, project_id: str | None = None) -> list[ProductProposalJob]: ...


class PreviewFeedbackReader(Protocol):
    def get_preview_feedback(self, feedback_id: str) -> PreviewFeedback | None: ...


class InMemoryProductJobRepository:
    def __init__(self) -> None:
        self._revisions: dict[str, dict[int, ProductProposalJob]] = defaultdict(dict)
        self._current: dict[str, int] = {}

    def save_job(
        self, job: ProductProposalJob, *, expected_revision: int | None
    ) -> ProductProposalJob:
        current = self.get_job(job.job_id)
        _validate_job_revision(current, job, expected_revision)
        self._revisions[job.job_id][job.meta.revision] = job
        self._current[job.job_id] = job.meta.revision
        return job

    def get_job(self, job_id: str) -> ProductProposalJob | None:
        revision = self._current.get(job_id)
        return self._revisions[job_id].get(revision) if revision else None

    def list_jobs(self, *, project_id: str | None = None) -> list[ProductProposalJob]:
        values = [self.get_job(job_id) for job_id in self._current]
        return sorted(
            [value for value in values if value and (project_id is None or value.project_id == project_id)],
            key=lambda item: item.meta.created_at,
        )


class ProductProposalJobService:
    def __init__(
        self,
        application: ProductApplicationService,
        job_repository: ProductJobRepository,
        *,
        provider: ProductContractProposalProvider | None = None,
        real_provider: ProductContractProposalProvider | None = None,
        feedback_repository: PreviewFeedbackReader | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.application = application
        self.job_repository = job_repository
        # B8 iteration jobs pin preview feedback, which lives outside the
        # product repository; without a reader they are simply unavailable.
        self.feedback_repository = feedback_repository
        self.provider = provider or DeterministicFakeProductContractProvider()
        self.real_provider = real_provider  # C0: optional real model provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")

    def create_job(
        self,
        *,
        project_id: str,
        kind: Literal[
            "product_intent",
            "problem_model",
            "outcome_contract",
            "product_theses",
            "web_generation_contract",
        ],
        actor: str,
        reason: str,
        raw_input: str | None = None,
        feedback_id: str | None = None,
        provider: Literal["deterministic_fake", "real"] = "deterministic_fake",
    ) -> ProductProposalJob:
        view = self.application.get_project_view(project_id)
        if view.project.status != "active":
            raise DomainStateError("product project must be active for proposal jobs")
        result_expected_revision: int | None = None
        if kind == "product_intent":
            if feedback_id is not None:
                raise DomainStateError("feedback_id is only accepted for web_generation_contract jobs")
            if view.product_intent is not None:
                raise DomainStateError(
                    "project already has a current product intent; revise it through a domain command"
                )
            if not raw_input or not raw_input.strip():
                raise DomainStateError("product intent proposal job requires raw input")
            dependencies = (
                DependencyRef(
                    object_type="product_project",
                    object_id=view.project.project_id,
                    revision=view.project.meta.revision,
                ),
            )
            result_object_id = self._id("intent")
            result_object_ids: tuple[str, ...] = ()
            raw_input = raw_input.strip()
            if len(raw_input) > PRODUCT_INTENT_MAX_INPUT_CHARS:
                raise DomainStateError(f"product intent raw input must be at most {PRODUCT_INTENT_MAX_INPUT_CHARS} characters")
        elif kind == "problem_model":
            if raw_input is not None:
                raise DomainStateError("raw input is only accepted for product intent jobs")
            if feedback_id is not None:
                raise DomainStateError("feedback_id is only accepted for web_generation_contract jobs")
            intent = view.product_intent
            if intent is None or intent.status != "confirmed":
                raise DomainStateError(
                    "product intent must be human-confirmed before problem proposal generation"
                )
            if view.problem_model is not None:
                raise DomainStateError(
                    "project already has a current problem model; revise it through a domain command"
                )
            dependencies = (
                DependencyRef(
                    object_type="product_intent",
                    object_id=intent.intent_id,
                    revision=intent.meta.revision,
                ),
            )
            result_object_id = self._id("problem")
            result_object_ids = ()
        elif kind == "outcome_contract":
            if raw_input is not None:
                raise DomainStateError("raw input is only accepted for product intent jobs")
            if feedback_id is not None:
                raise DomainStateError("feedback_id is only accepted for web_generation_contract jobs")
            intent = view.product_intent
            problem = view.problem_model
            if intent is None or intent.status != "confirmed":
                raise DomainStateError(
                    "product intent must be human-confirmed before outcome proposal generation"
                )
            if problem is None or problem.status != "confirmed":
                raise DomainStateError(
                    "problem model must be human-confirmed before outcome proposal generation"
                )
            if view.outcome_contract is not None:
                raise DomainStateError(
                    "project already has a current outcome contract; revise it through a domain command"
                )
            dependencies = (
                DependencyRef(
                    object_type="product_intent",
                    object_id=intent.intent_id,
                    revision=intent.meta.revision,
                ),
                DependencyRef(
                    object_type="problem_model",
                    object_id=problem.problem_model_id,
                    revision=problem.meta.revision,
                ),
            )
            result_object_id = self._id("contract")
            result_object_ids = ()
        elif kind == "product_theses":
            if raw_input is not None:
                raise DomainStateError("raw input is only accepted for product intent jobs")
            if feedback_id is not None:
                raise DomainStateError("feedback_id is only accepted for web_generation_contract jobs")
            problem = view.problem_model
            contract = view.outcome_contract
            if problem is None or problem.status != "confirmed":
                raise DomainStateError(
                    "problem model must be human-confirmed before product thesis generation"
                )
            if contract is None or contract.status != "confirmed":
                raise DomainStateError(
                    "outcome contract must be human-confirmed before product thesis generation"
                )
            if contract.problem_model_revision_id != problem.revision_id:
                raise DomainStateError(
                    "current outcome contract and problem model revisions do not match"
                )
            dependencies = (
                DependencyRef(
                    object_type="problem_model",
                    object_id=problem.problem_model_id,
                    revision=problem.meta.revision,
                ),
                DependencyRef(
                    object_type="outcome_contract",
                    object_id=contract.outcome_contract_id,
                    revision=contract.meta.revision,
                ),
            )
            result_object_ids = tuple(self._id("thesis") for _ in range(3))
            result_object_id = result_object_ids[0]
        elif kind == "web_generation_contract":
            if raw_input is not None:
                raise DomainStateError("raw input is only accepted for product intent jobs")
            if feedback_id is not None:
                feedback = self._require_feedback(project_id, feedback_id)
                baseline = view.web_generation_contract
                if baseline is None or baseline.status != "confirmed":
                    raise DomainStateError(
                        "a confirmed Web generation contract is required before iterating from feedback"
                    )
                if baseline.revision_id != feedback.web_generation_contract_revision_id:
                    raise DomainStateError(
                        "feedback was given on a different contract revision than the current confirmed contract"
                    )
                dependencies = (
                    DependencyRef(
                        object_type="web_generation_contract",
                        object_id=baseline.web_generation_contract_id,
                        revision=baseline.meta.revision,
                    ),
                    DependencyRef(
                        object_type="preview_feedback",
                        object_id=feedback.feedback_id,
                        revision=feedback.meta.revision,
                    ),
                )
                result_object_ids = ()
                result_object_id = baseline.web_generation_contract_id
                result_expected_revision = baseline.meta.revision
            else:
                thesis = next(
                    (
                        item
                        for item in view.product_theses
                        if item.status in {"exploring", "selected"}
                    ),
                    None,
                )
                outcome = view.outcome_contract
                if thesis is None:
                    raise DomainStateError(
                        "an exploring or selected product thesis is required before Web generation"
                    )
                if outcome is None or outcome.status != "confirmed":
                    raise DomainStateError(
                        "outcome contract must be human-confirmed before Web generation"
                    )
                if thesis.outcome_contract_revision_id != outcome.revision_id:
                    raise DomainStateError(
                        "current thesis and outcome contract revisions do not match"
                    )
                dependencies = (
                    DependencyRef(
                        object_type="product_thesis",
                        object_id=thesis.thesis_id,
                        revision=thesis.meta.revision,
                    ),
                    DependencyRef(
                        object_type="outcome_contract",
                        object_id=outcome.outcome_contract_id,
                        revision=outcome.meta.revision,
                    ),
                )
                result_object_ids = ()
                result_object_id = self._id("web-contract")
        else:
            raise DomainStateError(f"unknown job kind: {kind}")

        # C0: Select provider based on parameter
        if provider == "real":
            if self.real_provider is None:
                raise DomainStateError("real provider is not configured")
            selected_provider = self.real_provider
        else:
            selected_provider = self.provider

        fingerprint = _fingerprint(
            project_id,
            kind,
            dependencies,
            selected_provider.name,
            selected_provider.version,
            raw_input=raw_input,
        )
        reusable = next(
            (
                job
                for job in reversed(self.job_repository.list_jobs(project_id=project_id))
                if job.fingerprint == fingerprint and job.status in {"queued", "running", "succeeded"}
            ),
            None,
        )
        if reusable:
            return reusable
        job_id = self._id("proposal-job")
        job = ProductProposalJob(
            job_id=job_id,
            revision_id=f"{job_id}.r1",
            meta=RevisionMeta(
                revision=1,
                created_at=self._now(),
                created_by=actor,
                reason=reason,
            ),
            project_id=project_id,
            kind=kind,
            provider=provider,
            provider_version=selected_provider.version,
            input_dependencies=dependencies,
            result_object_id=result_object_id,
            result_object_ids=result_object_ids,
            result_expected_revision=result_expected_revision,
            raw_input=raw_input,
            feedback_id=feedback_id,
            fingerprint=fingerprint,
        )
        return self.job_repository.save_job(job, expected_revision=None)

    def get_job(self, project_id: str, job_id: str) -> ProductProposalJob:
        job = self.job_repository.get_job(job_id)
        if job is None:
            raise DomainStateError(f"unknown product proposal job: {job_id}")
        if job.project_id != project_id:
            raise DomainStateError(
                f"product proposal job belongs to project {job.project_id}, not {project_id}"
            )
        return job

    def list_jobs(self, project_id: str) -> tuple[ProductProposalJob, ...]:
        self.application.get_project_view(project_id)
        return tuple(self.job_repository.list_jobs(project_id=project_id))

    def run_job(self, project_id: str, job_id: str, *, actor: str) -> ProductProposalJob:
        job = self.get_job(project_id, job_id)
        if job.status == "succeeded":
            return job
        if job.status not in {"queued", "running"}:
            raise DomainStateError(
                f"product proposal job cannot run from status {job.status}"
            )
        reconciled = self._reconcile_committed_result(job, actor=actor)
        if reconciled:
            return reconciled
        if not self._inputs_are_current(job):
            return self._transition(job, status="stale_input", actor=actor, reason="pinned input revision changed")
        running = self._transition(
            job,
            status="running",
            actor=actor,
            reason="proposal worker claimed job",
            attempt=job.attempt + 1,
        )
        try:
            result = self._produce_and_commit(running, actor=actor)
        except ProductRepositoryError:
            if not self._inputs_are_current(running):
                return self._transition(
                    running,
                    status="stale_input",
                    actor=actor,
                    reason="input changed before proposal commit",
                )
            return self._transition(
                running,
                status="failed",
                actor=actor,
                reason="proposal commit conflict",
                error_code="proposal_commit_conflict",
                error_summary="The proposal could not be committed because its target changed.",
            )
        except Exception as exc:
            # Keep provider internals out of API responses, but retain a small
            # safe class hint so real-provider failures can be diagnosed.
            error_code = "provider_failed"
            error_summary = (
                "The proposal provider failed without committing a result "
                f"({type(exc).__name__})."
            )
            detail = str(exc)
            if detail.startswith("static_gate_rejected:"):
                error_code = "static_gate_rejected"
                error_summary = detail[:500]
            elif detail.startswith("provider_failed:"):
                error_summary = detail[:500]
            elif isinstance(exc, ValidationError):
                issues = "; ".join(
                    f"{'.'.join(str(part) for part in item.get('loc', ())) or 'value'}: {item.get('msg', 'invalid')}"
                    for item in exc.errors()[:5]
                )
                error_code = "provider_schema_invalid"
                error_summary = f"The provider proposal did not satisfy the local schema: {issues}"[:500]
            return self._transition(
                running,
                status="failed",
                actor=actor,
                reason="provider execution failed",
                error_code=error_code,
                error_summary=error_summary,
            )
        return self._transition(
            running,
            status="succeeded",
            actor=actor,
            reason="proposal committed",
            result_revision_id=(
                result[0].revision_id if isinstance(result, tuple) else result.revision_id
            ),
            result_revision_ids=(
                tuple(item.revision_id for item in result)
                if isinstance(result, tuple)
                else ()
            ),
        )

    def retry_job(self, project_id: str, job_id: str, *, actor: str) -> ProductProposalJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"failed", "stale_input"}:
            raise DomainStateError("only failed or stale proposal jobs can be retried")
        if not self._inputs_are_current(job):
            raise DomainStateError("proposal job inputs are no longer current; create a new job")
        return self._transition(job, status="queued", actor=actor, reason="proposal job retry requested")

    def _produce_and_commit(
        self, job: ProductProposalJob, *, actor: str
    ) -> ProductIntent | ProblemModel | OutcomeContract | WebProductGenerationContract | tuple[ProductThesis, ...]:
        dependencies = {item.object_type: item for item in job.input_dependencies}

        # C0: Select provider based on job's provider field
        if job.provider == "real":
            if self.real_provider is None:
                raise DomainStateError("real provider is not configured")
            selected_provider = self.real_provider
        else:
            selected_provider = self.provider

        provider_actor = f"provider:{selected_provider.name}"
        if job.kind == "product_intent":
            assert job.raw_input is not None
            proposal = selected_provider.propose_intent(job.raw_input, job_id=job.job_id)
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            return self.application.submit_product_intent(
                SubmitProductIntentProposal(
                    project_id=job.project_id,
                    intent_id=job.result_object_id,
                    proposal=proposal,
                    actor=provider_actor,
                    reason=f"proposal generated by job {job.job_id}",
                )
            )
        if job.kind == "problem_model":
            intent_ref = dependencies["product_intent"]
            intent = self.application.repository.get_revision(
                "product_intent", f"{intent_ref.object_id}.r{intent_ref.revision}"
            )
            assert isinstance(intent, ProductIntent)
            proposal = selected_provider.propose_problem(intent, job_id=job.job_id)
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            return self.application.submit_problem_model(
                SubmitProblemModelProposal(
                    project_id=job.project_id,
                    problem_model_id=job.result_object_id,
                    proposal=proposal,
                    actor=provider_actor,
                    reason=f"proposal generated by job {job.job_id}",
                )
            )
        if job.kind == "web_generation_contract" and job.feedback_id:
            baseline_ref = dependencies["web_generation_contract"]
            feedback_ref = dependencies["preview_feedback"]
            baseline = self.application.repository.get_revision(
                "web_generation_contract", f"{baseline_ref.object_id}.r{baseline_ref.revision}"
            )
            feedback = self._require_feedback(job.project_id, feedback_ref.object_id)
            assert isinstance(baseline, WebProductGenerationContract)
            proposal = selected_provider.propose_web_generation_contract_from_feedback(
                baseline, feedback, suggestion_id=job.job_id
            )
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            return self.application.submit_web_generation_contract(
                SubmitWebProductGenerationContractProposal(
                    project_id=job.project_id,
                    web_generation_contract_id=job.result_object_id,
                    expected_revision=job.result_expected_revision,
                    proposal=proposal,
                    actor=provider_actor,
                    reason=f"proposal generated by job {job.job_id}",
                )
            )
        if job.kind == "web_generation_contract":
            thesis_ref = dependencies["product_thesis"]
            outcome_ref = dependencies["outcome_contract"]
            thesis = self.application.repository.get_revision(
                "product_thesis", f"{thesis_ref.object_id}.r{thesis_ref.revision}"
            )
            outcome = self.application.repository.get_revision(
                "outcome_contract", f"{outcome_ref.object_id}.r{outcome_ref.revision}"
            )
            assert isinstance(thesis, ProductThesis)
            assert isinstance(outcome, OutcomeContract)
            proposal = selected_provider.propose_web_generation_contract(
                thesis, outcome, suggestion_id=job.job_id
            )
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            return self.application.submit_web_generation_contract(
                SubmitWebProductGenerationContractProposal(
                    project_id=job.project_id,
                    web_generation_contract_id=job.result_object_id,
                    proposal=proposal,
                    actor=provider_actor,
                    reason=f"proposal generated by job {job.job_id}",
                )
            )

        problem_ref = dependencies["problem_model"]
        problem = self.application.repository.get_revision(
            "problem_model", f"{problem_ref.object_id}.r{problem_ref.revision}"
        )
        assert isinstance(problem, ProblemModel)
        if job.kind == "outcome_contract":
            intent_ref = dependencies["product_intent"]
            intent = self.application.repository.get_revision(
                "product_intent", f"{intent_ref.object_id}.r{intent_ref.revision}"
            )
            assert isinstance(intent, ProductIntent)
            proposal = selected_provider.propose_outcome_contract(
                intent, problem, job_id=job.job_id
            )
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            return self.application.submit_outcome_contract(
                SubmitOutcomeContractProposal(
                    project_id=job.project_id,
                    outcome_contract_id=job.result_object_id,
                    proposal=proposal,
                    actor=provider_actor,
                    reason=f"proposal generated by job {job.job_id}",
                )
            )

        contract_ref = dependencies["outcome_contract"]
        contract = self.application.repository.get_revision(
            "outcome_contract",
            f"{contract_ref.object_id}.r{contract_ref.revision}",
        )
        assert isinstance(contract, OutcomeContract)
        proposals = selected_provider.propose_theses(
            problem, contract, job_id=job.job_id
        )
        if not 2 <= len(proposals) <= 3:
            raise ValueError("product thesis provider must return two or three proposals")
        differentiators = {
            (proposal.name.casefold(), proposal.differentiation.casefold())
            for proposal in proposals
        }
        if len(differentiators) != len(proposals):
            raise ValueError("product thesis proposals must be meaningfully differentiated")
        if len(job.result_object_ids) != len(proposals):
            raise ValueError("product thesis proposal count changed after job creation")
        if not self._inputs_are_current(job):
            raise ProductRepositoryError("revision conflict: job inputs changed")

        results: list[ProductThesis] = []
        for thesis_id, proposal in zip(job.result_object_ids, proposals, strict=True):
            current = self.application.repository.get_current(
                "product_thesis", thesis_id
            )
            if current is not None:
                if current.meta.reason != f"proposal generated by job {job.job_id}":
                    raise ProductRepositoryError(
                        "revision conflict: thesis target was written by another command"
                    )
                assert isinstance(current, ProductThesis)
                results.append(current)
                continue
            if not self._inputs_are_current(job):
                raise ProductRepositoryError("revision conflict: job inputs changed")
            results.append(
                self.application.submit_product_thesis(
                    SubmitProductThesisProposal(
                        project_id=job.project_id,
                        thesis_id=thesis_id,
                        proposal=proposal,
                        actor=provider_actor,
                        reason=f"proposal generated by job {job.job_id}",
                    )
                )
            )
        return tuple(results)

    def _inputs_are_current(self, job: ProductProposalJob) -> bool:
        for dependency in job.input_dependencies:
            if dependency.object_type == "preview_feedback":
                # Feedback is pinned by identity, not revision: a disposition
                # change keeps it usable, withdrawal makes the job stale.
                feedback = (
                    self.feedback_repository.get_preview_feedback(dependency.object_id)
                    if self.feedback_repository is not None
                    else None
                )
                if feedback is None or feedback.status != "submitted":
                    return False
                continue
            current = self.application.repository.get_current(
                dependency.object_type, dependency.object_id
            )
            if current is None or current.meta.revision != dependency.revision:
                return False
            if dependency.object_type == "product_project":
                if getattr(current, "status", None) != "active":
                    return False
            elif dependency.object_type == "product_thesis":
                if getattr(current, "status", None) not in {"exploring", "selected"}:
                    return False
            elif getattr(current, "status", None) != "confirmed":
                return False
        return True

    def _require_feedback(self, project_id: str, feedback_id: str) -> PreviewFeedback:
        if self.feedback_repository is None:
            raise DomainStateError("preview feedback is not available to proposal jobs")
        feedback = self.feedback_repository.get_preview_feedback(feedback_id)
        if feedback is None or feedback.project_id != project_id:
            raise DomainStateError(f"unknown preview feedback: {feedback_id}")
        if feedback.status != "submitted":
            raise DomainStateError("withdrawn preview feedback cannot drive an iteration")
        return feedback

    def _reconcile_committed_result(
        self, job: ProductProposalJob, *, actor: str
    ) -> ProductProposalJob | None:
        object_type = {
            "product_intent": "product_intent",
            "problem_model": "problem_model",
            "outcome_contract": "outcome_contract",
            "product_theses": "product_thesis",
            "web_generation_contract": "web_generation_contract",
        }[job.kind]
        if job.kind == "product_theses":
            results: list[ProductThesis] = []
            for object_id in job.result_object_ids:
                current = self.application.repository.get_current(
                    object_type, object_id
                )
                if (
                    current is None
                    or current.meta.reason
                    != f"proposal generated by job {job.job_id}"
                ):
                    return None
                assert isinstance(current, ProductThesis)
                results.append(current)
            return self._transition(
                job,
                status="succeeded",
                actor=actor,
                reason="reconciled previously committed thesis proposals",
                result_revision_id=results[0].revision_id,
                result_revision_ids=tuple(item.revision_id for item in results),
            )
        current = self.application.repository.get_current(object_type, job.result_object_id)
        if current is None:
            return None
        if current.meta.reason != f"proposal generated by job {job.job_id}":
            return None
        return self._transition(
            job,
            status="succeeded",
            actor=actor,
            reason="reconciled previously committed proposal",
            result_revision_id=current.revision_id,
        )

    def _transition(
        self,
        current: ProductProposalJob,
        *,
        status: Literal["queued", "running", "succeeded", "failed", "stale_input", "cancelled"],
        actor: str,
        reason: str,
        attempt: int | None = None,
        result_revision_id: str | None = None,
        result_revision_ids: tuple[str, ...] = (),
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> ProductProposalJob:
        revision = current.meta.revision + 1
        updated = current.model_copy(
            update={
                "revision_id": f"{current.job_id}.r{revision}",
                "meta": RevisionMeta(
                    revision=revision,
                    parent_revision_id=current.revision_id,
                    created_at=self._now(),
                    created_by=actor,
                    reason=reason,
                ),
                "status": status,
                "attempt": current.attempt if attempt is None else attempt,
                "result_revision_id": result_revision_id,
                "result_revision_ids": result_revision_ids,
                "error_code": error_code,
                "error_summary": error_summary,
            }
        )
        return self.job_repository.save_job(
            updated, expected_revision=current.meta.revision
        )

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("id_factory returned an empty identifier")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ProductProposalJobService clock must be timezone-aware")
        return value


def _validate_job_revision(
    current: ProductProposalJob | None,
    value: ProductProposalJob,
    expected_revision: int | None,
) -> None:
    if current is None:
        if expected_revision is not None or value.meta.revision != 1:
            raise ProductRepositoryError("proposal job first revision conflict")
        return
    if expected_revision != current.meta.revision:
        raise ProductRepositoryError(
            f"revision conflict: expected {expected_revision}, current {current.meta.revision}"
        )
    if value.meta.revision != current.meta.revision + 1:
        raise ProductRepositoryError("proposal job revisions must increase by one")
    if value.meta.parent_revision_id != current.revision_id:
        raise ProductRepositoryError("proposal job revision must reference current parent")


def _fingerprint(
    project_id: str,
    kind: str,
    dependencies: tuple[DependencyRef, ...],
    provider: str,
    version: str,
    *,
    raw_input: str | None = None,
) -> str:
    payload = {
        "project_id": project_id,
        "kind": kind,
        "dependencies": [item.model_dump(mode="json") for item in dependencies],
        "provider": provider,
        "version": version,
        "raw_input_hash": (
            hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
            if raw_input is not None
            else None
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
