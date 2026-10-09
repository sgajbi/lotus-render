"""Format selection inside the existing render engine boundary and lifecycle."""

from app.contracts.render_package import RenderPackage
from app.domain.rendering.models import RenderResult
from app.domain.templates.registry import TemplateCompatibilityError
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderEnginePort, RenderRuntimeMetadata


class FormatRenderService:
    def __init__(
        self,
        intake: RenderIntakeService,
        engines: dict[str, RenderEnginePort],
        supported_output_formats: tuple[str, ...],
    ) -> None:
        if "pdf" not in engines:
            raise ValueError("pdf_render_engine_required")
        self._intake = intake
        self._engines = dict(engines)
        self._supported_output_formats = supported_output_formats

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return self._engines["pdf"].runtime_metadata

    def runtime_metadata_for(self, package: RenderPackage) -> RenderRuntimeMetadata:
        # Unknown formats still reach normal package validation and persisted refusal.
        engine = self._engines.get(package.output_format, self._engines["pdf"])
        return engine.runtime_metadata

    def render(self, render_package: RenderPackage) -> RenderResult:
        manifest = self._intake.validate_package(render_package)
        engine = self._engines.get(render_package.output_format)
        if engine is None or render_package.output_format not in self._supported_output_formats:
            raise TemplateCompatibilityError(
                reason="output_format_not_supported", message="output_format_not_supported"
            )
        metadata = engine.runtime_metadata
        if manifest.runtime_engine != metadata.runtime_engine:
            raise TemplateCompatibilityError(
                reason="runtime_engine_not_supported", message="template_runtime_engine_mismatch"
            )
        return engine.render(render_package)
