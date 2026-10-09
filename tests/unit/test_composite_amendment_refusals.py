"""Rehashed source substitutions cannot borrow a valid amendment envelope."""

import hashlib
import json
from typing import Any

import pytest
from amendment_fixtures import amendment_data

from app.services.composite_workbook.source_cells import validate_dataset


def _digest(value: Any, *, content: bool = False) -> str:
    if content:
        value = {k: v for k, v in value.items() if k != "content_hash"}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _rebind_current(data: dict[str, Any]) -> None:
    month, pin = data["source_months"][0], data["selection"]["months"][0]
    published = month["evidence_kind"] == "PUBLISHED"
    proposal = month["receipt"]["approval"]["proposal"] if published else month["proposal"]
    proposal["content_hash"] = _digest(proposal, content=True)
    pin["proposal_content_hash"] = proposal["content_hash"]
    if published:
        receipt = month["receipt"]
        receipt["approval"]["content_hash"] = _digest(receipt["approval"], content=True)
        receipt["content_hash"] = _digest(receipt, content=True)
        pin.update(
            approval_content_hash=receipt["approval"]["content_hash"],
            receipt_content_hash=receipt["content_hash"],
        )
    for name in month["response_digests"]:
        digest = _digest(month[name])
        month["response_digests"][name] = digest
        key = "parent_response_digest" if name == "parent_membership" else name + "_response_digest"
        pin[key] = digest


@pytest.mark.parametrize("kind", ["evaluated", "published"])
@pytest.mark.parametrize(
    "field",
    [
        "predecessor_approval_binding",
        "predecessor_receipt_binding",
        "original_approval_binding",
        "expected_authority_binding",
        "projection_parent_membership_binding",
        "affected_from",
        "affected_to",
        "expected_current_publication_sequence",
    ],
)
def test_rehashed_amendment_cross_bindings_refuse(kind: str, field: str) -> None:
    data = amendment_data(kind=kind)
    month = data["source_months"][0]
    proposal = (
        month["proposal"] if "proposal" in month else month["receipt"]["approval"]["proposal"]
    )
    amendment = proposal["amendment"]
    if field.endswith("binding"):
        amendment[field]["digest"] = "sha256:" + "f" * 64
    elif field == "expected_current_publication_sequence":
        amendment[field] = 1
    else:
        amendment[field] = "2026-09-02"
    if kind == "published":
        month["receipt"]["lineage"] = amendment.copy()
    _rebind_current(data)
    with pytest.raises(ValueError, match="composite_amendment_.*conflict"):
        validate_dataset(data)


@pytest.mark.parametrize("change", ["missing", "reordered", "extra", "digest", "definition", "pin"])
def test_lineage_receipts_are_complete_ordered_and_pinned(change: str) -> None:
    data = amendment_data()
    month, pin = data["source_months"][0], data["selection"]["months"][0]
    if change == "missing":
        month["lineage_receipts"].pop()
    elif change == "reordered":
        month["lineage_receipts"].reverse()
        pin["lineage_receipts"].reverse()
    elif change == "extra":
        month["lineage_receipts"].append(month["lineage_receipts"][-1])
        pin["lineage_receipts"].append(pin["lineage_receipts"][-1])
    elif change == "digest":
        month["lineage_receipts"][0]["correlation_id"] = "substituted"
    elif change == "definition":
        month["lineage_receipts"][0]["definition"]["reporting_currency"] = "SGD"
    else:
        pin["lineage_receipts"][0]["approval_content_hash"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="composite_amendment_.*conflict"):
        validate_dataset(data)


@pytest.mark.parametrize(
    "field",
    [
        "tenant_id",
        "sequence",
        "membership_revision",
        "membership_content_hash",
        "policy_version",
        "source_cut_id",
        "supersedes_membership_revision",
        "affected_from",
        "affected_to",
        "decided_at",
    ],
)
def test_rehashed_parent_publication_cannot_borrow_current_publication(field: str) -> None:
    data = amendment_data()
    parent = data["source_months"][0]["parent_publication"]
    parent[field] = 99 if field == "sequence" else "foreign"
    if field == "membership_content_hash":
        parent[field] = "sha256:" + "f" * 64
    _rebind_current(data)
    with pytest.raises(ValueError, match="parent_publication_conflict"):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    ["table", "row", "pointer", "value", "availability", "policy", "disclosure", "financial"],
)
def test_exact_table_population_and_non_financial_boundary(change: str) -> None:
    data = amendment_data()
    table = data["tables"][-1]
    if change == "table":
        table["table_id"] = "FinancialReturns"
    elif change == "row":
        table["rows"].pop()
    elif change == "pointer":
        table["rows"][0]["cells"]["value"]["source_pointer"] = (
            "/source_months/0/receipt/product_version"
        )
    elif change == "value":
        table["rows"][0]["cells"]["value"]["canonical_value"] = "invented"
    elif change == "availability":
        table["rows"][0]["cells"]["value"]["availability"] = "UNAVAILABLE"
    elif change == "policy":
        table["columns"][1]["unit"] = "DECIMAL_RATIO"
    elif change == "disclosure":
        data["report_facts"]["disclosures"][-1]["text"] = "Official financial correction"
    else:
        data["report_facts"]["twr"] = "0.12"
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize("axis", ["contract", "qualification", "publication", "selector", "source"])
def test_no_implicit_financial_or_attested_promotion(axis: str) -> None:
    data = amendment_data()
    if axis == "contract":
        data["contract_version"] = "composite_review.v5"
    elif axis == "qualification":
        data["qualification"] = "EXPLICIT_RETAINED_CALCULATED_REPLAY"
    elif axis == "publication":
        data["publication_state"] = "ATTESTED"
    elif axis == "selector":
        data["selection"].pop("selection_version")
    else:
        data["source_months"][0]["receipt"]["product_version"] = "v1"
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize("change", ["tenant", "source_count", "variant", "responses"])
def test_source_months_match_the_selected_scope_and_variant(change: str) -> None:
    data = amendment_data()
    if change == "tenant":
        data["tenant_id"] = "foreign"
    elif change == "source_count":
        data["source_months"].append(data["source_months"][0])
    elif change == "variant":
        data["source_months"][0] = amendment_data(kind="evaluated")["source_months"][0]
    else:
        data["source_months"][0]["response_digests"].pop("parent_publication")
    with pytest.raises(ValueError, match="composite_amendment_.*conflict"):
        validate_dataset(data)


def test_source_correction_cannot_change_approved_policy_custody_after_rehash() -> None:
    data = amendment_data(kind="evaluated")
    data["source_months"][0]["proposal"]["policy_approval"]["approved_by"] = "foreign-checker"
    _rebind_current(data)
    with pytest.raises(ValueError, match="composite_amendment_lineage_conflict"):
        validate_dataset(data)


def test_published_receipt_lineage_must_equal_the_approved_amendment_after_rehash() -> None:
    data = amendment_data()
    data["source_months"][0]["receipt"]["lineage"]["reason"] = "unapproved reason"
    _rebind_current(data)
    with pytest.raises(ValueError, match="composite_amendment_lineage_conflict"):
        validate_dataset(data)
