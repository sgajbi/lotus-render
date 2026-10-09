"""Reconcile the complete linked selector and source population, without financial arithmetic."""

import json
from collections import Counter
from datetime import timedelta
from typing import Any

from app.contracts.composite_linked import CompositeLinkedContent, LinkedResponse, LinkedSelection
from app.services.composite_workbook.source_products import validate_response_digest
from app.services.composite_workbook.source_values import decimal_value

LINKED_FINANCIAL_POLICY = {
    "cumulative_return": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENT", 2),
    "return_value": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENT", 2),
    "weight": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENT", 2),
    "linked_contribution": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENTAGE_POINTS", 2),
    "contribution": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENTAGE_POINTS", 2),
    "total_linked_contribution": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENTAGE_POINTS", 2),
    "reconciliation_difference": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENTAGE_POINTS", 12),
    "display_rounding_difference": ("DECIMAL_RETURN", "DECIMAL_RATIO", "PERCENTAGE_POINTS", 12),
    "linking_factor": ("DECIMAL_FACTOR", "DECIMAL_RATIO", "DECIMAL_RATIO", 12),
    "beginning_market_value": ("MONEY", "CURRENCY_UNITS", "CURRENCY_UNITS", 2),
    "participating_period_count": ("COUNT", "PERIOD_COUNT", "PERIOD_COUNT", 0),
}


def validate_linked_source(content: CompositeLinkedContent) -> None:
    selection = LinkedSelection.model_validate_json(json.dumps(content.selection))
    source = LinkedResponse.model_validate_json(json.dumps(content.source_response))
    validate_response_digest(
        content.selection, content.source_response, content.source_response_digest
    )
    if content.tenant_id != selection.tenant_id:
        raise ValueError("composite_source_tenant_conflict")
    request = selection.source_request
    for field in type(request).model_fields.keys() - {
        "materialization_ids",
        "restatement_sequence",
    }:
        if getattr(request, field) != getattr(source, field):
            raise ValueError("composite_linked_request_conflict")
    manifest = source.selection_manifest
    if (
        content.selection["windows"] != content.source_response["selection_manifest"]["windows"]
        or selection.engine_version != manifest.engine_version
        or selection.calculation_fingerprint != manifest.calculation_fingerprint
    ):
        raise ValueError("composite_source_vector_conflict")
    _validate_windows(selection)
    _validate_population(source, selection)
    _validate_source_numbers(content.source_response)


def _validate_windows(selection: LinkedSelection) -> None:
    request, windows = selection.source_request, selection.windows
    identifiers = [window.materialization_id for window in windows]
    if len(set(identifiers)) != len(identifiers) or identifiers != request.materialization_ids:
        raise ValueError("composite_linked_materialization_conflict")
    if (windows[0].period_start, windows[-1].period_end) != (
        request.period_start,
        request.period_end,
    ):
        raise ValueError("composite_horizon_conflict")
    for previous, current in zip(windows, windows[1:]):
        if current.period_start - previous.period_end != timedelta(days=1):
            raise ValueError("composite_window_order_invalid")


def _validate_population(source: LinkedResponse, selection: LinkedSelection) -> None:
    _validate_member_population(source)
    _validate_period_vector(source, selection)


def _validate_member_population(source: LinkedResponse) -> None:
    members = [member.portfolio_id for member in source.members]
    periods = [
        (period.portfolio_id, period.period_start, period.period_end) for period in source.periods
    ]
    if len(set(members)) != len(members) or len(set(periods)) != len(periods):
        raise ValueError("composite_linked_population_duplicated")
    _validate_member_counts(source, members)


def _validate_member_counts(source: LinkedResponse, members: list[str]) -> None:
    counts = Counter(period.portfolio_id for period in source.periods)
    if set(counts) != set(members) or any(
        member.participating_period_count != counts[member.portfolio_id]
        for member in source.members
    ):
        raise ValueError("composite_linked_population_incomplete")


def _validate_period_vector(source: LinkedResponse, selection: LinkedSelection) -> None:
    windows = {(window.period_start, window.period_end): window for window in selection.windows}
    observed = set()
    for period in source.periods:
        key = (period.period_start, period.period_end)
        window = windows.get(key)
        if window is None or (
            period.restatement_sequence != window.restatement_sequence
            or period.restatement_version != str(window.materialization_id)
        ):
            raise ValueError("composite_linked_period_pin_conflict")
        observed.add(key)
    if observed != windows.keys():
        raise ValueError("composite_linked_window_population_incomplete")


def _validate_source_numbers(source: dict[str, Any]) -> None:
    for row in [source, *source["members"], *source["periods"]]:
        for key in LINKED_FINANCIAL_POLICY.keys() & row.keys():
            decimal_value(str(row[key]), linked=True)
