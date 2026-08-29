from pathlib import Path

import pytest

import app.observability.render_metrics as render_metrics
from app.observability.render_metrics import (
    FORBIDDEN_METRIC_LABELS,
    IMPLEMENTED_RENDER_OPERATIONS,
    RENDER_METRIC_CONTRACTS,
    RenderMetricContract,
    record_render_artifact_size,
    record_render_in_flight_summary,
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
        "lotus_render_in_flight_jobs",
        "lotus_render_oldest_in_flight_age_seconds",
    } <= implemented_names
    assert {
        "render_submission",
        "render_status_lookup",
        "render_diagnostics_lookup",
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
        # A label that is neither declared nor forbidden. It was `template_id` until
        # that became a declared label, which is the hazard with using a plausible
        # name as the sentinel for "not declared".
        labels=("operation", "never_a_declared_label"),
        implemented=True,
        description="invalid non-contract label",
    )
    monkeypatch.setattr(
        render_metrics,
        "RENDER_METRIC_CONTRACTS",
        (unsupported_label_contract,),
    )

    with pytest.raises(ValueError, match="unsupported_render_metric_label:never_a_declared_label"):
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


def test_record_render_in_flight_summary_sanitizes_labels_before_gauges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, str]] = []
    observed: list[float] = []

    class _Gauge:
        def labels(self, **labels: str) -> "_Gauge":
            captured.append(labels)
            return self

        def set(self, value: float) -> None:
            observed.append(value)

    monkeypatch.setattr(render_metrics, "_RENDER_IN_FLIGHT_JOBS", _Gauge())
    monkeypatch.setattr(render_metrics, "_RENDER_OLDEST_IN_FLIGHT_AGE_SECONDS", _Gauge())

    record_render_in_flight_summary(
        status="portfolio:PB_SG_GLOBAL_BAL_001",
        fresh_count=-1,
        stale_count=2,
        oldest_age_seconds=-20,
    )

    assert captured == [
        {"status": "rendering", "stale_state": "fresh"},
        {"status": "rendering", "stale_state": "stale"},
        {"status": "rendering"},
    ]
    assert observed == [0, 2, 0]


def test_a_degraded_document_is_distinguishable_from_a_complete_one() -> None:
    """Both render successfully and report `rendered`; only the measurement separates them.

    The golden degraded portfolio review returns 178 KB against the complete document's
    274 KB, with eleven of its content blocks reading "not available" -- and nothing in
    the response, the status or the metrics told them apart. Publishing a near-empty
    review to a client is a decision someone should be able to make; they could not see
    it to make it.
    """

    from app.contracts.render_package import RenderPackage
    from app.services.typst_contexts import (
        build_portfolio_review_context,
        count_empty_content_blocks,
    )

    def _blocks(path: str) -> int:
        package = RenderPackage.model_validate_json(Path(path).read_text(encoding="utf-8"))
        return count_empty_content_blocks(build_portfolio_review_context(package))

    complete = _blocks("tests/golden/portfolio-review/v1/render-package.json")
    degraded = _blocks("tests/golden/portfolio-review/v1/degraded/render-package.json")

    assert complete == 0, f"the complete golden should have no placeholders, found {complete}"
    assert degraded == 11, (
        f"the degraded golden renders {degraded} placeholder blocks, banked at 11. If the "
        "document genuinely changed, re-bank; if it did not, a content block silently "
        "stopped rendering."
    )


def test_the_empty_block_metric_is_a_governed_contract() -> None:
    """A metric nobody declared cannot be alerted on with any confidence."""

    declared = {metric.name for metric in RENDER_METRIC_CONTRACTS if metric.implemented}
    assert "lotus_render_empty_content_blocks" in declared
