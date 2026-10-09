"""Admit complete pinned source corrections without evaluating monthly rules."""

import json
from typing import Any

from app.contracts.composite_amendment import CompositeAmendmentContent
from app.contracts.composite_eligibility_selection import EligibilityPin, EligibilitySelection
from app.services.composite_workbook.amendment_lineage import validate_amendment_lineage
from app.services.composite_workbook.eligibility_population import validate_eligibility_horizon
from app.services.composite_workbook.eligibility_source import (
    _validate_proposal,
    _validate_publication,
    _validate_response_pins,
)


def common_selection(raw: dict[str, Any]) -> EligibilitySelection:
    """Project shared eligibility pins only; never rewrite retained source products."""
    selection = {k: v for k, v in raw.items() if k != "selection_version"}
    selection["months"] = [
        {
            k: v
            for k, v in pin.items()
            if k not in {"lineage_receipts", "parent_publication_response_digest"}
        }
        for pin in raw["months"]
    ]
    return EligibilitySelection.model_validate_json(json.dumps(selection))


def validate_amendment_source(content: CompositeAmendmentContent, raw: dict[str, Any]) -> None:
    selection = common_selection(raw["selection"])
    validate_eligibility_horizon(selection)
    if content.tenant_id != selection.tenant_id or len(content.source_months) != len(
        selection.months
    ):
        raise ValueError("composite_amendment_selection_conflict")
    for index, pin in enumerate(selection.months):
        _validate_month(
            raw["source_months"][index], raw["selection"]["months"][index], pin, selection
        )


def _validate_month(
    month: dict[str, Any],
    pins: dict[str, Any],
    pin: EligibilityPin,
    selection: EligibilitySelection,
) -> None:
    if month["evidence_kind"] != pin.evidence_kind:
        raise ValueError("composite_amendment_variant_conflict")
    published = pin.evidence_kind == "PUBLISHED"
    proposal = month["receipt"]["approval"]["proposal"] if published else month["proposal"]
    _validate_proposal(proposal, pin, selection)
    products = (
        (
            "receipt",
            "membership",
            "universe",
            "parent_membership",
            "publication",
            "parent_publication",
        )
        if published
        else ("proposal",)
    )
    if set(month["response_digests"]) != set(products):
        raise ValueError("composite_amendment_response_set_conflict")
    _validate_response_pins(month, pins, products)
    if published:
        _validate_publication(month, pins, selection)
    validate_amendment_lineage(month, pins, proposal, selection)
