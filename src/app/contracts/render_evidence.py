"""Read models for a job's after-the-fact evidence.

The submit and status surfaces answer "what is my job doing"; these two answer
"what exactly did it produce and why is it in this state" -- the artifact's
identity facts and the operator-facing diagnostics. They share the render
vocabulary (statuses, failure categories, recovery actions) with
``app.contracts.renders``, which remains the authority for it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.contracts.renders import (
    RENDER_STATUS_RESPONSE_EXAMPLE,
    RenderFailureCategory,
    RenderHandoffOwner,
    RenderJobStatus,
    RenderRecoveryAction,
    RenderStaleState,
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
    template_digest: str = Field(
        default="",
        description=(
            "Content hash of the template that produced this artifact. `template_version` "
            "names a directory whose contents can change, so the version alone cannot "
            "explain an output after the fact. Empty for artifacts rendered before the "
            "digest was recorded."
        ),
        examples=["sha256:ab7835d9dee0715480a2f458af7c0f1e"],
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


class RenderJobDiagnosticsResponse(BaseModel):
    render_job_id: str = Field(
        ...,
        description="Opaque render job identifier being diagnosed.",
        examples=["rdr_golden_portfolio_review_v1"],
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
    status: RenderJobStatus = Field(
        ...,
        description="Current persisted render job lifecycle state.",
        examples=["rendering"],
    )
    failure_category: RenderFailureCategory | None = Field(
        default=None,
        description="Machine-readable failure category when the render job failed.",
        examples=["timeout"],
    )
    artifact_ready: bool = Field(
        description="Whether artifact metadata is available for this render job.",
        examples=[False],
    )
    stale_state: RenderStaleState = Field(
        description=(
            "Stale posture for non-terminal jobs, or not_applicable for rendered and failed jobs."
        ),
        examples=["fresh"],
    )
    age_seconds: int = Field(
        ge=0,
        description="Age in seconds since the render job row was last updated.",
        examples=[42],
    )
    stale_threshold_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Configured threshold used for accepted/rendering stale classification.",
        examples=[900],
    )
    retryable: bool = Field(
        description="Whether an identical-package resubmission or recovery retry is appropriate.",
        examples=[False],
    )
    recovery_action: RenderRecoveryAction = Field(
        description="Bounded next action for operators and internal callers.",
        examples=["wait_for_completion"],
    )
    handoff_owner: RenderHandoffOwner = Field(
        description="Owning team or support boundary for the next action.",
        examples=["lotus-render"],
    )
    support_message: str = Field(
        description=(
            "Support-safe explanation of the next action. Raw packages and engine stderr are "
            "never returned."
        ),
        examples=["Render is in progress inside the governed runtime envelope."],
    )
    snapshot_id: str = Field(
        description="Support-safe upstream report snapshot identifier for lineage handoff.",
        examples=["rsnap_golden_portfolio_review_v1"],
    )
    lineage_refs: list[str] = Field(
        description="Support-safe source lineage references retained from the render package.",
        examples=[["rlineage_golden_portfolio_review_v1"]],
    )
    template_id: str = Field(
        description="Governed template identifier used for the render job.",
        examples=["portfolio-review"],
    )
    template_version: str = Field(
        description="Governed template version used for the render job.",
        examples=["v1"],
    )
    output_format: str = Field(
        description="Requested output format for the render job.",
        examples=["pdf"],
    )
    runtime_engine: str = Field(
        description="Governed render engine used for this render job.",
        examples=["typst"],
    )
    runtime_engine_version: str = Field(
        description="Governed render engine version used for this render job.",
        examples=["0.14.2"],
    )
    updated_at: datetime = Field(
        description="UTC timestamp when the render job was last updated.",
        examples=["2026-04-23T13:33:33Z"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the render job reached a terminal state.",
        examples=["2026-04-23T13:33:33Z"],
    )
