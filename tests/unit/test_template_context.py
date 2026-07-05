from __future__ import annotations

import pytest

from app.contracts.examples import load_portfolio_review_render_package_example
from app.contracts.render_package import RenderPackage
from app.services.template_context import TemplateContextRegistry, TemplateContextRenderer


def _package(**overrides: object) -> RenderPackage:
    payload = load_portfolio_review_render_package_example()
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


def test_template_context_registry_routes_registered_template_contexts() -> None:
    registry = TemplateContextRegistry(
        (
            TemplateContextRenderer(
                report_type="portfolio_review",
                template_id="portfolio-review",
                template_version="v1",
                build_context=lambda _package: {"ROUTED": "portfolio"},
            ),
        )
    )

    assert registry.supported_keys() == (("portfolio_review", "portfolio-review", "v1"),)
    assert registry.build_context(_package()) == {"ROUTED": "portfolio"}


def test_template_context_registry_rejects_unknown_template_contexts() -> None:
    registry = TemplateContextRegistry(())

    with pytest.raises(ValueError, match="unsupported template context renderer"):
        registry.build_context(_package(report_type="unknown", template_id="unknown"))


def test_template_context_registry_rejects_duplicate_registrations() -> None:
    renderer = TemplateContextRenderer(
        report_type="portfolio_review",
        template_id="portfolio-review",
        template_version="v1",
        build_context=lambda _package: {},
    )

    with pytest.raises(ValueError, match="duplicate_template_context_renderer"):
        TemplateContextRegistry((renderer, renderer))
