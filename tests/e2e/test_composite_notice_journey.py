"""Registered v9/SQLite/reopen and captured fake handoff; no joined Archive claim."""

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.services.archive_handoff import StdlibArchiveTransport


def package() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / (
        "fixtures/composite-notice-v9/valid-full-render-package.json.gz"
    )
    return json.loads(gzip.decompress(path.read_bytes()))  # type: ignore[no-any-return]


def test_registered_native_replay_reopen_conflict_and_exact_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wire = package()
    calls: list[Any] = []

    def capture(self: Any, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
        calls.append((payload, headers))
        return 201, {"document_id": "controlled-fake-notice-document"}

    monkeypatch.setattr(StdlibArchiveTransport, "post_document", capture)
    settings = Settings(
        render_store_path=str(tmp_path / "notice.sqlite3"),
        archive_base_url="http://archive.invalid",
    )
    headers = {"X-Tenant-Id": wire["report_data"]["tenant_id"]}
    with TestClient(create_app(settings), headers=headers) as client:
        first = client.post("/renders", json=wire)
        assert first.status_code == 201, first.text
        body = first.json()
        assert body["status"] == "rendered"
        assert len(calls) == 1
        artifact = base64.b64decode(body["artifact_base64"])
        sent, sent_headers = calls[0]
        assert base64.b64decode(sent["content_base64"]) == artifact
        metadata = sent["metadata"]
        assert metadata["declared_artifact_sha256"] == hashlib.sha256(artifact).hexdigest()
        assert (
            metadata["composite_report_identity"]
            == (wire["render_context"]["archive"]["composite_report_identity"])
        )
        assert sent_headers["X-Tenant-Id"] == headers["X-Tenant-Id"]
        assert metadata["report_revision_id"] == wire["render_context"]["report_revision_id"]
        retry = client.post("/renders", json=wire)
        assert retry.status_code == 200 and len(calls) == 1
        assert retry.json()["artifact_sha256"] == body["artifact_sha256"]
        wire["report_data"]["notice_completeness"] = "COMPLETE"
        assert client.post("/renders", json=wire).status_code == 409
    with TestClient(create_app(settings), headers=headers) as client:
        url = f"/renders/{wire['render_job_id']}"
        assert client.get(url).json()["artifact_sha256"] == body["artifact_sha256"]
        assert client.get(url, headers={"X-Tenant-Id": "foreign"}).status_code == 404
    assert len(calls) == 1


def test_invalid_native_custody_never_writes_or_calls_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wire = package()
    identity = wire["render_context"]["archive"]["composite_report_identity"]
    identity["generations"]["before"]["source_document_id"] = "PRIVATE_INVALID_MARKER"
    calls = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        raise AssertionError("Invalid custody reached Archive")

    monkeypatch.setattr(StdlibArchiveTransport, "post_document", refuse)
    settings = Settings(
        render_store_path=str(tmp_path / "invalid.sqlite3"),
        archive_base_url="http://archive.invalid",
    )
    with TestClient(
        create_app(settings), headers={"X-Tenant-Id": wire["report_data"]["tenant_id"]}
    ) as client:
        response = client.post("/renders", json=wire)
        assert response.status_code == 422, response.text
        assert "PRIVATE_INVALID_MARKER" not in response.text
        status = client.get(f"/renders/{wire['render_job_id']}").json()
        assert status["status"] == "failed" and status["artifact_sha256"] is None
    assert not calls
