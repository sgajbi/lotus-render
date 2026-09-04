from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.examples import load_portfolio_review_render_package_example
from app.contracts.render_package import RenderPackage

RenderJobStatus = Literal["accepted", "rendering", "rendered", "failed"]
RenderFailureCategory = Literal[
    "package_validation_failed",
    "template_not_supported",
    "template_render_failed",
    # A compile killed for exceeding its memory or CPU bound. The domain enum has had
    # this since #169; this list did not, so the runtime could classify a document as
    # too large and the response had no way to say so.
    "resource_limit_exceeded",
    "engine_unavailable",
    "artifact_validation_failed",
    "timeout",
    "operator_intervention_required",
    "unexpected_render_error",
]
RenderStaleState = Literal["fresh", "stale", "not_applicable"]
RenderRecoveryAction = Literal[
    "wait_for_completion",
    "resubmit_identical_package_or_escalate_runtime",
    "read_artifact_metadata",
    "fix_upstream_render_package",
    "fix_template_registry_or_package",
    "escalate_render_runtime",
    "escalate_template_support",
    # A document too large is not a support case: it fails identically on retry until
    # the document is smaller or the envelope is larger.
    "reduce_document_size_or_raise_envelope",
    "escalate_reporting_platform",
]
RenderHandoffOwner = Literal[
    "lotus-render",
    "lotus-report",
    "template-owner",
    "reporting-platform-on-call",
]

RENDER_SUBMIT_REQUEST_EXAMPLE: dict[str, Any] = load_portfolio_review_render_package_example()

RENDER_STATUS_RESPONSE_EXAMPLE: dict[str, Any] = {
    "render_job_id": "rdr_golden_portfolio_review_v1",
    "report_job_id": "rjob_83ca965c50334c40a17d2b8cc94873a5",
    "status": "rendered",
    "failure_category": None,
    "failure_message": None,
    "template_id": "portfolio-review",
    "template_version": "v1",
    "output_format": "pdf",
    "artifact_sha256": "sha256:2f817e5d665db6c709e1a9f2332ff7fa609d7304c55ba921f97d9b2d71b0679d",
    "bounded_determinism_fingerprint": (
        "376a56c2eae1ccd6a1e09f8c51b190d098b7b7221e266c86dcc524132b745140"
    ),
    "runtime_engine": "typst",
    "runtime_engine_version": "0.14.2",
    "determinism_mode": "bounded_runtime_envelope",
    "determinism_statement": (
        "Bounded determinism is guaranteed only within the governed lotus-render runtime envelope "
        "using Typst 0.14.2."
    ),
    "mime_type": "application/pdf",
    "output_size_bytes": 26823,
    "render_duration_ms": 842,
    "created_at": "2026-04-23T13:33:32Z",
    "updated_at": "2026-04-23T13:33:33Z",
    "completed_at": "2026-04-23T13:33:33Z",
}

RENDER_ARTIFACT_METADATA_RESPONSE_EXAMPLE: dict[str, Any] = {
    "render_job_id": "rdr_golden_portfolio_review_v1",
    "status": "rendered",
    "output_format": "pdf",
    "artifact_sha256": "sha256:2f817e5d665db6c709e1a9f2332ff7fa609d7304c55ba921f97d9b2d71b0679d",
    "bounded_determinism_fingerprint": (
        "376a56c2eae1ccd6a1e09f8c51b190d098b7b7221e266c86dcc524132b745140"
    ),
    "mime_type": "application/pdf",
    "output_size_bytes": 26823,
    "render_duration_ms": 842,
    "determinism_mode": "bounded_runtime_envelope",
}

RENDER_JOB_DIAGNOSTICS_RESPONSE_EXAMPLE: dict[str, Any] = {
    "render_job_id": "rdr_golden_portfolio_review_v1",
    "status": "rendering",
    "failure_category": None,
    "artifact_ready": False,
    "stale_state": "fresh",
    "age_seconds": 42,
    "stale_threshold_seconds": 900,
    "retryable": False,
    "recovery_action": "wait_for_completion",
    "handoff_owner": "lotus-render",
    "support_message": "Render is in progress inside the governed runtime envelope.",
    "snapshot_id": "rsnap_golden_portfolio_review_v1",
    "lineage_refs": ["rlineage_golden_portfolio_review_v1"],
    "template_id": "portfolio-review",
    "template_version": "v1",
    "output_format": "pdf",
    "runtime_engine": "typst",
    "runtime_engine_version": "0.14.2",
    "updated_at": "2026-04-23T13:33:33Z",
    "completed_at": None,
}

API_ERROR_RESPONSE_EXAMPLES: dict[str, dict[str, Any]] = {
    "invalid_content_length": {
        "detail": {
            "code": "invalid_content_length",
            "message": "Content-Length must be a non-negative integer.",
        }
    },
    "request_body_too_large": {
        "detail": {
            "code": "request_body_too_large",
            "message": "Request body exceeds the configured render API limit.",
        }
    },
    "render_job_not_found": {
        "detail": {
            "code": "render_job_not_found",
            "message": "Render job was not found.",
        }
    },
    "render_job_conflict": {
        "detail": {
            "code": "render_job_conflict",
            "message": "Render job identifier was reused with a different render package.",
        }
    },
    "render_package_invalid": {
        "detail": {
            "code": "render_package_invalid",
            "message": "Render package failed governed validation.",
        }
    },
    "render_artifact_not_ready": {
        "detail": {
            "code": "render_artifact_not_ready",
            "message": (
                "Render artifact metadata is not available because rendering has not succeeded."
            ),
        }
    },
    "render_failed": {
        "detail": {
            "code": "render_failed",
            "message": "Render execution failed in the governed runtime envelope.",
        }
    },
    "render_execution_capacity_exhausted": {
        "detail": {
            "code": "render_execution_capacity_exhausted",
            "message": (
                "Render execution capacity is exhausted. Retry after current render work completes."
            ),
        }
    },
}


class ApiErrorDetail(BaseModel):
    code: str = Field(
        ...,
        description="Machine-readable error code for deterministic internal caller handling.",
        examples=["render_job_not_found"],
    )
    message: str = Field(
        ...,
        description="Support-safe explanation of the render API failure.",
        examples=["Render job was not found."],
    )
    field_paths: list[str] | None = Field(
        default=None,
        description=(
            "Support-safe request field paths for framework validation failures. Raw request "
            "payload values are never echoed."
        ),
        examples=[["render_job_id"]],
    )
    correlation_id: str | None = Field(
        default=None,
        description="Request correlation identifier, matching the response header when available.",
        examples=["corr-golden-portfolio-review-v1"],
    )
    trace_id: str | None = Field(
        default=None,
        description="Request trace identifier, matching the response header when available.",
        examples=["trace-golden-portfolio-review-v1"],
    )


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail = Field(
        ...,
        description="Structured error envelope for support-safe internal render APIs.",
        examples=[API_ERROR_RESPONSE_EXAMPLES["render_job_not_found"]["detail"]],
    )


class RenderSubmitResponse(BaseModel):
    render_job_id: str = Field(
        ...,
        description="Opaque render job identifier supplied in the governed render package.",
        examples=["rdr_golden_portfolio_review_v1"],
    )
    report_job_id: str = Field(
        ...,
        description="Upstream lotus-report job identifier associated with this render attempt.",
        examples=["rjob_83ca965c50334c40a17d2b8cc94873a5"],
    )
    snapshot_id: str = Field(
        ...,
        description="Support-safe upstream report snapshot identifier used for render evidence.",
        examples=["rsnap_golden_portfolio_review_v1"],
    )
    lineage_refs: list[str] = Field(
        ...,
        description="Support-safe source lineage references retained from the render package.",
        examples=[["rlineage_golden_portfolio_review_v1"]],
    )
    disclosure_refs: list[str] = Field(
        ...,
        description="Disclosure fragment identifiers required by the governed render package.",
        examples=[["portfolio-review.standard-disclosures.v1"]],
    )
    requested_by: str = Field(
        ...,
        description="Support-safe caller identity supplied in the render package.",
        examples=["advisor.sg@example.com"],
    )
    package_correlation_id: str = Field(
        ...,
        description=(
            "Original render-package correlation identifier retained for audit traceability."
        ),
        examples=["corr-golden-portfolio-review-v1"],
    )
    package_trace_id: str = Field(
        ...,
        description="Original render-package trace identifier retained for audit traceability.",
        examples=["trace-golden-portfolio-review-v1"],
    )
    status: RenderJobStatus = Field(
        ...,
        description="Current render job status after submission handling.",
        examples=["rendered"],
    )
    failure_category: RenderFailureCategory | None = Field(
        default=None,
        description="Machine-readable failure category when rendering failed.",
        examples=["template_render_failed"],
    )
    failure_message: str | None = Field(
        default=None,
        description="Support-safe failure message when rendering failed.",
        examples=["Render execution failed in the governed runtime envelope."],
    )
    template_id: str = Field(
        ...,
        description="Governed template identifier used for this render request.",
        examples=["portfolio-review"],
    )
    template_version: str = Field(
        ...,
        description="Governed template version used for this render request.",
        examples=["v1"],
    )
    output_format: str = Field(
        ...,
        description="Requested output format for the render artifact.",
        examples=["pdf"],
    )
    artifact_sha256: str | None = Field(
        default=None,
        description="Raw SHA-256 hash of the produced render artifact when rendering succeeded.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["artifact_sha256"]],
    )
    bounded_determinism_fingerprint: str | None = Field(
        default=None,
        description="Bounded-determinism fingerprint for the produced artifact when available.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["bounded_determinism_fingerprint"]],
    )
    runtime_engine: str = Field(
        ...,
        description="Governed render engine used for this attempt.",
        examples=["typst"],
    )
    runtime_engine_version: str = Field(
        ...,
        description="Governed render engine version used for this attempt.",
        examples=["0.14.2"],
    )
    determinism_mode: str | None = Field(
        default=None,
        description="Declared determinism mode for this artifact when rendering succeeded.",
        examples=["bounded_runtime_envelope"],
    )
    determinism_statement: str | None = Field(
        default=None,
        description="Support-safe determinism statement for the render outcome.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["determinism_statement"]],
    )
    mime_type: str | None = Field(
        default=None,
        description="Artifact MIME type when rendering succeeded.",
        examples=["application/pdf"],
    )
    output_size_bytes: int | None = Field(
        default=None,
        description="Artifact size in bytes when rendering succeeded.",
        examples=[26823],
    )
    render_duration_ms: int | None = Field(
        default=None,
        description="Measured render duration in milliseconds when rendering succeeded.",
        examples=[842],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the render job was first accepted for processing.",
        examples=["2026-04-23T13:33:32Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when the render job was last updated.",
        examples=["2026-04-23T13:33:33Z"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the render job reached a terminal state.",
        examples=["2026-04-23T13:33:33Z"],
    )
    template_publication: str | None = Field(
        default=None,
        description=(
            "Governance posture of the template version AT RENDER TIME: 'published' "
            "means the version's bytes were frozen under recorded approval, making "
            "(template_id, template_version) a valid semantic identity for external "
            "client delivery; 'development' artifacts may be archived for internal "
            "proof but must not pass an external-publication gate. Null on jobs "
            "recorded before the posture existed. archived_verified and published "
            "are distinct facts -- an external gate needs both."
        ),
        examples=["published"],
    )
    archive_state: str | None = Field(
        default=None,
        description=(
            "Custody state of the rendered artifact with lotus-archive: 'archived_verified' "
            "once Archive independently verified the declared SHA-256 and holds the bytes, "
            "'archive_pending' when the handoff deadline expired and reconciliation by "
            "archive_request_id will resolve it, 'archive_failed' when Archive refused or "
            "was unreachable. Null when no archive handoff applies to this job."
        ),
        examples=["archived_verified"],
    )
    archive_document_id: str | None = Field(
        default=None,
        description=(
            "Durable lotus-archive document identifier, present once custody is verified."
        ),
        examples=["doc_5f0f4a7e1f2b4c8d9e3a6b7c8d9e0f1a"],
    )
    archive_request_id: str | None = Field(
        default=None,
        description=(
            "The idempotent Archive delivery identity Render used for this artifact, "
            "derived from (document_reference, artifact_sha256). This is the value to "
            "reconcile an 'archive_pending' outcome with (lotus-archive GET "
            "/documents/by-request-id/{id}). Render is the sole authority for it: "
            "consumers must read it from here, never re-derive it."
        ),
        examples=["areq_2a08ce2ad6fc822ffc9f89fef2054417"],
    )
    archive_detail: str | None = Field(
        default=None,
        description=(
            "Archive's own words for a non-verified custody state, bounded: the refusal "
            "code and message on 'archive_failed' (e.g. declared_checksum_mismatch and "
            "artifact_identity_collision are terminal -- a re-render redeclares the same "
            "digest -- while archive_unreachable is retry-eligible), or the reconciliation "
            "instruction on 'archive_pending'. Null when custody is verified or no handoff "
            "applies."
        ),
        examples=["archive_refused_422: declared_checksum_mismatch: declared sha256 ..."],
    )
    artifact_base64: str | None = Field(
        default=None,
        description=(
            "Base64-encoded artifact payload returned only on successful synchronous render "
            "submission."
        ),
        examples=["JVBERi0xLjcKJcfs..."],
    )


class RenderJobStatusResponse(BaseModel):
    render_job_id: str = Field(
        ...,
        description="Opaque render job identifier.",
        examples=["rdr_golden_portfolio_review_v1"],
    )
    report_job_id: str = Field(
        ...,
        description="Upstream lotus-report job identifier associated with this render job.",
        examples=["rjob_83ca965c50334c40a17d2b8cc94873a5"],
    )
    snapshot_id: str = Field(
        ...,
        description="Support-safe upstream report snapshot identifier used for render evidence.",
        examples=["rsnap_golden_portfolio_review_v1"],
    )
    lineage_refs: list[str] = Field(
        ...,
        description="Support-safe source lineage references retained from the render package.",
        examples=[["rlineage_golden_portfolio_review_v1"]],
    )
    disclosure_refs: list[str] = Field(
        ...,
        description="Disclosure fragment identifiers required by the governed render package.",
        examples=[["portfolio-review.standard-disclosures.v1"]],
    )
    requested_by: str = Field(
        ...,
        description="Support-safe caller identity supplied in the render package.",
        examples=["advisor.sg@example.com"],
    )
    package_correlation_id: str = Field(
        ...,
        description=(
            "Original render-package correlation identifier retained for audit traceability."
        ),
        examples=["corr-golden-portfolio-review-v1"],
    )
    package_trace_id: str = Field(
        ...,
        description="Original render-package trace identifier retained for audit traceability.",
        examples=["trace-golden-portfolio-review-v1"],
    )
    status: RenderJobStatus = Field(
        ...,
        description="Current render job status.",
        examples=["rendered"],
    )
    failure_category: RenderFailureCategory | None = Field(
        default=None,
        description="Machine-readable failure category when the render job failed.",
        examples=["template_render_failed"],
    )
    failure_message: str | None = Field(
        default=None,
        description="Support-safe failure message when the render job failed.",
        examples=["Render execution failed in the governed runtime envelope."],
    )
    template_id: str = Field(
        ...,
        description="Template identifier used for the render job.",
        examples=["portfolio-review"],
    )
    template_version: str = Field(
        ...,
        description="Template version used for the render job.",
        examples=["v1"],
    )
    output_format: str = Field(
        ...,
        description="Requested output format for the render job.",
        examples=["pdf"],
    )
    artifact_sha256: str | None = Field(
        default=None,
        description="Raw artifact hash when the render job succeeded.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["artifact_sha256"]],
    )
    bounded_determinism_fingerprint: str | None = Field(
        default=None,
        description="Bounded-determinism fingerprint when the render job succeeded.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["bounded_determinism_fingerprint"]],
    )
    runtime_engine: str = Field(
        ...,
        description="Governed render engine used for the render job.",
        examples=["typst"],
    )
    runtime_engine_version: str = Field(
        ...,
        description="Governed render engine version used for the render job.",
        examples=["0.14.2"],
    )
    determinism_mode: str | None = Field(
        default=None,
        description="Declared determinism mode when the render job succeeded.",
        examples=["bounded_runtime_envelope"],
    )
    determinism_statement: str | None = Field(
        default=None,
        description="Support-safe determinism statement for the current render job outcome.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["determinism_statement"]],
    )
    mime_type: str | None = Field(
        default=None,
        description="Artifact MIME type when rendering succeeded.",
        examples=["application/pdf"],
    )
    output_size_bytes: int | None = Field(
        default=None,
        description="Artifact size in bytes when rendering succeeded.",
        examples=[26823],
    )
    render_duration_ms: int | None = Field(
        default=None,
        description="Measured render duration in milliseconds when available.",
        examples=[842],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the render job was created.",
        examples=["2026-04-23T13:33:32Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when the render job was last updated.",
        examples=["2026-04-23T13:33:33Z"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the render job reached a terminal state.",
        examples=["2026-04-23T13:33:33Z"],
    )
    template_publication: str | None = Field(
        default=None,
        description=(
            "Governance posture of the template version AT RENDER TIME: 'published' "
            "means the version's bytes were frozen under recorded approval, making "
            "(template_id, template_version) a valid semantic identity for external "
            "client delivery; 'development' artifacts may be archived for internal "
            "proof but must not pass an external-publication gate. Null on jobs "
            "recorded before the posture existed. archived_verified and published "
            "are distinct facts -- an external gate needs both."
        ),
        examples=["published"],
    )
    archive_state: str | None = Field(
        default=None,
        description=(
            "Custody state of the rendered artifact with lotus-archive: 'archived_verified' "
            "once Archive independently verified the declared SHA-256 and holds the bytes, "
            "'archive_pending' when the handoff deadline expired and reconciliation by "
            "archive_request_id will resolve it, 'archive_failed' when Archive refused or "
            "was unreachable. Null when no archive handoff applies to this job."
        ),
        examples=["archived_verified"],
    )
    archive_document_id: str | None = Field(
        default=None,
        description=(
            "Durable lotus-archive document identifier, present once custody is verified."
        ),
        examples=["doc_5f0f4a7e1f2b4c8d9e3a6b7c8d9e0f1a"],
    )
    archive_request_id: str | None = Field(
        default=None,
        description=(
            "The idempotent Archive delivery identity Render used for this artifact, "
            "derived from (document_reference, artifact_sha256). This is the value to "
            "reconcile an 'archive_pending' outcome with (lotus-archive GET "
            "/documents/by-request-id/{id}). Render is the sole authority for it: "
            "consumers must read it from here, never re-derive it."
        ),
        examples=["areq_2a08ce2ad6fc822ffc9f89fef2054417"],
    )
    archive_detail: str | None = Field(
        default=None,
        description=(
            "Archive's own words for a non-verified custody state, bounded: the refusal "
            "code and message on 'archive_failed' (e.g. declared_checksum_mismatch and "
            "artifact_identity_collision are terminal -- a re-render redeclares the same "
            "digest -- while archive_unreachable is retry-eligible), or the reconciliation "
            "instruction on 'archive_pending'. Null when custody is verified or no handoff "
            "applies."
        ),
        examples=["archive_refused_422: declared_checksum_mismatch: declared sha256 ..."],
    )


class RenderSubmitRequest(RenderPackage):
    pass
