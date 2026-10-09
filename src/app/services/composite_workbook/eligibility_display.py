"""Bounded literal display of operational values with no investment conversion."""

from app.contracts.composite_eligibility import EligibilityCell, EligibilityColumn
from app.services.composite_workbook.numeric_display import display_number


def display_eligibility_cell(column: EligibilityColumn, cell: EligibilityCell) -> str:
    value = cell.canonical_value
    if value is None:
        return f"{cell.availability}: {', '.join(cell.reason_codes)}"
    if column.value_type in {"TEXT", "BOOLEAN"}:
        return value
    display = display_number(value, column.display_decimal_places or 0)
    return display + (f" {column.currency}" if column.value_type == "MONEY" else "")
