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
from app.services.number_format import format_money, format_percent, group_digits
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


def test_grouping_never_changes_the_number_it_groups() -> None:
    """Separators are presentation. Precision is the owning service's decision.

    `format_money` quantizes, which is right where Render chooses the precision and
    wrong where it is passing a figure through: rounding a quantity or an exchange
    rate to two places would be Render altering a number it does not own.
    """

    assert group_digits("9140740.73") == "9,140,740.73"
    assert group_digits("-1234567.5") == "-1,234,567.5"
    assert group_digits("1000") == "1,000"
    # Precision beyond two places survives; `format_money` would have destroyed it.
    assert group_digits("12.3456789") == "12.3456789"
    assert format_money("12.3456789") == "12.35"
    # A percent keeps its suffix, a date is not a number, and neither is a word.
    assert group_digits("-38.40%") == "-38.40%"
    assert group_digits("2026-04-23") == "2026-04-23"
    assert group_digits("Not available") == "Not available"
    # Already grouped input is left alone rather than mangled.
    assert group_digits("1,234.50") == "1,234.50"
    # A labelled amount is still an amount; producers send both forms.
    assert group_digits("USD 450000.00") == "USD 450,000.00"
    # Digits welded to letters, or carrying a leading zero, are a code and not a
    # quantity: grouping one would also silently drop the zero.
    assert group_digits("ISIN US0378331005") == "ISIN US0378331005"
    assert group_digits("0378331005") == "0378331005"


# A number with four or more integer digits and a decimal fraction, ungrouped. Dates
# have no fraction and identifiers have no decimal point, so neither is matched.
UNGROUPED_AMOUNT = re.compile(r"(?<![\d,.])\d{4,}\.\d+(?![\d])")


def test_no_amount_reaches_the_page_ungrouped() -> None:
    """A property of the output, because the source-scanning guard above cannot see this.

    That guard matches *bad formatting* -- an f-string with a `:.2f`. The emitters were
    not formatting badly; they were passing the producer's string through untouched, so
    the guard read green while the document showed `USD 14984567.89`, `9140740.73` in
    the portfolio scope table, and 60 more in the monthly performance table. Ninety
    amounts in one private-banking review, spelled the way a machine emitted them.

    Asserting on the built context cannot be evaded by not formatting at all.
    """

    package = RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    context = build_portfolio_review_context(package)

    offenders = {
        key: UNGROUPED_AMOUNT.findall(value)
        for key, value in context.items()
        if UNGROUPED_AMOUNT.search(value)
    }

    assert not offenders, (
        "these context values reach the document with ungrouped amounts: "
        f"{ {key: hits[:4] for key, hits in offenders.items()} }"
    )


def test_digits_that_are_not_a_quantity_are_refused_by_the_helper() -> None:
    """`_is_a_quantity` guards its own contract, not just the caller's current regex.

    The caller cannot presently hand it a non-digit whole part, because the pattern that
    produced it requires digits. The guard is what keeps that true if the pattern changes,
    so it is asserted directly rather than left as an unreachable line nobody can justify.
    """

    from app.services.number_format import _is_a_quantity

    assert _is_a_quantity("", "1234") is True
    assert _is_a_quantity("USD ", "1234") is True
    # Digits welded to letters, a leading zero, and a whole part that is not digits.
    assert _is_a_quantity("US", "0378331005") is False
    assert _is_a_quantity("", "0378331005") is False
    assert _is_a_quantity("", "12a4") is False
