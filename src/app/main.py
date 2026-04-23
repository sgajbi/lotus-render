from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes.system import router as system_router
from app.core.logging import configure_logging
from app.core.settings import Settings, get_settings
from app.domain.templates.registry import TemplateRegistry
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.render_foundation import RenderFoundationService

SERVICE_NAME = "lotus-render"


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        app.state.settings = configured_settings
        app.state.is_draining = False
        app.state.template_registry = TemplateRegistry.load_from_directory(
            Path(configured_settings.template_registry_path)
        )
        app.state.render_foundation = RenderFoundationService(configured_settings)
        yield

    app = FastAPI(
        title=configured_settings.service_name,
        version=configured_settings.service_version,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware, service_name=configured_settings.service_name)
    app.add_middleware(RequestLoggingMiddleware, service_name=configured_settings.service_name)
    Instrumentator().instrument(app).expose(app)
    app.include_router(system_router)
    return app


app = create_app()
