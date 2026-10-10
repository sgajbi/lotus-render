"""Bind opaque producer revision identity to retained mixed-source attachments."""

import json
from typing import Any, Literal

from pydantic import Field

from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.custody import validate_custody_bindings
from app.services.composite_workbook.source_context import require


class SourceContextCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v8"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: dict[str, Any]
    source_context: dict[str, Any]
    definition: dict[str, Any]
    source_products: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    series_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    factual_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def validate_source_context_custody(package: RenderPackage) -> None:
    archive = package.render_context.get("archive")
    require(isinstance(archive, dict))
    assert isinstance(archive, dict)
    identity = archive.get("composite_report_identity")
    SourceContextCustodyIdentity.model_validate_json(json.dumps(identity))
    assert isinstance(identity, dict)
    data = package.report_data
    for key in (
        "contract_version",
        "qualification",
        "publication_state",
        "selection",
        "source_context",
    ):
        require(identity[key] == data[key])
    require(
        identity["definition"]
        == {k: data["definition"][k] for k in ("pin", "source_response_digest")}
    )
    products = [
        {k: p[k] for k in ("pin", "source_response_digest")}
        for p in data.get("source_products", [])
    ]
    require(identity.get("source_products", []) == products)
    validate_custody_bindings(package, archive, prefix="composite_source_context")
