from fastapi.testclient import TestClient

from app.main import app


def test_e2e_smoke() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_metadata_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/metadata")
        assert response.status_code == 200
        assert response.json()["service"].startswith("lotus-")
        assert response.json()["supportedOutputFormats"] == ["pdf"]
