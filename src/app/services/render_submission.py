from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter

from app.contracts.render_package import RenderPackage
from app.contracts.renders import (
    RenderArtifactMetadataResponse,
    RenderFailureCategory,
    RenderHandoffOwner,
    RenderJobDiagnosticsResponse,
    RenderJobStatusResponse,
    RenderRecoveryAction,
    RenderStaleState,
    RenderSubmitResponse,
)
from app.domain.templates.registry import TemplateCompatibilityError
from app.infrastructure.render_store import (
    RenderJobConflictError,
    RenderJobNotFoundError,
    RenderJobTransitionError,
    StoredRenderJob,
)
from app.observability.render_metrics import record_render_artifact_size, record_render_operation
from app.services.render_ports import (
    RenderEnginePort,
    RenderEngineTimeoutError,
    RenderJobStorePort,
)


class RenderPackageInvalidError(ValueError):
    pass


class RenderExecutionFailedError(RuntimeError):
    pass


class RenderSubmissionService:
    def __init__(
        self,
        *,
        render_store: RenderJobStorePort,
        render_engine: RenderEnginePort,
    ) -> None:
        self._render_store = render_store
        self._render_engine = render_engine

    def submit(self, render_package: RenderPackage) -> RenderSubmitResponse:
        started_at = perf_counter()
        package_hash = hashlib.sha256(
            json.dumps(
                render_package.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        runtime_metadata = self._render_engine.runtime_metadata
        try:
            create_result = self._render_store.create_or_get_with_outcome(
                render_job_id=render_package.render_job_id,
                report_job_id=render_package.report_job_id,
                render_package_version=render_package.render_package_version,
                package_hash=package_hash,
                snapshot_id=render_package.snapshot_id,
                lineage_refs=tuple(render_package.lineage_refs),
                disclosure_refs=tuple(render_package.disclosure_refs),
                requested_by=render_package.requested_by,
                package_correlation_id=render_package.correlation_id,
                package_trace_id=render_package.trace_id,
                report_type=render_package.report_type,
                template_id=render_package.template_id,
                template_version=render_package.template_version,
                output_format=render_package.output_format,
                runtime_engine=runtime_metadata.runtime_engine,
                runtime_engine_version=runtime_metadata.runtime_engine_version,
            )
        except RenderJobConflictError:
            record_render_operation(
                operation="render_submission",
                status="failed",
                failure_category="render_job_conflict",
                duration_seconds=perf_counter() - started_at,
            )
            raise
        existing = create_result.job
        if existing.status == "rendered":
            self._record_submit_metric(existing, started_at=started_at)
            return self._to_submit_response(existing, artifact_base64=None)
        if existing.status == "failed":
            self._record_submit_metric(existing, started_at=started_at)
            return self._to_submit_response(existing, artifact_base64=None)
        if not create_result.created:
            self._record_submit_metric(existing, started_at=started_at)
            return self._to_submit_response(existing, artifact_base64=None)

        self._render_store.mark_rendering(render_package.render_job_id)
        try:
            result = self._render_engine.render(render_package)
        except RenderEngineTimeoutError as exc:
            failure = self._mark_failed_or_current_truth(
                render_package.render_job_id,
                failure_category="timeout",
                failure_message=_support_safe_render_failure_message("timeout"),
            )
            self._record_submit_metric(failure, started_at=started_at)
            if failure.status != "failed":
                return self._to_submit_response(failure, artifact_base64=None)
            raise RenderExecutionFailedError(failure.failure_message or "render_failed") from exc
        except TemplateCompatibilityError as exc:
            failure = self._mark_failed_or_current_truth(
                render_package.render_job_id,
                failure_category="template_not_supported",
                failure_message=str(exc),
            )
            self._record_submit_metric(failure, started_at=started_at)
            if failure.status != "failed":
                return self._to_submit_response(failure, artifact_base64=None)
            raise RenderPackageInvalidError(
                failure.failure_message or "template_not_supported"
            ) from exc
        except ValueError as exc:
            failure = self._mark_failed_or_current_truth(
                render_package.render_job_id,
                failure_category="package_validation_failed",
                failure_message=str(exc),
            )
            self._record_submit_metric(failure, started_at=started_at)
            if failure.status != "failed":
                return self._to_submit_response(failure, artifact_base64=None)
            raise RenderPackageInvalidError(
                failure.failure_message or "package_validation_failed"
            ) from exc
        except RuntimeError as exc:
            failure_message = str(exc)
            failure_category: RenderFailureCategory = "template_render_failed"
            if "neither docker nor typst is installed" in failure_message.lower():
                failure_category = "engine_unavailable"
            safe_message = _support_safe_render_failure_message(failure_category)
            failure = self._mark_failed_or_current_truth(
                render_package.render_job_id,
                failure_category=failure_category,
                failure_message=safe_message,
            )
            self._record_submit_metric(failure, started_at=started_at)
            if failure.status != "failed":
                return self._to_submit_response(failure, artifact_base64=None)
            raise RenderExecutionFailedError(failure.failure_message or "render_failed") from exc

        try:
            stored = self._render_store.mark_rendered(render_package.render_job_id, result)
        except RenderJobTransitionError:
            stored = self._render_store.get(render_package.render_job_id)
        self._record_submit_metric(stored, started_at=started_at)
        if stored.status != "rendered":
            return self._to_submit_response(stored, artifact_base64=None)
        return self._to_submit_response(
            stored,
            artifact_base64=base64.b64encode(result.artifact_bytes).decode("ascii"),
        )

    def get_status(self, render_job_id: str) -> RenderJobStatusResponse:
        started_at = perf_counter()
        try:
            stored = self._render_store.get(render_job_id)
        except RenderJobNotFoundError:
            record_render_operation(
                operation="render_status_lookup",
                status="not_found",
                failure_category="render_job_not_found",
                duration_seconds=perf_counter() - started_at,
            )
            raise
        record_render_operation(
            operation="render_status_lookup",
            status=stored.status,
            failure_category=stored.failure_category,
            duration_seconds=perf_counter() - started_at,
        )
        return self._to_status_response(stored)

    def get_artifact_metadata(
        self,
        render_job_id: str,
    ) -> RenderArtifactMetadataResponse:
        started_at = perf_counter()
        try:
            stored = self._render_store.get(render_job_id)
        except RenderJobNotFoundError:
            record_render_operation(
                operation="artifact_metadata_lookup",
                status="not_found",
                failure_category="render_job_not_found",
                duration_seconds=perf_counter() - started_at,
            )
            raise
        if stored.status != "rendered":
            record_render_operation(
                operation="artifact_metadata_lookup",
                status="not_ready",
                failure_category=stored.failure_category or "render_artifact_not_ready",
                duration_seconds=perf_counter() - started_at,
            )
            raise ValueError("render_artifact_not_ready")
        assert stored.artifact_sha256 is not None
        assert stored.bounded_determinism_fingerprint is not None
        assert stored.mime_type is not None
        assert stored.output_size_bytes is not None
        assert stored.render_duration_ms is not None
        assert stored.determinism_mode is not None
        record_render_operation(
            operation="artifact_metadata_lookup",
            status=stored.status,
            failure_category=stored.failure_category,
            duration_seconds=perf_counter() - started_at,
        )
        record_render_artifact_size(status=stored.status, size_bytes=stored.output_size_bytes)
        return RenderArtifactMetadataResponse(
            render_job_id=stored.render_job_id,
            status=stored.status,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            determinism_mode=stored.determinism_mode,
        )

    def get_diagnostics(
        self,
        render_job_id: str,
        *,
        accepted_stale_seconds: int,
        rendering_stale_seconds: int,
    ) -> RenderJobDiagnosticsResponse:
        started_at = perf_counter()
        try:
            stored = self._render_store.get(render_job_id)
        except RenderJobNotFoundError:
            record_render_operation(
                operation="render_diagnostics_lookup",
                status="not_found",
                failure_category="render_job_not_found",
                duration_seconds=perf_counter() - started_at,
            )
            raise
        record_render_operation(
            operation="render_diagnostics_lookup",
            status=stored.status,
            failure_category=stored.failure_category,
            duration_seconds=perf_counter() - started_at,
        )
        return self._to_diagnostics_response(
            stored,
            accepted_stale_seconds=accepted_stale_seconds,
            rendering_stale_seconds=rendering_stale_seconds,
        )

    def _mark_failed_or_current_truth(
        self,
        render_job_id: str,
        *,
        failure_category: RenderFailureCategory,
        failure_message: str,
    ) -> StoredRenderJob:
        try:
            return self._render_store.mark_failed(
                render_job_id=render_job_id,
                failure_category=failure_category,
                failure_message=failure_message,
            )
        except RenderJobTransitionError:
            return self._render_store.get(render_job_id)

    @staticmethod
    def _to_submit_response(
        stored: StoredRenderJob,
        *,
        artifact_base64: str | None,
    ) -> RenderSubmitResponse:
        return RenderSubmitResponse(
            render_job_id=stored.render_job_id,
            report_job_id=stored.report_job_id,
            snapshot_id=stored.snapshot_id,
            lineage_refs=list(stored.lineage_refs),
            disclosure_refs=list(stored.disclosure_refs),
            requested_by=stored.requested_by,
            package_correlation_id=stored.package_correlation_id,
            package_trace_id=stored.package_trace_id,
            status=stored.status,
            failure_category=stored.failure_category,
            failure_message=stored.failure_message,
            template_id=stored.template_id,
            template_version=stored.template_version,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            runtime_engine=stored.runtime_engine,
            runtime_engine_version=stored.runtime_engine_version,
            determinism_mode=stored.determinism_mode,
            determinism_statement=stored.determinism_statement,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            completed_at=stored.completed_at,
            artifact_base64=artifact_base64,
        )

    @staticmethod
    def _to_status_response(stored: StoredRenderJob) -> RenderJobStatusResponse:
        return RenderJobStatusResponse(
            render_job_id=stored.render_job_id,
            report_job_id=stored.report_job_id,
            snapshot_id=stored.snapshot_id,
            lineage_refs=list(stored.lineage_refs),
            disclosure_refs=list(stored.disclosure_refs),
            requested_by=stored.requested_by,
            package_correlation_id=stored.package_correlation_id,
            package_trace_id=stored.package_trace_id,
            status=stored.status,
            failure_category=stored.failure_category,
            failure_message=stored.failure_message,
            template_id=stored.template_id,
            template_version=stored.template_version,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            runtime_engine=stored.runtime_engine,
            runtime_engine_version=stored.runtime_engine_version,
            determinism_mode=stored.determinism_mode,
            determinism_statement=stored.determinism_statement,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            completed_at=stored.completed_at,
        )

    @staticmethod
    def _to_diagnostics_response(
        stored: StoredRenderJob,
        *,
        accepted_stale_seconds: int,
        rendering_stale_seconds: int,
    ) -> RenderJobDiagnosticsResponse:
        age_seconds = _age_seconds(stored.updated_at)
        stale_threshold_seconds = _stale_threshold_seconds(
            status=stored.status,
            accepted_stale_seconds=accepted_stale_seconds,
            rendering_stale_seconds=rendering_stale_seconds,
        )
        stale_state: RenderStaleState = "not_applicable"
        if stale_threshold_seconds is not None:
            stale_state = "stale" if age_seconds >= stale_threshold_seconds else "fresh"
        retryable, recovery_action, handoff_owner, support_message = _diagnostic_recovery(
            status=stored.status,
            failure_category=stored.failure_category,
            stale_state=stale_state,
        )
        return RenderJobDiagnosticsResponse(
            render_job_id=stored.render_job_id,
            status=stored.status,
            failure_category=stored.failure_category,
            artifact_ready=stored.status == "rendered",
            stale_state=stale_state,
            age_seconds=age_seconds,
            stale_threshold_seconds=stale_threshold_seconds,
            retryable=retryable,
            recovery_action=recovery_action,
            handoff_owner=handoff_owner,
            support_message=support_message,
            snapshot_id=stored.snapshot_id,
            lineage_refs=list(stored.lineage_refs),
            template_id=stored.template_id,
            template_version=stored.template_version,
            output_format=stored.output_format,
            runtime_engine=stored.runtime_engine,
            runtime_engine_version=stored.runtime_engine_version,
            updated_at=stored.updated_at,
            completed_at=stored.completed_at,
        )

    @staticmethod
    def _record_submit_metric(stored: StoredRenderJob, *, started_at: float) -> None:
        record_render_operation(
            operation="render_submission",
            status=stored.status,
            failure_category=stored.failure_category,
            duration_seconds=perf_counter() - started_at,
        )
        record_render_artifact_size(status=stored.status, size_bytes=stored.output_size_bytes)


def _support_safe_render_failure_message(failure_category: RenderFailureCategory) -> str:
    if failure_category == "engine_unavailable":
        return "Render runtime is unavailable in the governed runtime envelope."
    if failure_category == "timeout":
        return "Render execution timed out in the governed runtime envelope."
    return "Render execution failed in the governed runtime envelope."


def _age_seconds(updated_at: datetime) -> int:
    elapsed = datetime.now(UTC) - updated_at.astimezone(UTC)
    return max(0, int(elapsed.total_seconds()))


def _stale_threshold_seconds(
    *,
    status: str,
    accepted_stale_seconds: int,
    rendering_stale_seconds: int,
) -> int | None:
    if status == "accepted":
        return accepted_stale_seconds
    if status == "rendering":
        return rendering_stale_seconds
    return None


def _diagnostic_recovery(
    *,
    status: str,
    failure_category: RenderFailureCategory | None,
    stale_state: str,
) -> tuple[bool, RenderRecoveryAction, RenderHandoffOwner, str]:
    if status == "rendered":
        return (
            False,
            "read_artifact_metadata",
            "lotus-render",
            "Render completed; use artifact metadata for deterministic proof.",
        )
    if status in {"accepted", "rendering"}:
        if stale_state == "stale":
            return (
                True,
                "resubmit_identical_package_or_escalate_runtime",
                "reporting-platform-on-call",
                (
                    "Render is stale; resubmit the identical package for idempotent recovery or "
                    "escalate runtime support if it remains non-terminal."
                ),
            )
        return (
            False,
            "wait_for_completion",
            "lotus-render",
            "Render is in progress inside the governed runtime envelope.",
        )
    if failure_category == "package_validation_failed":
        return (
            False,
            "fix_upstream_render_package",
            "lotus-report",
            "Render package validation failed; fix or replay the upstream report package.",
        )
    if failure_category == "template_not_supported":
        return (
            False,
            "fix_template_registry_or_package",
            "template-owner",
            "Template compatibility failed; align the package with the governed template registry.",
        )
    if failure_category in {"engine_unavailable", "timeout"}:
        return (
            True,
            "escalate_render_runtime",
            "reporting-platform-on-call",
            (
                "Render runtime failed; check runtime availability, timeout posture, and retry "
                "envelope."
            ),
        )
    if failure_category in {"template_render_failed", "artifact_validation_failed"}:
        return (
            True,
            "escalate_template_support",
            "reporting-platform-on-call",
            "Template or artifact generation failed inside the governed runtime envelope.",
        )
    return (
        True,
        "escalate_reporting_platform",
        "reporting-platform-on-call",
        "Render requires operator intervention inside the reporting platform support boundary.",
    )
