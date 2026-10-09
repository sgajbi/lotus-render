"""Report-frozen v4 eligibility pins, without a financial calculation selector."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Digest, Identifier

Month = Annotated[str, Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")]


class EvaluatedEligibilityPin(CompositeModel):
    evidence_kind: Literal["EVALUATED_ONLY"]
    month: Month
    evaluation_revision: Identifier
    proposal_content_hash: Digest
    proposal_response_digest: Digest
    parent_membership_revision: Identifier
    parent_membership_content_hash: Digest
    source_cut_id: Identifier


class PublishedEligibilityPin(CompositeModel):
    evidence_kind: Literal["PUBLISHED"]
    month: Month
    evaluation_revision: Identifier
    proposal_content_hash: Digest
    approval_content_hash: Digest
    receipt_content_hash: Digest
    receipt_response_digest: Digest
    membership_revision: Identifier
    membership_content_hash: Digest
    membership_response_digest: Digest
    attestation_version: Identifier
    universe_content_hash: Digest
    universe_response_digest: Digest
    parent_membership_revision: Identifier
    parent_membership_content_hash: Digest
    parent_response_digest: Digest
    publication_sequence: int = Field(gt=0)
    publication_response_digest: Digest
    source_cut_id: Identifier


EligibilityPin = Annotated[
    PublishedEligibilityPin | EvaluatedEligibilityPin, Field(discriminator="evidence_kind")
]


class EligibilitySelection(CompositeModel):
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: date
    period_end: date
    months: list[EligibilityPin] = Field(min_length=1, max_length=120)
