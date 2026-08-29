from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_RENDER_PACKAGE_VERSION = "render_package.v1"

# Structural ceilings for the open payload mappings.
#
# ``report_data`` is untrusted input whose size is attacker-influenced up to the request
# body cap, and it is the only bound between the wire and the Typst compiler: rows are
# emitted unbounded by the table emitters, and every scalar is copied once per placeholder
# per template file. Without these ceilings a single in-cap request expands into a source
# one to two orders of magnitude larger and holds one of two render slots for the whole
# compile timeout (issue #107).
#
# The limits are far above any real report (the richest golden fixture has 12 rows in its
# largest list and a 121-character longest string) and exist to make the pipeline's cost a
# bounded function of documented input, not to shape legitimate payloads.
MAX_PAYLOAD_DEPTH = 32
MAX_PAYLOAD_LIST_ITEMS = 10_000
MAX_PAYLOAD_STRING_LENGTH = 100_000
MAX_PAYLOAD_NODES = 500_000


def _children_within_ceilings(current: object, *, field_name: str) -> list[object] | None:
    """Check one node against its own ceiling and return the children to walk next."""
    if isinstance(current, str):
        if len(current) > MAX_PAYLOAD_STRING_LENGTH:
            raise ValueError(
                f"{field_name} contains a string longer than {MAX_PAYLOAD_STRING_LENGTH} characters"
            )
        return None
    if isinstance(current, dict):
        return list(current.values())
    if isinstance(current, (list, tuple)):
        if len(current) > MAX_PAYLOAD_LIST_ITEMS:
            raise ValueError(
                f"{field_name} contains a list longer than {MAX_PAYLOAD_LIST_ITEMS} items"
            )
        return list(current)
    return None


def _assert_within_structural_ceilings(value: dict[str, Any], *, field_name: str) -> None:
    """Reject payloads whose structure would make render cost unbounded.

    Traversal is iterative: a recursive walk would raise ``RecursionError`` on exactly the
    deeply nested payload this guard exists to reject.
    """
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_PAYLOAD_NODES:
            raise ValueError(f"{field_name} exceeds {MAX_PAYLOAD_NODES} values")
        if depth > MAX_PAYLOAD_DEPTH:
            raise ValueError(f"{field_name} nests deeper than {MAX_PAYLOAD_DEPTH} levels")
        children = _children_within_ceilings(current, field_name=field_name)
        if children:
            stack.extend((child, depth + 1) for child in children)


class RenderPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_package_version: str = Field(
        ...,
        description="Versioned render package schema identity.",
        examples=[SUPPORTED_RENDER_PACKAGE_VERSION],
    )
    render_job_id: str = Field(
        ...,
        description="Renderer-owned attempt grouping identifier.",
        examples=["rdr_01JTJ7NQ98X4Y7G5M4K5F3N2A1"],
    )
    report_job_id: str = Field(
        ...,
        description="Upstream lotus-report job identifier.",
        examples=["rjob_01JTJ7NQ98X4Y7G5M4K5F3N2A1"],
    )
    snapshot_id: str = Field(
        ...,
        description="RFC-0101 snapshot identifier used for render evidence.",
        examples=["rsnap_01JTJ7NQ98X4Y7G5M4K5F3N2A1"],
    )
    report_type: str = Field(
        ...,
        description="Canonical report type for template compatibility checks.",
        examples=["portfolio_review"],
    )
    report_data_contract_version: str = Field(
        ...,
        description="Versioned report-data contract carried into rendering.",
        examples=["portfolio_review.v1"],
    )
    template_id: str = Field(
        ...,
        description="Governed template identifier.",
        examples=["portfolio-review"],
    )
    template_version: str = Field(
        ...,
        description="Governed template version.",
        examples=["v1"],
    )
    locale: str = Field(
        ...,
        description="Locale used for template compatibility and formatting behavior.",
        examples=["en-SG"],
    )
    brand_variant: str = Field(
        ...,
        description="Branding posture selected by the upstream reporting flow.",
        examples=["private_banking"],
    )
    output_format: str = Field(
        ...,
        description="Requested render artifact format.",
        examples=["pdf"],
    )
    render_context: dict[str, Any] = Field(
        ...,
        description=(
            "Render-time context that affects presentation but is not business data fetched by "
            "the renderer."
        ),
        examples=[{"as_of_date": "2026-04-23", "timezone": "Asia/Singapore"}],
    )
    report_data: dict[str, Any] = Field(
        ...,
        description="Self-sufficient report payload required for rendering.",
        examples=[{"report_id": "portfolio-review:PB_SG_GLOBAL_BAL_001:2026-04-23"}],
    )
    lineage_refs: list[str] = Field(
        default_factory=list,
        description="Support-safe RFC-0101 lineage references.",
        examples=[["rlineage_01JTJ7NQ98X4Y7G5M4K5F3N2A1"]],
    )
    disclosure_refs: list[str] = Field(
        default_factory=list,
        description="Disclosure fragment identifiers required by the selected template.",
        examples=[["portfolio-review.standard-disclosures.v1"]],
    )
    requested_by: str = Field(
        ...,
        description="Caller identity responsible for the render request.",
        examples=["advisor.sg@example.com"],
    )
    correlation_id: str = Field(
        ...,
        description="End-to-end correlation identifier.",
        examples=["corr-portfolio-review-1"],
    )
    trace_id: str = Field(
        ...,
        description="Trace identifier propagated through the rendering boundary.",
        examples=["trace-portfolio-review-1"],
    )

    @field_validator(
        "render_package_version",
        "render_job_id",
        "report_job_id",
        "snapshot_id",
        "report_type",
        "report_data_contract_version",
        "template_id",
        "template_version",
        "locale",
        "brand_variant",
        "output_format",
        "requested_by",
        "correlation_id",
        "trace_id",
    )
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("render_context", "report_data")
    @classmethod
    def _must_not_be_empty_mapping(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("render_context", "report_data")
    @classmethod
    def _must_be_within_structural_ceilings(cls, value: dict[str, Any]) -> dict[str, Any]:
        _assert_within_structural_ceilings(value, field_name="value")
        return value
