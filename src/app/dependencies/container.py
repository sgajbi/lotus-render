from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.domain.templates.registry import TemplateRegistry
from app.infrastructure.render_store import RenderStore
from app.services.render_foundation import RenderFoundationService
from app.services.render_runtime import RenderRuntimeProbe
from app.services.render_submission import RenderSubmissionService


@dataclass(slots=True)
class AppContainer:
    render_foundation: RenderFoundationService
    render_store: RenderStore
    render_submission_service: RenderSubmissionService
    render_runtime_probe: RenderRuntimeProbe
    template_registry: TemplateRegistry
    is_draining: bool = False

    def render_store_ready(self) -> bool:
        try:
            self.render_store.check_ready()
        except RuntimeError:
            return False
        return True

    def template_registry_ready(self) -> bool:
        return self.template_registry is not None

    def render_runtime_available(self) -> bool:
        return self.render_runtime_probe.check_available().available


def get_app_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        raise RuntimeError("app_container_unavailable")
    return container


ContainerDependency = Annotated[AppContainer, Depends(get_app_container)]


def get_render_submission_service(
    container: ContainerDependency,
) -> RenderSubmissionService:
    return container.render_submission_service


RenderSubmissionDependency = Annotated[
    RenderSubmissionService,
    Depends(get_render_submission_service),
]
