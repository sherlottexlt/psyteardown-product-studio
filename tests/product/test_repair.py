from collections import defaultdict
from datetime import datetime, timezone
import hashlib

from psyteardown.product import (
    InMemoryProductExecutionJobRepository,
    InMemoryProductRepairJobRepository,
    ProductRepairJobService,
    RepairBudget,
    ProductRepairJob,
    SQLiteProductRepository,
    RepairPlan,
    RepairPatch,
)
from psyteardown.experience.models import DependencyRef, RevisionMeta
from psyteardown.product.execution import CommandResult, ExecutionCommandError
from .test_execution import build_execution_service


NOW = datetime(2026, 9, 22, 13, 0, tzinfo=timezone.utc)


class SequenceIds:
    def __init__(self) -> None:
        self.counts = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}-{self.counts[prefix]}"


class FailBrowserOnce:
    def __init__(self) -> None:
        self.failed = False

    def run(self, argv, *, cwd, timeout, env):
        return CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="ok")

    def run_preview_and_browser(self, *, preview_argv, browser_argv, cwd, timeout, env):
        if not self.failed:
            self.failed = True
            raise ExecutionCommandError("command_failed", "The browser check failed safely.")
        return (
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="preview"),
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="browser"),
        )


class FailBuild:
    def run(self, argv, *, cwd, timeout, env):
        if "build" in argv:
            raise ExecutionCommandError("command_failed", "Unknown build failure")
        return CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="ok")

    def run_preview_and_browser(self, *, preview_argv, browser_argv, cwd, timeout, env):
        return (
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="preview"),
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="browser"),
        )


class TooManyPatchPlanner:
    def plan(self, context, *, workspace, manifest):
        source = workspace / "src" / "App.tsx"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        patch = RepairPatch(path="src/App.tsx", expected_sha256=digest, search="Ready.", replace="Ready!", rationale="bounded test patch")
        return RepairPlan("This deliberately exceeds the patch budget.", (patch, patch, patch))


def test_b5_repair_creates_child_lineage_and_reverifies(tmp_path):
    runner = FailBrowserOnce()
    execution_service, project, generated = build_execution_service(tmp_path, runner=runner, broken_template=True)
    failed = execution_service.run_job(
        project.project_id,
        execution_service.create_job(
            project_id=project.project_id,
            generation_job_id=generated.job_id,
            actor="user",
            reason="validate",
        ).job_id,
        actor="worker",
    )
    assert failed.status == "failed"
    repair_repository = InMemoryProductRepairJobRepository()
    repair_service = ProductRepairJobService(
        execution_service.application,
        repair_repository,
        execution_service.generation_repository,
        execution_service.job_repository,
        execution_service,
        workspace_root=tmp_path / "workspaces",
        clock=lambda: NOW,
        id_factory=SequenceIds(),
    )
    queued = repair_service.create_job(
        project_id=project.project_id,
        execution_job_id=failed.job_id,
        actor="user",
        reason="repair browser failure",
    )
    completed = repair_service.run_job(project.project_id, queued.job_id, actor="worker")
    assert completed.status == "succeeded"
    assert completed.attempts[0].status == "verified"
    assert completed.latest_generation_job_id
    assert completed.latest_execution_job_id
    repaired = execution_service.generation_repository.get_generation_job(completed.latest_generation_job_id)
    assert repaired is not None
    assert repaired.materialization_kind == "repair"
    assert repaired.parent_generation_job_id == generated.job_id
    assert repaired.job_id != generated.job_id
    assert generated.status == "succeeded"
    original_app = (tmp_path / "workspaces" / generated.workspace_relative_path / "src" / "App.tsx").read_text(encoding="utf-8")
    repaired_app = (tmp_path / "workspaces" / repaired.workspace_relative_path / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "aria-live" not in original_app
    assert "aria-live" in repaired_app


def test_b5_unknown_failure_is_retained_without_guessing(tmp_path):
    execution_service, project, generated = build_execution_service(tmp_path, runner=FailBuild())
    queued_execution = execution_service.create_job(
        project_id=project.project_id,
        generation_job_id=generated.job_id,
        actor="user",
        reason="validate",
    )
    failed = execution_service.run_job(project.project_id, queued_execution.job_id, actor="worker")
    repair_service = ProductRepairJobService(
        execution_service.application,
        InMemoryProductRepairJobRepository(),
        execution_service.generation_repository,
        execution_service.job_repository,
        execution_service,
        workspace_root=tmp_path / "workspaces",
    )
    queued = repair_service.create_job(
        project_id=project.project_id,
        execution_job_id=failed.job_id,
        actor="user",
        reason="repair",
        budget=RepairBudget(max_attempts=1),
    )
    completed = repair_service.run_job(project.project_id, queued.job_id, actor="worker")
    assert completed.status in {"failed", "budget_exhausted"}
    assert completed.attempts[0].status in {"failed", "unsupported"}
    assert completed.latest_generation_job_id is None
    assert completed.status == "failed"
    try:
        repair_service.retry_job(project.project_id, queued.job_id, actor="user")
    except Exception as exc:
        assert "no allowlisted patch" in str(exc)
    else:
        raise AssertionError("an unsupported deterministic repair must not be retried")
    duplicate = repair_service.create_job(
        project_id=project.project_id,
        execution_job_id=failed.job_id,
        actor="user",
        reason="repeat repair",
        budget=RepairBudget(max_attempts=1),
    )
    assert duplicate.job_id == queued.job_id


def test_b5_sqlite_repository_recovers_current_revision(tmp_path):
    database = tmp_path / "product.sqlite3"
    job = ProductRepairJob(
        job_id="repair-job-1",
        revision_id="repair-job-1.r1",
        meta=RevisionMeta(revision=1, created_at=NOW, created_by="user", reason="repair"),
        project_id="project-1",
        input_dependencies=(DependencyRef(object_type="product_execution_job", object_id="execution-job-1", revision=6),),
        execution_job_id="execution-job-1",
        execution_job_revision_id="execution-job-1.r6",
        generation_job_id="generation-job-1",
        generation_job_revision_id="generation-job-1.r2",
        budget=RepairBudget(),
        fingerprint="repair-fingerprint",
    )
    repository = SQLiteProductRepository(database)
    repository.save_repair_job(job, expected_revision=None)
    repository.close()
    reopened = SQLiteProductRepository(database)
    try:
        recovered = reopened.get_repair_job(job.job_id)
        assert recovered == job
        assert reopened.list_repair_jobs(project_id="project-1") == [job]
    finally:
        reopened.close()


def test_b5_over_budget_plan_is_rejected_without_invalid_persisted_attempt(tmp_path):
    execution_service, project, generated = build_execution_service(tmp_path, runner=FailBuild())
    execution = execution_service.create_job(project_id=project.project_id, generation_job_id=generated.job_id, actor="user", reason="validate")
    failed = execution_service.run_job(project.project_id, execution.job_id, actor="worker")
    repair_service = ProductRepairJobService(
        execution_service.application,
        InMemoryProductRepairJobRepository(),
        execution_service.generation_repository,
        execution_service.job_repository,
        execution_service,
        workspace_root=tmp_path / "workspaces",
        planner=TooManyPatchPlanner(),
    )
    queued = repair_service.create_job(project_id=project.project_id, execution_job_id=failed.job_id, actor="user", reason="repair", budget=RepairBudget(max_patches=2))
    completed = repair_service.run_job(project.project_id, queued.job_id, actor="worker")
    assert completed.status == "failed"
    assert completed.error_code == "patch_limit"
    assert completed.attempts[0].patches == ()
