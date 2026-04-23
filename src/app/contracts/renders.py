from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.render_package import RenderPackage

RenderJobStatus = Literal["accepted", "rendering", "rendered", "failed"]
RenderFailureCategory = Literal[
    "package_validation_failed",
    "template_not_supported",
    "template_render_failed",
    "engine_unavailable",
    "artifact_validation_failed",
    "timeout",
    "operator_intervention_required",
]

RENDER_SUBMIT_REQUEST_EXAMPLE: dict[str, Any] = {
    "render_package_version": "render_package.v1",
    "render_job_id": "rdr_golden_portfolio_review_v1",
    "report_job_id": "rjob_83ca965c50334c40a17d2b8cc94873a5",
    "snapshot_id": "rsnap_8c0c8f6fc2d947b89cb451d9f4f5d9bf",
    "report_type": "portfolio_review",
    "report_data_contract_version": "portfolio_review.v1",
    "template_id": "portfolio-review",
    "template_version": "v1",
    "locale": "en-SG",
    "brand_variant": "private_banking",
    "output_format": "pdf",
    "render_context": {"timezone": "Asia/Singapore"},
    "report_data": {
        "client_name": "Alex Tan",
        "portfolio_name": "PB SG Global Balanced",
        "as_of_date": "2026-04-23",
        "currency": "USD",
        "total_value": "15234567.89",
        "summary_paragraph": (
            "The portfolio remained aligned with balanced growth objectives while preserving "
            "liquidity discipline through the quarter."
        ),
        "review_observations": [
            "Equity positioning remained the main contributor to year-to-date performance.",
            "Risk posture stayed within the monitored balanced mandate range.",
        ],
    },
    "lineage_refs": ["rsnap_8c0c8f6fc2d947b89cb451d9f4f5d9bf"],
    "disclosure_refs": ["portfolio-review.standard-disclosures.v1"],
    "requested_by": "advisor.sg@example.com",
    "correlation_id": "corr-golden-portfolio-review-v1",
    "trace_id": "trace-golden-portfolio-review-v1",
}

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

API_ERROR_RESPONSE_EXAMPLES: dict[str, dict[str, Any]] = {
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


class RenderArtifactMetadataResponse(BaseModel):
    render_job_id: str = Field(
        ...,
        description="Opaque render job identifier whose artifact metadata is being returned.",
        examples=["rdr_golden_portfolio_review_v1"],
    )
    status: RenderJobStatus = Field(
        ...,
        description="Current render job status associated with the artifact metadata.",
        examples=["rendered"],
    )
    output_format: str = Field(
        ...,
        description="Artifact output format.",
        examples=["pdf"],
    )
    artifact_sha256: str = Field(
        ...,
        description="Raw SHA-256 hash of the produced artifact.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["artifact_sha256"]],
    )
    bounded_determinism_fingerprint: str = Field(
        ...,
        description="Bounded-determinism fingerprint for the produced artifact.",
        examples=[RENDER_STATUS_RESPONSE_EXAMPLE["bounded_determinism_fingerprint"]],
    )
    mime_type: str = Field(
        ...,
        description="Artifact MIME type.",
        examples=["application/pdf"],
    )
    output_size_bytes: int = Field(
        ...,
        description="Artifact size in bytes.",
        examples=[26823],
    )
    render_duration_ms: int = Field(
        ...,
        description="Measured render duration in milliseconds.",
        examples=[842],
    )
    determinism_mode: str = Field(
        ...,
        description="Declared determinism mode for the artifact.",
        examples=["bounded_runtime_envelope"],
    )


class RenderSubmitRequest(RenderPackage):
    pass
