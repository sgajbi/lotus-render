"""Bind v4 corrections to their exact historical v3 root; no current trust grant."""

from typing import Any

from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.services.composite_workbook.amendment_lineage import (
    _validate_link,
    _validate_parent_publication_binding,
    _validate_receipt_scope,
)
from app.services.composite_workbook.eligibility_hashes import whole_response_digest
from app.services.composite_workbook.eligibility_source import (
    _require_content_hash,
    _validate_proposal,
    require_equal_fields,
)
from app.services.composite_workbook.historical_proof import validate_operation, validate_policy


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("composite_amendment_lineage_conflict")


def validate_historical_lineage(
    month: dict[str, Any],
    pins: dict[str, Any],
    proposal: dict[str, Any],
    selection: EligibilitySelection,
) -> None:
    receipts = month["lineage_receipts"]
    _require(len(receipts) == len(pins["lineage_receipts"]))
    original = receipts[-1]
    _require(original["product_version"] == "v3")
    if month["evidence_kind"] == "PUBLISHED":
        _require(month["receipt"]["definition"] == original["definition"])
    revisions = [proposal["evaluation_revision"]]
    for receipt, pin in zip(receipts, pins["lineage_receipts"], strict=True):
        _require(receipt["definition"] == original["definition"])
        _validate_retained_receipt(receipt, pin, pins["month"], selection)
        revisions.append(receipt["approval"]["proposal"]["evaluation_revision"])
    _require(len(revisions) == len(set(revisions)))
    current = proposal
    for receipt in receipts:
        _require(current["product_version"] == "v4")
        _validate_link(current, receipt, original)
        current = receipt["approval"]["proposal"]
    _require(current["product_version"] == "v3")
    if month["evidence_kind"] == "PUBLISHED":
        _validate_parent_publication_binding(month, proposal, selection)
        _require(
            month["publication"]["sequence"]
            > proposal["amendment"]["expected_current_publication_sequence"]
        )


def _validate_retained_receipt(
    receipt: dict[str, Any],
    pin: dict[str, Any],
    month: str,
    selection: EligibilitySelection,
) -> None:
    approval, proposal = receipt["approval"], receipt["approval"]["proposal"]
    require_equal_fields(
        receipt,
        {"product_version": pin["product_version"], "content_hash": pin["receipt_content_hash"]},
        "composite_amendment_receipt_pin_conflict",
    )
    _require(whole_response_digest(receipt) == pin["receipt_response_digest"])
    _require(approval["content_hash"] == pin["approval_content_hash"])
    _require(proposal["evaluation_revision"] == pin["evaluation_revision"])
    _require(
        approval["product_version"] == proposal["product_version"] == receipt["product_version"]
    )
    # Shared validation receives an explicit EVALUATED_ONLY pin for this retained
    # proposal, not a fabricated published month or a rewritten v1 source product.
    from app.contracts.composite_eligibility_selection import EvaluatedEligibilityPin

    typed_pin = EvaluatedEligibilityPin.model_validate(
        {
            "evidence_kind": "EVALUATED_ONLY",
            "month": month,
            "evaluation_revision": pin["evaluation_revision"],
            "proposal_content_hash": proposal["content_hash"],
            "proposal_response_digest": whole_response_digest(proposal),
            "parent_membership_revision": proposal["parent_membership_revision"],
            "parent_membership_content_hash": proposal["parent_membership_content_hash"],
            "source_cut_id": proposal["observations"]["source_cut_id"],
        }
    )
    _validate_proposal(proposal, typed_pin, selection)
    validate_policy(proposal, selection.reporting_currency)
    _require(approval["approved_by"] != proposal["proposed_by"])
    validate_operation(approval, proposal, approval=True)
    for source in (approval, receipt):
        _require_content_hash(source)
    _validate_receipt_scope(receipt, selection)
    if receipt["product_version"] == "v4":
        _require(receipt["lineage"] == proposal["amendment"])
        _require(
            receipt["publication_sequence"]
            > proposal["amendment"]["expected_current_publication_sequence"]
        )
