"""End-to-end proof that the HTTP surface renders the banked golden documents.

`tests/e2e` previously issued only `GET /health` and `GET /metadata` while the docs
described it as "smoke coverage of the full submit-and-render path" (issue #109). This
drives every governed template through the real API and the real Typst runtime, and
checks the returned bytes against the fingerprint banked in the fixtures manifest -- an
oracle independent of the production function that computes it (issue #108).
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app

GOLDEN_PRODUCER_FIXTURES = Path("tests/golden/producer-fixtures.v1.json")


def _golden_fixtures() -> list[dict[str, Any]]:
    manifest: dict[str, Any] = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    fixtures: list[dict[str, Any]] = manifest["fixtures"]
    return fixtures


@pytest.mark.parametrize(
    "fixture",
    _golden_fixtures(),
    ids=lambda fixture: str(fixture["golden_sample_id"]),
)
def test_submit_renders_the_banked_document_end_to_end(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    payload = Path(fixture["package_path"]).read_text(encoding="utf-8")
    app = create_app(Settings(render_store_path=str(tmp_path / "render-store.sqlite3")))

    with TestClient(app) as client:
        submit = client.post(
            "/renders", content=payload, headers={"Content-Type": "application/json"}
        )

        assert submit.status_code == 201, submit.text
        body = submit.json()
        assert body["status"] == "rendered"

        artifact = base64.b64decode(body["artifact_base64"])
        assert artifact.startswith(b"%PDF")
        # The contract prefixes the digest with its algorithm.
        assert body["artifact_sha256"] == f"sha256:{hashlib.sha256(artifact).hexdigest()}"
        # The banked fingerprint is the independent oracle: only a render that reproduced
        # the governed document byte-for-byte (modulo timestamps and ids) can match it.
        assert body["bounded_determinism_fingerprint"] == fixture["bounded_determinism_fingerprint"]

        metadata = client.get(f"/renders/{body['render_job_id']}/artifact-metadata")
        assert metadata.status_code == 200
        assert metadata.json()["output_size_bytes"] == len(artifact)
