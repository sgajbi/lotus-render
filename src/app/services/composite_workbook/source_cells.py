"""Verify source-bound semantic cells, never derive missing financial facts."""

import json
import re
from collections.abc import Mapping
from typing import Any

from app.contracts.composite_amendment import CompositeAmendmentContent
from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.contracts.composite_linked import CompositeLinkedContent
from app.contracts.composite_pooled import CompositePooledReportData
from app.contracts.composite_products import (
    CompositeContent,
    CompositeProductsContent,
    ProductTable,
)
from app.contracts.composite_review import (
    CompositeCell,
    CompositeColumn,
    CompositeReviewContent,
    CompositeTable,
)
from app.contracts.composite_selection import CompositePinnedSelection
from app.services.composite_workbook.amendment_source import validate_amendment_source
from app.services.composite_workbook.amendment_tables import validate_amendment_tables
from app.services.composite_workbook.eligibility_source import validate_eligibility_source
from app.services.composite_workbook.eligibility_tables import validate_eligibility_tables
from app.services.composite_workbook.linked_source import validate_linked_source
from app.services.composite_workbook.linked_tables import validate_linked_tables
from app.services.composite_workbook.pinned_identity import validate_pinned_identity
from app.services.composite_workbook.product_tables import validate_product_tables
from app.services.composite_workbook.source_products import (
    PRODUCT_RETURN_POINTER,
    validate_product_pointer,
    validate_response_digest,
    validate_source_products,
)
from app.services.composite_workbook.source_values import decimal_value, resolve_pointer

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
_FINANCIAL_POINTER = re.compile(
    r"^/source_response/(?:cumulative_return|periods/(?:0|[1-9]\d*)/"
    r"(?:[a-z_]+|member_contributions/(?:0|[1-9]\d*)/[a-z_]+))$"
)


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
    if dataset.get("contract_version") == "composite_review.v2":
        validate_product_pointer(cell.source_pointer, column.value_type)
    source = resolve_pointer(dataset, cell.source_pointer)
    if isinstance(source, bool) or not (source is None or isinstance(source, (str, int))):
        raise ValueError("composite_cell_source_invalid")
    if cell.canonical_value != (None if source is None else str(source)):
        raise ValueError("composite_cell_source_value_conflict")
    _validate_financial_cell(column, cell)
    if dataset.get("contract_version") == "composite_review.v2":
        _validate_financial_basename(cell)


def _validate_financial_basename(cell: CompositeCell) -> None:
    field = cell.source_pointer.rsplit("/", 1)[-1]
    if field in FINANCIAL_FIELDS and not (
        _FINANCIAL_POINTER.fullmatch(cell.source_pointer)
        or PRODUCT_RETURN_POINTER.fullmatch(cell.source_pointer)
    ):
        raise ValueError("composite_cell_financial_path_not_authorized")


def _validate_financial_cell(column: CompositeColumn, cell: CompositeCell) -> None:
    field = cell.source_pointer.rsplit("/", 1)[-1]
    financial_field = (
        _FINANCIAL_POINTER.fullmatch(cell.source_pointer) is not None and field in FINANCIAL_FIELDS
    ) or PRODUCT_RETURN_POINTER.fullmatch(cell.source_pointer) is not None
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


def validate_table(dataset: dict[str, Any], table: CompositeTable | ProductTable) -> None:
    keys = [column.column_id for column in table.columns]
    if len(keys) != len(set(keys)) or len({row.row_id for row in table.rows}) != len(table.rows):
        raise ValueError("composite_table_identity_duplicated")
    for column in table.columns:
        validate_column(column, dataset["selection"].get("reporting_currency"))
    for row in table.rows:
        _validate_row(dataset, table, row.cells)


def _validate_row(
    dataset: dict[str, Any],
    table: CompositeTable | ProductTable,
    cells: Mapping[str, CompositeCell],
) -> None:
    if set(cells) != {column.column_id for column in table.columns}:
        raise ValueError("composite_table_row_incomplete")
    for column in table.columns:
        validate_cell(dataset, column, cells[column.column_id])


def validate_dataset(dataset: dict[str, Any]) -> CompositeContent:
    if dataset.get("contract_version") == "composite_review.v6":
        amendment = CompositeAmendmentContent.model_validate_json(
            json.dumps(dataset, allow_nan=False)
        )
        validate_amendment_source(amendment, dataset)
        validate_amendment_tables(amendment, dataset)
        return amendment
    if dataset.get("contract_version") == "composite_review.v5":
        return CompositePooledReportData.model_validate_json(json.dumps(dataset, allow_nan=False))
    if dataset.get("contract_version") == "composite_review.v4":
        eligibility = CompositeEligibilityContent.model_validate_json(json.dumps(dataset))
        validate_eligibility_source(eligibility, dataset)
        validate_eligibility_tables(eligibility, dataset)
        return eligibility
    if dataset.get("contract_version") == "composite_review.v3":
        linked = CompositeLinkedContent.model_validate(dataset)
        validate_linked_source(linked)
        validate_linked_tables(linked)
        return linked
    return _validate_return_dataset(dataset)


def _validate_return_dataset(
    dataset: dict[str, Any],
) -> CompositeReviewContent | CompositeProductsContent:
    content: CompositeReviewContent | CompositeProductsContent
    if dataset.get("contract_version") == "composite_review.v2":
        content = CompositeProductsContent.model_validate(dataset)
    else:
        content = CompositeReviewContent.model_validate(dataset)
    # Strict JSON admits ISO date/UUID wire strings while preserving the original
    # retained mapping; it does not coerce numeric strings or rewrite source text.
    CompositePinnedSelection.model_validate_json(json.dumps(content.selection))
    validate_response_digest(
        content.selection, content.source_response, content.source_response_digest
    )
    if content.tenant_id != content.selection.get("tenant_id"):
        raise ValueError("composite_source_tenant_conflict")
    validate_pinned_identity(content)
    if isinstance(content, CompositeProductsContent):
        validate_source_products(content)
    if len({table.table_id for table in content.tables}) != len(content.tables):
        raise ValueError("composite_table_identity_duplicated")
    for table in content.tables:
        validate_table(dataset, table)
    if isinstance(content, CompositeProductsContent):
        validate_product_tables(content)
    return content
