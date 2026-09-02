from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TemplateLifecycleStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED_RERENDERABLE = "deprecated_rerenderable"
    BLOCKED_FOR_NEW_RENDERS = "blocked_for_new_renders"
    BLOCKED = "blocked"


class TemplatePublication(StrEnum):
    """Whether this version's bytes are frozen.

    `development` versions change under re-approval (`--write`), which is honest while
    the visualization grammar is mid-build. `published` versions never change: a change
    creates the next version, because a published version is the semantic identity an
    archived artifact names forever after. The trigger for publishing is the first
    delivery of an artifact to a consumer outside this repository's own test suite --
    at latest, when the Archive handoff (#120) goes live.
    """

    DEVELOPMENT = "development"
    PUBLISHED = "published"


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
    publication: TemplatePublication = Field(
        ...,
        description=(
            "Whether this version's bytes are frozen. A published version never changes; "
            "a change creates the next version. Explicit rather than defaulted, so a "
            "manifest cannot be silently treated as development."
        ),
        examples=[TemplatePublication.DEVELOPMENT.value],
    )
    golden_sample_ids: list[str] = Field(
        default_factory=list,
        examples=[["golden-portfolio-review-en-SG-private-banking-v1"]],
    )
    template_digest: str = Field(
        ...,
        description=(
            "Content hash of the template directory this manifest describes. Without it "
            "template_version names a mutable directory and cannot explain an output."
        ),
        examples=["sha256:2a59e62b6a9476a20ec63102a0615dd3911e26520a4b094fd73c0875d70d002a"],
    )
    runtime_engine: str = Field(..., examples=["typst"])
    runtime_engine_version: str = Field(..., examples=["foundation"])
