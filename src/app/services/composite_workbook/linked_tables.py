"""Complete reviewed v3 table membership and exact source-cell/column policy admission."""

from typing import Any

from app.contracts.composite_linked import (
    CompositeLinkedContent,
    LinkedColumn,
    LinkedFacts,
    LinkedRow,
    LinkedTable,
)
from app.contracts.composite_review import CompositeCell
from app.services.composite_workbook.linked_source import LINKED_FINANCIAL_POLICY
from app.services.composite_workbook.source_values import resolve_pointer

LINKED_TABLE_COLUMNS = {
    "Summary": (
        "metric_id",
        "method",
        "status",
        "qualification",
        "constituent_decomposition",
        "period_start",
        "period_end",
        "return_view",
        "reporting_currency",
        "cumulative_return",
        "total_linked_contribution",
        "reconciliation_difference",
        "display_rounding_difference",
    ),
    "LinkedContribution": ("portfolio_id", "linked_contribution", "participating_period_count"),
    "LinkedPeriods": (
        "portfolio_id",
        "period_start",
        "period_end",
        "return_value",
        "beginning_market_value",
        "weight",
        "contribution",
        "linking_factor",
        "linked_contribution",
        "source_snapshot_id",
        "source_fingerprint",
        "calculation_id",
        "restatement_version",
        "restatement_sequence",
    ),
    "Methods": ("method", "units"),
    "Lineage": ("engine_version", "calculation_fingerprint"),
    "Disclosures": ("code", "text"),
    "UncapturedProducts": ("product", "availability", "value", "reason_code"),
}
UNCAPTURED_PRODUCTS = {
    "CalendarReturns",
    "TrailingReturns",
    "SinceInception",
    "Risk",
    "Attribution",
    "ApprovedRestatement",
    "CompleteEligibilityPopulation",
}
_DISCLOSURES = {
    "CALCULATED_REPLAY_NOT_OFFICIAL",
    "SOURCE_QUALIFICATION",
    "SOURCE_OWNED_LINKING",
    "PRECISION_AND_UNITS",
}


def validate_linked_tables(content: CompositeLinkedContent) -> None:
    dataset = content.model_dump(mode="python")
    _validate_facts(content.report_facts)
    if [table.table_id for table in content.tables] != list(LINKED_TABLE_COLUMNS):
        raise ValueError("composite_linked_table_set_invalid")
    for table in content.tables:
        _validate_table(dataset, table)


def _validate_facts(facts: dict[str, Any]) -> None:
    typed = LinkedFacts.model_validate(facts)
    codes = [item.code for item in typed.disclosures]
    if len(set(codes)) != len(codes) or not _DISCLOSURES.issubset(codes):
        raise ValueError("composite_linked_disclosure_missing")
    if {item.product for item in typed.uncaptured} != UNCAPTURED_PRODUCTS:
        raise ValueError("composite_linked_uncaptured_incomplete")


def _expected_rows(dataset: dict[str, Any], name: str) -> list[tuple[str, str]]:
    single = {
        "Summary": ("linked-summary", "/source_response"),
        "Methods": ("source-method", "/source_response"),
        "Lineage": ("selection", "/source_response/selection_manifest"),
    }
    if name in single:
        return [single[name]]
    base = {
        "LinkedContribution": "/source_response/members",
        "LinkedPeriods": "/source_response/periods",
        "Disclosures": "/report_facts/disclosures",
        "UncapturedProducts": "/report_facts/uncaptured",
    }[name]
    return [(str(index), f"{base}/{index}") for index in range(len(resolve_pointer(dataset, base)))]


def _validate_table(dataset: dict[str, Any], table: LinkedTable) -> None:
    columns = LINKED_TABLE_COLUMNS[table.table_id]
    if [column.column_id for column in table.columns] != list(columns):
        raise ValueError("composite_linked_columns_incomplete")
    expected_rows = _expected_rows(dataset, table.table_id)
    if [row.row_id for row in table.rows] != [key for key, _ in expected_rows]:
        raise ValueError("composite_linked_rows_incomplete")
    currency = dataset["source_response"]["reporting_currency"]
    for column in table.columns:
        _validate_column(column, currency)
    for row, (_, base) in zip(table.rows, expected_rows, strict=True):
        _validate_row(dataset, row, base, columns)


def _validate_row(
    dataset: dict[str, Any], row: LinkedRow, base: str, columns: tuple[str, ...]
) -> None:
    if set(row.cells) != set(columns):
        raise ValueError("composite_table_row_incomplete")
    for key, cell in row.cells.items():
        _validate_cell(dataset, cell, f"{base}/{key}")


def _validate_cell(dataset: dict[str, Any], cell: CompositeCell, pointer: str) -> None:
    source = resolve_pointer(dataset, pointer)
    if cell.source_pointer != pointer or cell.canonical_value != (
        None if source is None else str(source)
    ):
        raise ValueError("composite_linked_cell_source_conflict")
    reason = (
        "SOURCE_PRODUCT_NOT_CAPTURED"
        if pointer.startswith("/report_facts/uncaptured/") and pointer.endswith("/value")
        else "SOURCE_IDENTITY_NOT_PROVIDED"
    )
    expected = ("UNAVAILABLE", [reason]) if source is None else ("AVAILABLE", [])
    if (cell.availability, cell.reason_codes) != expected:
        raise ValueError("composite_linked_cell_availability_conflict")


def _validate_column(column: LinkedColumn, currency: str) -> None:
    policy = LINKED_FINANCIAL_POLICY.get(column.column_id, ("TEXT", "TEXT", "TEXT", None))
    value_type, unit, display, places = policy
    conversion = "RATIO_TO_PERCENT_DISPLAY" if value_type == "DECIMAL_RETURN" else "IDENTITY"
    expected = (
        value_type,
        unit,
        display,
        places,
        conversion,
        currency if value_type == "MONEY" else None,
    )
    if (
        column.value_type,
        column.unit,
        column.display_unit,
        column.display_decimal_places,
        column.display_conversion,
        column.currency,
    ) != expected or column.label != column.column_id.replace("_", " "):
        raise ValueError("composite_linked_column_policy_conflict")
