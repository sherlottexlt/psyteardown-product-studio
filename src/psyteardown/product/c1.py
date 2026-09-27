"""C1 manual outcome-observation intake for the first Product Studio slice.

C1 intentionally owns a Product-side intake boundary. It does not write the
legacy Experience research tables or collect runtime telemetry. Every trial
record is pinned to the confirmed C2 plan and a verified B6 delivery revision.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol, TypeAlias
from uuid import uuid4

from pydantic import Field, model_validator

from psyteardown.experience.models import (
    DomainStateError,
    FrozenModel,
    Identifier,
    RevisionMeta,
    ScalarValue,
)
from psyteardown.experience.multimodal import is_named_human_actor
from psyteardown.product.measurement import measurement_plan_blockers
from psyteardown.product.models import (
    MEASUREMENT_LAYER_CEILINGS,
    OutcomeMeasurementPlan,
    ProductDeliveryBundle,
)
from psyteardown.product.repositories import ProductRepositoryError


C1_CONSENT_POLICY_REVISION = "c1-local-v1"
C1_CONSENT_STATEMENT = (
    "This local, host-led trial records only a random participant ID and the structured "
    "task results entered by the host. It does not collect names, contact details, employer, "
    "keyboard or mouse activity, notifications, screen recordings, screenshots, telemetry, "
    "or participant raw text, and it never sends trial data to a model. Access is limited to "
    "the local host and the named human reviewer. You may stop or withdraw at any time without "
    "penalty; withdrawal erases this participant's source records and excludes them from review."
)
C1_ACCESS_POLICY: tuple[str, ...] = ("local_host", "named_reviewer")
C1_DATA_CATEGORIES: tuple[str, ...] = (
    "random_participant_id",
    "structured_task_measure_value",
    "task_completion_status",
    "manual_observation_timestamp",
)
C1_RETENTION_DAYS = 30
C1_RETENTION_PERIOD = timedelta(days=C1_RETENTION_DAYS)
C1_RETENTION_POLICY = (
    "Source records are retained locally for at most 30 days after envelope close; "
    "no anonymous aggregate is retained in C1."
)
C1_WITHDRAWAL_POLICY = (
    "Withdrawal immediately erases the participant receipt, presentations, observations "
    "and reviews, then leaves only a content-free tombstone."
)
C1_SOURCE_LAYER = "research_observation"
C1_EVIDENCE_CEILING = MEASUREMENT_LAYER_CEILINGS[C1_SOURCE_LAYER]
C1_TRIAL_PAUSED_MESSAGE = "C1 真实任务验证当前暂缓；先完成本地工作流风险复核。"
_C1_REVIEWER_PLACEHOLDERS = frozenset({"named-reviewer", "reviewer", "local-reviewer", "your-name", "填写 reviewer"})

C1ObservationStatus = Literal[
    "observed",
    "participant_withdrawal",
    "task_abandonment",
    "technical_failure",
    "skipped_by_protocol",
    "no_response",
    "not_applicable",
    "unknown",
]
C1EvidenceLevel = Literal["none", "exploratory", "observed", "supported", "replicated"]


class C1TrialEnvelope(FrozenModel):
    envelope_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    status: Literal["active", "closed", "stopped"] = "active"
    closed_at: datetime | None = None
    retention_expires_at: datetime | None = None
    close_reason: Identifier | None = None
    measurement_plan_revision_id: Identifier
    delivery_bundle_id: Identifier
    delivery_bundle_revision_id: Identifier
    execution_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    host: Identifier
    consent_policy_revision: Identifier = C1_CONSENT_POLICY_REVISION
    consent_statement: Identifier = C1_CONSENT_STATEMENT
    access_policy: tuple[Identifier, ...] = C1_ACCESS_POLICY
    data_categories: tuple[Identifier, ...] = C1_DATA_CATEGORIES
    retention_policy: Identifier = C1_RETENTION_POLICY
    withdrawal_policy: Identifier = C1_WITHDRAWAL_POLICY

    @model_validator(mode="after")
    def validate_shape(self) -> "C1TrialEnvelope":
        if self.meta.revision != 1 or self.revision_id != f"{self.envelope_id}.r1":
            raise ValueError("C1 trial envelopes are immutable single-revision pins")
        if self.consent_policy_revision != C1_CONSENT_POLICY_REVISION:
            raise ValueError("unsupported C1 consent policy revision")
        if self.access_policy != C1_ACCESS_POLICY:
            raise ValueError("C1 access policy cannot be widened by intake data")
        if self.status == "active" and (self.closed_at is not None or self.retention_expires_at is not None):
            raise ValueError("active C1 trial envelopes cannot have close timestamps")
        if self.status != "active":
            if self.closed_at is None or self.retention_expires_at is None:
                raise ValueError("closed C1 trial envelopes require retention timestamps")
            if self.retention_expires_at != self.closed_at + C1_RETENTION_PERIOD:
                raise ValueError("C1 retention expiry must be 30 days after envelope close")
        return self


@dataclass(frozen=True)
class C1RetentionCleanupResult:
    envelope_ids: tuple[str, ...] = ()
    deleted_receipts: int = 0
    deleted_participants: int = 0
    deleted_presentations: int = 0
    deleted_observations: int = 0
    deleted_reviews: int = 0

    @property
    def deleted_source_records(self) -> int:
        return (
            self.deleted_receipts
            + self.deleted_participants
            + self.deleted_presentations
            + self.deleted_observations
            + self.deleted_reviews
        )


class C1ConsentReceipt(FrozenModel):
    receipt_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    participant_id: Identifier
    policy_revision: Identifier
    scope: Identifier
    data_categories: tuple[Identifier, ...] = C1_DATA_CATEGORIES
    access_policy: tuple[Identifier, ...] = C1_ACCESS_POLICY
    retention_policy: Identifier = C1_RETENTION_POLICY
    withdrawal_policy: Identifier = C1_WITHDRAWAL_POLICY
    consented_by: Identifier
    granted_at: datetime
    status: Literal["granted"] = "granted"

    @model_validator(mode="after")
    def validate_receipt(self) -> "C1ConsentReceipt":
        if self.meta.revision != 1 or self.revision_id != f"{self.receipt_id}.r1":
            raise ValueError("C1 consent receipts are immutable single-revision records")
        if self.policy_revision != C1_CONSENT_POLICY_REVISION:
            raise ValueError("unsupported C1 consent policy revision")
        if self.data_categories != C1_DATA_CATEGORIES or self.access_policy != C1_ACCESS_POLICY:
            raise ValueError("C1 consent receipt must use the approved data boundary")
        return self


class C1Participant(FrozenModel):
    participant_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    consent_receipt_id: Identifier
    consent_receipt_revision_id: Identifier
    status: Literal["active", "withdrawn"] = "active"
    enrolled_at: datetime
    withdrawn_at: datetime | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "C1Participant":
        if self.meta.revision != 1 or self.revision_id != f"{self.participant_id}.r1":
            raise ValueError("C1 participant revisions are single-revision records")
        if self.status == "active" and self.withdrawn_at is not None:
            raise ValueError("active C1 participant cannot have withdrawn_at")
        if self.status == "withdrawn" and self.withdrawn_at is None:
            raise ValueError("withdrawn C1 participant requires withdrawn_at")
        return self


class C1TaskPresentation(FrozenModel):
    presentation_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    participant_id: Identifier
    task_id: Identifier
    consent_receipt_revision_id: Identifier
    delivery_bundle_id: Identifier
    delivery_bundle_revision_id: Identifier
    execution_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    status: Literal["presented", "completed", "withdrawn"] = "presented"
    started_at: datetime
    ended_at: datetime | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "C1TaskPresentation":
        if self.meta.revision != 1 or self.revision_id != f"{self.presentation_id}.r1":
            raise ValueError("C1 task presentations are immutable single-revision records")
        if self.status == "withdrawn" and self.ended_at is None:
            raise ValueError("withdrawn C1 presentation requires ended_at")
        return self


class C1OutcomeObservation(FrozenModel):
    observation_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    participant_id: Identifier
    presentation_id: Identifier
    measurement_plan_revision_id: Identifier
    measure_id: Identifier
    source_layer: Literal["research_observation"] = C1_SOURCE_LAYER
    value: ScalarValue | None = None
    status: C1ObservationStatus = "observed"
    completion_cause: str | None = None
    consent_receipt_revision_id: Identifier
    delivery_bundle_id: Identifier
    delivery_bundle_revision_id: Identifier
    execution_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    recorded_by: Identifier
    recorded_at: datetime
    evidence_refs: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_value_boundary(self) -> "C1OutcomeObservation":
        if self.status == "observed" and self.value is None:
            raise ValueError("an observed C1 outcome requires a structured value")
        if self.status != "observed" and self.value is not None:
            raise ValueError("non-observed C1 outcomes cannot carry a value")
        if self.meta.revision != 1 or self.revision_id != f"{self.observation_id}.r1":
            raise ValueError("C1 observations are immutable single-revision records")
        return self


class C1EvidenceReview(FrozenModel):
    review_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    observation_ids: tuple[Identifier, ...] = Field(min_length=1)
    measurement_plan_revision_id: Identifier
    delivery_bundle_revision_id: Identifier
    execution_job_revision_id: Identifier
    web_generation_contract_revision_id: Identifier
    source_layer: Literal["research_observation"] = C1_SOURCE_LAYER
    reviewer: Identifier
    decision: Literal["accepted", "modified", "rejected", "insufficient"]
    evidence_level_before: C1EvidenceLevel = "none"
    evidence_level_after: C1EvidenceLevel = "none"
    rationale: Identifier
    limitations: tuple[Identifier, ...] = ()
    reviewed_at: datetime

    @model_validator(mode="after")
    def validate_review(self) -> "C1EvidenceReview":
        if not is_named_human_actor(self.reviewer):
            raise ValueError("C1 EvidenceReview requires a named human reviewer")
        if self.meta.revision != 1 or self.revision_id != f"{self.review_id}.r1":
            raise ValueError("C1 EvidenceReviews are immutable single-revision records")
        if self.evidence_level_after not in {"none", "exploratory", "observed"}:
            raise ValueError("C1 research observations cannot be promoted above observed")
        if self.decision in {"accepted", "modified"} and self.evidence_level_after == "none":
            raise ValueError("an accepting C1 review must declare a non-none evidence level")
        if self.decision in {"rejected", "insufficient"} and self.evidence_level_after != "none":
            raise ValueError("a non-accepting C1 review cannot promote evidence")
        return self


class C1WithdrawalTombstone(FrozenModel):
    tombstone_id: Identifier
    revision_id: Identifier
    meta: RevisionMeta
    project_id: Identifier
    envelope_id: Identifier
    participant_digest: Identifier
    consent_policy_revision: Identifier = C1_CONSENT_POLICY_REVISION
    deleted_receipts: int = Field(ge=0)
    deleted_presentations: int = Field(ge=0)
    deleted_observations: int = Field(ge=0)
    deleted_reviews: int = Field(ge=0)
    withdrawn_at: datetime

    @model_validator(mode="after")
    def validate_tombstone(self) -> "C1WithdrawalTombstone":
        if self.meta.revision != 1 or self.revision_id != f"{self.tombstone_id}.r1":
            raise ValueError("C1 withdrawal tombstones are immutable single-revision records")
        if len(self.participant_digest) != 64:
            raise ValueError("C1 tombstone participant digest must be sha256")
        return self


C1Record: TypeAlias = (
    C1TrialEnvelope
    | C1ConsentReceipt
    | C1Participant
    | C1TaskPresentation
    | C1OutcomeObservation
    | C1EvidenceReview
)
_C1_MODELS: dict[str, type[FrozenModel]] = {
    "c1_trial_envelope": C1TrialEnvelope,
    "c1_consent_receipt": C1ConsentReceipt,
    "c1_participant": C1Participant,
    "c1_task_presentation": C1TaskPresentation,
    "c1_outcome_observation": C1OutcomeObservation,
    "c1_evidence_review": C1EvidenceReview,
    "c1_withdrawal_tombstone": C1WithdrawalTombstone,
}


class C1Repository(Protocol):
    def save_c1_batch(self, values: tuple[FrozenModel, ...]) -> None: ...

    def get_c1_current(self, object_type: str, object_id: str) -> FrozenModel | None: ...

    def list_c1(self, object_type: str, *, project_id: str | None = None) -> list[FrozenModel]: ...

    def withdraw_c1_participant(
        self,
        *,
        project_id: str,
        envelope_id: str,
        participant_id: str,
        tombstone: C1WithdrawalTombstone,
    ) -> C1WithdrawalTombstone: ...

    def list_tombstones(self, *, project_id: str | None = None) -> list[C1WithdrawalTombstone]: ...

    def transition_c1_envelope(
        self,
        *,
        project_id: str,
        envelope_id: str,
        status: Literal["closed", "stopped"],
        closed_at: datetime,
        close_reason: str,
        actor: str,
    ) -> C1TrialEnvelope: ...

    def cleanup_c1_retention(self, *, now: datetime) -> C1RetentionCleanupResult: ...

    def close(self) -> None: ...


class InMemoryC1Repository:
    """Atomic C1 store used by local application and domain tests."""

    def __init__(self) -> None:
        self._objects: dict[str, dict[str, FrozenModel]] = defaultdict(dict)
        self._current: dict[tuple[str, str], str] = {}
        self._tombstones: dict[str, C1WithdrawalTombstone] = {}

    def save_c1_batch(self, values: tuple[FrozenModel, ...]) -> None:
        pending: list[tuple[str, str, FrozenModel]] = []
        for value in values:
            object_type, object_id = _c1_identity(value)
            model = _C1_MODELS.get(object_type)
            if model is None or not isinstance(value, model):
                raise ProductRepositoryError(f"unsupported C1 object type: {object_type}")
            if self._get_current(object_type, object_id) is not None:
                raise ProductRepositoryError(f"C1 object already exists: {object_id}")
            if value.revision_id in self._objects[object_type]:
                raise ProductRepositoryError(f"C1 revision already exists: {value.revision_id}")
            pending.append((object_type, object_id, value))
        for object_type, object_id, value in pending:
            self._objects[object_type][value.revision_id] = value
            self._current[(object_type, object_id)] = value.revision_id

    def _get_current(self, object_type: str, object_id: str) -> FrozenModel | None:
        revision_id = self._current.get((object_type, object_id))
        return self._objects.get(object_type, {}).get(revision_id) if revision_id else None

    def get_c1_current(self, object_type: str, object_id: str) -> FrozenModel | None:
        return self._get_current(object_type, object_id)

    def list_c1(self, object_type: str, *, project_id: str | None = None) -> list[FrozenModel]:
        values = [
            value
            for (kind, object_id) in self._current
            if kind == object_type
            for value in (self._get_current(kind, object_id),)
            if value is not None
        ]
        if project_id is not None:
            values = [value for value in values if getattr(value, "project_id", None) == project_id]
        return sorted(values, key=lambda value: (value.meta.created_at, _c1_identity(value)[1]))

    def withdraw_c1_participant(
        self,
        *,
        project_id: str,
        envelope_id: str,
        participant_id: str,
        tombstone: C1WithdrawalTombstone,
    ) -> C1WithdrawalTombstone:
        if tombstone.tombstone_id in self._tombstones:
            raise ProductRepositoryError("C1 withdrawal tombstone already exists")
        observation_ids = {
            value.observation_id
            for value in self.list_c1("c1_outcome_observation", project_id=project_id)
            if isinstance(value, C1OutcomeObservation)
            and value.envelope_id == envelope_id
            and value.participant_id == participant_id
        }
        delete_ids: dict[str, set[str]] = defaultdict(set)
        for object_type in ("c1_consent_receipt", "c1_participant", "c1_task_presentation", "c1_outcome_observation", "c1_evidence_review"):
            for value in self.list_c1(object_type, project_id=project_id):
                if getattr(value, "envelope_id", None) != envelope_id:
                    continue
                if getattr(value, "participant_id", None) == participant_id or (
                    isinstance(value, C1EvidenceReview)
                    and observation_ids.intersection(value.observation_ids)
                ):
                    delete_ids[object_type].add(_c1_identity(value)[1])
        for object_type, object_ids in delete_ids.items():
            for object_id in object_ids:
                value = self._get_current(object_type, object_id)
                if value is None:
                    continue
                self._objects[object_type].pop(value.revision_id, None)
                self._current.pop((object_type, object_id), None)
        self._tombstones[tombstone.tombstone_id] = tombstone
        return tombstone

    def list_tombstones(self, *, project_id: str | None = None) -> list[C1WithdrawalTombstone]:
        values = list(self._tombstones.values())
        if project_id is not None:
            values = [value for value in values if value.project_id == project_id]
        return sorted(values, key=lambda value: (value.withdrawn_at, value.tombstone_id))

    def transition_c1_envelope(
        self,
        *,
        project_id: str,
        envelope_id: str,
        status: Literal["closed", "stopped"],
        closed_at: datetime,
        close_reason: str,
        actor: str,
    ) -> C1TrialEnvelope:
        current = self.get_c1_current("c1_trial_envelope", envelope_id)
        if not isinstance(current, C1TrialEnvelope) or current.project_id != project_id:
            raise DomainStateError(f"unknown C1 trial envelope: {envelope_id}")
        if current.status != "active":
            raise DomainStateError("C1 trial envelope is already closed")
        updated = C1TrialEnvelope.model_validate({
            **current.model_dump(mode="python"),
            "status": status,
            "closed_at": closed_at,
            "retention_expires_at": closed_at + C1_RETENTION_PERIOD,
            "close_reason": close_reason,
        })
        self._objects["c1_trial_envelope"][updated.revision_id] = updated
        self._current[("c1_trial_envelope", envelope_id)] = updated.revision_id
        return updated

    def cleanup_c1_retention(self, *, now: datetime) -> C1RetentionCleanupResult:
        expired = [
            item for item in self.list_c1("c1_trial_envelope")
            if isinstance(item, C1TrialEnvelope)
            and item.status != "active"
            and item.retention_expires_at is not None
            and item.retention_expires_at <= now
        ]
        counts = defaultdict(int)
        for envelope in expired:
            for object_type in (
                "c1_consent_receipt",
                "c1_participant",
                "c1_task_presentation",
                "c1_outcome_observation",
                "c1_evidence_review",
            ):
                for value in list(self.list_c1(object_type, project_id=envelope.project_id)):
                    if getattr(value, "envelope_id", None) != envelope.envelope_id:
                        continue
                    _, object_id = _c1_identity(value)
                    self._objects[object_type].pop(value.revision_id, None)
                    self._current.pop((object_type, object_id), None)
                    counts[object_type] += 1
        return C1RetentionCleanupResult(
            envelope_ids=tuple(item.envelope_id for item in expired),
            deleted_receipts=counts["c1_consent_receipt"],
            deleted_participants=counts["c1_participant"],
            deleted_presentations=counts["c1_task_presentation"],
            deleted_observations=counts["c1_outcome_observation"],
            deleted_reviews=counts["c1_evidence_review"],
        )

    def close(self) -> None:
        return None


def _c1_identity(value: FrozenModel) -> tuple[str, str]:
    if isinstance(value, C1TrialEnvelope):
        return "c1_trial_envelope", value.envelope_id
    if isinstance(value, C1ConsentReceipt):
        return "c1_consent_receipt", value.receipt_id
    if isinstance(value, C1Participant):
        return "c1_participant", value.participant_id
    if isinstance(value, C1TaskPresentation):
        return "c1_task_presentation", value.presentation_id
    if isinstance(value, C1OutcomeObservation):
        return "c1_outcome_observation", value.observation_id
    if isinstance(value, C1EvidenceReview):
        return "c1_evidence_review", value.review_id
    if isinstance(value, C1WithdrawalTombstone):
        return "c1_withdrawal_tombstone", value.tombstone_id
    raise ProductRepositoryError(f"unsupported C1 snapshot type: {type(value).__name__}")


def _validate_measure_value(measure, value: ScalarValue | None) -> None:
    if value is None:
        return
    valid = {
        "boolean": isinstance(value, bool),
        "count": isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        "duration_seconds": isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0,
        "ordinal_1_5": isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5,
        "categorical": isinstance(value, str),
        "free_text": isinstance(value, str),
    }[measure.value_kind]
    if not valid:
        raise DomainStateError(f"value does not match measure {measure.measure_id} value_kind {measure.value_kind}")


def _validate_delivery_pin(
    bundle: ProductDeliveryBundle,
    execution_revision_id: str,
    contract_revision_id: str,
    current_contract,
) -> None:
    if bundle.execution_job_revision_id != execution_revision_id:
        raise DomainStateError("C1 execution revision does not match the delivered bundle")
    if bundle.web_generation_contract_revision_id != contract_revision_id:
        raise DomainStateError("C1 Web contract revision does not match the delivered bundle")
    if not bundle.contract_is_current or current_contract is None or current_contract.revision_id != contract_revision_id:
        raise DomainStateError("C1 requires a delivered bundle built from the current Web generation contract")
    if tuple(step.status for step in bundle.verification_steps) != ("succeeded", "succeeded", "succeeded", "succeeded"):
        raise DomainStateError("C1 requires a fully verified B6 delivery bundle")



class SQLiteC1Repository:
    """Local C1 store with atomic commands and hard-delete withdrawal.

    C1 uses dedicated tables in the Product Studio SQLite file; it never writes
    the unrelated Experience experiment tables. Source records are not revision
    archived, so withdrawal physically deletes their rows before adding a
    content-free, non-participant-specific tombstone.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=5)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA secure_delete = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS c1_records (
              object_type TEXT NOT NULL, object_id TEXT NOT NULL,
              project_id TEXT NOT NULL, envelope_id TEXT NOT NULL,
              revision_id TEXT NOT NULL UNIQUE, object_json TEXT NOT NULL,
              PRIMARY KEY (object_type, object_id)
            );
            CREATE INDEX IF NOT EXISTS idx_c1_records_project
              ON c1_records(project_id, envelope_id, object_type);
            CREATE TABLE IF NOT EXISTS c1_withdrawal_tombstones (
              tombstone_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              envelope_id TEXT NOT NULL, tombstone_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS c1_audit_events (
              audit_id TEXT PRIMARY KEY, action TEXT NOT NULL,
              project_id TEXT NOT NULL, envelope_id TEXT NOT NULL,
              actor TEXT NOT NULL, occurred_at TEXT NOT NULL, details_json TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_c1_batch(self, values: tuple[FrozenModel, ...]) -> None:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            for value in values:
                object_type, object_id = _c1_identity(value)
                if not isinstance(value, _C1_MODELS[object_type]):
                    raise ProductRepositoryError(f"unsupported C1 object type: {object_type}")
                if value.meta.revision != 1:
                    raise ProductRepositoryError("C1 records are immutable single-revision records")
                envelope_id = getattr(value, "envelope_id", object_id)
                self._conn.execute(
                    "INSERT INTO c1_records VALUES(?,?,?,?,?,?)",
                    (object_type, object_id, value.project_id, envelope_id, value.revision_id, value.model_dump_json()),
                )
                self._audit(value, object_type, object_id)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _audit(self, value: FrozenModel, object_type: str, object_id: str) -> None:
        actor = getattr(value, "recorded_by", None) or getattr(value, "reviewer", None) or getattr(value, "consented_by", None) or value.meta.created_by
        action = object_type.removeprefix("c1_") + "_created"
        self._conn.execute(
            "INSERT INTO c1_audit_events VALUES(?,?,?,?,?,?,?)",
            (f"audit:{value.revision_id}", action, value.project_id,
             getattr(value, "envelope_id", object_id), actor,
             value.meta.created_at.isoformat(), __import__("json").dumps({"object_type": object_type}, sort_keys=True)),
        )

    def get_c1_current(self, object_type: str, object_id: str) -> FrozenModel | None:
        model = _C1_MODELS.get(object_type)
        if model is None:
            raise ProductRepositoryError(f"unsupported C1 object type: {object_type}")
        row = self._conn.execute(
            "SELECT object_json FROM c1_records WHERE object_type=? AND object_id=?",
            (object_type, object_id),
        ).fetchone()
        return model.model_validate_json(row[0]) if row else None

    def list_c1(self, object_type: str, *, project_id: str | None = None) -> list[FrozenModel]:
        model = _C1_MODELS.get(object_type)
        if model is None:
            raise ProductRepositoryError(f"unsupported C1 object type: {object_type}")
        query = "SELECT object_json FROM c1_records WHERE object_type=?"
        params: tuple[object, ...] = (object_type,)
        if project_id is not None:
            query += " AND project_id=?"
            params += (project_id,)
        query += " ORDER BY rowid"
        return [model.model_validate_json(row[0]) for row in self._conn.execute(query, params)]

    def withdraw_c1_participant(
        self, *, project_id: str, envelope_id: str, participant_id: str,
        tombstone: C1WithdrawalTombstone,
    ) -> C1WithdrawalTombstone:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            rows = self._conn.execute(
                "SELECT object_type,object_id,object_json FROM c1_records WHERE project_id=? AND envelope_id=?",
                (project_id, envelope_id),
            ).fetchall()
            decoded = [(kind, object_id, _C1_MODELS[kind].model_validate_json(payload)) for kind, object_id, payload in rows]
            participant_observations = {
                item.observation_id for kind, _, item in decoded
                if kind == "c1_outcome_observation" and item.participant_id == participant_id
            }
            delete_keys = set()
            counts = defaultdict(int)
            for kind, object_id, item in decoded:
                belongs = getattr(item, "participant_id", None) == participant_id
                related_review = kind == "c1_evidence_review" and bool(participant_observations.intersection(item.observation_ids))
                if belongs or related_review:
                    delete_keys.add((kind, object_id))
                    counts[kind] += 1
            # Participant and receipt contain the cross-reference required to
            # authorize withdrawal; fail closed if either is absent.
            if ("c1_participant", participant_id) not in delete_keys:
                raise DomainStateError("active participant record is not available for withdrawal")
            delete_revisions = [item.revision_id for kind, object_id, item in decoded if (kind, object_id) in delete_keys]
            self._conn.executemany(
                "DELETE FROM c1_records WHERE object_type=? AND object_id=?",
                tuple(delete_keys),
            )
            self._conn.executemany(
                "DELETE FROM c1_audit_events WHERE audit_id=?",
                tuple((f"audit:{revision_id}",) for revision_id in delete_revisions),
            )
            self._conn.execute(
                "INSERT INTO c1_withdrawal_tombstones VALUES(?,?,?,?)",
                (tombstone.tombstone_id, project_id, envelope_id, tombstone.model_dump_json()),
            )
            details = {"deleted_records": dict(counts), "withdrawal_tombstone_id": tombstone.tombstone_id}
            self._conn.execute(
                "INSERT INTO c1_audit_events VALUES(?,?,?,?,?,?,?)",
                (f"audit:{tombstone.revision_id}", "participant_withdrawn_and_source_erased",
                 project_id, envelope_id, tombstone.meta.created_by,
                 tombstone.withdrawn_at.isoformat(), __import__("json").dumps(details, sort_keys=True)),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        # The configured journal mode is DELETE by default. If an operator has
        # switched to WAL, checkpoint/truncate now; no backup erasure is claimed.
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.DatabaseError:
            pass
        return tombstone

    def list_tombstones(self, *, project_id: str | None = None) -> list[C1WithdrawalTombstone]:
        query = "SELECT tombstone_json FROM c1_withdrawal_tombstones"
        params: tuple[object, ...] = ()
        if project_id is not None:
            query += " WHERE project_id=?"
            params = (project_id,)
        query += " ORDER BY rowid"
        return [C1WithdrawalTombstone.model_validate_json(row[0]) for row in self._conn.execute(query, params)]

    def transition_c1_envelope(
        self,
        *,
        project_id: str,
        envelope_id: str,
        status: Literal["closed", "stopped"],
        closed_at: datetime,
        close_reason: str,
        actor: str,
    ) -> C1TrialEnvelope:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT object_json FROM c1_records WHERE object_type=? AND object_id=? AND project_id=?",
                ("c1_trial_envelope", envelope_id, project_id),
            ).fetchone()
            current = C1TrialEnvelope.model_validate_json(row[0]) if row else None
            if current is None:
                raise DomainStateError(f"unknown C1 trial envelope: {envelope_id}")
            if current.status != "active":
                raise DomainStateError("C1 trial envelope is already closed")
            updated = C1TrialEnvelope.model_validate({
                **current.model_dump(mode="python"),
                "status": status,
                "closed_at": closed_at,
                "retention_expires_at": closed_at + C1_RETENTION_PERIOD,
                "close_reason": close_reason,
            })
            self._conn.execute(
                "UPDATE c1_records SET object_json=? WHERE object_type=? AND object_id=?",
                (updated.model_dump_json(), "c1_trial_envelope", envelope_id),
            )
            self._conn.execute(
                "INSERT INTO c1_audit_events VALUES(?,?,?,?,?,?,?)",
                (
                    f"audit:{envelope_id}:{status}",
                    f"envelope_{status}",
                    project_id,
                    envelope_id,
                    actor,
                    closed_at.isoformat(),
                    __import__("json").dumps({"status": status, "retention_expires_at": updated.retention_expires_at.isoformat()}, sort_keys=True),
                ),
            )
            self._conn.commit()
            return updated
        except Exception:
            self._conn.rollback()
            raise

    def cleanup_c1_retention(self, *, now: datetime) -> C1RetentionCleanupResult:
        envelopes = [
            item for item in self.list_c1("c1_trial_envelope")
            if isinstance(item, C1TrialEnvelope)
            and item.status != "active"
            and item.retention_expires_at is not None
            and item.retention_expires_at <= now
        ]
        counts = defaultdict(int)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            for envelope in envelopes:
                rows = self._conn.execute(
                    "SELECT object_type,object_id,revision_id FROM c1_records WHERE project_id=? AND envelope_id=? AND object_type<>?",
                    (envelope.project_id, envelope.envelope_id, "c1_trial_envelope"),
                ).fetchall()
                if not rows:
                    continue
                self._conn.executemany(
                    "DELETE FROM c1_records WHERE object_type=? AND object_id=?",
                    tuple((kind, object_id) for kind, object_id, _ in rows),
                )
                self._conn.executemany(
                    "DELETE FROM c1_audit_events WHERE audit_id=?",
                    tuple((f"audit:{revision_id}",) for _, _, revision_id in rows),
                )
                for kind, _, _ in rows:
                    counts[kind] += 1
                self._conn.execute(
                    "INSERT OR IGNORE INTO c1_audit_events VALUES(?,?,?,?,?,?,?)",
                    (
                        f"retention:{envelope.envelope_id}",
                        "c1_retention_cleanup",
                        envelope.project_id,
                        envelope.envelope_id,
                        "local-retention",
                        now.isoformat(),
                        __import__("json").dumps({"deleted_source_records": len(rows)}, sort_keys=True),
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return C1RetentionCleanupResult(
            envelope_ids=tuple(item.envelope_id for item in envelopes),
            deleted_receipts=counts["c1_consent_receipt"],
            deleted_participants=counts["c1_participant"],
            deleted_presentations=counts["c1_task_presentation"],
            deleted_observations=counts["c1_outcome_observation"],
            deleted_reviews=counts["c1_evidence_review"],
        )


def _c1_meta(service, actor: str, reason: str) -> RevisionMeta:
    return RevisionMeta(revision=1, created_at=service._now(), created_by=actor, reason=reason)


class ProductC1ObservationService:
    """Application commands for local, manually hosted C1 task trials."""

    def __init__(self, application, delivery_service, repository: C1Repository, *,
                 clock: Callable[[], datetime] | None = None,
                 id_factory: Callable[[str], str] | None = None,
                 trial_enabled: bool = False):
        self.application = application
        self.delivery_service = delivery_service
        self.repository = repository
        self.trial_enabled = trial_enabled
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}-{uuid4().hex}")
        self.cleanup_retention()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("C1 clock must be timezone-aware")
        return value

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("C1 identifier factory returned an empty identifier")
        return value

    def start_envelope(self, *, project_id: str, measurement_plan_revision_id: str,
                       delivery_bundle_id: str, execution_job_revision_id: str,
                       web_generation_contract_revision_id: str, host: str,
                       actor: str, reason: str) -> C1TrialEnvelope:
        if not self.trial_enabled:
            raise DomainStateError(C1_TRIAL_PAUSED_MESSAGE)
        if not is_named_human_actor(host) or not is_named_human_actor(actor):
            raise DomainStateError("C1 trial envelope requires a named human host")
        view = self.application.get_project_view(project_id)
        plan = view.outcome_measurement_plan
        if plan is None or plan.revision_id != measurement_plan_revision_id or plan.status != "confirmed":
            raise DomainStateError("C1 requires the current confirmed OutcomeMeasurementPlan revision")
        blockers = measurement_plan_blockers(plan, view.outcome_contract)
        if blockers:
            raise DomainStateError("C1 measurement plan is not operational")
        bundle = self.delivery_service.get_bundle(project_id, delivery_bundle_id)
        _validate_delivery_pin(bundle, execution_job_revision_id, web_generation_contract_revision_id, view.web_generation_contract)
        envelope_id = self._id("c1-envelope")
        now = self._now()
        envelope = C1TrialEnvelope(
            envelope_id=envelope_id, revision_id=f"{envelope_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, measurement_plan_revision_id=plan.revision_id,
            delivery_bundle_id=bundle.bundle_id, delivery_bundle_revision_id=bundle.revision_id,
            execution_job_revision_id=execution_job_revision_id,
            web_generation_contract_revision_id=web_generation_contract_revision_id, host=host,
        )
        self.repository.save_c1_batch((envelope,))
        return envelope

    def cleanup_retention(self) -> C1RetentionCleanupResult:
        """Delete expired C1 source records in the local store.

        Cleanup is run on service construction and before envelope reads. This is
        deliberately local and deterministic; it is not a hosted retention worker.
        """
        return self.repository.cleanup_c1_retention(now=self._now())

    def _transition_envelope(
        self,
        *,
        project_id: str,
        envelope_id: str,
        status: Literal["closed", "stopped"],
        actor: str,
        reason: str,
    ) -> C1TrialEnvelope:
        envelope = self.get_envelope(project_id, envelope_id, active=True)
        if not is_named_human_actor(actor):
            raise DomainStateError("C1 envelope close/stop requires a named human host")
        if not reason.strip():
            raise DomainStateError("C1 envelope close/stop requires a reason")
        return self.repository.transition_c1_envelope(
            project_id=project_id,
            envelope_id=envelope.envelope_id,
            status=status,
            closed_at=self._now(),
            close_reason=reason,
            actor=actor,
        )

    def close_envelope(self, *, project_id: str, envelope_id: str, actor: str, reason: str) -> C1TrialEnvelope:
        return self._transition_envelope(project_id=project_id, envelope_id=envelope_id, status="closed", actor=actor, reason=reason)

    def stop_envelope(self, *, project_id: str, envelope_id: str, actor: str, reason: str) -> C1TrialEnvelope:
        return self._transition_envelope(project_id=project_id, envelope_id=envelope_id, status="stopped", actor=actor, reason=reason)

    def list_envelopes(self, project_id: str) -> tuple[C1TrialEnvelope, ...]:
        self.cleanup_retention()
        self.application.get_project_view(project_id)
        return tuple(item for item in self.repository.list_c1("c1_trial_envelope", project_id=project_id) if isinstance(item, C1TrialEnvelope))

    def get_envelope(self, project_id: str, envelope_id: str, *, active: bool = False) -> C1TrialEnvelope:
        self.cleanup_retention()
        value = self.repository.get_c1_current("c1_trial_envelope", envelope_id)
        if not isinstance(value, C1TrialEnvelope) or value.project_id != project_id:
            raise DomainStateError(f"unknown C1 trial envelope: {envelope_id}")
        if active and value.status != "active":
            raise DomainStateError("C1 trial envelope is not active")
        return value

    def enroll_participant(self, *, project_id: str, envelope_id: str,
                           consent_policy_revision: str, consent_scope_acknowledged: bool,
                           actor: str, reason: str) -> tuple[C1Participant, C1ConsentReceipt]:
        envelope = self.get_envelope(project_id, envelope_id, active=True)
        if not is_named_human_actor(actor):
            raise DomainStateError("C1 consent receipt requires a named human host")
        if consent_policy_revision != envelope.consent_policy_revision:
            raise DomainStateError("C1 consent policy revision is stale or unsupported")
        if not consent_scope_acknowledged:
            raise DomainStateError("C1 requires explicit participant consent acknowledgement")
        now = self._now()
        participant_id = self._id("participant")
        receipt_id = self._id("consent")
        receipt = C1ConsentReceipt(
            receipt_id=receipt_id, revision_id=f"{receipt_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, envelope_id=envelope_id, participant_id=participant_id,
            policy_revision=envelope.consent_policy_revision, scope=envelope.consent_statement,
            consented_by=actor, granted_at=now,
        )
        participant = C1Participant(
            participant_id=participant_id, revision_id=f"{participant_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, envelope_id=envelope_id,
            consent_receipt_id=receipt_id, consent_receipt_revision_id=receipt.revision_id,
            enrolled_at=now,
        )
        self.repository.save_c1_batch((receipt, participant))
        return participant, receipt

    def list_participants(self, project_id: str, envelope_id: str) -> tuple[C1Participant, ...]:
        self.get_envelope(project_id, envelope_id)
        return tuple(
            item for item in self.repository.list_c1("c1_participant", project_id=project_id)
            if isinstance(item, C1Participant) and item.envelope_id == envelope_id
        )

    def present_task(self, *, project_id: str, envelope_id: str,
                     participant_id: str, task_id: str, actor: str, reason: str) -> C1TaskPresentation:
        envelope = self.get_envelope(project_id, envelope_id, active=True)
        participant = self._participant(project_id, participant_id)
        if participant.envelope_id != envelope_id or participant.status != "active":
            raise DomainStateError("task presentation requires an active participant")
        receipt = self.repository.get_c1_current("c1_consent_receipt", participant.consent_receipt_id)
        if not isinstance(receipt, C1ConsentReceipt) or receipt.revision_id != participant.consent_receipt_revision_id:
            raise DomainStateError("task presentation requires a current consent receipt")
        view = self.application.get_project_view(project_id)
        contract = view.web_generation_contract
        if contract is None or contract.revision_id != envelope.web_generation_contract_revision_id:
            raise DomainStateError("C1 Web contract pin is stale")
        if task_id not in {task.task_id for task in contract.tasks}:
            raise DomainStateError("task is not part of the pinned Web contract")
        if not is_named_human_actor(actor):
            raise DomainStateError("C1 task presentation requires a named human host")
        now = self._now()
        presentation_id = self._id("presentation")
        value = C1TaskPresentation(
            presentation_id=presentation_id, revision_id=f"{presentation_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, envelope_id=envelope_id, participant_id=participant_id,
            task_id=task_id, consent_receipt_revision_id=receipt.revision_id,
            delivery_bundle_id=envelope.delivery_bundle_id,
            delivery_bundle_revision_id=envelope.delivery_bundle_revision_id,
            execution_job_revision_id=envelope.execution_job_revision_id,
            web_generation_contract_revision_id=envelope.web_generation_contract_revision_id,
            started_at=now,
        )
        self.repository.save_c1_batch((value,))
        return value

    def record_observation(self, *, project_id: str, envelope_id: str,
                           participant_id: str, presentation_id: str, measure_id: str,
                           value: ScalarValue | None, status: C1ObservationStatus,
                           completion_cause: str | None, actor: str, reason: str) -> C1OutcomeObservation:
        envelope = self.get_envelope(project_id, envelope_id, active=True)
        participant = self._participant(project_id, participant_id)
        if participant.envelope_id != envelope_id or participant.status != "active":
            raise DomainStateError("observation requires an active participant")
        presentation = self.repository.get_c1_current("c1_task_presentation", presentation_id)
        if not isinstance(presentation, C1TaskPresentation) or presentation.project_id != project_id:
            raise DomainStateError("unknown C1 task presentation")
        if presentation.envelope_id != envelope_id or presentation.participant_id != participant_id:
            raise DomainStateError("presentation does not belong to the participant and envelope")
        plan = self._current_confirmed_plan(project_id, envelope)
        measure = next((item for item in plan.measures if item.measure_id == measure_id), None)
        if measure is None or measure.source_layer != C1_SOURCE_LAYER:
            raise DomainStateError("measure must belong to the pinned plan and use research_observation")
        _validate_measure_value(measure, value)
        existing = self.list_observations(project_id, envelope_id)
        if any(item.presentation_id == presentation_id and item.measure_id == measure_id for item in existing):
            raise DomainStateError("C1 already has an observation for this presentation and measure")
        if not is_named_human_actor(actor):
            raise DomainStateError("C1 observation requires a named human recorder")
        observation_id = self._id("observation")
        now = self._now()
        observation = C1OutcomeObservation(
            observation_id=observation_id, revision_id=f"{observation_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, envelope_id=envelope_id, participant_id=participant_id,
            presentation_id=presentation_id, measurement_plan_revision_id=envelope.measurement_plan_revision_id,
            measure_id=measure_id, value=value, status=status, completion_cause=completion_cause,
            consent_receipt_revision_id=participant.consent_receipt_revision_id,
            delivery_bundle_id=envelope.delivery_bundle_id,
            delivery_bundle_revision_id=envelope.delivery_bundle_revision_id,
            execution_job_revision_id=envelope.execution_job_revision_id,
            web_generation_contract_revision_id=envelope.web_generation_contract_revision_id,
            recorded_by=actor, recorded_at=now,
            evidence_refs=(f"presentation:{presentation_id}", f"consent:{participant.consent_receipt_revision_id}"),
        )
        self.repository.save_c1_batch((observation,))
        return observation

    def list_observations(self, project_id: str, envelope_id: str) -> tuple[C1OutcomeObservation, ...]:
        self.get_envelope(project_id, envelope_id)
        return tuple(item for item in self.repository.list_c1("c1_outcome_observation", project_id=project_id) if isinstance(item, C1OutcomeObservation) and item.envelope_id == envelope_id)

    def withdraw_participant(self, *, project_id: str, envelope_id: str,
                             participant_id: str, actor: str, reason: str) -> C1WithdrawalTombstone:
        self.get_envelope(project_id, envelope_id)
        participant = self._participant(project_id, participant_id)
        if participant.envelope_id != envelope_id or participant.status != "active":
            raise DomainStateError("active participant in this envelope is required for withdrawal")
        if not is_named_human_actor(actor):
            raise DomainStateError("C1 withdrawal requires a named human actor")
        observations = [item for item in self.list_observations(project_id, envelope_id) if item.participant_id == participant_id]
        presentations = [item for item in self.repository.list_c1("c1_task_presentation", project_id=project_id) if isinstance(item, C1TaskPresentation) and item.envelope_id == envelope_id and item.participant_id == participant_id]
        observation_ids = {item.observation_id for item in observations}
        reviews = [item for item in self.repository.list_c1("c1_evidence_review", project_id=project_id) if isinstance(item, C1EvidenceReview) and item.envelope_id == envelope_id and observation_ids.intersection(item.observation_ids)]
        now = self._now()
        tombstone_id = self._id("withdrawal")
        tombstone = C1WithdrawalTombstone(
            tombstone_id=tombstone_id, revision_id=f"{tombstone_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=actor, reason=reason),
            project_id=project_id, envelope_id=envelope_id, participant_digest=hashlib.sha256(f"{project_id}:{envelope_id}:{participant_id}".encode("utf-8")).hexdigest(),
            deleted_receipts=1, deleted_presentations=len(presentations),
            deleted_observations=len(observations), deleted_reviews=len(reviews), withdrawn_at=now,
        )
        return self.repository.withdraw_c1_participant(
            project_id=project_id, envelope_id=envelope_id, participant_id=participant_id,
            tombstone=tombstone,
        )

    def review_evidence(self, *, project_id: str, envelope_id: str,
                        observation_ids: Iterable[str], reviewer: str,
                        decision: Literal["accepted", "modified", "rejected", "insufficient"],
                        evidence_level_after: C1EvidenceLevel, rationale: str,
                        limitations: Iterable[str] = ()) -> C1EvidenceReview:
        envelope = self.get_envelope(project_id, envelope_id)
        if not is_named_human_actor(reviewer) or reviewer.strip().lower() in _C1_REVIEWER_PLACEHOLDERS:
            raise DomainStateError("C1 EvidenceReview requires a named human reviewer, not a placeholder")
        if reviewer == envelope.host:
            raise DomainStateError("C1 reviewer must be independent from the trial host")
        ids = tuple(dict.fromkeys(observation_ids))
        if not ids:
            raise DomainStateError("C1 EvidenceReview requires at least one observation")
        observations = {item.observation_id: item for item in self.list_observations(project_id, envelope_id)}
        selected = [observations.get(item) for item in ids]
        if any(item is None for item in selected):
            raise DomainStateError("EvidenceReview references an unknown or withdrawn observation")
        concrete = [item for item in selected if isinstance(item, C1OutcomeObservation)]
        if len({item.measure_id for item in concrete}) != 1:
            raise DomainStateError("review one measure at a time")
        if any(item.status != "observed" for item in concrete) and decision in {"accepted", "modified"}:
            raise DomainStateError("non-success paths cannot be promoted as outcome evidence")
        if decision in {"rejected", "insufficient"} and evidence_level_after != "none":
            raise DomainStateError("rejected or insufficient C1 reviews must retain evidence level none")
        if evidence_level_after not in {"none", "exploratory", "observed"}:
            raise DomainStateError("research_observation evidence ceiling is observed")
        review_id = self._id("evidence-review")
        now = self._now()
        review = C1EvidenceReview(
            review_id=review_id, revision_id=f"{review_id}.r1",
            meta=RevisionMeta(revision=1, created_at=now, created_by=reviewer, reason=rationale),
            project_id=project_id, envelope_id=envelope_id, observation_ids=ids,
            measurement_plan_revision_id=envelope.measurement_plan_revision_id,
            delivery_bundle_revision_id=envelope.delivery_bundle_revision_id,
            execution_job_revision_id=envelope.execution_job_revision_id,
            web_generation_contract_revision_id=envelope.web_generation_contract_revision_id,
            reviewer=reviewer, decision=decision, evidence_level_after=evidence_level_after,
            rationale=rationale, limitations=tuple(limitations), reviewed_at=now,
        )
        self.repository.save_c1_batch((review,))
        return review

    def list_reviews(self, project_id: str, envelope_id: str) -> tuple[C1EvidenceReview, ...]:
        self.get_envelope(project_id, envelope_id)
        return tuple(item for item in self.repository.list_c1("c1_evidence_review", project_id=project_id) if isinstance(item, C1EvidenceReview) and item.envelope_id == envelope_id)

    def _participant(self, project_id: str, participant_id: str) -> C1Participant:
        value = self.repository.get_c1_current("c1_participant", participant_id)
        if not isinstance(value, C1Participant) or value.project_id != project_id:
            raise DomainStateError(f"unknown C1 participant: {participant_id}")
        return value

    def _current_confirmed_plan(self, project_id: str, envelope: C1TrialEnvelope) -> OutcomeMeasurementPlan:
        plan = self.application.get_project_view(project_id).outcome_measurement_plan
        if plan is None or plan.status != "confirmed" or plan.revision_id != envelope.measurement_plan_revision_id:
            raise DomainStateError("C1 measurement plan pin is stale")
        return plan


def _validate_measure_value(measure, value: ScalarValue | None) -> None:
    if value is None:
        return
    valid = {
        "boolean": isinstance(value, bool),
        "count": isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        "duration_seconds": isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0,
        "ordinal_1_5": isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5,
        "categorical": isinstance(value, str),
        "free_text": isinstance(value, str) and len(value) <= 200,
    }[measure.value_kind]
    if not valid:
        raise DomainStateError(f"value does not match measure {measure.measure_id} value_kind {measure.value_kind}")


def _validate_delivery_pin(bundle: ProductDeliveryBundle, execution_revision_id: str,
                           contract_revision_id: str, current_contract) -> None:
    if bundle.execution_job_revision_id != execution_revision_id:
        raise DomainStateError("execution revision does not match delivered bundle")
    if bundle.web_generation_contract_revision_id != contract_revision_id:
        raise DomainStateError("Web contract revision does not match delivered bundle")
    if not bundle.contract_is_current or current_contract is None or current_contract.revision_id != contract_revision_id:
        raise DomainStateError("C1 requires a bundle built from the current Web contract")
    if any(step.status != "succeeded" for step in bundle.verification_steps):
        raise DomainStateError("C1 requires all B6 verification steps to succeed")


__all__ = [
    "C1_ACCESS_POLICY", "C1_CONSENT_POLICY_REVISION", "C1_CONSENT_STATEMENT",
    "C1_DATA_CATEGORIES", "C1_EVIDENCE_CEILING", "C1_RETENTION_DAYS", "C1_RETENTION_PERIOD", "C1_RETENTION_POLICY",
    "C1_SOURCE_LAYER", "C1_WITHDRAWAL_POLICY", "C1ConsentReceipt",
    "C1EvidenceReview", "C1RetentionCleanupResult", "C1OutcomeObservation", "C1Participant", "C1Repository",
    "C1TaskPresentation", "C1TrialEnvelope", "C1WithdrawalTombstone",
    "InMemoryC1Repository", "SQLiteC1Repository", "ProductC1ObservationService",
]


