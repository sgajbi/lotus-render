"""Exact controlled Report identity; opaque digests confer no bank authority."""

import json
from typing import Literal

from app.contracts.composite_historical import HistoricalSelection
from app.contracts.composite_review import CompositeModel
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.custody import validate_custody_bindings
from app.services.composite_workbook.eligibility_custody import CustodyDigest
from app.services.composite_workbook.historical_tables import CALCULATION_BOUNDARY


class HistoricalCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v7"]
    qualification: Literal["CONTROLLED_HISTORICAL_POLICY_EVIDENCE_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    selection: HistoricalSelection
    series_digest: CustodyDigest
    source_revision_digest: CustodyDigest
    factual_content_digest: CustodyDigest
    calculation_boundary: str


def validate_historical_custody(package: RenderPackage) -> None:
    archive = package.render_context.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("composite_historical_archive_identity_required")
    identity = archive.get("composite_report_identity")
    typed = HistoricalCustodyIdentity.model_validate_json(json.dumps(identity))
    if (
        typed.calculation_boundary != CALCULATION_BOUNDARY
        or typed.selection.model_dump(mode="json") != package.report_data["selection"]
    ):
        raise ValueError("composite_historical_custody_identity_conflict")
    validate_custody_bindings(package, archive, prefix="composite_historical")
