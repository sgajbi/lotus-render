"""Compatibility and runtime identity remain format-specific at the engine port."""

from unittest.mock import Mock

import pytest

from app.contracts.examples import load_portfolio_review_render_package_example
from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateCompatibilityError
from app.services.render_dispatch import FormatRenderService
from app.services.render_ports import RenderRuntimeMetadata, package_runtime_metadata


def _package(output: str) -> RenderPackage:
    payload = load_portfolio_review_render_package_example()
    payload["output_format"] = output
    return RenderPackage.model_validate(payload)


def _engine(name: str) -> Mock:
    engine = Mock()
    engine.runtime_metadata = RenderRuntimeMetadata(name, "v1")
    return engine


def test_dispatch_selects_engine_and_admission_provenance_from_package_format() -> None:
    intake = Mock()
    intake.validate_package.return_value.runtime_engine = "xlsxwriter"
    pdf, xlsx = _engine("typst"), _engine("xlsxwriter")
    service = FormatRenderService(intake, {"pdf": pdf, "xlsx": xlsx}, ("pdf", "xlsx"))
    package = _package("xlsx")
    assert package_runtime_metadata(service, package) == xlsx.runtime_metadata
    assert service.render(package) is xlsx.render.return_value
    pdf.render.assert_not_called()


@pytest.mark.parametrize(
    "output,supported,engine",
    [
        ("unknown", ("pdf", "xlsx"), "typst"),
        ("xlsx", ("pdf",), "xlsxwriter"),
        ("xlsx", ("pdf", "xlsx"), "typst"),
    ],
)
def test_unsupported_format_setting_or_template_engine_never_executes(
    output: str, supported: tuple[str, ...], engine: str
) -> None:
    intake = Mock()
    intake.validate_package.return_value.runtime_engine = engine
    pdf, xlsx = _engine("typst"), _engine("xlsxwriter")
    service = FormatRenderService(intake, {"pdf": pdf, "xlsx": xlsx}, supported)
    with pytest.raises(TemplateCompatibilityError):
        service.render(_package(output))
    pdf.render.assert_not_called()
    xlsx.render.assert_not_called()


def test_registry_refusal_precedes_render_engine_execution() -> None:
    intake = Mock()
    intake.validate_package.side_effect = TemplateCompatibilityError(
        reason="template_not_supported", message="template_not_supported"
    )
    pdf = _engine("typst")
    service = FormatRenderService(intake, {"pdf": pdf}, ("pdf",))
    with pytest.raises(TemplateCompatibilityError, match="template_not_supported"):
        service.render(_package("pdf"))
    pdf.render.assert_not_called()


def test_dispatch_requires_pdf_compatibility() -> None:
    with pytest.raises(ValueError, match="pdf_render_engine_required"):
        FormatRenderService(Mock(), {}, ("xlsx",))
