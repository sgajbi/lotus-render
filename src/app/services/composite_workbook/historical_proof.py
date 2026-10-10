"""Bind recorded producer proof; never confer current trust or verify bank signatures."""

import base64
from datetime import datetime
from hashlib import sha256
from typing import Any

from app.services.composite_workbook.eligibility_hashes import source_content_digest
from app.services.composite_workbook.eligibility_source import _require_content_hash


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("composite_historical_proof_binding_conflict")


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None)
    return result


def validate_proof(
    proof: dict[str, Any],
    policy: dict[str, Any],
    *,
    operation: str,
    actor: str,
    revision: str,
    at: str,
    intent: str,
) -> None:
    _require_content_hash(proof)
    mapping = proof["mapping"]
    _require_content_hash(mapping)
    reference = mapping["reference"]
    original = base64.b64decode(mapping["raw_original_base64"], validate=True)
    require("sha256:" + sha256(original).hexdigest() == reference["raw_digest"])
    require(
        proof["request"]
        == {
            "product_name": "CompositeHistoricalPolicyVerificationRequest",
            "product_version": "v1",
            "purpose": "COMPOSITE_HISTORICAL_MONTHLY_POLICY_ADMISSION",
            "reference": reference,
            "scope": policy["policy"]["scope"],
            "month": policy["policy"]["month"],
            "eligibility_policy_version": policy["eligibility_policy_version"],
            "reporting_currency": mapping["reporting_currency"],
            "operation": operation,
            "revision": revision,
            "actor_id": actor,
            "requested_at": at,
            "intent_digest": intent,
        }
    )
    require(mapping == policy["verification"]["mapping"])
    require(mapping["policy"] == policy["policy"])
    require(mapping["attachments"] == policy["attachments"])
    require(mapping["eligibility_policy_version"] == policy["eligibility_policy_version"])
    checked, admitted, expiry = (
        instant(proof[key]) for key in ("checked_at", "admitted_at", "expires_at")
    )
    requested = instant(at)
    require(checked <= requested <= admitted < expiry)
    require((expiry - checked).total_seconds() <= 300)
    require(proof["original_signature_status"] == "VERIFIED_AT_ORIGINAL_APPROVAL")
    require(proof["current_revocation_status"] == "CLEAR")
    require(proof["signer_principal_id"] != proof["verifier_principal_id"])
    require(proof["signer_key_digest"] != proof["verifier_key_digest"])
    key = base64.b64decode(proof["verifier_public_key_base64"], validate=True)
    require(len(key) == 32 and "sha256:" + sha256(key).hexdigest() == proof["verifier_key_digest"])
    require(len(base64.b64decode(proof["verifier_credential"], validate=True)) == 64)


def validate_operation(
    product: dict[str, Any], proposal: dict[str, Any], *, approval: bool
) -> None:
    intent = (
        proposal["content_hash"]
        if approval
        else source_content_digest(
            {
                key: value
                for key, value in proposal.items()
                if key not in {"content_hash", "operation_verification"}
            }
        )
    )
    validate_proof(
        product["operation_verification"],
        proposal["policy_approval"]["proposal"],
        operation="EVALUATION_APPROVAL" if approval else "EVALUATION_PROPOSAL",
        actor=product["approved_by" if approval else "proposed_by"],
        revision=proposal["evaluation_revision"],
        at=product["approved_at" if approval else "proposed_at"],
        intent=intent,
    )


def validate_policy(proposal: dict[str, Any], currency: str) -> None:
    approval = proposal["policy_approval"]
    policy = approval["proposal"]
    for source in (approval, policy, policy["policy"]):
        _require_content_hash(source)
    require(policy["policy"] == proposal["evaluation"]["resolved_policy"])
    require(approval["approved_by"] != policy["proposed_by"])
    require(instant(approval["approved_at"]) >= instant(policy["proposed_at"]))
    mapping = policy["verification"]["mapping"]
    require(mapping["reporting_currency"] == currency)
    require(mapping["original_proposed_by"] != mapping["original_approved_by"])
    require(instant(mapping["original_proposed_at"]) <= instant(mapping["original_approved_at"]))
    require(
        instant(mapping["original_approved_at"])
        < instant(policy["policy"]["month"] + "-01T00:00:00Z")
    )
    intent = source_content_digest(
        {
            "reference": mapping["reference"],
            "proposal_revision": policy["proposal_revision"],
        }
    )
    for product, operation, actor, at, digest in (
        (policy, "POLICY_PROPOSAL", "proposed_by", "proposed_at", intent),
        (approval, "POLICY_APPROVAL", "approved_by", "approved_at", policy["content_hash"]),
    ):
        validate_proof(
            product["verification"],
            policy,
            operation=operation,
            actor=product[actor],
            revision=policy["proposal_revision"],
            at=product[at],
            intent=digest,
        )
    validate_operation(proposal, proposal, approval=False)
