"""Bound decimal display expansion by the workbook's literal-cell envelope."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from app.domain.render_attempts.models import RenderFailureCategory
from app.services.composite_workbook.literal_writer import MAX_CELL_UTF16_UNITS, validate_literal
from app.services.render_ports import RenderCompileFailedError


def display_number(value: str, places: int, *, percent: bool = False) -> str:
    validate_literal(value)
    try:
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("composite_cell_number_invalid")
        shift = 2 if percent else 0
        if number.adjusted() + shift >= MAX_CELL_UTF16_UNITS:
            raise RenderCompileFailedError(
                RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED,
                "composite_workbook_resource_limit_exceeded",
            )
        with localcontext() as context:
            context.prec = max(
                len(number.as_tuple().digits), number.adjusted() + shift + places + 2, 32
            )
            number = number.scaleb(shift)
            display = format(
                number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f"
            )
    except InvalidOperation as exc:
        raise ValueError("composite_cell_number_invalid") from exc
    validate_literal(display)
    return display
