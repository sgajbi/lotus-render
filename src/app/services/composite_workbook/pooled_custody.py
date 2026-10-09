"""Report-owned v5 custody identity; no derived revision or economic calculation."""

import json
from typing import Annotated, Literal

from pydantic import Field

from app.contracts.composite_pooled_selection import PooledAnalysisSelection
from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.custody import validate_custody_bindings

CustodyDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PooledCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v5"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: PooledAnalysisSelection
    series_digest: CustodyDigest
    source_revision_digest: CustodyDigest
    factual_content_digest: CustodyDigest


def validate_pooled_custody(package: RenderPackage) -> None:
    """Bind Report's retained identity without calculating its revision digests."""
    context = package.render_context
    archive = context.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("composite_pooled_archive_identity_required")
    identity = archive.get("composite_report_identity")
    PooledCustodyIdentity.model_validate_json(json.dumps(identity))
    if not isinstance(identity, dict) or identity["selection"] != package.report_data["selection"]:
        raise ValueError("composite_pooled_custody_selection_conflict")
    validate_custody_bindings(package, archive, prefix="composite_pooled")
