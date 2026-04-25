from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TemplateLifecycleStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED_RERENDERABLE = "deprecated_rerenderable"
    BLOCKED_FOR_NEW_RENDERS = "blocked_for_new_renders"
    BLOCKED = "blocked"


class TemplateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., examples=["portfolio-review"])
    template_version: str = Field(..., examples=["v1"])
    supported_report_types: list[str] = Field(..., min_length=1, examples=[["portfolio_review"]])
    supported_report_data_contract_versions: list[str] = Field(
        ...,
        min_length=1,
        examples=[["portfolio_review.v1"]],
    )
    supported_locales: list[str] = Field(..., min_length=1, examples=[["en-SG"]])
    supported_brand_variants: list[str] = Field(
        ...,
        min_length=1,
        examples=[["private_banking"]],
    )
    supported_output_formats: list[str] = Field(..., min_length=1, examples=[["pdf"]])
    required_disclosure_fragments: list[str] = Field(
        default_factory=list,
        examples=[["portfolio-review.standard-disclosures.v1"]],
    )
    owner_team: str = Field(..., examples=["lotus-reporting"])
    approver: str = Field(..., examples=["lotus-platform-governance"])
    approved_at: str = Field(..., examples=["2026-04-23"])
    status: TemplateLifecycleStatus = Field(..., examples=[TemplateLifecycleStatus.ACTIVE.value])
    golden_sample_ids: list[str] = Field(
        default_factory=list,
        examples=[["golden-portfolio-review-en-SG-private-banking-v1"]],
    )
    runtime_engine: str = Field(..., examples=["typst"])
    runtime_engine_version: str = Field(..., examples=["foundation"])
