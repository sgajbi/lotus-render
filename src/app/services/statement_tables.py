"""Declare a statement table once, and draw only the parts the data can fill.

The positions and transactions tables each declared their columns twice: a stack of
labels in the template's `table.header`, and a matching stack of values in a row
function, lined up by position with nothing holding them together. They had drifted.

The transactions table asked for `value_date`, `settlement_amount`, `place_of_execution`,
`reporting_currency` and `settlement_date`; no transaction in any fixture supplies any of
them, so every row printed "Not available" under a label for a field that never arrives.
Its "Purchase price" and "Transaction price" columns read the same value out of `price`,
so they were identical on every row. The positions table asked for `cost_price`,
`exchange_rate`, `duration`, `yield_to_maturity` and `accrued_interest` -- none supplied
-- and printed the literal "Sustainability / instrument details" under every holding,
which is a description of a field rather than a field.

So a table is declared here as columns of fields, each field knowing its own label and
how to read itself out of a row. A field no row can supply is drawn in neither the header
nor the body, and a column left with no fields is not drawn at all. The two halves cannot
drift because there is only one declaration.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from app.services.absence import is_supplied
from app.services.date_format import format_date
from app.services.number_format import group_digits
from app.services.typst_values import escape_typst_string

Row = Mapping[str, object]
Resolver = Callable[[Row], str | None]


@dataclass(frozen=True)
class StatementField:
    """One line of a stacked cell: what it is called and how to read it."""

    label: str
    resolve: Resolver
    tone: str = "slate"
    size: str = "7.4pt"
    weight: int = 400


@dataclass(frozen=True)
class StatementColumn:
    """One column: its width, and the lines stacked inside it."""

    width: str
    fields: tuple[StatementField, ...]
    placement: str = "right"


def text_of(*keys: str, prefix: str = "", money: bool = False, date: bool = False) -> Resolver:
    """Read the first of `keys` a row supplies, or None when it supplies none.

    `date` puts the value through the document's date format. Report data carries ISO
    dates for holdings and dotted ones for transactions, and a reader should not be
    shown the difference.
    """

    def resolve(row: Row) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is None:
                continue
            if not is_supplied(value):
                continue
            text = str(value).strip()
            if date:
                return f"{prefix}{format_date(text)}"
            return f"{prefix}{group_digits(text) if money else text}"
        return None

    return resolve


def joined(parts: Sequence[tuple[str, Resolver]], separator: str = "  |  ") -> Resolver:
    """One line assembled from several fields, each labelled, skipping the absent.

    Used where a row carries a handful of short identifiers that belong together on one
    line rather than in columns of their own.
    """

    def resolve(row: Row) -> str | None:
        pieces = [
            f"{label} {value}".strip() for label, part in parts if (value := part(row)) is not None
        ]
        return separator.join(pieces) if pieces else None

    return resolve


def _is_supplied(field: StatementField, rows: Sequence[Row]) -> bool:
    return any(field.resolve(row) is not None for row in rows)


def live_columns(columns: Sequence[StatementColumn], rows: Sequence[Row]) -> list[StatementColumn]:
    """The columns as this data can actually fill them.

    A field nothing supplies is removed, and a column whose fields all fall away goes
    with them -- an empty column is a header over a strip of blank cells.
    """
    live: list[StatementColumn] = []
    for column in columns:
        fields = tuple(field for field in column.fields if _is_supplied(field, rows))
        if fields:
            live.append(replace(column, fields=fields))
    return live


def render_widths(columns: Sequence[StatementColumn]) -> str:
    """The Typst column tuple, so widths are declared with the columns they size."""
    if not columns:
        return "()"
    widths = ", ".join(column.width for column in columns)
    return f"({widths},)" if len(columns) == 1 else f"({widths})"


def render_header(columns: Sequence[StatementColumn]) -> str:
    """Header cells, carrying exactly the labels the body will carry values for."""
    cells = []
    for column in columns:
        labels = ", ".join(f'"{escape_typst_string(field.label)}"' for field in column.fields)
        stacked = f"({labels},)" if len(column.fields) == 1 else f"({labels})"
        cells.append(f"[#stacked-table-label({stacked}, placement: {column.placement})]")
    return ",\n".join(cells) + ("," if cells else "")


def _cell(column: StatementColumn, row: Row) -> str:
    """One stacked cell, with its lines still under the labels the header gave them.

    Skipping a field this row does not supply shifts every value below it up one line,
    and the header stack is the only thing naming them. A coupon with no transaction
    value drew its net interest under "Transaction value". So an absent field keeps its
    line, blank, whenever something below it is present.
    """
    resolved = [field.resolve(row) for field in column.fields]
    last_present = max(
        (index for index, value in enumerate(resolved) if value is not None),
        default=-1,
    )

    lines = []
    for field, value in zip(column.fields[: last_present + 1], resolved[: last_present + 1]):
        lines.append(
            f'(value: "{escape_typst_string(value or "")}", size: {field.size}, '
            f'tone: "{field.tone}", weight: {field.weight})'
        )
    body = ", ".join(lines)
    stacked = f"({body},)" if len(lines) == 1 else f"({body})"
    return f"[#statement-cell({stacked}, placement: {column.placement})]"


def render_rows(columns: Sequence[StatementColumn], rows: Sequence[Row]) -> str:
    """Body cells, one tuple per row, for the template to spread into its table."""
    return "\n".join(
        "(" + ", ".join(_cell(column, row) for column in columns) + ")," for row in rows
    )
