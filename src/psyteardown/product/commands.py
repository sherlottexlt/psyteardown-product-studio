"""Boundary command DTOs for Product Studio application writes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from psyteardown.experience.models import BoundaryModel, Identifier, SamplePlan
from psyteardown.product.models import (
    CompetingExplanation,
    DeliveryEstimate,
    DeliveryMaturity,
    FalsifiablePrediction,
    MeasurementGuardrail,
    MechanismHypothesis,
    OutcomeMeasure,
    ProblemAssumption,
    ProblemFact,
    ProblemUnknown,
    ProhibitedOutcome,
    ResourceBoundary,
    SourceReference,
    StakeholderTension,
    StopCondition,
    SuccessIndicator,
    TargetOutcome,
    ValidationStep,
    WebAcceptanceCheck,
    WebContentSlot,
    WebScreenSpec,
    WebStateSpec,
    WebTaskSpec,
)


class CreateProductProject(BoundaryModel):
    name: Identifier
    collaboration_mode: Literal["managed", "co_design", "governance"] = "managed"
    actor: Identifier
    reason: Identifier
    project_id: str | None = None
    created_from: list[SourceReference] = Field(default_factory=list)


class ChangeProductProjectStatus(BoundaryModel):
    project_id: Identifier
    expected_revision: int = Field(ge=1)
    to_status: Literal["active", "paused", "archived"]
    actor: Identifier
    reason: Identifier


class ProductIntentProposal(BoundaryModel):
    desired_change: Identifier
    affected_people: list[Identifier] = Field(min_length=1)
    current_situation: str | None = None
    explicit_non_goals: list[str] = Field(default_factory=list)
    known_constraints: list[str] = Field(default_factory=list)
    resource_preferences: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(min_length=1)


class SubmitProductIntentProposal(BoundaryModel):
    project_id: Identifier
    proposal: ProductIntentProposal
    actor: Identifier
    reason: Identifier
    intent_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmProductIntent(BoundaryModel):
    project_id: Identifier
    intent_id: Identifier
    expected_revision: int = Field(ge=1)
    actor: Identifier
    reason: Identifier


class ProblemModelProposal(BoundaryModel):
    intent_revision_id: Identifier
    facts: list[ProblemFact] = Field(default_factory=list)
    assumptions: list[ProblemAssumption] = Field(default_factory=list)
    unknowns: list[ProblemUnknown] = Field(default_factory=list)
    competing_explanations: list[CompetingExplanation] = Field(default_factory=list)
    stakeholder_tensions: list[StakeholderTension] = Field(default_factory=list)


class SubmitProblemModelProposal(BoundaryModel):
    project_id: Identifier
    proposal: ProblemModelProposal
    actor: Identifier
    reason: Identifier
    problem_model_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmProblemModel(BoundaryModel):
    project_id: Identifier
    problem_model_id: Identifier
    expected_revision: int = Field(ge=1)
    actor: Identifier
    reason: Identifier


class OutcomeContractProposal(BoundaryModel):
    intent_revision_id: Identifier
    problem_model_revision_id: Identifier
    target_segments: list[str] = Field(default_factory=list)
    applicable_contexts: list[str] = Field(default_factory=list)
    target_outcomes: list[TargetOutcome] = Field(default_factory=list)
    success_indicators: list[SuccessIndicator] = Field(default_factory=list)
    prohibited_outcomes: list[ProhibitedOutcome] = Field(default_factory=list)
    prohibited_outcomes_reviewed: bool = False
    resource_boundary: ResourceBoundary
    stop_conditions: list[StopCondition] = Field(default_factory=list)
    minimum_delivery_maturity: DeliveryMaturity = DeliveryMaturity.CONCEPT
    required_real_world_evidence: list[str] = Field(default_factory=list)


class SubmitOutcomeContractProposal(BoundaryModel):
    project_id: Identifier
    proposal: OutcomeContractProposal
    actor: Identifier
    reason: Identifier
    outcome_contract_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmOutcomeContract(BoundaryModel):
    project_id: Identifier
    outcome_contract_id: Identifier
    expected_revision: int = Field(ge=1)
    actor: Identifier
    reason: Identifier


class ProductThesisProposal(BoundaryModel):
    problem_model_revision_id: Identifier
    outcome_contract_revision_id: Identifier
    name: Identifier
    product_promise: Identifier
    differentiation: Identifier
    realization_modes: list[
        Literal["software", "hardware", "service", "content", "process", "hybrid"]
    ] = Field(min_length=1)
    mechanism_hypotheses: list[MechanismHypothesis] = Field(min_length=1)
    falsifiable_predictions: list[FalsifiablePrediction] = Field(min_length=1)
    validation_strategy: list[ValidationStep] = Field(min_length=1)
    key_unknowns: list[Identifier] = Field(min_length=1)
    key_risks: list[Identifier] = Field(min_length=1)
    delivery_estimate: DeliveryEstimate


class SubmitProductThesisProposal(BoundaryModel):
    project_id: Identifier
    proposal: ProductThesisProposal
    actor: Identifier
    reason: Identifier
    thesis_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class TransitionProductThesis(BoundaryModel):
    project_id: Identifier
    thesis_id: Identifier
    expected_revision: int = Field(ge=1)
    to_status: Literal["exploring", "selected", "paused", "rejected"]
    actor: Identifier
    actor_type: Literal["human", "system"]
    reason: Identifier
    authorization_ref: str | None = None


class WebProductGenerationContractProposal(BoundaryModel):
    product_thesis_revision_id: Identifier
    outcome_contract_revision_id: Identifier
    app_title: Identifier
    screens: list[WebScreenSpec] = Field(min_length=1)
    tasks: list[WebTaskSpec] = Field(min_length=1)
    # Ordered happy-path task IDs for the first end-to-end user journey.
    primary_flow_task_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    states: list[WebStateSpec] = Field(min_length=1)
    content_slots: list[WebContentSlot] = Field(min_length=1)
    acceptance_checks: list[WebAcceptanceCheck] = Field(min_length=1)
    source_refs: list[SourceReference] = Field(min_length=1)


class SubmitWebProductGenerationContractProposal(BoundaryModel):
    project_id: Identifier
    proposal: WebProductGenerationContractProposal
    actor: Identifier
    reason: Identifier
    web_generation_contract_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmWebProductGenerationContract(BoundaryModel):
    project_id: Identifier
    web_generation_contract_id: Identifier
    expected_revision: int = Field(ge=1)
    actor: Identifier
    reason: Identifier


class OutcomeMeasurementPlanProposal(BoundaryModel):
    outcome_contract_revision_id: Identifier
    measures: list[OutcomeMeasure] = Field(min_length=1, max_length=20)
    guardrails: list[MeasurementGuardrail] = Field(default_factory=list, max_length=20)
    stop_condition_ids: list[Identifier] = Field(default_factory=list)
    sample_plan: SamplePlan
    observation_window: Identifier
    consent_scope: Identifier
    withdrawal_policy: Identifier


class DeriveOutcomeMeasurementPlan(BoundaryModel):
    """Ask for a deterministic plan proposal from the current confirmed contract."""

    project_id: Identifier
    actor: Identifier
    reason: Identifier
    measurement_plan_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SubmitOutcomeMeasurementPlanProposal(BoundaryModel):
    project_id: Identifier
    proposal: OutcomeMeasurementPlanProposal
    actor: Identifier
    reason: Identifier
    measurement_plan_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmOutcomeMeasurementPlan(BoundaryModel):
    project_id: Identifier
    measurement_plan_id: Identifier
    expected_revision: int = Field(ge=1)
    actor: Identifier
    reason: Identifier
