from __future__ import annotations

from app.contracts.render_package import RenderPackage
from app.domain.templates.models import TemplateManifest
from app.domain.templates.registry import TemplateRegistry


class RenderIntakeService:
    def __init__(self, template_registry: TemplateRegistry) -> None:
        self._template_registry = template_registry

    def validate_package(self, render_package: RenderPackage) -> TemplateManifest:
        return self._template_registry.resolve_for_new_render(render_package)
