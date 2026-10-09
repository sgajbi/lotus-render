"""The new layout admits only frozen v4 tables under unchanged writer bounds."""

import copy
import json
from pathlib import Path

import pytest

from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.eligibility_policy import ELIGIBILITY_TABLE_COLUMNS
from app.services.composite_workbook.rendering import _validate_layout


def layout() -> dict[str, object]:
    value: dict[str, object] = json.loads(
        Path("templates/xlsx/composite-review/v4/layout.json").read_bytes()
    )
    return value


def test_v4_layout_admits_exact_frozen_eight_tables_with_no_financial_period_table() -> None:
    _validate_layout(layout(), set(ELIGIBILITY_TABLE_COLUMNS), version="v4")


@pytest.mark.parametrize("name", list(ELIGIBILITY_TABLE_COLUMNS))
def test_v4_layout_refuses_each_missing_table(name: str) -> None:
    with pytest.raises(ValueError, match="table_set_invalid"):
        _validate_layout(layout(), set(ELIGIBILITY_TABLE_COLUMNS) - {name}, version="v4")


@pytest.mark.parametrize("name", ["MonthlyReturns", "LinkedContribution", "CanonicalData"])
def test_v4_layout_refuses_additional_or_duplicate_logical_evidence_tables(name: str) -> None:
    with pytest.raises(ValueError, match="table_set_invalid"):
        _validate_layout(layout(), set(ELIGIBILITY_TABLE_COLUMNS) | {name}, version="v4")


@pytest.mark.parametrize(
    "field,value",
    [
        ("optional_tables", ["MonthlyReturns"]),
        ("period_tables", ["MonthlyReturns"]),
        ("required_tables", list(reversed(ELIGIBILITY_TABLE_COLUMNS))),
        ("max_total_cells", 210001),
        ("max_rows_per_sheet", 1001),
        ("identity_storage", "new-encoding"),
    ],
)
def test_v4_layout_cannot_expand_policy_to_admit_unsupported_output(
    field: str, value: object
) -> None:
    changed = copy.deepcopy(layout())
    changed[field] = value
    with pytest.raises(TemplateRegistryError, match="layout_policy|layout_limit"):
        _validate_layout(changed, set(ELIGIBILITY_TABLE_COLUMNS), version="v4")
