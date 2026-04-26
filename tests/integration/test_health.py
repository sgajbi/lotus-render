import logging

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture

from app.main import app


def test_health_endpoints() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_correlation_and_trace_header_propagation() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-123", "X-Trace-Id": "trace-123"},
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-Id"] == "corr-123"
        assert response.headers["X-Trace-Id"] == "trace-123"
        assert "traceparent" not in response.headers


def test_valid_x_trace_id_emits_traceparent() -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-123", "X-Trace-Id": trace_id},
        )
        assert response.status_code == 200
        assert response.headers["traceparent"] == f"00-{trace_id}-0000000000000001-01"


def test_traceparent_header_preferred_for_trace_propagation() -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={
                "X-Correlation-Id": "corr-456",
                "X-Trace-Id": "trace-ignored",
                "traceparent": f"00-{trace_id}-0000000000000001-01",
            },
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-Id"] == "corr-456"
        assert response.headers["X-Trace-Id"] == trace_id
        assert response.headers["traceparent"] == f"00-{trace_id}-0000000000000001-01"


def test_missing_trace_header_is_generated() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-Id": "corr-generated"})
        assert response.status_code == 200
        assert response.headers["X-Trace-Id"]
        assert response.headers["traceparent"].startswith("00-")


def test_request_log_contains_correlation_and_trace(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="lotus_render.request")
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-log", "X-Trace-Id": "trace-log"},
        )
    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("correlation_id=corr-log" in message for message in messages)
    assert any("trace_id=trace-log" in message for message in messages)


def test_readiness_reports_draining_state() -> None:
    with TestClient(app) as client:
        app.state.is_draining = True
        try:
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["status"] == "draining"
        finally:
            app.state.is_draining = False


def test_readiness_reports_not_ready_when_render_store_is_unavailable() -> None:
    with TestClient(app) as client:
        original_store = app.state.render_store
        del app.state.render_store
        try:
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["status"] == "not_ready"
        finally:
            app.state.render_store = original_store


def test_metadata_endpoint_reports_foundation_posture() -> None:
    with TestClient(app) as client:
        response = client.get("/metadata")

        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "lotus-render"
        assert payload["runtimeEngine"] == "typst"
        assert payload["defaultOutputFormat"] == "pdf"
        assert payload["renderAttemptStatuses"] == [
            "accepted",
            "validating_package",
            "rendering",
            "rendered",
            "failed",
        ]
