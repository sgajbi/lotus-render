"""Whole Report-retained eligibility products and disjoint v4 source variants."""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.composite_eligibility_evaluation import (
    EligibilityProposal,
    EligibilitySourceModel,
    MemberStatus,
)
from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Digest, Identifier


class EligibilityApproval(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEvaluationApproval"]
    product_version: Literal["v1"]
    evidence_kind: Literal["SYNTHETIC_UNSIGNED"]
    official_activation: Literal["UNAVAILABLE"]
    proposal: EligibilityProposal
    approved_by: Identifier
    approved_at: str
    claims_digest: Digest
    membership_content_hash: Digest
    published_universe_content_hash: Digest
    content_hash: Digest


class MembershipDecision(EligibilitySourceModel):
    portfolio_id: Identifier
    effective_from: str
    effective_to: str | None
    status: MemberStatus
    reason_code: str | None
    discretionary: bool
    approval_ref: str | None
    source_snapshot_id: Identifier


class EligibilityMembership(EligibilitySourceModel):
    product_name: Literal["CompositeMembership"]
    product_version: Literal["v1"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    membership_revision: Identifier
    policy_version: Identifier
    source_cut_id: Identifier
    decisions: list[MembershipDecision] = Field(min_length=1)
    decided_at: str
    decided_by: Identifier
    correlation_id: Identifier
    supersedes_membership_revision: str | None
    affected_from: str | None
    affected_to: str | None
    content_hash: Digest


class EligibilityUniverse(EligibilitySourceModel):
    product_name: Literal["CompositeUniverseAttestation"]
    product_version: Literal["v1"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    membership_revision: Identifier
    membership_content_hash: Digest
    attestation_version: Identifier
    coverage_from: str
    coverage_to: str
    policy_version: Identifier
    source_cut_id: Identifier
    source_products: list[dict[str, Any]] = Field(min_length=1)
    posture: Literal["COMPLETE", "INCOMPLETE", "UNAVAILABLE"]
    expected_portfolio_ids: list[Identifier]
    expected_portfolio_count: int = Field(ge=0)
    observed_portfolio_count: int = Field(ge=0)
    missing_portfolio_ids: list[Identifier]
    unexpected_portfolio_ids: list[Identifier]
    coverage_gap_portfolio_ids: list[Identifier]
    reason_code: str | None
    attested_at: str
    attested_by: Identifier
    correlation_id: Identifier
    content_hash: Digest


class EligibilityPublication(EligibilitySourceModel):
    product_name: Literal["CompositeMembershipPublication"]
    product_version: Literal["v1"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    sequence: int = Field(gt=0)
    membership_revision: Identifier
    membership_content_hash: Digest
    policy_version: Identifier
    source_cut_id: Identifier
    decision_count: int = Field(ge=1)
    supersedes_membership_revision: str | None
    affected_from: str | None
    affected_to: str | None
    decided_at: str
    published_at: str
    completeness: Literal["UNVERIFIED"]


class EligibilityReceipt(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEligibilityPublicationReceipt"]
    product_version: Literal["v1"]
    definition: dict[str, Any]
    approval: EligibilityApproval
    membership_binding: dict[str, str]
    universe_binding: dict[str, str]
    source_cut_id: Identifier
    publication_sequence: int = Field(gt=0)
    completeness: Literal["UNVERIFIED"]
    content_hash: Digest


class EvaluatedSourceMonth(CompositeModel):
    evidence_kind: Literal["EVALUATED_ONLY"]
    proposal: EligibilityProposal
    response_digests: dict[str, Digest]


class PublishedSourceMonth(CompositeModel):
    evidence_kind: Literal["PUBLISHED"]
    receipt: EligibilityReceipt
    membership: EligibilityMembership
    universe: EligibilityUniverse
    parent_membership: EligibilityMembership
    publication: EligibilityPublication
    response_digests: dict[str, Digest]


EligibilitySourceMonth = Annotated[
    EvaluatedSourceMonth | PublishedSourceMonth, Field(discriminator="evidence_kind")
]
