"""Bind ordered original/predecessor custody independently of transport hashes."""

import json
from calendar import monthrange
from typing import Any

from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.contracts.composite_eligibility_sources import EligibilityPublication
from app.services.composite_workbook.eligibility_hashes import whole_response_digest
from app.services.composite_workbook.eligibility_source import (
    _require_content_hash,
    _validate_proposal,
    require_equal_fields,
)


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("composite_amendment_lineage_conflict")


def _binding(source: dict[str, Any], revision: str) -> dict[str, Any]:
    return {
        "product_name": source["product_name"],
        "product_version": source["product_version"],
        "revision": revision,
        "digest": source["content_hash"],
    }


def validate_amendment_lineage(
    month: dict[str, Any],
    pins: dict[str, Any],
    proposal: dict[str, Any],
    selection: EligibilitySelection,
) -> None:
    receipts = month["lineage_receipts"]
    _require(len(receipts) == len(pins["lineage_receipts"]))
    original = receipts[-1]
    _require(original["product_version"] == "v1")
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
        _require(current["product_version"] == "v2")
        _validate_link(current, receipt, original)
        current = receipt["approval"]["proposal"]
    _require(current["product_version"] == "v1")
    if month["evidence_kind"] == "PUBLISHED":
        _validate_parent_publication(month, proposal, selection)


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
    for source in (approval, receipt):
        _require_content_hash(source)
    _validate_receipt_scope(receipt, selection)
    if receipt["product_version"] == "v2":
        _require(receipt["lineage"] == proposal["amendment"])
        _require(
            receipt["publication_sequence"]
            == proposal["amendment"]["expected_current_publication_sequence"] + 1
        )


def _validate_receipt_scope(receipt: dict[str, Any], selection: EligibilitySelection) -> None:
    definition = receipt["definition"]
    require_equal_fields(
        definition,
        {
            "product_name": "CompositeDefinition",
            "tenant_id": selection.tenant_id,
            "composite_id": selection.composite_id,
            "definition_version": selection.definition_version,
            "reporting_currency": selection.reporting_currency,
        },
        "composite_amendment_definition_conflict",
    )
    _require(definition["product_version"] in {"v1", "v2"})
    _require_content_hash(definition, recursive=definition["product_version"] == "v1")
    approval, proposal = receipt["approval"], receipt["approval"]["proposal"]
    for name, product, revision, digest in (
        (
            "membership_binding",
            "CompositeMembership",
            proposal["target_membership_revision"],
            approval["membership_content_hash"],
        ),
        (
            "universe_binding",
            "CompositeUniverseAttestation",
            proposal["evaluation_revision"],
            approval["published_universe_content_hash"],
        ),
    ):
        _require(
            receipt[name]
            == {
                "product_name": product,
                "product_version": "v1",
                "revision": revision,
                "digest": digest,
            }
        )
    _require(receipt["source_cut_id"] == proposal["universe"]["source_cut_id"])


def _validate_link(
    current: dict[str, Any], predecessor: dict[str, Any], original: dict[str, Any]
) -> None:
    amendment = current["amendment"]
    prior = predecessor["approval"]["proposal"]
    revision = prior["evaluation_revision"]
    authority = _binding(predecessor["approval"], revision)
    _require(amendment["predecessor_approval_binding"] == authority)
    _require(amendment["expected_authority_binding"] == authority)
    _require(amendment["predecessor_receipt_binding"] == _binding(predecessor, revision))
    _require(
        amendment["original_approval_binding"]
        == _binding(original["approval"], original["approval"]["proposal"]["evaluation_revision"])
    )
    _require(
        amendment["projection_parent_membership_binding"]
        == {
            "product_name": "CompositeMembership",
            "product_version": "v1",
            "revision": current["parent_membership_revision"],
            "digest": current["parent_membership_content_hash"],
        }
    )
    _require(current["policy_approval"] == prior["policy_approval"])
    _require(
        current["observations"]["expected_portfolio_ids"]
        == prior["observations"]["expected_portfolio_ids"]
    )
    year, month = map(int, current["evaluation"]["month"].split("-"))
    _require(amendment["affected_from"] == f"{year:04d}-{month:02d}-01")
    _require(amendment["affected_to"] == f"{year:04d}-{month:02d}-{monthrange(year, month)[1]}")
    _require(
        amendment["expected_current_publication_sequence"] >= predecessor["publication_sequence"]
    )


def _validate_parent_publication_binding(
    month: dict[str, Any], proposal: dict[str, Any], selection: EligibilitySelection
) -> None:
    amendment = proposal["amendment"]
    parent = month["parent_membership"]
    EligibilityPublication.model_validate_json(json.dumps(month["parent_publication"]))
    require_equal_fields(
        month["parent_publication"],
        {
            "product_name": "CompositeMembershipPublication",
            "product_version": "v1",
            "tenant_id": selection.tenant_id,
            "composite_id": selection.composite_id,
            "definition_version": selection.definition_version,
            "sequence": amendment["expected_current_publication_sequence"],
            "membership_revision": parent["membership_revision"],
            "membership_content_hash": parent["content_hash"],
            **{
                key: parent[key]
                for key in (
                    "policy_version",
                    "source_cut_id",
                    "supersedes_membership_revision",
                    "affected_from",
                    "affected_to",
                    "decided_at",
                )
            },
            "decision_count": len(parent["decisions"]),
        },
        "composite_amendment_parent_publication_conflict",
    )
    _require(month["receipt"]["lineage"] == amendment)


def _validate_parent_publication(
    month: dict[str, Any], proposal: dict[str, Any], selection: EligibilitySelection
) -> None:
    _validate_parent_publication_binding(month, proposal, selection)
    _require(
        month["publication"]["sequence"]
        == proposal["amendment"]["expected_current_publication_sequence"] + 1
    )
