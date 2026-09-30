from collections import defaultdict
from datetime import datetime, timezone

import pytest

from psyteardown.product import (
    ConfirmWebProductGenerationContract,
    GenerationBudget,
    InMemoryProductGenerationJobRepository,
    ProductApplicationService,
    ProductGenerationJobService,
    ProductProposalJobService,
    SQLiteProductRepository,
    SubmitWebProductGenerationContractProposal,
    TransitionProductThesis,
)
from .test_jobs import _confirmed_outcome_contract, build_services


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


class SequenceIds:
    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}-{self.counts[prefix]}"


class BrokenAriaLiveGenerationService(ProductGenerationJobService):
    """Test-only broken workspace for exercising the bounded repair planner."""

    def _render_files(self, contract):
        files = super()._render_files(contract)
        files["src/App.tsx"] = files["src/App.tsx"].replace(' aria-live="polite"', "", 1)
        return files


def confirmed_generation(application, proposal_jobs):
    project, _, _ = _confirmed_outcome_contract(application, proposal_jobs)
    thesis_job = proposal_jobs.create_job(
        project_id=project.project_id,
        kind="product_theses",
        actor="user-li",
        reason="search paths",
    )
    proposal_jobs.run_job(project.project_id, thesis_job.job_id, actor="worker")
    thesis = application.get_project_view(project.project_id).product_theses[0]
    application.transition_product_thesis(
        TransitionProductThesis(
            project_id=project.project_id,
            thesis_id=thesis.thesis_id,
            expected_revision=thesis.meta.revision,
            to_status="exploring",
            actor="user-li",
            actor_type="human",
            reason="authorize exploration",
        )
    )
    web_job = proposal_jobs.create_job(
        project_id=project.project_id,
        kind="web_generation_contract",
        actor="user-li",
        reason="describe Web realization",
    )
    proposal_jobs.run_job(project.project_id, web_job.job_id, actor="worker")
    draft = application.get_project_view(project.project_id).web_generation_contract
    assert draft is not None
    return project, application.confirm_web_generation_contract(
        ConfirmWebProductGenerationContract(
            project_id=project.project_id,
            web_generation_contract_id=draft.web_generation_contract_id,
            expected_revision=draft.meta.revision,
            actor="user-li",
            reason="confirm generation boundary",
        )
    )


def build_generation_services(root, *, broken_template=False):
    application, _, proposal_jobs = build_services()
    project, contract = confirmed_generation(application, proposal_jobs)
    generation_repository = InMemoryProductGenerationJobRepository()
    generation_class = BrokenAriaLiveGenerationService if broken_template else ProductGenerationJobService
    generation = generation_class(
        application,
        generation_repository,
        workspace_root=root,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
    )
    return application, proposal_jobs, generation, project, contract


def test_confirmed_contract_materializes_bounded_workspace_and_is_idempotent(tmp_path):
    application, _, generation, project, contract = build_generation_services(
        tmp_path / "workspaces"
    )

    queued = generation.create_job(
        project_id=project.project_id, actor="user-li", reason="materialize"
    )
    duplicate = generation.create_job(
        project_id=project.project_id, actor="user-li", reason="repeat click"
    )
    assert duplicate.job_id == queued.job_id
    assert queued.web_generation_contract_revision_id == contract.revision_id
    assert not generation._workspace_path(queued).exists()

    completed = generation.run_job(project.project_id, queued.job_id, actor="worker")
    assert completed.status == "succeeded"
    assert completed.manifest is not None
    assert completed.consumed_files == len(completed.manifest.files)
    assert completed.consumed_bytes == completed.manifest.total_bytes
    assert completed.sandbox.network_policy == "none"
    assert completed.sandbox.execution_policy == "not_executed"
    workspace = generation._workspace_path(completed)
    assert (workspace / "src" / "App.tsx").is_file()
    assert (workspace / "generation-manifest.json").is_file()
    assert generation.run_job(project.project_id, queued.job_id, actor="worker") == completed


def test_template_materializer_version_invalidates_completed_b3_cache(tmp_path):
    from psyteardown.product.models import GENERATION_JOB_VERSION

    _, _, generation, project, _ = build_generation_services(tmp_path / "workspaces")
    queued = generation.create_job(
        project_id=project.project_id, actor="user-li", reason="materialize current renderer"
    )
    assert GENERATION_JOB_VERSION == "b3-v2"
    assert queued.provider_version == GENERATION_JOB_VERSION
    assert generation.create_job(
        project_id=project.project_id, actor="user-li", reason="same current renderer"
    ).job_id == queued.job_id


def test_generation_stale_input_does_not_materialize_workspace(tmp_path):
    application, _, generation, project, contract = build_generation_services(
        tmp_path / "workspaces"
    )
    queued = generation.create_job(
        project_id=project.project_id, actor="user-li", reason="materialize"
    )
    draft = application.get_project_view(project.project_id).web_generation_contract
    assert draft is not None
    application.submit_web_generation_contract(
        SubmitWebProductGenerationContractProposal(
            project_id=project.project_id,
            web_generation_contract_id=draft.web_generation_contract_id,
            expected_revision=draft.meta.revision,
            actor="user-li",
            reason="correct title",
            proposal=draft.model_dump(
                mode="python",
                exclude={"web_generation_contract_id", "revision_id", "meta", "project_id", "status", "confirmation", "dependencies", "template_id", "template_version", "runtime_dependencies", "development_dependencies", "output_paths", "network_policy", "data_policy"},
            ),
        )
    )
    stale = generation.run_job(project.project_id, queued.job_id, actor="worker")
    assert stale.status == "stale_input"
    assert not generation._workspace_path(stale).exists()


def test_generation_detects_transitive_thesis_revision_change(tmp_path):
    application, _, generation, project, _ = build_generation_services(
        tmp_path / "workspaces"
    )
    queued = generation.create_job(
        project_id=project.project_id, actor="user-li", reason="materialize"
    )
    thesis = application.get_project_view(project.project_id).product_theses[0]
    application.transition_product_thesis(
        TransitionProductThesis(
            project_id=project.project_id,
            thesis_id=thesis.thesis_id,
            expected_revision=thesis.meta.revision,
            to_status="selected",
            actor="user-li",
            actor_type="human",
            reason="select the path",
        )
    )
    stale = generation.run_job(project.project_id, queued.job_id, actor="worker")
    assert stale.status == "stale_input"


def test_generation_budget_exhaustion_is_explicit_and_safe(tmp_path):
    _, _, generation, project, _ = build_generation_services(tmp_path / "workspaces")
    queued = generation.create_job(
        project_id=project.project_id,
        actor="user-li",
        reason="materialize",
        budget=GenerationBudget(max_bytes=100),
    )
    exhausted = generation.run_job(project.project_id, queued.job_id, actor="worker")
    assert exhausted.status == "budget_exhausted"
    assert exhausted.error_code == "budget_exhausted"
    assert not generation._workspace_path(exhausted).exists()


def test_sqlite_generation_job_recovers_after_restart(tmp_path):
    database = tmp_path / "product.sqlite3"
    ids = SequenceIds()
    first_repository = SQLiteProductRepository(database)
    first_application = ProductApplicationService(first_repository, clock=lambda: NOW, id_factory=ids)
    # Build the domain chain against the SQLite application, preserving the
    # same setup helper's deterministic provider semantics.
    project, _ = confirmed_generation(
        first_application,
        ProductProposalJobService(first_application, first_repository, clock=lambda: NOW, id_factory=ids),
    )
    first_generation = ProductGenerationJobService(
        first_application,
        first_repository,
        workspace_root=tmp_path / "workspaces",
        clock=lambda: NOW,
        id_factory=ids,
    )
    queued = first_generation.create_job(
        project_id=project.project_id, actor="user-li", reason="materialize"
    )
    first_generation.run_job(project.project_id, queued.job_id, actor="worker")
    first_repository.close()

    second_repository = SQLiteProductRepository(database)
    try:
        second_application = ProductApplicationService(second_repository, clock=lambda: NOW, id_factory=ids)
        second_generation = ProductGenerationJobService(
            second_application,
            second_repository,
            workspace_root=tmp_path / "workspaces",
            clock=lambda: NOW,
            id_factory=ids,
        )
        recovered = second_generation.get_job(project.project_id, queued.job_id)
        assert recovered.status == "succeeded"
        assert recovered.manifest is not None
        assert second_generation.list_jobs(project.project_id)[0].job_id == queued.job_id
    finally:
        second_repository.close()


def test_generation_budget_limits_cannot_be_raised_above_defaults():
    with pytest.raises(ValueError):
        GenerationBudget(max_bytes=2 * 1024 * 1024)
