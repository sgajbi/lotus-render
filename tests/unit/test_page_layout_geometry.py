"""Assertions about how a rendered page is laid out, not only about its bytes.

Every client-visible defect this repository has found was byte-identical to itself,
so the banked fingerprints were green over it for as long as it existed: gridlines
drawn outside the plot (#152), a chart card severed from its title, a donut centre
that contradicted the summary card beside it. Each was found by rasterising a page
and looking at it. These tests do that looking on every run.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

# Anything darker than this is ink. Page backgrounds are white and the lightest thing
# the design system draws is `mist` (#F6F8FA, luminance ~248), so the threshold sits
# below the palette and above the anti-aliasing of a hairline rule.
INK_THRESHOLD = 245

# The running header and footer appear on every page and say nothing about how full it
# is, so the default region is the body between them.
BODY_TOP = 0.04
BODY_BOTTOM = 0.93

# Every fourth column, which is enough to find a hairline at export resolution and
# four times cheaper than reading them all.
_COLUMN_STEP = 4


@dataclass(frozen=True)
class RegionInk:
    """Where the ink lies in a region, as fractions of that region and of the page."""

    #: How much of the region's height is empty below its last ink. A region filled to
    #: the bottom scores 0; one whose content stops halfway scores 0.5.
    tail_blank: float
    #: Leftmost and rightmost ink, as fractions of the page width.
    left: float
    right: float

    @property
    def width(self) -> float:
        """How much of the page's width the content spans."""
        return self.right - self.left


def region_ink(
    page: bytes, *, top: float = BODY_TOP, bottom: float = BODY_BOTTOM
) -> RegionInk | None:
    """Measure a horizontal slice of a page, or None when it carries no ink.

    `top` and `bottom` are fractions of the page height. The greyscale image is read as
    one flat buffer -- for an "L" image `tobytes` is row-major, one byte per pixel.
    """
    image = Image.open(io.BytesIO(page)).convert("L")
    width, height = image.size
    data = image.tobytes()
    first_row = int(height * top)
    last_row = int(height * bottom)
    sampled = range(0, width, _COLUMN_STEP)

    rows = [
        y
        for y in range(first_row, last_row)
        if min(data[y * width + x] for x in sampled) < INK_THRESHOLD
    ]
    if not rows:
        return None

    columns = [x for x in sampled if min(data[y * width + x] for y in rows) < INK_THRESHOLD]
    return RegionInk(
        tail_blank=(last_row - rows[-1]) / (last_row - first_row),
        left=columns[0] / width,
        right=columns[-1] / width,
    )


GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")

# The banked golden's layout. #184 is expected to move these as it merges under-filled
# pages; when it does, re-measure rather than widen the bounds.
RISK_PROFILE_PAGE = 8
RISK_CARD_BAND = (0.16, 0.34)

# The emptiest page of the banked golden, measured. A ratchet rather than a bound: a
# change that fills pages better must lower it, and one that empties them fails. Page 8
# holds it -- six risk cards alone on a page they were given by an unconditional break,
# which is the defect #184 describes.
WORST_TAIL_BLANK = 0.688


@pytest.fixture(scope="module")
def golden_pages() -> list[bytes]:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    service = TypstRenderService(settings, RenderIntakeService(registry))
    package = RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    return service.render_page_images(package)


def test_a_card_fills_the_column_it_is_placed_in(golden_pages: list[bytes]) -> None:
    """A panel that hugs its own text leaves the grid it sits in looking broken.

    `note-panel` carried no width, so in the three-column risk grid each card sized to
    its own short value and the row rendered as three narrow islands, the columns' width
    left as dead space between them. The same component in `_overview.typ` carries
    sentences that wrap to fill, which is why the defect was invisible there (#184).
    """

    page = golden_pages[RISK_PROFILE_PAGE - 1]
    band = region_ink(page, top=RISK_CARD_BAND[0], bottom=RISK_CARD_BAND[1])
    # The page's own body width, taken from the rule under its header rather than from a
    # constant, so the two margins the document uses do not need to be tracked here.
    body = region_ink(page)

    assert band is not None and body is not None, "the risk profile page carries no ink"
    assert band.width == pytest.approx(body.width, abs=0.01), (
        f"the risk cards span {band.width:.1%} of the page where its body spans "
        f"{body.width:.1%}: they are hugging their own text rather than filling the "
        "columns they are placed in"
    )


def test_no_page_is_emptier_than_the_banked_worst(golden_pages: list[bytes]) -> None:
    """A ratchet on how much of the document is blank.

    Hard section breaks are guarded on a section having content, not on it having a
    page's worth, so a six-value section still gets a full page (#184). This bounds
    that at what it measures today so it can only improve.
    """

    measured = [
        (index, ink.tail_blank)
        for index, page in enumerate(golden_pages, 1)
        if (ink := region_ink(page)) is not None
    ]
    assert measured, "no page carried ink"
    page, worst = max(measured, key=lambda item: item[1])

    assert worst == pytest.approx(WORST_TAIL_BLANK, abs=0.01), (
        f"page {page} ends {worst:.1%} blank against a banked worst of "
        f"{WORST_TAIL_BLANK:.1%}. Above it, a page got emptier; below it, the document "
        "improved and the ratchet should be re-banked in the change that moved it."
    )


def test_every_page_carries_content(golden_pages: list[bytes]) -> None:
    """A page with no ink in its body is a break that fired with nothing behind it."""

    blank = [index for index, page in enumerate(golden_pages, 1) if region_ink(page) is None]

    assert not blank, f"pages {blank} render a header and footer over an empty body"
