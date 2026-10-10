"""Pointer ordering and global ordinals, without fabricating admitted source history."""

import json

import pytest
from historical_fixtures import historical_package

from app.services.composite_workbook.historical_rows import historical_rows, scalar_pointers


def test_escaped_keys_nulls_and_original_array_order() -> None:
    value = {"z": [None, {"b/c": 2, "a~d": 1}], "a": "exact"}
    assert scalar_pointers(value, "/proof") == [
        "/proof/a",
        "/proof/z/0",
        "/proof/z/1/a~0d",
        "/proof/z/1/b~1c",
    ]
    assert scalar_pointers(
        json.loads(json.dumps(value, sort_keys=True)), "/proof"
    ) == scalar_pointers(value, "/proof")


def test_global_ordinals_for_multiple_row_recipe_inputs() -> None:
    # This is an isolated row-recipe test, not source admission or a producer emission.
    raw = historical_package()["report_data"]
    raw["source_months"].append(raw["source_months"][0])
    rows = historical_rows(raw)
    for table, prefix in (("Amendments", "a"), ("PolicyAdmission", "p")):
        values = rows[table]
        half = len(values) // 2
        assert values[half][0] == f"m1:{prefix}{half}"
        assert values[-1][0] == f"m1:{prefix}{len(values) - 1}"
        assert values[half][1]["month"] == "/selection/months/1/month"
    assert historical_rows(json.loads(json.dumps(raw, sort_keys=True))) == rows


@pytest.mark.parametrize("outcome", ["evaluated", "published"])
def test_actual_two_month_emission_keeps_global_ordinals_and_distinct_originals(
    outcome: str,
) -> None:
    raw = historical_package(f"two-month/two-month-published-{outcome}")["report_data"]
    assert [pin["month"] for pin in raw["selection"]["months"]] == ["2026-09", "2026-10"]
    first, second = raw["source_months"]
    first_proposal = first["receipt"]["approval"]["proposal"]
    second_proposal = (
        second["proposal"] if outcome == "evaluated" else second["receipt"]["approval"]["proposal"]
    )
    originals = [
        proposal["policy_approval"]["proposal"]["verification"]["mapping"]["reference"][
            "raw_digest"
        ]
        for proposal in (first_proposal, second_proposal)
    ]
    assert originals[0] != originals[1]
    for table, prefix in (("Amendments", "a"), ("PolicyAdmission", "p")):
        values = next(item for item in raw["tables"] if item["table_id"] == table)["rows"]
        ordinal = next(index for index, row in enumerate(values) if row["row_id"].startswith("m1:"))
        assert values[ordinal]["row_id"] == f"m1:{prefix}{ordinal}"
        assert values[ordinal]["cells"]["month"]["source_pointer"] == "/selection/months/1/month"
        assert values[ordinal]["cells"]["month"]["canonical_value"] == "2026-10"
