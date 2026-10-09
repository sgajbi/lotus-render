"""Declared unit conversion and display rounding, separate from exact source text."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.contracts.composite_eligibility import EligibilityCell, EligibilityColumn
from app.contracts.composite_linked import LinkedColumn
from app.contracts.composite_pooled import PooledCell, PooledColumn
from app.contracts.composite_review import CompositeCell, CompositeColumn
from app.services.composite_workbook.eligibility_display import display_eligibility_cell
from app.services.composite_workbook.numeric_display import display_number
from app.services.composite_workbook.source_values import decimal_value


def display_cell(
    column: CompositeColumn | LinkedColumn | EligibilityColumn | PooledColumn,
    cell: CompositeCell | EligibilityCell | PooledCell,
) -> str:
    if isinstance(column, EligibilityColumn) and isinstance(cell, EligibilityCell):
        return display_eligibility_cell(column, cell)
    if cell.canonical_value is None:
        return f"{cell.availability}: {', '.join(cell.reason_codes)}"
    if column.value_type == "TEXT":
        return cell.canonical_value
    if isinstance(column, PooledColumn):
        return _pooled_number(column, cell.canonical_value)
    return _legacy_number(column, cell.canonical_value)


def _pooled_number(column: PooledColumn, value: str) -> str:
    display = display_number(
        value,
        column.display_decimal_places or 0,
        percent=column.display_conversion == "RATIO_TO_PERCENT_DISPLAY",
    )
    return display + (f" {column.currency}" if column.value_type == "MONEY" else "%")


def _legacy_number(column: CompositeColumn | LinkedColumn | EligibilityColumn, value: str) -> str:
    number = decimal_value(value, linked=isinstance(column, LinkedColumn))
    with localcontext() as context:
        context.prec = 2_048
        if column.display_conversion == "RATIO_TO_PERCENT_DISPLAY":
            number *= Decimal(100)
        if column.display_decimal_places is not None:
            quantum = Decimal(1).scaleb(-column.display_decimal_places)
            number = number.quantize(quantum, rounding=ROUND_HALF_UP)
        display = format(number, "f")
    suffix = {"PERCENT": "%", "PERCENTAGE_POINTS": " pp"}.get(column.display_unit, "")
    if column.value_type == "MONEY":
        suffix = f" {column.currency}"
    return display + suffix
