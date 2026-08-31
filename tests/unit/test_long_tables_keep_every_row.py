"""A table longer than a page draws each row in its own place.

`labelled-table` wrapped the subtitle, the column labels and every row in one
`block(breakable: false)`, so a table taller than a page could not be split. Typst does
not refuse: it fits what it can and stacks the remainder at the bottom edge. With 200
monthly rows supplied, 31 drew normally and the other 169 were overprinted on top of
each other into a black smear one line high.

Every row is still in the PDF's text layer, which is the trap. The first version of this
test asked whether each supplied period appeared in the extracted text, and it passed
against the smear -- all 200 were "there". Reading the text back proves the content was
emitted, never that a reader can see it. The assertion has to be about position.

Nothing else could have caught it either. The banked fixture has 12 rows against a
contract ceiling of 10,000, so no golden reaches a second page, and the page-image
measurements look at one page at a time and would see the smear as ink like any other.
"""

from __future__ import annotations

import copy
import io
import json
from collections import Counter
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")
# Several pages' worth. The broken layout fitted 31 before it began overprinting, and
# the contract admits 10,000, so this is nearer the fixture than the ceiling.
LONG_ENOUGH_TO_SPAN_PAGES = 200
ROW_MARK = "ROWMARK"


@pytest.fixture(scope="module")
def placed_rows() -> tuple[list[tuple[int, float]], list[str]]:
    """Where each supplied row was actually drawn: (page number, baseline)."""
    raw = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    source = raw["report_data"]["performance_monthly_history"]
    marks = [f"{ROW_MARK}{index:04d}" for index in range(LONG_ENOUGH_TO_SPAN_PAGES)]
    raw["report_data"]["performance_monthly_history"] = [
        {**copy.deepcopy(source[index % len(source)]), "period": marks[index]}
        for index in range(LONG_ENOUGH_TO_SPAN_PAGES)
    ]
    raw["render_job_id"] = "rdr_long_monthly_table"

    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    service = TypstRenderService(settings, RenderIntakeService(registry))
    reader = pypdf.PdfReader(
        io.BytesIO(service.render(RenderPackage.model_validate(raw)).artifact_bytes)
    )

    places: list[tuple[int, float]] = []
    for number, page in enumerate(reader.pages, 1):

        def visit(
            text: str,
            cm: list[float],
            _tm: list[float],
            _font: object,
            _size: float,
            number: int = number,
        ) -> None:
            if text.strip().startswith(ROW_MARK):
                places.append((number, round(cm[5], 1)))

        page.extract_text(visitor_text=visit)
    return places, marks


def test_no_two_rows_are_drawn_in_the_same_place(
    placed_rows: tuple[list[tuple[int, float]], list[str]],
) -> None:
    """The rows a page cannot hold go to the next page, not on top of each other."""

    places, marks = placed_rows

    assert len(set(places)) >= len(marks), (
        f"{len(marks)} rows were supplied and drawn in only {len(set(places))} distinct "
        "positions, so rows are printed over one another. A table that cannot break is "
        "not shortened -- what will not fit is stacked at the bottom edge, and Typst "
        "reports nothing."
    )


def test_no_single_position_holds_a_pile_of_rows(
    placed_rows: tuple[list[tuple[int, float]], list[str]],
) -> None:
    """Names the smear directly, so a failure says what went wrong rather than a count.

    A chart axis legitimately puts a dozen labels on one baseline, so this bounds the
    pile rather than forbidding every repeat.
    """

    places, _ = placed_rows
    worst_place, worst_count = Counter(places).most_common(1)[0]

    assert worst_count <= 12, (
        f"{worst_count} rows are drawn at the same point (page {worst_place[0]}, "
        f"y={worst_place[1]}). That is a stack of overprinted rows, not a table."
    )


def test_the_table_still_spans_more_than_one_page(
    placed_rows: tuple[list[tuple[int, float]], list[str]],
) -> None:
    """Otherwise the tests above prove nothing about breaking.

    If a future layout fits two hundred rows on one page, raise the count rather than
    relaxing the assertions.
    """

    places, _ = placed_rows
    pages = {number for number, _ in places}

    assert len(pages) > 1, (
        f"every supplied row landed on page(s) {sorted(pages)}, so this fixture no "
        "longer exercises a table that has to break."
    )
