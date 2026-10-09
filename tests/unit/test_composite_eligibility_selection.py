"""The v4 eligibility selector cannot impersonate a financial or publication selector."""

import copy
import json
from typing import Any

import pytest
from eligibility_fixtures import DIGEST, selector
from pydantic import ValidationError

from app.contracts.composite_eligibility_selection import EligibilitySelection


@pytest.mark.parametrize("kind", ["EVALUATED_ONLY", "PUBLISHED"])
def test_exact_eligibility_selector_admits_without_mutating_retained_wire(kind: str) -> None:
    wire = selector(kind)
    original = copy.deepcopy(wire)
    parsed = EligibilitySelection.model_validate_json(json.dumps(wire))
    assert parsed.model_dump(mode="json") == wire == original


@pytest.mark.parametrize(
    "change",
    ["financial", "promotion", "approval", "extra", "missing", "bad_month", "bad_digest"],
)
def test_evaluated_selector_refuses_financial_or_false_publication_authority(change: str) -> None:
    wire = selector()
    pin = wire["months"][0]
    if change == "financial":
        wire["calculation_id"] = "00000000-0000-0000-0000-000000000000"
    elif change == "promotion":
        pin["evidence_kind"] = "PUBLISHED"
    elif change == "approval":
        pin["approval_content_hash"] = DIGEST
    elif change == "extra":
        pin["membership_revision"] = "invented-publication"
    elif change == "missing":
        del pin["parent_membership_content_hash"]
    elif change == "bad_month":
        pin["month"] = "2026-13"
    else:
        pin["proposal_response_digest"] = "sha256:" + "A" * 64
    with pytest.raises(ValidationError):
        EligibilitySelection.model_validate_json(json.dumps(wire))


@pytest.mark.parametrize("sequence", [0, -1, True, "1", 1.5])
def test_published_selector_requires_genuine_positive_integer_sequence(sequence: Any) -> None:
    wire = selector("PUBLISHED")
    wire["months"][0]["publication_sequence"] = sequence
    with pytest.raises(ValidationError):
        EligibilitySelection.model_validate_json(json.dumps(wire))


def test_published_selector_cannot_keep_an_evaluated_only_response_pin() -> None:
    wire = selector("PUBLISHED")
    wire["months"][0]["proposal_response_digest"] = DIGEST
    with pytest.raises(ValidationError):
        EligibilitySelection.model_validate_json(json.dumps(wire))
