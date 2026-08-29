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
