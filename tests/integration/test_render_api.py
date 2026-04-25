from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.services.render_submission import RenderExecutionFailedError

GOLDEN_ROOT = Path("tests/golden/portfolio-review/v1")


def _build_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
        )
    )
    return TestClient(app)


def test_submit_render_and_fetch_status_and_artifact_metadata(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")

    with _build_client(tmp_path) as client:
        submit = client.post(
            "/renders",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

        assert submit.status_code == 201
        submit_body = submit.json()
        assert submit_body["status"] == "rendered"
        assert submit_body["artifact_base64"]

        status_response = client.get(f"/renders/{submit_body['render_job_id']}")
        assert status_response.status_code == 200
        assert status_response.json()["artifact_sha256"] == submit_body["artifact_sha256"]

        artifact_response = client.get(f"/renders/{submit_body['render_job_id']}/artifact-metadata")
        assert artifact_response.status_code == 200
        assert (
            artifact_response.json()["bounded_determinism_fingerprint"]
            == submit_body["bounded_determinism_fingerprint"]
        )


def test_submit_render_is_idempotent_for_same_render_job(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")

    with _build_client(tmp_path) as client:
        first = client.post(
            "/renders",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        second = client.post(
            "/renders",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["render_job_id"] == first.json()["render_job_id"]
        assert second.json()["artifact_base64"] is None


def test_submit_render_rejects_conflicting_reuse_of_render_job_id(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    conflicting = payload.replace("Alex Tan", "Jordan Lee")

    with _build_client(tmp_path) as client:
        first = client.post(
            "/renders",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        second = client.post(
            "/renders",
            content=conflicting,
            headers={"Content-Type": "application/json"},
        )

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "render_job_conflict"


def test_submit_render_returns_validation_failure_for_template_mismatch(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    invalid = payload.replace('"template_version": "v1"', '"template_version": "v9"')

    with _build_client(tmp_path) as client:
        response = client.post(
            "/renders",
            content=invalid,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "render_package_invalid"


def test_artifact_metadata_requires_successful_render(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    invalid = payload.replace('"template_version": "v1"', '"template_version": "v9"')

    with _build_client(tmp_path) as client:
        response = client.post(
            "/renders",
            content=invalid,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

        status_response = client.get("/renders/rdr_golden_portfolio_review_v1")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"

        artifact_response = client.get("/renders/rdr_golden_portfolio_review_v1/artifact-metadata")
        assert artifact_response.status_code == 409
        assert artifact_response.json()["detail"]["code"] == "render_artifact_not_ready"


def test_render_status_returns_not_found_for_unknown_job(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/renders/rdr_missing")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "render_job_not_found"


def test_artifact_metadata_returns_not_found_for_unknown_job(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/renders/rdr_missing/artifact-metadata")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "render_job_not_found"


def test_submit_render_returns_bad_gateway_when_render_execution_fails(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")

    class _FailingRenderSubmissionService:
        def submit(self, _request_payload: object) -> object:
            raise RenderExecutionFailedError("runtime render failed")

    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
        )
    )

    with TestClient(app) as client:
        app.state.render_submission_service = _FailingRenderSubmissionService()
        response = client.post(
            "/renders",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "render_failed"


def test_artifact_metadata_reraises_unexpected_value_error(tmp_path: Path) -> None:
    class _UnexpectedArtifactMetadataService:
        def get_artifact_metadata(self, _render_job_id: str) -> object:
            raise ValueError("unexpected-artifact-error")

    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
        )
    )

    with TestClient(app) as client:
        app.state.render_submission_service = _UnexpectedArtifactMetadataService()
        with pytest.raises(ValueError, match="unexpected-artifact-error"):
            client.get("/renders/rdr_unexpected/artifact-metadata")
