from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from prometheus_client import Counter, Histogram

METRIC_OPERATION_LABEL = "operation"
METRIC_STATUS_LABEL = "status"
METRIC_FAILURE_CATEGORY_LABEL = "failure_category"
METRIC_STATE_LABEL = "state"
METRIC_REASON_LABEL = "reason"
METRIC_FRESHNESS_BUCKET_LABEL = "freshness_bucket"

RENDER_METRIC_LABELS = frozenset(
    {
        METRIC_FRESHNESS_BUCKET_LABEL,
        METRIC_OPERATION_LABEL,
        METRIC_REASON_LABEL,
        METRIC_STATE_LABEL,
        METRIC_STATUS_LABEL,
        METRIC_FAILURE_CATEGORY_LABEL,
    }
)
FORBIDDEN_METRIC_LABELS = frozenset(
    {
        "account_id",
        "archive_document_id",
        "booking_center_code",
        "bucket",
        "client_id",
        "client_name",
        "correlation_id",
        "document_id",
        "idempotency_key",
        "portfolio_id",
        "portfolio_name",
        "raw_render_package",
        "raw_upstream_payload",
        "render_job_id",
        "report_job_id",
        "request_id",
        "snapshot_id",
        "storage_key",
        "tenant_id",
        "trace_id",
    }
)

IMPLEMENTED_RENDER_OPERATIONS = frozenset(
    {
        "artifact_metadata_lookup",
        "render_status_lookup",
        "render_submission",
    }
)
RENDER_OPERATION_STATUSES = frozenset(
    {
        "accepted",
        "failed",
        "not_found",
        "not_ready",
        "rendered",
        "rendering",
        "validating_package",
    }
)
RENDER_SUPPORTABILITY_STATES = frozenset({"ready", "degraded", "unavailable"})
RENDER_SUPPORTABILITY_REASONS = frozenset(
    {
        "render_supportability_ready",
        "render_supportability_draining",
        "render_store_unavailable",
        "template_registry_unavailable",
        "runtime_configuration_unavailable",
    }
)
RENDER_SUPPORTABILITY_FRESHNESS_BUCKETS = frozenset({"current", "unknown"})


@dataclass(frozen=True)
class RenderMetricContract:
    name: str
    metric_type: str
    labels: tuple[str, ...]
    implemented: bool
    description: str


RENDER_METRIC_CONTRACTS: tuple[RenderMetricContract, ...] = (
    RenderMetricContract(
        name="lotus_render_operations_total",
        metric_type="counter",
        labels=(METRIC_OPERATION_LABEL, METRIC_STATUS_LABEL, METRIC_FAILURE_CATEGORY_LABEL),
        implemented=True,
        description=(
            "Counts supported render submission, status lookup, and artifact metadata lookup "
            "operations by bounded operation, lifecycle status, and failure category."
        ),
    ),
    RenderMetricContract(
        name="lotus_render_operation_duration_seconds",
        metric_type="histogram",
        labels=(METRIC_OPERATION_LABEL, METRIC_STATUS_LABEL, METRIC_FAILURE_CATEGORY_LABEL),
        implemented=True,
        description="Measures supported render operation duration using bounded labels only.",
    ),
    RenderMetricContract(
        name="lotus_render_artifact_size_bytes",
        metric_type="histogram",
        labels=(METRIC_STATUS_LABEL,),
        implemented=True,
        description=(
            "Measures generated render artifact size without render job, report job, portfolio, "
            "tenant, trace, or storage identifiers."
        ),
    ),
    RenderMetricContract(
        name="lotus_render_supportability_total",
        metric_type="counter",
        labels=(METRIC_STATE_LABEL, METRIC_REASON_LABEL, METRIC_FRESHNESS_BUCKET_LABEL),
        implemented=True,
        description=(
            "Counts source-backed RFC-0108 render supportability observations using bounded "
            "state, reason, and freshness labels."
        ),
    ),
)

_RENDER_OPERATIONS_TOTAL = Counter(
    "lotus_render_operations_total",
    RENDER_METRIC_CONTRACTS[0].description,
    [METRIC_OPERATION_LABEL, METRIC_STATUS_LABEL, METRIC_FAILURE_CATEGORY_LABEL],
)
_RENDER_OPERATION_DURATION_SECONDS = Histogram(
    "lotus_render_operation_duration_seconds",
    RENDER_METRIC_CONTRACTS[1].description,
    [METRIC_OPERATION_LABEL, METRIC_STATUS_LABEL, METRIC_FAILURE_CATEGORY_LABEL],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
_RENDER_ARTIFACT_SIZE_BYTES = Histogram(
    "lotus_render_artifact_size_bytes",
    RENDER_METRIC_CONTRACTS[2].description,
    [METRIC_STATUS_LABEL],
    buckets=(1_024, 10_240, 102_400, 1_048_576, 5_242_880, 10_485_760),
)
_RENDER_SUPPORTABILITY_TOTAL = Counter(
    "lotus_render_supportability_total",
    RENDER_METRIC_CONTRACTS[3].description,
    [METRIC_STATE_LABEL, METRIC_REASON_LABEL, METRIC_FRESHNESS_BUCKET_LABEL],
)


def validate_render_metric_contracts() -> None:
    names = [contract.name for contract in RENDER_METRIC_CONTRACTS]
    if len(names) != len(set(names)):
        raise ValueError("duplicate_render_metric_name")
    for contract in RENDER_METRIC_CONTRACTS:
        _validate_labels(contract.labels)


def record_render_operation(
    *,
    operation: str,
    status: str,
    failure_category: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    operation_label = _implemented_operation(operation)
    status_label = _bounded_status(status)
    failure_label = _bounded_failure_category(failure_category)
    _RENDER_OPERATIONS_TOTAL.labels(
        operation=operation_label,
        status=status_label,
        failure_category=failure_label,
    ).inc()
    if duration_seconds is not None:
        _RENDER_OPERATION_DURATION_SECONDS.labels(
            operation=operation_label,
            status=status_label,
            failure_category=failure_label,
        ).observe(max(0.0, duration_seconds))


def record_render_artifact_size(*, status: str, size_bytes: int | None) -> None:
    if size_bytes is None:
        return
    _RENDER_ARTIFACT_SIZE_BYTES.labels(status=_bounded_status(status)).observe(max(0, size_bytes))


def record_render_supportability(
    *,
    state: str,
    reason: str,
    freshness_bucket: str,
) -> None:
    _RENDER_SUPPORTABILITY_TOTAL.labels(
        state=_bounded_supportability_state(state),
        reason=_bounded_supportability_reason(reason),
        freshness_bucket=_bounded_supportability_freshness_bucket(freshness_bucket),
    ).inc()


def _validate_labels(labels: Iterable[str]) -> None:
    label_set = set(labels)
    forbidden = label_set & FORBIDDEN_METRIC_LABELS
    if forbidden:
        raise ValueError(f"forbidden_render_metric_label:{sorted(forbidden)[0]}")
    unsupported = label_set - RENDER_METRIC_LABELS
    if unsupported:
        raise ValueError(f"unsupported_render_metric_label:{sorted(unsupported)[0]}")


def _implemented_operation(operation: str) -> str:
    if operation not in IMPLEMENTED_RENDER_OPERATIONS:
        raise ValueError(f"unsupported_render_metric_operation:{operation}")
    return operation


def _bounded_status(status: str) -> str:
    if status in RENDER_OPERATION_STATUSES:
        return status
    return "failed"


def _bounded_failure_category(failure_category: str | None) -> str:
    if not failure_category:
        return "none"
    normalized = failure_category.strip().lower().replace("-", "_")
    if not normalized:
        return "none"
    if len(normalized) > 80:
        return "other"
    if not all(character.isalnum() or character == "_" for character in normalized):
        return "other"
    return normalized


def _bounded_supportability_state(state: str) -> str:
    if state in RENDER_SUPPORTABILITY_STATES:
        return state
    return "unavailable"


def _bounded_supportability_reason(reason: str) -> str:
    if reason in RENDER_SUPPORTABILITY_REASONS:
        return reason
    return "runtime_configuration_unavailable"


def _bounded_supportability_freshness_bucket(freshness_bucket: str) -> str:
    if freshness_bucket in RENDER_SUPPORTABILITY_FRESHNESS_BUCKETS:
        return freshness_bucket
    return "unknown"
