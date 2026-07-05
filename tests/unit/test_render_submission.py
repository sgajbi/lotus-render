from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.infrastructure.render_store import RenderStore
from app.services.render_ports import RenderEngineTimeoutError, RenderRuntimeMetadata
from app.services.render_submission import (
    RenderExecutionFailedError,
    RenderPackageInvalidError,
    RenderSubmissionService,
)

GOLDEN_PACKAGE_PATH = Path("tests/golden/portfolio-review/v1/render-package.json")


def _render_package(**overrides: object) -> RenderPackage:
    payload = json.loads(GOLDEN_PACKAGE_PATH.read_text(encoding="utf-8"))
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


def _settings() -> Settings:
    return Settings()


def _package_hash(render_package: RenderPackage) -> str:
    return hashlib.sha256(
        json.dumps(
            render_package.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class _SuccessfulTypstService:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        self.calls += 1
        return RenderResult(
            attempt=RenderAttempt(
                render_job_id="rdr_success",
                report_job_id="rjob_success",
                attempt_number=1,
                template_id="portfolio-review",
                template_version="v1",
                output_format="pdf",
            ),
            diagnostic=RenderDiagnostic(
                render_job_id="rdr_success",
                render_package_version="v1",
                template_id="portfolio-review",
                template_version="v1",
                runtime_engine="typst",
                runtime_engine_version="0.14.2",
                output_format="pdf",
                status="rendered",
                determinism_mode="bounded",
                determinism_statement="bounded determinism",
                bounded_determinism_fingerprint="typst-0.14.2:test",
                artifact_sha256="artifact",
                mime_type="application/pdf",
                output_size_bytes=10,
                render_duration_ms=321,
            ),
            artifact_bytes=b"%PDF-1.7\n%",
        )


class _ValueErrorTypstService:
    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        raise ValueError("package payload invalid")


class _RuntimeErrorTypstService:
    def __init__(self, message: str) -> None:
        self._message = message

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        raise RuntimeError(self._message)


class _TimeoutTypstService:
    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        raise RenderEngineTimeoutError("render_timeout")


def test_render_submission_returns_existing_failed_job_without_retrying(tmp_path: Path) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    package = _render_package()
    existing = store.create_or_get(
        render_job_id=package.render_job_id,
        report_job_id=package.report_job_id,
        render_package_version=package.render_package_version,
        package_hash=_package_hash(package),
        report_type=package.report_type,
        template_id=package.template_id,
        template_version=package.template_version,
        output_format=package.output_format,
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    store.mark_failed(
        render_job_id=existing.render_job_id,
        failure_category="template_render_failed",
        failure_message="prior render failed",
    )

    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _SuccessfulTypstService()),
    )

    response = service.submit(package)

    assert response.status == "failed"
    assert response.failure_category == "template_render_failed"
    assert response.artifact_base64 is None


def test_render_submission_marks_failed_for_package_value_error(tmp_path: Path) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _ValueErrorTypstService()),
    )

    with pytest.raises(RenderPackageInvalidError, match="package payload invalid"):
        service.submit(_render_package(render_job_id="rdr_value_error"))

    stored = store.get("rdr_value_error")
    assert stored.status == "failed"
    assert stored.failure_category == "package_validation_failed"
    assert stored.failure_message == "package payload invalid"


def test_render_submission_marks_engine_unavailable_for_runtime_dependency_failure(
    tmp_path: Path,
) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(
            Any,
            _RuntimeErrorTypstService(
                "Neither Docker nor Typst is installed in the current runtime"
            ),
        ),
    )

    with pytest.raises(RenderExecutionFailedError, match="Render runtime is unavailable"):
        service.submit(_render_package(render_job_id="rdr_engine_unavailable"))

    stored = store.get("rdr_engine_unavailable")
    assert stored.status == "failed"
    assert stored.failure_category == "engine_unavailable"
    assert (
        stored.failure_message == "Render runtime is unavailable in the governed runtime envelope."
    )


def test_render_submission_marks_failed_for_render_timeout(tmp_path: Path) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _TimeoutTypstService()),
    )

    with pytest.raises(RenderExecutionFailedError, match="timed out"):
        service.submit(_render_package(render_job_id="rdr_timeout"))

    stored = store.get("rdr_timeout")
    assert stored.status == "failed"
    assert stored.failure_category == "timeout"
    assert stored.failure_message == "Render execution timed out in the governed runtime envelope."


def test_render_submission_returns_existing_in_progress_job_without_retrying(
    tmp_path: Path,
) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    package = _render_package(render_job_id="rdr_in_progress")
    existing = store.create_or_get(
        render_job_id=package.render_job_id,
        report_job_id=package.report_job_id,
        render_package_version=package.render_package_version,
        package_hash=_package_hash(package),
        report_type=package.report_type,
        template_id=package.template_id,
        template_version=package.template_version,
        output_format=package.output_format,
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    store.mark_rendering(existing.render_job_id)
    renderer = _SuccessfulTypstService()
    service = RenderSubmissionService(render_store=store, render_engine=renderer)

    response = service.submit(package)

    assert response.status == "rendering"
    assert response.artifact_base64 is None
    assert renderer.calls == 0


def test_render_submission_sanitizes_runtime_diagnostics_before_persistence(
    tmp_path: Path,
) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        render_store=store,
        render_engine=_RuntimeErrorTypstService(
            "typst failed near CLIENT_SENTINEL_ALICE_PRIVATE_NOTE trace-golden"
        ),
    )

    with pytest.raises(RenderExecutionFailedError, match="governed runtime envelope"):
        service.submit(_render_package(render_job_id="rdr_sensitive_failure"))

    stored = store.get("rdr_sensitive_failure")
    assert stored.status == "failed"
    assert stored.failure_category == "template_render_failed"
    assert stored.failure_message == "Render execution failed in the governed runtime envelope."
    assert "CLIENT_SENTINEL" not in (stored.failure_message or "")
