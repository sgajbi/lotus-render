from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoints() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
        assert response.status_code == 200
        assert response.headers["X-Correlation-Id"] == "corr-123"


def test_readiness_reports_draining_state() -> None:
    with TestClient(app) as client:
        app.state.is_draining = True
        try:
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["status"] == "draining"
        finally:
            app.state.is_draining = False


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
