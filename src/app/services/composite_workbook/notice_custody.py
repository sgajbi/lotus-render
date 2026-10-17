"""Verify notice own custody after full source/hash/path validation, with no source I/O."""

import json
from typing import Any

from app.contracts.composite_notice_custody import NoticeCustodyIdentity
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.notice_hashes import require
from app.services.composite_workbook.notice_source import (
    notice_schema_validator,
    source_custody_identity,
)


def _validate_source_anchors(data: dict[str, Any], identity: dict[str, Any]) -> None:
    for side, index in (("before", 0), ("after", 2)):
        generation = data["generations"][side]
        node = data["archive_path"]["nodes"][index]
        expected = {
            **generation["selection"],
            "source_document_id": node["document_id"],
            "source_identity": node["document_response"]["composite_report_identity"],
        }
        require(identity["generations"][side] == expected, "custody_source_anchor")
        require(
            expected["source_identity"] == source_custody_identity(generation),
            "custody_source_derivation",
        )


def validate_notice_custody(package: RenderPackage) -> None:
    data = package.report_data
    archive = package.render_context.get("archive")
    require(isinstance(archive, dict), "custody_required")
    assert isinstance(archive, dict)
    identity = archive.get("composite_report_identity")
    require(
        next(
            notice_schema_validator("composite_notice_custody.v9.schema.json").iter_errors(
                identity
            ),
            None,
        )
        is None,
        "custody_schema",
    )
    NoticeCustodyIdentity.model_validate_json(json.dumps(identity))
    assert isinstance(identity, dict)
    for key in (
        "contract_version",
        "comparison_profile",
        "qualification",
        "publication_state",
        "notice_completeness",
        "pair_fingerprint",
        "manifest_digest",
    ):
        require(identity[key] == data[key], "custody_notice_identity")
    _validate_own_capture(package, archive)
    _validate_notice_scope(data, archive)
    _validate_source_anchors(data, identity)


def _validate_own_capture(package: RenderPackage, archive: dict[str, Any]) -> None:
    data = package.report_data
    revision = package.render_context.get("report_revision_id")
    require(isinstance(revision, str) and bool(revision.strip()), "custody_revision_required")
    require(
        archive.get("report_revision_id") == revision
        and package.lineage_refs == [package.snapshot_id, revision],
        "custody_revision_lineage",
    )
    require(
        revision
        not in {g["selection"]["report_revision_id"] for g in data["generations"].values()},
        "custody_source_reuse",
    )
    require(
        package.snapshot_id
        not in {g["selection"]["snapshot_id"] for g in data["generations"].values()},
        "custody_source_reuse",
    )


def _validate_notice_scope(data: dict[str, Any], archive: dict[str, Any]) -> None:
    selection = data["generations"]["before"]["payload"]["selection"]
    expected = {
        "portfolio_scope": "composite",
        "portfolio_id": None,
        "tenant_id": data["tenant_id"],
        "composite_id": selection["composite_id"],
        "as_of_date": selection["period_end"],
        "reporting_period_start": selection["period_start"],
        "reporting_period_end": selection["period_end"],
        "retention_start_date": selection["period_end"],
    }
    require(
        all(key in archive and archive[key] == value for key, value in expected.items()),
        "custody_scope",
    )
