"""Nonapplicable fields, unknown facts and operational displays stay distinct."""

from typing import Literal

import pytest

from app.contracts.composite_eligibility import EligibilityCell, EligibilityColumn
from app.services.composite_workbook.eligibility_display import display_eligibility_cell
from app.services.composite_workbook.eligibility_policy import eligibility_column_policy
from app.services.composite_workbook.eligibility_tables import _validate_cell
from app.services.render_ports import RenderCompileFailedError


@pytest.mark.parametrize("value", ["1" * 32768, "1e32767"], ids=["literal_width", "expanded_width"])
def test_numeric_expansion_refuses_at_existing_literal_resource_limit(value: str) -> None:
    column = EligibilityColumn.model_validate(eligibility_column_policy("ratio", "USD"))
    cell = EligibilityCell(
        canonical_value=value,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/report_facts/value",
    )
    with pytest.raises(RenderCompileFailedError, match="resource_limit_exceeded"):
        display_eligibility_cell(column, cell)


@pytest.mark.parametrize("value", ["NaN", "1e999999999999999999999999"])
def test_invalid_numeric_literal_cannot_reach_excel(value: str) -> None:
    column = EligibilityColumn.model_validate(eligibility_column_policy("ratio", "USD"))
    cell = EligibilityCell(
        canonical_value=value,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/report_facts/value",
    )
    with pytest.raises(ValueError, match="number_invalid"):
        display_eligibility_cell(column, cell)


def test_non_scalar_source_cannot_acquire_literal_cell_authority() -> None:
    pointer = "/report_facts/value"
    cell = EligibilityCell(
        canonical_value="1.5", availability="AVAILABLE", reason_codes=[], source_pointer=pointer
    )
    with pytest.raises(ValueError, match="source_scalar_invalid"):
        _validate_cell({"report_facts": {"value": 1.5}}, cell, pointer)


@pytest.mark.parametrize(
    "rule,field,reason",
    [
        ("READINESS", "ratio", "RULE_FIELD_NOT_APPLICABLE"),
        ("CASH", "gross_inflow", "RULE_FIELD_NOT_APPLICABLE"),
        ("CASH", "admitted_flow_count", "RULE_FIELD_NOT_APPLICABLE"),
        ("SIGNIFICANT_FLOW", "ratio", "SOURCE_VALUE_UNAVAILABLE"),
        ("CASH", "ratio", "SOURCE_VALUE_UNAVAILABLE"),
    ],
)
def test_null_projection_distinguishes_rule_unused_and_missing_source(
    rule: str, field: str, reason: str
) -> None:
    raw = {"source_months": [{"assessments": [{"rule": rule, field: None}]}]}
    pointer = f"/source_months/0/assessments/0/{field}"
    availability: Literal["UNAVAILABLE", "NOT_APPLICABLE"] = (
        "UNAVAILABLE" if reason == "SOURCE_VALUE_UNAVAILABLE" else "NOT_APPLICABLE"
    )
    cell = EligibilityCell(
        canonical_value=None,
        availability=availability,
        reason_codes=[reason],
        source_pointer=pointer,
    )
    _validate_cell(raw, cell, pointer)
    wrong = cell.model_copy(
        update={"canonical_value": "0", "availability": "AVAILABLE", "reason_codes": []}
    )
    with pytest.raises(ValueError, match="cell_source_conflict"):
        _validate_cell(raw, wrong, pointer)
    wrong = cell.model_copy(update={"reason_codes": ["NO_APPLICABLE_REASONS"]})
    with pytest.raises(ValueError, match="cell_source_conflict"):
        _validate_cell(raw, wrong, pointer)


def test_known_empty_reasons_use_exact_not_applicable_sentinel() -> None:
    pointer = "/report_facts/no_reasons/value"
    raw = {"report_facts": {"no_reasons": {"value": None}}}
    cell = EligibilityCell(
        canonical_value=None,
        availability="NOT_APPLICABLE",
        reason_codes=["NO_APPLICABLE_REASONS"],
        source_pointer=pointer,
    )
    _validate_cell(raw, cell, pointer)
    with pytest.raises(ValueError, match="cell_source_conflict"):
        _validate_cell(raw, cell.model_copy(update={"availability": "UNAVAILABLE"}), pointer)


@pytest.mark.parametrize(
    "key,value,display",
    [
        ("ratio", "0.10", "0.100000000000"),
        ("numerator", "12.345", "12.35 USD"),
        ("admitted_flow_count", "2", "2"),
        ("observations_present", "true", "true"),
        ("ratio", "0." + "0" * 300 + "1", "0.000000000000"),
    ],
)
def test_operational_display_preserves_units_without_investment_percentage(
    key: str, value: str, display: str
) -> None:
    column = EligibilityColumn.model_validate(eligibility_column_policy(key, "USD"))
    cell = EligibilityCell(
        canonical_value=value,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/report_facts/value",
    )
    assert display_eligibility_cell(column, cell) == display
    assert cell.canonical_value == value
