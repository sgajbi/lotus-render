from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
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
    RenderJobNotFoundError,
    RenderJobTransitionError,
    RenderStore,
)
from app.infrastructure.render_store_rows import StoredRenderJob
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderEngineTimeoutError, RenderRuntimeMetadata
from app.services.render_submission import (
    RenderCapacityExhaustedError,
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


class _UnexpectedErrorTypstService:
    """Raises an exception outside the handled set (decimal.InvalidOperation is an
    ArithmeticError, not a ValueError/RuntimeError) to exercise the fail-closed path."""

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        settings = _settings()
        return RenderRuntimeMetadata(
            runtime_engine=settings.runtime_engine,
            runtime_engine_version=settings.runtime_engine_version,
        )

    def render(self, _render_package: RenderPackage) -> RenderResult:
        from decimal import InvalidOperation

        raise InvalidOperation("comparison with NaN")


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
        template_digest=None,
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

    def claim_for_rendering(
        self, render_job_id: str, *, rendering_stale_seconds: int
    ) -> StoredRenderJob | None:
        return self.mark_rendering(render_job_id)

    def record_archive_outcome(
        self,
        render_job_id: str,
        *,
        archive_state: str,
        archive_document_id: str | None,
        archive_request_id: str | None,
        archive_detail: str | None,
    ) -> StoredRenderJob:
        raise AssertionError("no archive handoff is configured in these tests")

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

    def claim_for_rendering(
        self, _render_job_id: str, *, rendering_stale_seconds: int
    ) -> StoredRenderJob | None:
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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


def test_render_submission_fail_closes_on_unexpected_exception(tmp_path: Path) -> None:
    """No exception may leave the job at 'rendering'; an unexpected error fails it closed."""

    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
        render_store=store,
        render_engine=cast(Any, _UnexpectedErrorTypstService()),
    )

    with pytest.raises(RenderExecutionFailedError):
        service.submit(_render_package(render_job_id="rdr_unexpected"))

    stored = store.get("rdr_unexpected")
    assert stored.status == "failed"
    assert stored.failure_category == "unexpected_render_error"
    assert stored.failure_message == "Render execution failed in the governed runtime envelope."


def test_render_submission_marks_failed_for_render_timeout(tmp_path: Path) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
        render_store=store,
        render_engine=cast(Any, _ExceptionTypstService(exc)),
    )

    response = service.submit(_render_package(render_job_id="rdr_failure_race"))

    assert response.status == "rendering"
    assert response.artifact_base64 is None


def test_render_submission_returns_current_truth_when_rendered_transition_races() -> None:
    store = _RacingRenderStore(fail_mark_rendered=True)
    service = RenderSubmissionService(
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
    service = RenderSubmissionService(
        render_store=store,
        render_engine=renderer,
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
    )

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
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(
            "UPDATE render_job SET updated_at = ? WHERE render_job_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=901)).isoformat().replace("+00:00", "Z"),
                existing.render_job_id,
            ),
        )
        connection.commit()
    service = RenderSubmissionService(
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
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


def _seed_job(store: RenderStore, package: RenderPackage) -> StoredRenderJob:
    return store.create_or_get(
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


def _age_job(db_path: Path, render_job_id: str, *, seconds: int) -> None:
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(
            "UPDATE render_job SET updated_at = ? WHERE render_job_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z"),
                render_job_id,
            ),
        )


def test_resubmitting_a_stale_rendering_job_actually_re_renders_it(tmp_path: Path) -> None:
    """The documented recovery action must do something.

    A worker that died mid-render leaves the row at 'rendering'. Resubmission used to
    echo that status and never re-execute, so the runbook's
    'resubmit_identical_package_or_escalate_runtime' was a no-op and the only way out was
    editing SQLite by hand (issue #105).
    """

    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    package = _render_package(render_job_id="rdr_stale_recoverable")
    existing = _seed_job(store, package)
    store.mark_rendering(existing.render_job_id)
    _age_job(db_path, existing.render_job_id, seconds=_settings().stale_rendering_seconds + 1)

    renderer = _SuccessfulTypstService()
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, renderer),
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
    )

    response = service.submit(package)

    assert renderer.calls == 1, "a stale abandoned job must be re-rendered, not echoed"
    assert response.status == "rendered"
    assert store.get(existing.render_job_id).status == "rendered"


def test_resubmitting_a_live_rendering_job_does_not_render_twice(tmp_path: Path) -> None:
    """Recovery must not become a way to double-render a job that is genuinely running."""

    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    package = _render_package(render_job_id="rdr_live_rendering")
    existing = _seed_job(store, package)
    store.mark_rendering(existing.render_job_id)

    renderer = _SuccessfulTypstService()
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, renderer),
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(_settings().render_execution_concurrency_limit),
    )

    response = service.submit(package)

    assert renderer.calls == 0
    assert response.status == "rendering"
    assert response.artifact_base64 is None


def test_only_one_caller_can_claim_a_stale_job(tmp_path: Path) -> None:
    """The claim is a single conditional UPDATE, so concurrent recoveries cannot both win."""

    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    package = _render_package(render_job_id="rdr_contended")
    existing = _seed_job(store, package)
    store.mark_rendering(existing.render_job_id)
    _age_job(db_path, existing.render_job_id, seconds=_settings().stale_rendering_seconds + 1)

    stale_seconds = _settings().stale_rendering_seconds
    first = store.claim_for_rendering(existing.render_job_id, rendering_stale_seconds=stale_seconds)
    second = store.claim_for_rendering(
        existing.render_job_id, rendering_stale_seconds=stale_seconds
    )

    assert first is not None, "the stale job must be claimable once"
    assert first.status == "rendering"
    assert second is None, "a job just claimed is fresh again and must not be claimable"


def test_claiming_an_unknown_job_is_reported_as_missing(tmp_path: Path) -> None:
    store = RenderStore(tmp_path / "render-store.sqlite3")

    with pytest.raises(RenderJobNotFoundError):
        store.claim_for_rendering("rdr_absent", rendering_stale_seconds=900)


def test_a_replay_does_not_consume_an_execution_slot(tmp_path: Path) -> None:
    """A submission that renders nothing must not exhaust capacity.

    The slot used to be held around the whole submit, including the short-circuit for an
    already-terminal job, so a caller retry storm against one finished render could 429
    genuine work (issue #115).
    """

    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    package = _render_package(render_job_id="rdr_replay_capacity")
    limiter = RenderExecutionLimiter(1)
    renderer = _SuccessfulTypstService()
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, renderer),
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=limiter,
    )

    first = service.submit(package)
    assert first.status == "rendered"
    assert renderer.calls == 1

    # Occupy the only slot, then replay the finished job: it must still answer.
    assert limiter.acquire() is True
    try:
        replay = service.submit(package)
    finally:
        limiter.release()

    assert replay.status == "rendered", "a replay was rejected for lack of capacity"
    assert renderer.calls == 1, "the replay re-rendered instead of echoing the stored truth"


def test_a_render_that_needs_a_slot_is_rejected_when_capacity_is_gone(tmp_path: Path) -> None:
    """Capacity still bounds real work, and the rejection leaves a recoverable job.

    The rejection happens before the claim, so the row stays 'accepted' -- which is always
    claimable, so the next submission simply renders it.
    """

    store = RenderStore(tmp_path / "render-store.sqlite3")
    package = _render_package(render_job_id="rdr_capacity_gone")
    limiter = RenderExecutionLimiter(1)
    renderer = _SuccessfulTypstService()
    service = RenderSubmissionService(
        render_store=store,
        render_engine=cast(Any, renderer),
        rendering_stale_seconds=_settings().stale_rendering_seconds,
        execution_limiter=limiter,
    )

    assert limiter.acquire() is True
    try:
        with pytest.raises(RenderCapacityExhaustedError):
            service.submit(package)
    finally:
        limiter.release()

    assert store.get(package.render_job_id).status == "accepted", (
        "a capacity rejection left the job somewhere other than 'accepted'"
    )

    recovered = service.submit(package)

    assert recovered.status == "rendered", "the rejected job could not be rendered afterwards"
    assert renderer.calls == 1
