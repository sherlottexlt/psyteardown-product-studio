"""FastAPI application factory for the local-first Product Studio API."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from psyteardown.api.errors import error_response, register_error_handlers
from psyteardown.api.projects import router as projects_router
from psyteardown.api.proposal_jobs import router as proposal_jobs_router
from psyteardown.api.generation_jobs import policy_router as source_model_policy_router
from psyteardown.api.generation_jobs import router as generation_jobs_router
from psyteardown.api.execution_jobs import router as execution_jobs_router
from psyteardown.api.repair_jobs import router as repair_jobs_router
from psyteardown.api.delivery_bundles import router as delivery_bundles_router
from psyteardown.api.preview_feedback import router as preview_feedback_router
from psyteardown.api.c1 import router as c1_router
from psyteardown.api.schemas import HealthResponse
from psyteardown.product import (
    ProductApplicationService,
    InMemoryProductJobRepository,
    ProductGenerationJobService,
    InMemoryProductGenerationJobRepository,
    ProductExecutionJobService,
    InMemoryProductExecutionJobRepository,
    ProductRepairJobService,
    InMemoryProductRepairJobRepository,
    ProductDeliveryBundleService,
    InMemoryProductDeliveryBundleRepository,
    ProductPreviewFeedbackService,
    InMemoryPreviewFeedbackRepository,
    ProductProposalJobService,
    SQLiteProductRepository,
    InMemoryC1Repository,
    SQLiteC1Repository,
    ProductC1ObservationService,
)
from psyteardown.product.source_model import ProductSourceModel, build_source_model_from_env
from psyteardown.product.contract_model import build_contract_model_from_env
from psyteardown.product.providers import RealModelProductContractProvider


DEFAULT_PRODUCT_STORE = Path("output/product-studio/product.sqlite3")
DEFAULT_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "testserver"})
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def create_app(
    *,
    database_path: Path | str | None = None,
    service: ProductApplicationService | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[str], str] | None = None,
    job_service: ProductProposalJobService | None = None,
    generation_job_service: ProductGenerationJobService | None = None,
    execution_job_service: ProductExecutionJobService | None = None,
    repair_job_service: ProductRepairJobService | None = None,
    delivery_bundle_service: ProductDeliveryBundleService | None = None,
    source_model: ProductSourceModel | None = None,
    allowed_hosts: Sequence[str] = tuple(DEFAULT_ALLOWED_HOSTS),
    allowed_origins: Sequence[str] = DEFAULT_ALLOWED_ORIGINS,
    c1_trial_enabled: bool | None = None,
) -> FastAPI:
    """Create an API app without opening persistence until lifespan starts."""

    owns_repository = service is None
    resolved_path = Path(
        database_path
        or os.getenv("PSYTEARDOWN_PRODUCT_STORE", str(DEFAULT_PRODUCT_STORE))
    )
    resolved_c1_trial_enabled = (
        c1_trial_enabled
        if c1_trial_enabled is not None
        else os.getenv("PSYTEARDOWN_C1_TRIAL_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = None
        if service is not None:
            app.state.product_service = service
            feedback_repository = InMemoryPreviewFeedbackRepository()
            app.state.product_job_service = job_service or ProductProposalJobService(
                service,
                InMemoryProductJobRepository(),
                feedback_repository=feedback_repository,
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            app.state.product_generation_job_service = generation_job_service or ProductGenerationJobService(
                service,
                InMemoryProductGenerationJobRepository(),
                workspace_root=Path("output/product-studio/workspaces"),
                source_model=source_model,
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            generation_repository = getattr(app.state.product_generation_job_service, "job_repository", None)
            app.state.product_execution_job_service = execution_job_service or ProductExecutionJobService(
                service,
                InMemoryProductExecutionJobRepository(generation_repository),
                generation_repository or InMemoryProductGenerationJobRepository(),
                workspace_root=getattr(
                    app.state.product_generation_job_service,
                    "workspace_root",
                    Path("output/product-studio/workspaces"),
                ),
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            execution_repository = getattr(app.state.product_execution_job_service, "job_repository", None)
            app.state.product_repair_job_service = repair_job_service or ProductRepairJobService(
                service,
                InMemoryProductRepairJobRepository(),
                generation_repository or InMemoryProductGenerationJobRepository(),
                execution_repository or InMemoryProductExecutionJobRepository(generation_repository),
                app.state.product_execution_job_service,
                workspace_root=getattr(
                    app.state.product_generation_job_service,
                    "workspace_root",
                    Path("output/product-studio/workspaces"),
                ),
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            workspace_root = getattr(
                app.state.product_generation_job_service,
                "workspace_root",
                Path("output/product-studio/workspaces"),
            )
            app.state.product_delivery_bundle_service = delivery_bundle_service or ProductDeliveryBundleService(
                service,
                InMemoryProductDeliveryBundleRepository(),
                generation_repository or InMemoryProductGenerationJobRepository(),
                execution_repository or InMemoryProductExecutionJobRepository(generation_repository),
                workspace_root=workspace_root,
                export_root=Path(workspace_root).parent / "exports",
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            app.state.product_preview_feedback_service = ProductPreviewFeedbackService(
                service,
                feedback_repository,
                app.state.product_delivery_bundle_service,
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
            app.state.product_c1_service = ProductC1ObservationService(
                service, app.state.product_delivery_bundle_service, InMemoryC1Repository(),
                trial_enabled=resolved_c1_trial_enabled,
                **({"clock": clock} if clock is not None else {}),
                **({"id_factory": id_factory} if id_factory is not None else {}),
            )
        else:
            repository = SQLiteProductRepository(resolved_path)
            kwargs = {}
            if clock is not None:
                kwargs["clock"] = clock
            if id_factory is not None:
                kwargs["id_factory"] = id_factory
            app.state.product_service = ProductApplicationService(
                repository, **kwargs
            )
            contract_model = build_contract_model_from_env()
            app.state.product_job_service = ProductProposalJobService(
                app.state.product_service,
                repository,
                feedback_repository=repository,
                real_provider=(
                    RealModelProductContractProvider() if contract_model is not None else None
                ),
                **kwargs,
            )
            app.state.product_generation_job_service = ProductGenerationJobService(
                app.state.product_service,
                repository,
                workspace_root=resolved_path.parent / "workspaces",
                source_model=source_model if source_model is not None else build_source_model_from_env(),
                **kwargs,
            )
            app.state.product_execution_job_service = ProductExecutionJobService(
                app.state.product_service,
                repository,
                repository,
                workspace_root=resolved_path.parent / "workspaces",
                **kwargs,
            )
            app.state.product_repair_job_service = ProductRepairJobService(
                app.state.product_service,
                repository,
                repository,
                repository,
                app.state.product_execution_job_service,
                workspace_root=resolved_path.parent / "workspaces",
                **kwargs,
            )
            app.state.product_delivery_bundle_service = ProductDeliveryBundleService(
                app.state.product_service,
                repository,
                repository,
                repository,
                workspace_root=resolved_path.parent / "workspaces",
                export_root=resolved_path.parent / "exports",
                **kwargs,
            )
            app.state.product_preview_feedback_service = ProductPreviewFeedbackService(
                app.state.product_service,
                repository,
                app.state.product_delivery_bundle_service,
                **kwargs,
            )
            app.state.product_c1_service = ProductC1ObservationService(
                app.state.product_service, app.state.product_delivery_bundle_service,
                SQLiteC1Repository(resolved_path),
                trial_enabled=resolved_c1_trial_enabled,
                **kwargs,
            )
        try:
            yield
        finally:
            app.state.product_service = None
            app.state.product_job_service = None
            app.state.product_generation_job_service = None
            app.state.product_execution_job_service = None
            app.state.product_repair_job_service = None
            app.state.product_delivery_bundle_service = None
            app.state.product_preview_feedback_service = None
            c1_service = getattr(app.state, "product_c1_service", None)
            if c1_service is not None:
                c1_service.repository.close()
            app.state.product_c1_service = None
            if owns_repository and repository is not None:
                repository.close()

    application = FastAPI(
        title="psyteardown Product Studio API",
        version="0.1.0",
        description=(
            "Local-first command and projection API for Product Studio. "
            "Proposal and generation work is created as a persisted job; an "
            "explicit run command performs only the bounded local step. "
            "Generated source is never executed by the generation job; a separate, "
            "explicit B4 execution job provides bounded build, preview and browser validation. "
            "A B5 repair job may apply only deterministic, allowlisted patches in a new lineage. "
            "A B6 delivery bundle is an immutable, content-addressed export of one verified execution. "
            "B7 previews a delivered build and records only explicit, consented, withdrawable feedback. "
            "B8 lets one feedback report drive a new, human-confirmed contract revision and compares deliveries."
        ),
        lifespan=lifespan,
    )
    register_error_handlers(application)

    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    allowed_host_set = frozenset(allowed_hosts)

    @application.middleware("http")
    async def local_request_boundary(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            supplied_request_id
            if _SAFE_REQUEST_ID.fullmatch(supplied_request_id)
            else uuid4().hex
        )
        host = request.url.hostname
        if allowed_host_set and host not in allowed_host_set:
            return error_response(
                request,
                status_code=400,
                code="host_not_allowed",
                message="Host is not allowed for this local Product Studio API",
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.get(
        "/api/v1/health", response_model=HealthResponse, tags=["system"]
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    application.include_router(projects_router, prefix="/api/v1")
    application.include_router(proposal_jobs_router, prefix="/api/v1")
    application.include_router(generation_jobs_router, prefix="/api/v1")
    application.include_router(source_model_policy_router, prefix="/api/v1")
    application.include_router(execution_jobs_router, prefix="/api/v1")
    application.include_router(repair_jobs_router, prefix="/api/v1")
    application.include_router(delivery_bundles_router, prefix="/api/v1")
    application.include_router(preview_feedback_router, prefix="/api/v1")
    application.include_router(c1_router, prefix="/api/v1")
    return application


def run() -> None:
    """Run the localhost-only development API."""

    import uvicorn

    uvicorn.run(
        "psyteardown.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


app = create_app()
