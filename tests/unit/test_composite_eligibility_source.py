"""Frozen Report unit emission is consumer proof, not Manage runtime qualification."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from eligibility_fixtures import producer_package

from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.services.composite_workbook.eligibility_source import validate_eligibility_source


def _digest(source: dict[str, Any], *, recursive: bool = False) -> str:
    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: strip(item) for key, item in value.items() if key != "content_hash"}
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    value = (
        strip(source)
        if recursive
        else {key: value for key, value in source.items() if key != "content_hash"}
    )
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
    )


def _rebind_proposal(data: dict[str, Any]) -> None:
    month = data["source_months"][0]
    proposal = month["proposal"]
    proposal["universe"]["content_hash"] = _digest(proposal["universe"], recursive=True)
    proposal["evaluation"]["universe_content_hash"] = proposal["universe"]["content_hash"]
    proposal["evaluation"]["input_content_hash"] = _digest(proposal["observations"])
    proposal["evaluation"]["content_hash"] = _digest(proposal["evaluation"])
    proposal["content_hash"] = _digest(proposal)
    response = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(proposal, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
    )
    month["response_digests"]["proposal"] = response
    data["selection"]["months"][0].update(
        proposal_content_hash=proposal["content_hash"], proposal_response_digest=response
    )


def test_parent_universe_cut_stays_distinct_from_observation_cut() -> None:
    data = producer_package()["report_data"]
    data["source_months"][0]["proposal"]["universe"]["source_cut_id"] = "prior-universe-cut"
    _rebind_proposal(data)
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    validate_eligibility_source(typed, data)


def test_coherently_rehashed_proposal_cannot_relabel_observation_cut() -> None:
    data = producer_package()["report_data"]
    proposal = data["source_months"][0]["proposal"]
    proposal["observations"]["source_cut_id"] = "wrong-observation-cut"
    proposal["evaluation"]["input_content_hash"] = _digest(proposal["observations"])
    _rebind_proposal(data)
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="source_scope_conflict"):
        validate_eligibility_source(typed, data)


@pytest.mark.parametrize(
    "change", ["tenant", "source_count", "variant", "response_set", "response_digest", "currency"]
)
def test_refuses_conflicting_complete_source_transport(change: str) -> None:
    data = producer_package()["report_data"]
    if change == "tenant":
        data["tenant_id"] = "foreign-tenant"
    elif change == "source_count":
        data["source_months"].append(copy.deepcopy(data["source_months"][0]))
    elif change == "response_set":
        data["source_months"][0]["response_digests"] = {}
    elif change == "response_digest":
        data["source_months"][0]["response_digests"]["proposal"] = "sha256:" + "f" * 64
    elif change == "currency":
        data["source_months"][0]["proposal"]["observations"]["portfolios"][0]["currency"] = "SGD"
        _rebind_proposal(data)
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    if change == "variant":
        data["source_months"][0]["evidence_kind"] = "PUBLISHED"
    with pytest.raises(ValueError, match="composite_eligibility_.*conflict"):
        validate_eligibility_source(typed, data)


def test_approval_hash_pin_cannot_be_borrowed_from_another_publication() -> None:
    data = producer_package("published")["report_data"]
    data["selection"]["months"][0]["approval_content_hash"] = "sha256:" + "f" * 64
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="approval_pin_conflict"):
        validate_eligibility_source(typed, data)


@pytest.mark.parametrize(
    "change,code",
    [("binding", "receipt_binding_conflict"), ("definition", "definition_version_conflict")],
)
def test_rehashed_receipt_cannot_change_bound_product_or_definition_version(
    change: str, code: str
) -> None:
    data = producer_package("published")["report_data"]
    month = data["source_months"][0]
    receipt = month["receipt"]
    if change == "binding":
        receipt["membership_binding"]["digest"] = "sha256:" + "f" * 64
    else:
        receipt["definition"]["product_version"] = "v3"
    receipt["content_hash"] = _digest(receipt)
    response = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
    )
    month["response_digests"]["receipt"] = response
    data["selection"]["months"][0].update(
        receipt_content_hash=receipt["content_hash"], receipt_response_digest=response
    )
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match=code):
        validate_eligibility_source(typed, data)


@pytest.mark.parametrize(
    ("kind", "digest"),
    [
        ("evaluated_only", "9d55e16a07146fa9f43b46897c849230cb3f4dc9f62b00331015c81ac7b71e31"),
        ("published", "3e84458fca2fedfeabdb4d20caffa8c65a1c7ca33b33096352ee4c260a14b613"),
    ],
)
def test_supplier_unit_package_bytes_and_complete_source_bindings(kind: str, digest: str) -> None:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "composite-eligibility-v4"
    assert hashlib.sha256((path / f"{kind}-render-package.json").read_bytes()).hexdigest() == digest
    data = producer_package(kind)["report_data"]
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    validate_eligibility_source(typed, data)
    assert typed.model_dump(mode="json") == data


@pytest.mark.parametrize("kind", ["evaluated_only", "published"])
@pytest.mark.parametrize("change", ["metadata", "decimal_spelling", "nested_hash"])
def test_whole_source_pins_refuse_tampering(kind: str, change: str) -> None:
    data = producer_package(kind)["report_data"]
    source = data["source_months"][0]
    proposal = (
        source["proposal"]
        if kind == "evaluated_only"
        else source["receipt"]["approval"]["proposal"]
    )
    if change == "metadata":
        proposal["new_metadata"] = "not captured"
    elif change == "decimal_spelling":
        proposal["evaluation"]["portfolios"][0]["assessments"][0]["ratio"] = "0.10"
    else:
        proposal["evaluation"]["resolved_policy"]["content_hash"] = "sha256:" + "f" * 64
    typed = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="composite_eligibility_.*conflict"):
        validate_eligibility_source(typed, data)
