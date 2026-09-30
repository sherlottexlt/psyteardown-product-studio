from collections import defaultdict
from datetime import datetime, timezone

import pytest

from psyteardown.experience.models import (
    AuditEvent,
    DomainEvent,
    DomainStateError,
    RevisionMeta,
)
from psyteardown.product import (
    ChangeProductProjectStatus,
    CompetingExplanation,
    ConfirmOutcomeContract,
    ConfirmProblemModel,
    ConfirmProductIntent,
    CreateProductProject,
    DeliveryEstimate,
    FalsifiablePrediction,
    InMemoryProductRepository,
    MechanismHypothesis,
    OutcomeContractProposal,
    ProblemFact,
    ProblemModelProposal,
    ProductApplicationService,
    ProductIntent,
    ProductIntentProposal,
    ProductRepositoryError,
    ProductThesisProposal,
    ResourceBoundary,
    SQLiteProductRepository,
    SourceReference,
    StopCondition,
    SubmitOutcomeContractProposal,
    SubmitProblemModelProposal,
    SubmitProductIntentProposal,
    SubmitProductThesisProposal,
    SuccessIndicator,
    TargetOutcome,
    TransitionProductThesis,
    ValidationStep,
)


NOW = datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc)


class SequenceIds:
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self._counts[prefix] += 1
        return f"{prefix}-{self._counts[prefix]}"


@pytest.fixture(params=["memory", "sqlite"])
def product_repository(request, tmp_path):
    if request.param == "memory":
        yield InMemoryProductRepository()
        return
    repository = SQLiteProductRepository(tmp_path / "product.sqlite3")
    try:
        yield repository
    finally:
        repository.close()


@pytest.fixture
def service(product_repository):
    return ProductApplicationService(
        product_repository,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
    )


def source() -> SourceReference:
    return SourceReference(source_type="user_input", source_id="message-1")


def intent_proposal(*, extra_constraint: str | None = None) -> ProductIntentProposal:
    constraints = ["local-first"]
    if extra_constraint:
        constraints.append(extra_constraint)
    return ProductIntentProposal(
        desired_change="Protect focused work without surveilling the user",
        affected_people=["independent knowledge workers"],
        current_situation="Frequent context switching during desktop work",
        explicit_non_goals=["score personal productivity"],
        known_constraints=constraints,
        source_refs=[source()],
    )


def problem_proposal(intent_revision_id: str) -> ProblemModelProposal:
    fact = ProblemFact(
        fact_id="fact-1",
        statement="The user reports unplanned context switches",
        source_refs=(source(),),
    )
    return ProblemModelProposal(
        intent_revision_id=intent_revision_id,
        facts=[fact],
        competing_explanations=[
            CompetingExplanation(
                explanation_id="explanation-1",
                statement="Incoming notifications drive the switches",
                supporting_fact_ids=(fact.fact_id,),
                cheapest_falsification="Observe a session with notifications muted",
            ),
            CompetingExplanation(
                explanation_id="explanation-2",
                statement="Ambiguous tasks drive voluntary switching",
                supporting_fact_ids=(fact.fact_id,),
                cheapest_falsification="Observe a session with a precommitted task list",
            ),
        ],
    )


def contract_proposal(
    intent_revision_id: str, problem_revision_id: str
) -> OutcomeContractProposal:
    return OutcomeContractProposal(
        intent_revision_id=intent_revision_id,
        problem_model_revision_id=problem_revision_id,
        target_segments=["independent knowledge workers"],
        applicable_contexts=["self-directed desktop work"],
        target_outcomes=[
            TargetOutcome(
                outcome_id="outcome-1",
                description="Complete chosen focus tasks with fewer involuntary switches",
                indicator_ids=("indicator-1",),
            )
        ],
        success_indicators=[
            SuccessIndicator(
                indicator_id="indicator-1",
                operational_definition="Unplanned task switches in a declared focus session",
                observation_method="Consented task-session review",
                desired_direction="decrease",
                threshold_or_target="below the user's unaided baseline",
                required_evidence="real_user_observation",
            )
        ],
        prohibited_outcomes_reviewed=True,
        resource_boundary=ResourceBoundary(
            time_budget="first prototype within one day",
            data_boundary="no hidden activity collection",
        ),
        stop_conditions=[
            StopCondition(
                condition_id="stop-1",
                condition="Perceived pressure increases",
                action="reframe",
            )
        ],
        required_real_world_evidence=["one consented real task session"],
    )


def thesis_proposal(
    problem_revision_id: str, contract_revision_id: str
) -> ProductThesisProposal:
    return ProductThesisProposal(
        problem_model_revision_id=problem_revision_id,
        outcome_contract_revision_id=contract_revision_id,
        name="Intentional interruption gate",
        product_promise="Delay nonessential interruptions until a chosen boundary",
        differentiation="Changes interruption timing rather than scoring the user",
        realization_modes=["software"],
        mechanism_hypotheses=[
            MechanismHypothesis(
                mechanism_id="mechanism-1",
                condition="A bounded focus task has been declared",
                proposed_intervention="Queue nonessential interruptions",
                expected_change="Fewer involuntary switches",
                uncertainty="The queue could increase anxiety",
            )
        ],
        falsifiable_predictions=[
            FalsifiablePrediction(
                prediction_id="prediction-1",
                prediction="Unplanned switches decrease",
                failure_observation="Switches do not decrease or pressure rises",
                cheapest_test="One reversible local prototype session",
            )
        ],
        validation_strategy=[
            ValidationStep(
                validation_step_id="validation-1",
                question="Can queued items be recovered without losing trust?",
                method="Scripted browser task followed by a consented session",
                evidence_level="real_user_observation",
                pass_condition="No missed critical item and acceptable perceived control",
                estimated_cost="one prototype and one session",
            )
        ],
        key_unknowns=["Effect of delayed items on anxiety"],
        key_risks=["Suppressing an urgent item"],
        delivery_estimate=DeliveryEstimate(
            initial_delivery_cost="one web prototype",
            operating_cost="local processing",
            maintenance_burden="browser integration updates",
        ),
    )


def create_project(service: ProductApplicationService):
    return service.create_project(
        CreateProductProject(
            project_id="project-1",
            name="Focus boundary experiment",
            actor="user-li",
            reason="start project",
        )
    )


def bootstrap_confirmed_contract(service: ProductApplicationService):
    project = create_project(service)
    intent_draft = service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id="intent-1",
            proposal=intent_proposal(),
            actor="studio",
            reason="structure user input",
        )
    )
    intent = service.confirm_product_intent(
        ConfirmProductIntent(
            project_id=project.project_id,
            intent_id=intent_draft.intent_id,
            expected_revision=1,
            actor="user-li",
            reason="intent boundary is correct",
        )
    )
    problem_draft = service.submit_problem_model(
        SubmitProblemModelProposal(
            project_id=project.project_id,
            problem_model_id="problem-1",
            proposal=problem_proposal(intent.revision_id),
            actor="studio",
            reason="compare problem explanations",
        )
    )
    problem = service.confirm_problem_model(
        ConfirmProblemModel(
            project_id=project.project_id,
            problem_model_id=problem_draft.problem_model_id,
            expected_revision=1,
            actor="researcher-li",
            reason="sources and competing explanations reviewed",
        )
    )
    contract_draft = service.submit_outcome_contract(
        SubmitOutcomeContractProposal(
            project_id=project.project_id,
            outcome_contract_id="contract-1",
            proposal=contract_proposal(intent.revision_id, problem.revision_id),
            actor="studio",
            reason="propose observable outcome boundary",
        )
    )
    contract = service.confirm_outcome_contract(
        ConfirmOutcomeContract(
            project_id=project.project_id,
            outcome_contract_id=contract_draft.outcome_contract_id,
            expected_revision=1,
            actor="user-li",
            reason="outcome and stop conditions approved",
        )
    )
    return project, intent, problem, contract


def test_same_application_flow_builds_project_view_for_both_adapters(service):
    project, intent, problem, contract = bootstrap_confirmed_contract(service)
    thesis = service.submit_product_thesis(
        SubmitProductThesisProposal(
            project_id=project.project_id,
            thesis_id="thesis-1",
            proposal=thesis_proposal(problem.revision_id, contract.revision_id),
            actor="studio",
            reason="propose a falsifiable product path",
        )
    )
    selected = service.transition_product_thesis(
        TransitionProductThesis(
            project_id=project.project_id,
            thesis_id=thesis.thesis_id,
            expected_revision=1,
            to_status="selected",
            actor="user-li",
            actor_type="human",
            reason="select for low-cost prototyping",
        )
    )

    view = service.get_project_view(project.project_id)
    assert view.project == project
    assert view.product_intent == intent
    assert view.problem_model == problem
    assert view.outcome_contract == contract
    assert view.product_theses == (selected,)
    assert len(service.repository.domain_events) == 9
    assert len(service.repository.audit_events) == 9


def test_downstream_use_requires_confirmed_upstream(service):
    project = create_project(service)
    draft = service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id="intent-1",
            proposal=intent_proposal(),
            actor="studio",
            reason="draft",
        )
    )
    with pytest.raises(DomainStateError, match="human-confirmed"):
        service.submit_problem_model(
            SubmitProblemModelProposal(
                project_id=project.project_id,
                proposal=problem_proposal(draft.revision_id),
                actor="studio",
                reason="must not bypass confirmation",
            )
        )
    assert len(service.repository.domain_events) == 2


def test_revision_conflict_writes_no_revision_event_or_audit(service):
    project = create_project(service)
    draft = service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id="intent-1",
            proposal=intent_proposal(),
            actor="studio",
            reason="draft",
        )
    )
    before_events = tuple(service.repository.domain_events)
    before_audits = tuple(service.repository.audit_events)
    with pytest.raises(ProductRepositoryError, match="revision conflict"):
        service.confirm_product_intent(
            ConfirmProductIntent(
                project_id=project.project_id,
                intent_id=draft.intent_id,
                expected_revision=9,
                actor="user-li",
                reason="stale client write",
            )
        )

    assert service.repository.list_revisions("product_intent", draft.intent_id) == [
        draft
    ]
    assert tuple(service.repository.domain_events) == before_events
    assert tuple(service.repository.audit_events) == before_audits


def test_intent_amendment_atomically_records_direct_impacts(service):
    project, intent, problem, contract = bootstrap_confirmed_contract(service)
    thesis = service.submit_product_thesis(
        SubmitProductThesisProposal(
            project_id=project.project_id,
            thesis_id="thesis-1",
            proposal=thesis_proposal(problem.revision_id, contract.revision_id),
            actor="studio",
            reason="propose path",
        )
    )
    amended = service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id=intent.intent_id,
            expected_revision=2,
            proposal=intent_proposal(extra_constraint="no cloud account required"),
            actor="user-li",
            reason="tighten delivery boundary",
        )
    )

    view = service.get_project_view(project.project_id)
    assert amended.status == "proposed"
    assert amended.meta.parent_revision_id == intent.revision_id
    assert [(impact.dependent_type, impact.impact) for impact in view.recorded_impacts] == [
        ("problem_model", "review_required"),
        ("outcome_contract", "stale"),
    ]
    assert view.problem_model == problem
    assert view.outcome_contract == contract
    assert view.product_theses == (thesis,)
    assert [event.event_type for event in service.repository.domain_events[-3:]] == [
        "product_intent_proposed",
        "product_dependency_impact_recorded",
        "product_dependency_impact_recorded",
    ]


def test_paused_project_blocks_child_writes_until_resumed(service):
    project = create_project(service)
    paused = service.change_project_status(
        ChangeProductProjectStatus(
            project_id=project.project_id,
            expected_revision=1,
            to_status="paused",
            actor="user-li",
            reason="pause spending",
        )
    )
    with pytest.raises(DomainStateError, match="must be active"):
        service.submit_product_intent(
            SubmitProductIntentProposal(
                project_id=project.project_id,
                proposal=intent_proposal(),
                actor="studio",
                reason="blocked while paused",
            )
        )
    resumed = service.change_project_status(
        ChangeProductProjectStatus(
            project_id=project.project_id,
            expected_revision=paused.meta.revision,
            to_status="active",
            actor="user-li",
            reason="resume project",
        )
    )
    assert resumed.status == "active"


def test_archived_project_can_be_restored(service):
    project = create_project(service)
    archived = service.change_project_status(
        ChangeProductProjectStatus(
            project_id=project.project_id,
            expected_revision=project.meta.revision,
            to_status="archived",
            actor="user-li",
            reason="hide abandoned project",
        )
    )
    restored = service.change_project_status(
        ChangeProductProjectStatus(
            project_id=project.project_id,
            expected_revision=archived.meta.revision,
            to_status="active",
            actor="user-li",
            reason="restore project",
        )
    )
    assert archived.status == "archived"
    assert restored.status == "active"


def test_repository_command_is_atomic_when_event_insert_fails(product_repository):
    intent = ProductIntent(
        intent_id="atomic-intent",
        revision_id="atomic-intent.r1",
        meta=RevisionMeta(
            revision=1, created_at=NOW, created_by="test", reason="atomicity"
        ),
        project_id="atomic-project",
        desired_change="Preserve atomic writes",
        affected_people=("developers",),
        source_refs=(source(),),
    )
    duplicate_event = DomainEvent(
        event_id="duplicate-event",
        event_type="product_intent_proposed",
        aggregate_id=intent.intent_id,
        aggregate_revision_id=intent.revision_id,
        occurred_at=NOW,
    )
    audit = AuditEvent(
        audit_id="audit-1",
        action="product_intent_proposed",
        target_id=intent.intent_id,
        target_revision_id=intent.revision_id,
        actor="test",
        reason="atomicity",
        occurred_at=NOW,
    )
    with pytest.raises(ProductRepositoryError):
        product_repository.save_command(
            "product_intent",
            intent.intent_id,
            intent.revision_id,
            intent,
            project_id=intent.project_id,
            expected_revision=None,
            domain_events=(duplicate_event, duplicate_event),
            audit_events=(audit,),
        )

    assert product_repository.get_current("product_intent", intent.intent_id) is None
    assert product_repository.domain_events == []
    assert product_repository.audit_events == []


def test_sqlite_restart_recovers_project_revisions_events_and_impacts(tmp_path):
    path = tmp_path / "restart.sqlite3"
    first_repo = SQLiteProductRepository(path)
    first_service = ProductApplicationService(
        first_repo, clock=lambda: NOW, id_factory=SequenceIds()
    )
    project, intent, problem, contract = bootstrap_confirmed_contract(first_service)
    first_service.submit_product_thesis(
        SubmitProductThesisProposal(
            project_id=project.project_id,
            thesis_id="thesis-1",
            proposal=thesis_proposal(problem.revision_id, contract.revision_id),
            actor="studio",
            reason="propose path",
        )
    )
    first_service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id=intent.intent_id,
            expected_revision=2,
            proposal=intent_proposal(extra_constraint="offline-capable"),
            actor="user-li",
            reason="add offline boundary",
        )
    )
    event_types = [event.event_type for event in first_repo.domain_events]
    first_repo.close()

    second_repo = SQLiteProductRepository(path)
    try:
        second_service = ProductApplicationService(
            second_repo, clock=lambda: NOW, id_factory=SequenceIds()
        )
        view = second_service.get_project_view(project.project_id)
        assert view.product_intent.meta.revision == 3
        assert view.problem_model == problem
        assert view.outcome_contract == contract
        assert len(view.product_theses) == 1
        assert len(view.recorded_impacts) == 2
        assert [event.event_type for event in second_repo.domain_events] == event_types
        assert len(second_repo.audit_events) == 9
        tables = {
            row[0]
            for row in second_repo._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "product_revisions",
            "product_current",
            "product_domain_events",
            "product_audit_events",
            "product_revision_impacts",
        } <= tables
    finally:
        second_repo.close()


def test_ids_and_clock_are_application_injected():
    ids = SequenceIds()
    service = ProductApplicationService(
        InMemoryProductRepository(), clock=lambda: NOW, id_factory=ids
    )
    project = service.create_project(
        CreateProductProject(
            name="Generated IDs",
            actor="user-li",
            reason="verify injection",
        )
    )
    intent = service.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            proposal=intent_proposal(),
            actor="studio",
            reason="verify injection",
        )
    )
    assert project.project_id == "project-1"
    assert intent.intent_id == "intent-1"
    assert project.meta.created_at == NOW
    assert intent.meta.created_at == NOW
