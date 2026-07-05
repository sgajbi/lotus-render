import logging
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture

from app.core.settings import Settings
from app.main import create_app


def _build_client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    return TestClient(app)


def test_health_endpoints(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_correlation_and_trace_header_propagation(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-123", "X-Trace-Id": "trace-123"},
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-Id"] == "corr-123"
        assert response.headers["X-Trace-Id"] == "trace-123"
        assert "traceparent" not in response.headers


def test_valid_x_trace_id_emits_traceparent(tmp_path: Path) -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    with _build_client(tmp_path) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-123", "X-Trace-Id": trace_id},
        )
        assert response.status_code == 200
        assert response.headers["traceparent"] == f"00-{trace_id}-0000000000000001-01"


def test_traceparent_header_preferred_for_trace_propagation(tmp_path: Path) -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    with _build_client(tmp_path) as client:
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


def test_missing_trace_header_is_generated(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/health", headers={"X-Correlation-Id": "corr-generated"})
        assert response.status_code == 200
        assert response.headers["X-Trace-Id"]
        assert response.headers["traceparent"].startswith("00-")


def test_request_log_contains_correlation_and_trace(
    tmp_path: Path,
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="lotus_render.request")
    with _build_client(tmp_path) as client:
        response = client.get(
            "/health",
            headers={"X-Correlation-Id": "corr-log", "X-Trace-Id": "trace-log"},
        )
    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("correlation_id=corr-log" in message for message in messages)
    assert any("trace_id=trace-log" in message for message in messages)


def test_readiness_reports_draining_state(tmp_path: Path) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        app.state.container.is_draining = True
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "draining"


def test_readiness_reports_not_ready_when_render_store_is_unavailable(tmp_path: Path) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        app.state.container.render_store._db_path = tmp_path / "missing" / "store.sqlite3"
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


def test_metadata_endpoint_reports_foundation_posture(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
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
        assert payload["supportability"] == {
            "featureKey": "render.observability.render_supportability",
            "state": "ready",
            "reason": "render_supportability_ready",
            "freshnessBucket": "current",
            "deterministicOutputSupported": True,
            "runtimeEngine": "typst",
            "runtimeEngineVersion": "0.14.2",
            "defaultOutputFormat": "pdf",
            "supportedOutputFormats": ["pdf"],
            "renderStoreReady": True,
            "templateRegistryReady": True,
            "draining": False,
        }
