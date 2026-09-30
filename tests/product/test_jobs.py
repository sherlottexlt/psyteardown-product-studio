from collections import defaultdict
from datetime import datetime, timezone

from psyteardown.product import (
    ConfirmOutcomeContract,
    ConfirmProblemModel,
    ConfirmProductIntent,
    CreateProductProject,
    DeterministicFakeProductContractProvider,
    InMemoryProductJobRepository,
    InMemoryProductRepository,
    ProductApplicationService,
    ProductIntentProposal,
    ProductProposalJobService,
    OutcomeContractProposal,
    SQLiteProductRepository,
    SourceReference,
    SubmitProductIntentProposal,
    SubmitOutcomeContractProposal,
    TransitionProductThesis,
)


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class SequenceIds:
    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}-{self.counts[prefix]}"


class FailingProvider(DeterministicFakeProductContractProvider):
    def propose_problem(self, intent, *, job_id):
        raise RuntimeError("private-provider-detail-must-not-leak")


def build_services(provider=None):
    ids = SequenceIds()
    repository = InMemoryProductRepository()
    application = ProductApplicationService(
        repository, clock=lambda: NOW, id_factory=ids
    )
    jobs = InMemoryProductJobRepository()
    job_service = ProductProposalJobService(
        application,
        jobs,
        provider=provider,
        clock=lambda: NOW,
        id_factory=ids,
    )
    return application, jobs, job_service


def confirmed_intent(application: ProductApplicationService):
    project = application.create_project(
        CreateProductProject(
            project_id="project-1",
            name="Focus boundary",
            actor="user-li",
            reason="start",
        )
    )
    proposal = application.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id="intent-1",
            proposal=ProductIntentProposal(
                desired_change="Protect focused work while preserving urgent contact",
                affected_people=["independent knowledge workers"],
                current_situation="Messages arrive through several tools",
                explicit_non_goals=["monitor personal productivity"],
                known_constraints=["local-first"],
                resource_preferences=["first prototype within one day"],
                source_refs=[
                    SourceReference(
                        source_type="user_input", source_id="message-1"
                    )
                ],
            ),
            actor="studio",
            reason="capture input",
        )
    )
    intent = application.confirm_product_intent(
        ConfirmProductIntent(
            project_id=project.project_id,
            intent_id=proposal.intent_id,
            expected_revision=1,
            actor="user-li",
            reason="intent is correct",
        )
    )
    return project, intent


def test_raw_input_job_creates_only_a_correctable_intent_proposal():
    application, _, service = build_services()
    project = application.create_project(
        CreateProductProject(
            project_id="project-raw",
            name="Incomplete idea",
            actor="user-li",
            reason="start from one sentence",
        )
    )
    raw_input = "I want fewer interruptions while I work"
    queued = service.create_job(
        project_id=project.project_id,
        kind="product_intent",
        raw_input=raw_input,
        actor="user-li",
        reason="structure incomplete input",
    )

    assert queued.status == "queued"
    assert queued.raw_input == raw_input
    assert application.get_project_view(project.project_id).product_intent is None
    completed = service.run_job(project.project_id, queued.job_id, actor="worker")
    intent = application.get_project_view(project.project_id).product_intent

    assert completed.status == "succeeded", completed.error_summary
    assert intent.status == "proposed"
    assert intent.desired_change == raw_input
    assert "human correction required" in intent.affected_people[0]
    assert intent.source_refs[0].locator == "product_proposal_job.raw_input"
    assert intent.source_refs[1].source_type == "model_proposal"


def test_problem_job_is_persisted_before_provider_runs_and_is_idempotent():
    application, job_repository, service = build_services()
    project, _ = confirmed_intent(application)

    queued = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate problem proposal",
    )
    duplicate = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="repeat click",
    )

    assert queued.status == "queued"
    assert queued.attempt == 0
    assert application.get_project_view(project.project_id).problem_model is None
    assert duplicate.job_id == queued.job_id
    assert job_repository.get_job(queued.job_id) == queued

    completed = service.run_job(project.project_id, queued.job_id, actor="worker")
    problem = application.get_project_view(project.project_id).problem_model
    assert completed.status == "succeeded", completed.error_summary
    assert completed.attempt == 1
    assert completed.result_revision_id == problem.revision_id
    assert problem.status == "proposed"
    assert problem.meta.created_by == "provider:deterministic_fake"
    assert problem.facts[0].source_refs[0].source_type == "user_input"
    assert len(problem.competing_explanations) == 2
    assert len(problem.unknowns) == 2


def test_changed_input_marks_queued_job_stale_without_committing_output():
    application, _, service = build_services()
    project, intent = confirmed_intent(application)
    queued = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate problem proposal",
    )
    application.submit_product_intent(
        SubmitProductIntentProposal(
            project_id=project.project_id,
            intent_id=intent.intent_id,
            expected_revision=intent.meta.revision,
            proposal=ProductIntentProposal(
                desired_change=intent.desired_change,
                affected_people=list(intent.affected_people),
                current_situation="The context changed before the worker ran",
                source_refs=list(intent.source_refs),
            ),
            actor="user-li",
            reason="correct context",
        )
    )

    stale = service.run_job(project.project_id, queued.job_id, actor="worker")

    assert stale.status == "stale_input"
    assert stale.attempt == 0
    assert application.get_project_view(project.project_id).problem_model is None


def test_provider_failure_is_safe_and_retryable():
    application, _, service = build_services(provider=FailingProvider())
    project, _ = confirmed_intent(application)
    queued = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate",
    )

    failed = service.run_job(project.project_id, queued.job_id, actor="worker")

    assert failed.status == "failed"
    assert failed.error_code == "provider_failed"
    assert "private-provider-detail" not in failed.error_summary
    assert application.get_project_view(project.project_id).problem_model is None
    retry = service.retry_job(project.project_id, queued.job_id, actor="user-li")
    assert retry.status == "queued"
    assert retry.error_code is None


def test_outcome_job_requires_confirmed_problem_and_keeps_human_review_gate():
    application, _, service = build_services()
    project, _ = confirmed_intent(application)
    problem_job = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate problem",
    )
    service.run_job(project.project_id, problem_job.job_id, actor="worker")
    problem = application.get_project_view(project.project_id).problem_model
    confirmed = application.confirm_problem_model(
        ConfirmProblemModel(
            project_id=project.project_id,
            problem_model_id=problem.problem_model_id,
            expected_revision=problem.meta.revision,
            actor="user-li",
            reason="problem framing is acceptable",
        )
    )

    outcome_job = service.create_job(
        project_id=project.project_id,
        kind="outcome_contract",
        actor="user-li",
        reason="generate outcome contract",
    )
    completed = service.run_job(
        project.project_id, outcome_job.job_id, actor="worker"
    )
    contract = application.get_project_view(project.project_id).outcome_contract

    assert completed.status == "succeeded"
    assert contract.problem_model_revision_id == confirmed.revision_id
    assert contract.status == "proposed"
    assert contract.prohibited_outcomes_reviewed is False
    assert contract.minimum_delivery_maturity.value == "runnable_prototype"
    assert contract.success_indicators[0].required_evidence == "real_user_observation"
    assert contract.required_real_world_evidence


def _confirmed_outcome_contract(
    application: ProductApplicationService, service: ProductProposalJobService
):
    project, _ = confirmed_intent(application)
    problem_job = service.create_job(
        project_id=project.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate problem",
    )
    service.run_job(project.project_id, problem_job.job_id, actor="worker")
    problem = application.get_project_view(project.project_id).problem_model
    confirmed_problem = application.confirm_problem_model(
        ConfirmProblemModel(
            project_id=project.project_id,
            problem_model_id=problem.problem_model_id,
            expected_revision=problem.meta.revision,
            actor="user-li",
            reason="problem framing is acceptable",
        )
    )
    outcome_job = service.create_job(
        project_id=project.project_id,
        kind="outcome_contract",
        actor="user-li",
        reason="generate outcome",
    )
    service.run_job(project.project_id, outcome_job.job_id, actor="worker")
    contract = application.get_project_view(project.project_id).outcome_contract
    # The deterministic contract is intentionally proposed. Correct the
    # human-review field before confirming it, preserving a new revision.
    corrected = application.submit_outcome_contract(
        SubmitOutcomeContractProposal(
            project_id=project.project_id,
            outcome_contract_id=contract.outcome_contract_id,
            expected_revision=contract.meta.revision,
            actor="user-li",
            reason="review prohibited outcomes before confirmation",
            proposal=OutcomeContractProposal(
                intent_revision_id=contract.intent_revision_id,
                problem_model_revision_id=contract.problem_model_revision_id,
                target_segments=list(contract.target_segments),
                applicable_contexts=list(contract.applicable_contexts),
                target_outcomes=list(contract.target_outcomes),
                success_indicators=list(contract.success_indicators),
                prohibited_outcomes=list(contract.prohibited_outcomes),
                prohibited_outcomes_reviewed=True,
                resource_boundary=contract.resource_boundary,
                stop_conditions=list(contract.stop_conditions),
                minimum_delivery_maturity=contract.minimum_delivery_maturity,
                required_real_world_evidence=list(contract.required_real_world_evidence),
            ),
        )
    )
    confirmed_contract = application.confirm_outcome_contract(
        ConfirmOutcomeContract(
            project_id=project.project_id,
            outcome_contract_id=contract.outcome_contract_id,
            expected_revision=corrected.meta.revision,
            actor="user-li",
            reason="outcome, harm, resources, and evidence reviewed",
        )
    )
    return project, confirmed_problem, confirmed_contract


def test_product_theses_job_generates_three_differentiated_proposals_and_is_idempotent():
    application, _, service = build_services()
    project, problem, contract = _confirmed_outcome_contract(application, service)

    queued = service.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="search differentiated product paths",
    )
    duplicate = service.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="repeat search click",
    )
    assert duplicate.job_id == queued.job_id
    assert len(queued.result_object_ids) == 3
    assert application.get_project_view(project.project_id).product_theses == ()

    completed = service.run_job(project.project_id, queued.job_id, actor="worker")
    view = application.get_project_view(project.project_id)
    assert completed.status == "succeeded"
    assert completed.result_revision_id == completed.result_revision_ids[0]
    assert len(completed.result_revision_ids) == 3
    assert len(view.product_theses) == 3
    assert len({thesis.name for thesis in view.product_theses}) == 3
    assert len({thesis.differentiation for thesis in view.product_theses}) == 3
    assert all(thesis.status == "proposed" for thesis in view.product_theses)
    assert all(
        thesis.problem_model_revision_id == problem.revision_id
        and thesis.outcome_contract_revision_id == contract.revision_id
        for thesis in view.product_theses
    )

    # A worker retry after all target writes have landed reconciles the same
    # three revisions rather than creating a second candidate set.
    assert service.run_job(project.project_id, queued.job_id, actor="worker") == completed
    assert len(application.get_project_view(project.project_id).product_theses) == 3


def test_product_theses_job_becomes_stale_when_pinned_contract_changes():
    application, _, service = build_services()
    project, _, contract = _confirmed_outcome_contract(application, service)
    queued = service.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="search paths",
    )
    # A confirmed upstream revision can be superseded without making the old
    # pinned job eligible to commit.
    application.submit_outcome_contract(
        SubmitOutcomeContractProposal(
            project_id=project.project_id,
            outcome_contract_id=contract.outcome_contract_id,
            expected_revision=contract.meta.revision,
            actor="user-li",
            reason="correct the outcome boundary",
            proposal=OutcomeContractProposal(
                intent_revision_id=contract.intent_revision_id,
                problem_model_revision_id=contract.problem_model_revision_id,
                target_segments=list(contract.target_segments),
                applicable_contexts=list(contract.applicable_contexts),
                target_outcomes=list(contract.target_outcomes),
                success_indicators=list(contract.success_indicators),
                prohibited_outcomes=list(contract.prohibited_outcomes),
                prohibited_outcomes_reviewed=contract.prohibited_outcomes_reviewed,
                resource_boundary=contract.resource_boundary,
                stop_conditions=list(contract.stop_conditions),
                minimum_delivery_maturity=contract.minimum_delivery_maturity,
                required_real_world_evidence=list(contract.required_real_world_evidence),
            ),
        )
    )
    stale = service.run_job(project.project_id, queued.job_id, actor="worker")
    assert stale.status == "stale_input"
    assert application.get_project_view(project.project_id).product_theses == ()


def test_web_generation_contract_job_uses_only_the_b2_template_and_local_boundary():
    application, _, service = build_services()
    project, _, contract = _confirmed_outcome_contract(application, service)
    thesis_job = service.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="search paths",
    )
    service.run_job(project.project_id, thesis_job.job_id, actor="worker")
    thesis = application.get_project_view(project.project_id).product_theses[0]
    exploring = application.transition_product_thesis(
        TransitionProductThesis(
            project_id=project.project_id,
            thesis_id=thesis.thesis_id,
            expected_revision=thesis.meta.revision,
            to_status="exploring",
            actor="user-li",
            actor_type="human",
            reason="authorize the lowest-cost Web exploration",
        )
    )
    web_job = service.create_job(
        project_id=project.project_id,
        kind="web_generation_contract",
        actor="user-li",
        reason="describe the first Web realization",
    )
    completed = service.run_job(project.project_id, web_job.job_id, actor="worker")
    view = application.get_project_view(project.project_id)
    generation = view.web_generation_contract

    assert completed.status == "succeeded", completed.error_summary
    assert generation is not None
    assert generation.status == "proposed"
    assert generation.template_id == "react_typescript_vite_spa"
    assert generation.template_version == "b2-v1"
    assert generation.network_policy == "none"
    assert generation.data_policy == "local_fixture_only"
    assert generation.product_thesis_revision_id == exploring.revision_id
    assert {item.kind for item in generation.states} >= {
        "ready", "loading", "empty", "error", "success"
    }
    assert generation.runtime_dependencies == ("react", "react-dom")
    assert "react-router" not in generation.development_dependencies
    assert all(item.source_kind != "research" for item in generation.content_slots)


def test_web_generation_reproposal_reuses_singleton_and_advances_revision():
    application, _, service = build_services()
    project, _, _ = _confirmed_outcome_contract(application, service)
    thesis_job = service.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="search paths",
    )
    service.run_job(project.project_id, thesis_job.job_id, actor="worker")
    thesis = application.get_project_view(project.project_id).product_theses[0]
    application.transition_product_thesis(
        TransitionProductThesis(
            project_id=project.project_id,
            thesis_id=thesis.thesis_id,
            expected_revision=thesis.meta.revision,
            to_status="selected",
            actor="user-li",
            actor_type="human",
            reason="select comparison board",
        )
    )
    first = service.create_job(
        project_id=project.project_id,
        kind="web_generation_contract",
        actor="user-li",
        reason="first proposal",
    )
    assert service.run_job(project.project_id, first.job_id, actor="worker").status == "succeeded"
    current = application.get_project_view(project.project_id).web_generation_contract
    assert current is not None and current.meta.revision == 1

    second = service.create_job(
        project_id=project.project_id,
        kind="web_generation_contract",
        actor="user-li",
        reason="explicitly refresh proposal",
    )
    assert second.job_id != first.job_id
    assert second.result_object_id == current.web_generation_contract_id
    assert second.result_expected_revision == current.meta.revision
    assert service.run_job(project.project_id, second.job_id, actor="worker").status == "succeeded"
    refreshed = application.get_project_view(project.project_id).web_generation_contract
    assert refreshed is not None
    assert refreshed.web_generation_contract_id == current.web_generation_contract_id
    assert refreshed.meta.revision == 2
    assert refreshed.status == "proposed"


def test_failed_sqlite_job_recovers_after_restart_and_can_be_retried(tmp_path):
    database = tmp_path / "product.sqlite3"
    ids = SequenceIds()
    first_repository = SQLiteProductRepository(database)
    first_application = ProductApplicationService(
        first_repository, clock=lambda: NOW, id_factory=ids
    )
    _, intent = confirmed_intent(first_application)
    first_jobs = ProductProposalJobService(
        first_application,
        first_repository,
        provider=FailingProvider(),
        clock=lambda: NOW,
        id_factory=ids,
    )
    queued = first_jobs.create_job(
        project_id=intent.project_id,
        kind="problem_model",
        actor="user-li",
        reason="generate",
    )
    failed = first_jobs.run_job(intent.project_id, queued.job_id, actor="worker")
    assert failed.status == "failed"
    first_repository.close()

    second_repository = SQLiteProductRepository(database)
    try:
        second_application = ProductApplicationService(
            second_repository, clock=lambda: NOW, id_factory=ids
        )
        second_jobs = ProductProposalJobService(
            second_application,
            second_repository,
            clock=lambda: NOW,
            id_factory=ids,
        )
        recovered = second_jobs.get_job(intent.project_id, queued.job_id)
        assert recovered.status == "failed"
        retry = second_jobs.retry_job(
            intent.project_id, queued.job_id, actor="user-li"
        )
        assert retry.status == "queued"
        completed = second_jobs.run_job(
            intent.project_id, queued.job_id, actor="worker"
        )
        assert completed.status == "succeeded"
        assert second_application.get_project_view(intent.project_id).problem_model
    finally:
        second_repository.close()


def test_feedback_iteration_requires_a_feedback_reader_and_web_kind():
    import pytest
    from psyteardown.experience.models import DomainStateError

    application, _, service = build_services()
    project, _, _ = _confirmed_outcome_contract(application, service)
    with pytest.raises(DomainStateError, match="only accepted for web_generation_contract"):
        service.create_job(
            project_id=project.project_id,
            kind="product_theses",
            actor="user-li",
            reason="search",
            feedback_id="preview-feedback-1",
        )
    with pytest.raises(DomainStateError, match="not available to proposal jobs"):
        service.create_job(
            project_id=project.project_id,
            kind="web_generation_contract",
            actor="user-li",
            reason="iterate",
            feedback_id="preview-feedback-1",
        )
