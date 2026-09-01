"""What the data said is what the document shows.

The markup escaper stopped at the tokens that can introduce code -- ``#``, ``[``, ``$``
and their neighbours -- on the reasoning that a bare ``*`` cannot run anything. True, and
beside the point. Rendering an advisor narrative through the unfixed escaper:

    data:      MARKA *bold* MARKB _emph_ MARKC `raw` MARKD 5~10bp MARKE 2020--2021
    document:  MARKA bold MARKB emph MARKC raw MARKD 5 10bp MARKE 2020-2021

The asterisks deleted themselves and redrew the text bold, and ``5~10bp`` -- a range --
was drawn ``5 10bp``. A line beginning ``= `` became a heading and one beginning ``- ``
gained a bullet glyph the data did not contain. ``a<label>b`` was the worst of them: a
label draws nothing at all, so ``a<label>b`` reached the page as ``ab``.

None of it fails a compile, none of it looks broken, and the byte-identical golden was
green over all of it. So this reads the text back off the page.
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

NARRATIVE_PACKAGE = Path("tests/golden/portfolio-review/v1/advisory-narrative/render-package.json")

# Each fragment puts a markup token where Typst gives it meaning: a pair for the inline
# styles, the start of a line for the block ones, after content for a label. Written as
# prose a producer could plausibly send, because that is the point -- none of this is an
# attack, it is a report that happens to contain punctuation.
FRAGMENTS = (
    "5~10bp",
    "*not bold*",
    "_not emphasis_",
    "`not raw`",
    "a<label>b",
    "2020--2021",
    "and/or",
    "= not a heading",
    "- not a bullet",
    "+ not an item",
    "/ not a term",
    "#panic",
    "$x$",
    "@ref",
    "[a]",
    "{b}",
)

PROBE_BODY = "\n".join(FRAGMENTS)


def _collapsed(text: str) -> str:
    """Whitespace collapsed, because the layout engine chooses where lines wrap.

    A tilde drawn as a space still fails: the assertion looks for ``5~10bp``, and
    ``5 10bp`` does not contain it however the spaces are counted.
    """
    return re.sub(r"\s+", " ", text)


@pytest.fixture(scope="module")
def narrative_text() -> str:
    package = json.loads(NARRATIVE_PACKAGE.read_text(encoding="utf-8"))
    sections = package["report_data"]["reviewed_advisory_narrative"]["sections"]
    sections[0]["body"] = PROBE_BODY

    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    service = TypstRenderService(settings, RenderIntakeService(registry))
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return _collapsed("\n".join(page.extract_text() for page in reader.pages))


@pytest.mark.parametrize("fragment", FRAGMENTS, ids=lambda fragment: fragment)
def test_a_markup_token_in_report_text_reaches_the_page_as_itself(
    fragment: str, narrative_text: str
) -> None:
    """One case each, so a failure names the token rather than the whole probe."""

    assert _collapsed(fragment) in narrative_text, (
        f"the document does not say {fragment!r}. Typst read it as markup and drew "
        "something else; escape_typst_text has to neutralise every markup token, not "
        "only the ones that can introduce code."
    )
