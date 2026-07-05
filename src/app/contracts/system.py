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
