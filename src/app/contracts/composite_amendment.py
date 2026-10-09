"""Explicit monthly source-v2 consumer; definition versions remain independent."""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.composite_eligibility import EligibilityTable
from app.contracts.composite_eligibility_evaluation import (
    EligibilityEvaluation,
    EligibilityObservations,
    EligibilitySourceModel,
)
from app.contracts.composite_eligibility_selection import (
    EvaluatedEligibilityPin,
    PublishedEligibilityPin,
)
from app.contracts.composite_eligibility_sources import (
    EligibilityMembership,
    EligibilityPublication,
    EligibilityReceipt,
    EligibilityUniverse,
)
from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Digest, Identifier


class MonthlyBinding(CompositeModel):
    product_name: Literal[
        "CompositeMonthlyEvaluationApproval",
        "CompositeMonthlyEligibilityPublicationReceipt",
        "CompositeMembership",
    ]
    product_version: Literal["v1", "v2"]
    revision: Identifier
    digest: Digest


class AmendmentEvidenceBinding(CompositeModel):
    product_name: Identifier
    product_version: Literal["v1"]
    revision: Identifier
    digest: Digest


class MonthlyAmendment(CompositeModel):
    correction_kind: Literal["SOURCE_CORRECTION"]
    predecessor_approval_binding: MonthlyBinding
    predecessor_receipt_binding: MonthlyBinding
    original_approval_binding: MonthlyBinding
    expected_authority_binding: MonthlyBinding
    projection_parent_membership_binding: MonthlyBinding
    expected_current_publication_sequence: int = Field(gt=0)
    affected_from: date
    affected_to: date
    reason_code: Identifier
    reason: str = Field(min_length=1, max_length=2048)
    evidence_bindings: list[AmendmentEvidenceBinding] = Field(min_length=1, max_length=32)


class AmendmentProposal(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEvaluationProposal"]
    product_version: Literal["v2"]
    evaluation_revision: Identifier
    target_membership_revision: Identifier
    parent_membership_revision: Identifier
    parent_membership_content_hash: Digest
    policy_approval: dict[str, Any]
    universe: dict[str, Any]
    observations: EligibilityObservations
    evaluation: EligibilityEvaluation
    proposed_by: Identifier
    proposed_at: str
    correlation_id: Identifier
    content_hash: Digest
    amendment: MonthlyAmendment
    publication_evidence_version: Literal["v1"]
    source_assembly_evidence: dict[str, Any] = Field(min_length=1)


class AmendmentApproval(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEvaluationApproval"]
    product_version: Literal["v2"]
    evidence_kind: Literal["SYNTHETIC_UNSIGNED"]
    official_activation: Literal["UNAVAILABLE"]
    proposal: AmendmentProposal
    approved_by: Identifier
    approved_at: str
    claims_digest: Digest
    membership_content_hash: Digest
    published_universe_content_hash: Digest
    content_hash: Digest


class AmendmentReceipt(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEligibilityPublicationReceipt"]
    product_version: Literal["v2"]
    definition: dict[str, Any]
    approval: AmendmentApproval
    membership_binding: dict[str, str]
    universe_binding: dict[str, str]
    source_cut_id: Identifier
    publication_sequence: int = Field(gt=0)
    completeness: Literal["UNVERIFIED"]
    content_hash: Digest
    lineage: MonthlyAmendment


class MonthlyReceiptPin(CompositeModel):
    product_version: Literal["v1", "v2"]
    evaluation_revision: Identifier
    approval_content_hash: Digest
    receipt_content_hash: Digest
    receipt_response_digest: Digest


class AmendmentEvaluatedPin(EvaluatedEligibilityPin):
    lineage_receipts: list[MonthlyReceiptPin] = Field(min_length=1, max_length=31)


class AmendmentPublishedPin(PublishedEligibilityPin):
    lineage_receipts: list[MonthlyReceiptPin] = Field(min_length=1, max_length=31)
    parent_publication_response_digest: Digest


AmendmentPin = Annotated[
    AmendmentEvaluatedPin | AmendmentPublishedPin, Field(discriminator="evidence_kind")
]
RetainedReceipt = Annotated[
    EligibilityReceipt | AmendmentReceipt, Field(discriminator="product_version")
]


class AmendmentEligibilitySelection(CompositeModel):
    selection_version: Literal["v2"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: date
    period_end: date
    months: list[AmendmentPin] = Field(min_length=1, max_length=120)


class AmendmentEvaluatedMonth(CompositeModel):
    evidence_kind: Literal["EVALUATED_ONLY"]
    proposal: AmendmentProposal
    response_digests: dict[str, Digest]
    lineage_receipts: list[RetainedReceipt] = Field(min_length=1, max_length=31)


class AmendmentPublishedMonth(CompositeModel):
    evidence_kind: Literal["PUBLISHED"]
    receipt: AmendmentReceipt
    membership: EligibilityMembership
    universe: EligibilityUniverse
    parent_membership: EligibilityMembership
    publication: EligibilityPublication
    response_digests: dict[str, Digest]
    lineage_receipts: list[RetainedReceipt] = Field(min_length=1, max_length=31)
    parent_publication: dict[str, Any]


AmendmentSourceMonth = Annotated[
    AmendmentEvaluatedMonth | AmendmentPublishedMonth, Field(discriminator="evidence_kind")
]


class CompositeAmendmentContent(CompositeModel):
    contract_version: Literal["composite_review.v6"]
    qualification: Literal["CONTROLLED_MONTHLY_SOURCE_AMENDMENT_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    tenant_id: Identifier
    selection: AmendmentEligibilitySelection
    source_months: list[AmendmentSourceMonth] = Field(min_length=1, max_length=120)
    report_facts: dict[str, Any]
    tables: list[EligibilityTable] = Field(min_length=9, max_length=9)
