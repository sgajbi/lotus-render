"""Additive v7 consumer; source evidence versions do not select definition versions."""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.composite_eligibility import EligibilityTable
from app.contracts.composite_eligibility_selection import (
    EvaluatedEligibilityPin,
    PublishedEligibilityPin,
)
from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Digest, Identifier


class HistoricalReceiptPin(CompositeModel):
    product_version: Literal["v3", "v4"]
    evaluation_revision: Identifier
    approval_content_hash: Digest
    receipt_content_hash: Digest
    receipt_response_digest: Digest


class HistoricalEvaluatedRootPin(EvaluatedEligibilityPin):
    product_version: Literal["v3"]


class HistoricalPublishedRootPin(PublishedEligibilityPin):
    product_version: Literal["v3"]


class HistoricalEvaluatedCorrectionPin(EvaluatedEligibilityPin):
    product_version: Literal["v4"]
    lineage_receipts: list[HistoricalReceiptPin] = Field(min_length=1, max_length=31)


class HistoricalPublishedCorrectionPin(PublishedEligibilityPin):
    product_version: Literal["v4"]
    lineage_receipts: list[HistoricalReceiptPin] = Field(min_length=1, max_length=31)
    parent_publication_response_digest: Digest


HistoricalPin = Annotated[
    Annotated[
        HistoricalEvaluatedRootPin | HistoricalPublishedRootPin,
        Field(discriminator="evidence_kind"),
    ]
    | Annotated[
        HistoricalEvaluatedCorrectionPin | HistoricalPublishedCorrectionPin,
        Field(discriminator="evidence_kind"),
    ],
    Field(discriminator="product_version"),
]


class HistoricalSelection(CompositeModel):
    selection_version: Literal["v3"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: date
    period_end: date
    months: list[HistoricalPin] = Field(min_length=1, max_length=120)


class CompositeHistoricalContent(CompositeModel):
    contract_version: Literal["composite_review.v7"]
    qualification: Literal["CONTROLLED_HISTORICAL_POLICY_EVIDENCE_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    tenant_id: Identifier
    selection: HistoricalSelection
    # The complete producer-namespaced JSON Schema validates these envelopes.
    # Retaining the mapping preserves every proof byte and additive source field.
    source_months: list[dict[str, Any]] = Field(min_length=1, max_length=120)
    report_facts: dict[str, Any]
    tables: list[EligibilityTable] = Field(min_length=10, max_length=10)
