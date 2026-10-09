"""Shared transport binding of opaque Report identity to composite custody scope."""

from typing import Any

from app.contracts.render_package import RenderPackage


def validate_custody_bindings(
    package: RenderPackage, archive: dict[str, Any], *, prefix: str
) -> None:
    revision = package.render_context.get("report_revision_id")
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError(prefix + "_report_revision_required")
    if archive.get("report_revision_id") != revision or package.lineage_refs != [
        package.snapshot_id,
        revision,
    ]:
        raise ValueError(prefix + "_snapshot_revision_conflict")
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
        raise ValueError(prefix + "_custody_scope_conflict")
