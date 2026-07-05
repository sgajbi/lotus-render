import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture

from app.core.settings import Settings
from app.main import create_app
from app.services.render_runtime import RenderRuntimeAvailability


class _UnavailableRuntimeProbe:
    def check_available(self) -> RenderRuntimeAvailability:
        return RenderRuntimeAvailability(
            available=False,
            reason="runtime_configuration_unavailable",
        )


def _build_client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    return TestClient(app)


def test_health_endpoints(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_trusted_host_boundary_rejects_unknown_hosts(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/health", headers={"host": "evil.example"})

        assert response.status_code == 400


def test_trusted_host_boundary_allows_configured_service_host(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/health", headers={"host": "lotus-render"})

        assert response.status_code == 200


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


def test_readiness_reports_not_ready_when_render_runtime_is_unavailable(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        app.state.container.render_runtime_probe = _UnavailableRuntimeProbe()
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
            "runtimeAvailable": True,
            "draining": False,
        }
        assert payload["renderStoreInFlight"] == [
            {
                "status": "accepted",
                "count": 0,
                "staleCount": 0,
                "freshCount": 0,
                "oldestAgeSeconds": None,
                "staleThresholdSeconds": 300,
            },
            {
                "status": "rendering",
                "count": 0,
                "staleCount": 0,
                "freshCount": 0,
                "oldestAgeSeconds": None,
                "staleThresholdSeconds": 900,
            },
        ]


def test_metadata_endpoint_reports_stale_in_flight_render_store_posture(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
            stale_accepted_seconds=30,
            stale_rendering_seconds=60,
        )
    )
    with TestClient(app) as client:
        store = app.state.container.render_store
        store.create_or_get(
            render_job_id="rdr_stale_metadata",
            report_job_id="rjob_stale_metadata",
            render_package_version="render_package.v1",
            package_hash="hash-stale-metadata",
            report_type="portfolio_review",
            template_id="portfolio-review",
            template_version="v1",
            output_format="pdf",
            runtime_engine="typst",
            runtime_engine_version="0.14.2",
        )
        with sqlite3.connect(tmp_path / "render-store.sqlite3") as connection:
            connection.execute(
                "UPDATE render_job SET updated_at = ? WHERE render_job_id = ?",
                (
                    (datetime.now(UTC) - timedelta(seconds=31)).isoformat().replace("+00:00", "Z"),
                    "rdr_stale_metadata",
                ),
            )
            connection.commit()

        response = client.get("/metadata")
        metrics_response = client.get("/metrics")

        assert response.status_code == 200
        assert response.json()["renderStoreInFlight"][0] == {
            "status": "accepted",
            "count": 1,
            "staleCount": 1,
            "freshCount": 0,
            "oldestAgeSeconds": 31,
            "staleThresholdSeconds": 30,
        }
        assert (
            'lotus_render_in_flight_jobs{stale_state="stale",status="accepted"} 1.0'
            in metrics_response.text
        )
        assert "rdr_stale_metadata" not in metrics_response.text


def test_metadata_endpoint_reports_runtime_configuration_unavailable(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        app.state.container.render_runtime_probe = _UnavailableRuntimeProbe()
        response = client.get("/metadata")

        assert response.status_code == 200
        supportability = response.json()["supportability"]
        assert supportability["state"] == "unavailable"
        assert supportability["reason"] == "runtime_configuration_unavailable"
        assert supportability["deterministicOutputSupported"] is False
        assert supportability["runtimeAvailable"] is False
