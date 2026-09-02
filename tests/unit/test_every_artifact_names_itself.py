"""Every artifact carries a document title in its metadata.

The conformance audit (2026-09-02) compiled the golden under Typst's own PDF/UA-1
enforcement, and the missing document title was the one mechanical violation it named.
The title is also what a browser tab, a file manager preview and assistive technology
call the document -- a client artifact should name itself. Substituted values keep the
title specific to the document, not to the family.
"""

from __future__ import annotations

import io
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

EXPECTED_TITLES = {
    "portfolio-review/v1": "PB SG Global Balanced - Portfolio review",
    "outcome-review/v1": "Outcome review",
    "proof-pack/v1": "Proof pack",
    "rebalance-wave/v1": "Rebalance wave",
}


@pytest.mark.parametrize("family", sorted(EXPECTED_TITLES))
def test_the_artifact_metadata_carries_a_specific_title(family: str) -> None:
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    package = RenderPackage.model_validate_json(
        Path(f"tests/golden/{family}/render-package.json").read_text(encoding="utf-8")
    )

    rendered = service.render(package)
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    metadata = reader.metadata
    assert metadata is not None, f"{family} carries no document information at all"
    title = str(metadata.title or "")

    assert title.startswith(EXPECTED_TITLES[family]), (
        f"{family} produced title {title!r}; a client artifact names itself"
    )
