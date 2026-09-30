"""B6 delivery bundles for verified Product Studio Web executions.

Export is deliberately a synchronous, single-revision record rather than a
job: packaging a bounded workspace is cheap, and an immutable record keyed by
the pinned execution revision is easier to audit than another lifecycle.  The
zip is content-addressed and byte-deterministic for the same workspace bytes.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.execution import (
    ProductExecutionJobRepository,
    validate_generated_workspace,
)
from psyteardown.product.generation import ProductGenerationJobRepository
from psyteardown.product.models import (
    DELIVERY_BASE_UNVERIFIED_CLAIMS,
    DELIVERY_BUNDLE_FORMAT_VERSION,
    DELIVERY_MAX_BYTES,
    DELIVERY_MAX_FILES,
    DeliveryBundleFile,
    ProductDeliveryBundle,
    ProductExecutionJob,
    ProductGenerationJob,
    WebProductGenerationContract,
)
from psyteardown.product.repositories import ProductRepositoryError


class ProductDeliveryBundleRepository(Protocol):
    def save_delivery_bundle(self, bundle: ProductDeliveryBundle) -> ProductDeliveryBundle: ...

    def get_delivery_bundle(self, bundle_id: str) -> ProductDeliveryBundle | None: ...

    def list_delivery_bundles(
        self, *, project_id: str | None = None
    ) -> list[ProductDeliveryBundle]: ...


class InMemoryProductDeliveryBundleRepository:
    """Insert-only in-memory adapter used by unit tests."""

    def __init__(self) -> None:
        self._bundles: dict[str, ProductDeliveryBundle] = {}

    def save_delivery_bundle(self, bundle: ProductDeliveryBundle) -> ProductDeliveryBundle:
        if bundle.bundle_id in self._bundles:
            raise ProductRepositoryError("delivery bundles are immutable and cannot be overwritten")
        self._bundles[bundle.bundle_id] = bundle
        return bundle

    def get_delivery_bundle(self, bundle_id: str) -> ProductDeliveryBundle | None:
        return self._bundles.get(bundle_id)

    def list_delivery_bundles(self, *, project_id: str | None = None) -> list[ProductDeliveryBundle]:
        return sorted(
            [
                value
                for value in self._bundles.values()
                if project_id is None or value.project_id == project_id
            ],
            key=lambda item: (item.meta.created_at, item.bundle_id),
        )


@dataclass(frozen=True)
class _Entry:
    path: str
    role: str
    data: bytes


# Fixed metadata keeps archives byte-identical across runs and platforms.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_DENIED_NAMES = {".env", ".npmrc", ".netrc", "id_rsa", "id_ed25519"}
_DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


@dataclass(frozen=True)
class DeliveryBundleDiff:
    base: ProductDeliveryBundle
    target: ProductDeliveryBundle
    contract_changes: tuple[str, ...]
    # (path, added|removed|modified|unchanged, base sha256, target sha256)
    files: tuple[tuple[str, str, str | None, str | None], ...]


_CONTRACT_COLLECTIONS = (
    ("screens", "screen_id"),
    ("tasks", "task_id"),
    ("states", "state_id"),
    ("content_slots", "slot_id"),
    ("acceptance_checks", "check_id"),
)


def _contract_changes(base, target) -> list[str]:
    if base is None or target is None:
        return ["contract revision unavailable; contract changes not compared"]
    if base.revision_id == target.revision_id:
        return []
    changes: list[str] = []
    if base.app_title != target.app_title:
        changes.append("app_title changed")
    for field, key in _CONTRACT_COLLECTIONS:
        before = {getattr(item, key): item for item in getattr(base, field)}
        after = {getattr(item, key): item for item in getattr(target, field)}
        changes.extend(f"{field}: added {item}" for item in sorted(after.keys() - before.keys()))
        changes.extend(f"{field}: removed {item}" for item in sorted(before.keys() - after.keys()))
        changes.extend(
            f"{field}: changed {item}"
            for item in sorted(before.keys() & after.keys())
            if before[item] != after[item]
        )
    return changes


class ProductDeliveryBundleService:
    """Package one verified execution into an immutable delivery bundle."""

    def __init__(
        self,
        application,
        bundle_repository: ProductDeliveryBundleRepository,
        generation_repository: ProductGenerationJobRepository,
        execution_repository: ProductExecutionJobRepository,
        *,
        workspace_root: Path | str = Path("output/product-studio/workspaces"),
        export_root: Path | str = Path("output/product-studio/exports"),
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.application = application
        self.bundle_repository = bundle_repository
        self.generation_repository = generation_repository
        self.execution_repository = execution_repository
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._root = self.workspace_root.resolve()
        self.export_root = Path(export_root)
        self.export_root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")

    def create_bundle(
        self,
        *,
        project_id: str,
        execution_job_id: str,
        actor: str,
        reason: str,
    ) -> ProductDeliveryBundle:
        view = self.application.get_project_view(project_id)
        execution = self.execution_repository.get_execution_job(execution_job_id)
        self._check_execution(project_id, execution)
        assert execution is not None
        dependency = DependencyRef(
            object_type="product_execution_job",
            object_id=execution.job_id,
            revision=execution.meta.revision,
        )
        fingerprint = _fingerprint(project_id, dependency)
        existing = next(
            (item for item in self.bundle_repository.list_delivery_bundles(project_id=project_id) if item.fingerprint == fingerprint),
            None,
        )
        if existing:
            return existing
        generation = self.generation_repository.get_generation_job(execution.generation_job_id)
        if (
            generation is None
            or generation.revision_id != execution.generation_job_revision_id
            or generation.status != "succeeded"
            or generation.manifest is None
        ):
            raise DomainStateError("delivery export requires the execution's pinned generation revision to be current")
        workspace = self._workspace_path(execution.workspace_relative_path)
        validate_generated_workspace(workspace, generation)
        contract = view.web_generation_contract
        contract_is_current = contract is not None and contract.revision_id == generation.web_generation_contract_revision_id
        claims = list(DELIVERY_BASE_UNVERIFIED_CLAIMS)
        if generation.materialization_kind == "model":
            claims.append("src/App.tsx and src/styles.css were written by a language model; they passed a static gate and the contract-derived browser test, but no human has reviewed the code.")
        if not contract_is_current:
            claims.append("The Web generation contract has changed since this workspace was generated; this bundle reflects the superseded revision.")
        entries = self._collect_entries(workspace, generation)
        if not any(item.role == "verification" for item in entries):
            claims.append("No browser report or screenshot was found in the workspace; only step summaries are included.")
        entries.append(_Entry("verification/execution-summary.json", "verification", _json_bytes(_execution_summary(execution))))
        entries.append(_Entry("DELIVERY.md", "notes", _delivery_notes(execution, generation, contract if contract_is_current else None, claims).encode("utf-8")))
        files = [_file(item) for item in entries]
        manifest_entry = _Entry(
            "bundle-manifest.json",
            "notes",
            _json_bytes(
                {
                    "format_version": DELIVERY_BUNDLE_FORMAT_VERSION,
                    "project_id": project_id,
                    "execution_job_revision_id": execution.revision_id,
                    "generation_job_revision_id": generation.revision_id,
                    "web_generation_contract_revision_id": generation.web_generation_contract_revision_id,
                    "outcome_evidence_level": "none",
                    "files": [item.model_dump(mode="json") for item in files],
                }
            ),
        )
        entries.append(manifest_entry)
        files.append(_file(manifest_entry))
        total_bytes = sum(item.byte_count for item in files)
        if len(files) > DELIVERY_MAX_FILES or total_bytes > DELIVERY_MAX_BYTES:
            raise DomainStateError("delivery export exceeds the bundle file or byte budget")
        archive = _zip_bytes(entries)
        archive_sha256 = hashlib.sha256(archive).hexdigest()
        self._store_archive(archive_sha256, archive)
        bundle_id = self._id("delivery-bundle")
        bundle = ProductDeliveryBundle(
            bundle_id=bundle_id,
            revision_id=f"{bundle_id}.r1",
            meta=RevisionMeta(revision=1, created_at=self._now(), created_by=actor, reason=reason),
            project_id=project_id,
            input_dependencies=(dependency,),
            execution_job_id=execution.job_id,
            execution_job_revision_id=execution.revision_id,
            generation_job_id=generation.job_id,
            generation_job_revision_id=generation.revision_id,
            web_generation_contract_revision_id=generation.web_generation_contract_revision_id,
            contract_is_current=contract_is_current,
            materialization_kind=generation.materialization_kind,
            parent_generation_job_id=generation.parent_generation_job_id,
            repair_job_id=generation.repair_job_id,
            template_version=generation.manifest.template_version,
            verification_steps=execution.steps,
            files=tuple(files),
            total_bytes=total_bytes,
            archive_sha256=archive_sha256,
            archive_bytes=len(archive),
            unverified_claims=tuple(claims),
            fingerprint=fingerprint,
        )
        return self.bundle_repository.save_delivery_bundle(bundle)

    def get_bundle(self, project_id: str, bundle_id: str) -> ProductDeliveryBundle:
        bundle = self.bundle_repository.get_delivery_bundle(bundle_id)
        if bundle is None:
            raise DomainStateError(f"unknown product delivery bundle: {bundle_id}")
        if bundle.project_id != project_id:
            raise DomainStateError(f"product delivery bundle belongs to project {bundle.project_id}, not {project_id}")
        return bundle

    def list_bundles(self, project_id: str) -> tuple[ProductDeliveryBundle, ...]:
        self.application.get_project_view(project_id)
        return tuple(self.bundle_repository.list_delivery_bundles(project_id=project_id))

    def diff_bundles(self, project_id: str, base_bundle_id: str, target_bundle_id: str) -> "DeliveryBundleDiff":
        """Compare two recorded deliveries by manifest hashes (B8, PS-O015).

        Only recorded sha256 values are compared: no archive is re-read and no
        line-level or semantic diff is claimed.
        """

        base = self.get_bundle(project_id, base_bundle_id)
        target = self.get_bundle(project_id, target_bundle_id)
        base_files = {item.path: item.sha256 for item in base.files}
        target_files = {item.path: item.sha256 for item in target.files}
        files = []
        for path in sorted(base_files.keys() | target_files.keys()):
            before, after = base_files.get(path), target_files.get(path)
            change = (
                "added" if before is None
                else "removed" if after is None
                else "unchanged" if before == after
                else "modified"
            )
            files.append((path, change, before, after))
        base_contract = self.application.repository.get_revision(
            "web_generation_contract", base.web_generation_contract_revision_id
        )
        target_contract = self.application.repository.get_revision(
            "web_generation_contract", target.web_generation_contract_revision_id
        )
        return DeliveryBundleDiff(
            base=base,
            target=target,
            contract_changes=tuple(_contract_changes(base_contract, target_contract)),
            files=tuple(files),
        )

    def archive_path(self, project_id: str, bundle_id: str) -> Path:
        """Return the stored archive only if its bytes still match the record."""

        bundle = self.get_bundle(project_id, bundle_id)
        path = self.export_root / f"{bundle.archive_sha256}.zip"
        if not path.is_file() or path.is_symlink():
            raise DomainStateError("delivery archive is unavailable; export the verified execution again")
        raw = path.read_bytes()
        if len(raw) != bundle.archive_bytes or hashlib.sha256(raw).hexdigest() != bundle.archive_sha256:
            raise DomainStateError("delivery archive failed integrity validation")
        return path

    def _check_execution(self, project_id: str, execution: ProductExecutionJob | None) -> None:
        if execution is None:
            raise DomainStateError("unknown product execution job")
        if execution.project_id != project_id:
            raise DomainStateError("product execution job belongs to another project")
        if execution.status != "succeeded" or any(step.status != "succeeded" for step in execution.steps):
            raise DomainStateError("delivery export requires a succeeded execution job")

    def _collect_entries(self, workspace: Path, generation: ProductGenerationJob) -> list[_Entry]:
        assert generation.manifest is not None
        entries = [
            _Entry(f"source/{item.path}", "source", (workspace / item.path).read_bytes())
            for item in sorted(generation.manifest.files, key=lambda value: value.path)
        ]
        build_root = workspace / "dist"
        if not (build_root / "index.html").is_file():
            raise DomainStateError("delivery export requires a built dist/index.html artifact")
        entries.extend(_tree_entries(build_root, "build/", "build", workspace))
        report_root = workspace / "test-results"
        if report_root.is_dir():
            entries.extend(_tree_entries(report_root, "verification/test-results/", "verification", workspace))
        return entries

    def _store_archive(self, archive_sha256: str, archive: bytes) -> None:
        target = self.export_root / f"{archive_sha256}.zip"
        if target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest() == archive_sha256:
            return
        handle, temporary = tempfile.mkstemp(prefix=".bundle-", suffix=".zip", dir=self.export_root)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(archive)
            os.replace(temporary, target)
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def _workspace_path(self, relative: str) -> Path:
        candidate = (self._root / relative).resolve(strict=False)
        try:
            if os.path.commonpath((str(self._root), str(candidate))) != str(self._root):
                raise ValueError
        except ValueError as exc:
            raise DomainStateError("delivery workspace is outside the configured root") from exc
        return candidate

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("delivery identifier cannot be empty")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("delivery clock must be timezone-aware")
        return value


def _tree_entries(root: Path, prefix: str, role: str, workspace: Path) -> list[_Entry]:
    if root.is_symlink():
        raise DomainStateError("delivery export rejected a symbolic link in the workspace")
    entries: list[_Entry] = []
    resolved_workspace = workspace.resolve()
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if path.is_symlink():
            raise DomainStateError("delivery export rejected a symbolic link in the workspace")
        if not path.is_file():
            continue
        if os.path.commonpath((str(resolved_workspace), str(path.resolve()))) != str(resolved_workspace):
            raise DomainStateError("delivery export rejected a path outside the workspace")
        name = path.name.lower()
        if name in _DENIED_NAMES or name.startswith(".env") or name.endswith(_DENIED_SUFFIXES):
            raise DomainStateError("delivery export rejected a credential-like file")
        entries.append(_Entry(prefix + path.relative_to(root).as_posix(), role, path.read_bytes()))
        if len(entries) > DELIVERY_MAX_FILES:
            raise DomainStateError("delivery export exceeds the bundle file or byte budget")
    return entries


def _file(entry: _Entry) -> DeliveryBundleFile:
    return DeliveryBundleFile(
        path=entry.path,
        role=entry.role,  # type: ignore[arg-type]
        byte_count=len(entry.data),
        sha256=hashlib.sha256(entry.data).hexdigest(),
    )


def _zip_bytes(entries: list[_Entry]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for entry in sorted(entries, key=lambda item: item.path):
            info = zipfile.ZipInfo(entry.path, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entry.data)
    return buffer.getvalue()


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _execution_summary(execution: ProductExecutionJob) -> dict[str, object]:
    return {
        "execution_job_revision_id": execution.revision_id,
        "provider": execution.provider,
        "provider_version": execution.provider_version,
        "sandbox": execution.sandbox.model_dump(mode="json"),
        "steps": [
            {"name": step.name, "status": step.status, "exit_code": step.exit_code, "summary": step.summary}
            for step in execution.steps
        ],
        "raw_logs_retained": False,
    }


def _delivery_notes(
    execution: ProductExecutionJob,
    generation: ProductGenerationJob,
    contract: WebProductGenerationContract | None,
    claims: list[str],
) -> str:
    # Notes intentionally omit actor, time and bundle id so identical inputs
    # produce identical archives.
    lines = ["# Delivery bundle", ""]
    if contract is not None:
        lines += [f"Product: {contract.app_title}", "", "## Key tasks", ""]
        lines += [f"- {task.goal} — success when: {task.success_criteria}" for task in contract.tasks]
        lines.append("")
    lines += [
        "## Provenance",
        "",
        f"- Web generation contract: `{generation.web_generation_contract_revision_id}`",
        f"- Generation: `{generation.revision_id}` ({generation.materialization_kind})",
    ]
    if generation.materialization_kind == "model":
        for call in generation.model_calls:
            lines.append(f"- Model call {call.attempt}: {call.provider} `{call.model}` — {call.outcome} (request sha256 `{call.request_sha256[:12]}`); only the confirmed Web contract was sent")
    if generation.materialization_kind == "repair":
        lines.append(f"- Repaired from generation `{generation.parent_generation_job_id}` by repair job `{generation.repair_job_id}`")
    lines += [
        f"- Execution: `{execution.revision_id}` ({execution.provider} {execution.provider_version})",
        "",
        "## Contents",
        "",
        "- `source/` — generated source, byte-identical to the generation manifest",
        "- `build/` — production build produced during execution",
        "- `verification/` — browser report artifacts and the safe execution step summary",
        "- `bundle-manifest.json` — sha256 of every other file in this bundle",
        "",
        "## Use the delivered interaction locally",
        "",
        "The recommended path is to serve the already verified static build; no npm install is needed:",
        "",
        "```powershell",
        "# From the folder that contains the downloaded zip",
        r"Expand-Archive .\<bundle>.zip -DestinationPath .\<bundle>",
        r"Set-Location .\<bundle>\build",
        "python -m http.server 4174 --bind 127.0.0.1",
        "# Open http://127.0.0.1:4174/ in a browser; press Ctrl+C to stop",
        "```",
        "",
        "Do not double-click `build/index.html` or open it with a `file://` URL; browser module and asset loading is not the verified local path.",
        "",
        "The Product Studio workbench preview is the path for submitting feedback. The downloaded build is a standalone interaction artifact; it does not send feedback back to Product Studio.",
        "",
        "## Optional: rebuild from source",
        "",
        "Use this only when developing the generated source, not when merely trying the delivered interaction:",
        "",
        "```powershell",
        r"Set-Location .\<bundle>\source",
        "npm install --ignore-scripts",
        "npm run build",
        "npm run preview -- --host 127.0.0.1 --port 4174",
        "```",
        "",
        "## What was verified",
        "",
    ]
    lines += [f"- {step.name}: {step.status}" + (f" — {step.summary}" if step.summary else "") for step in execution.steps]
    lines += ["", "## Not verified", ""]
    lines += [f"- {claim}" for claim in claims]
    return "\n".join(lines) + "\n"


def _fingerprint(project_id: str, dependency: DependencyRef) -> str:
    payload = {
        "project_id": project_id,
        "dependency": dependency.model_dump(mode="json"),
        "format_version": DELIVERY_BUNDLE_FORMAT_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
