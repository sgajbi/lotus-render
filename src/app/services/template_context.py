from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.contracts.render_package import RenderPackage

TemplateContext = dict[str, str]
TemplateContextBuilder = Callable[[RenderPackage], TemplateContext]


@dataclass(frozen=True, slots=True)
class TemplateContextRenderer:
    report_type: str
    template_id: str
    template_version: str
    build_context: TemplateContextBuilder

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.report_type, self.template_id, self.template_version)


class TemplateContextRegistry:
    def __init__(self, renderers: tuple[TemplateContextRenderer, ...]) -> None:
        self._renderers = {renderer.key: renderer for renderer in renderers}
        if len(self._renderers) != len(renderers):
            raise ValueError("duplicate_template_context_renderer")

    def build_context(self, render_package: RenderPackage) -> TemplateContext:
        key = (
            render_package.report_type,
            render_package.template_id,
            render_package.template_version,
        )
        renderer = self._renderers.get(key)
        if renderer is None:
            raise ValueError(
                "unsupported template context renderer: "
                f"{render_package.report_type}/{render_package.template_id}/"
                f"{render_package.template_version}"
            )
        return renderer.build_context(render_package)

    def supported_keys(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(sorted(self._renderers))
