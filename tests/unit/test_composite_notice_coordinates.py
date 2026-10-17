"""Complete union and inherited policy refusals independent of producer projection code."""

from copy import deepcopy
from typing import Any

import pytest

from app.services.composite_workbook.notice_coordinates import (
    expected_pair_index,
    validate_side_tables,
)
from app.services.composite_workbook.notice_hashes import canonical


def source(rows: list[str]) -> dict[str, Any]:
    return {
        "tables": [
            {
                "table_id": "Summary",
                "title": "Exact title",
                "columns": [{"column_id": "text", "label": "Original label"}],
                "rows": [
                    {
                        "row_id": key,
                        "cells": {
                            "text": {
                                "canonical_value": None,
                                "availability": "UNAVAILABLE",
                                "reason_codes": ["lowerCase", "2_reason", "_third"],
                                "source_pointer": "/report_facts/value",
                            }
                        },
                    }
                    for key in rows
                ],
            }
        ]
    }


def example() -> dict[str, Any]:
    data: dict[str, Any] = {
        "generations": {
            "before": {"payload": source(["z", "a/~"])},
            "after": {"payload": source(["b", "a/~"])},
        }
    }
    data["tables"] = []
    for side, prefix in (("before", "Before_"), ("after", "After_")):
        table = deepcopy(data["generations"][side]["payload"]["tables"][0])
        table["table_id"] = prefix + "Summary"
        for row in table["rows"]:
            row["cells"]["text"]["source_pointer"] = (
                f"/generations/{side}/payload/report_facts/value"
            )
        data["tables"].append(table)
    data["pair_index"] = expected_pair_index(data)
    return data


def test_union_is_complete_ordered_and_binds_actual_indexes() -> None:
    data = example()
    validate_side_tables(data)
    pairs = data["pair_index"]
    assert [p["coordinate"]["row_id"] for p in pairs] == ["a/~", "b", "z"]
    assert [p["presence"] for p in pairs] == ["BOTH_PRESENT", "AFTER_ONLY", "BEFORE_ONLY"]
    assert pairs[0]["before_ref"]["row_index"] == pairs[0]["after_ref"]["row_index"] == 1
    assert pairs[1]["before_ref"] is None and pairs[2]["after_ref"] is None
    assert pairs[0]["row_id"] == '["Summary","a/~","text"]'
    assert data["tables"][0]["rows"][0]["cells"]["text"]["reason_codes"] == [
        "lowerCase",
        "2_reason",
        "_third",
    ]


@pytest.mark.parametrize("mutation", ["omission", "duplicate", "index", "pointer", "presence"])
def test_coordinate_mutations_refuse_even_when_side_tables_are_complete(mutation: str) -> None:
    data = example()
    if mutation == "omission":
        data["pair_index"].pop()
    elif mutation == "duplicate":
        data["pair_index"].append(deepcopy(data["pair_index"][0]))
    elif mutation == "index":
        data["pair_index"][0]["before_ref"]["row_index"] = 0
    elif mutation == "pointer":
        data["pair_index"][0]["after_ref"]["source_pointer"] = "/report_facts/foreign"
    else:
        data["pair_index"][1]["presence"] = "BOTH_PRESENT"
    with pytest.raises(ValueError, match="coordinate_union"):
        validate_side_tables(data)


@pytest.mark.parametrize("mutation", ["reason", "policy", "null", "row", "title"])
def test_copied_source_must_remain_exact(mutation: str) -> None:
    data = example()
    table = data["tables"][0]
    if mutation == "reason":
        table["rows"][0]["cells"]["text"]["reason_codes"][0] = "LOWERCASE"
    elif mutation == "policy":
        table["columns"][0]["label"] = "New label"
    elif mutation == "null":
        table["rows"][0]["cells"]["text"]["canonical_value"] = "0"
    elif mutation == "row":
        table["rows"].pop()
    else:
        table["title"] = "Different title"
    with pytest.raises(ValueError, match="side_projection"):
        validate_side_tables(data)


def test_serialized_row_identity_limit_counts_escaping() -> None:
    data = example()
    for generation in data["generations"].values():
        generation["payload"]["tables"][0]["rows"][0]["row_id"] = "\u2603" * 45
    with pytest.raises(ValueError, match="coordinate_row_id_limit"):
        expected_pair_index(data)
    for generation in data["generations"].values():
        generation["payload"]["tables"][0]["rows"][0]["row_id"] = "\u2603" * 39
    assert len(expected_pair_index(data)) == 2
    assert len(canonical(["Summary", "\u2603" * 39, "text"])) <= 256
