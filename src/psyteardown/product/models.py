"""Immutable upper-domain snapshots for the Product Studio.

These models sit above the existing experience/design/engineering kernel.
They describe why a product should exist and what outcome it must pursue;
they do not replace lower-level briefs, evidence, or engineering records.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from psyteardown.experience.models import (
    DependencyRef,
    FrozenModel,
    Identifier,
    MeasureSpec,
    RevisionMeta,
    SamplePlan,
)


def _duplicates(values: tuple[str, ...]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _require_dependencies(
    dependencies: tuple[DependencyRef, ...], required_types: tuple[str, ...]
) -> None:
    actual = {dependency.object_type for dependency in dependencies}
    missing = set(required_types) - actual
    if missing:
        raise ValueError(
            "missing required dependencies: " + ", ".join(sorted(missing))
        )


class SourceReference(FrozenModel):
    """A compact pointer to the origin of a product-domain statement."""

    source_type: Literal[
        "user_input",
        "imported_artifact",
        "research",
        "evidence",
        "tool_result",
        "model_proposal",
        "human_decision",
        "preview_feedback",
    ]
    source_id: Identifier
    revision_id: str | None = None
    locator: str | None = None


class HumanConfirmation(FrozenModel):
    confirmed_by: Identifier
    confirmed_at: datetime
    rationale: Identifier


PRODUCT_INTENT_MAX_INPUT_CHARS = 4000


class ProductProject(FrozenModel):
    """Minimal project lifecycle aggregate; child objects remain independent."""

    project_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    name: Identifier
    collaboration_mode: Literal["managed", "co_design", "governance"] = "managed"
    status: Literal["active", "paused", "archived"] = "active"
    created_from: tuple[SourceReference, ...] = ()


class ProductIntent(FrozenModel):
    """A user-correctable statement of the reality worth changing."""

    intent_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    status: Literal["proposed", "confirmed"] = "proposed"
    desired_change: Identifier
    affected_people: tuple[Identifier, ...] = Field(min_length=1)
    current_situation: str | None = None
    explicit_non_goals: tuple[str, ...] = ()
    known_constraints: tuple[str, ...] = ()
    resource_preferences: tuple[str, ...] = ()
    source_refs: tuple[SourceReference, ...] = Field(min_length=1)
    confirmation: HumanConfirmation | None = None

    @model_validator(mode="after")
    def confirmation_matches_status(self) -> "ProductIntent":
        if self.status == "confirmed" and self.confirmation is None:
            raise ValueError("confirmed product intent requires human confirmation")
        if self.status == "proposed" and self.confirmation is not None:
            raise ValueError("proposed product intent cannot carry confirmation")
        return self


class ProblemFact(FrozenModel):
    fact_id: Identifier
    statement: Identifier
    source_refs: tuple[SourceReference, ...] = Field(min_length=1)


class ProblemAssumption(FrozenModel):
    assumption_id: Identifier
    statement: Identifier
    consequence_if_wrong: Identifier
    cheapest_validation: Identifier


class ProblemUnknown(FrozenModel):
    unknown_id: Identifier
    question: Identifier
    decision_impact: Identifier
    next_step: Identifier


class CompetingExplanation(FrozenModel):
    explanation_id: Identifier
    statement: Identifier
    supporting_fact_ids: tuple[str, ...] = ()
    contradicting_fact_ids: tuple[str, ...] = ()
    cheapest_falsification: Identifier


class StakeholderTension(FrozenModel):
    tension_id: Identifier
    stakeholder_refs: tuple[Identifier, ...] = Field(min_length=2)
    description: Identifier
    unresolved_value_choice: Identifier


class ProblemModel(FrozenModel):
    """Versioned separation of reality, interpretation, and uncertainty."""

    problem_model_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    intent_revision_id: Identifier
    status: Literal["proposed", "confirmed"] = "proposed"
    facts: tuple[ProblemFact, ...] = ()
    assumptions: tuple[ProblemAssumption, ...] = ()
    unknowns: tuple[ProblemUnknown, ...] = ()
    competing_explanations: tuple[CompetingExplanation, ...] = ()
    stakeholder_tensions: tuple[StakeholderTension, ...] = ()
    dependencies: tuple[DependencyRef, ...] = Field(min_length=1)
    confirmation: HumanConfirmation | None = None

    @model_validator(mode="after")
    def validate_problem_model(self) -> "ProblemModel":
        _require_dependencies(self.dependencies, ("product_intent",))
        id_groups = (
            ("fact", tuple(item.fact_id for item in self.facts)),
            ("assumption", tuple(item.assumption_id for item in self.assumptions)),
            ("unknown", tuple(item.unknown_id for item in self.unknowns)),
            (
                "explanation",
                tuple(item.explanation_id for item in self.competing_explanations),
            ),
            ("tension", tuple(item.tension_id for item in self.stakeholder_tensions)),
        )
        for label, values in id_groups:
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(f"duplicate {label} IDs: {sorted(duplicates)}")

        fact_ids = {item.fact_id for item in self.facts}
        for explanation in self.competing_explanations:
            referenced = set(explanation.supporting_fact_ids) | set(
                explanation.contradicting_fact_ids
            )
            unknown = referenced - fact_ids
            if unknown:
                raise ValueError(
                    f"explanation {explanation.explanation_id} references unknown facts: "
                    + ", ".join(sorted(unknown))
                )

        if self.status == "confirmed":
            if self.confirmation is None:
                raise ValueError("confirmed problem model requires human confirmation")
            if not self.facts:
                raise ValueError("confirmed problem model requires at least one sourced fact")
            if len(self.competing_explanations) < 2:
                raise ValueError(
                    "confirmed problem model requires at least two competing explanations"
                )
        elif self.confirmation is not None:
            raise ValueError("proposed problem model cannot carry confirmation")
        return self


class DeliveryMaturity(StrEnum):
    CONCEPT = "concept"
    RUNNABLE_PROTOTYPE = "runnable_prototype"
    FIELD_TRIAL = "field_trial"
    OPERATIONAL_CANDIDATE = "operational_candidate"
    RELEASED_PRODUCT = "released_product"


class SuccessIndicator(FrozenModel):
    indicator_id: Identifier
    operational_definition: Identifier
    observation_method: Identifier
    desired_direction: Identifier
    threshold_or_target: Identifier
    required_evidence: Literal[
        "deterministic_check",
        "tool_result",
        "expert_review",
        "real_user_observation",
        "operational_result",
    ]


class TargetOutcome(FrozenModel):
    outcome_id: Identifier
    description: Identifier
    indicator_ids: tuple[Identifier, ...] = ()


class ProhibitedOutcome(FrozenModel):
    prohibited_outcome_id: Identifier
    description: Identifier
    severity: Literal["hard", "strong_avoidance", "watch"]
    detection_method: Identifier
    response: Identifier


class ResourceBoundary(FrozenModel):
    time_budget: str | None = None
    economic_budget: str | None = None
    user_attention_budget: str | None = None
    maintenance_budget: str | None = None
    data_boundary: str | None = None
    explicit_unknowns: tuple[str, ...] = ()

    @model_validator(mode="after")
    def at_least_one_boundary_or_unknown(self) -> "ResourceBoundary":
        values = (
            self.time_budget,
            self.economic_budget,
            self.user_attention_budget,
            self.maintenance_budget,
            self.data_boundary,
        )
        if not any(values) and not self.explicit_unknowns:
            raise ValueError("resource boundary must declare a limit or an explicit unknown")
        return self


class StopCondition(FrozenModel):
    condition_id: Identifier
    condition: Identifier
    action: Literal["pause", "stop", "reframe", "escalate"]


class OutcomeContract(FrozenModel):
    """Human-confirmed outcome and delivery boundary for product search."""

    outcome_contract_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    intent_revision_id: Identifier
    problem_model_revision_id: Identifier
    status: Literal["proposed", "confirmed"] = "proposed"
    target_segments: tuple[str, ...] = ()
    applicable_contexts: tuple[str, ...] = ()
    target_outcomes: tuple[TargetOutcome, ...] = ()
    success_indicators: tuple[SuccessIndicator, ...] = ()
    prohibited_outcomes: tuple[ProhibitedOutcome, ...] = ()
    prohibited_outcomes_reviewed: bool = False
    resource_boundary: ResourceBoundary
    stop_conditions: tuple[StopCondition, ...] = ()
    minimum_delivery_maturity: DeliveryMaturity = DeliveryMaturity.CONCEPT
    required_real_world_evidence: tuple[str, ...] = ()
    dependencies: tuple[DependencyRef, ...] = Field(min_length=2)
    confirmation: HumanConfirmation | None = None

    @model_validator(mode="after")
    def validate_outcome_contract(self) -> "OutcomeContract":
        _require_dependencies(
            self.dependencies, ("product_intent", "problem_model")
        )
        outcome_ids = tuple(item.outcome_id for item in self.target_outcomes)
        indicator_ids = tuple(item.indicator_id for item in self.success_indicators)
        prohibited_ids = tuple(
            item.prohibited_outcome_id for item in self.prohibited_outcomes
        )
        stop_ids = tuple(item.condition_id for item in self.stop_conditions)
        for label, values in (
            ("outcome", outcome_ids),
            ("indicator", indicator_ids),
            ("prohibited outcome", prohibited_ids),
            ("stop condition", stop_ids),
        ):
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(f"duplicate {label} IDs: {sorted(duplicates)}")

        available_indicators = set(indicator_ids)
        for outcome in self.target_outcomes:
            unknown = set(outcome.indicator_ids) - available_indicators
            if unknown:
                raise ValueError(
                    f"outcome {outcome.outcome_id} references unknown indicators: "
                    + ", ".join(sorted(unknown))
                )

        if self.status == "confirmed":
            if self.confirmation is None:
                raise ValueError("confirmed outcome contract requires human confirmation")
            if not self.target_segments or not self.applicable_contexts:
                raise ValueError(
                    "confirmed outcome contract requires target segments and contexts"
                )
            if not self.target_outcomes:
                raise ValueError("confirmed outcome contract requires a target outcome")
            if any(not outcome.indicator_ids for outcome in self.target_outcomes):
                raise ValueError(
                    "every confirmed target outcome requires at least one indicator"
                )
            if not self.prohibited_outcomes_reviewed:
                raise ValueError(
                    "confirmed outcome contract requires prohibited-outcome review"
                )
            if not self.stop_conditions:
                raise ValueError("confirmed outcome contract requires a stop condition")
            if not self.required_real_world_evidence:
                raise ValueError(
                    "confirmed outcome contract requires real-world evidence requirements"
                )
        elif self.confirmation is not None:
            raise ValueError("proposed outcome contract cannot carry confirmation")
        return self


class MechanismHypothesis(FrozenModel):
    mechanism_id: Identifier
    condition: Identifier
    proposed_intervention: Identifier
    expected_change: Identifier
    uncertainty: Identifier
    evidence_refs: tuple[SourceReference, ...] = ()


class FalsifiablePrediction(FrozenModel):
    prediction_id: Identifier
    prediction: Identifier
    failure_observation: Identifier
    cheapest_test: Identifier


class ValidationStep(FrozenModel):
    validation_step_id: Identifier
    question: Identifier
    method: Identifier
    evidence_level: Literal[
        "deterministic_check",
        "simulation",
        "expert_review",
        "real_user_observation",
        "operational_result",
    ]
    pass_condition: Identifier
    estimated_cost: Identifier


class DeliveryEstimate(FrozenModel):
    initial_delivery_cost: Identifier
    operating_cost: Identifier
    maintenance_burden: Identifier


class ThesisDisposition(FrozenModel):
    action: Literal["exploring", "selected", "paused", "rejected"]
    decided_by: Identifier
    actor_type: Literal["human", "system"]
    decided_at: datetime
    rationale: Identifier
    authorization_ref: str | None = None


class ProductThesis(FrozenModel):
    """One differentiated and falsifiable route toward an outcome contract."""

    thesis_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    problem_model_revision_id: Identifier
    outcome_contract_revision_id: Identifier
    status: Literal["proposed", "exploring", "selected", "paused", "rejected"] = (
        "proposed"
    )
    name: Identifier
    product_promise: Identifier
    differentiation: Identifier
    realization_modes: tuple[
        Literal["software", "hardware", "service", "content", "process", "hybrid"],
        ...,
    ] = Field(min_length=1)
    mechanism_hypotheses: tuple[MechanismHypothesis, ...] = Field(min_length=1)
    falsifiable_predictions: tuple[FalsifiablePrediction, ...] = Field(min_length=1)
    validation_strategy: tuple[ValidationStep, ...] = Field(min_length=1)
    key_unknowns: tuple[Identifier, ...] = Field(min_length=1)
    key_risks: tuple[Identifier, ...] = Field(min_length=1)
    delivery_estimate: DeliveryEstimate
    dependencies: tuple[DependencyRef, ...] = Field(min_length=2)
    disposition: ThesisDisposition | None = None

    @model_validator(mode="after")
    def validate_product_thesis(self) -> "ProductThesis":
        _require_dependencies(
            self.dependencies, ("problem_model", "outcome_contract")
        )
        id_groups = (
            (
                "mechanism",
                tuple(item.mechanism_id for item in self.mechanism_hypotheses),
            ),
            (
                "prediction",
                tuple(item.prediction_id for item in self.falsifiable_predictions),
            ),
            (
                "validation step",
                tuple(item.validation_step_id for item in self.validation_strategy),
            ),
        )
        for label, values in id_groups:
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(f"duplicate {label} IDs: {sorted(duplicates)}")

        if len(set(self.realization_modes)) != len(self.realization_modes):
            raise ValueError("product thesis realization modes must be unique")
        if self.status == "proposed" and self.disposition is not None:
            raise ValueError("proposed product thesis cannot carry a disposition")
        if self.status != "proposed":
            if self.disposition is None or self.disposition.action != self.status:
                raise ValueError(
                    "non-proposed product thesis requires a matching disposition"
                )
            if (
                self.status == "selected"
                and self.disposition.actor_type != "human"
                and not self.disposition.authorization_ref
            ):
                raise ValueError(
                    "selected product thesis requires a human decision or explicit authorization"
                )
        return self


# B2 freezes one realization template for the first digital-product slice.
# These constants are intentionally narrow: choosing a template does not grant
# permission to execute generated code or access external services.
WEB_TEMPLATE_ID = "react_typescript_vite_spa"
WEB_TEMPLATE_VERSION = "b2-v1"
WEB_RUNTIME_DEPENDENCIES = ("react", "react-dom")
WEB_DEVELOPMENT_DEPENDENCIES = (
    "@axe-core/playwright",
    "@vitejs/plugin-react",
    "@playwright/test",
    "@types/react",
    "@types/react-dom",
    "@testing-library/react",
    "typescript",
    "vite",
    "vitest",
)
WEB_OUTPUT_PATHS = (
    "src/main.tsx",
    "src/App.tsx",
    "src/styles.css",
    "tests/",
    "public/",
)


class WebScreenSpec(FrozenModel):
    screen_id: Identifier
    title: Identifier
    purpose: Identifier
    task_ids: tuple[Identifier, ...] = Field(min_length=1)
    state_ids: tuple[Identifier, ...] = Field(min_length=1)


class WebTaskSpec(FrozenModel):
    task_id: Identifier
    screen_id: Identifier
    goal: Identifier
    success_criteria: Identifier
    user_decision_limit: Identifier


class WebStateSpec(FrozenModel):
    state_id: Identifier
    kind: Literal[
        "ready", "loading", "empty", "error", "success", "paused", "stopped"
    ]
    user_visible_behavior: Identifier
    recovery_action: Identifier


class WebContentSlot(FrozenModel):
    slot_id: Identifier
    semantic_role: Literal[
        "heading",
        "instruction",
        "label",
        "status",
        "error",
        "confirmation",
    ]
    description: Identifier
    source_kind: Literal[
        "outcome_contract",
        "product_thesis",
        "user_input",
        "local_fixture",
    ]
    fallback_text: Identifier
    required: bool = True


class WebAcceptanceCheck(FrozenModel):
    check_id: Identifier
    task_id: Identifier
    assertion: Identifier
    evidence_level: Literal["deterministic_check"] = "deterministic_check"


class WebProductGenerationContract(FrozenModel):
    """Minimal, traceable input contract for the first Web realization.

    This object describes what a later generator may build. It is deliberately
    not a source tree, dependency lockfile, execution grant, or user-result
    claim.
    """

    web_generation_contract_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    product_thesis_revision_id: Identifier
    outcome_contract_revision_id: Identifier
    status: Literal["proposed", "confirmed"] = "proposed"
    template_id: Literal["react_typescript_vite_spa"] = WEB_TEMPLATE_ID
    template_version: Identifier = WEB_TEMPLATE_VERSION
    app_title: Identifier
    screens: tuple[WebScreenSpec, ...] = Field(min_length=1, max_length=5)
    tasks: tuple[WebTaskSpec, ...] = Field(min_length=1, max_length=8)
    # Ordered happy-path task IDs for the one journey the human should run.
    primary_flow_task_ids: tuple[Identifier, ...] = Field(default_factory=tuple, max_length=8)
    states: tuple[WebStateSpec, ...] = Field(min_length=5, max_length=20)
    content_slots: tuple[WebContentSlot, ...] = Field(min_length=1, max_length=20)
    acceptance_checks: tuple[WebAcceptanceCheck, ...] = Field(min_length=1, max_length=20)
    runtime_dependencies: tuple[str, ...] = WEB_RUNTIME_DEPENDENCIES
    development_dependencies: tuple[str, ...] = WEB_DEVELOPMENT_DEPENDENCIES
    output_paths: tuple[str, ...] = WEB_OUTPUT_PATHS
    network_policy: Literal["none"] = "none"
    data_policy: Literal["local_fixture_only"] = "local_fixture_only"
    source_refs: tuple[SourceReference, ...] = Field(min_length=1)
    dependencies: tuple[DependencyRef, ...] = Field(min_length=2)
    confirmation: HumanConfirmation | None = None

    @model_validator(mode="after")
    def validate_generation_contract(self) -> "WebProductGenerationContract":
        _require_dependencies(
            self.dependencies, ("product_thesis", "outcome_contract")
        )
        if self.template_id != WEB_TEMPLATE_ID:
            raise ValueError("unsupported Web realization template")
        if self.template_version != WEB_TEMPLATE_VERSION:
            raise ValueError("unsupported Web realization template version")
        if self.runtime_dependencies != WEB_RUNTIME_DEPENDENCIES:
            raise ValueError("Web runtime dependencies are fixed for the first slice")
        if self.development_dependencies != WEB_DEVELOPMENT_DEPENDENCIES:
            raise ValueError(
                "Web development dependencies are fixed for the first slice"
            )
        if self.output_paths != WEB_OUTPUT_PATHS:
            raise ValueError("Web output layout is fixed for the first slice")
        screen_ids = tuple(item.screen_id for item in self.screens)
        task_ids = tuple(item.task_id for item in self.tasks)
        primary_flow_ids = tuple(self.primary_flow_task_ids)
        state_ids = tuple(item.state_id for item in self.states)
        slot_ids = tuple(item.slot_id for item in self.content_slots)
        check_ids = tuple(item.check_id for item in self.acceptance_checks)
        for label, values in (
            ("screen", screen_ids),
            ("task", task_ids),
            ("primary flow task", primary_flow_ids),
            ("state", state_ids),
            ("content slot", slot_ids),
            ("acceptance check", check_ids),
        ):
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(f"duplicate Web {label} IDs: {sorted(duplicates)}")
        screen_set = set(screen_ids)
        task_set = set(task_ids)
        if not set(primary_flow_ids) <= task_set:
            raise ValueError("primary flow references an unknown task")
        state_set = set(state_ids)
        for task in self.tasks:
            if task.screen_id not in screen_set:
                raise ValueError(f"task {task.task_id} references an unknown screen")
        for screen in self.screens:
            if not set(screen.task_ids) <= task_set:
                raise ValueError(f"screen {screen.screen_id} references an unknown task")
            if not set(screen.state_ids) <= state_set:
                raise ValueError(f"screen {screen.screen_id} references an unknown state")
        for check in self.acceptance_checks:
            if check.task_id not in task_set:
                raise ValueError(
                    f"acceptance check {check.check_id} references an unknown task"
                )
        required_states = {"ready", "loading", "empty", "error", "success"}
        missing_states = required_states - {item.kind for item in self.states}
        if missing_states:
            raise ValueError(
                "Web contract must define ready/loading/empty/error/success states; "
                + ", ".join(sorted(missing_states))
            )
        if self.status == "confirmed" and self.confirmation is None:
            raise ValueError("confirmed Web generation contract requires human confirmation")
        if self.status == "proposed" and self.confirmation is not None:
            raise ValueError("proposed Web generation contract cannot carry confirmation")
        thesis_dep = next(
            (item for item in self.dependencies if item.object_type == "product_thesis"),
            None,
        )
        if thesis_dep is None:
            raise ValueError("Web generation contract requires a product thesis dependency")
        if self.product_thesis_revision_id != (
            f"{thesis_dep.object_id}.r{thesis_dep.revision}"
        ):
            raise ValueError("Web generation contract thesis dependency does not match its revision")
        return self


# C2 turns a confirmed Outcome Contract into a measurement plan.  Source layers
# keep what produced an observation apart; each layer caps the evidence level
# a later human EvidenceReview may assign, and a model interpretation is never
# a measurement source.  Planning metadata is not recruited data.
MEASUREMENT_PLAN_VERSION = "c2-v1"
MeasurementSourceLayer = Literal[
    "software_check",
    "runtime_event",
    "user_report",
    "research_observation",
    "expert_review",
]
MEASUREMENT_SOURCE_LAYERS: tuple[str, ...] = (
    "software_check",
    "runtime_event",
    "user_report",
    "research_observation",
    "expert_review",
)
MEASUREMENT_NON_EVIDENCE_LAYERS: tuple[str, ...] = ("model_interpretation",)
MEASUREMENT_LAYER_CEILINGS: dict[str, str] = {
    "software_check": "none",
    "runtime_event": "observed",
    "user_report": "exploratory",
    "research_observation": "observed",
    "expert_review": "exploratory",
}
MEASUREMENT_LAYER_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "deterministic_check": ("software_check",),
    "tool_result": ("software_check", "runtime_event"),
    "expert_review": ("expert_review",),
    "real_user_observation": ("research_observation", "user_report", "runtime_event"),
    "operational_result": ("runtime_event", "research_observation"),
}
MEASUREMENT_REAL_WORLD_EVIDENCE: tuple[str, ...] = (
    "real_user_observation",
    "operational_result",
)
# The deterministic outcome proposal leaves thresholds to a human; a plan
# carrying this text is not operational and cannot be confirmed.
MEASUREMENT_THRESHOLD_PLACEHOLDER = "Must be set by a human before confirmation"
_MEASUREMENT_THRESHOLD_PLACEHOLDERS = frozenset(
    {
        "tbd",
        "todo",
        "placeholder",
        "not set",
        "to be determined",
        MEASUREMENT_THRESHOLD_PLACEHOLDER.casefold(),
    }
)


def is_measurement_threshold_placeholder(value: str) -> bool:
    """Reject blank or unresolved threshold text, independent of casing/spacing."""

    normalized = " ".join(value.split()).casefold()
    return (
        not normalized
        or normalized in _MEASUREMENT_THRESHOLD_PLACEHOLDERS
        or "to be determined" in normalized
        or normalized.startswith("must be set by a human")
    )


MEASUREMENT_RUNTIME_EVENT_BLOCKED_REASON = (
    "PS-O007: the preview records only explicit user reports; "
    "automatic event capture is not authorized"
)


class OutcomeMeasure(MeasureSpec):
    """One operational measure for a contract indicator, bound to a source layer."""

    indicator_id: Identifier
    source_layer: MeasurementSourceLayer
    value_kind: Literal[
        "boolean",
        "count",
        "duration_seconds",
        "ordinal_1_5",
        "categorical",
        "free_text",
    ]
    desired_direction: Identifier
    threshold_or_target: Identifier
    blocked_reason: str | None = None
    on_contradiction: Literal["product_thesis", "outcome_contract", "problem_model"] = (
        "product_thesis"
    )

    @model_validator(mode="after")
    def runtime_events_stay_blocked(self) -> "OutcomeMeasure":
        if self.source_layer == "runtime_event" and not self.blocked_reason:
            raise ValueError(
                "runtime_event measures must stay blocked until automatic capture is authorized"
            )
        return self

    @property
    def collectable(self) -> bool:
        return self.blocked_reason is None

    @property
    def evidence_ceiling(self) -> str:
        return MEASUREMENT_LAYER_CEILINGS[self.source_layer]


class MeasurementGuardrail(FrozenModel):
    """How a prohibited outcome is watched for during a trial."""

    guardrail_id: Identifier
    prohibited_outcome_id: Identifier
    severity: Literal["hard", "strong_avoidance", "watch"]
    detection_method: Identifier
    source_layer: MeasurementSourceLayer
    response: Identifier
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def runtime_events_stay_blocked(self) -> "MeasurementGuardrail":
        if self.source_layer == "runtime_event" and not self.blocked_reason:
            raise ValueError(
                "runtime_event guardrails must stay blocked until automatic capture is authorized"
            )
        return self

    @property
    def collectable(self) -> bool:
        return self.blocked_reason is None

    @property
    def evidence_ceiling(self) -> str:
        return MEASUREMENT_LAYER_CEILINGS[self.source_layer]


class OutcomeMeasurementPlan(FrozenModel):
    """Human-confirmed plan for observing one Outcome Contract revision."""

    measurement_plan_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    outcome_contract_revision_id: Identifier
    status: Literal["proposed", "confirmed"] = "proposed"
    plan_version: Literal["c2-v1"] = MEASUREMENT_PLAN_VERSION
    origin: Literal["deterministic_derivation", "human_revision"]
    measures: tuple[OutcomeMeasure, ...] = Field(min_length=1, max_length=20)
    guardrails: tuple[MeasurementGuardrail, ...] = Field(default=(), max_length=20)
    stop_condition_ids: tuple[Identifier, ...] = ()
    sample_plan: SamplePlan
    observation_window: Identifier
    consent_scope: Identifier
    withdrawal_policy: Identifier
    dependencies: tuple[DependencyRef, ...] = Field(min_length=1, max_length=1)
    confirmation: HumanConfirmation | None = None

    @model_validator(mode="after")
    def validate_measurement_plan(self) -> "OutcomeMeasurementPlan":
        _require_dependencies(self.dependencies, ("outcome_contract",))
        dependency = self.dependencies[0]
        if self.outcome_contract_revision_id != (
            f"{dependency.object_id}.r{dependency.revision}"
        ):
            raise ValueError(
                "measurement plan outcome contract dependency does not match its revision"
            )
        for label, values in (
            ("measure", tuple(item.measure_id for item in self.measures)),
            ("guardrail", tuple(item.guardrail_id for item in self.guardrails)),
            ("stop condition reference", self.stop_condition_ids),
        ):
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(f"duplicate {label} IDs: {sorted(duplicates)}")
        if self.status == "confirmed":
            if self.confirmation is None:
                raise ValueError("confirmed measurement plan requires human confirmation")
            if sum(1 for item in self.measures if item.primary) != 1:
                raise ValueError("confirmed measurement plan requires exactly one primary measure")
            if any(
                is_measurement_threshold_placeholder(item.threshold_or_target)
                for item in self.measures
            ):
                raise ValueError("confirmed measurement plan cannot carry placeholder thresholds")
            if not self.sample_plan.target_population.strip():
                raise ValueError("confirmed measurement plan requires a sample target population")
            if not any(item.strip() for item in self.sample_plan.inclusion_criteria):
                raise ValueError("confirmed measurement plan requires sample inclusion criteria")
            for field_name in ("observation_window", "consent_scope", "withdrawal_policy"):
                if not getattr(self, field_name).strip():
                    raise ValueError(f"confirmed measurement plan requires {field_name}")
        elif self.confirmation is not None:
            raise ValueError("proposed measurement plan cannot carry confirmation")
        return self


class RevisionImpact(FrozenModel):
    dependent_type: Literal[
        "problem_model",
        "outcome_contract",
        "product_thesis",
        "web_generation_contract",
        "outcome_measurement_plan",
    ]
    dependent_id: Identifier
    dependent_revision_id: Identifier
    impact: Literal["review_required", "stale"]
    changed_dependency: DependencyRef
    reason: Identifier


class ProductProjectView(FrozenModel):
    """Read-only composition of independent current revisions for one project."""

    project: ProductProject
    product_intent: ProductIntent | None = None
    problem_model: ProblemModel | None = None
    outcome_contract: OutcomeContract | None = None
    product_theses: tuple[ProductThesis, ...] = ()
    web_generation_contract: WebProductGenerationContract | None = None
    outcome_measurement_plan: OutcomeMeasurementPlan | None = None
    # Why the current measurement plan cannot be confirmed yet, if anything.
    measurement_plan_blockers: tuple[str, ...] = ()
    recorded_impacts: tuple[RevisionImpact, ...] = ()


class ProductProposalJob(FrozenModel):
    """Persisted, revision-pinned work that may only create a proposal."""

    job_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    kind: Literal[
        "product_intent",
        "problem_model",
        "outcome_contract",
        "product_theses",
        "web_generation_contract",
    ]
    status: Literal[
        "queued", "running", "succeeded", "failed", "stale_input", "cancelled"
    ] = "queued"
    provider: Literal["deterministic_fake", "real"] = "deterministic_fake"
    provider_version: Identifier = "b2-v1"
    input_dependencies: tuple[DependencyRef, ...] = Field(min_length=1)
    result_object_id: Identifier
    result_object_ids: tuple[Identifier, ...] = ()
    result_expected_revision: int | None = Field(default=None, ge=1)
    raw_input: str | None = Field(default=None, max_length=PRODUCT_INTENT_MAX_INPUT_CHARS)
    feedback_id: Identifier | None = None
    fingerprint: Identifier
    attempt: int = Field(default=0, ge=0)
    result_revision_id: str | None = None
    result_revision_ids: tuple[str, ...] = ()
    error_code: str | None = None
    error_summary: str | None = None

    @model_validator(mode="after")
    def validate_job_state(self) -> "ProductProposalJob":
        expected_types = {
            "product_intent": {"product_project"},
            "problem_model": {"product_intent"},
            "outcome_contract": {"product_intent", "problem_model"},
            "product_theses": {"problem_model", "outcome_contract"},
            "web_generation_contract": {"product_thesis", "outcome_contract"},
        }[self.kind]
        actual_types = {item.object_type for item in self.input_dependencies}
        # B8: an iteration revises the pinned baseline contract from one
        # explicit feedback report instead of the thesis/outcome pair.
        if self.kind == "web_generation_contract" and self.feedback_id:
            if actual_types != {"web_generation_contract", "preview_feedback"}:
                raise ValueError(
                    "feedback iteration job requires its baseline contract and feedback dependencies"
                )
            baseline = next(
                item for item in self.input_dependencies if item.object_type == "web_generation_contract"
            )
            feedback = next(
                item for item in self.input_dependencies if item.object_type == "preview_feedback"
            )
            if feedback.object_id != self.feedback_id:
                raise ValueError("feedback iteration job dependency does not match its feedback")
            if (
                self.result_object_id != baseline.object_id
                or self.result_expected_revision != baseline.revision
            ):
                raise ValueError("feedback iteration job must revise its baseline contract")
        elif actual_types != expected_types:
            raise ValueError(
                f"{self.kind} job requires dependencies: "
                + ", ".join(sorted(expected_types))
            )
        if self.kind == "product_intent" and not self.raw_input:
            raise ValueError("product intent job requires the original raw input")
        if self.kind != "product_intent" and self.raw_input is not None:
            raise ValueError("only product intent jobs may retain raw input")
        if self.kind != "web_generation_contract" and self.feedback_id:
            raise ValueError("only web generation contract jobs may reference feedback")
        if self.kind == "product_theses":
            if not 2 <= len(self.result_object_ids) <= 3:
                raise ValueError(
                    "product thesis job requires two or three result object IDs"
                )
            if len(set(self.result_object_ids)) != len(self.result_object_ids):
                raise ValueError("product thesis job result object IDs must be unique")
            if self.result_object_id != self.result_object_ids[0]:
                raise ValueError(
                    "product thesis job primary result must be its first result object"
                )
            if self.status == "succeeded" and (
                len(self.result_revision_ids) != len(self.result_object_ids)
                or self.result_revision_id != self.result_revision_ids[0]
            ):
                raise ValueError(
                    "succeeded product thesis job requires every result revision"
                )
        elif self.result_object_ids or self.result_revision_ids:
            raise ValueError("single-result proposal jobs cannot carry result lists")
        elif self.status == "succeeded" and not self.result_revision_id:
            raise ValueError("succeeded proposal job requires a result revision")
        if self.status == "failed" and (not self.error_code or not self.error_summary):
            raise ValueError("failed proposal job requires a safe error code and summary")
        if self.status != "failed" and (self.error_code or self.error_summary):
            raise ValueError("only failed proposal jobs may carry an error")
        return self


# B3 keeps source generation separate from proposal jobs.  A proposal creates
# a revision; a generation job materializes a confirmed realization contract in
# an isolated workspace.  The latter must therefore carry its own budget,
# sandbox declaration, checkpoint and artifact manifest.
GENERATION_JOB_PROVIDER = "deterministic_template"
GENERATION_JOB_VERSION = "b3-v2"
GENERATION_WORKSPACE_RELATIVE_ROOT = "workspaces"
GENERATION_DEFAULT_MAX_ATTEMPTS = 1
GENERATION_DEFAULT_MAX_FILES = 64
GENERATION_DEFAULT_MAX_BYTES = 1024 * 1024
GENERATION_DEFAULT_MAX_DURATION_SECONDS = 60
GENERATION_DEFAULT_MAX_COST_UNITS = 1

# B7m lets a real model write the two source files of the fixed template.  Only
# the human-confirmed Web contract is sent; each model call costs one unit and
# a model job may spend at most two, so a rejected first draft gets one retry.
GENERATION_MODEL_PROVIDER = "model_source"
GENERATION_MODEL_VERSION = "b7m-v1"
GENERATION_SAVED_SOURCE_PROVIDER = "saved_model_revalidation"
GENERATION_SAVED_SOURCE_VERSION = "b7m-saved-source-v1"
GENERATION_MODEL_MAX_CALLS = 2
GENERATION_MODEL_MAX_DURATION_SECONDS = 300
GENERATION_MODEL_SOURCE_PATHS = ("src/App.tsx", "src/styles.css")

# B4 execution is deliberately a different budget and policy from B3 source
# generation.  A generation job may only write files; an execution job is the
# explicit capability that may install the fixed template dependencies and run
# its build/preview/browser checks.
EXECUTION_JOB_PROVIDER = "local_execution_sandbox"
EXECUTION_JOB_VERSION = "b4-v1"
EXECUTION_DEFAULT_MAX_ATTEMPTS = 1
EXECUTION_DEFAULT_MAX_DURATION_SECONDS = 180
EXECUTION_DEFAULT_MAX_OUTPUT_BYTES = 256 * 1024
EXECUTION_DEFAULT_MAX_COST_UNITS = 4

# B5 keeps automatic repair deliberately narrower than source generation. A
# repair planner may only propose bounded, reviewable text patches; applying a
# patch always creates a new generation lineage and a new B4 execution job.
REPAIR_JOB_PROVIDER = "deterministic_repair"
REPAIR_JOB_VERSION = "b5-v1"
REPAIR_DEFAULT_MAX_ATTEMPTS = 2
REPAIR_DEFAULT_MAX_PATCHES = 2
REPAIR_DEFAULT_MAX_PATCH_BYTES = 16 * 1024
REPAIR_DEFAULT_MAX_COST_UNITS = 2


class GenerationBudget(FrozenModel):
    """Small, explicit limits for one local source-generation job."""

    max_attempts: int = Field(default=GENERATION_DEFAULT_MAX_ATTEMPTS, ge=1, le=3)
    max_files: int = Field(default=GENERATION_DEFAULT_MAX_FILES, ge=1, le=GENERATION_DEFAULT_MAX_FILES)
    max_bytes: int = Field(default=GENERATION_DEFAULT_MAX_BYTES, ge=1, le=GENERATION_DEFAULT_MAX_BYTES)
    max_duration_seconds: int = Field(
        default=GENERATION_DEFAULT_MAX_DURATION_SECONDS,
        ge=1,
        le=GENERATION_MODEL_MAX_DURATION_SECONDS,
    )
    max_cost_units: int = Field(
        default=GENERATION_DEFAULT_MAX_COST_UNITS,
        ge=1,
        le=GENERATION_MODEL_MAX_CALLS,
    )


def model_generation_budget() -> "GenerationBudget":
    return GenerationBudget(
        max_attempts=GENERATION_MODEL_MAX_CALLS,
        max_duration_seconds=GENERATION_MODEL_MAX_DURATION_SECONDS,
        max_cost_units=GENERATION_MODEL_MAX_CALLS,
    )


class ModelCallRecord(FrozenModel):
    """Provenance of one model call; the full transcript stays local."""

    attempt: int = Field(ge=1, le=GENERATION_MODEL_MAX_CALLS)
    provider: Identifier
    model: Identifier
    outcome: Literal["accepted", "rejected", "failed"]
    request_sha256: Identifier
    response_sha256: Identifier | None = None
    transcript_path: Identifier
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)
    rejection_reasons: tuple[Identifier, ...] = Field(default=(), max_length=20)
    # Preserve provider-call outcome as immutable provenance. A later local
    # gate correction is recorded separately and never relabels the provider.
    static_gate_revalidated: bool = False
    static_gate_version: Identifier | None = None
    sent_object_types: tuple[Literal["web_generation_contract"], ...] = ("web_generation_contract",)


class GenerationSandboxPolicy(FrozenModel):
    """The B3 sandbox declaration; it is not an execution grant."""

    workspace_scope: Literal["project_job"] = "project_job"
    network_policy: Literal["none"] = "none"
    secret_policy: Literal["none"] = "none"
    execution_policy: Literal["not_executed"] = "not_executed"
    symlink_policy: Literal["deny"] = "deny"


class GeneratedFile(FrozenModel):
    path: Identifier
    byte_count: int = Field(ge=0)
    sha256: Identifier

    @model_validator(mode="after")
    def path_is_relative(self) -> "GeneratedFile":
        if self.path.startswith(("/", "\\")) or ".." in self.path.replace("\\", "/").split("/"):
            raise ValueError("generated file path must stay inside the workspace")
        return self


class GenerationManifest(FrozenModel):
    template_id: Literal["react_typescript_vite_spa"] = WEB_TEMPLATE_ID
    template_version: Identifier = WEB_TEMPLATE_VERSION
    files: tuple[GeneratedFile, ...] = Field(min_length=1)
    total_bytes: int = Field(ge=0)
    manifest_version: Literal["b3-v1"] = "b3-v1"

    @model_validator(mode="after")
    def totals_match(self) -> "GenerationManifest":
        paths = tuple(item.path for item in self.files)
        if len(set(paths)) != len(paths):
            raise ValueError("generation manifest file paths must be unique")
        if self.total_bytes != sum(item.byte_count for item in self.files):
            raise ValueError("generation manifest byte total does not match files")
        return self


class ProductGenerationJob(FrozenModel):
    """Persistent, revision-pinned materialization of a Web contract."""

    job_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    kind: Literal["web_product"] = "web_product"
    status: Literal[
        "queued",
        "running",
        "paused",
        "succeeded",
        "failed",
        "stale_input",
        "budget_exhausted",
        "cancelled",
    ] = "queued"
    provider: Literal["deterministic_template", "deterministic_repair", "model_source", "saved_model_revalidation"] = GENERATION_JOB_PROVIDER
    provider_version: Identifier = GENERATION_JOB_VERSION
    input_dependencies: tuple[DependencyRef, ...] = Field(min_length=1, max_length=1)
    web_generation_contract_revision_id: Identifier
    workspace_id: Identifier
    workspace_relative_path: Identifier
    budget: GenerationBudget = Field(default_factory=GenerationBudget)
    sandbox: GenerationSandboxPolicy = Field(default_factory=GenerationSandboxPolicy)
    fingerprint: Identifier
    materialization_kind: Literal["template", "repair", "model", "saved_model"] = "template"
    parent_generation_job_id: Identifier | None = None
    repair_job_id: Identifier | None = None
    source_generation_job_id: Identifier | None = None
    source_generation_job_revision_id: Identifier | None = None
    source_response_sha256: Identifier | None = None
    static_gate_version: Identifier | None = None
    model_calls: tuple[ModelCallRecord, ...] = Field(default=(), max_length=GENERATION_MODEL_MAX_CALLS)
    attempt: int = Field(default=0, ge=0)
    checkpoint_step: Literal["prepare", "generate", "validate"] | None = None
    consumed_files: int = Field(default=0, ge=0)
    consumed_bytes: int = Field(default=0, ge=0)
    consumed_duration_seconds: float = Field(default=0, ge=0)
    consumed_cost_units: int = Field(default=0, ge=0)
    manifest: GenerationManifest | None = None
    error_code: str | None = None
    error_summary: str | None = None

    @model_validator(mode="after")
    def validate_generation_job(self) -> "ProductGenerationJob":
        if {item.object_type for item in self.input_dependencies} != {"web_generation_contract"}:
            raise ValueError("Web generation job requires one Web generation contract dependency")
        dependency = self.input_dependencies[0]
        if self.web_generation_contract_revision_id != f"{dependency.object_id}.r{dependency.revision}":
            raise ValueError("generation job contract dependency does not match its revision")
        if self.workspace_relative_path.startswith(("/", "\\")) or ".." in self.workspace_relative_path.replace("\\", "/").split("/"):
            raise ValueError("generation workspace path must be relative and contained")
        if self.materialization_kind == "repair":
            if self.provider != "deterministic_repair" or self.provider_version != REPAIR_JOB_VERSION or not self.parent_generation_job_id or not self.repair_job_id:
                raise ValueError("repair generation requires repair provider and lineage")
            if self.source_generation_job_id or self.source_generation_job_revision_id or self.source_response_sha256 or self.static_gate_version:
                raise ValueError("repair generation cannot carry saved-model source provenance")
        elif self.materialization_kind == "model":
            if self.provider != GENERATION_MODEL_PROVIDER or self.provider_version != GENERATION_MODEL_VERSION or self.parent_generation_job_id or self.repair_job_id:
                raise ValueError("model generation requires the model provider and no repair lineage")
            if self.source_generation_job_id or self.source_generation_job_revision_id or self.source_response_sha256 or self.static_gate_version:
                raise ValueError("provider model generation cannot carry saved-source lineage")
            if self.budget.max_cost_units > GENERATION_MODEL_MAX_CALLS or len(self.model_calls) > self.consumed_cost_units:
                raise ValueError("model generation calls exceed the consumed budget")
            if [item.attempt for item in self.model_calls] != list(range(1, len(self.model_calls) + 1)):
                raise ValueError("model call attempts must be sequential")
            if self.status == "succeeded" and (
                not self.model_calls
                or not (
                    self.model_calls[-1].outcome == "accepted"
                    or (
                        self.model_calls[-1].outcome == "rejected"
                        and self.model_calls[-1].static_gate_revalidated
                        and self.model_calls[-1].static_gate_version is not None
                    )
                )
            ):
                raise ValueError("succeeded model generation requires a provider-accepted call or an audited local gate revalidation")
        elif self.materialization_kind == "saved_model":
            if self.provider != GENERATION_SAVED_SOURCE_PROVIDER or self.provider_version != GENERATION_SAVED_SOURCE_VERSION:
                raise ValueError("saved-model materialization requires its deterministic local provider")
            if self.parent_generation_job_id or self.repair_job_id or self.model_calls:
                raise ValueError("saved-model materialization uses explicit source provenance, not provider calls or repair lineage")
            if not self.source_generation_job_id or not self.source_generation_job_revision_id or not self.source_response_sha256 or not self.static_gate_version:
                raise ValueError("saved-model materialization requires a pinned source job, response hash, and gate version")
            if self.consumed_cost_units > 0:
                raise ValueError("saved-model materialization cannot charge model provider cost")
        elif self.provider != "deterministic_template" or self.parent_generation_job_id or self.repair_job_id or self.source_generation_job_id or self.source_generation_job_revision_id or self.source_response_sha256 or self.static_gate_version:
            raise ValueError("template generation cannot carry model or repair lineage")
        if self.materialization_kind not in {"model", "saved_model"} and self.model_calls:
            raise ValueError("only model generation may record model calls")
        if self.status == "succeeded" and self.manifest is None:
            raise ValueError("succeeded generation job requires an artifact manifest")
        if self.status in {"failed", "budget_exhausted"} and (
            not self.error_code or not self.error_summary
        ):
            raise ValueError(
                "failed or budget-exhausted generation job requires a safe error code and summary"
            )
        if self.status not in {"failed", "budget_exhausted"} and (self.error_code or self.error_summary):
            raise ValueError("only failed or budget-exhausted generation jobs may carry an error")
        if self.manifest is not None:
            if self.manifest.template_id != WEB_TEMPLATE_ID or self.manifest.template_version != WEB_TEMPLATE_VERSION:
                raise ValueError("generation manifest template does not match the B3 template")
            if len(self.manifest.files) > self.budget.max_files or self.manifest.total_bytes > self.budget.max_bytes:
                raise ValueError("generation manifest exceeds the job budget")
        return self


class ExecutionBudget(FrozenModel):
    """Boundaries for one install/build/run/browser execution attempt."""

    max_attempts: int = Field(default=EXECUTION_DEFAULT_MAX_ATTEMPTS, ge=1, le=3)
    max_duration_seconds: int = Field(
        default=EXECUTION_DEFAULT_MAX_DURATION_SECONDS,
        ge=1,
        le=EXECUTION_DEFAULT_MAX_DURATION_SECONDS,
    )
    max_output_bytes: int = Field(
        default=EXECUTION_DEFAULT_MAX_OUTPUT_BYTES,
        ge=1024,
        le=EXECUTION_DEFAULT_MAX_OUTPUT_BYTES,
    )
    max_cost_units: int = Field(
        default=EXECUTION_DEFAULT_MAX_COST_UNITS,
        ge=1,
        le=EXECUTION_DEFAULT_MAX_COST_UNITS,
    )


class RepairBudget(FrozenModel):
    """Limits for one deterministic repair lineage."""

    max_attempts: int = Field(default=REPAIR_DEFAULT_MAX_ATTEMPTS, ge=1, le=3)
    max_patches: int = Field(default=REPAIR_DEFAULT_MAX_PATCHES, ge=1, le=REPAIR_DEFAULT_MAX_PATCHES)
    max_patch_bytes: int = Field(
        default=REPAIR_DEFAULT_MAX_PATCH_BYTES,
        ge=1,
        le=REPAIR_DEFAULT_MAX_PATCH_BYTES,
    )
    max_cost_units: int = Field(
        default=REPAIR_DEFAULT_MAX_COST_UNITS,
        ge=1,
        le=REPAIR_DEFAULT_MAX_COST_UNITS,
    )


class RepairPatch(FrozenModel):
    """A single exact text replacement against a pinned generated file."""

    path: Identifier
    expected_sha256: Identifier
    search: str = Field(min_length=1, max_length=4096)
    replace: str = Field(default="", max_length=16 * 1024)
    rationale: Identifier = Field(max_length=240)


class RepairAttempt(FrozenModel):
    """Persisted safe summary of one repair proposal/application/verification."""

    attempt: int = Field(ge=1)
    execution_job_revision_id: Identifier
    failure_step: Literal["install", "build", "run", "browser"]
    failure_code: Identifier
    diagnosis: Identifier = Field(max_length=240)
    patches: tuple[RepairPatch, ...] = ()
    status: Literal["planned", "applied", "verified", "failed", "unsupported"]
    cost_units: int = Field(default=1, ge=0)
    output_generation_job_id: Identifier | None = None
    output_execution_job_id: Identifier | None = None
    error_code: str | None = None
    error_summary: str | None = None


class ProductRepairJob(FrozenModel):
    """Revisioned B5 repair orchestration, separate from execution state."""

    job_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    kind: Literal["web_product_repair"] = "web_product_repair"
    status: Literal[
        "queued",
        "running",
        "succeeded",
        "failed",
        "stale_input",
        "budget_exhausted",
        "cancelled",
    ] = "queued"
    provider: Literal["deterministic_repair"] = REPAIR_JOB_PROVIDER
    provider_version: Identifier = REPAIR_JOB_VERSION
    input_dependencies: tuple[DependencyRef, ...] = Field(min_length=1, max_length=1)
    execution_job_id: Identifier
    execution_job_revision_id: Identifier
    generation_job_id: Identifier
    generation_job_revision_id: Identifier
    budget: RepairBudget = Field(default_factory=RepairBudget)
    fingerprint: Identifier
    attempt: int = Field(default=0, ge=0)
    attempts: tuple[RepairAttempt, ...] = ()
    consumed_cost_units: int = Field(default=0, ge=0)
    latest_generation_job_id: Identifier | None = None
    latest_execution_job_id: Identifier | None = None
    error_code: str | None = None
    error_summary: str | None = None

    @model_validator(mode="after")
    def validate_repair_job(self) -> "ProductRepairJob":
        dependency = self.input_dependencies[0]
        if dependency.object_type != "product_execution_job" or dependency.object_id != self.execution_job_id:
            raise ValueError("repair job requires its execution dependency")
        if self.execution_job_revision_id != f"{dependency.object_id}.r{dependency.revision}":
            raise ValueError("repair job dependency does not match its revision")
        if not self.generation_job_revision_id.startswith(f"{self.generation_job_id}.r"):
            raise ValueError("repair job generation lineage does not match its job")
        if self.consumed_cost_units > self.budget.max_cost_units:
            raise ValueError("repair job cost exceeds budget")
        if self.attempt > self.budget.max_attempts or len(self.attempts) > self.budget.max_attempts:
            raise ValueError("repair job attempts exceed budget")
        attempt_numbers = tuple(item.attempt for item in self.attempts)
        if len(set(attempt_numbers)) != len(attempt_numbers):
            raise ValueError("repair attempts must be unique")
        if any(len(item.patches) > self.budget.max_patches for item in self.attempts):
            raise ValueError("repair attempt contains too many patches")
        if any(sum(len(p.search.encode()) + len(p.replace.encode()) for p in item.patches) > self.budget.max_patch_bytes for item in self.attempts):
            raise ValueError("repair attempt patch bytes exceed budget")
        if self.status == "succeeded":
            if not self.latest_generation_job_id or not self.latest_execution_job_id or not any(item.status == "verified" for item in self.attempts):
                raise ValueError("succeeded repair job requires a verified output")
        if self.status in {"failed", "budget_exhausted", "stale_input"} and not self.error_code:
            raise ValueError("unsuccessful repair job requires an error code")
        if self.status not in {"failed", "budget_exhausted", "stale_input"} and (self.error_code or self.error_summary):
            raise ValueError("only unsuccessful repair jobs may carry an error")
        return self


class ExecutionSandboxPolicy(FrozenModel):
    """Explicit B4 execution grant; never implied by source generation."""

    workspace_scope: Literal["generation_job"] = "generation_job"
    dependency_policy: Literal["fixed_npm_template"] = "fixed_npm_template"
    install_network_policy: Literal["registry_only"] = "registry_only"
    runtime_network_policy: Literal["none"] = "none"
    secret_policy: Literal["none"] = "none"
    command_policy: Literal["allowlisted_npm_scripts"] = "allowlisted_npm_scripts"
    browser_policy: Literal["chromium_headless"] = "chromium_headless"


class ExecutionStep(FrozenModel):
    """Safe summary of one execution phase; raw logs are never persisted."""

    name: Literal["install", "build", "run", "browser"]
    status: Literal["pending", "running", "succeeded", "failed", "skipped"] = "pending"
    exit_code: int | None = None
    duration_seconds: float = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)
    summary: str | None = None
    error_code: str | None = None


class ProductExecutionJob(FrozenModel):
    """Revisioned, separately authorized execution of a generated workspace."""

    job_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    kind: Literal["web_product_execution"] = "web_product_execution"
    status: Literal[
        "queued",
        "running",
        "succeeded",
        "failed",
        "stale_input",
        "budget_exhausted",
        "cancelled",
    ] = "queued"
    provider: Literal["local_execution_sandbox"] = EXECUTION_JOB_PROVIDER
    provider_version: Identifier = EXECUTION_JOB_VERSION
    input_dependencies: tuple[DependencyRef, ...] = Field(min_length=1, max_length=1)
    generation_job_id: Identifier
    generation_job_revision_id: Identifier
    workspace_relative_path: Identifier
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    sandbox: ExecutionSandboxPolicy = Field(default_factory=ExecutionSandboxPolicy)
    fingerprint: Identifier
    attempt: int = Field(default=0, ge=0)
    checkpoint_step: Literal["install", "build", "run", "browser"] | None = None
    steps: tuple[ExecutionStep, ...] = ()
    consumed_duration_seconds: float = Field(default=0, ge=0)
    consumed_output_bytes: int = Field(default=0, ge=0)
    consumed_cost_units: int = Field(default=0, ge=0)
    build_artifact_relative_path: str | None = None
    browser_report_relative_path: str | None = None
    error_code: str | None = None
    error_summary: str | None = None

    @model_validator(mode="after")
    def validate_execution_job(self) -> "ProductExecutionJob":
        if {item.object_type for item in self.input_dependencies} != {"product_generation_job"}:
            raise ValueError("execution job requires one product generation job dependency")
        dependency = self.input_dependencies[0]
        if dependency.object_id != self.generation_job_id:
            raise ValueError("execution job dependency does not match generation job")
        if self.generation_job_revision_id != f"{dependency.object_id}.r{dependency.revision}":
            raise ValueError("execution job dependency does not match its revision")
        if self.workspace_relative_path.startswith(("/", "\\")) or ".." in self.workspace_relative_path.replace("\\", "/").split("/"):
            raise ValueError("execution workspace path must be relative and contained")
        names = tuple(step.name for step in self.steps)
        if len(set(names)) != len(names):
            raise ValueError("execution steps must be unique")
        if self.status == "succeeded" and {step.name for step in self.steps} != {"install", "build", "run", "browser"}:
            raise ValueError("succeeded execution job requires all execution steps")
        if self.status in {"failed", "budget_exhausted", "stale_input"} and self.error_code is None:
            raise ValueError("unsuccessful execution job requires an error code")
        if self.status not in {"failed", "budget_exhausted", "stale_input"} and (self.error_code or self.error_summary):
            raise ValueError("only unsuccessful execution jobs may carry an error")
        if self.consumed_output_bytes > self.budget.max_output_bytes:
            raise ValueError("execution output exceeds budget")
        for label, path in (("build artifact", self.build_artifact_relative_path), ("browser report", self.browser_report_relative_path)):
            if path is not None and (path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/")):
                raise ValueError(f"{label} path must stay inside the workspace")
        return self


# B6 delivery bundles package only a verified execution.  They are immutable
# single-revision records: a changed workspace needs a new execution and a new
# bundle, never an edited one.
DELIVERY_BUNDLE_FORMAT_VERSION = "b6-v1"
DELIVERY_MAX_FILES = 256
DELIVERY_MAX_BYTES = 8 * 1024 * 1024
DELIVERY_BASE_UNVERIFIED_CLAIMS = (
    "No real-user, task or outcome evidence exists for this product; outcome evidence level is none.",
    "Content and structure come from a deterministic template and fake provider, not research or a real model.",
    "Execution ran as a local allowlisted subprocess without OS/container isolation.",
    "Browser checks covered headless Chromium desktop only; no cross-browser, mobile or manual accessibility review.",
    "Screenshots are review artifacts, not an approved visual regression baseline.",
    "package-lock.json and node_modules are excluded; dependency versions are pinned in package.json only.",
)


class DeliveryBundleFile(FrozenModel):
    path: Identifier
    role: Literal["source", "build", "verification", "notes"]
    byte_count: int = Field(ge=0)
    sha256: Identifier

    @model_validator(mode="after")
    def path_is_contained(self) -> "DeliveryBundleFile":
        parts = self.path.split("/")
        if "\\" in self.path or self.path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("delivery bundle path must be a normalized relative path")
        return self


class ProductDeliveryBundle(FrozenModel):
    """Immutable, content-addressed export of one verified execution."""

    bundle_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    kind: Literal["web_product_delivery"] = "web_product_delivery"
    format_version: Literal["b6-v1"] = DELIVERY_BUNDLE_FORMAT_VERSION
    input_dependencies: tuple[DependencyRef, ...] = Field(min_length=1, max_length=1)
    execution_job_id: Identifier
    execution_job_revision_id: Identifier
    generation_job_id: Identifier
    generation_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    contract_is_current: bool
    materialization_kind: Literal["template", "repair", "model"]
    parent_generation_job_id: Identifier | None = None
    repair_job_id: Identifier | None = None
    template_id: Literal["react_typescript_vite_spa"] = WEB_TEMPLATE_ID
    template_version: Identifier = WEB_TEMPLATE_VERSION
    verification_steps: tuple[ExecutionStep, ...] = Field(min_length=4, max_length=4)
    files: tuple[DeliveryBundleFile, ...] = Field(min_length=1, max_length=DELIVERY_MAX_FILES)
    total_bytes: int = Field(ge=0, le=DELIVERY_MAX_BYTES)
    archive_sha256: Identifier
    archive_bytes: int = Field(ge=1)
    unverified_claims: tuple[Identifier, ...] = Field(min_length=1)
    outcome_evidence_level: Literal["none"] = "none"
    fingerprint: Identifier

    @model_validator(mode="after")
    def validate_delivery_bundle(self) -> "ProductDeliveryBundle":
        if self.meta.revision != 1 or self.revision_id != f"{self.bundle_id}.r1":
            raise ValueError("delivery bundles are immutable single-revision records")
        dependency = self.input_dependencies[0]
        if dependency.object_type != "product_execution_job" or dependency.object_id != self.execution_job_id:
            raise ValueError("delivery bundle requires its execution dependency")
        if self.execution_job_revision_id != f"{dependency.object_id}.r{dependency.revision}":
            raise ValueError("delivery bundle dependency does not match its revision")
        if not self.generation_job_revision_id.startswith(f"{self.generation_job_id}.r"):
            raise ValueError("delivery bundle generation lineage does not match its job")
        if tuple(step.name for step in self.verification_steps) != ("install", "build", "run", "browser") or any(
            step.status != "succeeded" for step in self.verification_steps
        ):
            raise ValueError("delivery bundle requires four succeeded execution steps")
        if self.materialization_kind == "repair":
            if not self.parent_generation_job_id or not self.repair_job_id:
                raise ValueError("repaired delivery bundle requires repair lineage")
        elif self.parent_generation_job_id or self.repair_job_id:
            raise ValueError("template delivery bundle cannot carry repair lineage")
        paths = tuple(item.path for item in self.files)
        if len(set(paths)) != len(paths):
            raise ValueError("delivery bundle file paths must be unique")
        if self.total_bytes != sum(item.byte_count for item in self.files):
            raise ValueError("delivery bundle byte total does not match files")
        roles = {item.role for item in self.files}
        if not {"source", "build", "notes"} <= roles:
            raise ValueError("delivery bundle requires source, build and notes files")
        return self


# B7 preview feedback (PS-O007): only explicit, user-written reports are
# recorded.  Nothing is captured automatically from the preview.  Withdrawal
# replaces the single stored record with a tombstone so the body is erased
# rather than hidden behind a newer revision.
PREVIEW_FEEDBACK_CONSENT_VERSION = "b7-explicit-v1"
PREVIEW_FEEDBACK_MAX_TEXT = 2000
PREVIEW_FEEDBACK_CONSENT_STATEMENT = (
    "Only what you write here is recorded: the text, its category, the page/task/state you anchor it to, "
    "the preview revision, your name and the time. No clicks, navigation, typing, screen recording or "
    "screenshots are captured from the preview. You can withdraw a report at any time; its text is then erased."
)
PREVIEW_FEEDBACK_CAPTURED = ("text", "category", "anchor", "bundle_revision", "actor", "time")
PREVIEW_FEEDBACK_NOT_CAPTURED = ("clicks", "navigation", "typed_input", "screen_recording", "screenshots", "dwell_time")


class PreviewFeedbackConsent(FrozenModel):
    version: Literal["b7-explicit-v1"] = PREVIEW_FEEDBACK_CONSENT_VERSION
    granted_by: Identifier
    granted_at: datetime


class PreviewFeedbackAnchor(FrozenModel):
    screen_id: Identifier
    task_id: Identifier | None = None
    state_id: Identifier | None = None


class PreviewFeedback(FrozenModel):
    """One explicit report about a previewed delivery bundle revision."""

    feedback_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    delivery_bundle_id: Identifier
    delivery_bundle_revision_id: Identifier
    execution_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    anchor: PreviewFeedbackAnchor
    status: Literal["submitted", "withdrawn"] = "submitted"
    category: Literal["bug", "confusing", "missing", "works"] | None = None
    text: str | None = Field(default=None, min_length=1, max_length=PREVIEW_FEEDBACK_MAX_TEXT)
    submitted_by: Identifier
    submitted_at: datetime
    consent: PreviewFeedbackConsent
    withdrawn_at: datetime | None = None
    # B8: set only by an explicit human decision; never inferred from a job.
    disposition: Literal["pending", "incorporated", "deferred"] = "pending"
    evidence_level: Literal["user_report"] = "user_report"
    automatic_capture: Literal["none"] = "none"

    @model_validator(mode="after")
    def validate_preview_feedback(self) -> "PreviewFeedback":
        if self.revision_id != f"{self.feedback_id}.r{self.meta.revision}":
            raise ValueError("preview feedback revision id does not match its revision")
        if self.consent.granted_by != self.submitted_by:
            raise ValueError("preview feedback consent must be granted by its submitter")
        if not self.delivery_bundle_revision_id.startswith(f"{self.delivery_bundle_id}.r"):
            raise ValueError("preview feedback bundle revision does not match its bundle")
        if self.status == "submitted":
            if self.category is None or self.text is None or self.withdrawn_at is not None:
                raise ValueError("submitted preview feedback requires a category and text")
            if self.meta.revision == 1 and self.disposition != "pending":
                raise ValueError("new preview feedback starts with a pending disposition")
        else:
            if self.meta.revision < 2 or self.category is not None or self.text is not None or self.withdrawn_at is None:
                raise ValueError("withdrawn preview feedback is a later-revision tombstone without content")
            if self.disposition != "pending":
                raise ValueError("withdrawn preview feedback keeps no disposition")
        return self
