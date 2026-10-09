"""Retain Report-owned v6 identity without deriving Report revision digests."""

import json
from typing import Literal

from app.contracts.composite_amendment import AmendmentEligibilitySelection
from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.custody import validate_custody_bindings
from app.services.composite_workbook.eligibility_custody import CustodyDigest


class AmendmentCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v6"]
    qualification: Literal["CONTROLLED_MONTHLY_SOURCE_AMENDMENT_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: AmendmentEligibilitySelection
    series_digest: CustodyDigest
    source_revision_digest: CustodyDigest
    factual_content_digest: CustodyDigest


def validate_amendment_custody(package: RenderPackage) -> None:
    archive = package.render_context.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("composite_amendment_archive_identity_required")
    identity = archive.get("composite_report_identity")
    AmendmentCustodyIdentity.model_validate_json(json.dumps(identity))
    if not isinstance(identity, dict) or identity["selection"] != package.report_data["selection"]:
        raise ValueError("composite_amendment_custody_selection_conflict")
    validate_custody_bindings(package, archive, prefix="composite_amendment")
