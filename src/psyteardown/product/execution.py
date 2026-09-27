"""B4 execution sandbox for generated Web workspaces.

Source generation and execution intentionally have different services and
different persisted jobs.  The default runner is conservative (argument
arrays, a scrubbed environment, a contained cwd and bounded output); tests
can inject a runner without spawning npm or a browser.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.generation import ProductGenerationJobRepository
from psyteardown.product.models import (
    ExecutionBudget,
    ExecutionStep,
    GenerationManifest,
    ProductExecutionJob,
    ProductGenerationJob,
)
from psyteardown.product.repositories import ProductRepositoryError


class ProductExecutionJobRepository(Protocol):
    def save_execution_job(
        self, job: ProductExecutionJob, *, expected_revision: int | None
    ) -> ProductExecutionJob: ...

    def get_execution_job(self, job_id: str) -> ProductExecutionJob | None: ...

    def list_execution_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductExecutionJob]: ...

    def get_generation_job(self, job_id: str) -> ProductGenerationJob | None: ...


class InMemoryProductExecutionJobRepository:
    """Revisioned in-memory execution adapter used by unit tests."""

    def __init__(self, generation_repository: ProductGenerationJobRepository | None = None) -> None:
        self._revisions: dict[str, dict[int, ProductExecutionJob]] = defaultdict(dict)
        self._current: dict[str, int] = {}
        self._generation_repository = generation_repository

    def attach_generation_repository(self, repository: ProductGenerationJobRepository) -> None:
        self._generation_repository = repository

    def save_execution_job(
        self, job: ProductExecutionJob, *, expected_revision: int | None
    ) -> ProductExecutionJob:
        current = self.get_execution_job(job.job_id)
        _validate_execution_job_revision(current, job, expected_revision)
        self._revisions[job.job_id][job.meta.revision] = job
        self._current[job.job_id] = job.meta.revision
        return job

    def get_execution_job(self, job_id: str) -> ProductExecutionJob | None:
        revision = self._current.get(job_id)
        return self._revisions[job_id].get(revision) if revision else None

    def list_execution_jobs(self, *, project_id: str | None = None) -> list[ProductExecutionJob]:
        values = [self.get_execution_job(job_id) for job_id in self._current]
        return sorted(
            [
                value
                for value in values
                if value is not None
                and (project_id is None or value.project_id == project_id)
            ],
            key=lambda item: (item.meta.created_at, item.job_id),
        )

    def get_generation_job(self, job_id: str) -> ProductGenerationJob | None:
        return self._generation_repository.get_generation_job(job_id) if self._generation_repository else None


class ExecutionCommandError(RuntimeError):
    def __init__(self, code: str, summary: str, *, output_bytes: int = 0) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.output_bytes = output_bytes


class ExecutionCommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, cwd: Path, timeout: float, env: Mapping[str, str]) -> "CommandResult": ...

    def run_preview_and_browser(
        self,
        *,
        preview_argv: Sequence[str],
        browser_argv: Sequence[str],
        cwd: Path,
        timeout: float,
        env: Mapping[str, str],
    ) -> tuple["CommandResult", "CommandResult"]: ...


class CommandResult:
    def __init__(self, *, exit_code: int, output_bytes: int = 0, duration_seconds: float = 0, summary: str = "") -> None:
        self.exit_code = exit_code
        self.output_bytes = output_bytes
        self.duration_seconds = duration_seconds
        self.summary = summary


def _classify_browser_failure(output: bytes, default_code: str) -> str:
    """Map browser output to a safe diagnostic category without retaining it."""

    if not default_code.startswith("browser_"):
        return default_code
    text = output.decode("utf-8", errors="replace").lower()
    if "axe" in text or "accessibility" in text or "violations" in text:
        return "browser_accessibility_failed"
    if "expect(" in text or "tobevisible" in text or "locator" in text or "assert" in text:
        return "browser_assertion_failed"
    if "browsertype.launch" in text or "executable doesn't exist" in text or "browser executable" in text:
        return "browser_launch_failed"
    return default_code


def _browser_timeout(*, output_bytes: int = 0) -> ExecutionCommandError:
    """Build a safe timeout error for the browser phase.

    ``run_timeout`` is reserved for the outer C3 attempt watchdog. A timeout
    raised by the B4 browser command must remain a B4 diagnostic so the two
    boundaries cannot be confused in an aggregate report.
    """

    return ExecutionCommandError(
        "browser_timeout",
        "The browser validation exceeded its time budget.",
        output_bytes=output_bytes,
    )


class SubprocessExecutionCommandRunner:
    """Allowlisted, no-shell subprocess runner for the local development slice."""

    def run(self, argv: Sequence[str], *, cwd: Path, timeout: float, env: Mapping[str, str]) -> CommandResult:
        return self._run(argv, cwd=cwd, timeout=timeout, env=env)

    def run_preview_and_browser(
        self,
        *,
        preview_argv: Sequence[str],
        browser_argv: Sequence[str],
        cwd: Path,
        timeout: float,
        env: Mapping[str, str],
    ) -> tuple[CommandResult, CommandResult]:
        started = time.monotonic()
        preview_port = _preview_port_from_argv(preview_argv)
        preview_url = f"http://127.0.0.1:{preview_port}"
        if _loopback_port_open(preview_port):
            # Validating whatever already listens there would verify another
            # workspace (or an orphan from an earlier run), not this one.
            raise ExecutionCommandError("preview_port_busy", "The loopback preview port is already in use.")
        try:
            process = subprocess.Popen(
                list(preview_argv), cwd=str(cwd), env=dict(env), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, shell=False,
                **_process_group_options(),
            )
        except OSError as exc:
            raise ExecutionCommandError("runtime_unavailable", "The local preview command could not be started.") from exc
        try:
            deadline = time.monotonic() + min(timeout, 30)
            healthy = False
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(_PREVIEW_URL, timeout=0.5) as response:
                        healthy = 200 <= response.status < 500
                        if healthy:
                            break
                except Exception:
                    time.sleep(0.1)
            if not healthy:
                raise ExecutionCommandError("preview_unavailable", "The local preview did not become ready.")
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                # Preview is the B4 ``run`` phase. Keep its exhausted budget
                # out of the browser diagnostic namespace.
                raise ExecutionCommandError("timeout", "The preview and browser steps exceeded their time budget.")
            browser = self._run(
                browser_argv,
                cwd=cwd,
                timeout=remaining,
                env={**env, "BASE_URL": preview_url},
                failure_code="browser_command_failed",
            )
            preview = CommandResult(exit_code=0, output_bytes=0, duration_seconds=time.monotonic() - started, summary="Local preview served on loopback.")
            return preview, browser
        finally:
            _stop_process_tree(process)

    def _run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
        env: Mapping[str, str],
        failure_code: str = "command_failed",
    ) -> CommandResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(argv), cwd=str(cwd), env=dict(env), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, shell=False,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            if failure_code.startswith("browser_"):
                raise _browser_timeout(output_bytes=len(exc.output or b"")) from exc
            raise ExecutionCommandError("timeout", "The execution step exceeded its time budget.", output_bytes=len(exc.output or b"")) from exc
        except OSError as exc:
            if failure_code.startswith("browser_"):
                raise ExecutionCommandError("browser_launch_failed", "The browser validation command could not be started.") from exc
            raise ExecutionCommandError("command_unavailable", "The allowlisted execution command is unavailable.") from exc
        output = completed.stdout or b""
        if completed.returncode != 0:
            raise ExecutionCommandError(
                _classify_browser_failure(output, failure_code),
                f"The allowlisted command failed with exit code {completed.returncode}.",
                output_bytes=len(output),
            )
        return CommandResult(
            exit_code=completed.returncode,
            output_bytes=len(output),
            duration_seconds=time.monotonic() - started,
            summary="Command completed successfully.",
        )


_PREVIEW_PORT = 4173
_PREVIEW_URL = f"http://127.0.0.1:{_PREVIEW_PORT}"


def _preview_port_from_argv(argv: Sequence[str]) -> int:
    try:
        index = list(argv).index("--port")
        return int(argv[index + 1])
    except (ValueError, IndexError, TypeError):
        return _PREVIEW_PORT


def _select_preview_port() -> int:
    """Prefer the documented port, then fall back to an available local port."""
    if not _loopback_port_open(_PREVIEW_PORT):
        return _PREVIEW_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _loopback_port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _process_group_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _stop_process_tree(process: subprocess.Popen) -> None:
    """Stop the preview and every descendant (npm.cmd -> node vite)."""

    if os.name == "nt":
        # Always run: taskkill /T also reaps children whose wrapper already exited.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.wait(timeout=3)


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class ProductExecutionJobService:
    """Run only a successful B3 workspace under an explicit B4 grant."""

    def __init__(
        self,
        application,
        job_repository: ProductExecutionJobRepository,
        generation_repository: ProductGenerationJobRepository,
        *,
        workspace_root: Path | str = Path("output/product-studio/workspaces"),
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
        command_runner: ExecutionCommandRunner | None = None,
    ) -> None:
        self.application = application
        self.job_repository = job_repository
        self.generation_repository = generation_repository
        if hasattr(job_repository, "attach_generation_repository"):
            job_repository.attach_generation_repository(generation_repository)
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._root = self.workspace_root.resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")
        self.runner = command_runner or SubprocessExecutionCommandRunner()

    def create_job(
        self,
        *,
        project_id: str,
        generation_job_id: str,
        actor: str,
        reason: str,
        budget: ExecutionBudget | None = None,
    ) -> ProductExecutionJob:
        self.application.get_project_view(project_id)
        generation = self.generation_repository.get_generation_job(generation_job_id)
        self._check_generation(project_id, generation)
        selected_budget = budget or ExecutionBudget()
        dependency = DependencyRef(
            object_type="product_generation_job",
            object_id=generation.job_id,
            revision=generation.meta.revision,
        )
        fingerprint = _fingerprint(project_id, dependency, selected_budget)
        reusable = next(
            (item for item in reversed(self.job_repository.list_execution_jobs(project_id=project_id))
             if item.fingerprint == fingerprint and item.status in {"queued", "running", "succeeded"}),
            None,
        )
        if reusable:
            return reusable
        job_id = self._id("execution-job")
        job = ProductExecutionJob(
            job_id=job_id,
            revision_id=f"{job_id}.r1",
            meta=RevisionMeta(revision=1, created_at=self._now(), created_by=actor, reason=reason),
            project_id=project_id,
            input_dependencies=(dependency,),
            generation_job_id=generation.job_id,
            generation_job_revision_id=generation.revision_id,
            workspace_relative_path=generation.workspace_relative_path,
            budget=selected_budget,
            fingerprint=fingerprint,
        )
        return self.job_repository.save_execution_job(job, expected_revision=None)

    def get_job(self, project_id: str, job_id: str) -> ProductExecutionJob:
        job = self.job_repository.get_execution_job(job_id)
        if job is None:
            raise DomainStateError(f"unknown product execution job: {job_id}")
        if job.project_id != project_id:
            raise DomainStateError(f"product execution job belongs to project {job.project_id}, not {project_id}")
        return job

    def list_jobs(self, project_id: str) -> tuple[ProductExecutionJob, ...]:
        self.application.get_project_view(project_id)
        return tuple(self.job_repository.list_execution_jobs(project_id=project_id))

    def run_job(self, project_id: str, job_id: str, *, actor: str) -> ProductExecutionJob:
        job = self.get_job(project_id, job_id)
        if job.status == "succeeded":
            return job
        if job.status != "queued":
            raise DomainStateError(f"product execution job cannot run from status {job.status}")
        generation = self.generation_repository.get_generation_job(job.generation_job_id)
        self._check_generation(project_id, generation)
        assert generation is not None
        if generation.meta.revision != job.input_dependencies[0].revision or generation.status != "succeeded":
            return self._transition(job, status="stale_input", actor=actor, reason="generated workspace revision changed", error_code="stale_input", error_summary="The generated workspace is no longer the pinned input.")
        workspace = self._workspace_path(job)
        try:
            self._validate_workspace(workspace, generation)
        except DomainStateError:
            return self._transition(job, status="failed", actor=actor, reason="execution sandbox rejected workspace", error_code="sandbox_violation", error_summary="The generated workspace failed execution integrity checks.")
        started = time.monotonic()
        running = self._transition(job, status="running", actor=actor, reason="execution worker claimed job", attempt=job.attempt + 1, checkpoint_step="install", consumed_cost_units=1, steps=_initial_steps())
        env = _safe_environment()
        try:
            self._check_budget(running, started)
            install = self.runner.run([_npm(), "install", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=workspace, timeout=running.budget.max_duration_seconds, env=env)
            running = self._step_transition(running, "install", install, actor)
            build = self.runner.run([_npm(), "run", "build"], cwd=workspace, timeout=self._remaining(running, started), env=env)
            running = self._step_transition(running, "build", build, actor)
            preview, browser = self.runner.run_preview_and_browser(
                preview_argv=[_npm(), "run", "preview", "--", "--host", "127.0.0.1", "--port", str(_select_preview_port())],
                browser_argv=[_npx(), "--no-install", "playwright", "test", "--config", "playwright.config.ts"],
                cwd=workspace, timeout=self._remaining(running, started), env=env,
            )
            running = self._step_transition(running, "run", preview, actor)
            running = self._step_transition(running, "browser", browser, actor)
            self._check_budget(running, started)
        except ExecutionCommandError as exc:
            # Preview startup is the `run` phase, while Playwright is the
            # `browser` phase even though both are launched by one runner call.
            # Preserve that distinction so C3 can diagnose browser flakiness
            # without exposing command output.
            if exc.code.startswith("browser_"):
                # The combined runner only raises for the browser after the
                # preview has become healthy. Commit that successful run phase
                # before recording the browser failure.
                running = self._step_transition(
                    running,
                    "run",
                    CommandResult(exit_code=0, summary="Local preview served on loopback."),
                    actor,
                )
                step_name = "browser"
            else:
                step_name = running.checkpoint_step or "install"
            running = self._failure_step(running, step_name, exc, actor)
            return self._transition(running, status="budget_exhausted" if exc.code in {"timeout", "browser_timeout", "output_limit"} else "failed", actor=actor, reason="execution sandbox step failed", error_code=exc.code, error_summary=exc.summary, consumed_duration_seconds=time.monotonic() - started)
        except (ProductRepositoryError, DomainStateError):
            raise
        except Exception:
            return self._transition(running, status="failed", actor=actor, reason="execution sandbox rejected workspace", error_code="sandbox_violation", error_summary="The workspace did not satisfy the execution sandbox policy.", consumed_duration_seconds=time.monotonic() - started)
        return self._transition(
            running,
            status="succeeded",
            actor=actor,
            reason="build, preview and browser validation completed",
            checkpoint_step="browser",
            consumed_duration_seconds=time.monotonic() - started,
            build_artifact_relative_path="dist/",
            browser_report_relative_path="test-results/",
        )

    def recover_job(
        self,
        project_id: str,
        job_id: str,
        *,
        actor: str,
        confirm_orphaned: bool = False,
    ) -> ProductExecutionJob:
        """Requeue a persisted running job after the client/process was interrupted.

        This is deliberately explicit: the service cannot prove whether an old
        subprocess is still alive, so the caller must confirm that the job is
        orphaned before another run may start.
        """
        job = self.get_job(project_id, job_id)
        if job.status != "running":
            raise DomainStateError("only running execution jobs can be recovered")
        if not confirm_orphaned:
            raise DomainStateError("confirm that the running execution is orphaned before recovery")
        return self._transition(
            job,
            status="queued",
            actor=actor,
            reason="recovered orphaned execution after local interruption",
            checkpoint_step=None,
            steps=(),
            consumed_duration_seconds=0,
            consumed_output_bytes=0,
            error_code=None,
            error_summary=None,
        )

    def cancel_job(self, project_id: str, job_id: str, *, actor: str) -> ProductExecutionJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"queued", "running"}:
            raise DomainStateError("only active execution jobs can be cancelled")
        return self._transition(job, status="cancelled", actor=actor, reason="execution cancelled by user")

    def retry_job(self, project_id: str, job_id: str, *, actor: str) -> ProductExecutionJob:
        job = self.get_job(project_id, job_id)
        if job.status not in {"failed", "budget_exhausted", "stale_input"}:
            raise DomainStateError("only failed execution jobs can be retried")
        if job.attempt >= job.budget.max_attempts or job.consumed_cost_units >= job.budget.max_cost_units:
            return self._transition(job, status="budget_exhausted", actor=actor, reason="execution retry exceeds budget", error_code="budget_exhausted", error_summary="The execution retry budget was exhausted.")
        return self._transition(job, status="queued", actor=actor, reason="execution retry requested")

    def _check_generation(self, project_id: str, generation: ProductGenerationJob | None) -> None:
        if generation is None:
            raise DomainStateError("unknown product generation job")
        if generation.project_id != project_id:
            raise DomainStateError("product generation job belongs to another project")
        if generation.status != "succeeded" or generation.manifest is None:
            raise DomainStateError("a succeeded generation workspace is required before execution")

    def _workspace_path(self, job: ProductExecutionJob) -> Path:
        candidate = (self._root / job.workspace_relative_path).resolve(strict=False)
        try:
            if os.path.commonpath((str(self._root), str(candidate))) != str(self._root):
                raise ValueError
        except ValueError as exc:
            raise DomainStateError("execution workspace is outside the configured root") from exc
        return candidate

    def _validate_workspace(self, workspace: Path, generation: ProductGenerationJob) -> None:
        validate_generated_workspace(workspace, generation)

    def _step_transition(self, current: ProductExecutionJob, name: str, result: CommandResult, actor: str) -> ProductExecutionJob:
        if current.consumed_output_bytes + result.output_bytes > current.budget.max_output_bytes:
            raise ExecutionCommandError("output_limit", "The execution output budget was exhausted.", output_bytes=result.output_bytes)
        steps = tuple(ExecutionStep(name=step.name, status="succeeded", exit_code=result.exit_code, duration_seconds=result.duration_seconds, output_bytes=result.output_bytes, summary=result.summary) if step.name == name else step for step in current.steps)
        next_name = {"install": "build", "build": "run", "run": "browser", "browser": "browser"}[name]
        return self._transition(current, status="running", actor=actor, reason=f"execution {name} completed", checkpoint_step=next_name, steps=steps, consumed_output_bytes=current.consumed_output_bytes + result.output_bytes, consumed_duration_seconds=current.consumed_duration_seconds + result.duration_seconds)

    def _failure_step(self, current: ProductExecutionJob, name: str, error: ExecutionCommandError, actor: str) -> ProductExecutionJob:
        output_bytes = min(error.output_bytes, current.budget.max_output_bytes)
        steps = tuple(ExecutionStep(name=step.name, status="failed", output_bytes=output_bytes, summary=error.summary, error_code=error.code) if step.name == name else step for step in current.steps)
        return self._transition(current, status="running", actor=actor, reason=f"execution {name} failed", steps=steps, consumed_output_bytes=min(current.consumed_output_bytes + output_bytes, current.budget.max_output_bytes), consumed_duration_seconds=current.consumed_duration_seconds)

    def _check_budget(self, job: ProductExecutionJob, started: float) -> None:
        if job.consumed_output_bytes > job.budget.max_output_bytes or time.monotonic() - started > job.budget.max_duration_seconds or job.consumed_cost_units > job.budget.max_cost_units:
            raise ExecutionCommandError("output_limit" if job.consumed_output_bytes > job.budget.max_output_bytes else "timeout", "The execution budget was exhausted.")

    def _remaining(self, job: ProductExecutionJob, started: float) -> float:
        remaining = job.budget.max_duration_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ExecutionCommandError("timeout", "The execution step exceeded its time budget.")
        return remaining

    def _transition(self, current: ProductExecutionJob, *, status: str, actor: str, reason: str, **updates) -> ProductExecutionJob:
        revision = current.meta.revision + 1
        values = {**updates, "status": status, "revision_id": f"{current.job_id}.r{revision}", "meta": RevisionMeta(revision=revision, parent_revision_id=current.revision_id, created_at=self._now(), created_by=actor, reason=reason)}
        if status not in {"failed", "budget_exhausted", "stale_input"}:
            values.setdefault("error_code", None)
            values.setdefault("error_summary", None)
        return self.job_repository.save_execution_job(current.model_copy(update=values), expected_revision=current.meta.revision)

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value or not _SAFE_SEGMENT.fullmatch(value):
            raise ValueError("execution identifier is not safe")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("execution clock must be timezone-aware")
        return value


_EXECUTION_OUTPUT_ROOTS = frozenset({"node_modules", "dist", "test-results", "playwright-report"})
# Root files written by generation bookkeeping or by execution tooling.
_EXECUTION_ROOT_FILES = frozenset({"generation-manifest.json", "package-lock.json", "tsconfig.tsbuildinfo"})


def validate_generated_workspace(workspace: Path, generation: ProductGenerationJob) -> None:
    """Check a generation workspace against its manifest and fixed package policy.

    Shared by B4 execution, B5 repair and B6 delivery so every consumer applies
    the same integrity rules before trusting workspace bytes.
    """
    if not workspace.is_dir() or workspace.is_symlink():
        raise DomainStateError("generated workspace is unavailable")
    manifest_path = workspace / "generation-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise DomainStateError("generated workspace manifest is unavailable")
    try:
        manifest = generation.manifest
        payload = GenerationManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest is None or payload != manifest:
            raise ValueError
        declared = {item.path for item in manifest.files}
        # Execution outputs are owned by npm/tsc/vite/Playwright, never packaged
        # as source, and may legitimately contain symlinks (node_modules/.bin).
        # B6 re-checks dist/ and test-results/ itself before packaging them.
        actual: set[str] = set()
        for directory, subdirectories, files in os.walk(workspace):
            base = Path(directory)
            if base == workspace:
                subdirectories[:] = [name for name in subdirectories if name not in _EXECUTION_OUTPUT_ROOTS]
            for name in subdirectories:
                if (base / name).is_symlink():
                    raise ValueError
            for name in files:
                path = base / name
                if path.is_symlink():
                    raise ValueError
                relative = path.relative_to(workspace).as_posix()
                if relative not in _EXECUTION_ROOT_FILES:
                    actual.add(relative)
        if actual != declared:
            raise ValueError
        for item in manifest.files:
            target = (workspace / item.path).resolve(strict=False)
            source = workspace / item.path
            if source.is_symlink() or os.path.commonpath((str(workspace.resolve()), str(target))) != str(workspace.resolve()) or not target.is_file() or target.is_symlink():
                raise ValueError
            raw = target.read_bytes()
            if len(raw) != item.byte_count or hashlib.sha256(raw).hexdigest() != item.sha256:
                raise ValueError
        package = json.loads((workspace / "package.json").read_text(encoding="utf-8"))
        scripts = package.get("scripts", {})
        if scripts.get("build") != "tsc -b && vite build" or scripts.get("preview") != "vite preview":
            raise ValueError
        if package.get("private") is not True:
            raise ValueError
        expected_dependencies = {
            "react": "19.1.1",
            "react-dom": "19.1.1",
        }
        expected_dev_dependencies = {
            "@axe-core/playwright": "4.13.0",
            "@playwright/test": "1.55.1",
            "@testing-library/react": "16.3.0",
            "@types/react": "19.1.16",
            "@types/react-dom": "19.1.9",
            "@vitejs/plugin-react": "5.0.4",
            "typescript": "5.9.3",
            "vite": "7.1.9",
            "vitest": "5.0.1",
        }
        if package.get("dependencies") != expected_dependencies or package.get("devDependencies") != expected_dev_dependencies:
            raise ValueError
    except Exception as exc:
        raise DomainStateError("generated workspace failed integrity validation") from exc


def _initial_steps() -> tuple[ExecutionStep, ...]:
    return tuple(ExecutionStep(name=name) for name in ("install", "build", "run", "browser"))


def _safe_environment() -> dict[str, str]:
    # PATH is needed to locate node/npm on the host; all token/config/home
    # variables are intentionally dropped before entering the workspace.
    # Windows reports keys upper-cased, so match case-insensitively; Node
    # cannot initialise its CSPRNG without SYSTEMROOT.
    allowed = {"PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "USERPROFILE"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update({
        "CI": "1",
        "NPM_CONFIG_IGNORE_SCRIPTS": "true",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        **_empty_npm_configs(),
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
    })
    return environment


def _empty_npm_configs() -> dict[str, str]:
    # npm rejects one path loaded as both user and global config, so each gets
    # its own empty file.  They live outside every workspace so the manifest
    # integrity check never sees them.
    directory = Path(tempfile.gettempdir()) / "psyteardown-npm-config"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {"NPM_CONFIG_USERCONFIG": directory / "userconfig", "NPM_CONFIG_GLOBALCONFIG": directory / "globalconfig"}
    for path in paths.values():
        if path.is_symlink() or not path.is_file() or path.stat().st_size:
            path.unlink(missing_ok=True)
            path.write_text("", encoding="utf-8")
    return {key: str(path.resolve()) for key, path in paths.items()}


def _npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _npx() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def _fingerprint(project_id: str, dependency: DependencyRef, budget: ExecutionBudget) -> str:
    payload = {"project_id": project_id, "dependency": dependency.model_dump(mode="json"), "budget": budget.model_dump(mode="json"), "provider": "local_execution_sandbox", "version": "b4-v1"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_execution_job_revision(current: ProductExecutionJob | None, value: ProductExecutionJob, expected_revision: int | None) -> None:
    if current is None:
        if expected_revision is not None or value.meta.revision != 1:
            raise ProductRepositoryError("execution job first revision conflict")
        return
    if expected_revision != current.meta.revision:
        raise ProductRepositoryError(f"revision conflict: expected {expected_revision}, current {current.meta.revision}")
    if value.meta.revision != current.meta.revision + 1 or value.meta.parent_revision_id != current.revision_id:
        raise ProductRepositoryError("execution job revisions must increase by one and reference current parent")
