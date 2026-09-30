"""HTTP boundary for bounded Web source-generation jobs."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, status

from psyteardown.api.dependencies import get_product_generation_job_service
from psyteardown.api.projects import ERROR_RESPONSES
from psyteardown.api.schemas import (
    CreateGenerationJobRequest,
    GenerationJobActionRequest,
    ModelCallTranscriptResponse,
    ProductGenerationJobResponse,
    SourceModelPolicyResponse,
)
from psyteardown.experience.models import DomainStateError
from psyteardown.product import (
    GENERATION_MODEL_MAX_CALLS,
    GENERATION_MODEL_SOURCE_PATHS,
    SOURCE_MODEL_NOT_SENT,
    SOURCE_MODEL_RETENTION,
    SOURCE_MODEL_SENT,
    GenerationBudget,
    ProductGenerationJobService,
)


router = APIRouter(prefix="/projects", tags=["product-generation-jobs"])
policy_router = APIRouter(tags=["product-generation-jobs"])
GenerationService = Annotated[
    ProductGenerationJobService, Depends(get_product_generation_job_service)
]


@policy_router.get("/source-model-policy", response_model=SourceModelPolicyResponse)
async def get_source_model_policy(service: GenerationService) -> SourceModelPolicyResponse:
    model = service.source_model
    return SourceModelPolicyResponse(
        available=model is not None,
        provider=getattr(model, "name", None),
        model=getattr(model, "model", None),
        sent=list(SOURCE_MODEL_SENT),
        not_sent=list(SOURCE_MODEL_NOT_SENT),
        retention=SOURCE_MODEL_RETENTION,
        max_calls_per_job=GENERATION_MODEL_MAX_CALLS,
        model_writes=list(GENERATION_MODEL_SOURCE_PATHS),
        repair_uses_model=False,
    )


@router.post(
    "/{project_id}/generation-jobs",
    response_model=ProductGenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_generation_job(
    project_id: str,
    request: CreateGenerationJobRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    budget = GenerationBudget(**request.budget.model_dump()) if request.budget else None
    return ProductGenerationJobResponse.from_domain(
        service.create_job(
            project_id=project_id,
            actor=request.actor,
            reason=request.reason,
            budget=None if request.source == "model" else budget,
            source=request.source,
        )
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/saved-source-materializations",
    response_model=ProductGenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_saved_source_materialization(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    """Create an independent B3 child job from a saved, locally revalidated source."""
    return ProductGenerationJobResponse.from_domain(
        service.create_saved_source_job(
            project_id=project_id,
            source_job_id=job_id,
            actor=request.actor,
            reason="Create a new workspace lineage from locally saved model source without another provider call",
        )
    )


@router.get(
    "/{project_id}/generation-jobs/{job_id}/model-calls/{attempt}",
    response_model=ModelCallTranscriptResponse,
    responses=ERROR_RESPONSES,
)
async def get_model_call_transcript(
    project_id: str, job_id: str, attempt: int, service: GenerationService
) -> ModelCallTranscriptResponse:
    job = service.get_job(project_id, job_id)
    path = service.transcript_path(job, attempt)
    if not path.is_file():
        raise DomainStateError(f"unknown model call transcript: {attempt}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ModelCallTranscriptResponse(
        attempt=payload["attempt"],
        provider=payload["provider"],
        model=payload.get("response_model") or payload["model"],
        system=payload["system"],
        prompt=payload["prompt"],
        response=payload.get("response"),
        gate=payload.get("gate"),
        provider_gate=payload.get("provider_gate"),
        gate_revalidations=payload.get("gate_revalidations", []),
        static_gate_version=payload.get("static_gate_version"),
        error=payload.get("error"),
    )


@router.get(
    "/{project_id}/generation-jobs",
    response_model=list[ProductGenerationJobResponse],
    responses=ERROR_RESPONSES,
)
async def list_generation_jobs(
    project_id: str, service: GenerationService
) -> list[ProductGenerationJobResponse]:
    return [
        ProductGenerationJobResponse.from_domain(job)
        for job in service.list_jobs(project_id)
    ]


@router.get(
    "/{project_id}/generation-jobs/{job_id}",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def get_generation_job(
    project_id: str, job_id: str, service: GenerationService
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(service.get_job(project_id, job_id))


@router.post(
    "/{project_id}/generation-jobs/{job_id}/runs",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def run_generation_job(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(
        service.run_job(project_id, job_id, actor=request.actor)
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/pauses",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def pause_generation_job(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(
        service.pause_job(project_id, job_id, actor=request.actor)
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/resumes",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def resume_generation_job(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(
        service.resume_job(project_id, job_id, actor=request.actor)
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/cancellations",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def cancel_generation_job(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(
        service.cancel_job(project_id, job_id, actor=request.actor)
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/revalidations",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def revalidate_saved_model_draft(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    """Re-run the local static gate on a saved rejected draft without calling a provider."""
    return ProductGenerationJobResponse.from_domain(
        service.revalidate_saved_model_draft(
            project_id, job_id, actor=request.actor
        )
    )


@router.post(
    "/{project_id}/generation-jobs/{job_id}/retries",
    response_model=ProductGenerationJobResponse,
    responses=ERROR_RESPONSES,
)
async def retry_generation_job(
    project_id: str,
    job_id: str,
    request: GenerationJobActionRequest,
    service: GenerationService,
) -> ProductGenerationJobResponse:
    return ProductGenerationJobResponse.from_domain(
        service.retry_job(project_id, job_id, actor=request.actor)
    )
