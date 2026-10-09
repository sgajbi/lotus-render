"""Bind whole v4 source variants to frozen selector pins, without rule evaluation."""

from typing import Any

from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.contracts.composite_eligibility_selection import EligibilityPin, EligibilitySelection
from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)
from app.services.composite_workbook.eligibility_population import (
    validate_eligibility_horizon,
    validate_eligibility_population,
)


def require_equal_fields(source: dict[str, Any], expected: dict[str, Any], code: str) -> None:
    if any(key not in source or source[key] != value for key, value in expected.items()):
        raise ValueError(code)


def _require_content_hash(source: dict[str, Any], *, recursive: bool = False) -> None:
    if source.get("content_hash") != source_content_digest(source, recursive=recursive):
        raise ValueError("composite_eligibility_content_hash_conflict")


def validate_eligibility_source(content: CompositeEligibilityContent, raw: dict[str, Any]) -> None:
    selection = content.selection
    validate_eligibility_horizon(selection)
    months = [pin.month for pin in selection.months]
    if (
        content.tenant_id != selection.tenant_id
        or len(set(months)) != len(months)
        or len(content.source_months) != len(months)
    ):
        raise ValueError("composite_eligibility_selection_conflict")
    for index, pin in enumerate(selection.months):
        month = raw["source_months"][index]
        if month["evidence_kind"] != pin.evidence_kind:
            raise ValueError("composite_eligibility_variant_conflict")
        _validate_month(month, pin, selection)


def _validate_month(
    month: dict[str, Any], pin: EligibilityPin, selection: EligibilitySelection
) -> None:
    published = pin.evidence_kind == "PUBLISHED"
    proposal = month["receipt"]["approval"]["proposal"] if published else month["proposal"]
    _validate_proposal(proposal, pin, selection)
    products = (
        ("receipt", "membership", "universe", "parent_membership", "publication")
        if published
        else ("proposal",)
    )
    if set(month["response_digests"]) != set(products):
        raise ValueError("composite_eligibility_response_set_conflict")
    pins = pin.model_dump(mode="json")
    _validate_response_pins(month, pins, products)
    if published:
        _validate_publication(month, pins, selection)


def _validate_response_pins(
    month: dict[str, Any], pins: dict[str, Any], products: tuple[str, ...]
) -> None:
    for name in products:
        key = "parent_response_digest" if name == "parent_membership" else name + "_response_digest"
        digest = whole_response_digest(month[name])
        if digest != month["response_digests"][name] or digest != pins[key]:
            raise ValueError("composite_eligibility_response_digest_conflict")


def _validate_proposal(
    proposal: dict[str, Any], pin: EligibilityPin, selection: EligibilitySelection
) -> None:
    require_equal_fields(
        proposal,
        {
            "evaluation_revision": pin.evaluation_revision,
            "content_hash": pin.proposal_content_hash,
            "parent_membership_revision": pin.parent_membership_revision,
            "parent_membership_content_hash": pin.parent_membership_content_hash,
        },
        "composite_eligibility_proposal_pin_conflict",
    )
    scope = {
        "tenant_id": selection.tenant_id,
        "composite_id": selection.composite_id,
        "definition_version": selection.definition_version,
        "month": pin.month,
        "source_cut_id": pin.source_cut_id,
    }
    for name in ("evaluation", "observations"):
        require_equal_fields(proposal[name], scope, "composite_eligibility_source_scope_conflict")
    observations = proposal["observations"]
    validate_eligibility_population(observations, proposal["evaluation"])
    _validate_proposal_inputs(proposal, pin, selection)
    require_equal_fields(
        observations,
        {"reporting_currency": selection.reporting_currency},
        "composite_eligibility_currency_conflict",
    )
    for item in observations["portfolios"]:
        if item["currency"] != selection.reporting_currency:
            raise ValueError("composite_eligibility_currency_conflict")
    policy = proposal["evaluation"]["resolved_policy"]
    require_equal_fields(
        policy, {"month": pin.month}, "composite_eligibility_policy_month_conflict"
    )
    for product in (policy, proposal["evaluation"], proposal):
        _require_content_hash(product)


def _validate_publication(
    month: dict[str, Any], pins: dict[str, Any], selection: EligibilitySelection
) -> None:
    bindings = {
        "receipt": {
            "content_hash": pins["receipt_content_hash"],
            "publication_sequence": pins["publication_sequence"],
        },
        "membership": {
            "content_hash": pins["membership_content_hash"],
            "membership_revision": pins["membership_revision"],
        },
        "parent_membership": {
            "content_hash": pins["parent_membership_content_hash"],
            "membership_revision": pins["parent_membership_revision"],
        },
        "universe": {
            "content_hash": pins["universe_content_hash"],
            "attestation_version": pins["attestation_version"],
        },
        "publication": {
            "sequence": pins["publication_sequence"],
            "membership_revision": pins["membership_revision"],
            "membership_content_hash": pins["membership_content_hash"],
        },
    }
    scope = {
        "tenant_id": selection.tenant_id,
        "composite_id": selection.composite_id,
        "definition_version": selection.definition_version,
    }
    for name, expected in bindings.items():
        require_equal_fields(
            month[name], expected, "composite_eligibility_publication_pin_conflict"
        )
        if name != "receipt":
            require_equal_fields(
                month[name], scope, "composite_eligibility_publication_scope_conflict"
            )
    approval = month["receipt"]["approval"]
    if approval["content_hash"] != pins["approval_content_hash"]:
        raise ValueError("composite_eligibility_approval_pin_conflict")
    for name in ("membership", "parent_membership", "universe"):
        _require_content_hash(month[name], recursive=True)
    _require_content_hash(approval)
    _require_content_hash(month["receipt"])
    _validate_publication_bindings(month, pins, selection)


def _validate_proposal_inputs(
    proposal: dict[str, Any], pin: EligibilityPin, selection: EligibilitySelection
) -> None:
    evaluation, universe = proposal["evaluation"], proposal["universe"]
    require_equal_fields(
        evaluation,
        {
            "input_content_hash": source_content_digest(proposal["observations"]),
            "universe_content_hash": universe["content_hash"],
        },
        "composite_eligibility_input_hash_conflict",
    )
    require_equal_fields(
        universe,
        {
            "tenant_id": selection.tenant_id,
            "composite_id": selection.composite_id,
            "definition_version": selection.definition_version,
            "membership_revision": pin.parent_membership_revision,
            "membership_content_hash": pin.parent_membership_content_hash,
            "expected_portfolio_ids": proposal["observations"]["expected_portfolio_ids"],
        },
        "composite_eligibility_input_universe_conflict",
    )
    _require_content_hash(universe, recursive=True)
    require_equal_fields(
        evaluation["resolved_policy"]["scope"],
        {
            "tenant_id": selection.tenant_id,
            "composite_id": selection.composite_id,
            "definition_version": selection.definition_version,
        },
        "composite_eligibility_policy_scope_conflict",
    )


def _validate_publication_bindings(
    month: dict[str, Any], pins: dict[str, Any], selection: EligibilitySelection
) -> None:
    receipt, membership, universe = month["receipt"], month["membership"], month["universe"]
    approval = receipt["approval"]
    _validate_publication_cuts(month, approval["proposal"]["universe"]["source_cut_id"])
    require_equal_fields(
        approval,
        {
            "membership_content_hash": membership["content_hash"],
            "published_universe_content_hash": universe["content_hash"],
        },
        "composite_eligibility_approval_binding_conflict",
    )
    require_equal_fields(
        approval["proposal"],
        {
            "target_membership_revision": membership["membership_revision"],
        },
        "composite_eligibility_target_membership_conflict",
    )
    require_equal_fields(
        universe,
        {
            "membership_revision": membership["membership_revision"],
            "membership_content_hash": membership["content_hash"],
        },
        "composite_eligibility_published_universe_conflict",
    )
    require_equal_fields(
        membership,
        {
            "supersedes_membership_revision": pins["parent_membership_revision"],
        },
        "composite_eligibility_membership_binding_conflict",
    )
    require_equal_fields(
        month["publication"],
        {
            **{
                key: membership[key]
                for key in (
                    "policy_version",
                    "supersedes_membership_revision",
                    "affected_from",
                    "affected_to",
                    "decided_at",
                )
            },
            "decision_count": len(membership["decisions"]),
        },
        "composite_eligibility_publication_binding_conflict",
    )
    _validate_receipt_bindings(receipt, membership, universe, selection)


def _validate_receipt_bindings(
    receipt: dict[str, Any],
    membership: dict[str, Any],
    universe: dict[str, Any],
    selection: EligibilitySelection,
) -> None:
    for name, source, revision in (
        ("membership_binding", membership, "membership_revision"),
        ("universe_binding", universe, "attestation_version"),
    ):
        expected = {
            "product_name": source["product_name"],
            "product_version": source["product_version"],
            "revision": source[revision],
            "digest": source["content_hash"],
        }
        if receipt[name] != expected:
            raise ValueError("composite_eligibility_receipt_binding_conflict")
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
        "composite_eligibility_definition_scope_conflict",
    )
    if definition.get("product_version") not in {"v1", "v2"}:
        raise ValueError("composite_eligibility_definition_version_conflict")
    _require_content_hash(definition, recursive=definition["product_version"] == "v1")


def _validate_publication_cuts(month: dict[str, Any], universe_cut: str) -> None:
    # R3: publication products bind the input-universe cut; observations and
    # evaluation bind the selector's distinct observation cut.
    for name in ("receipt", "membership", "universe", "publication"):
        require_equal_fields(
            month[name],
            {"source_cut_id": universe_cut},
            "composite_eligibility_publication_source_cut_conflict",
        )
