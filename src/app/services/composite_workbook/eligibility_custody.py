"""Report-owned v4 custody identity; no financial selector or derived revision."""

import json
from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage

CustodyDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class EligibilityCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v4"]
    qualification: Literal["CONTROLLED_ELIGIBILITY_SOURCE_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: EligibilitySelection
    series_digest: CustodyDigest
    source_revision_digest: CustodyDigest
    factual_content_digest: CustodyDigest


def validate_eligibility_custody(package: RenderPackage) -> None:
    """Bind Report's retained identity without calculating its revision digests."""
    context = package.render_context
    archive = context.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("composite_eligibility_archive_identity_required")
    identity = archive.get("composite_report_identity")
    EligibilityCustodyIdentity.model_validate_json(json.dumps(identity))
    if not isinstance(identity, dict) or identity["selection"] != package.report_data["selection"]:
        raise ValueError("composite_eligibility_custody_selection_conflict")
    _validate_revision(package, archive)
    _validate_scope(package, archive)


def _validate_revision(package: RenderPackage, archive: dict[str, Any]) -> None:
    revision = package.render_context.get("report_revision_id")
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("composite_eligibility_report_revision_required")
    if archive.get("report_revision_id") != revision or package.lineage_refs != [
        package.snapshot_id,
        revision,
    ]:
        raise ValueError("composite_eligibility_snapshot_revision_conflict")


def _validate_scope(package: RenderPackage, archive: dict[str, Any]) -> None:
    selection = package.report_data["selection"]
    expected = {
        "portfolio_scope": "composite",
        "portfolio_id": None,
        "tenant_id": package.report_data["tenant_id"],
        "composite_id": selection["composite_id"],
        "as_of_date": selection["period_end"],
        "reporting_period_start": selection["period_start"],
        "reporting_period_end": selection["period_end"],
        "retention_start_date": selection["period_end"],
    }
    if any(key not in archive or archive[key] != value for key, value in expected.items()):
        raise ValueError("composite_eligibility_custody_scope_conflict")
