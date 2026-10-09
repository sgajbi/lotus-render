"""Independently admit the exact v4 table, row, policy and source-cell population."""

from typing import Any

from app.contracts.composite_eligibility import (
    CompositeEligibilityContent,
    EligibilityCell,
    EligibilityTable,
)
from app.services.composite_workbook.eligibility_facts import ELIGIBILITY_REPORT_FACTS
from app.services.composite_workbook.eligibility_policy import (
    ELIGIBILITY_TABLE_COLUMNS,
    eligibility_column_policy,
)
from app.services.composite_workbook.eligibility_rows import eligibility_rows
from app.services.composite_workbook.source_values import resolve_pointer


def validate_eligibility_tables(content: CompositeEligibilityContent, raw: dict[str, Any]) -> None:
    if content.report_facts != ELIGIBILITY_REPORT_FACTS:
        raise ValueError("composite_eligibility_report_facts_conflict")
    if [table.table_id for table in content.tables] != list(ELIGIBILITY_TABLE_COLUMNS):
        raise ValueError("composite_eligibility_table_population_conflict")
    expected = eligibility_rows(raw)
    for table in content.tables:
        _validate_table(raw, table, expected[table.table_id], content.selection.reporting_currency)


def _validate_table(
    raw: dict[str, Any],
    table: EligibilityTable,
    rows: list[tuple[str, dict[str, str]]],
    currency: str,
) -> None:
    columns = ELIGIBILITY_TABLE_COLUMNS[table.table_id]
    policies = [eligibility_column_policy(key, currency) for key in columns]
    if (
        table.title != table.table_id
        or [column.model_dump() for column in table.columns] != policies
    ):
        raise ValueError("composite_eligibility_column_policy_conflict")
    if [row.row_id for row in table.rows] != [identity for identity, _ in rows]:
        raise ValueError("composite_eligibility_row_population_conflict")
    _validate_rows(raw, table, rows, columns)


def _validate_rows(
    raw: dict[str, Any],
    table: EligibilityTable,
    rows: list[tuple[str, dict[str, str]]],
    columns: tuple[str, ...],
) -> None:
    for row, (_, pointers) in zip(table.rows, rows, strict=True):
        if set(row.cells) != set(columns):
            raise ValueError("composite_eligibility_cell_population_conflict")
        for key, cell in row.cells.items():
            _validate_cell(raw, cell, pointers[key])


def _validate_cell(raw: dict[str, Any], cell: EligibilityCell, pointer: str) -> None:
    source = resolve_pointer(raw, pointer)
    expected: dict[str, Any] = {
        "canonical_value": _scalar(source),
        "availability": "AVAILABLE",
        "reason_codes": [],
        "source_pointer": pointer,
    }
    if source is None:
        availability, reason = _null_policy(raw, pointer)
        expected.update(availability=availability, reason_codes=[reason])
    if cell.model_dump() != expected:
        raise ValueError("composite_eligibility_cell_source_conflict")


def _scalar(source: Any) -> str | None:
    if source is None:
        return None
    if isinstance(source, bool):
        return "true" if source else "false"
    if isinstance(source, (str, int)):
        return str(source)
    raise ValueError("composite_eligibility_source_scalar_invalid")


def _null_policy(raw: dict[str, Any], pointer: str) -> tuple[str, str]:
    if pointer == "/report_facts/no_reasons/value":
        return "NOT_APPLICABLE", "NO_APPLICABLE_REASONS"
    base, key = pointer.rsplit("/", 1)
    if "/assessments/" in base:
        rule = resolve_pointer(raw, base + "/rule")
        if rule == "READINESS" or (
            rule == "CASH" and key in {"gross_inflow", "gross_outflow", "admitted_flow_count"}
        ):
            return "NOT_APPLICABLE", "RULE_FIELD_NOT_APPLICABLE"
    return "UNAVAILABLE", "SOURCE_VALUE_UNAVAILABLE"
