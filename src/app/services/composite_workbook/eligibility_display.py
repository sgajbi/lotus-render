"""Bounded literal display of operational values with no investment conversion."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from app.contracts.composite_eligibility import EligibilityCell, EligibilityColumn
from app.domain.render_attempts.models import RenderFailureCategory
from app.services.composite_workbook.literal_writer import MAX_CELL_UTF16_UNITS, validate_literal
from app.services.render_ports import RenderCompileFailedError


def display_eligibility_cell(column: EligibilityColumn, cell: EligibilityCell) -> str:
    value = cell.canonical_value
    if value is None:
        return f"{cell.availability}: {', '.join(cell.reason_codes)}"
    if column.value_type in {"TEXT", "BOOLEAN"}:
        return value
    display = _display_number(value, column.display_decimal_places or 0)
    return display + (f" {column.currency}" if column.value_type == "MONEY" else "")


def _display_number(value: str, places: int) -> str:
    # The source schema has no 256-character decimal ceiling. Bound expansion by
    # the existing literal-cell limit, while retaining source spelling in evidence.
    validate_literal(value)
    try:
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("composite_cell_number_invalid")
        if number.adjusted() >= MAX_CELL_UTF16_UNITS:
            raise RenderCompileFailedError(
                RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED,
                "composite_workbook_resource_limit_exceeded",
            )
        with localcontext() as context:
            context.prec = max(len(number.as_tuple().digits), number.adjusted() + places + 2, 32)
            display = format(
                number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f"
            )
    except InvalidOperation as exc:
        raise ValueError("composite_cell_number_invalid") from exc
    return display
