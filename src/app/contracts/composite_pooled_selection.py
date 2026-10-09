"""Frozen pooled selector and exact money wire types from Report de686fd; no arithmetic."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, model_validator

from app.contracts.composite_review import CompositeModel

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^\S+$")]
FeeView = Literal["GROSS", "NET_ACTUAL", "NET_MODEL_FEE"]


def finite_source_number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("composite_pooled_money_not_exact")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("composite_pooled_money_invalid") from exc
    if not result.is_finite():
        raise ValueError("composite_pooled_money_not_finite")
    return result


SourceNumber = Annotated[
    Decimal,
    BeforeValidator(finite_source_number),
    Field(allow_inf_nan=False),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "integer"},
                {
                    "type": "string",
                    "pattern": r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$",
                },
            ]
        },
        mode="validation",
    ),
]


class SourceModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class PooledSourcePin(CompositeModel):
    """Exact retained owner source vector, distinct from read authority."""

    model_config = ConfigDict(extra="forbid")
    pin_id: Identifier
    owner: Identifier
    product_name: Identifier
    product_version: Identifier
    revision: Identifier
    source_cut_id: Identifier
    payload_digest: Digest
    compatibility_group: Identifier
    coverage_from: date
    coverage_to: date
    completeness: Literal["COMPLETE"]
    page_ids: list[Identifier] = Field(min_length=1, max_length=10000)
    expected_page_count: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def require_complete_pages(self) -> PooledSourcePin:
        if self.coverage_to < self.coverage_from or (
            len(self.page_ids) != self.expected_page_count
            or len(set(self.page_ids)) != len(self.page_ids)
        ):
            raise ValueError("COMPOSITE_POOLED_SOURCE_PIN_INCOMPLETE")
        return self


class PooledAnalysisSelection(CompositeModel):
    """Read an exact final result; neither submission nor caller economics."""

    model_config = ConfigDict(extra="forbid")
    tenant_id: Identifier
    composite_id: Identifier
    calculation_id: UUID
    schema_version: Literal["composite-pooled-mwr.v1"]
    metric_id: Literal["POOLED_MONEY_WEIGHTED_RETURN"]
    method: Literal["XIRR:v1"]
    period_start: date
    period_end: date
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    return_view: FeeView
    fee_basis: Identifier
    policy_binding_id: Identifier
    policy_content_hash: Identifier
    day_count_basis: Literal["BUS/252", "ACT/365", "ACT/ACT"]
    fallback_policy: Literal["REQUIRE_XIRR", "ALLOW_MODIFIED_DIETZ"]
    engine_version: Identifier
    source_manifest_id: Identifier
    input_manifest_digest: Digest
    source_bundle_digest: Digest
    response_digest: Digest
    expected_portfolio_ids: list[Identifier] = Field(min_length=1, max_length=10000)
    source_pins: list[PooledSourcePin] = Field(min_length=1, max_length=128)
    correction_of_calculation_id: UUID | None
    predecessor_response_digest: Digest | None

    @model_validator(mode="after")
    def require_exact_pooled_identity(self) -> PooledAnalysisSelection:
        if self.period_end <= self.period_start:
            raise ValueError("COMPOSITE_POOLED_POSITIVE_INTERVAL_REQUIRED")
        if len(set(self.expected_portfolio_ids)) != len(self.expected_portfolio_ids):
            raise ValueError("COMPOSITE_POOLED_DUPLICATE_MEMBER")
        if len({pin.pin_id for pin in self.source_pins}) != len(self.source_pins):
            raise ValueError("COMPOSITE_POOLED_DUPLICATE_SOURCE_PIN")
        if (self.correction_of_calculation_id is None) != (
            self.predecessor_response_digest is None
        ) or self.correction_of_calculation_id == self.calculation_id:
            raise ValueError("COMPOSITE_POOLED_CORRECTION_PIN_REQUIRED")
        return self
