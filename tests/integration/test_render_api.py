from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.dependencies.container import get_render_submission_service
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

        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        metrics_text = metrics_response.text
        expected_render_metrics = [
            'lotus_render_operations_total{failure_category="none",'
            'operation="render_submission",status="rendered"}',
            'lotus_render_operations_total{failure_category="none",'
            'operation="render_status_lookup",status="rendered"}',
            'lotus_render_operations_total{failure_category="none",'
            'operation="artifact_metadata_lookup",status="rendered"}',
        ]
        for expected_metric in expected_render_metrics:
            assert expected_metric in metrics_text
        assert "lotus_render_artifact_size_bytes_bucket" in metrics_text
        assert submit_body["render_job_id"] not in metrics_text
        assert submit_body["report_job_id"] not in metrics_text
        assert "corr-golden-portfolio-review-v1" not in metrics_text


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
        app.dependency_overrides[get_render_submission_service] = lambda: (
            _FailingRenderSubmissionService()
        )
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
        app.dependency_overrides[get_render_submission_service] = lambda: (
            _UnexpectedArtifactMetadataService()
        )
        with pytest.raises(ValueError, match="unexpected-artifact-error"):
            client.get("/renders/rdr_unexpected/artifact-metadata")


def test_submit_render_framework_validation_is_support_safe(tmp_path: Path) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    invalid = payload.replace('"render_job_id": "rdr_golden_portfolio_review_v1",', "")

    with _build_client(tmp_path) as client:
        response = client.post(
            "/renders",
            content=invalid,
            headers={
                "Content-Type": "application/json",
                "X-Correlation-Id": "corr-validation",
                "X-Trace-Id": "trace-validation",
            },
        )

        assert response.status_code == 422
        body = response.json()
        assert body["detail"]["code"] == "render_package_invalid"
        assert "render_job_id" in body["detail"]["field_paths"]
        assert body["detail"]["correlation_id"] == "corr-validation"
        response_text = response.text
        assert "Alex Tan" not in response_text
        assert "summary_paragraph" not in response_text


def test_submit_render_rejects_oversized_request_body_without_payload_echo(
    tmp_path: Path,
) -> None:
    payload = (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    app = create_app(
        Settings(
            render_store_path=str(tmp_path / "render-store.sqlite3"),
            max_request_body_bytes=128,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/renders",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Correlation-Id": "corr-body-limit",
                "X-Trace-Id": "trace-body-limit",
            },
        )

        assert response.status_code == 413
        body = response.json()
        assert body["detail"]["code"] == "request_body_too_large"
        assert body["detail"]["correlation_id"] == "corr-body-limit"
        assert body["detail"]["trace_id"] == "trace-body-limit"
        assert "Alex Tan" not in response.text
        assert "summary_paragraph" not in response.text


def test_submit_render_extra_field_validation_is_support_safe(tmp_path: Path) -> None:
    payload = json.loads((GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8"))
    payload["snapshot_hash"] = "sha256:not-contract"

    with _build_client(tmp_path) as client:
        response = client.post(
            "/renders",
            json=payload,
            headers={"X-Correlation-Id": "corr-extra-field"},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["detail"]["code"] == "render_package_invalid"
        assert "snapshot_hash" in body["detail"]["field_paths"]
        assert body["detail"]["correlation_id"] == "corr-extra-field"
        assert "sha256:not-contract" not in response.text
        assert payload["report_data"]["client_name"] not in response.text
