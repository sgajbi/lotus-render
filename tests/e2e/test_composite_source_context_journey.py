"""Registered SQLite render/reopen journey; no joined Archive or live finance claim."""

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


@pytest.mark.parametrize("case", ["original", "corrected"])
def test_registered_v8_retained_render_reopens_and_refuses_foreign_tenant(
    tmp_path: Path, case: str
) -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "composite-source-context-v8"
    payload = json.loads((root / f"{case}.package.json").read_bytes())
    settings = Settings(
        render_store_path=str(tmp_path / "source-context.sqlite3"), archive_base_url=None
    )
    headers = {"X-Tenant-Id": payload["report_data"]["tenant_id"]}
    with TestClient(create_app(settings), headers=headers) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "rendered"
        artifact = base64.b64decode(body["artifact_base64"])
        assert body["artifact_sha256"] == "sha256:" + hashlib.sha256(artifact).hexdigest()
        retry = client.post("/renders", json=payload)
        assert retry.status_code == 200
        assert retry.json()["artifact_sha256"] == body["artifact_sha256"]
    with TestClient(create_app(settings), headers=headers) as client:
        url = f"/renders/{payload['render_job_id']}"
        assert client.get(url).json()["artifact_sha256"] == body["artifact_sha256"]
        assert client.get(url, headers={"X-Tenant-Id": "foreign"}).status_code == 404


def test_invalid_v8_does_not_create_artifact_or_call_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.archive_handoff import StdlibArchiveTransport

    root = Path(__file__).resolve().parents[1] / "fixtures" / "composite-source-context-v8"
    payload = json.loads((root / "original.package.json").read_bytes())
    table = next(t for t in payload["report_data"]["tables"] if t["table_id"] == "SinceInception")
    table["rows"][0]["cells"]["return"]["canonical_value"] = "PRIVATE_INVALID_MARKER"
    calls = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        raise AssertionError("Invalid package reached Archive")

    monkeypatch.setattr(StdlibArchiveTransport, "post_document", refuse)
    settings = Settings(
        render_store_path=str(tmp_path / "invalid.sqlite3"),
        archive_base_url="http://archive.invalid",
    )
    with TestClient(
        create_app(settings), headers={"X-Tenant-Id": payload["report_data"]["tenant_id"]}
    ) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 422, response.text
        assert "PRIVATE_INVALID_MARKER" not in response.text
        status = client.get(f"/renders/{payload['render_job_id']}").json()
        assert status["status"] == "failed"
        assert status["artifact_sha256"] is None
    assert not calls
