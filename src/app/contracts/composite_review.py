"""Render's typed consumer projection of the Report-owned composite_review.v1 contract."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CompositeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CompositeColumn(CompositeModel):
    column_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    value_type: Literal["TEXT", "DECIMAL_RETURN", "MONEY", "COUNT"]
    unit: Literal["TEXT", "DECIMAL_RATIO", "CURRENCY_UNITS", "PORTFOLIO_COUNT"]
    display_unit: Literal[
        "TEXT", "PERCENT", "PERCENTAGE_POINTS", "CURRENCY_UNITS", "PORTFOLIO_COUNT"
    ]
    display_conversion: Literal["IDENTITY", "RATIO_TO_PERCENT_DISPLAY"]
    display_decimal_places: int | None = Field(ge=0, le=12)
    display_rounding_mode: Literal["HALF_UP"] = "HALF_UP"
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    scale: Literal["1"] = "1"


class CompositeCell(CompositeModel):
    canonical_value: str | None
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN", "NOT_APPLICABLE"]
    reason_codes: list[str] = Field(max_length=32)
    source_pointer: str = Field(pattern=r"^/(source_response|selection|report_facts)/")


class CompositeRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, CompositeCell]


class CompositeTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[CompositeColumn] = Field(min_length=1, max_length=32)
    rows: list[CompositeRow] = Field(min_length=1, max_length=10_000)


class CompositeReviewContent(CompositeModel):
    contract_version: Literal["composite_review.v1"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    tenant_id: str = Field(min_length=1, max_length=128)
    selection: dict[str, Any]
    source_response_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_response: dict[str, Any]
    report_facts: dict[str, Any]
    tables: list[CompositeTable] = Field(min_length=1, max_length=32)
