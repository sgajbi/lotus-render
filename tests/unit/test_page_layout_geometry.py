"""Assertions about how a rendered page is laid out, not only about its bytes.

Every client-visible defect this repository has found was byte-identical to itself,
so the banked fingerprints were green over it for as long as it existed: gridlines
drawn outside the plot (#152), a chart card severed from its title, a donut centre
that contradicted the summary card beside it. Each was found by rasterising a page
and looking at it. These tests do that looking on every run.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pypdf
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

# The banked golden's layout. #184 moves these as it merges under-filled pages; when it
# does, re-measure rather than widen the bounds.
RISK_CARD_BAND = (0.71, 0.88)

# The emptiest page of the banked golden, measured. A baseline rather than a bound: it
# moves in either direction only with a reason, the way MAX_CYCLOMATIC_COMPLEXITY does.
#
# It has been 68.8% (six risk cards given a page by an unconditional break), then 49.9%
# (the contents page, which is meant to be short), and is now the transaction list. That
# last move was upward and is still an improvement: the transactions table stopped
# printing five fields no transaction supplies, so it draws fewer lines over the same
# three rows. The measure cannot tell whitespace from removed noise, which is why a move
# in either direction has to be looked at rather than accepted.
# 0.556 -> 0.521 when the earnings statement landed in the transaction page's empty half
# (#233): the page that had been the document's emptiest stopped being on the list at
# all, and the worst became the contribution tail.
# 0.521 -> 0.499 when the attribution bridge (#160) landed in that contribution tail --
# the fourth analytic absorbed into reserved space. The worst is now the contents page,
# which is exempt by decision (#184): a deliberate pause, not a page to fill. It matters
# here only as the baseline; if a *content* page ever overtakes it, that page is the one
# to look at.
WORST_TAIL_BLANK = 0.499


def _golden_service() -> tuple[TypstRenderService, RenderPackage]:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return (
        TypstRenderService(settings, RenderIntakeService(registry)),
        RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8")),
    )


@pytest.fixture(scope="module")
def golden_pages() -> list[bytes]:
    service, package = _golden_service()
    return service.render_page_images(package)


def _page_carrying(pages: list[bytes], texts: list[str], phrase: str) -> bytes:
    """The page whose text carries `phrase`.

    A page index is a fact about the current document, not about the layout being
    checked. `RISK_PROFILE_PAGE = 6` was right until the document grew a section, and
    then the risk test asserted against whatever had moved into position six.
    """
    for index, text in enumerate(texts):
        if phrase in text:
            return pages[index]
    raise AssertionError(f"no page carries {phrase!r}")


def test_a_card_fills_the_column_it_is_placed_in(
    golden_pages: list[bytes], golden_page_text: list[str]
) -> None:
    """A panel that hugs its own text leaves the grid it sits in looking broken.

    `note-panel` carried no width, so in the three-column risk grid each card sized to
    its own short value and the row rendered as three narrow islands, the columns' width
    left as dead space between them. The same component in `_overview.typ` carries
    sentences that wrap to fill, which is why the defect was invisible there (#184).
    """

    # Found by what is on it rather than by a page number. The constant was 6 and the
    # document grew a section, so the test asserted against a page that had moved -- a
    # page index is a fact about the current document, not about the layout being checked.
    page = _page_carrying(golden_pages, golden_page_text, "Risk profile")
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


# The other families' emptiest pages, measured and banked the same way. Each of these
# is a one-page governance document, so its tail is the final-page tail -- the floor of
# this measure, since no following section exists to fill it (recorded on #184). The
# bank therefore does not demand filling; it catches a page quietly getting emptier
# (content dropped, layout waste grown) or fuller for an unexamined reason.
FAMILY_WORST_TAIL_BLANK = {
    "outcome-review/v1": 0.546,
    "proof-pack/v1": 0.513,
    "rebalance-wave/v1": 0.544,
}


@pytest.mark.parametrize("family", sorted(FAMILY_WORST_TAIL_BLANK))
def test_no_family_page_is_emptier_than_its_banked_worst(family: str) -> None:
    """The tail ratchet, extended to every family (#184).

    The portfolio review had the ratchet; the governance families had nothing, so a
    change could empty half of a proof pack and every gate would stay green.
    """
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

    measured = [
        (index, ink.tail_blank)
        for index, page in enumerate(service.render_page_images(package), 1)
        if (ink := region_ink(page)) is not None
    ]
    assert measured, f"no page of {family} carried ink"
    page, worst = max(measured, key=lambda item: item[1])

    assert worst == pytest.approx(FAMILY_WORST_TAIL_BLANK[family], abs=0.01), (
        f"{family} page {page} ends {worst:.1%} blank against a banked worst of "
        f"{FAMILY_WORST_TAIL_BLANK[family]:.1%}. Above it, a page got emptier; below "
        "it, the document improved and the bank should move in the change that moved it."
    )


def test_every_page_carries_content(golden_pages: list[bytes]) -> None:
    """A page with no ink in its body is a break that fired with nothing behind it."""

    blank = [index for index, page in enumerate(golden_pages, 1) if region_ink(page) is None]

    assert not blank, f"pages {blank} render a header and footer over an empty body"


def _page_text(package: RenderPackage) -> list[str]:
    """The text of each page of the rendered document, in order."""
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    service = TypstRenderService(settings, RenderIntakeService(registry))
    reader = pypdf.PdfReader(io.BytesIO(service.render(package).artifact_bytes))
    return [page.extract_text() for page in reader.pages]


@pytest.fixture(scope="module")
def golden_page_text() -> list[str]:
    return _page_text(RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8")))


# Each table's subtitle, paired with a column label only that table carries.
TABLE_LABELS = {
    "Performance against benchmark (TWR)": "Relative",
    "Annual net performance (TWR)": "Cum.",
    "Monthly net performance valued in": "Inflows",
}


def test_a_table_is_never_separated_from_what_names_it(golden_page_text: list[str]) -> None:
    """A subtitle at the foot of one page and its table on the next names nothing.

    This is the widow #138 described and left open, and it is not hypothetical: making
    the performance panels relocate whole rather than split stranded two subtitles on
    the page before their tables. `labelled-table` binds subtitle, column labels and
    rows into one unbreakable unit; this asserts they stayed bound.
    """

    for subtitle, label in TABLE_LABELS.items():
        pages = [index for index, text in enumerate(golden_page_text, 1) if subtitle in text]
        assert len(pages) == 1, f"'{subtitle}' appears on pages {pages}, expected exactly one"
        assert label in golden_page_text[pages[0] - 1], (
            f"'{subtitle}' is on page {pages[0]} but its column labels are not: the "
            "subtitle has been separated from the table it names"
        )


# What each contents entry is called in the running header of its own pages. The two
# differ on purpose: the overview is listed as "Overview" and headed "Scope of
# analysis".
CONTENTS_TO_HEADER = {
    "Overview": "Scope of analysis",
    "Performance": "Performance",
    "Asset allocation": "Asset allocation",
    "Detailed positions": "Detailed positions",
    "Transactions": "Transaction list",
    "Appendix": "Appendix",
}


def _heads(text: str, title: str) -> bool:
    """Whether a page belongs to the section headed `title`."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[0].startswith(title)


def _contents_entries(contents: str) -> dict[str, int]:
    """The contents page as {section title: claimed page}.

    Each entry occupies three lines -- a numbered title, its detail, then the page
    reference -- so the title has to be taken positionally rather than by pattern; a
    looser regex matches the detail line instead.
    """
    lines = [line.strip() for line in contents.splitlines() if line.strip()]
    entries: dict[str, int] = {}
    for index, line in enumerate(lines[:-2]):
        numbered = re.match(r"^\d+ (.+)$", line)
        reference = re.match(r"^p\. (\d+)$", lines[index + 2])
        if numbered and reference:
            entries[numbered.group(1)] = int(reference.group(1))
    return entries


def test_the_contents_page_numbers_point_at_the_sections(golden_page_text: list[str]) -> None:
    """Every contents entry must name the page its section actually starts on.

    #137 replaced hard-coded page numbers with computed ones, and nothing has asserted
    since that the computation is right -- a document whose contents are confidently
    wrong is worse than one carrying none. The numbers move whenever breaks move, which
    is exactly what #184 does, so this is the guard that makes such a change safe.
    """

    entries = _contents_entries(golden_page_text[1])
    assert set(entries) == set(CONTENTS_TO_HEADER), (
        f"the contents lists {sorted(entries)}, which is not the set this test knows "
        f"how to locate: {sorted(CONTENTS_TO_HEADER)}"
    )

    for title, claimed in entries.items():
        page = int(claimed)
        header = CONTENTS_TO_HEADER[title]
        assert 1 <= page <= len(golden_page_text), f"'{title}' claims page {page}, out of range"
        assert _heads(golden_page_text[page - 1], header), (
            f"the contents send a reader to page {page} for '{title}', which is not a "
            f"'{header}' page"
        )
        # And it is where the section *starts*, not merely a page it covers.
        assert not _heads(golden_page_text[page - 2], header), (
            f"'{title}' claims page {page}, but page {page - 1} is already part of that "
            "section, so the entry points past its own beginning"
        )


def test_the_document_writes_a_date_one_way(golden_page_text: list[str]) -> None:
    """Four forms appeared in one review: ISO on the positions page, dotted on the
    transactions page beside it, long in the running header, short on the chart axis.
    The header carried two of them in a single phrase.

    The axis keeps its own form deliberately. Twelve labels have to fit across a plot,
    and it is a different problem from writing a date in prose or in a table.
    """

    document = "\n".join(golden_page_text)

    assert not re.findall(r"\b\d{4}-\d{2}-\d{2}\b", document), "an ISO date reached the page"
    assert not re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", document), "a dotted date reached the page"
    assert re.findall(r"\b\d{1,2} [A-Z][a-z]{2} \d{4}\b", document), "no date reached the page"


def test_the_reporting_period_is_the_one_the_package_describes(
    golden_page_text: list[str],
) -> None:
    """The header said "Reporting period 1 Jan 2026 - 2026-04-23" on every page, and the
    first half was a template literal. What a package carries is a period label and an
    as-of date, so that is what the document says."""

    header = golden_page_text[2].splitlines()[0]

    assert "YTD to 23 Apr 2026" in "\n".join(golden_page_text)
    assert "Reporting period" not in header, (
        "the header names a period start that no render package supplies"
    )
