"""Pure state transitions for Product Studio upper-domain snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Literal, TypeVar

from psyteardown.experience.models import DependencyRef, DomainStateError, RevisionMeta
from psyteardown.product.models import (
    HumanConfirmation,
    OutcomeContract,
    OutcomeMeasurementPlan,
    ProblemModel,
    ProductIntent,
    ProductProject,
    ProductThesis,
    RevisionImpact,
    ThesisDisposition,
    WebProductGenerationContract,
)


SnapshotT = TypeVar(
    "SnapshotT",
    ProductProject,
    ProductIntent,
    ProblemModel,
    OutcomeContract,
    ProductThesis,
    WebProductGenerationContract,
    OutcomeMeasurementPlan,
)
ConfirmableT = TypeVar(
    "ConfirmableT", ProductIntent, ProblemModel, OutcomeContract, OutcomeMeasurementPlan
)
ThesisStatus = Literal["exploring", "selected", "paused", "rejected"]
ProjectStatus = Literal["active", "paused", "archived"]


def _next_meta(
    current: SnapshotT, *, actor: str, reason: str, occurred_at: datetime
) -> RevisionMeta:
    return RevisionMeta(
        revision=current.meta.revision + 1,
        parent_revision_id=current.revision_id,
        created_at=occurred_at,
        created_by=actor,
        reason=reason,
    )


def _ensure_new_revision_id(current: SnapshotT, new_revision_id: str) -> None:
    if not new_revision_id or new_revision_id == current.revision_id:
        raise DomainStateError("a transition requires a distinct non-empty revision_id")


_PROJECT_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"paused", "archived"}),
    "paused": frozenset({"active", "archived"}),
    # Archive is a reversible visibility state; it is not data deletion.
    "archived": frozenset({"active"}),
}


def transition_product_project_status(
    current: ProductProject,
    to_status: ProjectStatus,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProductProject:
    if to_status not in _PROJECT_TRANSITIONS[current.status]:
        raise DomainStateError(
            f"invalid product project transition: {current.status} -> {to_status}"
        )
    _ensure_new_revision_id(current, new_revision_id)
    payload = current.model_dump(mode="python")
    payload.update(
        {
            "revision_id": new_revision_id,
            "meta": _next_meta(
                current, actor=actor, reason=reason, occurred_at=occurred_at
            ),
            "status": to_status,
        }
    )
    return ProductProject.model_validate(payload)


def _confirm(
    current: ConfirmableT,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ConfirmableT:
    if current.status != "proposed":
        raise DomainStateError("only a proposed snapshot can be confirmed")
    _ensure_new_revision_id(current, new_revision_id)
    payload = current.model_dump(mode="python")
    payload.update(
        {
            "revision_id": new_revision_id,
            "meta": _next_meta(
                current, actor=actor, reason=reason, occurred_at=occurred_at
            ),
            "status": "confirmed",
            "confirmation": HumanConfirmation(
                confirmed_by=actor,
                confirmed_at=occurred_at,
                rationale=reason,
            ),
        }
    )
    return current.__class__.model_validate(payload)


def confirm_product_intent(
    current: ProductIntent,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProductIntent:
    return _confirm(
        current,
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def confirm_problem_model(
    current: ProblemModel,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProblemModel:
    return _confirm(
        current,
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def confirm_outcome_contract(
    current: OutcomeContract,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> OutcomeContract:
    return _confirm(
        current,
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def _revise_to_proposal(
    current: SnapshotT,
    changes: Mapping[str, object],
    *,
    stable_id_field: str,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> SnapshotT:
    _ensure_new_revision_id(current, new_revision_id)
    reserved = {
        stable_id_field,
        "project_id",
        "revision_id",
        "meta",
        "status",
        "confirmation",
        "disposition",
    }
    attempted = reserved.intersection(changes)
    if attempted:
        raise DomainStateError(
            "revision changes cannot replace identity or workflow fields: "
            + ", ".join(sorted(attempted))
        )
    payload = current.model_dump(mode="python")
    payload.update(changes)
    payload.update(
        {
            "revision_id": new_revision_id,
            "meta": _next_meta(
                current, actor=actor, reason=reason, occurred_at=occurred_at
            ),
            "status": "proposed",
        }
    )
    if "confirmation" in payload:
        payload["confirmation"] = None
    if "disposition" in payload:
        payload["disposition"] = None
    return current.__class__.model_validate(payload)


def revise_product_intent(
    current: ProductIntent,
    changes: Mapping[str, object],
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProductIntent:
    return _revise_to_proposal(
        current,
        changes,
        stable_id_field="intent_id",
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def revise_problem_model(
    current: ProblemModel,
    changes: Mapping[str, object],
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProblemModel:
    return _revise_to_proposal(
        current,
        changes,
        stable_id_field="problem_model_id",
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def revise_outcome_contract(
    current: OutcomeContract,
    changes: Mapping[str, object],
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> OutcomeContract:
    return _revise_to_proposal(
        current,
        changes,
        stable_id_field="outcome_contract_id",
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def confirm_outcome_measurement_plan(
    current: OutcomeMeasurementPlan,
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> OutcomeMeasurementPlan:
    return _confirm(
        current,
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def revise_outcome_measurement_plan(
    current: OutcomeMeasurementPlan,
    changes: Mapping[str, object],
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> OutcomeMeasurementPlan:
    return _revise_to_proposal(
        current,
        changes,
        stable_id_field="measurement_plan_id",
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


def revise_product_thesis(
    current: ProductThesis,
    changes: Mapping[str, object],
    *,
    new_revision_id: str,
    actor: str,
    reason: str,
    occurred_at: datetime,
) -> ProductThesis:
    return _revise_to_proposal(
        current,
        changes,
        stable_id_field="thesis_id",
        new_revision_id=new_revision_id,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
    )


_THESIS_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"exploring", "selected", "paused", "rejected"}),
    "exploring": frozenset({"selected", "paused", "rejected"}),
    "selected": frozenset({"paused", "rejected"}),
    "paused": frozenset({"exploring", "selected", "rejected"}),
    "rejected": frozenset(),
}


def transition_product_thesis(
    current: ProductThesis,
    to_status: ThesisStatus,
    *,
    new_revision_id: str,
    actor: str,
    actor_type: Literal["human", "system"],
    reason: str,
    occurred_at: datetime,
    authorization_ref: str | None = None,
) -> ProductThesis:
    if to_status not in _THESIS_TRANSITIONS[current.status]:
        raise DomainStateError(
            f"invalid product thesis transition: {current.status} -> {to_status}"
        )
    _ensure_new_revision_id(current, new_revision_id)
    payload = current.model_dump(mode="python")
    payload.update(
        {
            "revision_id": new_revision_id,
            "meta": _next_meta(
                current, actor=actor, reason=reason, occurred_at=occurred_at
            ),
            "status": to_status,
            "disposition": ThesisDisposition(
                action=to_status,
                decided_by=actor,
                actor_type=actor_type,
                decided_at=occurred_at,
                rationale=reason,
                authorization_ref=authorization_ref,
            ),
        }
    )
    return ProductThesis.model_validate(payload)


def assess_revision_impacts(
    changed_dependency: DependencyRef,
    dependents: Iterable[
        ProblemModel
        | OutcomeContract
        | ProductThesis
        | WebProductGenerationContract
        | OutcomeMeasurementPlan
    ],
) -> tuple[RevisionImpact, ...]:
    """Return direct impacts for snapshots pinned to the changed revision.

    ``changed_dependency`` identifies the old revision that has just gained a
    successor.  The function never mutates dependents or recursively invents
    impacts; application services persist and propagate the returned facts.
    """

    impacts: list[RevisionImpact] = []
    for dependent in dependents:
        if changed_dependency not in dependent.dependencies:
            continue
        if isinstance(dependent, ProblemModel):
            dependent_type = "problem_model"
            dependent_id = dependent.problem_model_id
            impact = "review_required"
        elif isinstance(dependent, OutcomeContract):
            dependent_type = "outcome_contract"
            dependent_id = dependent.outcome_contract_id
            impact = "stale"
        elif isinstance(dependent, ProductThesis):
            dependent_type = "product_thesis"
            dependent_id = dependent.thesis_id
            impact = "stale"
        elif isinstance(dependent, OutcomeMeasurementPlan):
            dependent_type = "outcome_measurement_plan"
            dependent_id = dependent.measurement_plan_id
            impact = "stale"
        else:
            dependent_type = "web_generation_contract"
            dependent_id = dependent.web_generation_contract_id
            impact = "stale"
        impacts.append(
            RevisionImpact(
                dependent_type=dependent_type,
                dependent_id=dependent_id,
                dependent_revision_id=dependent.revision_id,
                impact=impact,
                changed_dependency=changed_dependency,
                reason=(
                    f"{dependent_type} references superseded "
                    f"{changed_dependency.object_type} revision "
                    f"{changed_dependency.revision}"
                ),
            )
        )
    return tuple(impacts)
