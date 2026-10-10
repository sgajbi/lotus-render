"""Exact v7 schema and producer-bound custody, without policy recomputation."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from app.contracts.composite_eligibility_selection import EligibilityPin, EligibilitySelection
from app.contracts.composite_historical import CompositeHistoricalContent
from app.services.composite_workbook.amendment_source import common_selection
from app.services.composite_workbook.eligibility_population import validate_eligibility_horizon
from app.services.composite_workbook.eligibility_source import (
    _validate_proposal,
    _validate_publication,
    _validate_response_pins,
)
from app.services.composite_workbook.historical_lineage import (
    _validate_retained_receipt,
    validate_historical_lineage,
)
from app.services.composite_workbook.historical_proof import require, validate_policy


@lru_cache
def historical_schema_validator() -> Any:
    path = files("app.contracts").joinpath("historical_schemas/composite_review.v7.schema.json")
    return Draft202012Validator(json.loads(path.read_bytes()))


def historical_common_selection(raw: dict[str, Any]) -> EligibilitySelection:
    common = {
        **raw,
        "months": [
            {key: value for key, value in pin.items() if key != "product_version"}
            for pin in raw["months"]
        ],
    }
    return common_selection(common)


def validate_historical_source(content: CompositeHistoricalContent, raw: dict[str, Any]) -> None:
    require(next(historical_schema_validator().iter_errors(raw), None) is None)
    selection = historical_common_selection(raw["selection"])
    validate_eligibility_horizon(selection)
    require(content.tenant_id == selection.tenant_id)
    require(len(content.source_months) == len(selection.months))
    for index, pin in enumerate(selection.months):
        _validate_month(
            raw["source_months"][index], raw["selection"]["months"][index], pin, selection
        )


def _response_products(published: bool, correction: bool) -> tuple[str, ...]:
    products = (
        ("receipt", "membership", "universe", "parent_membership", "publication")
        if published
        else ("proposal",)
    )
    if published and correction:
        return (*products, "parent_publication")
    return products


def _validate_month(
    month: dict[str, Any],
    pins: dict[str, Any],
    pin: EligibilityPin,
    selection: EligibilitySelection,
) -> None:
    published = pin.evidence_kind == "PUBLISHED"
    require(month["evidence_kind"] == pin.evidence_kind)
    proposal = month["receipt"]["approval"]["proposal"] if published else month["proposal"]
    require(proposal["product_version"] == pins["product_version"])
    _validate_proposal(proposal, pin, selection)
    validate_policy(proposal, selection.reporting_currency)
    correction = pins["product_version"] == "v4"
    products = _response_products(published, correction)
    require(set(month["response_digests"]) == set(products))
    _validate_response_pins(month, pins, products)
    if published:
        _validate_publication(month, pins, selection)
        receipt_pin = {
            key: pins[key]
            for key in (
                "product_version",
                "evaluation_revision",
                "approval_content_hash",
                "receipt_content_hash",
                "receipt_response_digest",
            )
        }
        _validate_retained_receipt(month["receipt"], receipt_pin, pins["month"], selection)
    if correction:
        require(all(row["product_version"] == "v4" for row in month["lineage_receipts"][:-1]))
        validate_historical_lineage(month, pins, proposal, selection)
    else:
        require(not month["lineage_receipts"] and month.get("parent_publication") is None)
