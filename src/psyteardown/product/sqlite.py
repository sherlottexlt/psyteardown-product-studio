"""SQLite persistence adapter for Product Studio upper-domain revisions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TypeVar

from psyteardown.experience.models import AuditEvent, DomainEvent
from psyteardown.product.jobs import _validate_job_revision
from psyteardown.product.generation import _validate_generation_job_revision
from psyteardown.product.execution import _validate_execution_job_revision
from psyteardown.product.repair import _validate_repair_job_revision
from psyteardown.product.models import PreviewFeedback, ProductDeliveryBundle, ProductExecutionJob, ProductGenerationJob, ProductProposalJob, ProductRepairJob, RevisionImpact
from psyteardown.product.repositories import (
    ProductRepositoryError,
    ProductSnapshot,
    _stable_id,
    impact_key,
    model_for,
    validate_revision_chain,
    validate_snapshot_type,
)


T = TypeVar("T", bound=ProductSnapshot)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_revisions (
    object_type TEXT NOT NULL,
    project_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    parent_revision_id TEXT,
    object_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (object_type, revision_id),
    UNIQUE (object_type, object_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_product_revisions_project
    ON product_revisions (project_id, object_type, object_id, revision);
CREATE TABLE IF NOT EXISTS product_current (
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    PRIMARY KEY (object_type, object_id),
    FOREIGN KEY (object_type, revision_id)
      REFERENCES product_revisions (object_type, revision_id)
);
CREATE INDEX IF NOT EXISTS idx_product_current_project
    ON product_current (project_id, object_type, object_id);
CREATE TABLE IF NOT EXISTS product_domain_events (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_revision_id TEXT NOT NULL,
    event_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_domain_events_project
    ON product_domain_events (project_id, aggregate_id, aggregate_revision_id);
CREATE TABLE IF NOT EXISTS product_audit_events (
    audit_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_revision_id TEXT NOT NULL,
    audit_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_audit_events_project
    ON product_audit_events (project_id, target_id, target_revision_id);
CREATE TABLE IF NOT EXISTS product_revision_impacts (
    project_id TEXT NOT NULL,
    changed_object_type TEXT NOT NULL,
    changed_object_id TEXT NOT NULL,
    changed_revision INTEGER NOT NULL,
    dependent_type TEXT NOT NULL,
    dependent_id TEXT NOT NULL,
    dependent_revision_id TEXT NOT NULL,
    impact_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (
      changed_object_type, changed_object_id, changed_revision,
      dependent_type, dependent_id, dependent_revision_id
    )
);
CREATE INDEX IF NOT EXISTS idx_product_impacts_project
    ON product_revision_impacts (project_id, dependent_type, dependent_id);
CREATE TABLE IF NOT EXISTS product_job_revisions (
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    revision_id TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    job_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, revision),
    UNIQUE (revision_id)
);
CREATE INDEX IF NOT EXISTS idx_product_jobs_project
    ON product_job_revisions (project_id, job_id, revision);
CREATE INDEX IF NOT EXISTS idx_product_jobs_fingerprint
    ON product_job_revisions (project_id, fingerprint, revision);
CREATE TABLE IF NOT EXISTS product_job_current (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    FOREIGN KEY (job_id, revision)
      REFERENCES product_job_revisions (job_id, revision)
);
CREATE TABLE IF NOT EXISTS product_generation_job_revisions (
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    revision_id TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    job_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, revision),
    UNIQUE (revision_id)
);
CREATE INDEX IF NOT EXISTS idx_product_generation_jobs_project
    ON product_generation_job_revisions (project_id, job_id, revision);
CREATE INDEX IF NOT EXISTS idx_product_generation_jobs_fingerprint
    ON product_generation_job_revisions (project_id, fingerprint, revision);
CREATE TABLE IF NOT EXISTS product_generation_job_current (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    FOREIGN KEY (job_id, revision)
      REFERENCES product_generation_job_revisions (job_id, revision)
);
CREATE TABLE IF NOT EXISTS product_execution_job_revisions (
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    revision_id TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    job_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, revision),
    UNIQUE (revision_id)
);
CREATE INDEX IF NOT EXISTS idx_product_execution_jobs_project
    ON product_execution_job_revisions (project_id, job_id, revision);
CREATE INDEX IF NOT EXISTS idx_product_execution_jobs_fingerprint
    ON product_execution_job_revisions (project_id, fingerprint, revision);
CREATE TABLE IF NOT EXISTS product_execution_job_current (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    FOREIGN KEY (job_id, revision)
      REFERENCES product_execution_job_revisions (job_id, revision)
);
CREATE TABLE IF NOT EXISTS product_repair_job_revisions (
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    revision_id TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    job_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, revision),
    UNIQUE (revision_id)
);
CREATE INDEX IF NOT EXISTS idx_product_repair_jobs_project
    ON product_repair_job_revisions (project_id, job_id, revision);
CREATE INDEX IF NOT EXISTS idx_product_repair_jobs_fingerprint
    ON product_repair_job_revisions (project_id, fingerprint, revision);
CREATE TABLE IF NOT EXISTS product_repair_job_current (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    FOREIGN KEY (job_id, revision)
      REFERENCES product_repair_job_revisions (job_id, revision)
);
CREATE TABLE IF NOT EXISTS product_delivery_bundles (
    bundle_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    execution_job_revision_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    archive_sha256 TEXT NOT NULL,
    bundle_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_product_delivery_bundles_project
    ON product_delivery_bundles (project_id, created_at, bundle_id);
-- One row per feedback: withdrawal overwrites the row with a tombstone so the
-- erased text is not kept as an older revision (PS-O007).
CREATE TABLE IF NOT EXISTS product_preview_feedback (
    feedback_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    feedback_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_preview_feedback_project
    ON product_preview_feedback (project_id, bundle_id, submitted_at, feedback_id);
"""


class SQLiteProductRepository:
    """Product repository with command-level SQLite transactions."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        # Withdrawn preview feedback must not survive in freed pages.
        self._conn.execute("PRAGMA secure_delete = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SQLiteProductRepository":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_revision(self, object_type: str, revision_id: str) -> T | None:
        model = model_for(object_type)
        row = self._conn.execute(
            "SELECT object_json FROM product_revisions "
            "WHERE object_type = ? AND revision_id = ?",
            (object_type, revision_id),
        ).fetchone()
        return model.model_validate_json(row[0]) if row else None  # type: ignore[return-value]

    def get_current(self, object_type: str, object_id: str) -> T | None:
        model_for(object_type)
        row = self._conn.execute(
            "SELECT revision_id FROM product_current "
            "WHERE object_type = ? AND object_id = ?",
            (object_type, object_id),
        ).fetchone()
        return self.get_revision(object_type, row[0]) if row else None

    def list_current(
        self, object_type: str, *, project_id: str | None = None
    ) -> list[T]:
        model = model_for(object_type)
        if project_id is None:
            rows = self._conn.execute(
                "SELECT r.object_json FROM product_current c "
                "JOIN product_revisions r ON r.object_type=c.object_type "
                "AND r.revision_id=c.revision_id "
                "WHERE c.object_type=? ORDER BY c.object_id",
                (object_type,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT r.object_json FROM product_current c "
                "JOIN product_revisions r ON r.object_type=c.object_type "
                "AND r.revision_id=c.revision_id "
                "WHERE c.object_type=? AND c.project_id=? ORDER BY c.object_id",
                (object_type, project_id),
            ).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]  # type: ignore[return-value]

    def list_revisions(self, object_type: str, object_id: str) -> list[T]:
        model = model_for(object_type)
        rows = self._conn.execute(
            "SELECT object_json FROM product_revisions "
            "WHERE object_type=? AND object_id=? ORDER BY revision",
            (object_type, object_id),
        ).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]  # type: ignore[return-value]

    def current_revision_id(self, object_type: str, object_id: str) -> str | None:
        model_for(object_type)
        row = self._conn.execute(
            "SELECT revision_id FROM product_current "
            "WHERE object_type=? AND object_id=?",
            (object_type, object_id),
        ).fetchone()
        return row[0] if row else None

    def list_impacts(
        self, *, project_id: str | None = None
    ) -> list[RevisionImpact]:
        if project_id is None:
            rows = self._conn.execute(
                "SELECT impact_json FROM product_revision_impacts ORDER BY rowid"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT impact_json FROM product_revision_impacts "
                "WHERE project_id=? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [RevisionImpact.model_validate_json(row[0]) for row in rows]

    @property
    def domain_events(self) -> list[DomainEvent]:
        rows = self._conn.execute(
            "SELECT event_json FROM product_domain_events ORDER BY rowid"
        ).fetchall()
        return [DomainEvent.model_validate_json(row[0]) for row in rows]

    @property
    def audit_events(self) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT audit_json FROM product_audit_events ORDER BY rowid"
        ).fetchall()
        return [AuditEvent.model_validate_json(row[0]) for row in rows]

    def get_job(self, job_id: str) -> ProductProposalJob | None:
        row = self._conn.execute(
            "SELECT r.job_json FROM product_job_current c "
            "JOIN product_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision WHERE c.job_id=?",
            (job_id,),
        ).fetchone()
        return ProductProposalJob.model_validate_json(row[0]) if row else None

    def list_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductProposalJob]:
        if project_id is None:
            rows = self._conn.execute(
                "SELECT r.job_json FROM product_job_current c "
                "JOIN product_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision ORDER BY r.created_at, r.job_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT r.job_json FROM product_job_current c "
                "JOIN product_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision WHERE c.project_id=? "
                "ORDER BY r.created_at, r.job_id",
                (project_id,),
            ).fetchall()
        return [ProductProposalJob.model_validate_json(row[0]) for row in rows]

    def save_job(
        self,
        job: ProductProposalJob,
        *,
        expected_revision: int | None,
    ) -> ProductProposalJob:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT r.job_json FROM product_job_current c "
                "JOIN product_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision WHERE c.job_id=?",
                (job.job_id,),
            ).fetchone()
            current = ProductProposalJob.model_validate_json(row[0]) if row else None
            _validate_job_revision(current, job, expected_revision)
            self._conn.execute(
                "INSERT INTO product_job_revisions "
                "(job_id,project_id,revision,revision_id,status,fingerprint,job_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    job.job_id,
                    job.project_id,
                    job.meta.revision,
                    job.revision_id,
                    job.status,
                    job.fingerprint,
                    job.model_dump_json(),
                    job.meta.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO product_job_current (job_id,project_id,revision) "
                "VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
                "project_id=excluded.project_id,revision=excluded.revision",
                (job.job_id, job.project_id, job.meta.revision),
            )
            self._conn.commit()
        except ProductRepositoryError:
            self._conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "atomic proposal job revision failed; transaction rolled back"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return job

    def get_generation_job(self, job_id: str) -> ProductGenerationJob | None:
        row = self._conn.execute(
            "SELECT r.job_json FROM product_generation_job_current c "
            "JOIN product_generation_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision WHERE c.job_id=?",
            (job_id,),
        ).fetchone()
        return ProductGenerationJob.model_validate_json(row[0]) if row else None

    def get_generation_job_revision(self, job_id: str, revision_id: str) -> ProductGenerationJob | None:
        row = self._conn.execute(
            "SELECT job_json FROM product_generation_job_revisions WHERE job_id=? AND revision_id=?",
            (job_id, revision_id),
        ).fetchone()
        return ProductGenerationJob.model_validate_json(row[0]) if row else None

    def get_generation_job_revision(self, job_id: str, revision_id: str) -> ProductGenerationJob | None:
        row = self._conn.execute(
            "SELECT job_json FROM product_generation_job_revisions WHERE job_id=? AND revision_id=?",
            (job_id, revision_id),
        ).fetchone()
        return ProductGenerationJob.model_validate_json(row[0]) if row else None

    def list_generation_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductGenerationJob]:
        query = (
            "SELECT r.job_json FROM product_generation_job_current c "
            "JOIN product_generation_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision"
        )
        params: tuple[object, ...] = ()
        if project_id is not None:
            query += " WHERE c.project_id=?"
            params = (project_id,)
        query += " ORDER BY r.created_at, r.job_id"
        rows = self._conn.execute(query, params).fetchall()
        return [ProductGenerationJob.model_validate_json(row[0]) for row in rows]

    def save_generation_job(
        self,
        job: ProductGenerationJob,
        *,
        expected_revision: int | None,
    ) -> ProductGenerationJob:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT r.job_json FROM product_generation_job_current c "
                "JOIN product_generation_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision WHERE c.job_id=?",
                (job.job_id,),
            ).fetchone()
            current = ProductGenerationJob.model_validate_json(row[0]) if row else None
            _validate_generation_job_revision(current, job, expected_revision)
            self._conn.execute(
                "INSERT INTO product_generation_job_revisions "
                "(job_id,project_id,revision,revision_id,status,fingerprint,job_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    job.job_id,
                    job.project_id,
                    job.meta.revision,
                    job.revision_id,
                    job.status,
                    job.fingerprint,
                    job.model_dump_json(),
                    job.meta.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO product_generation_job_current (job_id,project_id,revision) "
                "VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
                "project_id=excluded.project_id,revision=excluded.revision",
                (job.job_id, job.project_id, job.meta.revision),
            )
            self._conn.commit()
        except ProductRepositoryError:
            self._conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "atomic generation job revision failed; transaction rolled back"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return job

    def get_execution_job(self, job_id: str) -> ProductExecutionJob | None:
        row = self._conn.execute(
            "SELECT r.job_json FROM product_execution_job_current c "
            "JOIN product_execution_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision WHERE c.job_id=?",
            (job_id,),
        ).fetchone()
        return ProductExecutionJob.model_validate_json(row[0]) if row else None

    def list_execution_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductExecutionJob]:
        query = (
            "SELECT r.job_json FROM product_execution_job_current c "
            "JOIN product_execution_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision"
        )
        params: tuple[object, ...] = ()
        if project_id is not None:
            query += " WHERE c.project_id=?"
            params = (project_id,)
        query += " ORDER BY r.created_at, r.job_id"
        rows = self._conn.execute(query, params).fetchall()
        return [ProductExecutionJob.model_validate_json(row[0]) for row in rows]

    def save_execution_job(
        self,
        job: ProductExecutionJob,
        *,
        expected_revision: int | None,
    ) -> ProductExecutionJob:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT r.job_json FROM product_execution_job_current c "
                "JOIN product_execution_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision WHERE c.job_id=?",
                (job.job_id,),
            ).fetchone()
            current = ProductExecutionJob.model_validate_json(row[0]) if row else None
            _validate_execution_job_revision(current, job, expected_revision)
            self._conn.execute(
                "INSERT INTO product_execution_job_revisions "
                "(job_id,project_id,revision,revision_id,status,fingerprint,job_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    job.job_id,
                    job.project_id,
                    job.meta.revision,
                    job.revision_id,
                    job.status,
                    job.fingerprint,
                    job.model_dump_json(),
                    job.meta.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO product_execution_job_current (job_id,project_id,revision) "
                "VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
                "project_id=excluded.project_id,revision=excluded.revision",
                (job.job_id, job.project_id, job.meta.revision),
            )
            self._conn.commit()
        except ProductRepositoryError:
            self._conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "atomic execution job revision failed; transaction rolled back"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return job

    def get_repair_job(self, job_id: str) -> ProductRepairJob | None:
        row = self._conn.execute(
            "SELECT r.job_json FROM product_repair_job_current c "
            "JOIN product_repair_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision WHERE c.job_id=?",
            (job_id,),
        ).fetchone()
        return ProductRepairJob.model_validate_json(row[0]) if row else None

    def list_repair_jobs(
        self, *, project_id: str | None = None
    ) -> list[ProductRepairJob]:
        query = (
            "SELECT r.job_json FROM product_repair_job_current c "
            "JOIN product_repair_job_revisions r ON r.job_id=c.job_id "
            "AND r.revision=c.revision"
        )
        params: tuple[object, ...] = ()
        if project_id is not None:
            query += " WHERE c.project_id=?"
            params = (project_id,)
        query += " ORDER BY r.created_at, r.job_id"
        rows = self._conn.execute(query, params).fetchall()
        return [ProductRepairJob.model_validate_json(row[0]) for row in rows]

    def save_repair_job(
        self,
        job: ProductRepairJob,
        *,
        expected_revision: int | None,
    ) -> ProductRepairJob:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT r.job_json FROM product_repair_job_current c "
                "JOIN product_repair_job_revisions r ON r.job_id=c.job_id "
                "AND r.revision=c.revision WHERE c.job_id=?",
                (job.job_id,),
            ).fetchone()
            current = ProductRepairJob.model_validate_json(row[0]) if row else None
            _validate_repair_job_revision(current, job, expected_revision)
            self._conn.execute(
                "INSERT INTO product_repair_job_revisions "
                "(job_id,project_id,revision,revision_id,status,fingerprint,job_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    job.job_id,
                    job.project_id,
                    job.meta.revision,
                    job.revision_id,
                    job.status,
                    job.fingerprint,
                    job.model_dump_json(),
                    job.meta.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO product_repair_job_current (job_id,project_id,revision) "
                "VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
                "project_id=excluded.project_id,revision=excluded.revision",
                (job.job_id, job.project_id, job.meta.revision),
            )
            self._conn.commit()
        except ProductRepositoryError:
            self._conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "atomic repair job revision failed; transaction rolled back"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return job

    def get_delivery_bundle(self, bundle_id: str) -> ProductDeliveryBundle | None:
        row = self._conn.execute(
            "SELECT bundle_json FROM product_delivery_bundles WHERE bundle_id=?",
            (bundle_id,),
        ).fetchone()
        return ProductDeliveryBundle.model_validate_json(row[0]) if row else None

    def list_delivery_bundles(
        self, *, project_id: str | None = None
    ) -> list[ProductDeliveryBundle]:
        query = "SELECT bundle_json FROM product_delivery_bundles"
        params: tuple[object, ...] = ()
        if project_id is not None:
            query += " WHERE project_id=?"
            params = (project_id,)
        query += " ORDER BY created_at, bundle_id"
        rows = self._conn.execute(query, params).fetchall()
        return [ProductDeliveryBundle.model_validate_json(row[0]) for row in rows]

    def save_delivery_bundle(self, bundle: ProductDeliveryBundle) -> ProductDeliveryBundle:
        # Insert-only: the primary key and (project, fingerprint) uniqueness
        # make an overwrite or a duplicate export fail atomically.
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO product_delivery_bundles "
                "(bundle_id,project_id,execution_job_revision_id,fingerprint,archive_sha256,bundle_json,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    bundle.bundle_id,
                    bundle.project_id,
                    bundle.execution_job_revision_id,
                    bundle.fingerprint,
                    bundle.archive_sha256,
                    bundle.model_dump_json(),
                    bundle.meta.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "delivery bundles are immutable and cannot be overwritten"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return bundle

    def get_preview_feedback(self, feedback_id: str) -> PreviewFeedback | None:
        row = self._conn.execute(
            "SELECT feedback_json FROM product_preview_feedback WHERE feedback_id=?",
            (feedback_id,),
        ).fetchone()
        return PreviewFeedback.model_validate_json(row[0]) if row else None

    def list_preview_feedback(
        self, *, project_id: str | None = None, bundle_id: str | None = None
    ) -> list[PreviewFeedback]:
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if bundle_id is not None:
            clauses.append("bundle_id=?")
            params.append(bundle_id)
        query = "SELECT feedback_json FROM product_preview_feedback"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY submitted_at, feedback_id"
        rows = self._conn.execute(query, tuple(params)).fetchall()
        return [PreviewFeedback.model_validate_json(row[0]) for row in rows]

    def save_preview_feedback(
        self, feedback: PreviewFeedback, *, expected_revision: int | None
    ) -> PreviewFeedback:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if expected_revision is None:
                if feedback.meta.revision != 1:
                    raise ProductRepositoryError("first preview feedback revision must be revision 1")
                self._conn.execute(
                    "INSERT INTO product_preview_feedback "
                    "(feedback_id,project_id,bundle_id,revision,feedback_json,submitted_at) VALUES (?,?,?,?,?,?)",
                    (
                        feedback.feedback_id,
                        feedback.project_id,
                        feedback.delivery_bundle_id,
                        feedback.meta.revision,
                        feedback.model_dump_json(),
                        feedback.submitted_at.isoformat(),
                    ),
                )
            else:
                row = self._conn.execute(
                    "SELECT feedback_json FROM product_preview_feedback WHERE feedback_id=?",
                    (feedback.feedback_id,),
                ).fetchone()
                current = PreviewFeedback.model_validate_json(row[0]) if row else None
                if current is None or current.meta.revision != expected_revision:
                    raise ProductRepositoryError(
                        f"revision conflict: expected {expected_revision}, "
                        f"current {current.meta.revision if current else None}"
                    )
                if (
                    feedback.meta.revision != current.meta.revision + 1
                    or feedback.meta.parent_revision_id != current.revision_id
                ):
                    raise ProductRepositoryError("preview feedback revision must follow the current revision")
                self._conn.execute(
                    "UPDATE product_preview_feedback SET revision=?, feedback_json=? "
                    "WHERE feedback_id=? AND revision=?",
                    (feedback.meta.revision, feedback.model_dump_json(), feedback.feedback_id, expected_revision),
                )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError("preview feedback already exists") from exc
        except Exception:
            self._conn.rollback()
            raise
        return feedback

    def save_command(
        self,
        object_type: str,
        object_id: str,
        revision_id: str,
        value: T,
        *,
        project_id: str,
        expected_revision: int | None,
        domain_events: tuple[DomainEvent, ...] = (),
        audit_events: tuple[AuditEvent, ...] = (),
        impacts: tuple[RevisionImpact, ...] = (),
    ) -> T:
        validate_snapshot_type(object_type, value, project_id=project_id)
        if revision_id != value.revision_id:
            raise ProductRepositoryError("revision_id does not match snapshot")
        if object_id != _stable_id(value):
            raise ProductRepositoryError("object_id does not match snapshot stable identity")

        try:
            self._conn.execute("BEGIN IMMEDIATE")
            current_row = self._conn.execute(
                "SELECT r.object_json FROM product_current c "
                "JOIN product_revisions r ON r.object_type=c.object_type "
                "AND r.revision_id=c.revision_id "
                "WHERE c.object_type=? AND c.object_id=?",
                (object_type, object_id),
            ).fetchone()
            current = (
                model_for(object_type).model_validate_json(current_row[0])
                if current_row
                else None
            )
            validate_revision_chain(
                current, value, expected_revision=expected_revision
            )
            self._conn.execute(
                "INSERT INTO product_revisions "
                "(object_type,project_id,object_id,revision_id,revision,parent_revision_id,object_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    object_type,
                    project_id,
                    object_id,
                    revision_id,
                    value.meta.revision,
                    value.meta.parent_revision_id,
                    value.model_dump_json(),
                    value.meta.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO product_current (object_type,object_id,project_id,revision_id) "
                "VALUES (?,?,?,?) ON CONFLICT(object_type,object_id) DO UPDATE SET "
                "project_id=excluded.project_id,revision_id=excluded.revision_id",
                (object_type, object_id, project_id, revision_id),
            )
            for event in domain_events:
                self._conn.execute(
                    "INSERT INTO product_domain_events "
                    "(event_id,project_id,event_type,aggregate_id,aggregate_revision_id,event_json) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        event.event_id,
                        project_id,
                        event.event_type,
                        event.aggregate_id,
                        event.aggregate_revision_id,
                        event.model_dump_json(),
                    ),
                )
            for event in audit_events:
                self._conn.execute(
                    "INSERT INTO product_audit_events "
                    "(audit_id,project_id,action,target_id,target_revision_id,audit_json) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        event.audit_id,
                        project_id,
                        event.action,
                        event.target_id,
                        event.target_revision_id,
                        event.model_dump_json(),
                    ),
                )
            for impact in impacts:
                changed_type, changed_id, changed_revision, dependent_type, dependent_id, dependent_revision_id = impact_key(impact)
                self._conn.execute(
                    "INSERT INTO product_revision_impacts "
                    "(project_id,changed_object_type,changed_object_id,changed_revision,"
                    "dependent_type,dependent_id,dependent_revision_id,impact_json,recorded_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        changed_type,
                        changed_id,
                        changed_revision,
                        dependent_type,
                        dependent_id,
                        dependent_revision_id,
                        impact.model_dump_json(),
                        value.meta.created_at.isoformat(),
                    ),
                )
            self._conn.commit()
        except ProductRepositoryError:
            self._conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise ProductRepositoryError(
                "atomic product command failed; transaction rolled back"
            ) from exc
        except Exception:
            self._conn.rollback()
            raise
        return value
