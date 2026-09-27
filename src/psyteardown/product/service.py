"""Application command boundary for Product Studio upper-domain objects."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from uuid import uuid4

from psyteardown.experience.models import (
    AuditEvent,
    DependencyRef,
    DomainEvent,
    DomainStateError,
    RevisionMeta,
)
from psyteardown.product.commands import (
    ChangeProductProjectStatus,
    ConfirmOutcomeContract,
    ConfirmProblemModel,
    ConfirmProductIntent,
    CreateProductProject,
    SubmitOutcomeContractProposal,
    SubmitProblemModelProposal,
    SubmitProductIntentProposal,
    SubmitProductThesisProposal,
    TransitionProductThesis,
    ConfirmWebProductGenerationContract,
    SubmitWebProductGenerationContractProposal,
    ConfirmOutcomeMeasurementPlan,
    DeriveOutcomeMeasurementPlan,
    OutcomeMeasurementPlanProposal,
    SubmitOutcomeMeasurementPlanProposal,
)
from psyteardown.product.measurement import (
    derive_measurement_plan_proposal,
    measurement_plan_blockers,
    measurement_plan_structure_errors,
)
from psyteardown.product.models import (
    OutcomeContract,
    OutcomeMeasurementPlan,
    ProblemModel,
    ProductIntent,
    ProductProject,
    ProductProjectView,
    ProductThesis,
    RevisionImpact,
    WebProductGenerationContract,
)
from psyteardown.product.repositories import (
    InMemoryProductRepository,
    ProductRepository,
    ProductRepositoryError,
    ProductSnapshot,
)
from psyteardown.product.transitions import (
    assess_revision_impacts,
    confirm_outcome_contract,
    confirm_outcome_measurement_plan,
    confirm_problem_model,
    confirm_product_intent,
    revise_outcome_contract,
    revise_outcome_measurement_plan,
    revise_problem_model,
    revise_product_intent,
    revise_product_thesis,
    transition_product_project_status,
    transition_product_thesis,
)


Clock = Callable[[], datetime]
IdFactory = Callable[[str], str]


def _system_clock() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class ProductApplicationService:
    """Coordinates independent product aggregates through atomic commands."""

    def __init__(
        self,
        repository: ProductRepository | None = None,
        *,
        clock: Clock = _system_clock,
        id_factory: IdFactory = _uuid_id,
    ) -> None:
        self.repository = repository or InMemoryProductRepository()
        self._clock = clock
        self._id_factory = id_factory

    def create_project(self, command: CreateProductProject) -> ProductProject:
        now = self._now()
        project_id = command.project_id or self._id("project")
        if self.repository.get_current("product_project", project_id) is not None:
            raise ProductRepositoryError(f"product project already exists: {project_id}")
        project = ProductProject(
            project_id=project_id,
            revision_id=self._revision_id(project_id, 1),
            meta=RevisionMeta(
                revision=1,
                created_at=now,
                created_by=command.actor,
                reason=command.reason,
            ),
            name=command.name,
            collaboration_mode=command.collaboration_mode,
            created_from=tuple(command.created_from),
        )
        return self._persist(
            "product_project",
            project_id,
            project,
            project_id=project_id,
            expected_revision=None,
            event_type="product_project_created",
            actor=command.actor,
            reason=command.reason,
        )

    def list_projects(self) -> tuple[ProductProject, ...]:
        """Return current projects for local workspace recovery."""
        values = self.repository.list_current("product_project")
        return tuple(sorted(values, key=lambda item: item.meta.created_at, reverse=True))

    def change_project_status(
        self, command: ChangeProductProjectStatus
    ) -> ProductProject:
        project = self._require_project(command.project_id)
        self._check_expected(project, command.expected_revision)
        now = self._now()
        updated = transition_product_project_status(
            project,
            command.to_status,
            new_revision_id=self._revision_id(
                project.project_id, project.meta.revision + 1
            ),
            actor=command.actor,
            reason=command.reason,
            occurred_at=now,
        )
        return self._persist(
            "product_project",
            project.project_id,
            updated,
            project_id=project.project_id,
            expected_revision=command.expected_revision,
            event_type="product_project_status_changed",
            actor=command.actor,
            reason=command.reason,
        )

    def submit_product_intent(
        self, command: SubmitProductIntentProposal
    ) -> ProductIntent:
        self._require_active_project(command.project_id)
        current, intent_id = self._proposal_target(
            "product_intent",
            command.project_id,
            command.intent_id,
            command.expected_revision,
            singleton=True,
            id_prefix="intent",
        )
        now = self._now()
        changes = command.proposal.model_dump(mode="python")
        if current is None:
            proposed = ProductIntent(
                intent_id=intent_id,
                revision_id=self._revision_id(intent_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                project_id=command.project_id,
                **changes,
            )
            impacts: tuple[RevisionImpact, ...] = ()
        else:
            assert isinstance(current, ProductIntent)
            impacts = self._direct_impacts("product_intent", current)
            proposed = revise_product_intent(
                current,
                changes,
                new_revision_id=self._revision_id(
                    intent_id, current.meta.revision + 1
                ),
                actor=command.actor,
                reason=command.reason,
                occurred_at=now,
            )
        return self._persist(
            "product_intent",
            intent_id,
            proposed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="product_intent_proposed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def confirm_product_intent(
        self, command: ConfirmProductIntent
    ) -> ProductIntent:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "product_intent", command.intent_id, command.project_id
        )
        assert isinstance(current, ProductIntent)
        self._check_expected(current, command.expected_revision)
        impacts = self._direct_impacts("product_intent", current)
        confirmed = confirm_product_intent(
            current,
            new_revision_id=self._revision_id(
                current.intent_id, current.meta.revision + 1
            ),
            actor=command.actor,
            reason=command.reason,
            occurred_at=self._now(),
        )
        return self._persist(
            "product_intent",
            current.intent_id,
            confirmed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="product_intent_confirmed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def submit_problem_model(
        self, command: SubmitProblemModelProposal
    ) -> ProblemModel:
        self._require_active_project(command.project_id)
        intent = self._require_revision(
            "product_intent",
            command.proposal.intent_revision_id,
            command.project_id,
            confirmed=True,
        )
        assert isinstance(intent, ProductIntent)
        current, problem_model_id = self._proposal_target(
            "problem_model",
            command.project_id,
            command.problem_model_id,
            command.expected_revision,
            singleton=True,
            id_prefix="problem",
        )
        now = self._now()
        changes = command.proposal.model_dump(mode="python")
        changes["dependencies"] = (
            DependencyRef(
                object_type="product_intent",
                object_id=intent.intent_id,
                revision=intent.meta.revision,
            ),
        )
        if current is None:
            proposed = ProblemModel(
                problem_model_id=problem_model_id,
                revision_id=self._revision_id(problem_model_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                project_id=command.project_id,
                **changes,
            )
            impacts = ()
        else:
            assert isinstance(current, ProblemModel)
            impacts = self._direct_impacts("problem_model", current)
            proposed = revise_problem_model(
                current,
                changes,
                new_revision_id=self._revision_id(
                    problem_model_id, current.meta.revision + 1
                ),
                actor=command.actor,
                reason=command.reason,
                occurred_at=now,
            )
        return self._persist(
            "problem_model",
            problem_model_id,
            proposed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="problem_model_proposed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def confirm_problem_model(
        self, command: ConfirmProblemModel
    ) -> ProblemModel:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "problem_model", command.problem_model_id, command.project_id
        )
        assert isinstance(current, ProblemModel)
        self._check_expected(current, command.expected_revision)
        impacts = self._direct_impacts("problem_model", current)
        confirmed = confirm_problem_model(
            current,
            new_revision_id=self._revision_id(
                current.problem_model_id, current.meta.revision + 1
            ),
            actor=command.actor,
            reason=command.reason,
            occurred_at=self._now(),
        )
        return self._persist(
            "problem_model",
            current.problem_model_id,
            confirmed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="problem_model_confirmed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def submit_outcome_contract(
        self, command: SubmitOutcomeContractProposal
    ) -> OutcomeContract:
        self._require_active_project(command.project_id)
        intent = self._require_revision(
            "product_intent",
            command.proposal.intent_revision_id,
            command.project_id,
            confirmed=True,
        )
        problem = self._require_revision(
            "problem_model",
            command.proposal.problem_model_revision_id,
            command.project_id,
            confirmed=True,
        )
        assert isinstance(intent, ProductIntent)
        assert isinstance(problem, ProblemModel)
        if problem.intent_revision_id != intent.revision_id:
            raise DomainStateError(
                "outcome contract inputs do not share the same product intent revision"
            )
        current, contract_id = self._proposal_target(
            "outcome_contract",
            command.project_id,
            command.outcome_contract_id,
            command.expected_revision,
            singleton=True,
            id_prefix="contract",
        )
        now = self._now()
        changes = command.proposal.model_dump(mode="python")
        changes["dependencies"] = (
            DependencyRef(
                object_type="product_intent",
                object_id=intent.intent_id,
                revision=intent.meta.revision,
            ),
            DependencyRef(
                object_type="problem_model",
                object_id=problem.problem_model_id,
                revision=problem.meta.revision,
            ),
        )
        if current is None:
            proposed = OutcomeContract(
                outcome_contract_id=contract_id,
                revision_id=self._revision_id(contract_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                project_id=command.project_id,
                **changes,
            )
            impacts = ()
        else:
            assert isinstance(current, OutcomeContract)
            impacts = self._direct_impacts("outcome_contract", current)
            proposed = revise_outcome_contract(
                current,
                changes,
                new_revision_id=self._revision_id(
                    contract_id, current.meta.revision + 1
                ),
                actor=command.actor,
                reason=command.reason,
                occurred_at=now,
            )
        return self._persist(
            "outcome_contract",
            contract_id,
            proposed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="outcome_contract_proposed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def confirm_outcome_contract(
        self, command: ConfirmOutcomeContract
    ) -> OutcomeContract:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "outcome_contract", command.outcome_contract_id, command.project_id
        )
        assert isinstance(current, OutcomeContract)
        self._check_expected(current, command.expected_revision)
        impacts = self._direct_impacts("outcome_contract", current)
        confirmed = confirm_outcome_contract(
            current,
            new_revision_id=self._revision_id(
                current.outcome_contract_id, current.meta.revision + 1
            ),
            actor=command.actor,
            reason=command.reason,
            occurred_at=self._now(),
        )
        return self._persist(
            "outcome_contract",
            current.outcome_contract_id,
            confirmed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="outcome_contract_confirmed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def submit_product_thesis(
        self, command: SubmitProductThesisProposal
    ) -> ProductThesis:
        self._require_active_project(command.project_id)
        problem = self._require_revision(
            "problem_model",
            command.proposal.problem_model_revision_id,
            command.project_id,
            confirmed=True,
        )
        contract = self._require_revision(
            "outcome_contract",
            command.proposal.outcome_contract_revision_id,
            command.project_id,
            confirmed=True,
        )
        assert isinstance(problem, ProblemModel)
        assert isinstance(contract, OutcomeContract)
        if contract.problem_model_revision_id != problem.revision_id:
            raise DomainStateError(
                "product thesis inputs do not share the same problem model revision"
            )
        current, thesis_id = self._proposal_target(
            "product_thesis",
            command.project_id,
            command.thesis_id,
            command.expected_revision,
            singleton=False,
            id_prefix="thesis",
        )
        now = self._now()
        changes = command.proposal.model_dump(mode="python")
        changes["dependencies"] = (
            DependencyRef(
                object_type="problem_model",
                object_id=problem.problem_model_id,
                revision=problem.meta.revision,
            ),
            DependencyRef(
                object_type="outcome_contract",
                object_id=contract.outcome_contract_id,
                revision=contract.meta.revision,
            ),
        )
        if current is None:
            proposed = ProductThesis(
                thesis_id=thesis_id,
                revision_id=self._revision_id(thesis_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                project_id=command.project_id,
                **changes,
            )
            impacts: tuple[RevisionImpact, ...] = ()
        else:
            assert isinstance(current, ProductThesis)
            impacts = self._direct_impacts("product_thesis", current)
            proposed = revise_product_thesis(
                current,
                changes,
                new_revision_id=self._revision_id(
                    thesis_id, current.meta.revision + 1
                ),
                actor=command.actor,
                reason=command.reason,
                occurred_at=now,
            )
        return self._persist(
            "product_thesis",
            thesis_id,
            proposed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="product_thesis_proposed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def transition_product_thesis(
        self, command: TransitionProductThesis
    ) -> ProductThesis:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "product_thesis", command.thesis_id, command.project_id
        )
        assert isinstance(current, ProductThesis)
        self._check_expected(current, command.expected_revision)
        impacts = self._direct_impacts("product_thesis", current)
        updated = transition_product_thesis(
            current,
            command.to_status,
            new_revision_id=self._revision_id(
                current.thesis_id, current.meta.revision + 1
            ),
            actor=command.actor,
            actor_type=command.actor_type,
            reason=command.reason,
            occurred_at=self._now(),
            authorization_ref=command.authorization_ref,
        )
        return self._persist(
            "product_thesis",
            current.thesis_id,
            updated,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="product_thesis_disposition_changed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def submit_web_generation_contract(
        self, command: SubmitWebProductGenerationContractProposal
    ) -> WebProductGenerationContract:
        self._require_active_project(command.project_id)
        thesis = self._require_revision(
            "product_thesis",
            command.proposal.product_thesis_revision_id,
            command.project_id,
            confirmed=False,
        )
        outcome = self._require_revision(
            "outcome_contract",
            command.proposal.outcome_contract_revision_id,
            command.project_id,
            confirmed=True,
        )
        assert isinstance(thesis, ProductThesis)
        assert isinstance(outcome, OutcomeContract)
        if thesis.status not in {"exploring", "selected"}:
            raise DomainStateError(
                "Web generation requires an exploring or selected product thesis"
            )
        if thesis.outcome_contract_revision_id != outcome.revision_id:
            raise DomainStateError(
                "Web generation inputs do not share the same outcome contract revision"
            )
        current, contract_id = self._proposal_target(
            "web_generation_contract",
            command.project_id,
            command.web_generation_contract_id,
            command.expected_revision,
            singleton=True,
            id_prefix="web-contract",
        )
        now = self._now()
        changes = command.proposal.model_dump(mode="python")
        changes["product_thesis_revision_id"] = thesis.revision_id
        changes["outcome_contract_revision_id"] = outcome.revision_id
        changes["dependencies"] = (
            DependencyRef(
                object_type="product_thesis",
                object_id=thesis.thesis_id,
                revision=thesis.meta.revision,
            ),
            DependencyRef(
                object_type="outcome_contract",
                object_id=outcome.outcome_contract_id,
                revision=outcome.meta.revision,
            ),
        )
        if current is None:
            proposed = WebProductGenerationContract(
                web_generation_contract_id=contract_id,
                revision_id=self._revision_id(contract_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                project_id=command.project_id,
                **changes,
            )
            impacts: tuple[RevisionImpact, ...] = ()
        else:
            assert isinstance(current, WebProductGenerationContract)
            impacts = self._direct_impacts("web_generation_contract", current)
            proposed = current.__class__.model_validate(
                {
                    **current.model_dump(mode="python"),
                    **changes,
                    "revision_id": self._revision_id(
                        contract_id, current.meta.revision + 1
                    ),
                    "meta": RevisionMeta(
                        revision=current.meta.revision + 1,
                        parent_revision_id=current.revision_id,
                        created_at=now,
                        created_by=command.actor,
                        reason=command.reason,
                    ),
                    "status": "proposed",
                    "confirmation": None,
                }
            )
        return self._persist(
            "web_generation_contract",
            contract_id,
            proposed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="web_generation_contract_proposed",
            actor=command.actor,
            reason=command.reason,
            impacts=impacts,
        )

    def confirm_web_generation_contract(
        self, command: ConfirmWebProductGenerationContract
    ) -> WebProductGenerationContract:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "web_generation_contract",
            command.web_generation_contract_id,
            command.project_id,
        )
        assert isinstance(current, WebProductGenerationContract)
        self._check_expected(current, command.expected_revision)
        now = self._now()
        confirmed = current.model_validate(
            {
                **current.model_dump(mode="python"),
                "revision_id": self._revision_id(
                    current.web_generation_contract_id, current.meta.revision + 1
                ),
                "meta": RevisionMeta(
                    revision=current.meta.revision + 1,
                    parent_revision_id=current.revision_id,
                    created_at=now,
                    created_by=command.actor,
                    reason=command.reason,
                ),
                "status": "confirmed",
                "confirmation": {
                    "confirmed_by": command.actor,
                    "confirmed_at": now,
                    "rationale": command.reason,
                },
            }
        )
        return self._persist(
            "web_generation_contract",
            current.web_generation_contract_id,
            confirmed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="web_generation_contract_confirmed",
            actor=command.actor,
            reason=command.reason,
        )

    def derive_outcome_measurement_plan(
        self, command: DeriveOutcomeMeasurementPlan
    ) -> OutcomeMeasurementPlan:
        """Propose a plan copied from the current confirmed outcome contract."""

        self._require_active_project(command.project_id)
        contract = self._single_current("outcome_contract", command.project_id)
        if not isinstance(contract, OutcomeContract) or contract.status != "confirmed":
            raise DomainStateError(
                "a measurement plan requires the current outcome contract to be human-confirmed"
            )
        return self._save_measurement_plan(
            project_id=command.project_id,
            proposal=derive_measurement_plan_proposal(contract),
            origin="deterministic_derivation",
            measurement_plan_id=command.measurement_plan_id,
            expected_revision=command.expected_revision,
            actor=command.actor,
            reason=command.reason,
        )

    def submit_outcome_measurement_plan(
        self, command: SubmitOutcomeMeasurementPlanProposal
    ) -> OutcomeMeasurementPlan:
        self._require_active_project(command.project_id)
        return self._save_measurement_plan(
            project_id=command.project_id,
            proposal=command.proposal,
            origin="human_revision",
            measurement_plan_id=command.measurement_plan_id,
            expected_revision=command.expected_revision,
            actor=command.actor,
            reason=command.reason,
        )

    def confirm_outcome_measurement_plan(
        self, command: ConfirmOutcomeMeasurementPlan
    ) -> OutcomeMeasurementPlan:
        self._require_active_project(command.project_id)
        current = self._require_current(
            "outcome_measurement_plan", command.measurement_plan_id, command.project_id
        )
        assert isinstance(current, OutcomeMeasurementPlan)
        self._check_expected(current, command.expected_revision)
        contract = self._single_current("outcome_contract", command.project_id)
        blockers = measurement_plan_blockers(
            current, contract if isinstance(contract, OutcomeContract) else None
        )
        if blockers:
            raise DomainStateError(
                "measurement plan cannot be confirmed: " + "; ".join(blockers)
            )
        confirmed = confirm_outcome_measurement_plan(
            current,
            new_revision_id=self._revision_id(
                current.measurement_plan_id, current.meta.revision + 1
            ),
            actor=command.actor,
            reason=command.reason,
            occurred_at=self._now(),
        )
        return self._persist(
            "outcome_measurement_plan",
            current.measurement_plan_id,
            confirmed,
            project_id=command.project_id,
            expected_revision=command.expected_revision,
            event_type="outcome_measurement_plan_confirmed",
            actor=command.actor,
            reason=command.reason,
        )

    def _save_measurement_plan(
        self,
        *,
        project_id: str,
        proposal: OutcomeMeasurementPlanProposal,
        origin: str,
        measurement_plan_id: str | None,
        expected_revision: int | None,
        actor: str,
        reason: str,
    ) -> OutcomeMeasurementPlan:
        contract = self._require_revision(
            "outcome_contract",
            proposal.outcome_contract_revision_id,
            project_id,
            confirmed=True,
        )
        assert isinstance(contract, OutcomeContract)
        errors = measurement_plan_structure_errors(proposal, contract)
        if errors:
            raise DomainStateError(
                "measurement plan does not fit its outcome contract: " + "; ".join(errors)
            )
        current, plan_id = self._proposal_target(
            "outcome_measurement_plan",
            project_id,
            measurement_plan_id,
            expected_revision,
            singleton=True,
            id_prefix="measurement-plan",
        )
        now = self._now()
        changes = proposal.model_dump(mode="python")
        changes["origin"] = origin
        changes["dependencies"] = (
            DependencyRef(
                object_type="outcome_contract",
                object_id=contract.outcome_contract_id,
                revision=contract.meta.revision,
            ),
        )
        if current is None:
            proposed = OutcomeMeasurementPlan(
                measurement_plan_id=plan_id,
                revision_id=self._revision_id(plan_id, 1),
                meta=RevisionMeta(
                    revision=1,
                    created_at=now,
                    created_by=actor,
                    reason=reason,
                ),
                project_id=project_id,
                **changes,
            )
        else:
            assert isinstance(current, OutcomeMeasurementPlan)
            proposed = revise_outcome_measurement_plan(
                current,
                changes,
                new_revision_id=self._revision_id(plan_id, current.meta.revision + 1),
                actor=actor,
                reason=reason,
                occurred_at=now,
            )
        return self._persist(
            "outcome_measurement_plan",
            plan_id,
            proposed,
            project_id=project_id,
            expected_revision=expected_revision,
            event_type="outcome_measurement_plan_proposed",
            actor=actor,
            reason=reason,
        )

    def get_project_view(self, project_id: str) -> ProductProjectView:
        project = self._require_project(project_id)
        contract = self._single_current("outcome_contract", project_id)
        plan = self._single_current("outcome_measurement_plan", project_id)
        return ProductProjectView(
            project=project,
            product_intent=self._single_current("product_intent", project_id),
            problem_model=self._single_current("problem_model", project_id),
            outcome_contract=contract,
            product_theses=tuple(
                self.repository.list_current("product_thesis", project_id=project_id)
            ),
            web_generation_contract=self._single_current(
                "web_generation_contract", project_id
            ),
            outcome_measurement_plan=plan,
            measurement_plan_blockers=(
                measurement_plan_blockers(plan, contract)
                if isinstance(plan, OutcomeMeasurementPlan)
                else ()
            ),
            recorded_impacts=tuple(
                self.repository.list_impacts(project_id=project_id)
            ),
        )

    def _persist(
        self,
        object_type: str,
        object_id: str,
        value: ProductSnapshot,
        *,
        project_id: str,
        expected_revision: int | None,
        event_type: str,
        actor: str,
        reason: str,
        impacts: tuple[RevisionImpact, ...] = (),
    ):
        occurred_at = value.meta.created_at
        domain_events = [
            DomainEvent(
                event_id=self._id("event"),
                event_type=event_type,
                aggregate_id=object_id,
                aggregate_revision_id=value.revision_id,
                occurred_at=occurred_at,
                data=(
                    ("project_id", project_id),
                    ("content_hash", value.content_hash),
                ),
            )
        ]
        for impact in impacts:
            domain_events.append(
                DomainEvent(
                    event_id=self._id("event"),
                    event_type="product_dependency_impact_recorded",
                    aggregate_id=impact.dependent_id,
                    aggregate_revision_id=impact.dependent_revision_id,
                    occurred_at=occurred_at,
                    data=(
                        ("project_id", project_id),
                        ("impact", impact.impact),
                        (
                            "changed_dependency",
                            f"{impact.changed_dependency.object_type}:"
                            f"{impact.changed_dependency.object_id}:"
                            f"r{impact.changed_dependency.revision}",
                        ),
                    ),
                )
            )
        audit = AuditEvent(
            audit_id=self._id("audit"),
            action=event_type,
            target_id=object_id,
            target_revision_id=value.revision_id,
            actor=actor,
            reason=reason,
            occurred_at=occurred_at,
            expected_revision=expected_revision,
        )
        return self.repository.save_command(
            object_type,
            object_id,
            value.revision_id,
            value,
            project_id=project_id,
            expected_revision=expected_revision,
            domain_events=tuple(domain_events),
            audit_events=(audit,),
            impacts=impacts,
        )

    def _proposal_target(
        self,
        object_type: str,
        project_id: str,
        requested_id: str | None,
        expected_revision: int | None,
        *,
        singleton: bool,
        id_prefix: str,
    ) -> tuple[ProductSnapshot | None, str]:
        existing_for_project = self.repository.list_current(
            object_type, project_id=project_id
        )
        if requested_id is None:
            if singleton and existing_for_project:
                raise DomainStateError(
                    f"project already has a current {object_type}; its stable ID is required for revision"
                )
            if expected_revision is not None:
                raise ProductRepositoryError(
                    "expected_revision cannot be used without an aggregate ID"
                )
            return None, self._id(id_prefix)

        current = self.repository.get_current(object_type, requested_id)
        if current is None:
            if expected_revision is not None:
                raise ProductRepositoryError(
                    f"revision conflict: expected {expected_revision}, current None"
                )
            if singleton and existing_for_project:
                raise DomainStateError(
                    f"project already has a different current {object_type}"
                )
            return None, requested_id
        if current.project_id != project_id:
            raise DomainStateError(
                f"{object_type} belongs to project {current.project_id}, not {project_id}"
            )
        if expected_revision is None:
            raise ProductRepositoryError(
                "expected_revision is required for an existing aggregate"
            )
        self._check_expected(current, expected_revision)
        return current, requested_id

    def _require_project(self, project_id: str) -> ProductProject:
        project = self.repository.get_current("product_project", project_id)
        if project is None:
            raise DomainStateError(f"unknown product project: {project_id}")
        assert isinstance(project, ProductProject)
        return project

    def _require_active_project(self, project_id: str) -> ProductProject:
        project = self._require_project(project_id)
        if project.status != "active":
            raise DomainStateError(
                f"product project must be active for writes; current status is {project.status}"
            )
        return project

    def _require_current(
        self, object_type: str, object_id: str, project_id: str
    ) -> ProductSnapshot:
        current = self.repository.get_current(object_type, object_id)
        if current is None:
            raise DomainStateError(f"unknown {object_type}: {object_id}")
        if current.project_id != project_id:
            raise DomainStateError(
                f"{object_type} belongs to project {current.project_id}, not {project_id}"
            )
        return current

    def _require_revision(
        self,
        object_type: str,
        revision_id: str,
        project_id: str,
        *,
        confirmed: bool,
    ) -> ProductSnapshot:
        value = self.repository.get_revision(object_type, revision_id)
        if value is None:
            raise DomainStateError(f"unknown {object_type} revision: {revision_id}")
        if value.project_id != project_id:
            raise DomainStateError(
                f"{object_type} revision belongs to project {value.project_id}, not {project_id}"
            )
        if confirmed and getattr(value, "status", None) != "confirmed":
            raise DomainStateError(
                f"{object_type} revision must be human-confirmed before downstream use"
            )
        return value

    def _direct_impacts(
        self, object_type: str, current: ProductSnapshot
    ) -> tuple[RevisionImpact, ...]:
        if object_type == "product_project":
            return ()
        changed = DependencyRef(
            object_type=object_type,
            object_id=self._stable_id(current),
            revision=current.meta.revision,
        )
        if object_type == "product_thesis":
            changed = DependencyRef(
                object_type=object_type,
                object_id=self._stable_id(current),
                revision=current.meta.revision,
            )
            web_contracts = self.repository.list_current(
                "web_generation_contract", project_id=current.project_id
            )
            return assess_revision_impacts(changed, web_contracts)
        dependents: list[
            ProblemModel
            | OutcomeContract
            | ProductThesis
            | WebProductGenerationContract
            | OutcomeMeasurementPlan
        ] = []
        for dependent_type in (
            "problem_model",
            "outcome_contract",
            "product_thesis",
            "web_generation_contract",
            "outcome_measurement_plan",
        ):
            dependents.extend(
                self.repository.list_current(
                    dependent_type, project_id=current.project_id
                )
            )
        return assess_revision_impacts(changed, dependents)

    def _single_current(
        self, object_type: str, project_id: str
    ) -> ProductSnapshot | None:
        values = self.repository.list_current(object_type, project_id=project_id)
        if len(values) > 1:
            raise ProductRepositoryError(
                f"project has multiple current {object_type} aggregates"
            )
        return values[0] if values else None

    @staticmethod
    def _check_expected(value: ProductSnapshot, expected_revision: int) -> None:
        if value.meta.revision != expected_revision:
            raise ProductRepositoryError(
                f"revision conflict: expected {expected_revision}, current {value.meta.revision}"
            )

    @staticmethod
    def _stable_id(value: ProductSnapshot) -> str:
        if isinstance(value, ProductProject):
            return value.project_id
        if isinstance(value, ProductIntent):
            return value.intent_id
        if isinstance(value, ProblemModel):
            return value.problem_model_id
        if isinstance(value, OutcomeContract):
            return value.outcome_contract_id
        if isinstance(value, WebProductGenerationContract):
            return value.web_generation_contract_id
        if isinstance(value, OutcomeMeasurementPlan):
            return value.measurement_plan_id
        return value.thesis_id

    @staticmethod
    def _revision_id(object_id: str, revision: int) -> str:
        return f"{object_id}.r{revision}"

    def _id(self, prefix: str) -> str:
        value = self._id_factory(prefix)
        if not value:
            raise ValueError("id_factory returned an empty identifier")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ProductApplicationService clock must return timezone-aware UTC")
        if value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("ProductApplicationService clock must return UTC")
        return value
