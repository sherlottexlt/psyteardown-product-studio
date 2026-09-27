"""Versioned HTTP transport DTOs for the Product Studio API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from psyteardown.product.commands import (
    OutcomeContractProposal,
    OutcomeMeasurementPlanProposal,
    ProblemModelProposal,
    ProductIntentProposal,
    ProductThesisProposal,
)
from psyteardown.product.c1 import (
    C1ConsentReceipt,
    C1EvidenceReview,
    C1OutcomeObservation,
    C1Participant,
    C1TaskPresentation,
    C1TrialEnvelope,
    C1WithdrawalTombstone,
    C1_ACCESS_POLICY,
    C1_CONSENT_POLICY_REVISION,
    C1_CONSENT_STATEMENT,
    C1_DATA_CATEGORIES,
    C1_EVIDENCE_CEILING,
    C1_RETENTION_POLICY,
    C1_SOURCE_LAYER,
    C1_WITHDRAWAL_POLICY,
)
from psyteardown.product.models import (
    HumanConfirmation,
    OutcomeContract,
    OutcomeMeasurementPlan,
    ProblemModel,
    ProductIntent,
    ProductProject,
    ProductProjectView,
    ProductProposalJob,
    ProductGenerationJob,
    ProductExecutionJob,
    ProductRepairJob,
    ProductDeliveryBundle,
    DeliveryBundleFile,
    PreviewFeedback,
    PreviewFeedbackAnchor,
    PREVIEW_FEEDBACK_MAX_TEXT,
    PRODUCT_INTENT_MAX_INPUT_CHARS,
    GenerationBudget,
    GenerationManifest,
    ModelCallRecord,
    GenerationSandboxPolicy,
    ExecutionBudget,
    ExecutionSandboxPolicy,
    ExecutionStep,
    RepairBudget,
    RepairAttempt,
    ProductThesis,
    RevisionImpact,
    SourceReference,
    ThesisDisposition,
    WebProductGenerationContract,
    WebAcceptanceCheck,
    WebContentSlot,
    WebScreenSpec,
    WebStateSpec,
    WebTaskSpec,
)


class TransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateProjectRequest(TransportModel):
    name: str = Field(min_length=1)
    collaboration_mode: Literal["managed", "co_design", "governance"] = "managed"
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_from: list[SourceReference] = Field(default_factory=list)


class ChangeProjectStatusRequest(TransportModel):
    expected_revision: int = Field(ge=1)
    to_status: Literal["active", "paused", "archived"]
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class SubmitProductIntentRequest(TransportModel):
    proposal: ProductIntentProposal
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    intent_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SubmitProblemModelRequest(TransportModel):
    proposal: ProblemModelProposal
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    problem_model_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SubmitOutcomeContractRequest(TransportModel):
    proposal: OutcomeContractProposal
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    outcome_contract_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SubmitProductThesisRequest(TransportModel):
    proposal: ProductThesisProposal
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    thesis_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmRevisionRequest(TransportModel):
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class TransitionProductThesisRequest(TransportModel):
    expected_revision: int = Field(ge=1)
    to_status: Literal["exploring", "selected", "paused", "rejected"]
    actor: str = Field(min_length=1)
    actor_type: Literal["human", "system"]
    reason: str = Field(min_length=1)
    authorization_ref: str | None = None


class StartC1EnvelopeRequest(TransportModel):
    measurement_plan_revision_id: str = Field(min_length=1)
    delivery_bundle_id: str = Field(min_length=1)
    execution_job_revision_id: str = Field(min_length=1)
    web_generation_contract_revision_id: str = Field(min_length=1)
    host: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EnrollC1ParticipantRequest(TransportModel):
    consent_policy_revision: str = Field(min_length=1)
    consent_scope_acknowledged: bool
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EndC1EnvelopeRequest(TransportModel):
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PresentC1TaskRequest(TransportModel):
    participant_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RecordC1ObservationRequest(TransportModel):
    participant_id: str = Field(min_length=1)
    presentation_id: str = Field(min_length=1)
    measure_id: str = Field(min_length=1)
    value: str | int | float | bool | None = None
    status: Literal[
        "observed", "participant_withdrawal", "task_abandonment", "technical_failure",
        "skipped_by_protocol", "no_response", "not_applicable", "unknown",
    ] = "observed"
    completion_cause: str | None = None
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReviewC1EvidenceRequest(TransportModel):
    observation_ids: list[str] = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    decision: Literal["accepted", "modified", "rejected", "insufficient"]
    evidence_level_after: Literal["none", "exploratory", "observed"]
    rationale: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class WithdrawC1ParticipantRequest(TransportModel):
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class WebProductGenerationContractProposalRequest(TransportModel):
    product_thesis_revision_id: str
    outcome_contract_revision_id: str
    app_title: str
    screens: list[WebScreenSpec]
    tasks: list[WebTaskSpec]
    primary_flow_task_ids: list[str] = Field(default_factory=list, max_length=8)
    states: list[WebStateSpec]
    content_slots: list[WebContentSlot]
    acceptance_checks: list[WebAcceptanceCheck]
    source_refs: list[SourceReference]


class SubmitWebProductGenerationContractRequest(TransportModel):
    proposal: WebProductGenerationContractProposalRequest
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    web_generation_contract_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class DeriveOutcomeMeasurementPlanRequest(TransportModel):
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    measurement_plan_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SubmitOutcomeMeasurementPlanRequest(TransportModel):
    proposal: OutcomeMeasurementPlanProposal
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    measurement_plan_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class WebProductGenerationContractResponse(TransportModel):
    web_generation_contract_id: str
    project_id: str
    revision_id: str
    meta: RevisionMetaResponse
    product_thesis_revision_id: str
    outcome_contract_revision_id: str
    status: Literal["proposed", "confirmed"]
    template_id: Literal["react_typescript_vite_spa"]
    template_version: str
    app_title: str
    screens: list[WebScreenSpec]
    tasks: list[WebTaskSpec]
    primary_flow_task_ids: list[str] = Field(default_factory=list, max_length=8)
    states: list[WebStateSpec]
    content_slots: list[WebContentSlot]
    acceptance_checks: list[WebAcceptanceCheck]
    runtime_dependencies: list[str]
    development_dependencies: list[str]
    output_paths: list[str]
    network_policy: Literal["none"]
    data_policy: Literal["local_fixture_only"]
    source_refs: list[SourceReference]
    dependencies: list[dict[str, Any]]
    confirmation: HumanConfirmation | None
    content_hash: str

    @classmethod
    def from_domain(
        cls, value: WebProductGenerationContract
    ) -> "WebProductGenerationContractResponse":
        return cls.model_validate(_with_content_hash(value))


class CreateProposalJobRequest(TransportModel):
    kind: Literal[
        "product_intent",
        "problem_model",
        "outcome_contract",
        "product_theses",
        "web_generation_contract",
    ]
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    raw_input: str | None = Field(default=None, min_length=1, max_length=PRODUCT_INTENT_MAX_INPUT_CHARS)
    feedback_id: str | None = None
    provider: Literal["deterministic_fake", "real"] = "deterministic_fake"


class ProposalJobActionRequest(TransportModel):
    actor: str = Field(min_length=1)


class GenerationBudgetRequest(TransportModel):
    max_attempts: int = Field(default=1, ge=1, le=3)
    max_files: int = Field(default=64, ge=1, le=64)
    max_bytes: int = Field(default=1024 * 1024, ge=1, le=1024 * 1024)
    max_duration_seconds: int = Field(default=60, ge=1, le=60)
    max_cost_units: int = Field(default=1, ge=1, le=1)


class CreateGenerationJobRequest(TransportModel):
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    budget: GenerationBudgetRequest | None = None
    # "model" asks the configured source model to write App.tsx/styles.css
    # from the confirmed contract; its budget is fixed server-side.
    source: Literal["template", "model"] = "template"


class SourceModelPolicyResponse(TransportModel):
    available: bool
    provider: str | None
    model: str | None
    sent: list[str]
    not_sent: list[str]
    retention: str
    max_calls_per_job: int
    model_writes: list[str]
    repair_uses_model: bool


class ModelCallTranscriptResponse(TransportModel):
    attempt: int
    provider: str
    model: str
    system: str
    prompt: str
    response: str | None
    gate: dict[str, Any] | None
    error: str | None


class GenerationJobActionRequest(TransportModel):
    actor: str = Field(min_length=1)


class ExecutionBudgetRequest(TransportModel):
    max_attempts: int = Field(default=1, ge=1, le=3)
    max_duration_seconds: int = Field(default=180, ge=1, le=180)
    max_output_bytes: int = Field(default=256 * 1024, ge=1024, le=256 * 1024)
    max_cost_units: int = Field(default=4, ge=1, le=4)


class CreateExecutionJobRequest(TransportModel):
    generation_job_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    budget: ExecutionBudgetRequest | None = None


class ExecutionJobActionRequest(TransportModel):
    actor: str = Field(min_length=1)
    confirm_orphaned: bool = False


class RevisionMetaResponse(TransportModel):
    revision: int
    parent_revision_id: str | None
    created_at: datetime
    created_by: str
    reason: str


class C1PolicyResponse(TransportModel):
    trial_state: Literal["paused", "available"]
    trial_status_message: str
    consent_policy_revision: str
    statement: str
    access_policy: list[str]
    data_categories: list[str]
    retention_policy: str
    withdrawal_policy: str
    source_layer: Literal["research_observation"]
    evidence_ceiling: Literal["observed"]


class C1TrialEnvelopeResponse(TransportModel):
    envelope_id: str
    revision_id: str
    project_id: str
    meta: RevisionMetaResponse
    status: Literal["active", "closed", "stopped"]
    closed_at: datetime | None
    retention_expires_at: datetime | None
    close_reason: str | None
    measurement_plan_revision_id: str
    delivery_bundle_id: str
    delivery_bundle_revision_id: str
    execution_job_revision_id: str
    web_generation_contract_revision_id: str
    host: str
    consent_policy_revision: str
    consent_statement: str
    access_policy: list[str]
    data_categories: list[str]
    retention_policy: str
    withdrawal_policy: str

    @classmethod
    def from_domain(cls, value: C1TrialEnvelope) -> "C1TrialEnvelopeResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1ConsentReceiptResponse(TransportModel):
    meta: RevisionMetaResponse
    receipt_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    participant_id: str
    policy_revision: str
    scope: str
    data_categories: list[str]
    access_policy: list[str]
    retention_policy: str
    withdrawal_policy: str
    consented_by: str
    granted_at: datetime
    status: Literal["granted"]

    @classmethod
    def from_domain(cls, value: C1ConsentReceipt) -> "C1ConsentReceiptResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1ParticipantResponse(TransportModel):
    meta: RevisionMetaResponse
    participant_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    consent_receipt_id: str
    consent_receipt_revision_id: str
    status: Literal["active", "withdrawn"]
    enrolled_at: datetime
    withdrawn_at: datetime | None

    @classmethod
    def from_domain(cls, value: C1Participant) -> "C1ParticipantResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1EnrollmentResponse(TransportModel):
    participant: C1ParticipantResponse
    consent_receipt: C1ConsentReceiptResponse


class C1TaskPresentationResponse(TransportModel):
    meta: RevisionMetaResponse
    presentation_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    participant_id: str
    task_id: str
    consent_receipt_revision_id: str
    delivery_bundle_id: str
    delivery_bundle_revision_id: str
    execution_job_revision_id: str
    web_generation_contract_revision_id: str
    status: Literal["presented", "completed", "withdrawn"]
    started_at: datetime
    ended_at: datetime | None

    @classmethod
    def from_domain(cls, value: C1TaskPresentation) -> "C1TaskPresentationResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1OutcomeObservationResponse(TransportModel):
    meta: RevisionMetaResponse
    observation_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    participant_id: str
    presentation_id: str
    measurement_plan_revision_id: str
    measure_id: str
    source_layer: Literal["research_observation"]
    value: str | int | float | bool | None
    status: Literal[
        "observed", "participant_withdrawal", "task_abandonment", "technical_failure",
        "skipped_by_protocol", "no_response", "not_applicable", "unknown",
    ]
    completion_cause: str | None
    consent_receipt_revision_id: str
    delivery_bundle_id: str
    delivery_bundle_revision_id: str
    execution_job_revision_id: str
    web_generation_contract_revision_id: str
    recorded_by: str
    recorded_at: datetime
    evidence_refs: list[str]

    @classmethod
    def from_domain(cls, value: C1OutcomeObservation) -> "C1OutcomeObservationResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1EvidenceReviewResponse(TransportModel):
    meta: RevisionMetaResponse
    review_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    observation_ids: list[str]
    measurement_plan_revision_id: str
    delivery_bundle_revision_id: str
    execution_job_revision_id: str
    web_generation_contract_revision_id: str
    source_layer: Literal["research_observation"]
    reviewer: str
    decision: Literal["accepted", "modified", "rejected", "insufficient"]
    evidence_level_before: Literal["none", "exploratory", "observed", "supported", "replicated"]
    evidence_level_after: Literal["none", "exploratory", "observed"]
    rationale: str
    limitations: list[str]
    reviewed_at: datetime

    @classmethod
    def from_domain(cls, value: C1EvidenceReview) -> "C1EvidenceReviewResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class C1WithdrawalTombstoneResponse(TransportModel):
    meta: RevisionMetaResponse
    tombstone_id: str
    revision_id: str
    project_id: str
    envelope_id: str
    participant_digest: str
    consent_policy_revision: str
    deleted_receipts: int
    deleted_presentations: int
    deleted_observations: int
    deleted_reviews: int
    withdrawn_at: datetime

    @classmethod
    def from_domain(cls, value: C1WithdrawalTombstone) -> "C1WithdrawalTombstoneResponse":
        return cls.model_validate(value.model_dump(mode="json"))


class ExecutionJobResponse(TransportModel):
    job_id: str
    revision_id: str
    project_id: str
    kind: Literal["web_product_execution"]
    status: Literal["queued", "running", "succeeded", "failed", "stale_input", "budget_exhausted", "cancelled"]
    provider: str
    provider_version: str
    meta: RevisionMetaResponse
    input_dependencies: list[dict[str, Any]]
    generation_job_id: str
    generation_job_revision_id: str
    workspace_relative_path: str
    budget: ExecutionBudget
    sandbox: ExecutionSandboxPolicy
    fingerprint: str
    attempt: int
    checkpoint_step: str | None
    steps: list[ExecutionStep]
    consumed_duration_seconds: float
    consumed_output_bytes: int
    consumed_cost_units: int
    build_artifact_relative_path: str | None
    browser_report_relative_path: str | None
    error_code: str | None
    error_summary: str | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductExecutionJob) -> "ExecutionJobResponse":
        return cls.model_validate(_with_content_hash(value))


class ProductProjectResponse(TransportModel):
    project_id: str
    revision_id: str
    meta: RevisionMetaResponse
    name: str
    collaboration_mode: Literal["managed", "co_design", "governance"]
    status: Literal["active", "paused", "archived"]
    created_from: list[SourceReference]
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductProject) -> "ProductProjectResponse":
        return cls.model_validate(_with_content_hash(value))


class ProductIntentResponse(ProductIntentProposal):
    project_id: str
    intent_id: str
    revision_id: str
    meta: RevisionMetaResponse
    status: Literal["proposed", "confirmed"]
    confirmation: HumanConfirmation | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductIntent) -> "ProductIntentResponse":
        return cls.model_validate(_with_content_hash(value))


class ProblemModelResponse(ProblemModelProposal):
    project_id: str
    problem_model_id: str
    revision_id: str
    meta: RevisionMetaResponse
    status: Literal["proposed", "confirmed"]
    dependencies: list[dict[str, Any]]
    confirmation: HumanConfirmation | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProblemModel) -> "ProblemModelResponse":
        return cls.model_validate(_with_content_hash(value))


class OutcomeContractResponse(OutcomeContractProposal):
    project_id: str
    outcome_contract_id: str
    revision_id: str
    meta: RevisionMetaResponse
    status: Literal["proposed", "confirmed"]
    dependencies: list[dict[str, Any]]
    confirmation: HumanConfirmation | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: OutcomeContract) -> "OutcomeContractResponse":
        return cls.model_validate(_with_content_hash(value))


class OutcomeMeasureResponse(TransportModel):
    measure_id: str
    label: str
    operational_definition: str
    method: str
    unit: str | None
    primary: bool
    missingness_policy: str
    indicator_id: str
    source_layer: Literal[
        "software_check", "runtime_event", "user_report", "research_observation", "expert_review"
    ]
    value_kind: Literal[
        "boolean", "count", "duration_seconds", "ordinal_1_5", "categorical", "free_text"
    ]
    desired_direction: str
    threshold_or_target: str
    blocked_reason: str | None
    on_contradiction: Literal["product_thesis", "outcome_contract", "problem_model"]
    collectable: bool
    evidence_ceiling: Literal["none", "exploratory", "observed", "supported", "replicated"]


class MeasurementGuardrailResponse(TransportModel):
    guardrail_id: str
    prohibited_outcome_id: str
    severity: Literal["hard", "strong_avoidance", "watch"]
    detection_method: str
    source_layer: Literal[
        "software_check", "runtime_event", "user_report", "research_observation", "expert_review"
    ]
    response: str
    blocked_reason: str | None
    collectable: bool
    evidence_ceiling: Literal["none", "exploratory", "observed", "supported", "replicated"]


class OutcomeMeasurementPlanResponse(OutcomeMeasurementPlanProposal):
    measures: list[OutcomeMeasureResponse]
    guardrails: list[MeasurementGuardrailResponse]
    project_id: str
    measurement_plan_id: str
    revision_id: str
    meta: RevisionMetaResponse
    status: Literal["proposed", "confirmed"]
    plan_version: Literal["c2-v1"]
    origin: Literal["deterministic_derivation", "human_revision"]
    dependencies: list[dict[str, Any]]
    confirmation: HumanConfirmation | None
    blockers: list[str]
    content_hash: str

    @classmethod
    def from_domain(
        cls,
        value: OutcomeMeasurementPlan,
        *,
        blockers: tuple[str, ...] = (),
    ) -> "OutcomeMeasurementPlanResponse":
        payload = _with_content_hash(value)
        payload["measures"] = [
            {
                **measure,
                "collectable": item.collectable,
                "evidence_ceiling": item.evidence_ceiling,
            }
            for item, measure in zip(value.measures, payload["measures"], strict=True)
        ]
        payload["guardrails"] = [
            {
                **guardrail,
                "collectable": item.collectable,
                "evidence_ceiling": item.evidence_ceiling,
            }
            for item, guardrail in zip(value.guardrails, payload["guardrails"], strict=True)
        ]
        payload["blockers"] = list(blockers)
        return cls.model_validate(payload)


class ProductThesisResponse(ProductThesisProposal):
    project_id: str
    thesis_id: str
    revision_id: str
    meta: RevisionMetaResponse
    status: Literal["proposed", "exploring", "selected", "paused", "rejected"]
    dependencies: list[dict[str, Any]]
    disposition: ThesisDisposition | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductThesis) -> "ProductThesisResponse":
        return cls.model_validate(_with_content_hash(value))


class RevisionImpactResponse(TransportModel):
    dependent_type: Literal[
        "problem_model",
        "outcome_contract",
        "product_thesis",
        "web_generation_contract",
        "outcome_measurement_plan",
    ]
    dependent_id: str
    dependent_revision_id: str
    impact: Literal["review_required", "stale"]
    changed_dependency: dict[str, Any]
    reason: str

    @classmethod
    def from_domain(cls, value: RevisionImpact) -> "RevisionImpactResponse":
        return cls.model_validate(value.model_dump(mode="python"))


class ProductProposalJobResponse(TransportModel):
    job_id: str
    revision_id: str
    meta: RevisionMetaResponse
    project_id: str
    kind: Literal[
        "product_intent",
        "problem_model",
        "outcome_contract",
        "product_theses",
        "web_generation_contract",
    ]
    status: Literal[
        "queued", "running", "succeeded", "failed", "stale_input", "cancelled"
    ]
    provider: Literal["deterministic_fake", "real"]
    provider_version: str
    input_dependencies: list[dict[str, Any]]
    result_object_id: str
    result_object_ids: list[str]
    result_expected_revision: int | None
    raw_input: str | None
    feedback_id: str | None
    fingerprint: str
    attempt: int
    result_revision_id: str | None
    result_revision_ids: list[str]
    error_code: str | None
    error_summary: str | None
    content_hash: str

    @classmethod
    def from_domain(
        cls, value: ProductProposalJob
    ) -> "ProductProposalJobResponse":
        return cls.model_validate(_with_content_hash(value))


class ProductGenerationJobResponse(TransportModel):
    job_id: str
    revision_id: str
    meta: RevisionMetaResponse
    project_id: str
    kind: Literal["web_product"]
    status: Literal[
        "queued", "running", "paused", "succeeded", "failed", "stale_input", "budget_exhausted", "cancelled"
    ]
    provider: Literal["deterministic_template", "deterministic_repair", "model_source"]
    provider_version: str
    input_dependencies: list[dict[str, Any]]
    web_generation_contract_revision_id: str
    workspace_id: str
    workspace_relative_path: str
    budget: GenerationBudget
    sandbox: GenerationSandboxPolicy
    fingerprint: str
    materialization_kind: Literal["template", "repair", "model"]
    parent_generation_job_id: str | None
    repair_job_id: str | None
    model_calls: list[ModelCallRecord]
    attempt: int
    checkpoint_step: Literal["prepare", "generate", "validate"] | None
    consumed_files: int
    consumed_bytes: int
    consumed_duration_seconds: float
    consumed_cost_units: int
    manifest: GenerationManifest | None
    error_code: str | None
    error_summary: str | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductGenerationJob) -> "ProductGenerationJobResponse":
        return cls.model_validate(_with_content_hash(value))


class RepairBudgetRequest(TransportModel):
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_patches: int = Field(default=2, ge=1, le=2)
    max_patch_bytes: int = Field(default=16 * 1024, ge=1, le=16 * 1024)
    max_cost_units: int = Field(default=2, ge=1, le=2)


class CreateRepairJobRequest(TransportModel):
    execution_job_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    budget: RepairBudgetRequest | None = None


class RepairJobActionRequest(TransportModel):
    actor: str = Field(min_length=1)


class RepairJobResponse(TransportModel):
    job_id: str
    revision_id: str
    project_id: str
    kind: Literal["web_product_repair"]
    status: Literal["queued", "running", "succeeded", "failed", "stale_input", "budget_exhausted", "cancelled"]
    provider: Literal["deterministic_repair"]
    provider_version: str
    meta: RevisionMetaResponse
    input_dependencies: list[dict[str, Any]]
    execution_job_id: str
    execution_job_revision_id: str
    generation_job_id: str
    generation_job_revision_id: str
    budget: RepairBudget
    fingerprint: str
    attempt: int
    attempts: list[RepairAttempt]
    consumed_cost_units: int
    latest_generation_job_id: str | None
    latest_execution_job_id: str | None
    error_code: str | None
    error_summary: str | None
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductRepairJob) -> "RepairJobResponse":
        return cls.model_validate(_with_content_hash(value))


class CreateDeliveryBundleRequest(TransportModel):
    execution_job_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DeliveryBundleResponse(TransportModel):
    bundle_id: str
    revision_id: str
    project_id: str
    kind: Literal["web_product_delivery"]
    format_version: Literal["b6-v1"]
    meta: RevisionMetaResponse
    input_dependencies: list[dict[str, Any]]
    execution_job_id: str
    execution_job_revision_id: str
    generation_job_id: str
    generation_job_revision_id: str
    web_generation_contract_revision_id: str
    contract_is_current: bool
    materialization_kind: Literal["template", "repair", "model"]
    parent_generation_job_id: str | None
    repair_job_id: str | None
    template_id: Literal["react_typescript_vite_spa"]
    template_version: str
    verification_steps: list[ExecutionStep]
    files: list[DeliveryBundleFile]
    total_bytes: int
    archive_sha256: str
    archive_bytes: int
    unverified_claims: list[str]
    outcome_evidence_level: Literal["none"]
    fingerprint: str
    content_hash: str

    @classmethod
    def from_domain(cls, value: ProductDeliveryBundle) -> "DeliveryBundleResponse":
        return cls.model_validate(_with_content_hash(value))


class PreviewFeedbackPolicyResponse(TransportModel):
    consent_version: Literal["b7-explicit-v1"]
    statement: str
    captured: list[str]
    not_captured: list[str]
    max_text_length: int
    evidence_level: Literal["user_report"]


class SubmitPreviewFeedbackRequest(TransportModel):
    screen_id: str = Field(min_length=1)
    task_id: str | None = Field(default=None, min_length=1)
    state_id: str | None = Field(default=None, min_length=1)
    category: Literal["bug", "confusing", "missing", "works"]
    text: str = Field(min_length=1, max_length=PREVIEW_FEEDBACK_MAX_TEXT)
    actor: str = Field(min_length=1)
    consent_version: str = Field(min_length=1)
    consent_granted: bool


class PreviewFeedbackDispositionRequest(TransportModel):
    disposition: Literal["pending", "incorporated", "deferred"]
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DeliveryBundleFileChange(TransportModel):
    path: str
    change: Literal["added", "removed", "modified", "unchanged"]
    base_sha256: str | None
    target_sha256: str | None


class DeliveryBundleDiffResponse(TransportModel):
    base_bundle_id: str
    target_bundle_id: str
    base_contract_revision_id: str
    target_contract_revision_id: str
    contract_changes: list[str]
    files: list[DeliveryBundleFileChange]


class WithdrawPreviewFeedbackRequest(TransportModel):
    actor: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)


class PreviewFeedbackResponse(TransportModel):
    feedback_id: str
    revision_id: str
    project_id: str
    meta: RevisionMetaResponse
    delivery_bundle_id: str
    delivery_bundle_revision_id: str
    execution_job_revision_id: str
    web_generation_contract_revision_id: str
    anchor: PreviewFeedbackAnchor
    status: Literal["submitted", "withdrawn"]
    category: Literal["bug", "confusing", "missing", "works"] | None
    text: str | None
    submitted_by: str
    submitted_at: datetime
    consent: dict[str, Any]
    withdrawn_at: datetime | None
    disposition: Literal["pending", "incorporated", "deferred"]
    evidence_level: Literal["user_report"]
    automatic_capture: Literal["none"]
    content_hash: str

    @classmethod
    def from_domain(cls, value: PreviewFeedback) -> "PreviewFeedbackResponse":
        return cls.model_validate(_with_content_hash(value))


class ProductProjectViewResponse(TransportModel):
    project: ProductProjectResponse
    product_intent: ProductIntentResponse | None
    problem_model: ProblemModelResponse | None
    outcome_contract: OutcomeContractResponse | None
    outcome_measurement_plan: OutcomeMeasurementPlanResponse | None
    measurement_plan_blockers: list[str]
    product_theses: list[ProductThesisResponse]
    web_generation_contract: WebProductGenerationContractResponse | None
    recorded_impacts: list[RevisionImpactResponse]

    @classmethod
    def from_domain(cls, value: ProductProjectView) -> "ProductProjectViewResponse":
        return cls(
            project=ProductProjectResponse.from_domain(value.project),
            product_intent=(
                ProductIntentResponse.from_domain(value.product_intent)
                if value.product_intent
                else None
            ),
            problem_model=(
                ProblemModelResponse.from_domain(value.problem_model)
                if value.problem_model
                else None
            ),
            outcome_contract=(
                OutcomeContractResponse.from_domain(value.outcome_contract)
                if value.outcome_contract
                else None
            ),
            outcome_measurement_plan=(
                OutcomeMeasurementPlanResponse.from_domain(
                    value.outcome_measurement_plan,
                    blockers=value.measurement_plan_blockers,
                )
                if value.outcome_measurement_plan
                else None
            ),
            measurement_plan_blockers=list(value.measurement_plan_blockers),
            product_theses=[
                ProductThesisResponse.from_domain(item)
                for item in value.product_theses
            ],
            web_generation_contract=(
                WebProductGenerationContractResponse.from_domain(
                    value.web_generation_contract
                )
                if value.web_generation_contract
                else None
            ),
            recorded_impacts=[
                RevisionImpactResponse.from_domain(item)
                for item in value.recorded_impacts
            ],
        )


class HealthResponse(TransportModel):
    status: Literal["ok"] = "ok"
    api_version: Literal["v1"] = "v1"
    service: Literal["psyteardown-product-studio"] = "psyteardown-product-studio"


class ApiErrorIssue(TransportModel):
    location: list[str | int]
    code: str
    message: str


class ApiErrorDetail(TransportModel):
    code: str
    message: str
    request_id: str
    issues: list[ApiErrorIssue] = Field(default_factory=list)


class ApiErrorResponse(TransportModel):
    error: ApiErrorDetail


def _with_content_hash(value: Any) -> dict[str, Any]:
    payload = value.model_dump(mode="python")
    payload["content_hash"] = value.content_hash
    return payload
