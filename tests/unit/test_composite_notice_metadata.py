"""Derived metadata is checked independently rather than trusted after hashing."""

from copy import deepcopy
from typing import Any

import pytest

from app.contracts.composite_notice import OBLIGATIONS
from app.services.composite_workbook.notice_hashes import canonical, digest, require
from app.services.composite_workbook.notice_metadata import SCOPE, metadata_facts, validate_metadata


def test_canonical_hash_preserves_raw_strings_and_array_order() -> None:
    assert canonical({"z": "0.0100", "a": ["\u2603", None]}) == (
        '{"a":["\\u2603",null],"z":"0.0100"}'
    )
    assert digest({"a": 1}) == (
        "sha256:015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
    )
    assert digest(["a", "b"]) != digest(["b", "a"])
    assert digest({"domain": "pair.v1"}) != digest({"domain": "manifest.v1"})
    with pytest.raises(ValueError):
        canonical(float("nan"))
    with pytest.raises(ValueError, match="composite_notice_invalid"):
        require(False, "invalid")
    require(True, "valid")


def metadata_input() -> dict[str, Any]:
    data: dict[str, Any] = {
        "generations": {},
        "archive_path": {"edges": []},
        "pair_index": [],
        "obligations": {},
    }
    for side in ("before", "after"):
        data["generations"][side] = {"selection": {}, "payload": {"selection": {}}}
    for key, pointer in SCOPE:
        current = data
        parts = pointer.split("/")[1:]
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = key
    for key in OBLIGATIONS:
        data["obligations"][key] = {
            "status": "UNAVAILABLE",
            "reason_code": "MISSING",
            "evidence_refs": [],
        }
    return data


def test_facts_mismatch_refuses_without_relying_on_manifest_hash() -> None:
    data = metadata_input()
    data["notice_facts"] = metadata_facts(data)
    data["notice_facts"]["scope"][0]["value"] = "wrong"
    data["manifest_digest"] = digest(deepcopy(data))
    with pytest.raises(ValueError, match="derived_facts"):
        validate_metadata(data)
