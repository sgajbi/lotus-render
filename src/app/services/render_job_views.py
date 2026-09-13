"""How a stored render job is spoken about: response fields, staleness, failure words.

The submission service orchestrates; this module spells. Every job-shaped response
surface states the same facts through ``job_response_fields``, failure classification
and the support-safe messages live beside it, and none of it touches the store or the
engine -- these are pure functions of a job row or an exception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.contracts.render_evidence import RenderArtifactMetadataResponse
from app.contracts.renders import RenderFailureCategory
from app.infrastructure.render_store_rows import StoredRenderJob
from app.services.render_ports import RenderCompileFailedError


def to_artifact_metadata_response(stored: StoredRenderJob) -> RenderArtifactMetadataResponse:
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


def unexpected_failure_category(exc: Exception) -> RenderFailureCategory:
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


def support_safe_render_failure_message(failure_category: RenderFailureCategory) -> str:
    if failure_category == "engine_unavailable":
        return "Render runtime is unavailable in the governed runtime envelope."
    if failure_category == "timeout":
        return "Render execution timed out in the governed runtime envelope."
    return "Render execution failed in the governed runtime envelope."


def age_seconds(updated_at: datetime) -> int:
    elapsed = datetime.now(UTC) - updated_at.astimezone(UTC)
    return max(0, int(elapsed.total_seconds()))


def stale_threshold_seconds(
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


def job_response_fields(stored: StoredRenderJob) -> dict[str, Any]:
    """The job facts every job-shaped response surface states verbatim.

    The submit and status responses must never disagree about the same job; stating
    the shared facts once is what makes that impossible rather than merely tested.
    ``claim_generation`` is deliberately absent: ownership mechanics are internal,
    not part of the caller contract (#313).
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
