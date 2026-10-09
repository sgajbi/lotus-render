"""Malformed retained evidence and ambiguous authority fail before workbook projection."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.composite_review import CompositeCell, CompositeColumn, CompositeReviewContent
from app.contracts.composite_selection import CompositePinnedSelection
from app.services.composite_workbook.pinned_identity import validate_pinned_identity
from app.services.composite_workbook.presentation import display_cell
from app.services.composite_workbook.source_cells import (
    validate_cell,
    validate_column,
)
from app.services.composite_workbook.source_values import resolve_pointer


def _data() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        Path("tests/golden/composite-review/v1/report-data.json").read_text()
    )
    return value


@pytest.mark.parametrize(
    "pointer,value,code",
    [
        ("/source_response/periods/0/status", "UNKNOWN", "source_status_invalid"),
        ("/source_response/periods/0/member_contributions", {}, "population_incomplete"),
        ("/source_response/periods/0/member_contributions/0", "invalid", "source_member_invalid"),
        ("/source_response/periods/0/status", "BLOCKED", "blocked_financial_value"),
        ("/source_response/periods/0/return_value", None, "ready_financial_value_missing"),
        ("/source_response/periods/0/reporting_currency", None, "period_context_missing"),
        ("/source_response/selection_manifest", None, "source_manifest_missing"),
        ("/source_response/periods", {}, "source_period_missing"),
        ("/source_response/periods/0", None, "source_period_invalid"),
        ("/source_response/status", "UNKNOWN", "source_status_invalid"),
        ("/source_response/status", "BLOCKED", "blocked_financial_value"),
        ("/report_facts/qualification", "OFFICIAL", "authority_conflict"),
        ("/selection/windows", [], "source_manifest_missing"),
        ("/selection/windows/0/restatement_sequence", True, "window_pin_invalid"),
        ("/selection/windows/0/source_cut_id", "", "window_pin_missing"),
        ("/selection/windows/0", None, "window_pin_missing"),
    ],
)
def test_retained_identity_guard_refuses_malformed_evidence(
    pointer: str, value: Any, code: str
) -> None:
    data = _data()
    parent_pointer, key = pointer.rsplit("/", 1)
    parent = resolve_pointer(data, parent_pointer)
    parent[int(key) if isinstance(parent, list) else key] = value
    if pointer.startswith("/selection/windows/0"):
        data["source_response"]["selection_manifest"]["windows"] = data["selection"]["windows"]
    # Exercise the retained-evidence boundary independently of the selector's
    # earlier wire validator; neither boundary may trust malformed source data.
    with pytest.raises(ValueError, match=code):
        validate_pinned_identity(CompositeReviewContent.model_validate(data))


def test_degraded_missing_context_keeps_unavailable_values_without_inference() -> None:
    data = _data()
    for period in data["source_response"]["periods"]:
        period.update(status="DEGRADED", return_value=None, cumulative_return=None)
        period.pop("reporting_currency")
        period.pop("return_view")
    data["source_response"].update(status="DEGRADED", cumulative_return=None)
    validate_pinned_identity(CompositeReviewContent.model_validate(data))


@pytest.mark.parametrize("change", ["reversed_window", "horizon"])
def test_selector_dates_cannot_reverse_or_escape_declared_horizon(change: str) -> None:
    selection = _data()["selection"]
    if change == "reversed_window":
        selection["windows"][0]["period_end"] = "2025-12-31"
        code = "window_dates_invalid"
    else:
        selection["period_end"] = "2026-03-01"
        code = "horizon_conflict"
    with pytest.raises(ValueError, match=code):
        CompositePinnedSelection.model_validate_json(json.dumps(selection))


@pytest.mark.parametrize("value", [True, {}, [], 0.25])
def test_cells_reject_non_literal_source_scalars(value: Any) -> None:
    column = CompositeColumn.model_validate(_data()["tables"][0]["columns"][0])
    cell = CompositeCell(
        canonical_value="value",
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/selection/unsafe",
    )
    with pytest.raises(ValueError, match="source_invalid"):
        validate_cell({"selection": {"unsafe": value}}, column, cell)


def test_pointer_cannot_traverse_a_scalar() -> None:
    with pytest.raises(ValueError, match="pointer_invalid"):
        resolve_pointer({"selection": {"literal": "id"}}, "/selection/literal/child")


@pytest.mark.parametrize("value", ["-1", "1.5"])
def test_population_count_cannot_be_negative_or_fractional(value: str) -> None:
    column = CompositeColumn(
        column_id="count",
        label="Count",
        value_type="COUNT",
        unit="PORTFOLIO_COUNT",
        display_unit="PORTFOLIO_COUNT",
        display_conversion="IDENTITY",
        display_decimal_places=None,
        display_rounding_mode="HALF_UP",
        currency=None,
        scale="1",
    )
    cell = CompositeCell(
        canonical_value=value,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/source_response/periods/0/member_count",
    )
    with pytest.raises(ValueError, match="count_invalid"):
        validate_cell({"source_response": {"periods": [{"member_count": value}]}}, column, cell)


def test_decimal_return_cannot_claim_currency_display() -> None:
    column = CompositeColumn.model_validate(_data()["tables"][0]["columns"][1])
    column = column.model_copy(
        update={"value_type": "DECIMAL_RETURN", "display_unit": "CURRENCY_UNITS"}
    )
    with pytest.raises(ValueError, match="unit_conflict"):
        validate_column(column, "USD")


def test_exact_money_without_quantization_retains_canonical_display() -> None:
    column = CompositeColumn(
        column_id="money",
        label="Money",
        value_type="MONEY",
        unit="CURRENCY_UNITS",
        display_unit="CURRENCY_UNITS",
        display_conversion="IDENTITY",
        display_decimal_places=None,
        display_rounding_mode="HALF_UP",
        currency="USD",
        scale="1",
    )
    cell = CompositeCell(
        canonical_value="12345678901234567890.123456789",
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/source_response/periods/0/beginning_market_value",
    )
    validate_column(column, "USD")
    assert display_cell(column, cell) == "12345678901234567890.123456789 USD"
