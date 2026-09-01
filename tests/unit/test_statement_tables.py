"""A statement table is declared once and drawn only as far as the data reaches.

The positions and transactions tables each declared their columns twice -- labels in the
template's `table.header`, values in a row function, lined up by position -- and both had
drifted. The transactions table labelled a value date, a settlement amount, a place of
execution, a brokerage, a tax and two custody accounts; nothing in the render package
supplies any of them, so those cells read "Not available" or were blank on every row of
every document. Its "Purchase price" and "Transaction price" columns both read `price`,
so they printed the same number twice. The positions table labelled a cost price, an
exchange rate, a duration, a yield and an accrued interest the same way, and printed the
literal "Sustainability / instrument details" under every holding.

None of that was visible to a test, because the tests asserted the joined strings the
rows produced -- including the "Not available" runs, which they held in place.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.statement_layouts import POSITION_COLUMNS, TRANSACTION_COLUMNS
from app.services.statement_tables import (
    StatementColumn,
    StatementField,
    joined,
    live_columns,
    render_header,
    render_rows,
    render_widths,
    text_of,
)

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")


def _golden(key: str) -> list[dict[str, Any]]:
    package: dict[str, Any] = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = package["report_data"][key]
    return rows


def _labels(columns: list[StatementColumn]) -> set[str]:
    return {field.label for column in columns for field in column.fields}


def test_a_field_no_row_supplies_is_drawn_nowhere() -> None:
    """Neither a label in the header nor "Not available" in the body: absent."""

    columns = (
        StatementColumn(
            width="1fr",
            fields=(
                StatementField("Present", text_of("here")),
                StatementField("Absent", text_of("nowhere")),
            ),
        ),
    )
    rows = [{"here": "yes"}, {"here": "also"}]

    live = live_columns(columns, rows)

    assert _labels(live) == {"Present"}
    assert "Absent" not in render_header(live)
    assert "Not available" not in render_rows(live, rows)


def test_a_field_one_row_supplies_is_drawn_for_all_of_them() -> None:
    """The column exists because the data can fill it, not because every row does.

    A holding that has no rating does not remove the rating column from a statement
    that has ratings; its own cell simply carries one line fewer.
    """

    columns = (
        StatementColumn(
            width="1fr",
            fields=(
                StatementField("Name", text_of("name")),
                StatementField("Rating", text_of("rating")),
            ),
        ),
    )
    rows = [{"name": "A", "rating": "AA"}, {"name": "B"}]

    live = live_columns(columns, rows)
    body = render_rows(live, rows)

    assert _labels(live) == {"Name", "Rating"}
    assert body.count("#statement-cell(") == 2
    assert body.splitlines()[0].count("value:") == 2
    assert body.splitlines()[1].count("value:") == 1


def test_a_column_left_with_nothing_is_not_drawn_at_all() -> None:
    """An empty column is a header over a strip of blank cells."""

    columns = (
        StatementColumn(width="1fr", fields=(StatementField("Kept", text_of("kept")),)),
        StatementColumn(width="2fr", fields=(StatementField("Gone", text_of("missing")),)),
    )
    rows = [{"kept": "x"}]

    live = live_columns(columns, rows)

    assert render_widths(live) == "(1fr,)"
    assert render_header(live).count("#stacked-table-label(") == 1
    assert render_rows(live, rows).count("#statement-cell(") == 1


def test_the_header_and_the_body_always_carry_the_same_columns() -> None:
    """The defect the single declaration exists to prevent, on the real fixtures."""

    for columns, rows in (
        (POSITION_COLUMNS, _golden("top_holdings")),
        (TRANSACTION_COLUMNS, _golden("transactions")),
    ):
        live = live_columns(columns, rows)
        header = render_header(live)
        body = render_rows(live, rows)

        assert header.count("#stacked-table-label(") == len(live)
        for line in body.splitlines():
            assert line.count("#statement-cell(") == len(live)


def test_the_golden_statement_tables_print_no_absence() -> None:
    """Every label the document draws has a value under it somewhere.

    A blank line inside a cell is not an absence: it is the place a field this row does
    not supply would occupy, held open so the values below stay under their own labels.
    This asserted there were none, which was the same mistake as skipping them -- the
    banked golden's Cash holding has no rating, so its sector was drawn under "Rating",
    its country under "Sector" and its liquidity under "Country of risk".
    """

    for columns, rows in (
        (POSITION_COLUMNS, _golden("top_holdings")),
        (TRANSACTION_COLUMNS, _golden("transactions")),
    ):
        live = live_columns(columns, rows)
        body = render_rows(live, rows)

        assert "Not available" not in body
        # A cell never ends on a blank: there is nothing below it to keep in place.
        for line in body.splitlines():
            for cell in line.split("[#statement-cell(")[1:]:
                values = re.findall(r'value: "([^"]*)"', cell)
                assert not values or values[-1] != "", (
                    f"a cell ends with a blank line, which holds nothing open: {values}"
                )


def test_an_absence_spelt_any_of_its_ways_counts_as_absent() -> None:
    """Report data says "there is nothing here" in more than one way."""

    columns = (StatementColumn(width="1fr", fields=(StatementField("Thing", text_of("thing")),)),)
    for absent in ("", "  ", "Not available", "n/a", "N/A", "None", "-", "null"):
        assert live_columns(columns, [{"thing": absent}]) == []
    assert live_columns(columns, [{"thing": "0.00"}]), "zero is a value, not an absence"


def test_a_joined_line_skips_the_parts_that_are_missing() -> None:
    """Three identifiers on one line, however many of them arrived."""

    resolve = joined(
        (
            ("Reference", text_of("ref")),
            ("Security", text_of("sec")),
            ("Instrument", text_of("ins")),
        )
    )

    assert resolve({"ref": "R1", "sec": "S1", "ins": "I1"}) == (
        "Reference R1  |  Security S1  |  Instrument I1"
    )
    assert resolve({"ref": "R1", "ins": "I1"}) == "Reference R1  |  Instrument I1"
    assert resolve({}) is None


def test_no_declared_field_reads_the_same_thing_as_its_neighbour() -> None:
    """Two columns reading one key print one number twice.

    The transactions table's "Purchase price" and "Transaction price" both read `price`,
    so every row showed the same figure in two columns under two names.
    """

    for columns in (POSITION_COLUMNS, TRANSACTION_COLUMNS):
        rows = [{key: f"value-{index}" for index, key in enumerate(_probe_keys(columns))}]
        drawn = [field.resolve(rows[0]) for column in columns for field in column.fields]
        supplied = [value for value in drawn if value is not None]

        assert len(supplied) == len(set(supplied)), (
            f"two fields resolve to the same value from distinct inputs: {supplied}"
        )


def _probe_keys(columns: tuple[StatementColumn, ...]) -> list[str]:
    """Every report-data key the columns can read, discovered by asking them."""
    seen: list[str] = []
    for candidate in _CANDIDATE_KEYS:
        row = {candidate: "probe"}
        if any(field.resolve(row) is not None for column in columns for field in column.fields):
            seen.append(candidate)
    return seen


# The union of what a render package carries for a holding and for a transaction.
_CANDIDATE_KEYS = (
    "accrued_interest",
    "amount",
    "asset_class",
    "booking_text",
    "cost_basis_reporting_currency",
    "cost_price",
    "country_of_risk",
    "currency",
    "description",
    "duration",
    "exchange_rate",
    "gain_loss",
    "gross_amount_reporting_currency",
    "held_since_date",
    "instrument_id",
    "instrument_name",
    "isin",
    "liquidity_tier",
    "market_price",
    "market_price_date",
    "market_value",
    "net_interest_amount_reporting_currency",
    "place_of_execution",
    "price",
    "product_type",
    "quantity",
    "rating",
    "realized_pnl_reporting_currency",
    "sector",
    "security_id",
    "security_name",
    "settlement_amount_reporting_currency",
    "trade_date",
    "transaction_category",
    "transaction_id",
    "transaction_type",
    "transaction_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "value_date",
    "weight_pct",
    "withholding_tax_amount_reporting_currency",
    "ytd_average_weight_pct",
    "ytd_contribution_pct",
    "ytd_total_return_pct",
    "yield_to_maturity",
)


def _cell_values(rendered_row: str, column_index: int) -> list[str]:
    """The stacked values of one cell, in the order they are drawn."""
    cells = rendered_row.split("[#statement-cell(")[1:]
    return re.findall(r'value: "([^"]*)"', cells[column_index])


def test_a_row_missing_a_field_keeps_its_other_values_under_their_own_labels() -> None:
    """The header stack names the lines; only position joins the two.

    `live_columns` keeps a field because some row supplies it, and the cell used to skip
    the fields a particular row does not -- so every value below a gap shifted up one
    line. On a transaction list whose last column reads "Transaction value / Net
    interest / Withholding tax", a coupon with no transaction value drew its net
    interest of 7.00 under "Transaction value". Mixed transaction types reach this
    immediately; the banked fixture is three trades of one shape, so it cannot.
    """

    rows: list[dict[str, Any]] = [
        {
            "trade_date": "2026-01-09",
            "description": "Purchase",
            "transaction_value": "450000",
            "net_interest_amount_reporting_currency": "0",
            "withholding_tax_amount_reporting_currency": "0",
        },
        {
            "trade_date": "2026-02-17",
            "description": "Coupon",
            "net_interest_amount_reporting_currency": "7.00",
            "withholding_tax_amount_reporting_currency": "1.00",
        },
        {
            "trade_date": "2026-03-31",
            "description": "Fee",
            "withholding_tax_amount_reporting_currency": "2.50",
        },
    ]
    live = live_columns(TRANSACTION_COLUMNS, rows)
    money_column = len(live) - 1
    labels = [field.label for field in live[money_column].fields]
    assert labels == ["Transaction value", "Net interest", "Withholding tax"]

    body = render_rows(live, rows).splitlines()

    assert _cell_values(body[0], money_column) == ["450,000", "0", "0"]
    # The coupon has no transaction value, so that line is blank rather than absent.
    assert _cell_values(body[1], money_column) == ["", "7.00", "1.00"]
    assert _cell_values(body[2], money_column) == ["", "", "2.50"]


def test_a_value_is_never_drawn_on_a_line_that_names_something_else() -> None:
    """Stated as the property, over every column and every row shape.

    Whatever a row supplies, the nth drawn line of a cell must belong to the nth label
    of that column -- which is the only guarantee a reader has, because the body lines
    carry no labels of their own.
    """

    rows: list[dict[str, Any]] = [
        {
            "trade_date": "2026-01-09",
            "description": "All",
            "transaction_value": "1",
            "net_interest_amount_reporting_currency": "2",
            "withholding_tax_amount_reporting_currency": "3",
            "price": "4",
            "gross_amount_reporting_currency": "5",
            "amount": "6",
        },
        {
            "trade_date": "2026-02-17",
            "description": "Sparse",
            "withholding_tax_amount_reporting_currency": "9",
        },
    ]
    live = live_columns(TRANSACTION_COLUMNS, rows)
    body = render_rows(live, rows).splitlines()

    for row_index, row in enumerate(rows):
        for column_index, column in enumerate(live):
            drawn = _cell_values(body[row_index], column_index)
            for line_index, value in enumerate(drawn):
                expected = column.fields[line_index].resolve(row)
                assert value == (expected or ""), (
                    f"row {row_index}, column {column_index}: line {line_index} is "
                    f"labelled {column.fields[line_index].label!r} and carries {value!r}"
                )
