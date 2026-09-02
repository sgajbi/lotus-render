"""Every artifact is PDF/A-2a, declared in its own metadata and enforced at compile.

The selected bank-grade output standard (#246 phase 5). Archival custody is what the
document evidence chain exists for, and the "a" level carries the tagged-structure
requirements phases 2-4 built. Conformance is an executable property: the compiler
refuses a violating document, so every render is the certification gate -- these tests
only pin that the claim is present and that determinism survived the flip (PDF/A writes
an XMP revision-history event whose timestamp and instance id vary per render; the
bounded fingerprint strips them like the creation dates it already stripped).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import PDF_STANDARD, TypstRenderService

FAMILIES = [
    "portfolio-review/v1",
    "outcome-review/v1",
    "proof-pack/v1",
    "rebalance-wave/v1",
]


def _service() -> TypstRenderService:
    settings = Settings()
    return TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )


def _package(family: str) -> RenderPackage:
    return RenderPackage.model_validate_json(
        Path(f"tests/golden/{family}/render-package.json").read_text(encoding="utf-8")
    )


def test_the_selected_standard_is_the_recorded_decision() -> None:
    assert PDF_STANDARD == "a-2a", (
        "the output standard is a recorded decision (#246 phase 5); moving it means "
        "re-running the conformance audit, not editing a constant"
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_the_artifact_declares_pdf_a_2a(family: str) -> None:
    artifact = _service().render(_package(family)).artifact_bytes

    part = re.search(rb"pdfaid:part[^0-9]{0,4}(\d)", artifact)
    conformance = re.search(rb"pdfaid:conformance[^A-Z]{0,4}([ABU])", artifact)

    assert part is not None and part.group(1) == b"2", f"{family} does not declare PDF/A-2"
    assert conformance is not None and conformance.group(1) == b"A", (
        f"{family} does not declare conformance level A"
    )


def test_two_renders_stay_deterministically_equivalent_under_the_standard() -> None:
    """PDF/A's XMP revision history varies per render; the bounded fingerprint must
    keep treating two renders of one package as the same document."""

    service = _service()
    package = _package("portfolio-review/v1")

    one = service.render(package).artifact_bytes
    two = service.render(package).artifact_bytes

    fingerprint = TypstRenderService._compute_bounded_determinism_fingerprint
    assert fingerprint(one) == fingerprint(two), (
        "two renders of the identical package diverged in the bounded fingerprint: "
        "the standard introduced a volatile byte pattern the fingerprint must strip"
    )
