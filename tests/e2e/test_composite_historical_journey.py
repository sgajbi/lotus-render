"""Registered v7 HTTP/SQLite lifecycle from Report r3 unit transport fixtures."""

import base64
import gzip
import json
from pathlib import Path
from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.services.archive_handoff import StdlibArchiveTransport
from app.services.composite_workbook import rendering


def _package() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        gzip.decompress(
            Path(
                "tests/fixtures/composite-historical-v7/v2-correction-3-published.package.json.gz"
            ).read_bytes()
        )
    )
    return data


def test_component_v7_submit_retry_restart_and_new_job_rerender(tmp_path: Path) -> None:
    payload = _package()
    settings = Settings(
        render_store_path=str(tmp_path / "historical.sqlite3"), archive_base_url=None
    )
    headers = {"X-Tenant-Id": payload["report_data"]["tenant_id"]}
    with TestClient(create_app(settings), headers=headers) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "rendered"
        assert body["runtime_engine"] == "xlsxwriter"
        assert base64.b64decode(body["artifact_base64"]).startswith(b"PK")
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
        # A separate render job consumes the same retained report dataset and custody
        # identity. Job identity changes the artifact; source financial facts do not appear.
        payload["render_job_id"] = "60000000-0000-4000-8000-000000000003"
        rerender = client.post("/renders", json=payload)
        assert rerender.status_code == 201, rerender.text
        assert rerender.json()["status"] == "rendered"


@pytest.mark.parametrize("change", ["lineage", "parent", "row", "financial", "custody"])
def test_invalid_v7_has_no_artifact_or_archive_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    payload = _package()
    data = payload["report_data"]
    if change == "lineage":
        data["source_months"][0]["lineage_receipts"].pop()
    elif change == "parent":
        data["source_months"][0]["parent_publication"]["sequence"] = 99
    elif change == "row":
        data["tables"][-1]["rows"].pop()
    elif change == "financial":
        data["report_facts"]["twr"] = "PRIVATE_INVALID_MARKER"
    else:
        payload["render_context"]["archive"]["composite_id"] = "foreign"
    calls: list[object] = []

    def refuse_transport(*args: Any, **kwargs: Any) -> NoReturn:
        calls.append((args, kwargs))
        raise AssertionError("invalid source correction reached Archive")

    monkeypatch.setattr(StdlibArchiveTransport, "post_document", refuse_transport)
    monkeypatch.setattr(rendering, "write_literal_workbook", refuse_transport)
    settings = Settings(
        render_store_path=str(tmp_path / "historical.sqlite3"),
        archive_base_url="http://archive.invalid",
    )
    with TestClient(create_app(settings), headers={"X-Tenant-Id": data["tenant_id"]}) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 422, response.text
        assert "PRIVATE_INVALID_MARKER" not in response.text
        status = client.get(f"/renders/{payload['render_job_id']}").json()
        assert status["status"] == "failed"
        assert status["failure_category"] == "package_validation_failed"
        assert status["artifact_sha256"] is None
        assert (
            client.get(f"/renders/{payload['render_job_id']}/artifact-metadata").status_code == 409
        )
    assert calls == []
