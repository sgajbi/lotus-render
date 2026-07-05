from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


def test_e2e_smoke(tmp_path: Path) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_metadata_endpoint(tmp_path: Path) -> None:
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))
    with TestClient(app) as client:
        response = client.get("/metadata")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"].startswith("lotus-")
        assert payload["supportedOutputFormats"] == ["pdf"]
        assert payload["renderAttemptStatuses"] == [
            "accepted",
            "validating_package",
            "rendering",
            "rendered",
            "failed",
        ]
