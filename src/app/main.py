from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.renders import router as renders_router
from app.api.routes.system import router as system_router
from app.core.logging import configure_logging
from app.core.settings import Settings, get_settings
from app.dependencies.container import AppContainer
from app.domain.templates.registry import TemplateRegistry
from app.infrastructure.render_store import RenderStore
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.http_boundary import RequestBodySizeLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.observability.render_metrics import validate_render_metric_contracts
from app.services.render_foundation import RenderFoundationService
from app.services.render_intake import RenderIntakeService
from app.services.render_runtime import RenderRuntimeProbe
from app.services.render_submission import RenderSubmissionService
from app.services.typst_rendering import TypstRenderService

SERVICE_NAME = "lotus-render"


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        app.state.settings = configured_settings
        template_registry = TemplateRegistry.load_from_directory(
            Path(configured_settings.template_registry_path)
        )
        render_store = RenderStore(Path(configured_settings.render_store_path))
        app.state.container = AppContainer(
            settings=configured_settings,
            render_foundation=RenderFoundationService(configured_settings),
            render_store=render_store,
            render_submission_service=RenderSubmissionService(
                render_store=render_store,
                render_engine=TypstRenderService(
                    configured_settings,
                    RenderIntakeService(template_registry),
                ),
            ),
            render_runtime_probe=RenderRuntimeProbe(),
            template_registry=template_registry,
        )
        app.state.is_draining = False
        app.state.template_registry = template_registry
        app.state.render_store = render_store
        app.state.render_foundation = app.state.container.render_foundation
        app.state.render_submission_service = app.state.container.render_submission_service
        yield

    app = FastAPI(
        title=configured_settings.service_name,
        version=configured_settings.service_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(configured_settings.allowed_hosts),
    )
    if configured_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(configured_settings.cors_allowed_origins),
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Correlation-Id",
                "X-Trace-Id",
                "traceparent",
            ],
        )
    app.add_middleware(
        RequestBodySizeLimitMiddleware,
        max_request_body_bytes=configured_settings.max_request_body_bytes,
    )
    app.add_middleware(CorrelationIdMiddleware, service_name=configured_settings.service_name)
    app.add_middleware(RequestLoggingMiddleware, service_name=configured_settings.service_name)
    validate_render_metric_contracts()
    Instrumentator().instrument(app).expose(app)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request, exc):  # type: ignore[no-untyped-def]
        field_paths = sorted(
            {
                ".".join(str(part) for part in error.get("loc", []) if part != "body")
                for error in exc.errors()
            }
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "render_package_invalid",
                    "message": "Render request validation failed.",
                    "field_paths": [path for path in field_paths if path],
                    "correlation_id": getattr(request.state, "correlation_id", None),
                    "trace_id": getattr(request.state, "trace_id", None),
                }
            },
        )

    app.include_router(system_router)
    app.include_router(renders_router)
    return app


app = create_app()
