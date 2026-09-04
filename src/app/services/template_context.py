from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.contracts.render_package import RenderPackage
from app.services.typst_contexts import (
    build_outcome_review_context,
    build_portfolio_review_context,
    build_portfolio_review_v2_context,
    build_portfolio_review_v3_context,
    build_proof_pack_context,
    build_wave_context,
)

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


def default_template_context_registry() -> TemplateContextRegistry:
    """Every (report_type, template, version) this service can populate.

    Declarative configuration, kept beside the registry it fills rather than
    inside the engine that consumes it.
    """
    return TemplateContextRegistry(
        (
            TemplateContextRenderer(
                report_type="portfolio_review",
                template_id="portfolio-review",
                template_version="v1",
                build_context=build_portfolio_review_context,
            ),
            TemplateContextRenderer(
                report_type="portfolio_review",
                template_id="portfolio-review",
                template_version="v2",
                build_context=build_portfolio_review_v2_context,
            ),
            TemplateContextRenderer(
                report_type="portfolio_review",
                template_id="portfolio-review",
                template_version="v3",
                build_context=build_portfolio_review_v3_context,
            ),
            TemplateContextRenderer(
                report_type="proof_pack",
                template_id="proof-pack",
                template_version="v1",
                build_context=build_proof_pack_context,
            ),
            TemplateContextRenderer(
                report_type="outcome_review",
                template_id="outcome-review",
                template_version="v1",
                build_context=build_outcome_review_context,
            ),
            TemplateContextRenderer(
                report_type="rebalance_wave",
                template_id="rebalance-wave",
                template_version="v1",
                build_context=build_wave_context,
            ),
        )
    )
