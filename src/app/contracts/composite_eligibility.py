"""Report v4 consumer dataset: whole eligibility source, never financial inference."""

from typing import Any, Literal

from pydantic import Field

from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.contracts.composite_eligibility_sources import EligibilitySourceMonth
from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Identifier


class EligibilityCell(CompositeModel):
    canonical_value: str | None
    availability: Literal["AVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"]
    reason_codes: list[str]
    source_pointer: str = Field(pattern=r"^/(source_months|selection|report_facts)/")


class EligibilityColumn(CompositeModel):
    column_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    value_type: Literal["TEXT", "DECIMAL_FACTOR", "MONEY", "COUNT", "BOOLEAN"]
    unit: Literal[
        "TEXT", "DECIMAL_RATIO", "CURRENCY_UNITS", "PORTFOLIO_COUNT", "EVENT_COUNT", "BOOLEAN"
    ]
    display_unit: Literal[
        "TEXT", "DECIMAL_RATIO", "CURRENCY_UNITS", "PORTFOLIO_COUNT", "EVENT_COUNT", "BOOLEAN"
    ]
    display_conversion: Literal["IDENTITY"]
    display_decimal_places: int | None = Field(ge=0, le=12)
    display_rounding_mode: Literal["HALF_UP"]
    currency: str | None = Field(pattern=r"^[A-Z]{3}$")
    scale: Literal["1"]


class EligibilityRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, EligibilityCell]


class EligibilityTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[EligibilityColumn] = Field(min_length=1, max_length=32)
    rows: list[EligibilityRow] = Field(min_length=1, max_length=10_000)


class CompositeEligibilityContent(CompositeModel):
    contract_version: Literal["composite_review.v4"]
    qualification: Literal["CONTROLLED_ELIGIBILITY_SOURCE_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    tenant_id: Identifier
    selection: EligibilitySelection
    source_months: list[EligibilitySourceMonth] = Field(min_length=1, max_length=120)
    report_facts: dict[str, Any]
    tables: list[EligibilityTable] = Field(min_length=8, max_length=8)
