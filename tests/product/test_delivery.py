from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import zipfile

import pytest

from psyteardown.experience.models import DomainStateError
from psyteardown.product import (
    InMemoryProductDeliveryBundleRepository,
    InMemoryProductRepairJobRepository,
    ProductDeliveryBundleService,
    ProductRepairJobService,
    ProductRepositoryError,
    SQLiteProductRepository,
)
from psyteardown.product.execution import CommandResult, ExecutionCommandError
from .test_execution import build_execution_service


NOW = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)


class SequenceIds:
    def __init__(self) -> None:
        self.counts = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}-{self.counts[prefix]}"


class ArtifactRunner:
    """Fake runner that leaves the same artifacts a real build/browser run would."""

    def __init__(self, *, fail_browser_once: bool = False) -> None:
        self.fail_browser_once = fail_browser_once

    def run(self, argv, *, cwd, timeout, env):
        if "build" in argv:
            (cwd / "dist" / "assets").mkdir(parents=True, exist_ok=True)
            (cwd / "dist" / "index.html").write_text("<!doctype html><div id=root></div>\n", encoding="utf-8")
            (cwd / "dist" / "assets" / "index.js").write_text("console.log('built');\n", encoding="utf-8")
        return CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="ok")

    def run_preview_and_browser(self, *, preview_argv, browser_argv, cwd, timeout, env):
        if self.fail_browser_once:
            self.fail_browser_once = False
            raise ExecutionCommandError("command_failed", "The browser check failed safely.")
        (cwd / "test-results").mkdir(exist_ok=True)
        (cwd / "test-results" / "generated-product.png").write_bytes(b"\x89PNG fake screenshot")
        return (
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="preview"),
            CommandResult(exit_code=0, output_bytes=10, duration_seconds=0.01, summary="browser"),
        )


def _executed(tmp_path, runner=None, *, broken_template=False):
    execution_service, project, generated = build_execution_service(tmp_path, runner=runner or ArtifactRunner(), broken_template=broken_template)
    queued = execution_service.create_job(
        project_id=project.project_id, generation_job_id=generated.job_id, actor="user", reason="validate"
    )
    executed = execution_service.run_job(project.project_id, queued.job_id, actor="worker")
    return execution_service, project, generated, executed


def _delivery_service(tmp_path, execution_service, repository=None):
    return ProductDeliveryBundleService(
        execution_service.application,
        repository or InMemoryProductDeliveryBundleRepository(),
        execution_service.generation_repository,
        execution_service.job_repository,
        workspace_root=tmp_path / "workspaces",
        export_root=tmp_path / "exports",
        clock=lambda: NOW,
        id_factory=SequenceIds(),
    )


def test_b6_verified_execution_exports_content_addressed_bundle(tmp_path):
    execution_service, project, generated, executed = _executed(tmp_path)
    assert executed.status == "succeeded"
    service = _delivery_service(tmp_path, execution_service)
    bundle = service.create_bundle(
        project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver"
    )

    archive = service.archive_path(project.project_id, bundle.bundle_id)
    raw = archive.read_bytes()
    assert archive.name == f"{bundle.archive_sha256}.zip"
    assert hashlib.sha256(raw).hexdigest() == bundle.archive_sha256
    assert bundle.execution_job_revision_id == executed.revision_id
    assert bundle.generation_job_revision_id == generated.revision_id
    assert bundle.materialization_kind == "template"
    assert bundle.outcome_evidence_level == "none"
    assert bundle.contract_is_current is True

    with zipfile.ZipFile(io.BytesIO(raw)) as bundle_zip:
        names = bundle_zip.namelist()
        assert names == sorted(names)
        assert set(names) == {item.path for item in bundle.files}
        for item in bundle.files:
            assert hashlib.sha256(bundle_zip.read(item.path)).hexdigest() == item.sha256
        assert {f"source/{item.path}" for item in generated.manifest.files} <= set(names)
        assert "build/index.html" in names
        assert "verification/test-results/generated-product.png" in names
        assert not any("node_modules" in name or name.endswith("package-lock.json") for name in names)
        notes = bundle_zip.read("DELIVERY.md").decode("utf-8")
        assert "## Not verified" in notes
        assert "python -m http.server 4174 --bind 127.0.0.1" in notes
        assert "file://" in notes
        assert executed.revision_id in notes

    duplicate = service.create_bundle(
        project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="click again"
    )
    assert duplicate == bundle
    assert len(service.list_bundles(project.project_id)) == 1

    # A fresh store packing the same execution produces byte-identical output.
    again = _delivery_service(tmp_path, execution_service).create_bundle(
        project_id=project.project_id, execution_job_id=executed.job_id, actor="other", reason="re-export"
    )
    assert again.archive_sha256 == bundle.archive_sha256


def test_b6_rejects_unverified_executions_without_writing(tmp_path):
    execution_service, project, generated = build_execution_service(tmp_path, runner=ArtifactRunner(fail_browser_once=True))
    queued = execution_service.create_job(
        project_id=project.project_id, generation_job_id=generated.job_id, actor="user", reason="validate"
    )
    repository = InMemoryProductDeliveryBundleRepository()
    service = _delivery_service(tmp_path, execution_service, repository)
    with pytest.raises(DomainStateError, match="requires a succeeded execution"):
        service.create_bundle(project_id=project.project_id, execution_job_id=queued.job_id, actor="user", reason="deliver")
    failed = execution_service.run_job(project.project_id, queued.job_id, actor="worker")
    assert failed.status == "failed"
    with pytest.raises(DomainStateError, match="requires a succeeded execution"):
        service.create_bundle(project_id=project.project_id, execution_job_id=failed.job_id, actor="user", reason="deliver")
    with pytest.raises(DomainStateError, match="unknown"):
        service.create_bundle(project_id=project.project_id, execution_job_id="missing", actor="user", reason="deliver")
    assert repository.list_delivery_bundles() == []
    assert not list((tmp_path / "exports").glob("*.zip"))


def test_b6_rejects_tampered_source_missing_build_and_credentials(tmp_path):
    execution_service, project, generated, executed = _executed(tmp_path)
    workspace = tmp_path / "workspaces" / generated.workspace_relative_path
    repository = InMemoryProductDeliveryBundleRepository()
    service = _delivery_service(tmp_path, execution_service, repository)

    (workspace / "dist" / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    with pytest.raises(DomainStateError, match="credential-like"):
        service.create_bundle(project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver")
    (workspace / "dist" / ".env").unlink()

    (workspace / "dist" / "index.html").unlink()
    with pytest.raises(DomainStateError, match="dist/index.html"):
        service.create_bundle(project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver")

    app = workspace / "src" / "App.tsx"
    app.write_text(app.read_text(encoding="utf-8") + "\n// tampered\n", encoding="utf-8")
    with pytest.raises(DomainStateError, match="integrity"):
        service.create_bundle(project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver")
    assert repository.list_delivery_bundles() == []


def test_b6_rejects_symlinked_build_artifact(tmp_path):
    execution_service, project, generated, executed = _executed(tmp_path)
    workspace = tmp_path / "workspaces" / generated.workspace_relative_path
    outside = tmp_path / "outside.txt"
    outside.write_text("not part of the product", encoding="utf-8")
    try:
        (workspace / "dist" / "linked.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this host")
    service = _delivery_service(tmp_path, execution_service)
    with pytest.raises(DomainStateError):
        service.create_bundle(project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver")


def test_b6_repaired_execution_bundle_records_repair_lineage(tmp_path):
    execution_service, project, generated, failed = _executed(tmp_path, ArtifactRunner(fail_browser_once=True), broken_template=True)
    assert failed.status == "failed"
    repair_service = ProductRepairJobService(
        execution_service.application,
        InMemoryProductRepairJobRepository(),
        execution_service.generation_repository,
        execution_service.job_repository,
        execution_service,
        workspace_root=tmp_path / "workspaces",
        clock=lambda: NOW,
        id_factory=SequenceIds(),
    )
    queued = repair_service.create_job(project_id=project.project_id, execution_job_id=failed.job_id, actor="user", reason="repair")
    repaired = repair_service.run_job(project.project_id, queued.job_id, actor="worker")
    assert repaired.status == "succeeded"

    bundle = _delivery_service(tmp_path, execution_service).create_bundle(
        project_id=project.project_id,
        execution_job_id=repaired.latest_execution_job_id,
        actor="user",
        reason="deliver repaired product",
    )
    assert bundle.materialization_kind == "repair"
    assert bundle.parent_generation_job_id == generated.job_id
    assert bundle.repair_job_id == repaired.job_id
    assert bundle.generation_job_id == repaired.latest_generation_job_id


def test_b6_tampered_archive_is_not_served(tmp_path):
    execution_service, project, _, executed = _executed(tmp_path)
    service = _delivery_service(tmp_path, execution_service)
    bundle = service.create_bundle(project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver")
    archive = service.archive_path(project.project_id, bundle.bundle_id)
    archive.write_bytes(archive.read_bytes() + b"tampered")
    with pytest.raises(DomainStateError, match="integrity"):
        service.archive_path(project.project_id, bundle.bundle_id)
    archive.unlink()
    with pytest.raises(DomainStateError, match="unavailable"):
        service.archive_path(project.project_id, bundle.bundle_id)
    with pytest.raises(DomainStateError, match="belongs to project"):
        service.get_bundle("another-project", bundle.bundle_id)


def test_b6_sqlite_bundle_is_insert_only_and_recovers(tmp_path):
    execution_service, project, _, executed = _executed(tmp_path)
    database = tmp_path / "product.sqlite3"
    repository = SQLiteProductRepository(database)
    try:
        bundle = _delivery_service(tmp_path, execution_service, repository).create_bundle(
            project_id=project.project_id, execution_job_id=executed.job_id, actor="user", reason="deliver"
        )
        with pytest.raises(ProductRepositoryError, match="immutable"):
            repository.save_delivery_bundle(bundle)
    finally:
        repository.close()
    reopened = SQLiteProductRepository(database)
    try:
        assert reopened.get_delivery_bundle(bundle.bundle_id) == bundle
        assert reopened.list_delivery_bundles(project_id=project.project_id) == [bundle]
    finally:
        reopened.close()
