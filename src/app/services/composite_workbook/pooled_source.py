"""Exact retained source/policy/pin/outcome admission; never solve XIRR or derive returns."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.contracts.composite_pooled import (
    PooledObservation,
    PooledOutcome,
    PooledResponse,
    QualifiedPooledConvergence,
)
from app.contracts.composite_pooled_selection import (
    PooledAnalysisSelection,
    PooledSourcePin,
    SourceNumber,
)

_SOURCE_MONEY = TypeAdapter(SourceNumber)


def response_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _refuse(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _finite_json(value: Any) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("COMPOSITE_POOLED_NONFINITE_DIAGNOSTIC") from exc


def admit_pooled_response(
    *,
    selection: PooledAnalysisSelection,
    admitted_tenant_id: str,
    payload: dict[str, Any],
) -> PooledResponse:
    _refuse(selection.tenant_id == admitted_tenant_id, "COMPOSITE_REPORT_TENANT_MISMATCH")
    _finite_json(payload)
    _refuse(
        response_digest(payload) == selection.response_digest, "COMPOSITE_REPORT_RESPONSE_CHANGED"
    )
    source = PooledResponse.model_validate(payload)
    observation = source.observation
    identity = {
        "calculation_id": selection.calculation_id,
        "composite_id": selection.composite_id,
        "schema_version": selection.schema_version,
        "metric_id": selection.metric_id,
        "method": selection.method,
        "input_manifest_digest": selection.input_manifest_digest,
        "calculation_engine_version": selection.engine_version,
        "correction_of_calculation_id": selection.correction_of_calculation_id,
    }
    _refuse(
        all(getattr(source, key) == value for key, value in identity.items()),
        "COMPOSITE_POOLED_SOURCE_IDENTITY_CONFLICT",
    )
    _refuse(
        all(
            getattr(observation, key) == getattr(selection, key)
            for key in (
                "tenant_id",
                "composite_id",
                "source_manifest_id",
                "input_manifest_digest",
                "period_start",
                "period_end",
                "reporting_currency",
            )
        ),
        "COMPOSITE_POOLED_OBSERVATION_IDENTITY_CONFLICT",
    )
    bundle = observation.source_bundle
    _refuse(
        response_digest(bundle) == selection.source_bundle_digest,
        "COMPOSITE_POOLED_BUNDLE_DIGEST_CONFLICT",
    )
    _refuse(
        all(
            bundle.get(key) == getattr(selection, key)
            for key in (
                "tenant_id",
                "composite_id",
                "source_manifest_id",
                "reporting_currency",
            )
        )
        and bundle.get("period_start") == selection.period_start.isoformat()
        and bundle.get("period_end") == selection.period_end.isoformat(),
        "COMPOSITE_POOLED_BUNDLE_SCOPE_CONFLICT",
    )
    _require_bundle(selection, bundle, observation)
    _require_outcome(selection, source.outcome)
    return source


def _require_bundle(
    selection: PooledAnalysisSelection,
    bundle: dict[str, Any],
    observation: PooledObservation,
) -> None:
    _require_population(selection, bundle, observation)
    pin_ids = _require_source_pins(selection, bundle)
    _require_policy(selection, bundle)
    _require_member_money(selection, bundle, pin_ids)
    _require_flow_coverage(selection, bundle, observation, pin_ids)


def _require_population(
    selection: PooledAnalysisSelection, bundle: dict[str, Any], observation: PooledObservation
) -> None:
    expected = selection.expected_portfolio_ids
    _refuse(
        bundle.get("population_complete") is True
        and type(bundle.get("expected_population_count")) is int
        and bundle["expected_population_count"] == len(expected)
        and bundle.get("expected_portfolio_ids") == expected
        and set(observation.per_member_controls) == set(expected),
        "COMPOSITE_POOLED_POPULATION_CONFLICT",
    )
    _refuse(
        bundle.get("qualification") in {"CONTROLLED_SYNTHETIC_ONLY", "OWNER_QUALIFIED_SOURCE"}
        and bundle.get("institutional_attestation") in {"NOT_ATTESTED", "OWNER_ATTESTED"},
        "COMPOSITE_POOLED_QUALIFICATION_REQUIRED",
    )
    _refuse(
        all(
            isinstance(bundle.get(key), str) and bundle[key]
            for key in (
                "definition_revision",
                "definition_hash",
                "membership_revision",
                "membership_hash",
                "compatibility_reference",
                "population_source_pin_id",
            )
        ),
        "COMPOSITE_POOLED_SOURCE_REVISION_REQUIRED",
    )


def _require_source_pins(selection: PooledAnalysisSelection, bundle: dict[str, Any]) -> set[str]:
    pins = [PooledSourcePin.model_validate_json(json.dumps(pin)) for pin in bundle["source_pins"]]
    _refuse(pins == selection.source_pins, "COMPOSITE_POOLED_SOURCE_VECTOR_CONFLICT")
    pin_ids = {pin.pin_id for pin in pins}
    _refuse(
        set(bundle.get("compatible_pin_ids", [])) == pin_ids
        and len(bundle.get("compatible_pin_ids", [])) == len(pin_ids)
        and bundle["population_source_pin_id"] in pin_ids
        and set(bundle["raw_source_bodies"]) == pin_ids,
        "COMPOSITE_POOLED_SOURCE_COMPATIBILITY_CONFLICT",
    )
    for pin in pins:
        _require_source_body(selection, bundle, pin)
    return pin_ids


def _require_source_body(
    selection: PooledAnalysisSelection, bundle: dict[str, Any], pin: PooledSourcePin
) -> None:
    _refuse(
        pin.coverage_from <= selection.period_start
        and pin.coverage_to >= selection.period_end
        and response_digest(bundle["raw_source_bodies"][pin.pin_id]) == pin.payload_digest,
        "COMPOSITE_POOLED_SOURCE_BODY_CONFLICT",
    )


def _require_policy(selection: PooledAnalysisSelection, bundle: dict[str, Any]) -> None:
    policy = bundle["policy"]
    fields = {
        "binding_id": selection.policy_binding_id,
        "content_hash": selection.policy_content_hash,
        "method": selection.method,
        "return_view": selection.return_view,
        "fee_basis": selection.fee_basis,
        "day_count_basis": selection.day_count_basis,
        "fallback_policy": selection.fallback_policy,
    }
    _refuse(
        all(policy.get(key) == value for key, value in fields.items()),
        "COMPOSITE_POOLED_POLICY_CONFLICT",
    )


def _require_member_money(
    selection: PooledAnalysisSelection, bundle: dict[str, Any], pin_ids: set[str]
) -> None:
    expected = selection.expected_portfolio_ids
    for row in bundle["membership"]:
        _refuse(
            row["portfolio_id"] in expected
            and row["status"] in {"INCLUDED", "EXCLUDED", "PENDING"}
            and date.fromisoformat(row["effective_from"])
            <= date.fromisoformat(row["effective_to"]),
            "COMPOSITE_POOLED_MEMBERSHIP_CONFLICT",
        )
    for row in bundle["valuations"] + bundle["flows"]:
        _refuse(
            row["portfolio_id"] in expected
            and row["currency"] == selection.reporting_currency
            and row["source_pin_id"] in pin_ids
            and row["units"] == "MONETARY_AMOUNT",
            "COMPOSITE_POOLED_MONEY_SCOPE_CONFLICT",
        )
        # Validate exact source money without modifying the retained raw representation.
        _SOURCE_MONEY.validate_python(row["amount"])


def _require_flow_coverage(
    selection: PooledAnalysisSelection,
    bundle: dict[str, Any],
    observation: PooledObservation,
    pin_ids: set[str],
) -> None:
    expected = selection.expected_portfolio_ids
    coverage = bundle["flow_coverage"]
    _refuse(
        len(coverage) == len(expected)
        and {row["portfolio_id"] for row in coverage} == set(expected)
        and all(
            row["complete"] is True
            and row["source_pin_id"] in pin_ids
            and date.fromisoformat(row["coverage_from"]) <= selection.period_start
            and date.fromisoformat(row["coverage_to"]) >= selection.period_end
            for row in coverage
        ),
        "COMPOSITE_POOLED_FLOW_COVERAGE_CONFLICT",
    )
    _require_flow_dates(selection, observation)


def _require_flow_dates(selection: PooledAnalysisSelection, observation: PooledObservation) -> None:
    _refuse(
        all(
            selection.period_start <= row.economic_date <= selection.period_end
            for row in observation.investor_cash_flows + observation.portfolio_cash_flows
        ),
        "COMPOSITE_POOLED_FLOW_DATE_CONFLICT",
    )


def _require_outcome(selection: PooledAnalysisSelection, outcome: PooledOutcome) -> None:
    values = (outcome.return_value, outcome.annualized_return, outcome.holding_period_return)
    _require_solver_interval(selection, outcome.diagnostics)
    if outcome.availability == "NOT_CALCULABLE":
        _refuse(
            all(value is None for value in values) and bool(outcome.reason_codes),
            "COMPOSITE_POOLED_REJECTED_RETURN_PRESENT",
        )
        return
    _require_calculable_outcome(selection, outcome)


def _require_solver_interval(
    selection: PooledAnalysisSelection, diagnostics: dict[str, Any]
) -> None:
    _refuse(
        diagnostics.get("actual_interval_start") == selection.period_start.isoformat()
        and diagnostics.get("actual_interval_end") == selection.period_end.isoformat()
        and diagnostics.get("day_count_basis", selection.day_count_basis)
        == selection.day_count_basis
        and diagnostics.get("output_units", "DECIMAL_FRACTION") == "DECIMAL_FRACTION",
        "COMPOSITE_POOLED_SOLVER_INTERVAL_CONFLICT",
    )


def _require_calculable_outcome(selection: PooledAnalysisSelection, outcome: PooledOutcome) -> None:
    diagnostics = outcome.diagnostics
    # Successful and explicitly elected fallback outputs must state their units
    # and date convention. Sparse numerical-domain failures above retain absence.
    _refuse(
        diagnostics.get("day_count_basis") == selection.day_count_basis
        and diagnostics.get("output_units") == "DECIMAL_FRACTION",
        "COMPOSITE_POOLED_SOLVER_INTERVAL_CONFLICT",
    )
    if outcome.availability == "FALLBACK_ANALYSIS":
        _require_elected_fallback(selection, outcome)
    else:
        _require_available_xirr(selection, outcome)


def _require_elected_fallback(selection: PooledAnalysisSelection, outcome: PooledOutcome) -> None:
    _refuse(
        selection.fallback_policy == "ALLOW_MODIFIED_DIETZ"
        and outcome.actual_method == "MODIFIED_DIETZ"
        and outcome.return_value is not None
        and outcome.original_solver_result.get("status") == "FALLBACK_USED"
        and outcome.original_solver_result.get("method") == "MODIFIED_DIETZ"
        and outcome.diagnostics.get("fallback_from") == "XIRR"
        and bool(outcome.diagnostics.get("fallback_reason")),
        "COMPOSITE_POOLED_FALLBACK_NOT_ELECTED",
    )


def _require_available_xirr(selection: PooledAnalysisSelection, outcome: PooledOutcome) -> None:
    convergence = outcome.diagnostics.get("convergence", {})
    values = (outcome.return_value, outcome.annualized_return, outcome.holding_period_return)
    _refuse(
        outcome.actual_method == "XIRR"
        and all(value is not None for value in values)
        and convergence.get("day_count_basis") == selection.day_count_basis
        and outcome.original_solver_result.get("status") == "CALCULATED"
        and outcome.original_solver_result.get("method") == "XIRR",
        "COMPOSITE_POOLED_XIRR_NOT_QUALIFIED",
    )
    try:
        QualifiedPooledConvergence.model_validate(convergence)
    except ValidationError as exc:
        raise ValueError("COMPOSITE_POOLED_XIRR_NOT_QUALIFIED") from exc


def require_predecessor(
    selection: PooledAnalysisSelection,
    predecessor: dict[str, Any] | None,
) -> None:
    if selection.correction_of_calculation_id is None:
        _refuse(predecessor is None, "COMPOSITE_POOLED_UNEXPECTED_PREDECESSOR")
        return
    _refuse(predecessor is not None, "COMPOSITE_POOLED_PREDECESSOR_REQUIRED")
    assert predecessor is not None
    _finite_json(predecessor)
    parent = PooledResponse.model_validate(predecessor)
    _require_predecessor_scope(selection, predecessor, parent)
    bundle = parent.observation.source_bundle
    _refuse(
        all(
            bundle.get(key) == getattr(parent.observation, key)
            for key in ("tenant_id", "composite_id", "source_manifest_id", "reporting_currency")
        )
        and bundle.get("period_start") == selection.period_start.isoformat()
        and bundle.get("period_end") == selection.period_end.isoformat(),
        "COMPOSITE_POOLED_PREDECESSOR_SCOPE_CONFLICT",
    )
    # The selected raw predecessor digest is the immutable pin. Validate its
    # own population and source bodies without requiring recursive history.
    parent_scope = selection.model_copy(
        update={
            "expected_portfolio_ids": bundle["expected_portfolio_ids"],
            "source_pins": [
                PooledSourcePin.model_validate_json(json.dumps(pin))
                for pin in bundle["source_pins"]
            ],
        }
    )
    _require_bundle(parent_scope, bundle, parent.observation)
    _require_outcome(parent_scope, parent.outcome)


def _require_predecessor_scope(
    selection: PooledAnalysisSelection, predecessor: dict[str, Any], parent: PooledResponse
) -> None:
    _refuse(
        response_digest(predecessor) == selection.predecessor_response_digest,
        "COMPOSITE_POOLED_PREDECESSOR_SCOPE_CONFLICT",
    )
    expected = {
        "calculation_id": selection.correction_of_calculation_id,
        "composite_id": selection.composite_id,
        "metric_id": selection.metric_id,
        "method": selection.method,
    }
    _refuse(
        all(getattr(parent, key) == value for key, value in expected.items()),
        "COMPOSITE_POOLED_PREDECESSOR_SCOPE_CONFLICT",
    )
    fields = ("tenant_id", "period_start", "period_end", "reporting_currency")
    _refuse(
        all(getattr(parent.observation, key) == getattr(selection, key) for key in fields),
        "COMPOSITE_POOLED_PREDECESSOR_SCOPE_CONFLICT",
    )
