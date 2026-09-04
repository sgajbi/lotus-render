from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.contracts.render_evidence import (
    RenderArtifactMetadataResponse,
    RenderJobDiagnosticsResponse,
)
from app.contracts.render_package import RenderPackage
from app.contracts.renders import (
    RenderFailureCategory,
    RenderJobStatusResponse,
    RenderStaleState,
    RenderSubmitResponse,
)
from app.domain.rendering.models import RenderResult
from app.domain.templates.registry import TemplateCompatibilityError
from app.infrastructure.render_store import (
    RenderJobConflictError,
    RenderJobNotFoundError,
    RenderJobTransitionError,
)
from app.infrastructure.render_store_rows import StoredRenderJob
from app.observability.render_log import log_render_accepted, log_render_failed
from app.observability.render_metrics import record_render_artifact_size, record_render_operation
from app.services.archive_handoff import ArchiveHandoff, hand_off_and_record
from app.services.render_envelope import envelope_refusal
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import (
    RenderCompileFailedError,
    RenderEnginePort,
    RenderEngineTimeoutError,
    RenderJobStorePort,
)
from app.services.render_recovery import diagnostic_recovery
from app.services.section_selection import section_selection_refusal


class RenderPackageInvalidError(ValueError):
    pass


class RenderExecutionFailedError(RuntimeError):
    pass


class RenderCapacityExhaustedError(RuntimeError):
    """No execution slot was free for a render that actually needed one."""


class RenderSubmissionService:
    def __init__(
        self,
        *,
        render_store: RenderJobStorePort,
        render_engine: RenderEnginePort,
        rendering_stale_seconds: int,
        execution_limiter: RenderExecutionLimiter,
        archive_handoff: ArchiveHandoff | None = None,
    ) -> None:
        self._render_store = render_store
        self._render_engine = render_engine
        # How long a job may sit at 'rendering' before a resubmission is allowed to take it
        # over. Recovery policy, not a per-request choice: it must be the same window the
        # diagnostics surface calls stale, or operators would be told to resubmit a job the
        # service still refuses to re-render.
        self._rendering_stale_seconds = rendering_stale_seconds
        # Held only around work that actually renders. Acquiring it around the whole
        # submit meant an idempotent replay - which does no rendering at all - could
        # exhaust capacity and 429 a genuine render (issue #115).
        self._execution_limiter = execution_limiter
        # None when this deployment has no Archive; jobs then carry a null archive
        # state, which the contract defines as "no handoff applies" (issue #120).
        self._archive_handoff = archive_handoff

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
        log_render_accepted(
            render_job_id=render_package.render_job_id,
            template_id=render_package.template_id,
            template_version=render_package.template_version,
            package_correlation_id=render_package.correlation_id,
            package_trace_id=render_package.trace_id,
        )
        if existing.status in ("rendered", "failed"):
            self._record_submit_metric(existing, started_at=started_at)
            return self._to_submit_response(existing, artifact_base64=None)
        return self._execute_render(render_package, started_at=started_at, current=existing)

    def _execute_render(
        self, render_package: RenderPackage, *, started_at: float, current: StoredRenderJob
    ) -> RenderSubmitResponse:
        """Claim the job and render it, or report the truth if it cannot be claimed.

        Claiming, rather than short-circuiting on "the row already existed", is what makes
        the documented recovery action real: a job whose worker died sits at 'rendering'
        forever and is taken over here once it goes stale (issue #105). A job someone is
        genuinely still rendering is not claimable, and its current truth is returned.

        The claim and the fail-closed handlers below live in the same method deliberately:
        the transition to 'rendering' and the guarantee that a terminal state is reached
        are one invariant, and splitting them leaves a window that strands the job (#104).

        The execution slot is taken *before* the claim, so a capacity rejection leaves the
        row at 'accepted' rather than 'rendering'. That is safe because an 'accepted' job
        is always claimable, so the next submission simply renders it (issue #115); it was
        not safe before #105, when a non-terminal row could not be re-executed at all.
        """
        # Refused before the slot, because the point of refusing is not to spend one. A
        # document over the envelope holds one of two slots for the whole compile timeout
        # and then fails, and the caller learns nothing they could not have been told at
        # admission (#168).
        refusal = envelope_refusal(render_package.report_data)
        if refusal is not None:
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="resource_limit_exceeded",
                failure_message=refusal,
                error_type=RenderPackageInvalidError,
                fallback_message="resource_limit_exceeded",
                cause=ValueError(refusal),
                started_at=started_at,
            )
        # An explicit section selection that cannot be honoured exactly refuses here
        # too: the same selection refuses identically on retry, and honouring part of
        # it -- or widening it to the default -- expands caller intent.
        selection_refusal = section_selection_refusal(render_package)
        if selection_refusal is not None:
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="package_validation_failed",
                failure_message=selection_refusal,
                error_type=RenderPackageInvalidError,
                fallback_message="section_selection_invalid",
                cause=ValueError(selection_refusal),
                started_at=started_at,
            )
        if not self._execution_limiter.acquire():
            raise RenderCapacityExhaustedError("render_execution_capacity_exhausted")
        try:
            return self._claim_and_render(render_package, started_at=started_at, current=current)
        finally:
            self._execution_limiter.release()

    def _claim_and_render(
        self, render_package: RenderPackage, *, started_at: float, current: StoredRenderJob
    ) -> RenderSubmitResponse:
        claimed = self._render_store.claim_for_rendering(
            render_package.render_job_id,
            rendering_stale_seconds=self._rendering_stale_seconds,
        )
        if claimed is None:
            self._record_submit_metric(current, started_at=started_at)
            return self._to_submit_response(current, artifact_base64=None)
        try:
            result = self._render_engine.render(render_package)
        except RenderEngineTimeoutError as exc:
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="timeout",
                failure_message=_support_safe_render_failure_message("timeout"),
                error_type=RenderExecutionFailedError,
                fallback_message="render_failed",
                cause=exc,
                started_at=started_at,
            )
        except TemplateCompatibilityError as exc:
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="template_not_supported",
                failure_message=str(exc),
                error_type=RenderPackageInvalidError,
                fallback_message="template_not_supported",
                cause=exc,
                started_at=started_at,
            )
        except ValueError as exc:
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="package_validation_failed",
                failure_message=str(exc),
                error_type=RenderPackageInvalidError,
                fallback_message="package_validation_failed",
                cause=exc,
                started_at=started_at,
            )
        except Exception as exc:
            # Fail-closed: RuntimeError and every other unexpected error (ArithmeticError
            # from malformed numerics, OSError, OverflowError, sqlite failures, ...) must
            # move the job to 'failed'. Nothing may leave it at 'rendering': a stranded job
            # is only recoverable once it goes stale and a resubmission reclaims it (#105).
            failure_category = _unexpected_failure_category(exc)
            return self._fail_submit(
                render_package.render_job_id,
                failure_category=failure_category,
                failure_message=_support_safe_render_failure_message(failure_category),
                error_type=RenderExecutionFailedError,
                fallback_message="render_failed",
                cause=exc,
                started_at=started_at,
            )

        return self._record_render_result(render_package, result, started_at=started_at)

    def _record_render_result(
        self, render_package: RenderPackage, result: RenderResult, *, started_at: float
    ) -> RenderSubmitResponse:
        """Persist a successful render, or fail the job closed if persisting it fails."""
        try:
            stored = self._render_store.mark_rendered(render_package.render_job_id, result)
        except RenderJobTransitionError:
            stored = self._render_store.get(render_package.render_job_id)
        except Exception as exc:
            # The render succeeded but recording it did not; still fail-close so the job
            # reaches a terminal state rather than stranding at 'rendering'.
            return self._fail_submit(
                render_package.render_job_id,
                failure_category="unexpected_render_error",
                failure_message=_support_safe_render_failure_message("unexpected_render_error"),
                error_type=RenderExecutionFailedError,
                fallback_message="render_failed",
                cause=exc,
                started_at=started_at,
            )
        self._record_submit_metric(stored, started_at=started_at)
        if stored.status != "rendered":
            return self._to_submit_response(stored, artifact_base64=None)
        stored = hand_off_and_record(
            self._archive_handoff, self._render_store, render_package, result, stored
        )
        return self._to_submit_response(
            stored,
            artifact_base64=base64.b64encode(result.artifact_bytes).decode("ascii"),
        )

    def _fail_submit(
        self,
        render_job_id: str,
        *,
        failure_category: RenderFailureCategory,
        failure_message: str,
        error_type: type[Exception],
        fallback_message: str,
        cause: Exception,
        started_at: float,
    ) -> RenderSubmitResponse:
        """Persist the failure, then raise -- unless a racing writer already holds the truth."""
        # The support-safe message is what gets persisted and returned; the engine's own
        # diagnostic is only available here, on `cause`, and is otherwise discarded (#129).
        log_render_failed(
            render_job_id=render_job_id,
            failure_category=failure_category,
            diagnostic=str(cause),
        )
        failure = self._mark_failed_or_current_truth(
            render_job_id,
            failure_category=failure_category,
            failure_message=failure_message,
        )
        self._record_submit_metric(failure, started_at=started_at)
        if failure.status != "failed":
            return self._to_submit_response(failure, artifact_base64=None)
        raise error_type(failure.failure_message or fallback_message) from cause

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
        response = _to_artifact_metadata_response(stored)
        record_render_operation(
            operation="artifact_metadata_lookup",
            status=stored.status,
            failure_category=stored.failure_category,
            duration_seconds=perf_counter() - started_at,
        )
        record_render_artifact_size(status=stored.status, size_bytes=response.output_size_bytes)
        return response

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
        return RenderSubmitResponse(**_job_response_fields(stored), artifact_base64=artifact_base64)

    @staticmethod
    def _to_status_response(stored: StoredRenderJob) -> RenderJobStatusResponse:
        return RenderJobStatusResponse(**_job_response_fields(stored))

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
        retryable, recovery_action, handoff_owner, support_message = diagnostic_recovery(
            status=stored.status,
            failure_category=stored.failure_category,
            stale_state=stale_state,
        )
        return RenderJobDiagnosticsResponse(
            render_job_id=stored.render_job_id,
            status=stored.status,
            failure_category=stored.failure_category,
            artifact_ready=stored.status == "rendered",
            template_publication=stored.template_publication,
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


def _to_artifact_metadata_response(stored: StoredRenderJob) -> RenderArtifactMetadataResponse:
    """A rendered job always carries its artifact facts; anything else is store corruption."""
    assert stored.artifact_sha256 is not None
    assert stored.bounded_determinism_fingerprint is not None
    assert stored.mime_type is not None
    assert stored.output_size_bytes is not None
    assert stored.render_duration_ms is not None
    assert stored.determinism_mode is not None
    return RenderArtifactMetadataResponse(
        render_job_id=stored.render_job_id,
        status=stored.status,
        output_format=stored.output_format,
        artifact_sha256=stored.artifact_sha256,
        bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
        template_digest=stored.template_digest or "",
        template_publication=stored.template_publication,
        mime_type=stored.mime_type,
        output_size_bytes=stored.output_size_bytes,
        render_duration_ms=stored.render_duration_ms,
        determinism_mode=stored.determinism_mode,
    )


def _runtime_failure_category(failure_message: str) -> RenderFailureCategory:
    if "neither docker nor typst is installed" in failure_message.lower():
        return "engine_unavailable"
    return "template_render_failed"


def _unexpected_failure_category(exc: Exception) -> RenderFailureCategory:
    """Classify an exception the render step did not expect to fail-close on.

    A ``RuntimeError`` keeps its runtime classification (engine vs template);
    anything else is a genuinely unexpected internal error.
    """
    if isinstance(exc, RenderCompileFailedError):
        # The runtime already decided; matching on the message would discard it.
        # `.value` crosses from the runtime StrEnum to the contract Literal, which
        # `test_the_two_failure_category_spellings_agree` holds to the same members --
        # they had drifted, and that drift is why this category had nowhere to land.
        return exc.failure_category.value
    if isinstance(exc, RuntimeError):
        return _runtime_failure_category(str(exc))
    return "unexpected_render_error"


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


def _job_response_fields(stored: StoredRenderJob) -> dict[str, Any]:
    """The job facts every job-shaped response surface states verbatim.

    The submit and status responses must never disagree about the same job; stating
    the shared facts once is what makes that impossible rather than merely tested.
    """
    return dict(
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
        archive_state=stored.archive_state,
        archive_document_id=stored.archive_document_id,
        archive_request_id=stored.archive_request_id,
        archive_detail=stored.archive_detail,
        template_publication=stored.template_publication,
    )
