"""Complete primary populations and pointer recipes frozen with Report v8."""

import calendar
from datetime import date
from typing import Any

from app.contracts.composite_source_context import CompositeSourceContextContent
from app.services.composite_workbook.source_context import require

PERIOD_FIELDS = (
    "period_start",
    "period_end",
    "status",
    "return_value",
    "cumulative_return",
    "beginning_market_value",
    "ending_market_value",
    "member_count",
    "excluded_member_count",
    "dispersion_equal_weight",
    "return_view",
    "reporting_currency",
    "restatement_sequence",
)
MEMBER_FIELDS = (
    "portfolio_id",
    "period_start",
    "period_end",
    "return_value",
    "beginning_market_value",
    "beginning_asset_weight",
    "contribution",
    "source_snapshot_id",
    "source_fingerprint",
    "restatement_version",
    "restatement_sequence",
)
SUMMARY_POINTERS = {
    "composite_id": "/selection/composite_id",
    "period_start": "/selection/period_start",
    "period_end": "/selection/period_end",
    "return_view": "/selection/return_view",
    "currency": "/selection/reporting_currency",
    "return": "/source_response/cumulative_return",
    "status": "/source_response/status",
    "qualification": "/report_facts/qualification",
    "publication": "/report_facts/publication_state",
    "authority_receipt": "/report_facts/authority/receipt",
    "control_revision": "/report_facts/authority/control_revision",
}


def validate_primary_tables(content: CompositeSourceContextContent) -> None:
    tables = {table.table_id: table for table in content.tables}
    _require_rows(tables["Summary"], [("summary", SUMMARY_POINTERS)])
    monthly = all(_complete_month(window) for window in content.selection["windows"])
    name = "MonthlyReturns" if monthly else "PeriodReturns"
    require(("PeriodReturns" if monthly else "MonthlyReturns") not in tables)
    periods = content.source_response["periods"]
    rows = [
        (str(i), {key: f"/source_response/periods/{i}/{key}" for key in PERIOD_FIELDS})
        for i in range(len(periods))
    ]
    _require_rows(tables[name], rows)
    _require_rows(tables["Contribution"], _member_rows(periods))
    _validate_pointer_tables(content, tables)
    _validate_disclosures(content, tables["Disclosures"])
    _validate_uncaptured(content, tables)


def _complete_month(window: dict[str, Any]) -> bool:
    start, end = (
        date.fromisoformat(window["period_start"]),
        date.fromisoformat(window["period_end"]),
    )
    return (
        start.day == 1
        and (start.year, start.month) == (end.year, end.month)
        and (end.day == calendar.monthrange(end.year, end.month)[1])
    )


def _require_rows(table: Any, expected: list[tuple[str, dict[str, str]]]) -> None:
    actual = [
        (row.row_id, {key: cell.source_pointer for key, cell in row.cells.items()})
        for row in table.rows
    ]
    require(actual == expected)
    require([c.column_id for c in table.columns] == list(expected[0][1]))
    for column in table.columns:
        places = {"TEXT": None, "DECIMAL_RETURN": 2, "MONEY": 2, "COUNT": 0}
        require(column.display_decimal_places == places[column.value_type])
    for row in table.rows:
        for cell in row.cells.values():
            _require_primary_availability(cell)


def _require_primary_availability(cell: Any) -> None:
    if cell.canonical_value is not None:
        require(cell.availability == "AVAILABLE" and cell.reason_codes == [])
        return
    reason = (
        "SOURCE_AUTHORITY_NOT_ATTESTED"
        if "/authority/" in cell.source_pointer
        else "SOURCE_PRODUCT_NOT_CAPTURED"
        if "/uncaptured/" in cell.source_pointer
        else "SOURCE_VALUE_UNAVAILABLE"
    )
    require(cell.availability == "UNAVAILABLE" and cell.reason_codes == [reason])


def _member_rows(periods: list[dict[str, Any]]) -> list[tuple[str, dict[str, str]]]:
    rows = [
        (
            f"{i}:{j}",
            {
                key: f"/source_response/periods/{i}/member_contributions/{j}/{key}"
                for key in MEMBER_FIELDS
            },
        )
        for i, period in enumerate(periods)
        for j in range(len(period["member_contributions"]))
    ]
    return rows or [("unavailable", {"value": "/report_facts/unavailable_contribution"})]


def _validate_pointer_tables(
    content: CompositeSourceContextContent, tables: dict[str, Any]
) -> None:
    methods = ["/selection/methodology", "/selection/engine_version"]
    lineage = [
        "/selection/calculation_id",
        "/selection/calculation_fingerprint",
        "/report_facts/source_response_digest",
    ]
    for i, window in enumerate(content.selection["windows"]):
        methods.extend(
            f"/selection/windows/{i}/method_binding/" + key.replace("~", "~0").replace("/", "~1")
            for key in sorted(window["method_binding"])
        )
        lineage.extend(
            f"/selection/windows/{i}/{key}"
            for key in (
                "materialization_id",
                "definition_content_hash",
                "membership_content_hash",
                "attestation_content_hash",
                "source_cut_id",
                "retained_receipt_fingerprint",
            )
        )
    for name, pointers in (("Methods", methods), ("Lineage", lineage)):
        require(content.report_facts[name] == pointers)
        _require_rows(
            tables[name],
            [
                (str(i), {"field": f"/report_facts/{name}/{i}", "value": p})
                for i, p in enumerate(pointers)
            ],
        )
    require(content.report_facts["source_response_digest"] == content.source_response_digest)


def _validate_disclosures(content: CompositeSourceContextContent, table: Any) -> None:
    codes = [
        "CALCULATED_REPLAY_NOT_OFFICIAL",
        "FINANCIAL_VALUES_SOURCE_OWNED",
        "EXACT_VALUES_AND_DISPLAY",
        "NULL_IS_NOT_ZERO",
        "COUNT_SCOPE",
    ]
    require([d["code"] for d in content.report_facts["disclosures"]] == codes)
    _require_rows(
        table,
        [
            (str(i), {key: f"/report_facts/disclosures/{i}/{key}" for key in ("code", "text")})
            for i in range(len(codes))
        ],
    )


def _validate_uncaptured(content: CompositeSourceContextContent, tables: dict[str, Any]) -> None:
    expected = {
        "AnnualReturns",
        "Risk",
        "Members",
        "EligibilityReasons",
        "MembershipHistory",
        "Attribution",
        "Restatement",
    }
    if any(p.pin.kind == "CALENDAR_RETURN" for p in content.source_products):
        expected.remove("AnnualReturns")
    if content.supplied_memberships:
        expected.remove("MembershipHistory")
    require(set(content.report_facts["uncaptured"]) == expected)
    for name in expected:
        facts = content.report_facts["uncaptured"][name]
        require(facts["value"] is None and facts["reason_code"] == "SOURCE_PRODUCT_NOT_CAPTURED")
        _require_rows(
            tables[name],
            [
                (
                    "unavailable",
                    {
                        key: f"/report_facts/uncaptured/{name}/{key}"
                        for key in ("metric", "value", "reason_code")
                    },
                )
            ],
        )
