"""Proposal providers for the Product Studio application boundary."""

from __future__ import annotations

import os
import time
from typing import Protocol

from psyteardown.product.commands import (
    OutcomeContractProposal,
    ProblemModelProposal,
    ProductIntentProposal,
    ProductThesisProposal,
    WebProductGenerationContractProposal,
)
from psyteardown.product.models import (
    CompetingExplanation,
    DeliveryEstimate,
    DeliveryMaturity,
    FalsifiablePrediction,
    MechanismHypothesis,
    OutcomeContract,
    PreviewFeedback,
    ProblemFact,
    ProblemModel,
    ProblemUnknown,
    ProhibitedOutcome,
    ResourceBoundary,
    SourceReference,
    StopCondition,
    SuccessIndicator,
    TargetOutcome,
    ProductIntent,
    ProductThesis,
    ValidationStep,
    WebAcceptanceCheck,
    WebContentSlot,
    WebProductGenerationContract,
    WebScreenSpec,
    WebStateSpec,
    WebTaskSpec,
    WEB_TEMPLATE_VERSION,
    MEASUREMENT_THRESHOLD_PLACEHOLDER,
)


class ProductContractProposalProvider(Protocol):
    name: str
    version: str

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal: ...

    def propose_problem(self, intent: ProductIntent, *, job_id: str) -> ProblemModelProposal: ...

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal: ...

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]: ...

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal: ...

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal: ...


class DeterministicFakeProductContractProvider:
    """Network-free A5/B1 provider that makes its synthetic status explicit."""

    name = "deterministic_fake"
    version = "b2-v1"

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal:
        return ProductIntentProposal(
            desired_change=raw_input,
            affected_people=[
                "People implied by the original input — human correction required"
            ],
            current_situation=raw_input,
            explicit_non_goals=[],
            known_constraints=[],
            resource_preferences=[],
            source_refs=[
                SourceReference(
                    source_type="user_input",
                    source_id=f"{job_id}:raw-input",
                    locator="product_proposal_job.raw_input",
                ),
                SourceReference(
                    source_type="model_proposal",
                    source_id=job_id,
                    revision_id=self.version,
                ),
            ],
        )

    def propose_problem(
        self, intent: ProductIntent, *, job_id: str
    ) -> ProblemModelProposal:
        reported = intent.current_situation or intent.desired_change
        fact = ProblemFact(
            fact_id=f"{job_id}-reported-context",
            statement=f"The user reports: {reported}",
            source_refs=intent.source_refs,
        )
        return ProblemModelProposal(
            intent_revision_id=intent.revision_id,
            facts=[fact],
            assumptions=[],
            unknowns=[
                ProblemUnknown(
                    unknown_id=f"{job_id}-observable-failure",
                    question=(
                        "Which observable event most clearly shows that the current "
                        "situation is failing the affected people?"
                    ),
                    decision_impact=(
                        "It changes which intervention and success measure are appropriate."
                    ),
                    next_step="Observe or document one concrete recent occurrence.",
                ),
                ProblemUnknown(
                    unknown_id=f"{job_id}-existing-alternative",
                    question="Which existing alternative has already been tried, and why was it insufficient?",
                    decision_impact="It determines whether a new product is needed at all.",
                    next_step="Compare the current workaround before selecting a product path.",
                ),
            ],
            competing_explanations=[
                CompetingExplanation(
                    explanation_id=f"{job_id}-tool-friction",
                    statement=(
                        "The reported difficulty may be driven primarily by friction in "
                        "the current tools or process."
                    ),
                    supporting_fact_ids=(fact.fact_id,),
                    cheapest_falsification=(
                        "Try one reversible session with the suspected tool or process "
                        "friction removed."
                    ),
                ),
                CompetingExplanation(
                    explanation_id=f"{job_id}-context-clarity",
                    statement=(
                        "The reported difficulty may instead be driven by unclear goals "
                        "or contextual constraints rather than a missing product."
                    ),
                    supporting_fact_ids=(fact.fact_id,),
                    cheapest_falsification=(
                        "Run one comparable session with an explicit goal and constraints "
                        "but no new product."
                    ),
                ),
            ],
            stakeholder_tensions=[],
        )

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal:
        indicator_id = f"{job_id}-indicator"
        prohibited = [
            ProhibitedOutcome(
                prohibited_outcome_id=f"{job_id}-non-goal-{index}",
                description=value,
                severity="hard",
                detection_method="Explicit human review before trial and user report during trial",
                response="Stop the trial and reframe the product path",
            )
            for index, value in enumerate(intent.explicit_non_goals, start=1)
        ]
        preferences = tuple(intent.resource_preferences)
        known_constraints = tuple(intent.known_constraints)
        return OutcomeContractProposal(
            intent_revision_id=intent.revision_id,
            problem_model_revision_id=problem.revision_id,
            target_segments=list(intent.affected_people),
            applicable_contexts=[
                intent.current_situation or "The context described in the confirmed ProductIntent"
            ],
            target_outcomes=[
                TargetOutcome(
                    outcome_id=f"{job_id}-outcome",
                    description=intent.desired_change,
                    indicator_ids=(indicator_id,),
                )
            ],
            success_indicators=[
                SuccessIndicator(
                    indicator_id=indicator_id,
                    operational_definition=(
                        "A user-observable instance of the desired change during the "
                        "declared context"
                    ),
                    observation_method="Consented real task observation and user report",
                    desired_direction="improve relative to the user's unaided baseline",
                    threshold_or_target=MEASUREMENT_THRESHOLD_PLACEHOLDER,
                    required_evidence="real_user_observation",
                )
            ],
            prohibited_outcomes=prohibited,
            prohibited_outcomes_reviewed=False,
            resource_boundary=ResourceBoundary(
                time_budget=preferences[0] if preferences else None,
                data_boundary=(
                    "; ".join(known_constraints) if known_constraints else None
                ),
                explicit_unknowns=(
                    ()
                    if preferences or known_constraints
                    else ("Time, cost, attention, maintenance, and data limits need human review",)
                ),
            ),
            stop_conditions=[
                StopCondition(
                    condition_id=f"{job_id}-stop",
                    condition=(
                        "A prohibited outcome occurs, or the target indicator cannot be "
                        "observed without exceeding the agreed boundary"
                    ),
                    action="reframe",
                )
            ],
            # A6 freezes a runnable Web prototype as the first slice's
            # minimum delivery target. This remains a proposal until a
            # human confirms the complete OutcomeContract.
            minimum_delivery_maturity=DeliveryMaturity.RUNNABLE_PROTOTYPE,
            required_real_world_evidence=[
                "At least one consented real task observation in the applicable context"
            ],
        )

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]:
        """Return three inspectable B1 paths without claiming research evidence."""

        source = SourceReference(
            source_type="model_proposal",
            source_id=job_id,
            revision_id="b1-thesis-set-v1",
        )
        common = {
            "problem_model_revision_id": problem.revision_id,
            "outcome_contract_revision_id": contract.revision_id,
            "realization_modes": ["software"],
        }
        return (
            ProductThesisProposal(
                **common,
                name="Urgency-aware interruption gate",
                product_promise=(
                    "Hold non-urgent contact until the chosen focus boundary while "
                    "keeping an explicit urgent bypass under the user's control."
                ),
                differentiation=(
                    "Changes when interruptions surface; it does not score the user "
                    "or infer urgency from message content."
                ),
                mechanism_hypotheses=[
                    MechanismHypothesis(
                        mechanism_id=f"{job_id}-gate-mechanism",
                        condition="The user has declared a bounded focus session and explicit bypass rules.",
                        proposed_intervention="Queue non-urgent interruption cards and expose an always-visible stop and urgent bypass.",
                        expected_change="Fewer involuntary switches without removing control over urgent contact.",
                        uncertainty="A visible queue may create anticipatory anxiety or require unavailable integrations.",
                        evidence_refs=(source,),
                    )
                ],
                falsifiable_predictions=[
                    FalsifiablePrediction(
                        prediction_id=f"{job_id}-gate-prediction",
                        prediction="Declared sessions contain fewer unplanned switches than the same user's unaided baseline.",
                        failure_observation="Switches do not fall, control ratings worsen, or an urgent contact is delayed without explicit choice.",
                        cheapest_test="Run a local clickable queue with scripted interruption cards; do not connect real accounts.",
                    )
                ],
                validation_strategy=[
                    ValidationStep(
                        validation_step_id=f"{job_id}-gate-validation",
                        question="Can the user understand, bypass, stop, and recover every queued item?",
                        method="Scripted browser tasks covering urgent bypass, stop, recovery, and empty/error states.",
                        evidence_level="deterministic_check",
                        pass_condition="All control paths complete without hidden collection or an unrecoverable item.",
                        estimated_cost="One static local Web prototype and one Playwright task suite.",
                    )
                ],
                key_unknowns=[
                    "Whether delayed items reduce switching or merely move anxiety into the queue."
                ],
                key_risks=[
                    "A real integration could misroute urgent contact or require excessive permissions."
                ],
                delivery_estimate=DeliveryEstimate(
                    initial_delivery_cost="Medium: session controls, queue states, and scripted contact fixtures.",
                    operating_cost="Low for a local prototype; unknown for real communication integrations.",
                    maintenance_burden="High if adapters for external communication tools are later added.",
                ),
            ),
            ProductThesisProposal(
                **common,
                name="Deliberate contact checkpoints",
                product_promise=(
                    "Replace repeated anticipatory checking with user-chosen contact "
                    "checkpoints and an explicit emergency exception."
                ),
                differentiation=(
                    "Changes the user's checking rhythm rather than intercepting or "
                    "classifying incoming messages."
                ),
                mechanism_hypotheses=[
                    MechanismHypothesis(
                        mechanism_id=f"{job_id}-checkpoint-mechanism",
                        condition="The user worries that staying focused could make an important contact easy to miss.",
                        proposed_intervention="Precommit the next check time, show the remaining interval, and keep a manual emergency channel visible.",
                        expected_change="Less voluntary checking between declared checkpoints while preserving perceived control.",
                        uncertainty="A countdown could increase time monitoring or become another source of pressure.",
                        evidence_refs=(source,),
                    )
                ],
                falsifiable_predictions=[
                    FalsifiablePrediction(
                        prediction_id=f"{job_id}-checkpoint-prediction",
                        prediction="Voluntary message checks between checkpoints decrease without a drop in reported control.",
                        failure_observation="Users check outside checkpoints as often as before or report greater vigilance and pressure.",
                        cheapest_test="Compare one paper-timer session and one no-assistance session before building integrations.",
                    )
                ],
                validation_strategy=[
                    ValidationStep(
                        validation_step_id=f"{job_id}-checkpoint-validation",
                        question="Does a declared checkpoint reduce checking without making the session feel coercive?",
                        method="A consented within-person task comparison using manual check counts and a control rating.",
                        evidence_level="real_user_observation",
                        pass_condition="Fewer checks than baseline and no deterioration in the participant's control rating.",
                        estimated_cost="Two short observed sessions; no external account access.",
                    )
                ],
                key_unknowns=[
                    "Whether anticipatory checking is a material cause of switching for the target user."
                ],
                key_risks=[
                    "Visible time pressure may worsen anxiety or encourage productivity self-scoring."
                ],
                delivery_estimate=DeliveryEstimate(
                    initial_delivery_cost="Low: local session setup, checkpoint timer, and explicit bypass state.",
                    operating_cost="Very low with no external service integration.",
                    maintenance_burden="Low; browser timing and local persistence only.",
                ),
            ),
            ProductThesisProposal(
                **common,
                name="Re-entry bookmark",
                product_promise=(
                    "Make unavoidable interruptions cheaper by preserving the exact "
                    "next step and guiding a deliberate return to the focus task."
                ),
                differentiation=(
                    "Reduces recovery cost after an interruption instead of suppressing, "
                    "delaying, or scheduling contact."
                ),
                mechanism_hypotheses=[
                    MechanismHypothesis(
                        mechanism_id=f"{job_id}-bookmark-mechanism",
                        condition="An interruption cannot or should not be prevented.",
                        proposed_intervention="Capture a one-line next action before switching and restore it through a short return ritual.",
                        expected_change="Fewer secondary detours and faster return after unavoidable contact.",
                        uncertainty="Capturing a bookmark may add friction at the worst possible moment.",
                        evidence_refs=(source,),
                    )
                ],
                falsifiable_predictions=[
                    FalsifiablePrediction(
                        prediction_id=f"{job_id}-bookmark-prediction",
                        prediction="After a scripted interruption, users resume the declared task with fewer unrelated detours.",
                        failure_observation="Bookmark capture is skipped, return takes no less time, or extra steps cause frustration.",
                        cheapest_test="Use a one-screen bookmark prototype with one scripted interruption and timed resumption task.",
                    )
                ],
                validation_strategy=[
                    ValidationStep(
                        validation_step_id=f"{job_id}-bookmark-validation",
                        question="Is the bookmark fast enough to use and specific enough to support resumption?",
                        method="Scripted browser task first, followed by a consented observed work interruption.",
                        evidence_level="real_user_observation",
                        pass_condition="The bookmark is captured in one decision and supports return without an unrelated detour.",
                        estimated_cost="One small local Web flow and one observed task session.",
                    )
                ],
                key_unknowns=[
                    "Whether recovery cost, rather than interruption arrival, drives the measured task switches."
                ],
                key_risks=[
                    "The capture step may become burdensome or accidentally retain sensitive task text."
                ],
                delivery_estimate=DeliveryEstimate(
                    initial_delivery_cost="Low: bookmark capture, interruption state, and guided return flow.",
                    operating_cost="Very low with local-only storage.",
                    maintenance_burden="Low, provided no cross-application capture is added.",
                ),
            ),
        )

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Create a deterministic, content-minimal B2 contract suggestion.

        This only describes a later realization. It intentionally creates no
        source files, installs no dependencies, and makes no claim about a
        running product or real-user outcome.
        """

        focus_screen = f"{suggestion_id}-focus-screen"
        interruption_screen = f"{suggestion_id}-interruption-screen"
        start_task = f"{suggestion_id}-start-focus"
        interrupt_task = f"{suggestion_id}-handle-interruption"
        finish_task = f"{suggestion_id}-finish-focus"
        stop_task = f"{suggestion_id}-stop-recover"
        state_ids = {
            kind: f"{suggestion_id}-{kind}" for kind in
            ("ready", "loading", "empty", "error", "success", "paused", "stopped")
        }
        return WebProductGenerationContractProposal(
            product_thesis_revision_id=thesis.revision_id,
            outcome_contract_revision_id=contract.revision_id,
            app_title=thesis.name,
            screens=[
                WebScreenSpec(
                    screen_id=focus_screen,
                    title="Focus session",
                    purpose="Declare a bounded focus session and show the user's current control boundary.",
                    task_ids=(start_task, finish_task, stop_task),
                    state_ids=(state_ids["ready"], state_ids["loading"], state_ids["success"], state_ids["paused"], state_ids["stopped"]),
                ),
                WebScreenSpec(
                    screen_id=interruption_screen,
                    title="Interruption decision",
                    purpose="Present one local fixture interruption with explicit allow, defer, stop, and recover controls.",
                    task_ids=(interrupt_task, stop_task),
                    state_ids=(state_ids["empty"], state_ids["error"], state_ids["success"], state_ids["stopped"]),
                ),
            ],
            tasks=[
                WebTaskSpec(
                    task_id=start_task,
                    screen_id=focus_screen,
                    goal="Declare one concrete task and start a bounded 10-minute focus session.",
                    success_criteria="The session is visibly active and the next action is clear.",
                    user_decision_limit="One setup decision; no hidden defaults that delay urgent contact.",
                ),
                WebTaskSpec(
                    task_id=interrupt_task,
                    screen_id=interruption_screen,
                    goal="Make one explicit decision about a local non-urgent interruption.",
                    success_criteria="The user can allow it now, defer it, or stop without message content leaving the fixture.",
                    user_decision_limit="At most one decision per surfaced interruption.",
                ),
                WebTaskSpec(
                    task_id=finish_task,
                    screen_id=focus_screen,
                    goal="Return to the declared task, complete the bounded work unit, and see what was deferred.",
                    success_criteria="The task completion and deferred interruption are both visible; no outcome is claimed automatically.",
                    user_decision_limit="One completion decision; the user can still stop or recover.",
                ),
                WebTaskSpec(
                    task_id=stop_task,
                    screen_id=focus_screen,
                    goal="Stop the intervention and recover the session state.",
                    success_criteria="Stop and recovery are immediate, visible, and reversible.",
                    user_decision_limit="No confirmation wall before stop or recovery.",
                ),
            ],
            primary_flow_task_ids=[start_task, interrupt_task, finish_task],
            states=[
                WebStateSpec(state_id=state_ids["ready"], kind="ready", user_visible_behavior="Show the next available focus action and boundary.", recovery_action="Start or leave the session."),
                WebStateSpec(state_id=state_ids["loading"], kind="loading", user_visible_behavior="Show a deterministic local transition without implying network activity.", recovery_action="Wait briefly or stop the local transition."),
                WebStateSpec(state_id=state_ids["empty"], kind="empty", user_visible_behavior="Explain that no local interruption fixture is waiting.", recovery_action="Return to the focus session."),
                WebStateSpec(state_id=state_ids["error"], kind="error", user_visible_behavior="Explain the local failure without exposing sensitive content.", recovery_action="Retry locally or stop the intervention."),
                WebStateSpec(state_id=state_ids["success"], kind="success", user_visible_behavior="Confirm the chosen local action and current control boundary.", recovery_action="Continue or stop."),
                WebStateSpec(state_id=state_ids["paused"], kind="paused", user_visible_behavior="Show that the session is paused and no intervention is active.", recovery_action="Resume or stop."),
                WebStateSpec(state_id=state_ids["stopped"], kind="stopped", user_visible_behavior="Show that the intervention has ended and controls are restored.", recovery_action="Start a new session."),
            ],
            content_slots=[
                WebContentSlot(slot_id=f"{suggestion_id}-title", semantic_role="heading", description="Name the focus session without claiming a measured result.", source_kind="product_thesis", fallback_text="Focus session"),
                WebContentSlot(slot_id=f"{suggestion_id}-goal", semantic_role="instruction", description="Explain the declared task boundary in the user's own terms.", source_kind="outcome_contract", fallback_text="Choose a focus task and duration."),
                WebContentSlot(slot_id=f"{suggestion_id}-control", semantic_role="status", description="State that stop, recovery, and urgent contact controls remain available.", source_kind="outcome_contract", fallback_text="You can stop or recover this intervention at any time."),
                WebContentSlot(slot_id=f"{suggestion_id}-next", semantic_role="instruction", description="Tell the user the next action in the primary flow without claiming an outcome.", source_kind="outcome_contract", fallback_text="Next: complete the declared focus task."),
                WebContentSlot(slot_id=f"{suggestion_id}-error", semantic_role="error", description="Give a safe local recovery instruction without message content.", source_kind="local_fixture", fallback_text="Something went wrong locally. Retry or stop."),
            ],
            acceptance_checks=[
                WebAcceptanceCheck(check_id=f"{suggestion_id}-start-check", task_id=start_task, assertion="Start task reaches an active 10-minute session, exposes the next action, and makes the declared task visible without a network request."),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-interrupt-check", task_id=interrupt_task, assertion="Interruption task presents exactly one explicit allow/defer/stop decision and preserves local-only data boundary."),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-finish-check", task_id=finish_task, assertion="The primary flow returns to the declared task, makes completion visible, and exposes the deferred interruption without claiming a measured outcome."),
                WebAcceptanceCheck(check_id=f"{suggestion_id}-stop-check", task_id=stop_task, assertion="Stop and recovery are available from every active or paused state."),
            ],
            source_refs=[
                SourceReference(source_type="model_proposal", source_id=suggestion_id, revision_id=WEB_TEMPLATE_VERSION),
                SourceReference(source_type="human_decision", source_id=thesis.thesis_id, revision_id=thesis.revision_id),
            ],
        )

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Revise a confirmed B2 contract in response to one explicit report (B8).

        Only the anchor, category and feedback ID are used; the report text is
        never copied into the contract, so withdrawing the feedback still
        erases it everywhere.  Every baseline ID is preserved so anchors and
        revision diffs stay comparable; the revision adds one reviewable check.
        """

        screen = next(
            item for item in baseline_contract.screens if item.screen_id == feedback.anchor.screen_id
        )
        task_id = feedback.anchor.task_id or screen.task_ids[0]
        focus = {
            "bug": "no longer reproduces the reported defect",
            "confusing": "makes the next step unambiguous",
            "missing": "exposes the reported missing capability or explains its absence",
            "works": "keeps the confirmed behaviour unchanged",
        }[feedback.category or "works"]
        state_note = f" in state {feedback.anchor.state_id}" if feedback.anchor.state_id else ""
        check = WebAcceptanceCheck(
            check_id=f"{suggestion_id}-feedback-check",
            task_id=task_id,
            assertion=(
                f"Screen {screen.screen_id}{state_note} {focus} "
                f"(preview feedback {feedback.feedback_id}, {feedback.category}); human review required."
            ),
        )
        return WebProductGenerationContractProposal(
            product_thesis_revision_id=baseline_contract.product_thesis_revision_id,
            outcome_contract_revision_id=baseline_contract.outcome_contract_revision_id,
            app_title=baseline_contract.app_title,
            screens=list(baseline_contract.screens),
            tasks=list(baseline_contract.tasks),
            states=list(baseline_contract.states),
            content_slots=list(baseline_contract.content_slots),
            acceptance_checks=[*baseline_contract.acceptance_checks, check],
            source_refs=[
                *baseline_contract.source_refs,
                SourceReference(
                    source_type="preview_feedback",
                    source_id=feedback.feedback_id,
                    revision_id=feedback.revision_id,
                    locator="anchor+category only; text not copied",
                ),
                SourceReference(source_type="model_proposal", source_id=suggestion_id, revision_id="b8-v1"),
            ],
        )


class RealModelProductContractProvider:
    """C0 real model provider for Product Contract proposals (Intent/Problem/Outcome/Thesis).

    Uses DeepSeek via contract_model module. Follows C0 decisions:
    - PS-O017: Full confirmed upstream + user input sent; transcript local only
    - PS-O018: Max 2 calls per object; no monetary budget
    - PS-O019: No automatic retry; user must explicitly retry on failure
    """

    name = "deepseek"
    version = "c0-v1"

    def __init__(self) -> None:
        """Initialize with environment-configured DeepSeek model."""
        from psyteardown.product.contract_model import (
            ContractModelError,
            build_contract_model_from_env,
        )

        model = build_contract_model_from_env()
        if model is None:
            raise ContractModelError(
                "Real model provider requires PSYTEARDOWN_PRODUCT_CONTRACT_MODEL=deepseek and DEEPSEEK_API_KEY"
            )
        self._model = model
        # C0 stage 6 local evidence. This is intentionally an in-memory
        # diagnostic ledger; proposal jobs remain the persisted source of
        # truth and no prompt/response content is retained here.
        self.usage_records: list[dict[str, object]] = []

    def _generate(self, *, kind: str, system: str, prompt: str):
        started = time.monotonic()
        try:
            reply = self._model.generate(system=system, prompt=prompt)
        except Exception as exc:
            self.usage_records.append(
                {
                    "kind": kind,
                    "model": self._model.model,
                    "outcome": "failed",
                    "error_type": type(exc).__name__,
                    "duration_seconds": time.monotonic() - started,
                }
            )
            raise
        self.usage_records.append(
            {
                "kind": kind,
                "model": reply.model,
                "outcome": "accepted",
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "truncated": reply.truncated,
                "duration_seconds": time.monotonic() - started,
            }
        )
        return reply

    def propose_intent(
        self, raw_input: str, *, job_id: str
    ) -> ProductIntentProposal:
        """Generate ProductIntent proposal from raw user input."""
        from psyteardown.product.contract_model import (
            INTENT_SYSTEM,
            ContractModelError,
            build_intent_prompt,
            parse_intent_reply,
        )

        prompt = build_intent_prompt(raw_input)
        try:
            reply = self._generate(kind="product_intent", system=INTENT_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_intent_reply(reply.text, job_id=job_id)
        if isinstance(result, list):
            # Static gate rejection
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_problem(
        self, intent: ProductIntent, *, job_id: str
    ) -> ProblemModelProposal:
        """Generate ProblemModel proposal from confirmed ProductIntent."""
        from psyteardown.product.contract_model import (
            PROBLEM_SYSTEM,
            ContractModelError,
            build_problem_prompt,
            parse_problem_reply,
        )

        prompt = build_problem_prompt(intent)
        try:
            reply = self._generate(kind="problem_model", system=PROBLEM_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_problem_reply(reply.text, job_id=job_id, intent=intent)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_outcome_contract(
        self,
        intent: ProductIntent,
        problem: ProblemModel,
        *,
        job_id: str,
    ) -> OutcomeContractProposal:
        """Generate OutcomeContract proposal from confirmed Intent and ProblemModel."""
        from psyteardown.product.contract_model import (
            OUTCOME_SYSTEM,
            ContractModelError,
            build_outcome_prompt,
            parse_outcome_reply,
        )

        prompt = build_outcome_prompt(intent, problem)
        try:
            reply = self._generate(kind="outcome_contract", system=OUTCOME_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_outcome_reply(reply.text, job_id=job_id, intent=intent, problem=problem)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_theses(
        self,
        problem: ProblemModel,
        contract: OutcomeContract,
        *,
        job_id: str,
    ) -> tuple[ProductThesisProposal, ...]:
        """Generate 3 ProductThesis proposals from confirmed ProblemModel and OutcomeContract."""
        from psyteardown.product.contract_model import (
            THESIS_SYSTEM,
            ContractModelError,
            build_theses_prompt,
            parse_theses_reply,
        )

        prompt = build_theses_prompt(problem, contract)
        try:
            reply = self._generate(kind="product_theses", system=THESIS_SYSTEM, prompt=prompt)
        except ContractModelError as exc:
            raise RuntimeError(f"provider_failed: {exc}") from exc

        result = parse_theses_reply(reply.text, job_id=job_id, problem=problem, contract=contract)
        if isinstance(result, list):
            reasons = "; ".join(result)
            raise RuntimeError(f"static_gate_rejected: {reasons}")
        return result

    def propose_web_generation_contract(
        self,
        thesis: ProductThesis,
        contract: OutcomeContract,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Delegate to fake provider for now; real model Web generation is B7m's domain."""
        fake = DeterministicFakeProductContractProvider()
        return fake.propose_web_generation_contract(thesis, contract, suggestion_id=suggestion_id)

    def propose_web_generation_contract_from_feedback(
        self,
        baseline_contract: WebProductGenerationContract,
        feedback: PreviewFeedback,
        *,
        suggestion_id: str,
    ) -> WebProductGenerationContractProposal:
        """Delegate to fake provider for now; feedback iteration uses fake revision."""
        fake = DeterministicFakeProductContractProvider()
        return fake.propose_web_generation_contract_from_feedback(
            baseline_contract, feedback, suggestion_id=suggestion_id
        )


def build_provider_from_env(provider_name: str = "fake") -> ProductContractProposalProvider:
    """Build provider from environment or explicit name.

    Args:
        provider_name: "fake" (default) or "real"

    Returns:
        DeterministicFakeProductContractProvider or RealModelProductContractProvider

    Raises:
        ValueError: if provider_name is invalid or real provider cannot be initialized
    """
    if provider_name == "fake":
        return DeterministicFakeProductContractProvider()
    elif provider_name == "real":
        return RealModelProductContractProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}; expected 'fake' or 'real'")
