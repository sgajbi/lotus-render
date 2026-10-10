"""Unchanged public native products and independently isolated recorded chronology."""

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, NoReturn

import pytest
from historical_fixtures import historical_package

from app.contracts.render_package import RenderPackage
from app.services.composite_workbook import historical_proof
from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)
from app.services.composite_workbook.historical_custody import validate_historical_custody
from app.services.composite_workbook.historical_lineage import validate_historical_lineage
from app.services.composite_workbook.historical_source import historical_common_selection
from app.services.composite_workbook.source_cells import validate_dataset

ROOT = Path("tests/fixtures/composite-historical-v7/native-r12")
MANIFEST = json.loads((ROOT / "manifest.json").read_bytes())["files"]


def retained(name: str) -> dict[str, Any]:
    raw = gzip.decompress((ROOT / (name + ".gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == MANIFEST[name]["sha256"]
    assert len(raw) == MANIFEST[name]["bytes"]
    result: dict[str, Any] = json.loads(raw)
    return result


@pytest.mark.parametrize("name", [name for name in MANIFEST if name != "render-request.json"])
def test_all_nine_unchanged_native_datasets_and_sorted_replay(name: str) -> None:
    data = retained(name)["report_data"]
    assert validate_dataset(data).model_dump(mode="json") == data
    assert (
        validate_dataset(json.loads(json.dumps(data, sort_keys=True))).model_dump(mode="json")
        == data
    )


def test_unchanged_native_request_and_custody() -> None:
    wire = retained("render-request.json")
    package = RenderPackage.model_validate(wire)
    validate_historical_custody(package)
    assert validate_dataset(package.report_data).model_dump(mode="json") == wire["report_data"]
    policy = wire["report_data"]["source_months"][0]["receipt"]["approval"]["proposal"]
    proof = policy["policy_approval"]["proposal"]["verification"]
    assert historical_proof.instant(proof["request"]["requested_at"]) < historical_proof.instant(
        proof["admitted_at"]
    )


def window(
    checked: float, requested: float, admitted: float, expiry: float
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Unsigned structural clones never stand in for producer crypto or authority."""
    proposal = historical_package("v1-root-evaluated-only")["report_data"]["source_months"][0][
        "proposal"
    ]
    proof = proposal["operation_verification"]
    base = datetime(2001, 1, 1, tzinfo=timezone.utc)
    for key, offset in (("checked_at", checked), ("admitted_at", admitted), ("expires_at", expiry)):
        proof[key] = (base + timedelta(seconds=offset)).isoformat()
    proof["request"]["requested_at"] = (base + timedelta(seconds=requested)).isoformat()
    proof["content_hash"] = source_content_digest(proof)
    return proof, proposal["policy_approval"]["proposal"]


def admit(proof: dict[str, Any], policy: dict[str, Any], *, at: str | None = None) -> None:
    request = proof["request"]
    historical_proof.validate_proof(
        proof,
        policy,
        operation=request["operation"],
        actor=request["actor_id"],
        revision=request["revision"],
        at=request["requested_at"] if at is None else at,
        intent=request["intent_digest"],
    )


class RecordedClock(datetime):
    @classmethod
    def now(cls, _tz: tzinfo | None = None) -> NoReturn:
        raise AssertionError("Retained proof validation must not ask the current clock")


@pytest.mark.parametrize(
    "clocks", [(0, 0, 0, 1), (0, 0, 0.000001, 1), (0, 1, 299, 300), (0, 0, 299.999999, 300)]
)
def test_valid_recorded_window_after_expiry(
    clocks: tuple[float, float, float, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(historical_proof, "datetime", RecordedClock)
    admit(*window(*clocks))


@pytest.mark.parametrize(
    "clocks",
    [
        (1, 0, 2, 3),
        (0, 2, 1, 3),
        (0, 2, 2, 2),
        (0, 1, 3, 2),
        (0, 0, 0, 0),
        (1, 1, 1, 0),
        (0, 0, 1, 300.000001),
    ],
)
def test_invalid_recorded_window_refuses(clocks: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="composite_historical_proof_binding_conflict"):
        admit(*window(*clocks))


@pytest.mark.parametrize("field", ["checked_at", "requested_at", "admitted_at", "expires_at"])
def test_naive_recorded_clock_refuses(field: str) -> None:
    proof, policy = window(0, 1, 2, 3)
    target = proof["request"] if field == "requested_at" else proof
    target[field] = target[field].removesuffix("+00:00")
    proof["content_hash"] = source_content_digest(proof)
    with pytest.raises(ValueError, match="composite_historical_proof_binding_conflict"):
        admit(proof, policy)


def test_operation_time_remains_exact_request_time() -> None:
    proof, policy = window(0, 1, 2, 3)
    with pytest.raises(ValueError, match="composite_historical_proof_binding_conflict"):
        admit(proof, policy, at=proof["admitted_at"])


@pytest.mark.parametrize(
    "change",
    [
        "equal",
        "older",
        "published_equal",
        "published_older",
        "parent_sequence",
        "parent_identity",
        "receipt_hash",
        "missing",
        "reordered",
    ],
)
def test_native_gapped_publication_preserves_parent_and_lineage_refusals(change: str) -> None:
    data = retained("v2-correction-3-evaluated-only.json")["report_data"]
    month, pin = data["source_months"][0], data["selection"]["months"][0]
    proposal = month["proposal"]
    receipt = month["lineage_receipts"][0]
    assert (
        receipt["publication_sequence"]
        > receipt["lineage"]["expected_current_publication_sequence"] + 1
    )
    if change in {"equal", "older"}:
        receipt["publication_sequence"] = receipt["lineage"][
            "expected_current_publication_sequence"
        ] - (change == "older")
        receipt["content_hash"] = source_content_digest(receipt)
        pin["lineage_receipts"][0]["receipt_content_hash"] = receipt["content_hash"]
        pin["lineage_receipts"][0]["receipt_response_digest"] = whole_response_digest(receipt)
    elif change == "receipt_hash":
        receipt["content_hash"] = "sha256:" + "0" * 64
    elif change == "missing":
        month["lineage_receipts"].pop()
    elif change == "reordered":
        month["lineage_receipts"].reverse()
    else:
        # Published corrections independently bind the full exact parent publication.
        data = retained("v2-correction-2-published.json")["report_data"]
        month, pin = data["source_months"][0], data["selection"]["months"][0]
        proposal = month["receipt"]["approval"]["proposal"]
        if change.startswith("published_"):
            month["publication"]["sequence"] = proposal["amendment"][
                "expected_current_publication_sequence"
            ] - (change == "published_older")
        else:
            month["parent_publication"][
                "sequence" if change == "parent_sequence" else "membership_revision"
            ] = 999 if change == "parent_sequence" else "foreign"
    with pytest.raises(ValueError):
        validate_historical_lineage(
            month, pin, proposal, historical_common_selection(data["selection"])
        )
