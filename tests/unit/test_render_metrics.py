import pytest

import app.observability.render_metrics as render_metrics
from app.observability.render_metrics import (
    FORBIDDEN_METRIC_LABELS,
    IMPLEMENTED_RENDER_OPERATIONS,
    RENDER_METRIC_CONTRACTS,
    RenderMetricContract,
    record_render_artifact_size,
    record_render_operation,
    record_render_supportability,
    validate_render_metric_contracts,
)


def test_render_metric_contracts_are_bounded_and_implementation_truthful() -> None:
    validate_render_metric_contracts()

    implemented_names = {
        contract.name for contract in RENDER_METRIC_CONTRACTS if contract.implemented
    }
    assert {
        "lotus_render_operations_total",
        "lotus_render_operation_duration_seconds",
        "lotus_render_artifact_size_bytes",
        "lotus_render_supportability_total",
    } <= implemented_names
    assert {
        "render_submission",
        "render_status_lookup",
        "artifact_metadata_lookup",
    } <= IMPLEMENTED_RENDER_OPERATIONS
    for contract in RENDER_METRIC_CONTRACTS:
        assert not (set(contract.labels) & FORBIDDEN_METRIC_LABELS)
        assert "render_job_id" not in contract.labels
        assert "report_job_id" not in contract.labels
        assert "correlation_id" not in contract.labels
        assert "trace_id" not in contract.labels
        assert "portfolio_id" not in contract.labels


def test_render_metric_contract_validation_rejects_duplicate_metric_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_contracts = RENDER_METRIC_CONTRACTS + (RENDER_METRIC_CONTRACTS[0],)
    monkeypatch.setattr(render_metrics, "RENDER_METRIC_CONTRACTS", duplicate_contracts)

    with pytest.raises(ValueError, match="duplicate_render_metric_name"):
        validate_render_metric_contracts()


def test_render_metric_contract_validation_rejects_forbidden_and_unsupported_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_label_contract = RenderMetricContract(
        name="lotus_render_invalid_forbidden_label_total",
        metric_type="counter",
        labels=("operation", "render_job_id"),
        implemented=True,
        description="invalid high-cardinality label",
    )
    monkeypatch.setattr(
        render_metrics,
        "RENDER_METRIC_CONTRACTS",
        (forbidden_label_contract,),
    )

    with pytest.raises(ValueError, match="forbidden_render_metric_label:render_job_id"):
        validate_render_metric_contracts()

    unsupported_label_contract = RenderMetricContract(
        name="lotus_render_invalid_unsupported_label_total",
        metric_type="counter",
        labels=("operation", "template_id"),
        implemented=True,
        description="invalid non-contract label",
    )
    monkeypatch.setattr(
        render_metrics,
        "RENDER_METRIC_CONTRACTS",
        (unsupported_label_contract,),
    )

    with pytest.raises(ValueError, match="unsupported_render_metric_label:template_id"):
        validate_render_metric_contracts()


def test_record_render_operation_rejects_unknown_operation() -> None:
    with pytest.raises(ValueError, match="unsupported_render_metric_operation"):
        record_render_operation(operation="rerender_command", status="failed")


def test_record_render_operation_bounds_status_failure_category_and_duration() -> None:
    record_render_operation(
        operation="render_submission",
        status="rendered",
        failure_category=None,
        duration_seconds=0.01,
    )
    record_render_operation(
        operation="render_status_lookup",
        status="not-a-contract-status",
        failure_category=" Template-Render-Failed ",
        duration_seconds=-1.0,
    )
    record_render_operation(
        operation="artifact_metadata_lookup",
        status="not_ready",
        failure_category="",
    )
    record_render_operation(
        operation="artifact_metadata_lookup",
        status="failed",
        failure_category="   ",
    )
    record_render_operation(
        operation="render_submission",
        status="failed",
        failure_category="render failed!",
    )
    record_render_operation(
        operation="render_submission",
        status="failed",
        failure_category="x" * 81,
    )


def test_record_render_artifact_size_clamps_counts_and_ignores_missing_size() -> None:
    record_render_artifact_size(status="rendered", size_bytes=2048)
    record_render_artifact_size(status="rendered", size_bytes=-1)
    record_render_artifact_size(status="not-a-contract-status", size_bytes=1)
    record_render_artifact_size(status="rendered", size_bytes=None)


def test_record_render_supportability_bounds_state_reason_and_freshness() -> None:
    record_render_supportability(
        state="ready",
        reason="render_supportability_ready",
        freshness_bucket="current",
    )
    record_render_supportability(
        state="not-a-contract-state",
        reason="not-a-contract-reason",
        freshness_bucket="not-a-contract-freshness",
    )


def test_record_render_supportability_sanitizes_labels_before_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    class _Counter:
        def labels(self, **labels: str) -> "_Counter":
            captured.update(labels)
            return self

        def inc(self) -> None:
            return None

    monkeypatch.setattr(render_metrics, "_RENDER_SUPPORTABILITY_TOTAL", _Counter())

    record_render_supportability(
        state="portfolio:PB_SG_GLOBAL_BAL_001",
        reason="client_name:private-bank-client",
        freshness_bucket="trace:1234567890abcdef1234567890abcdef",
    )

    assert captured == {
        "state": "unavailable",
        "reason": "runtime_configuration_unavailable",
        "freshness_bucket": "unknown",
    }
    assert "PB_SG_GLOBAL_BAL_001" not in captured.values()
    assert "client_name:private-bank-client" not in captured.values()
