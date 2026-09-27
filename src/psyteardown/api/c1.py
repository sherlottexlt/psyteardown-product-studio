"""HTTP boundary for C1 consented, manually hosted task observations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from psyteardown.api.dependencies import get_product_c1_service
from psyteardown.api.projects import ERROR_RESPONSES
from psyteardown.api.schemas import (
    C1ConsentReceiptResponse,
    C1EvidenceReviewResponse,
    C1EnrollmentResponse,
    C1OutcomeObservationResponse,
    C1ParticipantResponse,
    C1PolicyResponse,
    C1TaskPresentationResponse,
    C1TrialEnvelopeResponse,
    EndC1EnvelopeRequest,
    C1WithdrawalTombstoneResponse,
    EnrollC1ParticipantRequest,
    PresentC1TaskRequest,
    RecordC1ObservationRequest,
    ReviewC1EvidenceRequest,
    StartC1EnvelopeRequest,
    WithdrawC1ParticipantRequest,
)
from psyteardown.product import (
    C1_ACCESS_POLICY,
    C1_CONSENT_POLICY_REVISION,
    C1_CONSENT_STATEMENT,
    C1_DATA_CATEGORIES,
    C1_EVIDENCE_CEILING,
    C1_RETENTION_POLICY,
    C1_SOURCE_LAYER,
    C1_TRIAL_PAUSED_MESSAGE,
    C1_WITHDRAWAL_POLICY,
    ProductC1ObservationService,
)


router = APIRouter(tags=["product-c1-observations"])
C1Service = Annotated[ProductC1ObservationService, Depends(get_product_c1_service)]


@router.get("/c1-policy", response_model=C1PolicyResponse)
async def get_c1_policy(service: C1Service) -> C1PolicyResponse:
    return C1PolicyResponse(
        trial_state="available" if service.trial_enabled else "paused",
        trial_status_message="本地 C1 试用可启动。" if service.trial_enabled else C1_TRIAL_PAUSED_MESSAGE,
        consent_policy_revision=C1_CONSENT_POLICY_REVISION,
        statement=C1_CONSENT_STATEMENT,
        access_policy=list(C1_ACCESS_POLICY),
        data_categories=list(C1_DATA_CATEGORIES),
        retention_policy=C1_RETENTION_POLICY,
        withdrawal_policy=C1_WITHDRAWAL_POLICY,
        source_layer=C1_SOURCE_LAYER,
        evidence_ceiling=C1_EVIDENCE_CEILING,
    )


@router.post(
    "/projects/{project_id}/c1/envelopes",
    response_model=C1TrialEnvelopeResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def start_c1_envelope(project_id: str, request: StartC1EnvelopeRequest, service: C1Service) -> C1TrialEnvelopeResponse:
    return C1TrialEnvelopeResponse.from_domain(service.start_envelope(
        project_id=project_id,
        measurement_plan_revision_id=request.measurement_plan_revision_id,
        delivery_bundle_id=request.delivery_bundle_id,
        execution_job_revision_id=request.execution_job_revision_id,
        web_generation_contract_revision_id=request.web_generation_contract_revision_id,
        host=request.host,
        actor=request.actor,
        reason=request.reason,
    ))


@router.get(
    "/projects/{project_id}/c1/envelopes",
    response_model=list[C1TrialEnvelopeResponse],
    responses=ERROR_RESPONSES,
)
async def list_c1_envelopes(project_id: str, service: C1Service) -> list[C1TrialEnvelopeResponse]:
    return [C1TrialEnvelopeResponse.from_domain(item) for item in service.list_envelopes(project_id)]


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/close",
    response_model=C1TrialEnvelopeResponse,
    responses=ERROR_RESPONSES,
)
async def close_c1_envelope(project_id: str, envelope_id: str, request: EndC1EnvelopeRequest, service: C1Service) -> C1TrialEnvelopeResponse:
    return C1TrialEnvelopeResponse.from_domain(service.close_envelope(
        project_id=project_id, envelope_id=envelope_id, actor=request.actor, reason=request.reason,
    ))


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/stop",
    response_model=C1TrialEnvelopeResponse,
    responses=ERROR_RESPONSES,
)
async def stop_c1_envelope(project_id: str, envelope_id: str, request: EndC1EnvelopeRequest, service: C1Service) -> C1TrialEnvelopeResponse:
    return C1TrialEnvelopeResponse.from_domain(service.stop_envelope(
        project_id=project_id, envelope_id=envelope_id, actor=request.actor, reason=request.reason,
    ))


@router.get(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/participants",
    response_model=list[C1ParticipantResponse],
    responses=ERROR_RESPONSES,
)
async def list_c1_participants(project_id: str, envelope_id: str, service: C1Service) -> list[C1ParticipantResponse]:
    return [C1ParticipantResponse.from_domain(item) for item in service.list_participants(project_id, envelope_id)]


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/participants",
    response_model=C1EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def enroll_c1_participant(project_id: str, envelope_id: str, request: EnrollC1ParticipantRequest, service: C1Service) -> C1EnrollmentResponse:
    participant, receipt = service.enroll_participant(
        project_id=project_id,
        envelope_id=envelope_id,
        consent_policy_revision=request.consent_policy_revision,
        consent_scope_acknowledged=request.consent_scope_acknowledged,
        actor=request.actor,
        reason=request.reason,
    )
    return C1EnrollmentResponse(
        participant=C1ParticipantResponse.from_domain(participant),
        consent_receipt=C1ConsentReceiptResponse.from_domain(receipt),
    )


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/presentations",
    response_model=C1TaskPresentationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def present_c1_task(project_id: str, envelope_id: str, request: PresentC1TaskRequest, service: C1Service) -> C1TaskPresentationResponse:
    return C1TaskPresentationResponse.from_domain(service.present_task(
        project_id=project_id,
        envelope_id=envelope_id,
        participant_id=request.participant_id,
        task_id=request.task_id,
        actor=request.actor,
        reason=request.reason,
    ))


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/observations",
    response_model=C1OutcomeObservationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def record_c1_observation(project_id: str, envelope_id: str, request: RecordC1ObservationRequest, service: C1Service) -> C1OutcomeObservationResponse:
    return C1OutcomeObservationResponse.from_domain(service.record_observation(
        project_id=project_id,
        envelope_id=envelope_id,
        participant_id=request.participant_id,
        presentation_id=request.presentation_id,
        measure_id=request.measure_id,
        value=request.value,
        status=request.status,
        completion_cause=request.completion_cause,
        actor=request.actor,
        reason=request.reason,
    ))


@router.get(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/observations",
    response_model=list[C1OutcomeObservationResponse],
    responses=ERROR_RESPONSES,
)
async def list_c1_observations(project_id: str, envelope_id: str, service: C1Service) -> list[C1OutcomeObservationResponse]:
    return [C1OutcomeObservationResponse.from_domain(item) for item in service.list_observations(project_id, envelope_id)]


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/withdrawals/{participant_id}",
    response_model=C1WithdrawalTombstoneResponse,
    responses=ERROR_RESPONSES,
)
async def withdraw_c1_participant(project_id: str, envelope_id: str, participant_id: str, request: WithdrawC1ParticipantRequest, service: C1Service) -> C1WithdrawalTombstoneResponse:
    return C1WithdrawalTombstoneResponse.from_domain(service.withdraw_participant(
        project_id=project_id,
        envelope_id=envelope_id,
        participant_id=participant_id,
        actor=request.actor,
        reason=request.reason,
    ))


@router.post(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/reviews",
    response_model=C1EvidenceReviewResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def review_c1_evidence(project_id: str, envelope_id: str, request: ReviewC1EvidenceRequest, service: C1Service) -> C1EvidenceReviewResponse:
    return C1EvidenceReviewResponse.from_domain(service.review_evidence(
        project_id=project_id,
        envelope_id=envelope_id,
        observation_ids=request.observation_ids,
        reviewer=request.reviewer,
        decision=request.decision,
        evidence_level_after=request.evidence_level_after,
        rationale=request.rationale,
        limitations=request.limitations,
    ))


@router.get(
    "/projects/{project_id}/c1/envelopes/{envelope_id}/reviews",
    response_model=list[C1EvidenceReviewResponse],
    responses=ERROR_RESPONSES,
)
async def list_c1_reviews(project_id: str, envelope_id: str, service: C1Service) -> list[C1EvidenceReviewResponse]:
    return [C1EvidenceReviewResponse.from_domain(item) for item in service.list_reviews(project_id, envelope_id)]


