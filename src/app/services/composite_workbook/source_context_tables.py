"""Exact SI and direct supplied-history recipes; no financial derivation."""

from typing import Any

from app.contracts.composite_review import CompositeColumn
from app.contracts.composite_source_context import CompositeSourceContextContent, SourceContextTable
from app.services.composite_workbook.product_tables import validate_product_tables
from app.services.composite_workbook.source_context import product_view, require
from app.services.composite_workbook.source_context_primary import validate_primary_tables
from app.services.composite_workbook.source_values import resolve_pointer

HISTORY_FIELDS = (
    "membership_revision",
    "supersedes_membership_revision",
    "affected_from",
    "affected_to",
    "portfolio_id",
    "effective_from",
    "effective_to",
    "status",
    "reason_code",
    "discretionary",
    "approval_ref",
    "source_snapshot_id",
)
BASE_TABLES = (
    "Summary",
    "Contribution",
    "Methods",
    "Lineage",
    "Disclosures",
    "AnnualReturns",
    "Risk",
    "Members",
    "EligibilityReasons",
    "MembershipHistory",
    "Attribution",
    "Restatement",
)


def validate_source_context_tables(
    content: CompositeSourceContextContent, raw: dict[str, Any]
) -> None:
    # Import here to keep the common version dispatcher independent of this recipe.
    from app.services.composite_workbook.source_cells import validate_table

    tables = {t.table_id: t for t in content.tables}
    require(len(tables) == len(content.tables))
    for table in content.tables:
        if table.table_id == "SinceInception":
            continue
        if table.table_id == "MembershipHistory" and content.supplied_memberships:
            continue
        validate_table({**raw, "contract_version": "composite_review.v2"}, table)
    validate_product_tables(product_view(content))
    validate_primary_tables(content)
    _validate_si(content, raw, tables.get("SinceInception"))
    if content.supplied_memberships:
        _validate_history(content, raw, tables.get("MembershipHistory"))


def _column(field: str, *, financial: bool = False) -> CompositeColumn:
    return CompositeColumn(
        column_id=field,
        label=field.replace("_", " ").capitalize(),
        value_type="DECIMAL_RETURN" if financial else "TEXT",
        unit="DECIMAL_RATIO" if financial else "TEXT",
        display_unit="PERCENT" if financial else "TEXT",
        display_conversion="RATIO_TO_PERCENT_DISPLAY" if financial else "IDENTITY",
        display_decimal_places=2 if financial else None,
        currency=None,
    )


def _validate_si(
    content: CompositeSourceContextContent, raw: dict[str, Any], table: SourceContextTable | None
) -> None:
    if not content.source_context.since_inception:
        require(table is None and "since_inception" not in content.report_facts)
        return
    require(table is not None)
    assert table is not None
    reason = _si_reason(content)
    _validate_si_facts(content, reason)
    _validate_si_row(table, raw, reason)


def _validate_si_row(table: SourceContextTable, raw: dict[str, Any], reason: str | None) -> None:
    pointers = _si_pointers(reason)
    require(table.columns == [_column(k, financial=k == "return") for k in pointers])
    require(len(table.rows) == 1 and table.rows[0].row_id == "since_inception")
    expected = {
        k: _cell(raw, pointer, reason=reason if k == "return" else None, availability="UNAVAILABLE")
        for k, pointer in pointers.items()
    }
    require({k: v.model_dump() for k, v in table.rows[0].cells.items()} == expected)


def _si_reason(content: CompositeSourceContextContent) -> str | None:
    if content.selection["period_start"] != content.definition.source_response["inception_date"]:
        return "SOURCE_VECTOR_BEGINS_AFTER_PINNED_INCEPTION"
    if content.source_response["status"] != "READY" or any(
        p["status"] != "READY" for p in content.source_response["periods"]
    ):
        return "COMPLETE_READY_SOURCE_VECTOR_REQUIRED"
    return None


def _validate_si_facts(content: CompositeSourceContextContent, reason: str | None) -> None:
    require(
        content.report_facts.get("since_inception")
        == {
            "availability": "UNAVAILABLE" if reason else "AVAILABLE",
            "reason": reason or "NONE",
            "value": None if reason else content.source_response["cumulative_return"],
            "coverage_convention": "INCLUSIVE_SOURCE_INCEPTION",
        }
    )


def _si_pointers(reason: str | None) -> dict[str, str]:
    return {
        "inception_date": "/definition/source_response/inception_date",
        "period_start": "/selection/period_start",
        "period_end": "/selection/period_end",
        "return": "/report_facts/since_inception/value"
        if reason
        else "/source_response/cumulative_return",
        "availability": "/report_facts/since_inception/availability",
        "reason": "/report_facts/since_inception/reason",
        "coverage_convention": "/report_facts/since_inception/coverage_convention",
        "definition_version": "/definition/pin/definition_version",
        "definition_hash": "/definition/pin/content_hash",
        "definition_response_digest": "/definition/source_response_digest",
    }


def _cell(
    raw: dict[str, Any],
    pointer: str,
    *,
    reason: str | None = None,
    availability: str = "NOT_APPLICABLE",
    boolean: bool = False,
) -> dict[str, Any]:
    value = resolve_pointer(raw, pointer)
    if boolean:
        require(type(value) is bool)
        value = "true" if value else "false"
    return {
        "canonical_value": None if value is None else str(value),
        "source_pointer": pointer,
        "availability": availability if reason else "AVAILABLE",
        "reason_codes": [reason] if reason else [],
    }


def _validate_history(
    content: CompositeSourceContextContent, raw: dict[str, Any], table: SourceContextTable | None
) -> None:
    require(table is not None)
    assert table is not None
    require(table.columns == [_column(field) for field in HISTORY_FIELDS])
    expected = []
    for index, capture in enumerate(content.supplied_memberships):
        for ordinal, _ in enumerate(capture.source_response["decisions"]):
            base = f"/supplied_memberships/{index}/source_response"
            cells = _history_cells(raw, base, ordinal)
            expected.append({"row_id": f"r{index}:d{ordinal}", "cells": cells})
    require([r.model_dump() for r in table.rows] == expected)
    require("MembershipHistory" not in content.report_facts["uncaptured"])


def _history_cells(raw: dict[str, Any], base: str, ordinal: int) -> dict[str, Any]:
    cells = {}
    for field in HISTORY_FIELDS:
        pointer = (
            f"{base}/{field}"
            if field in HISTORY_FIELDS[:4]
            else f"{base}/decisions/{ordinal}/{field}"
        )
        reason = None
        if resolve_pointer(raw, pointer) is None:
            reason = (
                "OPEN_ENDED_INTERVAL" if field == "effective_to" else "SOURCE_FIELD_NOT_APPLICABLE"
            )
        cells[field] = _cell(raw, pointer, reason=reason, boolean=field == "discretionary")
    return cells


def validate_source_context_table_set(layout: dict[str, Any], names: set[str]) -> None:
    require(layout.get("required_tables") == list(BASE_TABLES))
    require(layout.get("optional_tables") == ["TrailingReturns", "SinceInception"])
    require(layout.get("period_tables") == ["MonthlyReturns", "PeriodReturns"])
    require(len(names & {"MonthlyReturns", "PeriodReturns"}) == 1)
    require(set(BASE_TABLES).issubset(names))
    require(
        names
        <= set(BASE_TABLES)
        | {"MonthlyReturns", "PeriodReturns", "TrailingReturns", "SinceInception"}
    )
