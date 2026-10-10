"""Exact v7 pointer populations, including complete original and operation proof."""

from copy import deepcopy
from typing import Any

from app.contracts.composite_eligibility import EligibilityCell, EligibilityTable
from app.contracts.composite_historical import CompositeHistoricalContent
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.eligibility_facts import ELIGIBILITY_REPORT_FACTS
from app.services.composite_workbook.eligibility_policy import (
    ELIGIBILITY_TABLE_COLUMNS,
    eligibility_column_policy,
)
from app.services.composite_workbook.eligibility_rows import PointerRow, eligibility_rows
from app.services.composite_workbook.eligibility_tables import _validate_cell, _validate_table
from app.services.composite_workbook.historical_rows import historical_rows
from app.services.composite_workbook.source_values import resolve_pointer

CALCULATION_BOUNDARY = (
    "Configured-identity controlled producer custody only; no cryptographic or bank "
    "provenance acceptance, TWR, MWR, dispersion, contribution or model-fee calculation. "
    "CONTROLLED / NOT_ATTESTED."
)
HISTORICAL_TABLE_COLUMNS = {
    **ELIGIBILITY_TABLE_COLUMNS,
    "Amendments": ("month", "value"),
    "PolicyAdmission": ("month", "evidence_role", "value"),
}


def historical_facts() -> dict[str, Any]:
    facts: dict[str, Any] = deepcopy(ELIGIBILITY_REPORT_FACTS)
    facts["no_amendment"] = None
    facts["evidence_roles"] = {
        key: key for key in ("POLICY_ADMISSION", "EVALUATION_PROPOSAL", "EVALUATION_APPROVAL")
    }
    facts["disclosures"].append(
        {"code": "HISTORICAL_POLICY_CUSTODY_BOUNDARY", "text": CALCULATION_BOUNDARY}
    )
    return facts


def validate_historical_tables(content: CompositeHistoricalContent, raw: dict[str, Any]) -> None:
    if content.report_facts != historical_facts():
        raise ValueError("composite_historical_report_facts_conflict")
    if [table.table_id for table in content.tables] != list(HISTORICAL_TABLE_COLUMNS):
        raise ValueError("composite_historical_table_population_conflict")
    expected = {**eligibility_rows(raw), **historical_rows(raw)}
    for table in content.tables:
        if table.table_id in ELIGIBILITY_TABLE_COLUMNS:
            _validate_table(
                raw, table, expected[table.table_id], content.selection.reporting_currency
            )
            continue
        _validate_provenance_table(
            raw, table, expected[table.table_id], content.selection.reporting_currency
        )


def _validate_provenance_table(
    raw: dict[str, Any],
    table: EligibilityTable,
    rows: list[PointerRow],
    currency: str,
) -> None:
    columns = HISTORICAL_TABLE_COLUMNS[table.table_id]
    policies = [eligibility_column_policy(key, currency) for key in columns]
    if table.title != table.table_id or [c.model_dump() for c in table.columns] != policies:
        raise ValueError("composite_historical_column_policy_conflict")
    if [row.row_id for row in table.rows] != [identity for identity, _ in rows]:
        raise ValueError("composite_historical_row_population_conflict")
    _validate_provenance_rows(raw, table, rows, columns)


def _validate_provenance_rows(
    raw: dict[str, Any], table: EligibilityTable, rows: list[PointerRow], columns: tuple[str, ...]
) -> None:
    for row, (_, fields) in zip(table.rows, rows, strict=True):
        if set(row.cells) != set(columns):
            raise ValueError("composite_historical_cell_population_conflict")
        for key, cell in row.cells.items():
            _validate_provenance_cell(raw, cell, fields[key])


def _validate_provenance_cell(raw: dict[str, Any], cell: EligibilityCell, pointer: str) -> None:
    reason = None
    if pointer == "/report_facts/no_amendment":
        reason = "ORDINARY_ROOT_NO_AMENDMENT"
    elif pointer.endswith("/scope/run_id") and resolve_pointer(raw, pointer) is None:
        reason = "POLICY_RUN_NOT_APPLICABLE"
    if reason is None:
        _validate_cell(raw, cell, pointer)
    elif cell.model_dump() != {
        "canonical_value": None,
        "availability": "NOT_APPLICABLE",
        "reason_codes": [reason],
        "source_pointer": pointer,
    }:
        raise ValueError("composite_historical_null_policy_conflict")


def validate_historical_table_set(layout: dict[str, Any], table_names: set[str]) -> None:
    if (
        layout.get("required_tables") != list(HISTORICAL_TABLE_COLUMNS)
        or layout.get("optional_tables") != []
        or layout.get("period_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if table_names != set(HISTORICAL_TABLE_COLUMNS):
        raise ValueError("composite_workbook_table_set_invalid")
