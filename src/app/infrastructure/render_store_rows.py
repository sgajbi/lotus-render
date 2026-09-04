"""The render-job row codec: one place where a row becomes a job and back.

The store operates; this module spells. Keeping the dataclass, the column
contract, and the row mapping together means a new column is added in exactly
one file plus its migration -- the store's SQL references columns by name and
never needs to know their shapes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from app.contracts.renders import RenderFailureCategory, RenderJobStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class StoredRenderJob:
    render_job_id: str
    report_job_id: str
    render_package_version: str
    package_hash: str
    snapshot_id: str
    lineage_refs: tuple[str, ...]
    disclosure_refs: tuple[str, ...]
    requested_by: str
    package_correlation_id: str
    package_trace_id: str
    report_type: str
    template_id: str
    template_version: str
    output_format: str
    status: RenderJobStatus
    failure_category: RenderFailureCategory | None
    failure_message: str | None
    runtime_engine: str
    runtime_engine_version: str
    determinism_mode: str | None
    determinism_statement: str | None
    bounded_determinism_fingerprint: str | None
    template_digest: str | None
    artifact_sha256: str | None
    mime_type: str | None
    output_size_bytes: int | None
    render_duration_ms: int | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    archive_state: str | None = None
    archive_document_id: str | None = None
    archive_request_id: str | None = None
    archive_detail: str | None = None
    template_publication: str | None = None


def dt_to_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def dt_from_text(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


REQUIRED_RENDER_JOB_COLUMNS = {
    "render_job_id",
    "report_job_id",
    "render_package_version",
    "package_hash",
    "snapshot_id",
    "lineage_refs_json",
    "disclosure_refs_json",
    "requested_by",
    "package_correlation_id",
    "package_trace_id",
    "report_type",
    "template_id",
    "template_version",
    "output_format",
    "status",
    "runtime_engine",
    "runtime_engine_version",
    "created_at",
    "updated_at",
}


def _json_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    payload = json.loads(value)
    if not isinstance(payload, list):
        return ()
    return tuple(str(item) for item in payload)


def row_to_job(row: sqlite3.Row) -> StoredRenderJob:
    return StoredRenderJob(
        render_job_id=str(row["render_job_id"]),
        report_job_id=str(row["report_job_id"]),
        render_package_version=str(row["render_package_version"]),
        package_hash=str(row["package_hash"]),
        snapshot_id=str(row["snapshot_id"]),
        lineage_refs=_json_tuple(row["lineage_refs_json"]),
        disclosure_refs=_json_tuple(row["disclosure_refs_json"]),
        requested_by=str(row["requested_by"]),
        package_correlation_id=str(row["package_correlation_id"]),
        package_trace_id=str(row["package_trace_id"]),
        report_type=str(row["report_type"]),
        template_id=str(row["template_id"]),
        template_version=str(row["template_version"]),
        output_format=str(row["output_format"]),
        status=cast(RenderJobStatus, row["status"]),
        failure_category=cast(RenderFailureCategory | None, row["failure_category"]),
        failure_message=row["failure_message"],
        runtime_engine=str(row["runtime_engine"]),
        runtime_engine_version=str(row["runtime_engine_version"]),
        determinism_mode=row["determinism_mode"],
        determinism_statement=row["determinism_statement"],
        bounded_determinism_fingerprint=row["bounded_determinism_fingerprint"],
        template_digest=row["template_digest"] or None,
        artifact_sha256=row["artifact_sha256"],
        mime_type=row["mime_type"],
        output_size_bytes=int(row["output_size_bytes"]) if row["output_size_bytes"] else None,
        render_duration_ms=int(row["render_duration_ms"]) if row["render_duration_ms"] else None,
        created_at=dt_from_text(row["created_at"]) or utc_now(),
        updated_at=dt_from_text(row["updated_at"]) or utc_now(),
        completed_at=dt_from_text(row["completed_at"]),
        archive_state=row["archive_state"],
        archive_document_id=row["archive_document_id"],
        archive_request_id=row["archive_request_id"],
        archive_detail=row["archive_detail"],
        template_publication=row["template_publication"],
    )
