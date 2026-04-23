from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Current health posture.", examples=["ok"])
    service: str | None = Field(
        default=None,
        description="Owning service name when relevant.",
        examples=["lotus-render"],
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
        description="Foundation render-attempt lifecycle statuses.",
        examples=[["accepted", "running", "succeeded", "failed"]],
    )
