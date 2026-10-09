"""Frozen Manage source projections; validation never evaluates eligibility rules."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.composite_selection import Digest, Identifier


# Source DTOs deliberately retain their supplier-approved additional metadata;
# whole-response hashes include it. Outer selectors and source variants are closed.
class EligibilitySourceModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


SourceDecimal = Annotated[
    str, Field(pattern=r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
]
SourceNumber = int | SourceDecimal
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
MemberStatus = Literal["INCLUDED", "EXCLUDED", "PENDING_REVIEW"]


class EligibilityAssessment(EligibilitySourceModel):
    rule: Literal["SIGNIFICANT_FLOW", "CASH", "READINESS"]
    outcome: Literal["PASS", "FAIL", "UNKNOWN"]
    failure_reasons: list[str]
    unknown_reasons: list[str]
    numerator: SourceNumber | None
    denominator: SourceNumber | None
    ratio: SourceNumber | None
    gross_inflow: SourceNumber | None
    gross_outflow: SourceNumber | None
    admitted_flow_count: int | None = Field(ge=0, le=250)


class EligibilityMember(EligibilitySourceModel):
    portfolio_id: Identifier
    observations_present: bool
    status: MemberStatus
    assessments: list[EligibilityAssessment] = Field(min_length=3, max_length=3)


class EligibilityObservationMember(EligibilitySourceModel):
    portfolio_id: Identifier
    currency: Currency
    prior_month_end_assets: SourceNumber | None
    prior_assets_as_of: str | None
    month_end_assets: SourceNumber | None
    settled_unencumbered_cash: SourceNumber | None
    cash_as_of: str | None
    discretionary: bool | None
    funded: bool | None
    invested: bool | None
    readiness_as_of: str | None
    flow_coverage_from: str | None
    flow_coverage_to: str | None
    flows: list[dict[str, Any]] = Field(max_length=250)


class EligibilityObservations(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEligibilityObservations"]
    product_version: Literal["v1"]
    evidence_class: Literal["SYNTHETIC_UNQUALIFIED", "SOURCE_UNVERIFIED"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    month: str
    source_cut_id: Identifier
    source_revision: Identifier
    reporting_currency: Currency
    source_generated_at: str
    expected_portfolio_ids: list[Identifier] = Field(min_length=1, max_length=1_000)
    portfolios: list[EligibilityObservationMember] = Field(max_length=1_000)


class EligibilityPolicy(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEligibilityPolicy"]
    product_version: Literal["v1"]
    profile_kind: Literal["SYNTHETIC_MONTHLY_ABS_NET_CASH_READINESS"]
    official_activation: Literal["UNAVAILABLE"]
    month: str
    scope: dict[str, Any]
    layers: list[dict[str, Any]] = Field(min_length=1, max_length=5)
    flow_threshold: SourceNumber
    cash_threshold: SourceNumber
    membership_frequency: Literal["CALENDAR_MONTH"]
    flow_measure: Literal["ABS_NET"]
    flow_denominator: Literal["PRIOR_MONTH_END_NET_ASSETS"]
    flow_breach_operator: Literal["GREATER_THAN_OR_EQUAL"]
    cash_denominator: Literal["MONTH_END_NET_ASSETS"]
    cash_numerator: Literal["SETTLED_UNENCUMBERED_CASH_ONLY"]
    cash_breach_operator: Literal["GREATER_THAN"]
    ratio_unit: Literal["DECIMAL_FRACTION"]
    flow_date_basis: Literal["SOURCE_BUSINESS_DATE_UTC"]
    holiday_treatment: Literal["NO_DATE_SHIFT"]
    currency_treatment: Literal["SOURCE_NORMALIZED_SINGLE_CURRENCY"]
    observation_window: Literal["WHOLE_TARGET_MONTH"]
    evaluation_timing: Literal["AFTER_MONTH_END"]
    source_cut_timing: Literal["AFTER_MONTH_END"]
    missing_data: Literal["REQUIRED_UNKNOWN"]
    reentry: Literal["REEVALUATE_ALL_NEXT_MONTH_RULES"]
    content_hash: Digest


class EligibilityEvaluation(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEligibilityEvaluation"]
    product_version: Literal["v1"]
    evidence_class: Literal["SYNTHETIC_UNQUALIFIED", "SOURCE_UNVERIFIED"]
    official_activation: Literal["UNAVAILABLE"]
    population_verification: Literal["UNVERIFIED"]
    tenant_id: Identifier
    composite_id: Identifier
    definition_version: Identifier
    month: str
    source_cut_id: Identifier
    source_revision: Identifier
    evaluated_at: str
    input_content_hash: Digest
    universe_content_hash: Digest
    resolved_policy: EligibilityPolicy
    declared_universe_coverage: Literal["COMPLETE", "INCOMPLETE"]
    expected_count: int = Field(ge=1, le=1_000)
    observed_count: int = Field(ge=0, le=1_000)
    included_count: int = Field(ge=0, le=1_000)
    excluded_count: int = Field(ge=0, le=1_000)
    pending_review_count: int = Field(ge=0, le=1_000)
    portfolios: list[EligibilityMember] = Field(min_length=1, max_length=1_000)
    content_hash: Digest


class EligibilityProposal(EligibilitySourceModel):
    product_name: Literal["CompositeMonthlyEvaluationProposal"]
    product_version: Literal["v1"]
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
