"""Exact v6 eligibility tables plus all ordered amendment scalar occurrences."""

import json
from typing import Any, cast

from app.contracts.composite_amendment import CompositeAmendmentContent, MonthlyAmendment
from app.contracts.composite_eligibility import EligibilityTable
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.eligibility_facts import ELIGIBILITY_REPORT_FACTS
from app.services.composite_workbook.eligibility_policy import (
    ELIGIBILITY_TABLE_COLUMNS,
    eligibility_column_policy,
)
from app.services.composite_workbook.eligibility_rows import PointerRow, eligibility_rows
from app.services.composite_workbook.eligibility_tables import _validate_rows, _validate_table

AMENDMENT_TABLE_COLUMNS = {**ELIGIBILITY_TABLE_COLUMNS, "Amendments": ("month", "value")}
AMENDMENT_REPORT_FACTS = {
    **ELIGIBILITY_REPORT_FACTS,
    "disclosures": [
        *cast(list[dict[str, str]], ELIGIBILITY_REPORT_FACTS["disclosures"]),
        {
            "code": "SOURCE_CORRECTION_ONLY",
            "text": "Ordinary-month source correction with unchanged approved policy and expected "
            "population. Full predecessor/original custody is retained; no Performance aggregates "
            "are joined. XLSX is unavailable until explicit Render and Archive v6 support.",
        },
    ],
}


def _leaves(value: Any, pointer: str) -> list[str]:
    if isinstance(value, dict):
        return [
            leaf
            for key, child in value.items()
            for leaf in _leaves(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        ]
    if isinstance(value, list):
        return [
            leaf
            for index, child in enumerate(value)
            for leaf in _leaves(child, f"{pointer}/{index}")
        ]
    return [pointer]


def amendment_rows(raw: dict[str, Any]) -> list[PointerRow]:
    rows: list[PointerRow] = []
    for index, month in enumerate(raw["source_months"]):
        root = f"/source_months/{index}"
        proposal_path = (
            "/proposal"
            if month["evidence_kind"] == "EVALUATED_ONLY"
            else "/receipt/approval/proposal"
        )
        proposal = (
            month["proposal"] if "proposal" in month else month["receipt"]["approval"]["proposal"]
        )
        pointers = _amendment_pointers(proposal["amendment"], root + proposal_path + "/amendment")
        for ordinal, receipt in enumerate(month["lineage_receipts"]):
            base = f"{root}/lineage_receipts/{ordinal}"
            pointers.extend(
                base + "/" + key
                for key in (
                    "product_name",
                    "product_version",
                    "content_hash",
                    "publication_sequence",
                )
            )
            if "lineage" in receipt:
                pointers.extend(_amendment_pointers(receipt["lineage"], base + "/lineage"))
        rows.extend(
            (
                f"m{index}:a{ordinal}",
                {"month": f"/selection/months/{index}/month", "value": pointer},
            )
            for ordinal, pointer in enumerate(pointers)
        )
    return rows


def _amendment_pointers(value: dict[str, Any], pointer: str) -> list[str]:
    # Report's frozen DTO field order defines row occurrence order. JSON object
    # insertion order is not evidence and changes during sorted pinned replay.
    typed = MonthlyAmendment.model_validate_json(json.dumps(value))
    return _leaves(typed.model_dump(mode="json"), pointer)


def validate_amendment_tables(content: CompositeAmendmentContent, raw: dict[str, Any]) -> None:
    if content.report_facts != AMENDMENT_REPORT_FACTS:
        raise ValueError("composite_amendment_report_facts_conflict")
    if [table.table_id for table in content.tables] != list(AMENDMENT_TABLE_COLUMNS):
        raise ValueError("composite_amendment_table_population_conflict")
    expected = {**eligibility_rows(raw), "Amendments": amendment_rows(raw)}
    for table in content.tables:
        if table.table_id == "Amendments":
            _validate_amendment_table(
                raw, table, expected["Amendments"], content.selection.reporting_currency
            )
        else:
            _validate_table(
                raw, table, expected[table.table_id], content.selection.reporting_currency
            )


def _validate_amendment_table(
    raw: dict[str, Any], table: EligibilityTable, rows: list[PointerRow], currency: str
) -> None:
    columns = AMENDMENT_TABLE_COLUMNS["Amendments"]
    if table.title != "Amendments" or [c.model_dump() for c in table.columns] != [
        eligibility_column_policy(key, currency) for key in columns
    ]:
        raise ValueError("composite_amendment_column_policy_conflict")
    if [row.row_id for row in table.rows] != [identity for identity, _ in rows]:
        raise ValueError("composite_amendment_row_population_conflict")
    _validate_rows(raw, table, rows, columns)


def validate_amendment_table_set(layout: dict[str, Any], table_names: set[str]) -> None:
    if (
        layout.get("required_tables") != list(AMENDMENT_TABLE_COLUMNS)
        or layout.get("optional_tables") != []
        or layout.get("period_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if table_names != set(AMENDMENT_TABLE_COLUMNS):
        raise ValueError("composite_workbook_table_set_invalid")
