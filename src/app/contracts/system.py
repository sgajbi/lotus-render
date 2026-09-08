from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Current health posture.", examples=["ok"])
    service: str | None = Field(
        default=None,
        description="Owning service name when relevant.",
        examples=["lotus-render"],
    )


class VersionResponse(BaseModel):
    """Build provenance for the running service.

    Every field is a plain string including when it is unknown, so an operator reading
    this never has to distinguish a missing key from an unidentifiable build: the
    answer is always present and always says which of the two it is.
    """

    service_name: str = Field(description="Owning service name.", examples=["lotus-render"])
    service_version: str = Field(description="Declared service version.", examples=["0.1.0"])
    git_commit_sha: str = Field(
        description=(
            "Commit the image was built from, suffixed `-dirty` when the source tree "
            "carried uncommitted changes, or `unknown` when the build supplied none."
        ),
        examples=["927aec7de39b3d05db6d895d9db023bbefced37c"],
    )
    git_branch: str = Field(description="Branch the build was taken from.", examples=["main"])
    repository_url: str = Field(
        description="Repository the build came from.",
        examples=["https://github.com/sgajbi/lotus-render"],
    )
    build_timestamp_utc: str = Field(
        description="UTC instant the image was built.", examples=["2026-09-08T00:00:00Z"]
    )
    ci_pipeline_run_id: str = Field(
        description="Pipeline run that produced the image, or `local`.", examples=["local"]
    )
    image_digest: str = Field(
        description=(
            "Image digest once the image has been pushed. Reports "
            "`unavailable-before-push` otherwise, because an image cannot contain its own "
            "digest -- the digest exists only once the image does, so no build argument "
            "can supply it and a value must arrive from the deployment surface."
        ),
        examples=["unavailable-before-push"],
    )


class RenderSupportabilitySummary(BaseModel):
    featureKey: Literal["render.observability.render_supportability"] = Field(
        description="RFC-0108 feature key for render supportability posture.",
        examples=["render.observability.render_supportability"],
    )
    state: Literal["ready", "degraded", "unavailable"] = Field(
        description="Current render supportability posture.",
        examples=["ready"],
    )
    reason: Literal[
        "render_supportability_ready",
        "render_supportability_draining",
        "render_store_unavailable",
        "template_registry_unavailable",
        "runtime_configuration_unavailable",
    ] = Field(
        description="Bounded product-safe reason for the supportability state.",
        examples=["render_supportability_ready"],
    )
    freshnessBucket: Literal["current", "unknown"] = Field(
        description="Freshness of the supportability signal.",
        examples=["current"],
    )
    deterministicOutputSupported: bool = Field(
        description="Whether the configured runtime can support deterministic render proof.",
        examples=[True],
    )
    runtimeEngine: str = Field(
        description="Configured render engine family.",
        examples=["typst"],
    )
    runtimeEngineVersion: str = Field(
        description="Current runtime-engine version posture.",
        examples=["0.14.2"],
    )
    defaultOutputFormat: str = Field(
        description="Default output format for render jobs.",
        examples=["pdf"],
    )
    supportedOutputFormats: list[str] = Field(
        description="Supported output formats for render jobs.",
        examples=[["pdf"]],
    )
    renderStoreReady: bool = Field(
        description="Whether the render store is ready for persisted render attempts.",
        examples=[True],
    )
    templateRegistryReady: bool = Field(
        description="Whether the governed template registry is loaded.",
        examples=[True],
    )
    runtimeAvailable: bool = Field(
        description="Whether the configured Typst/Docker render runtime is executable.",
        examples=[True],
    )
    draining: bool = Field(
        description="Whether the service is currently draining.",
        examples=[False],
    )


class RenderInFlightJobSummary(BaseModel):
    status: Literal["accepted", "rendering"] = Field(
        description="Non-terminal persisted render job lifecycle state.",
        examples=["rendering"],
    )
    count: int = Field(
        ge=0,
        description="Number of persisted non-terminal render jobs in this state.",
        examples=[2],
    )
    staleCount: int = Field(
        ge=0,
        description="Number of jobs at or beyond the configured stale threshold.",
        examples=[1],
    )
    freshCount: int = Field(
        ge=0,
        description="Number of jobs below the configured stale threshold.",
        examples=[1],
    )
    oldestAgeSeconds: int | None = Field(
        default=None,
        ge=0,
        description="Age in seconds of the oldest job in this state, or null when none exist.",
        examples=[912],
    )
    staleThresholdSeconds: int = Field(
        ge=1,
        description="Configured threshold used to classify stale jobs in this state.",
        examples=[900],
    )


class MetadataResponse(BaseModel):
    service: str = Field(description="Service name.", examples=["lotus-render"])
    version: str = Field(description="Service version.", examples=["0.1.0"])
    roundingPolicyVersion: str = Field(
        description="Governed rounding policy version.",
        examples=["v1"],
    )
    environment: str = Field(
        description="Current runtime environment.",
        examples=["development"],
    )
    runtimeEngine: str = Field(
        description="Configured render engine family.",
        examples=["typst"],
    )
    runtimeEngineVersion: str = Field(
        description="Current runtime-engine version posture.",
        examples=["foundation"],
    )
    defaultOutputFormat: str = Field(
        description="Default output format for render jobs.",
        examples=["pdf"],
    )
    supportedOutputFormats: list[str] = Field(
        description="Supported output formats in the current foundation slice.",
        examples=[["pdf"]],
    )
    renderAttemptStatuses: list[str] = Field(
        description=(
            "Transient render-attempt phases used inside the render engine. Persisted render jobs "
            "use accepted, rendering, rendered, and failed."
        ),
        examples=[["accepted", "validating_package", "rendering", "rendered", "failed"]],
    )
    supportability: RenderSupportabilitySummary = Field(
        description="Source-backed RFC-0108 render supportability posture.",
    )
    renderStoreInFlight: list[RenderInFlightJobSummary] = Field(
        description=(
            "Source-backed aggregate non-terminal render job posture. This is bounded aggregate "
            "state and never includes render job, report job, portfolio, tenant, trace, or storage "
            "identifiers."
        ),
    )


class TemplateProjectionEntry(BaseModel):
    template_id: str = Field(
        ...,
        description="Template family identifier.",
        examples=["portfolio-review"],
    )
    template_version: str = Field(
        ...,
        description="Registered version of the template family.",
        examples=["v1"],
    )
    status: str = Field(
        ...,
        description=(
            "Lifecycle status of this version -- the renderable posture the registry "
            "gates new renders on."
        ),
        examples=["active"],
    )
    template_publication: str = Field(
        ...,
        description=(
            "'published' means this version's bytes are frozen under recorded approval "
            "and (template_id, template_version) is a stable semantic identity; "
            "'development' versions may still change under re-approval. Publication is "
            "a separate stated fact from rendering support, and neither implies "
            "distribution authority."
        ),
        examples=["published"],
    )
    published_at: str | None = Field(
        default=None,
        description="Date the version's bytes were frozen; absent on development versions.",
        examples=["2026-09-04"],
    )
    published_by: str | None = Field(
        default=None,
        description="Governance identity that approved the freeze; absent on development versions.",
        examples=["lotus-platform-governance"],
    )
    supported_report_types: list[str] = Field(
        ...,
        description="Report types this version renders.",
        examples=[["portfolio_review"]],
    )
    supported_report_data_contract_versions: list[str] = Field(
        ...,
        description="Report data contract versions this version accepts.",
        examples=[["portfolio_review.v1"]],
    )


class TemplatesProjectionResponse(BaseModel):
    templates: list[TemplateProjectionEntry] = Field(
        ...,
        description=(
            "One entry per registered template version, ordered by (template_id, template_version)."
        ),
    )
