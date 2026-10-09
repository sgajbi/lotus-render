"""Preserve Report-owned revision authority and bind its v3 custody envelope."""

import json
from typing import Any, Literal

from pydantic import Field

from app.contracts.composite_linked import LinkedSelection
from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage


class LinkedCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v3"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: LinkedSelection
    series_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    factual_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def validate_linked_custody(package: RenderPackage) -> None:
    """Validate transport bindings without deriving Report's revision algorithm."""
    context = package.render_context
    archive = context.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("composite_linked_archive_identity_required")
    identity = archive.get("composite_report_identity")
    LinkedCustodyIdentity.model_validate_json(json.dumps(identity))
    if not isinstance(identity, dict) or identity["selection"] != package.report_data["selection"]:
        raise ValueError("composite_linked_custody_selection_conflict")
    revision = context.get("report_revision_id")
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("composite_linked_report_revision_required")
    if archive.get("report_revision_id") != revision or package.lineage_refs != [
        package.snapshot_id,
        revision,
    ]:
        raise ValueError("composite_linked_snapshot_revision_conflict")
    _validate_scope(archive, package.report_data)


def _validate_scope(archive: dict[str, Any], data: dict[str, Any]) -> None:
    request = data["selection"]["source_request"]
    expected = {
        "portfolio_scope": "composite",
        "portfolio_id": None,
        "tenant_id": data["tenant_id"],
        "composite_id": request["composite_id"],
        "as_of_date": request["period_end"],
        "reporting_period_start": request["period_start"],
        "reporting_period_end": request["period_end"],
        "retention_start_date": request["period_end"],
    }
    if any(key not in archive or archive[key] != value for key, value in expected.items()):
        raise ValueError("composite_linked_custody_scope_conflict")
