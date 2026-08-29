"""A table that spans pages must carry its header onto every page it spans.

Every "table" was a header `#grid` emitted once, followed by N independent row `#grid`s
inside one breakable panel. Nothing could repeat a header, because Typst's
`table.header(repeat: true)` only applies to a real `table()` element -- so a 500-row
statement paginated into pages of eight unlabelled right-aligned numeric columns, and
each row's rule was a sibling element that could land alone at the top of a page
(issue #138).

Measured on a 200-position statement: 53 pages and 7,142 text-draw operations with
`repeat: true`, against 50 pages and 6,611 without. The difference is the header being
redrawn on each continuation page.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService
from app.services.typst_tables import DENSE_POSITION_COLUMNS, render_dense_position_rows

TEMPLATE_ROOT = Path("templates/typst/portfolio-review/v1")
# Both long tables; each is bounded only by the 10,000-item contract ceiling.
PAGINATING_TABLES = (TEMPLATE_ROOT / "_positions.typ", TEMPLATE_ROOT / "_transactions.typ")
POSITIONS_TEMPLATE = TEMPLATE_ROOT / "_positions.typ"


def test_the_positions_table_repeats_its_header() -> None:
    """The property the whole change exists for; a grid cannot express it."""

    for template in PAGINATING_TABLES:
        source = template.read_text(encoding="utf-8")
        assert "#table(" in source, (
            f"{template.name} is not a Typst table element, so no header can repeat"
        )
        header = re.search(r"table\.header\(\s*repeat:\s*(\w+)", source)
        assert header is not None, f"{template.name} declares no header"
        assert header.group(1) == "true", (
            f"{template.name}'s header does not repeat, so page 2 of a long statement "
            "shows unlabelled numeric columns"
        )


def test_each_row_carries_its_own_separator() -> None:
    """A rule emitted beside a row can land alone at the top of the next page."""

    for template in PAGINATING_TABLES:
        source = template.read_text(encoding="utf-8")
        assert "stroke:" in source, f"{template.name} draws no row separator"
        assert "#line(" not in source, (
            f"{template.name} emits a standalone rule alongside rows again; it belongs to "
            "the row's own stroke so the two cannot separate across a page break"
        )


def test_position_rows_are_spreadable_table_cells() -> None:
    """Rows must be cell arrays the table spreads, not self-contained blocks."""

    rows = render_dense_position_rows(
        [{"security_name": "A", "weight_pct": "10"}, {"security_name": "B", "weight_pct": "20"}]
    )

    lines = rows.splitlines()
    assert len(lines) == 2, f"expected one call per row, got {lines}"
    for line in lines:
        assert line.startswith("dense-position-row("), line
        assert line.endswith("),"), (
            f"row is not comma-terminated, so the template cannot spread it: {line[-40:]}"
        )


def test_the_empty_state_is_a_row_of_the_table() -> None:
    """A block outside the table would sit above the repeating header on later pages."""

    empty = render_dense_position_rows([])

    assert empty.startswith(f"table.cell(colspan: {DENSE_POSITION_COLUMNS})"), empty[:60]
    assert "No position detail available." in empty
    assert empty.rstrip().endswith(",")


def test_a_long_statement_paginates_and_still_renders() -> None:
    """200 positions is well inside the contract ceiling of 10,000 list items."""

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    base = json.loads(
        Path("tests/golden/portfolio-review/v1/render-package.json").read_text(encoding="utf-8")
    )
    report_data = deepcopy(base["report_data"])
    holding = report_data["top_holdings"][0]
    report_data["top_holdings"] = [
        {**holding, "security_name": f"Holding {index:03d}"} for index in range(200)
    ]

    result = service.render(RenderPackage.model_validate({**base, "report_data": report_data}))

    assert result.attempt.status.value == "rendered"
    pages = len(re.findall(rb"/Type\s*/Page[^s]", result.artifact_bytes))
    assert pages > 20, f"a 200-position statement rendered only {pages} pages"


def _render(package_path: str) -> bytes:
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    package = RenderPackage.model_validate_json(Path(package_path).read_text(encoding="utf-8"))
    return service.render(package).artifact_bytes


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_a_report_with_no_data_is_shorter_than_a_full_one() -> None:
    """Intra-section page breaks fired unconditionally, padding an empty report.

    The performance section broke twice and the allocation section once regardless of
    content, so a portfolio with no history still shipped three near-blank pages -- and
    an all-empty report was exactly as long as a full one (issue #138). The appendix's
    static definition pages are constant by design and are not affected.
    """

    full = _page_count(_render("tests/golden/portfolio-review/v1/render-package.json"))
    degraded = _page_count(_render("tests/golden/portfolio-review/v1/degraded/render-package.json"))

    assert degraded < full, (
        f"an all-empty report renders {degraded} pages against {full} for a full one; "
        "the section breaks are still firing without content behind them"
    )


COMPONENTS_TEMPLATE = TEMPLATE_ROOT / "_components.typ"
# Small fixed-size cards. Splitting one shows a stroke with no bottom, or a label whose
# value is on the next page.
#
# The chart cards are here for a second reason: they pair a figure with the words that
# say what it is. Left breakable, `chart-card` stranded the title "12-Month Cumulative
# Performance" at the foot of one page and put the plot, unlabelled, at the top of the
# next. A chart nobody can name is worse than no chart. This list did not cover them,
# which is why that regression was reachable at all.
UNBREAKABLE_CARDS = (
    "note-panel",
    "metric-card",
    "review-note",
    "chart-card",
    "chart-placeholder",
)


def test_small_cards_and_captioned_figures_cannot_split_across_a_page_break() -> None:
    """Typst 0.14.2 has no widow or orphan control -- `#set par(widows:)` is rejected.

    `breakable: false` on the units that are always wrong to split is the mechanism the
    engine does offer (issue #138). Verified against typst 0.14.2: a card straddling a
    boundary renders across 3 pages breakable and 2 unbreakable.
    """

    source = COMPONENTS_TEMPLATE.read_text(encoding="utf-8")

    for card in UNBREAKABLE_CARDS:
        start = source.index(f"#let {card}(")
        declaration = source[start : source.index("[", start)]
        assert "breakable: false" in declaration, (
            f"{card} can split across a page break, which always looks broken for a bordered card"
        )


def test_panels_that_wrap_long_tables_stay_breakable() -> None:
    """The guard must not be applied where it would prevent pagination entirely."""

    source = COMPONENTS_TEMPLATE.read_text(encoding="utf-8")

    start = source.index("#let report-panel(")
    declaration = source[start : source.index("[", start)]
    assert "breakable: false" not in declaration, (
        "report-panel wraps the positions and transactions tables; making it unbreakable "
        "would stop a long statement paginating at all"
    )
