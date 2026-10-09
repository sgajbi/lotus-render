"""Pinned controlled Manage in-memory/Report examples; no API or PG proof."""

import json
from pathlib import Path
from typing import Any

from eligibility_fixtures import producer_package


def amendment_data(version: str = "v2", kind: str = "published") -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "composite-amendment-v6"
    data: dict[str, Any] = json.loads(
        (path / f"composite-review.v6.definition-{version}.{kind}.expected.json").read_bytes()
    )
    return data


def unit_amendment_package(version: str = "v2", kind: str = "published") -> dict[str, Any]:
    """Artificial Render test envelope, never an emitted Report package."""
    package = producer_package()
    data = amendment_data(version, kind)
    package.update(
        template_version="v6", report_data_contract_version="composite_review.v6", report_data=data
    )
    package.update(
        render_job_id="60000000-0000-4000-8000-000000000001",
        report_job_id="60000000-0000-4000-8000-000000000002",
        snapshot_id="unit-monthly-amendment-v6",
        lineage_refs=["unit-monthly-amendment-v6", "unit-monthly-amendment-revision-v6"],
    )
    package["render_context"]["report_revision_id"] = "unit-monthly-amendment-revision-v6"
    archive = package["render_context"]["archive"]
    archive.update(
        report_revision_id="unit-monthly-amendment-revision-v6",
        tenant_id=data["tenant_id"],
        composite_id=data["selection"]["composite_id"],
        as_of_date=data["selection"]["period_end"],
        retention_start_date=data["selection"]["period_end"],
        reporting_period_start=data["selection"]["period_start"],
        reporting_period_end=data["selection"]["period_end"],
    )
    identity = archive["composite_report_identity"]
    identity.update(
        contract_version=data["contract_version"],
        qualification=data["qualification"],
        selection=data["selection"],
    )
    identity.update(
        series_digest="1" * 64, source_revision_digest="2" * 64, factual_content_digest="3" * 64
    )
    return package
