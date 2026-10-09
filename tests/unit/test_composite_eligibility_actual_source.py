"""Actual controlled Manage source, offline Report datasets; no fabricated custody envelope."""

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.services.composite_workbook.source_cells import validate_dataset


def _dataset(version: str) -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "composite-eligibility-v4"
        / "actual-published-datasets.json"
    )
    receipt = json.loads(path.read_bytes())
    item = next(
        item for item in receipt["datasets"] if item["definition_product_version"] == version
    )
    assert item["encoding"] == "gzip_base64"
    raw = gzip.decompress(base64.b64decode(item["payload"]))
    expected = {
        "v1": (262387, "2437ec8d8d78e5fca171450ed1d0c1473288c9f86f971aa2d9131c56c3e8870e"),
        "v2": (279403, "f0d0756b6c41d4fdd87fd7e41fef3bd6d37d451afa3437f46b7b40d505808076"),
    }[version]
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == expected
    data: dict[str, Any] = json.loads(raw)
    return data


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_actual_three_month_source_retains_complete_assessments_and_revision_history(
    version: str,
) -> None:
    data = _dataset(version)
    parsed = validate_dataset(data)
    assert isinstance(parsed, CompositeEligibilityContent)
    assert parsed.model_dump(mode="json") == data
    proposals = [month["receipt"]["approval"]["proposal"] for month in data["source_months"]]
    assert [p["evaluation"]["portfolios"][0]["status"] for p in proposals] == [
        "EXCLUDED",
        "EXCLUDED",
        "INCLUDED",
    ]
    assert [
        [a["outcome"] for a in p["evaluation"]["portfolios"][0]["assessments"]] for p in proposals
    ] == [
        ["PASS", "FAIL", "FAIL"],
        ["PASS", "PASS", "FAIL"],
        ["PASS", "PASS", "PASS"],
    ]
    assert all(
        p["observations"]["source_cut_id"] != p["universe"]["source_cut_id"] for p in proposals
    )
    reasons = next(t for t in data["tables"] if t["table_id"] == "EligibilityReasons")
    assert reasons["rows"][-1]["row_id"] == "m2:not_applicable"
    assert reasons["rows"][-1]["cells"]["reason_code"]["availability"] == "NOT_APPLICABLE"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_actual_source_cannot_drop_genuine_revision_intervals(version: str) -> None:
    data = _dataset(version)
    history = next(t for t in data["tables"] if t["table_id"] == "MembershipHistory")
    history["rows"].pop()
    with pytest.raises(ValueError, match="row_population_conflict"):
        validate_dataset(data)


def test_rehashed_actual_publication_cannot_substitute_the_observation_cut() -> None:
    data = _dataset("v2")
    month = data["source_months"][0]
    month["publication"]["source_cut_id"] = month["receipt"]["approval"]["proposal"][
        "observations"
    ]["source_cut_id"]
    response = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                month["publication"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
        ).hexdigest()
    )
    month["response_digests"]["publication"] = response
    data["selection"]["months"][0]["publication_response_digest"] = response
    with pytest.raises(ValueError, match="publication_source_cut_conflict"):
        validate_dataset(data)
