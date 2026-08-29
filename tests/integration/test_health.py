import logging
import re
import sqlite3
from contextlib import closing
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


_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-01$")


def _traceparent_span(header: str, expected_trace_id: str) -> bool:
    """The response advertises this service's own span within the caller's trace.

    The span id used to be the constant `0000000000000001` for every response of every
    service, which leaves a tracing backend no tree to build: each response claims to be
    the same span its caller should attach to. Asserted by shape rather than by value,
    because a correct span id is different every time.
    """
    match = _TRACEPARENT.fullmatch(header)
    assert match, f"not a W3C traceparent: {header!r}"
    assert match.group(1) == expected_trace_id, "the caller's trace must be preserved"
    assert match.group(2) != "0" * 16, "the all-zero span id is forbidden by the spec"
    assert match.group(2) != "0000000000000001", "the constant span id is back"
    return True


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


def test_trusted_host_boundary_allows_canonical_ingress_host(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/health/ready", headers={"host": "render.dev.lotus"})

        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_trusted_host_boundary_allows_report_docker_host_identity(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/metadata", headers={"host": "host.docker.internal"})

        assert response.status_code == 200
        assert response.json()["supportability"]["state"] == "ready"


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
        assert _traceparent_span(response.headers["traceparent"], trace_id)


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
        assert _traceparent_span(response.headers["traceparent"], trace_id)


def test_invalid_traceparent_falls_back_to_trace_header(tmp_path: Path) -> None:
    trace_id = "0123456789abcdef0123456789abcdef"
    with _build_client(tmp_path) as client:
        response = client.get(
            "/health",
            headers={
                "X-Correlation-Id": "corr-invalid-traceparent",
                "X-Trace-Id": trace_id,
                "traceparent": "00-not-a-valid-trace-id-0000000000000001-01",
            },
        )

        assert response.status_code == 200
        assert response.headers["X-Trace-Id"] == trace_id
        assert _traceparent_span(response.headers["traceparent"], trace_id)


def test_missing_trace_header_is_generated(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/health", headers={"X-Correlation-Id": "corr-generated"})
        assert response.status_code == 200
        assert response.headers["X-Trace-Id"]
        assert response.headers["traceparent"].startswith("00-")


def test_cors_middleware_is_enabled_when_origins_are_configured(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
            cors_allowed_origins=("https://lotus.example",),
        )
    )
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://lotus.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://lotus.example"


def test_malformed_content_length_is_rejected_without_echoing_body(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.post(
            "/renders",
            content=b"{}",
            headers={
                "Content-Length": "not-a-number",
                "X-Correlation-Id": "corr-bad-length",
                "X-Trace-Id": "trace-bad-length",
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_content_length"
        assert detail["correlation_id"] == "corr-bad-length"
        assert detail["trace_id"] == "trace-bad-length"


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
        with closing(sqlite3.connect(tmp_path / "render-store.sqlite3")) as connection, connection:
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


def test_each_response_advertises_a_span_of_its_own(tmp_path: Path) -> None:
    """Two requests in one trace are two spans, and must not claim to be the same one.

    This is the property the constant `0000000000000001` destroyed: with one span id for
    every response, a tracing backend cannot tell which call produced which, and the
    parent-child edges it builds the tree from all point at the same node.
    """

    trace_id = "0123456789abcdef0123456789abcdef"
    with _build_client(tmp_path) as client:
        headers = {"X-Correlation-Id": "corr-spans", "X-Trace-Id": trace_id}
        first = client.get("/health", headers=headers).headers["traceparent"]
        second = client.get("/health", headers=headers).headers["traceparent"]

    first_span = _TRACEPARENT.fullmatch(first).group(2)  # type: ignore[union-attr]
    second_span = _TRACEPARENT.fullmatch(second).group(2)  # type: ignore[union-attr]

    assert first_span != second_span, (
        "two requests reported the same span id, so their spans are indistinguishable "
        f"to any tracing backend: {first_span}"
    )
