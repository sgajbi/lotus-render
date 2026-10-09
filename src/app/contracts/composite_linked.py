"""Strict linked-only v3 consumer shapes; retained source mappings remain untouched."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.contracts.composite_review import CompositeCell, CompositeModel, CompositeReviewIdentity
from app.contracts.composite_selection import CompositeWindowPin, Digest, Identifier

DecimalText = Annotated[
    str,
    Field(max_length=256, pattern=r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"),
]


class LinkedRequest(CompositeModel):
    metric_id: Literal["LINKED_MEMBER_CONTRIBUTION"]
    method: Literal["CARINO:v1"]
    composite_id: Identifier
    calculation_id: UUID
    period_start: date
    period_end: date
    return_view: Literal["GROSS", "NET_ACTUAL", "NET_MODEL_FEE"]
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    materialization_ids: list[UUID] = Field(min_length=1, max_length=120)
    restatement_sequence: None = None


class LinkedSelection(CompositeModel):
    tenant_id: Identifier
    source_request: LinkedRequest
    windows: list[CompositeWindowPin] = Field(min_length=1, max_length=120)
    engine_version: Identifier
    calculation_fingerprint: Digest
    response_digest: Digest


class LinkedManifest(CompositeModel):
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    windows: list[CompositeWindowPin] = Field(min_length=1, max_length=120)
    engine_version: Identifier
    calculation_fingerprint: Digest


class LinkedSourceAuthority(CompositeModel):
    source_kind: Literal["INTERNAL", "EXTERNAL_PROVIDER", "HYBRID"]
    return_source_kind: Literal["LOTUS_PERFORMANCE", "EXTERNAL_PROVIDER"]
    provider_id: Identifier
    source_member_id: Identifier
    product_name: Identifier
    product_version: Identifier
    source_revision: Identifier
    source_digest: Digest


class LinkedMember(CompositeModel):
    portfolio_id: Identifier
    linked_contribution: DecimalText
    participating_period_count: int = Field(ge=1, le=120)


class LinkedPeriod(CompositeModel):
    portfolio_id: Identifier
    period_start: date
    period_end: date
    return_value: DecimalText
    beginning_market_value: DecimalText
    weight: DecimalText
    contribution: DecimalText
    linking_factor: DecimalText
    linked_contribution: DecimalText
    source_snapshot_id: Identifier
    source_fingerprint: Identifier
    calculation_id: str | None
    restatement_version: Identifier
    restatement_sequence: int = Field(ge=1)
    source_authority_identity: LinkedSourceAuthority | None


class LinkedResponse(CompositeModel):
    metric_id: Literal["LINKED_MEMBER_CONTRIBUTION"]
    method: Literal["CARINO:v1"]
    calculation_id: UUID
    composite_id: Identifier
    period_start: date
    period_end: date
    return_view: Literal["GROSS", "NET_ACTUAL", "NET_MODEL_FEE"]
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    status: Literal["CALCULATED_ANALYSIS"]
    qualification: Literal["RETAINED_SOURCE_ATTESTATION_NOT_LIVE_QUALIFIED"]
    units: Literal["DECIMAL_RETURN"]
    constituent_decomposition: Literal["AVAILABLE"]
    cumulative_return: DecimalText
    total_linked_contribution: DecimalText
    reconciliation_difference: DecimalText
    display_rounding_difference: DecimalText
    members: list[LinkedMember] = Field(min_length=1, max_length=10_000)
    periods: list[LinkedPeriod] = Field(min_length=1, max_length=10_000)
    selection_manifest: LinkedManifest


class LinkedColumn(CompositeModel):
    column_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    value_type: Literal["TEXT", "DECIMAL_RETURN", "DECIMAL_FACTOR", "MONEY", "COUNT"]
    unit: Literal["TEXT", "DECIMAL_RATIO", "CURRENCY_UNITS", "PERIOD_COUNT"]
    display_unit: Literal[
        "TEXT", "PERCENT", "PERCENTAGE_POINTS", "DECIMAL_RATIO", "CURRENCY_UNITS", "PERIOD_COUNT"
    ]
    display_conversion: Literal["IDENTITY", "RATIO_TO_PERCENT_DISPLAY"]
    display_decimal_places: int | None = Field(ge=0, le=12)
    display_rounding_mode: Literal["HALF_UP"] = "HALF_UP"
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    scale: Literal["1"] = "1"


class LinkedRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, CompositeCell]


class LinkedTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[LinkedColumn] = Field(min_length=1, max_length=32)
    rows: list[LinkedRow] = Field(min_length=1, max_length=10_000)


class CompositeLinkedContent(CompositeReviewIdentity):
    contract_version: Literal["composite_review.v3"]
    tables: list[LinkedTable] = Field(min_length=1, max_length=32)


class LinkedDisclosure(CompositeModel):
    code: Identifier
    text: str = Field(min_length=1, pattern=r"\S")


class LinkedUncaptured(CompositeModel):
    product: Literal[
        "CalendarReturns",
        "TrailingReturns",
        "SinceInception",
        "Risk",
        "Attribution",
        "ApprovedRestatement",
        "CompleteEligibilityPopulation",
    ]
    availability: Literal["UNAVAILABLE"]
    value: None
    reason_code: Literal["SOURCE_PRODUCT_NOT_CAPTURED"]


class LinkedFacts(CompositeModel):
    disclosures: list[LinkedDisclosure] = Field(min_length=1, max_length=10_000)
    uncaptured: list[LinkedUncaptured] = Field(min_length=7, max_length=7)
