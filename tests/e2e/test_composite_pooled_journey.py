"""Registered v5 HTTP/SQLite proof using frozen Report worker output."""

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.services.archive_handoff import StdlibArchiveTransport

FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures/composite-pooled-v5/producer-packages.json"
)
CASES = tuple(json.loads(FIXTURES.read_bytes())["packages"])


def _package(kind: str) -> dict[str, Any]:
    item = json.loads(FIXTURES.read_bytes())["packages"][kind]
    raw = gzip.decompress(base64.b64decode(item["gzip_base64"]))
    assert hashlib.sha256(raw).hexdigest() == item["sha256"]
    payload: dict[str, Any] = json.loads(raw)
    return payload


@pytest.mark.parametrize("kind", CASES)
def test_v5_registered_submission_idempotence_and_restored_store(tmp_path: Path, kind: str) -> None:
    payload = _package(kind)
    settings = Settings(render_store_path=str(tmp_path / "pooled.sqlite3"), archive_base_url=None)
    headers = {"X-Tenant-Id": payload["report_data"]["tenant_id"]}
    with TestClient(create_app(settings), headers=headers) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "rendered" and body["runtime_engine"] == "xlsxwriter"
        artifact = base64.b64decode(body["artifact_base64"])
        assert body["artifact_sha256"] == "sha256:" + hashlib.sha256(artifact).hexdigest()
        assert body["output_size_bytes"] == len(artifact)
        retry = client.post("/renders", json=payload)
        assert retry.status_code == 200
        assert retry.json()["artifact_base64"] is None
        assert retry.json()["artifact_sha256"] == body["artifact_sha256"]
    with TestClient(create_app(settings), headers=headers) as client:
        url = f"/renders/{payload['render_job_id']}"
        restored = client.get(url)
        assert restored.status_code == 200
        assert restored.json()["artifact_sha256"] == body["artifact_sha256"]
        assert client.get(url, headers={"X-Tenant-Id": "foreign"}).status_code == 404


@pytest.mark.parametrize("change", ["table", "digest", "scope", "attestation", "predecessor"])
def test_v5_invalid_evidence_creates_no_artifact_or_archive_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    payload = _package("corrected")
    data = payload["report_data"]
    if change == "table":
        cells = data["tables"][0]["rows"][0]["cells"]
        cells[next(iter(cells))]["canonical_value"] = "PRIVATE_INVALID_MARKER"
    elif change == "digest":
        data["source_response_digest"] = "sha256:" + "f" * 64
    elif change == "scope":
        payload["render_context"]["archive"]["composite_id"] = "foreign"
    elif change == "attestation":
        data["institutional_attestation"] = "APPROVED"
    else:
        data["predecessor_source_response"] = None
    calls: list[object] = []

    def refuse_transport(*args: Any, **kwargs: Any) -> NoReturn:
        calls.append((args, kwargs))
        raise AssertionError("invalid input reached Archive")

    monkeypatch.setattr(StdlibArchiveTransport, "post_document", refuse_transport)
    settings = Settings(
        render_store_path=str(tmp_path / "pooled.sqlite3"),
        archive_base_url="http://archive.invalid",
    )
    with TestClient(create_app(settings), headers={"X-Tenant-Id": data["tenant_id"]}) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 422, response.text
        assert "PRIVATE_INVALID_MARKER" not in response.text
        status = client.get(f"/renders/{payload['render_job_id']}").json()
        assert status["status"] == "failed" and status["artifact_sha256"] is None
        assert status["failure_category"] == "package_validation_failed"
        assert (
            client.get(f"/renders/{payload['render_job_id']}/artifact-metadata").status_code == 409
        )
    assert calls == []
