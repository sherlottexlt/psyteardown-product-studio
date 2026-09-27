"""HTTP boundary for explicitly authorized B4 execution jobs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from psyteardown.api.dependencies import get_product_execution_job_service
from psyteardown.api.projects import ERROR_RESPONSES
from psyteardown.api.schemas import (
    CreateExecutionJobRequest,
    ExecutionJobActionRequest,
    ExecutionJobResponse,
)
from psyteardown.product import ExecutionBudget, ProductExecutionJobService


router = APIRouter(prefix="/projects", tags=["product-execution-jobs"])
ExecutionService = Annotated[
    ProductExecutionJobService, Depends(get_product_execution_job_service)
]


@router.post(
    "/{project_id}/execution-jobs",
    response_model=ExecutionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_execution_job(
    project_id: str,
    request: CreateExecutionJobRequest,
    service: ExecutionService,
) -> ExecutionJobResponse:
    budget = ExecutionBudget(**request.budget.model_dump()) if request.budget else None
    return ExecutionJobResponse.from_domain(
        service.create_job(
            project_id=project_id,
            generation_job_id=request.generation_job_id,
            actor=request.actor,
            reason=request.reason,
            budget=budget,
        )
    )


@router.get(
    "/{project_id}/execution-jobs",
    response_model=list[ExecutionJobResponse],
    responses=ERROR_RESPONSES,
)
async def list_execution_jobs(
    project_id: str, service: ExecutionService
) -> list[ExecutionJobResponse]:
    return [ExecutionJobResponse.from_domain(job) for job in service.list_jobs(project_id)]


@router.get(
    "/{project_id}/execution-jobs/{job_id}",
    response_model=ExecutionJobResponse,
    responses=ERROR_RESPONSES,
)
async def get_execution_job(
    project_id: str, job_id: str, service: ExecutionService
) -> ExecutionJobResponse:
    return ExecutionJobResponse.from_domain(service.get_job(project_id, job_id))


@router.post(
    "/{project_id}/execution-jobs/{job_id}/runs",
    response_model=ExecutionJobResponse,
    responses=ERROR_RESPONSES,
)
async def run_execution_job(
    project_id: str,
    job_id: str,
    request: ExecutionJobActionRequest,
    service: ExecutionService,
) -> ExecutionJobResponse:
    return ExecutionJobResponse.from_domain(service.run_job(project_id, job_id, actor=request.actor))


@router.post(
    "/{project_id}/execution-jobs/{job_id}/cancellations",
    response_model=ExecutionJobResponse,
    responses=ERROR_RESPONSES,
)
async def cancel_execution_job(
    project_id: str,
    job_id: str,
    request: ExecutionJobActionRequest,
    service: ExecutionService,
) -> ExecutionJobResponse:
    return ExecutionJobResponse.from_domain(service.cancel_job(project_id, job_id, actor=request.actor))


@router.post(
    "/{project_id}/execution-jobs/{job_id}/recoveries",
    response_model=ExecutionJobResponse,
    responses=ERROR_RESPONSES,
)
async def recover_execution_job(
    project_id: str,
    job_id: str,
    request: ExecutionJobActionRequest,
    service: ExecutionService,
) -> ExecutionJobResponse:
    return ExecutionJobResponse.from_domain(
        service.recover_job(
            project_id,
            job_id,
            actor=request.actor,
            confirm_orphaned=request.confirm_orphaned,
        )
    )


@router.post(
    "/{project_id}/execution-jobs/{job_id}/retries",
    response_model=ExecutionJobResponse,
    responses=ERROR_RESPONSES,
)
async def retry_execution_job(
    project_id: str,
    job_id: str,
    request: ExecutionJobActionRequest,
    service: ExecutionService,
) -> ExecutionJobResponse:
    return ExecutionJobResponse.from_domain(service.retry_job(project_id, job_id, actor=request.actor))
