"""Golden proof at the granularity of a page.

The artifact fingerprint answers "did anything change". It cannot answer "what changed",
and it cannot answer "is this right". Six defects found in this repository were
byte-identical to themselves and so were green under it for as long as they existed:

- a performance bar that drew +18.4%, -14.2% and -38.4% identically (#151)
- gridlines rendered below the axis and off the canvas (#152)
- a chart card split from its title across a page break (#159)
- three families printing their own Typst source as body text (#165)
- amounts reaching a private-banking document ungrouped (#161)
- a weight bar floored at five times its true length (#170)

Every one was found by rasterising a page and looking at it. These hashes do not make
that unnecessary -- a wrong page is still identical to itself -- but they narrow it:
when a golden moves, the failure names the pages that moved, so the reader knows which
pages to open rather than the whole document.

The images come from the same pinned Typst container that produces the PDF, so this adds
no dependency, and PNG output carries no timestamp: a plain hash is stable where the PDF
needs eight patterns stripped from it first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService, page_image_hashes

FIXTURES_PATH = Path("tests/golden/producer-fixtures.v1.json")


def _fixtures() -> list[dict[str, object]]:
    manifest: dict[str, list[dict[str, object]]] = json.loads(
        FIXTURES_PATH.read_text(encoding="utf-8")
    )
    return manifest["fixtures"]


def _service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


@pytest.mark.parametrize(
    "fixture", _fixtures(), ids=lambda fixture: str(fixture["golden_sample_id"])
)
def test_every_page_matches_the_page_that_was_banked(fixture: dict[str, object]) -> None:
    banked = fixture.get("page_image_hashes")
    assert isinstance(banked, list) and banked, (
        f"{fixture['golden_sample_id']} has no banked page hashes; run "
        "`make golden-fixtures` to bank them"
    )

    package = RenderPackage.model_validate_json(
        Path(str(fixture["package_path"])).read_text(encoding="utf-8")
    )
    measured = page_image_hashes(_service(), package)

    assert len(measured) == len(banked), (
        f"the document is now {len(measured)} pages and was banked at {len(banked)}. "
        "A page appearing or disappearing is a layout change, not a content one."
    )

    moved = [index for index, (a, b) in enumerate(zip(banked, measured, strict=True), 1) if a != b]
    assert not moved, (
        f"pages {moved} render differently from what was banked. Look at them: a page can "
        "change in ways the artifact fingerprint reports identically -- a bar that hides "
        "its sign, a gridline outside the plot, a card split from its title. If the change "
        "is intended, re-bank with `make golden-fixtures` and say in the pull request what "
        "these pages now show."
    )


def test_page_hashes_are_banked_for_every_fixture() -> None:
    """A fixture with no page hashes is covered by the document fingerprint alone."""

    missing = [
        fixture["golden_sample_id"]
        for fixture in _fixtures()
        if not fixture.get("page_image_hashes")
    ]
    assert not missing, f"these fixtures have no banked page hashes: {missing}"
