"""Every document carries real heading structure, not just heading-shaped text.

The conformance audit (#246) measured the tag tree and found zero H tags: section
titles were styled `#text`, invisible to assistive-technology navigation, and the
reading order had no anchors. Phase 2 makes the flow titles real `heading()` elements
-- one H1 (the document names itself once) and an H2 per section label -- styled
exactly as before, with heading block spacing pinned to each family's paragraph
spacing so the visual rhythm stayed.

Typst writes tagged PDF by default, so the structure is asserted on the ordinary
rendered artifact, no conformance flag involved.
"""

from __future__ import annotations

import collections
import io
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

# The H2 floor is a floor, not a bank: a new section subtitle adds a heading, and that
# is the system working. Falling below means subtitles stopped being headings.
MINIMUM_H2 = {
    "portfolio-review/v1": 13,
    "outcome-review/v1": 2,
    "proof-pack/v1": 1,
    "rebalance-wave/v1": 1,
}


def _structure_counts(family: str) -> collections.Counter[str]:
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
    counts: collections.Counter[str] = collections.Counter()

    def walk(node: object) -> None:
        obj = node.get_object()  # type: ignore[attr-defined]
        if not isinstance(obj, dict):
            return
        tag = obj.get("/S")
        if tag is not None:
            counts[str(tag)] += 1
        kids = obj.get("/K")
        if kids is None:
            return
        for kid in kids if isinstance(kids, list) else [kids]:
            if hasattr(kid, "get_object") and isinstance(kid.get_object(), dict):
                walk(kid)

    root = reader.trailer["/Root"].get_object()
    walk(root["/StructTreeRoot"])  # type: ignore[index]
    return counts


@pytest.mark.parametrize("family", sorted(MINIMUM_H2))
def test_the_tag_tree_carries_one_h1_and_the_section_headings(family: str) -> None:
    counts = _structure_counts(family)

    assert counts["/H1"] == 1, (
        f"{family} carries {counts['/H1']} H1 tags; the document names itself exactly "
        "once, and zero means the titles regressed to styled text"
    )
    assert counts["/H2"] >= MINIMUM_H2[family], (
        f"{family} carries {counts['/H2']} H2 tags against a floor of "
        f"{MINIMUM_H2[family]}: section labels stopped being headings"
    )
