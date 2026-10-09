"""Strict v5 consumer projection of the frozen Report-owned pooled contract."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, FiniteFloat, StrictBool, model_validator

from app.contracts.composite_pooled_selection import (
    Digest,
    Identifier,
    PooledAnalysisSelection,
    SourceModel,
    SourceNumber,
)
from app.contracts.composite_review import CompositeModel


class PooledCashFlow(SourceModel):
    economic_date: date
    amount: SourceNumber
    source_event_ids: list[Identifier]


class PooledObservation(SourceModel):
    tenant_id: Identifier
    composite_id: Identifier
    source_manifest_id: Identifier
    input_manifest_digest: Digest
    period_start: date
    period_end: date
    reporting_currency: str = Field(pattern=r"^[A-Z]{3}$")
    opening_value: SourceNumber
    terminal_value: SourceNumber
    investor_cash_flows: list[PooledCashFlow] = Field(max_length=10000)
    portfolio_cash_flows: list[PooledCashFlow] = Field(max_length=10000)
    per_member_controls: dict[str, dict[str, SourceNumber]]
    eliminated_transfer_event_ids: list[Identifier]
    excluded_flow_event_ids: list[Identifier]
    source_bundle: dict[str, Any]


class PooledOutcome(SourceModel):
    availability: Literal["AVAILABLE", "NOT_CALCULABLE", "FALLBACK_ANALYSIS"]
    actual_method: Literal["XIRR", "MODIFIED_DIETZ", "DIETZ"]
    return_value: SourceNumber | None
    annualized_return: SourceNumber | None
    holding_period_return: SourceNumber | None
    units: Literal["DECIMAL_FRACTION"]
    root_precision: Literal["FLOAT64"]
    input_money_precision: Literal["EXACT_DECIMAL"]
    reason_codes: list[Identifier] = Field(max_length=32)
    diagnostics: dict[str, Any]
    original_solver_result: dict[str, Any]


class QualifiedPooledConvergence(SourceModel):
    """Source-stated controls of an AVAILABLE root; no independent solver claim."""

    algorithm: Identifier
    anchor_date: date
    day_count_basis: Literal["BUS/252", "ACT/365", "ACT/ACT"]
    converged: StrictBool
    uniqueness_supported: StrictBool
    non_simple_root_detected: StrictBool
    root_count_detected: int = Field(ge=0, strict=True)
    normalized_flow_count: int = Field(ge=2, strict=True)
    iterations: int = Field(ge=0, strict=True)
    max_iterations: int = Field(ge=1, strict=True)
    root_scan_steps: int = Field(ge=1, strict=True)
    solver_work_units: int = Field(ge=1, strict=True)
    gross_cash_flow_scale: FiniteFloat = Field(gt=0)
    rate_lower_bound: FiniteFloat = Field(gt=-1)
    rate_upper_bound: FiniteFloat
    residual: FiniteFloat
    residual_npv: FiniteFloat
    tolerance: FiniteFloat = Field(gt=0)
    termination_reason: Identifier

    @model_validator(mode="after")
    def require_qualified_control_state(self) -> QualifiedPooledConvergence:
        if not (
            self.converged
            and self.uniqueness_supported
            and not self.non_simple_root_detected
            and self.root_count_detected == 1
            and self.iterations <= self.max_iterations
            and self.rate_upper_bound > self.rate_lower_bound
        ):
            raise ValueError("COMPOSITE_POOLED_XIRR_NOT_QUALIFIED")
        return self


class PooledResponse(SourceModel):
    schema_version: Literal["composite-pooled-mwr.v1"]
    calculation_id: UUID
    metric_id: Literal["POOLED_MONEY_WEIGHTED_RETURN"]
    method: Literal["XIRR:v1"]
    composite_id: Identifier
    input_manifest_digest: Digest
    calculation_engine_version: Identifier
    correction_of_calculation_id: UUID | None
    result_classification: Literal["NON_OFFICIAL_CALCULATED_ANALYSIS"]
    observation: PooledObservation
    outcome: PooledOutcome

    @model_validator(mode="after")
    def require_bound_observation(self) -> PooledResponse:
        if (
            self.composite_id != self.observation.composite_id
            or self.input_manifest_digest != self.observation.input_manifest_digest
            or self.correction_of_calculation_id == self.calculation_id
        ):
            raise ValueError("COMPOSITE_POOLED_OBSERVATION_IDENTITY_CONFLICT")
        return self


class PooledColumn(CompositeModel):
    column_id: Identifier
    label: str
    value_type: Literal["TEXT", "DECIMAL_RETURN", "MONEY"]
    unit: Literal["TEXT", "DECIMAL_RATIO", "CURRENCY_UNITS"]
    display_unit: Literal["TEXT", "PERCENT", "CURRENCY_UNITS"]
    display_conversion: Literal["IDENTITY", "RATIO_TO_PERCENT_DISPLAY"]
    display_decimal_places: int | None = Field(ge=0, le=12)
    display_rounding_mode: Literal["HALF_UP"]
    currency: str | None
    scale: Literal["1"]


class PooledCell(CompositeModel):
    canonical_value: str | None
    availability: Literal["AVAILABLE", "UNAVAILABLE"]
    reason_codes: list[Identifier] = Field(max_length=32)
    source_pointer: str = Field(
        pattern=r"^/(source_response|selection|report_facts|predecessor_source_response)/"
    )


class PooledRow(CompositeModel):
    row_id: Identifier
    cells: dict[str, PooledCell]


class PooledTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str
    columns: list[PooledColumn] = Field(min_length=1, max_length=32)
    rows: list[PooledRow] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def complete_rows(self) -> PooledTable:
        keys = [column.column_id for column in self.columns]
        if len(keys) != len(set(keys)) or len({r.row_id for r in self.rows}) != len(self.rows):
            raise ValueError("composite_pooled_table_identity_duplicated")
        if any(set(row.cells) != set(keys) for row in self.rows):
            raise ValueError("composite_pooled_row_incomplete")
        return self


class CompositePooledReportData(CompositeModel):
    contract_version: Literal["composite_review.v5"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    tenant_id: Identifier
    selection: PooledAnalysisSelection
    source_response_digest: Digest
    source_response: dict[str, Any]
    predecessor_source_response: dict[str, Any] | None
    report_facts: dict[str, Any]
    tables: list[PooledTable] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def require_complete_projection(self) -> CompositePooledReportData:
        from app.services.composite_workbook.pooled_source import (
            _refuse,
            admit_pooled_response,
            require_predecessor,
        )
        from app.services.composite_workbook.pooled_tables import pooled_report_facts, pooled_tables

        admit_pooled_response(
            selection=self.selection,
            admitted_tenant_id=self.tenant_id,
            payload=self.source_response,
        )
        _refuse(
            self.source_response_digest == self.selection.response_digest,
            "COMPOSITE_REPORT_DATASET_DIGEST_CONFLICT",
        )
        require_predecessor(self.selection, self.predecessor_source_response)
        raw = self.model_dump(mode="json")
        _refuse(
            self.report_facts == pooled_report_facts() and raw["tables"] == pooled_tables(raw),
            "COMPOSITE_POOLED_TABLE_LAYOUT_CONFLICT",
        )
        return self
