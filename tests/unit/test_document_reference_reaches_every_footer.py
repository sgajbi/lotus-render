"""The governed document reference reaches every family's footer, or nothing does.

The evidence-chain decision (#158, #120): Report mints one externally meaningful
document reference before render and supplies it in the render context; Render places it
verbatim, the same way in every family -- no family invents its own provenance treatment,
and internal trace/correlation ids are not a client-facing identity. Given a returned
PDF, the reference is now on the page; given a package without one, the artifact is
byte-identical to what it always was.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

REFERENCE = "LR-DOC-2026-000123"

FAMILIES = [
    "portfolio-review/v1",
    "outcome-review/v1",
    "proof-pack/v1",
    "rebalance-wave/v1",
]


def _document(family: str, reference: object) -> str:
    package = json.loads(
        Path(f"tests/golden/{family}/render-package.json").read_text(encoding="utf-8")
    )
    if reference is not None:
        package["render_context"]["document_reference"] = reference
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in reader.pages))


@pytest.mark.parametrize("family", FAMILIES)
def test_a_supplied_reference_is_placed_and_an_absent_one_is_not_invented(
    family: str,
) -> None:
    """One treatment, four families. The absent case matters as much: before this, the
    client-facing portfolio review carried no identity at all, and the fix must not
    swing to printing an identity nobody minted."""

    assert REFERENCE in _document(family, REFERENCE)
    assert REFERENCE not in _document(family, None)


def test_a_malformed_reference_is_not_coerced_into_an_identity() -> None:
    """A number is not a document reference; printing `12345` as one would be Render
    inventing identity, which is the forbidden move the chain exists to prevent."""

    document = _document("portfolio-review/v1", 12345)

    assert "12345" not in document


def test_every_family_places_the_reference_through_the_one_shared_treatment() -> None:
    """No family invents its own provenance treatment -- the defect #158 opened with
    was four families with four treatments. The shared component is the treatment."""

    for family in FAMILIES:
        main = Path(f"templates/typst/{family}/main.typ").read_text(encoding="utf-8")
        assert 'document-reference-mark("${DOCUMENT_REFERENCE}")' in main, (
            f"{family} does not place the document reference through the shared mark"
        )
