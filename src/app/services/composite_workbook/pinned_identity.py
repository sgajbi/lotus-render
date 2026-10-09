"""Structural equality of pinned vectors, without calculations or authority inference."""

from typing import Any

from app.contracts.composite_review import CompositeReviewContent

_SERIES_KEYS = ("calculation_id", "composite_id", "period_start", "period_end", "methodology")
_PIN_KEYS = (
    "materialization_id",
    "period_start",
    "period_end",
    "restatement_sequence",
    "definition_content_hash",
    "membership_content_hash",
    "attestation_content_hash",
    "source_cut_id",
    "method_binding",
    "retained_receipt_fingerprint",
)


def _require_period_pin(period: dict[str, Any], window: dict[str, Any]) -> None:
    _require_equal_keys(
        period,
        window,
        ("period_start", "period_end", "restatement_sequence"),
        "composite_period_pin_conflict",
    )
    if period.get("status") not in {"READY", "DEGRADED", "BLOCKED"}:
        raise ValueError("composite_source_status_invalid")
    members = _sequence(
        period.get("member_contributions"), "composite_period_population_incomplete"
    )
    if len(members) != period.get("member_count"):
        raise ValueError("composite_period_population_incomplete")
    members = [_mapping(member, "composite_source_member_invalid") for member in members]
    if len({member.get("portfolio_id") for member in members}) != len(members):
        raise ValueError("composite_period_population_duplicated")
    for member in members:
        _require_member_pin(member, period)
    _require_status_values(period)


def _require_member_pin(member: dict[str, Any], period: dict[str, Any]) -> None:
    _require_equal_keys(
        member,
        period,
        ("period_start", "period_end", "restatement_sequence"),
        "composite_member_pin_conflict",
    )
    if member.get("source_fingerprint") not in period.get("source_fingerprints", []):
        raise ValueError("composite_member_fingerprint_conflict")
    if member.get("restatement_version") not in period.get("restatement_versions", []):
        raise ValueError("composite_member_version_conflict")


def _require_financial_context(period: dict[str, Any], selection: dict[str, Any]) -> None:
    for key in ("return_view", "reporting_currency"):
        if period.get(key) not in (None, selection.get(key)):
            raise ValueError("composite_period_context_conflict")
    if period.get("return_value") is not None:
        _require_equal_keys(
            period,
            selection,
            ("return_view", "reporting_currency"),
            "composite_period_context_missing",
        )


def _require_status_values(period: dict[str, Any]) -> None:
    values = [period.get(key) for key in ("return_value", "cumulative_return")]
    if period["status"] == "BLOCKED" and values != [None, None]:
        raise ValueError("composite_blocked_financial_value")
    if period["status"] == "READY" and (None in values or period.get("member_count") == 0):
        raise ValueError("composite_ready_financial_value_missing")


def _require_equal_keys(
    left: dict[str, Any], right: dict[str, Any], keys: tuple[str, ...], code: str
) -> None:
    if any(not right.get(key) or left.get(key) != right[key] for key in keys):
        raise ValueError(code)


def _mapping(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def _sequence(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(code)
    return value


def _require_window(period: Any, window: Any, selection: dict[str, Any]) -> None:
    window = _mapping(window, "composite_window_pin_missing")
    if any(not window.get(key) for key in _PIN_KEYS):
        raise ValueError("composite_window_pin_missing")
    sequence = window["restatement_sequence"]
    if type(sequence) is not int or sequence < 1:
        raise ValueError("composite_window_pin_invalid")
    period = _mapping(period, "composite_source_period_invalid")
    _require_period_pin(period, window)
    _require_financial_context(period, selection)


def validate_pinned_identity(content: CompositeReviewContent) -> None:
    selection, source = content.selection, content.source_response
    _require_equal_keys(source, selection, _SERIES_KEYS, "composite_series_pin_conflict")
    manifest = _mapping(source.get("selection_manifest"), "composite_source_manifest_missing")
    if manifest.get("qualification") != content.qualification:
        raise ValueError("composite_source_qualification_conflict")
    windows = _sequence(selection.get("windows"), "composite_source_manifest_missing")
    periods = _sequence(source.get("periods"), "composite_source_period_missing")
    if not windows:
        raise ValueError("composite_source_manifest_missing")
    if len(periods) != len(windows):
        raise ValueError("composite_source_period_missing")
    if len(windows) > 120 or manifest.get("windows") != windows:
        raise ValueError("composite_source_vector_conflict")
    _require_equal_keys(
        manifest,
        selection,
        ("engine_version", "calculation_fingerprint"),
        "composite_source_vector_conflict",
    )
    for period, window in zip(periods, windows, strict=True):
        _require_window(period, window, selection)
    _require_series_status(source, periods)
    _require_unattested_authority(content)


def _require_series_status(source: dict[str, Any], periods: list[Any]) -> None:
    if source.get("status") not in {"READY", "DEGRADED", "BLOCKED"}:
        raise ValueError("composite_source_status_invalid")
    if source.get("cumulative_return") != periods[-1].get("cumulative_return"):
        raise ValueError("composite_cumulative_pin_conflict")
    if source["status"] == "BLOCKED" and source.get("cumulative_return") is not None:
        raise ValueError("composite_blocked_financial_value")


def _require_unattested_authority(content: CompositeReviewContent) -> None:
    if content.report_facts.get("authority") != {
        "receipt": None,
        "control_revision": None,
        "availability": "UNAVAILABLE",
        "reason_code": "SOURCE_AUTHORITY_NOT_ATTESTED",
    }:
        raise ValueError("composite_authority_not_supported")
    for key in ("qualification", "publication_state"):
        if content.report_facts.get(key) != getattr(content, key):
            raise ValueError("composite_authority_conflict")
