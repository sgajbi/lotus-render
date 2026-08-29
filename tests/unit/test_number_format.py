"""One convention for presenting numbers, across every emitter.

The same figure was spelled two ways on the same page: the allocation donut's legend
read `9,140,741` while the table beneath it read `9140740.73`. Two independent regimes
had grown up -- `Decimal` with `quantize` and thousands separators in the chart module,
bare f-string floats in the table emitters -- and nothing made them agree.

Precision may differ between a compact legend and a statement line. The separator
convention may not.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.contracts.render_package import RenderPackage
from app.services.number_format import format_money, format_percent
from app.services.portfolio_charts import (
    _format_currency,
    _format_decimal,
    allocation_items_from_report_data,
)
from app.services.typst_contexts import build_portfolio_review_context

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")


def test_money_is_grouped_and_rounded_half_up() -> None:
    assert format_money("9140740.735") == "9,140,740.74"
    assert format_money(1234.5) == "1,234.50"
    assert format_money("9140740.73", decimals=0) == "9,140,741"


def test_a_value_that_is_not_a_number_passes_through_unchanged() -> None:
    """Report data owns the truth; inventing a zero would be recreating it."""

    assert format_money("Not available") == "Not available"
    assert format_percent("Not available") == "Not available"


def test_percent_formatting_is_idempotent_on_an_already_suffixed_value() -> None:
    """Whether the input carried a `%` must not change the outcome."""

    assert format_percent("60.00") == "60.00%"
    assert format_percent("60.00%") == "60.00%"
    assert format_percent("-3.5") == "-3.50%"


def test_the_chart_legend_and_the_table_agree_on_convention() -> None:
    """Both render the same amount on the same page of the same document."""

    package = RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    items = allocation_items_from_report_data(package.report_data)
    assert items, "the golden package carries no allocation items"

    legend_amount = _format_currency(items[0].market_value)
    table_values = re.findall(
        r'"([\d.,]+)"', build_portfolio_review_context(package)["ASSET_CLASS_ROWS"]
    )
    table_amount = next(value for value in table_values if "," in value or "." in value)

    grouped = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$")
    assert grouped.match(legend_amount), f"legend amount is not grouped: {legend_amount}"
    assert grouped.match(table_amount), (
        f"table amount is not grouped while the legend beside it is: {table_amount}"
    )
    # The legend's percent uses the same convention as the amounts beside it.
    assert grouped.match(_format_decimal(items[0].weight_pct))


def test_no_emitter_formats_a_monetary_value_with_a_bare_f_string() -> None:
    """The regimes must not regrow; one convention means one place that spells it."""

    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path("src/app/services/typst_tables.py"),
            Path("src/app/services/portfolio_charts.py"),
        )
    )
    offenders = re.findall(r"f\"\{[a-z_\[\]'\" ]*(?:value|amount|price)[^}]*:\.\d+f\}\"", sources)

    assert not offenders, (
        f"these emitters format a monetary value directly instead of via number_format: {offenders}"
    )
