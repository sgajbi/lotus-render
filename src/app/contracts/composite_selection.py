"""Exact Report-owned selector wire shape, validated without rewriting retained data."""

from datetime import date, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^\S+$")]


class CompositeWindowPin(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    materialization_id: UUID
    period_start: date
    period_end: date
    restatement_sequence: int = Field(ge=1)
    definition_content_hash: Digest
    membership_content_hash: Digest
    attestation_content_hash: Digest
    source_cut_id: Identifier
    method_binding: dict[str, str] = Field(min_length=1)
    retained_receipt_fingerprint: Digest

    @model_validator(mode="after")
    def validate_window(self) -> "CompositeWindowPin":
        if self.period_end < self.period_start:
            raise ValueError("composite_window_dates_invalid")
        if any(not key.strip() or not value.strip() for key, value in self.method_binding.items()):
            raise ValueError("composite_method_identity_missing")
        return self


class CompositePinnedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenant_id: Identifier
    composite_id: Identifier
    calculation_id: UUID
    period_start: date
    period_end: date
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    return_view: Literal["GROSS", "NET_ACTUAL", "NET_MODEL_FEE"]
    methodology: Identifier
    engine_version: Identifier
    calculation_fingerprint: Digest
    response_digest: Digest
    windows: list[CompositeWindowPin] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_vector(self) -> "CompositePinnedSelection":
        if len({item.materialization_id for item in self.windows}) != len(self.windows):
            raise ValueError("composite_materialization_duplicated")
        if (self.windows[0].period_start, self.windows[-1].period_end) != (
            self.period_start,
            self.period_end,
        ):
            raise ValueError("composite_horizon_conflict")
        for previous, current in zip(self.windows, self.windows[1:]):
            if current.period_start != previous.period_end + timedelta(days=1):
                raise ValueError("composite_window_order_invalid")
        return self
