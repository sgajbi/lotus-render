"""Verify source-bound semantic cells, never derive missing financial facts."""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.composite_review import (
    CompositeCell,
    CompositeColumn,
    CompositeReviewContent,
    CompositeTable,
)
from app.contracts.composite_selection import CompositePinnedSelection
from app.services.composite_workbook.pinned_identity import validate_pinned_identity

FINANCIAL_FIELDS = {
    "return_value": ("DECIMAL_RETURN", "PERCENT"),
    "cumulative_return": ("DECIMAL_RETURN", "PERCENT"),
    "dispersion_equal_weight": ("DECIMAL_RETURN", "PERCENT"),
    "beginning_asset_weight": ("DECIMAL_RETURN", "PERCENT"),
    "contribution": ("DECIMAL_RETURN", "PERCENTAGE_POINTS"),
    "beginning_market_value": ("MONEY", "CURRENCY_UNITS"),
    "ending_market_value": ("MONEY", "CURRENCY_UNITS"),
    "member_count": ("COUNT", "PORTFOLIO_COUNT"),
    "excluded_member_count": ("COUNT", "PORTFOLIO_COUNT"),
}
_DECIMAL_TEXT = re.compile(r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d{1,4})?$")
_FINANCIAL_POINTER = re.compile(
    r"^/source_response/(?:cumulative_return|periods/(?:0|[1-9]\d*)/"
    r"(?:[a-z_]+|member_contributions/(?:0|[1-9]\d*)/[a-z_]+))$"
)


def resolve_pointer(dataset: dict[str, Any], pointer: str) -> Any:
    current: Any = dataset
    try:
        for token in pointer.split("/")[1:]:
            if re.search(r"~(?![01])", token):
                raise ValueError("invalid JSON pointer escape")
            key = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, list):
                if not re.fullmatch(r"0|[1-9]\d*", key):
                    raise ValueError("invalid array index")
                current = current[int(key)]
            elif isinstance(current, dict):
                current = current[key]
            else:
                raise ValueError("pointer does not name a scalar")
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("composite_cell_pointer_invalid") from exc
    return current


def decimal_value(value: str) -> Decimal:
    if len(value) > 256 or not _DECIMAL_TEXT.fullmatch(value):
        raise ValueError("composite_cell_number_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("composite_cell_number_invalid") from exc
    if not number.is_finite() or abs(number.adjusted()) > 1_000:
        raise ValueError("composite_cell_number_invalid")
    return number


def validate_column(column: CompositeColumn, currency: object) -> None:
    expected: tuple[object, ...]
    if column.value_type == "DECIMAL_RETURN":
        expected = ("DECIMAL_RATIO", column.display_unit, "RATIO_TO_PERCENT_DISPLAY", None)
        if column.display_unit not in {"PERCENT", "PERCENTAGE_POINTS"}:
            raise ValueError("composite_column_unit_conflict")
        if column.display_decimal_places is None:
            raise ValueError("composite_column_rounding_missing")
    else:
        unit = {"TEXT": "TEXT", "MONEY": "CURRENCY_UNITS", "COUNT": "PORTFOLIO_COUNT"}[
            column.value_type
        ]
        expected = (unit, unit, "IDENTITY", currency if column.value_type == "MONEY" else None)
    actual = (column.unit, column.display_unit, column.display_conversion, column.currency)
    if actual != expected:
        raise ValueError("composite_column_unit_conflict")


def _validate_availability(cell: CompositeCell) -> None:
    if cell.availability == "AVAILABLE":
        if cell.canonical_value is None:
            raise ValueError("composite_cell_available_value_missing")
    elif cell.canonical_value is not None or not cell.reason_codes:
        raise ValueError("composite_cell_unavailable_value_conflict")
    if any(not re.fullmatch(r"[A-Za-z0-9_]{1,128}", code) for code in cell.reason_codes):
        raise ValueError("composite_cell_reason_invalid")


def validate_cell(dataset: dict[str, Any], column: CompositeColumn, cell: CompositeCell) -> None:
    _validate_availability(cell)
    source = resolve_pointer(dataset, cell.source_pointer)
    if isinstance(source, bool) or not (source is None or isinstance(source, (str, int))):
        raise ValueError("composite_cell_source_invalid")
    if cell.canonical_value != (None if source is None else str(source)):
        raise ValueError("composite_cell_source_value_conflict")
    _validate_financial_cell(column, cell)


def _validate_financial_cell(column: CompositeColumn, cell: CompositeCell) -> None:
    field = cell.source_pointer.rsplit("/", 1)[-1]
    financial_field = (
        _FINANCIAL_POINTER.fullmatch(cell.source_pointer) is not None and field in FINANCIAL_FIELDS
    )
    if column.value_type == "TEXT":
        if financial_field:
            raise ValueError("composite_cell_source_unit_conflict")
        return
    if not financial_field or FINANCIAL_FIELDS.get(field) != (
        column.value_type,
        column.display_unit,
    ):
        raise ValueError("composite_cell_source_unit_conflict")
    _validate_financial_number(column, cell)


def _validate_financial_number(column: CompositeColumn, cell: CompositeCell) -> None:
    if cell.canonical_value is not None:
        number = decimal_value(cell.canonical_value)
        if column.value_type == "COUNT" and (number < 0 or number != number.to_integral_value()):
            raise ValueError("composite_cell_count_invalid")


def validate_table(dataset: dict[str, Any], table: CompositeTable) -> None:
    keys = [column.column_id for column in table.columns]
    if len(keys) != len(set(keys)) or len({row.row_id for row in table.rows}) != len(table.rows):
        raise ValueError("composite_table_identity_duplicated")
    for column in table.columns:
        validate_column(column, dataset["selection"].get("reporting_currency"))
    for row in table.rows:
        _validate_row(dataset, table, row.cells)


def _validate_row(
    dataset: dict[str, Any], table: CompositeTable, cells: dict[str, CompositeCell]
) -> None:
    if set(cells) != {column.column_id for column in table.columns}:
        raise ValueError("composite_table_row_incomplete")
    for column in table.columns:
        validate_cell(dataset, column, cells[column.column_id])


def validate_dataset(dataset: dict[str, Any]) -> CompositeReviewContent:
    content = CompositeReviewContent.model_validate(dataset)
    # Strict JSON admits ISO date/UUID wire strings while preserving the original
    # retained mapping; it does not coerce numeric strings or rewrite source text.
    CompositePinnedSelection.model_validate_json(json.dumps(content.selection))
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(content.source_response, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    if digest != content.source_response_digest or digest != content.selection.get(
        "response_digest"
    ):
        raise ValueError("composite_source_digest_conflict")
    if content.tenant_id != content.selection.get("tenant_id"):
        raise ValueError("composite_source_tenant_conflict")
    validate_pinned_identity(content)
    if len({table.table_id for table in content.tables}) != len(content.tables):
        raise ValueError("composite_table_identity_duplicated")
    for table in content.tables:
        validate_table(dataset, table)
    return content
