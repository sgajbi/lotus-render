from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.contracts.renders import RenderFailureCategory, RenderJobStatus
from app.core.settings import Settings
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.domain.templates.registry import TemplateCompatibilityError
from app.infrastructure.render_store import (
    CreateOrGetRenderJobResult,
    RenderJobTransitionError,
    RenderStore,
    StoredRenderJob,
)
from app.services.render_ports import RenderEngineTimeoutError, RenderRuntimeMetadata
from app.services.render_submission import (
    RenderExecutionFailedError,
    RenderPackageInvalidError,
    RenderSubmissionService,
)


def _render_package(**overrides: object) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
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


class _ExceptionTypstService:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        raise self._exc


def _stored_job(
    *,
    render_job_id: str = "rdr_current_truth",
    status: RenderJobStatus = "accepted",
    failure_category: RenderFailureCategory | None = None,
    failure_message: str | None = None,
    updated_at: datetime | None = None,
) -> StoredRenderJob:
    observed_at = updated_at or datetime.now(UTC)
    return StoredRenderJob(
        render_job_id=render_job_id,
        report_job_id="rjob_current_truth",
        render_package_version="render_package.v1",
        package_hash="hash-current-truth",
        snapshot_id="rsnap_current_truth",
        lineage_refs=("rlineage_current_truth",),
        disclosure_refs=("portfolio-review.standard-disclosures.v1",),
        requested_by="advisor.sg@example.com",
        package_correlation_id="corr-current-truth",
        package_trace_id="trace-current-truth",
        report_type="portfolio_review",
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
        status=status,
        failure_category=failure_category,
        failure_message=failure_message,
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
        determinism_mode=None,
        determinism_statement=None,
        bounded_determinism_fingerprint=None,
        artifact_sha256=None,
        mime_type=None,
        output_size_bytes=None,
        render_duration_ms=None,
        created_at=observed_at,
        updated_at=observed_at,
        completed_at=None,
    )


class _RacingRenderStore:
    def __init__(self, *, fail_mark_failed: bool = False, fail_mark_rendered: bool = False) -> None:
        self.current = _stored_job()
        self._fail_mark_failed = fail_mark_failed
        self._fail_mark_rendered = fail_mark_rendered

    def create_or_get_with_outcome(self, **_: object) -> CreateOrGetRenderJobResult:
        return CreateOrGetRenderJobResult(job=self.current, created=True)

    def mark_rendering(self, render_job_id: str) -> StoredRenderJob:
        self.current = _stored_job(render_job_id=render_job_id, status="rendering")
        return self.current

    def mark_rendered(self, render_job_id: str, _result: RenderResult) -> StoredRenderJob:
        if self._fail_mark_rendered:
            raise RenderJobTransitionError("rendering->rendered raced")
        self.current = _stored_job(render_job_id=render_job_id, status="rendered")
        return self.current

    def mark_failed(
        self,
        *,
        render_job_id: str,
        failure_category: RenderFailureCategory,
        failure_message: str,
    ) -> StoredRenderJob:
        if self._fail_mark_failed:
            raise RenderJobTransitionError("rendering->failed raced")
        self.current = _stored_job(
            render_job_id=render_job_id,
            status="failed",
            failure_category=failure_category,
            failure_message=failure_message,
        )
        return self.current

    def get(self, _render_job_id: str) -> StoredRenderJob:
        return self.current


class _StaticRenderStore:
    def __init__(self, job: StoredRenderJob) -> None:
        self._job = job

    def create_or_get_with_outcome(self, **_: object) -> CreateOrGetRenderJobResult:
        return CreateOrGetRenderJobResult(job=self._job, created=False)

    def mark_rendering(self, _render_job_id: str) -> StoredRenderJob:
        return self._job

    def mark_rendered(self, _render_job_id: str, _result: RenderResult) -> StoredRenderJob:
        return self._job

    def mark_failed(
        self,
        *,
        render_job_id: str,
        failure_category: RenderFailureCategory,
        failure_message: str,
    ) -> StoredRenderJob:
        return self._job

    def get(self, _render_job_id: str) -> StoredRenderJob:
        return self._job


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


@pytest.mark.parametrize(
    "exc",
    [
        RenderEngineTimeoutError("render_timeout"),
        TemplateCompatibilityError(reason="template_not_supported", message="template mismatch"),
        ValueError("package payload invalid"),
        RuntimeError("typst failed"),
    ],
)
def test_render_submission_returns_current_truth_when_failure_transition_races(
    exc: Exception,
) -> None:
    store = _RacingRenderStore(fail_mark_failed=True)
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _ExceptionTypstService(exc)),
    )

    response = service.submit(_render_package(render_job_id="rdr_failure_race"))

    assert response.status == "rendering"
    assert response.artifact_base64 is None


def test_render_submission_returns_current_truth_when_rendered_transition_races() -> None:
    store = _RacingRenderStore(fail_mark_rendered=True)
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _SuccessfulTypstService()),
    )

    response = service.submit(_render_package(render_job_id="rdr_rendered_race"))

    assert response.status == "rendering"
    assert response.artifact_base64 is None


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


def test_render_submission_diagnostics_reports_stale_in_progress_handoff(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    package = _render_package(render_job_id="rdr_stale")
    existing = store.create_or_get(
        render_job_id=package.render_job_id,
        report_job_id=package.report_job_id,
        render_package_version=package.render_package_version,
        package_hash=_package_hash(package),
        snapshot_id=package.snapshot_id,
        lineage_refs=tuple(package.lineage_refs),
        disclosure_refs=tuple(package.disclosure_refs),
        requested_by=package.requested_by,
        package_correlation_id=package.correlation_id,
        package_trace_id=package.trace_id,
        report_type=package.report_type,
        template_id=package.template_id,
        template_version=package.template_version,
        output_format=package.output_format,
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    store.mark_rendering(existing.render_job_id)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE render_job SET updated_at = ? WHERE render_job_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=901)).isoformat().replace("+00:00", "Z"),
                existing.render_job_id,
            ),
        )
        connection.commit()
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _SuccessfulTypstService()),
    )

    diagnostics = service.get_diagnostics(
        existing.render_job_id,
        accepted_stale_seconds=300,
        rendering_stale_seconds=900,
    )

    assert diagnostics.status == "rendering"
    assert diagnostics.stale_state == "stale"
    assert diagnostics.retryable is True
    assert diagnostics.recovery_action == "resubmit_identical_package_or_escalate_runtime"
    assert diagnostics.handoff_owner == "reporting-platform-on-call"
    assert diagnostics.snapshot_id == package.snapshot_id
    assert diagnostics.lineage_refs == package.lineage_refs


def test_render_submission_diagnostics_maps_failed_runtime_without_raw_message(
    tmp_path: Path,
) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, _TimeoutTypstService()),
    )
    with pytest.raises(RenderExecutionFailedError):
        service.submit(_render_package(render_job_id="rdr_diagnostics_timeout"))

    diagnostics = service.get_diagnostics(
        "rdr_diagnostics_timeout",
        accepted_stale_seconds=300,
        rendering_stale_seconds=900,
    )

    assert diagnostics.status == "failed"
    assert diagnostics.failure_category == "timeout"
    assert diagnostics.stale_state == "not_applicable"
    assert diagnostics.retryable is True
    assert diagnostics.recovery_action == "escalate_render_runtime"
    assert diagnostics.handoff_owner == "reporting-platform-on-call"
    assert "timed out" not in diagnostics.support_message.lower()
    assert not hasattr(diagnostics, "package_correlation_id")


@pytest.mark.parametrize(
    (
        "job",
        "expected_stale_state",
        "expected_retryable",
        "expected_recovery_action",
        "expected_handoff_owner",
    ),
    [
        (
            _stored_job(status="accepted"),
            "fresh",
            False,
            "wait_for_completion",
            "lotus-render",
        ),
        (
            _stored_job(
                status="failed",
                failure_category="package_validation_failed",
                failure_message="package invalid",
            ),
            "not_applicable",
            False,
            "fix_upstream_render_package",
            "lotus-report",
        ),
        (
            _stored_job(
                status="failed",
                failure_category="template_not_supported",
                failure_message="template mismatch",
            ),
            "not_applicable",
            False,
            "fix_template_registry_or_package",
            "template-owner",
        ),
        (
            _stored_job(
                status="failed",
                failure_category="template_render_failed",
                failure_message="template failed",
            ),
            "not_applicable",
            True,
            "escalate_template_support",
            "reporting-platform-on-call",
        ),
        (
            _stored_job(
                status="failed",
                failure_category="artifact_validation_failed",
                failure_message="artifact failed",
            ),
            "not_applicable",
            True,
            "escalate_template_support",
            "reporting-platform-on-call",
        ),
        (
            _stored_job(status="failed", failure_message="unknown failed"),
            "not_applicable",
            True,
            "escalate_reporting_platform",
            "reporting-platform-on-call",
        ),
    ],
)
def test_render_submission_diagnostics_maps_recovery_actions(
    job: StoredRenderJob,
    expected_stale_state: str,
    expected_retryable: bool,
    expected_recovery_action: str,
    expected_handoff_owner: str,
) -> None:
    service = RenderSubmissionService(
        render_store=cast(Any, _StaticRenderStore(job)),
        render_engine=cast(Any, _SuccessfulTypstService()),
    )

    diagnostics = service.get_diagnostics(
        job.render_job_id,
        accepted_stale_seconds=300,
        rendering_stale_seconds=900,
    )

    assert diagnostics.stale_state == expected_stale_state
    assert diagnostics.retryable is expected_retryable
    assert diagnostics.recovery_action == expected_recovery_action
    assert diagnostics.handoff_owner == expected_handoff_owner


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
