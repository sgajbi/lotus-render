"""Declared unit conversion and display rounding, separate from exact source text."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.contracts.composite_linked import LinkedColumn
from app.contracts.composite_review import CompositeCell, CompositeColumn
from app.services.composite_workbook.source_values import decimal_value


def display_cell(column: CompositeColumn | LinkedColumn, cell: CompositeCell) -> str:
    if cell.canonical_value is None:
        return f"{cell.availability}: {', '.join(cell.reason_codes)}"
    if column.value_type == "TEXT":
        return cell.canonical_value
    number = decimal_value(cell.canonical_value, linked=isinstance(column, LinkedColumn))
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
