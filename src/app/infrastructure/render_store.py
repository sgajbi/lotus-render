from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, cast

from app.contracts.renders import RenderFailureCategory, RenderJobStatus
from app.domain.rendering.models import RenderResult


class RenderJobNotFoundError(ValueError):
    pass


class RenderJobConflictError(ValueError):
    pass


class RenderJobTransitionError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class StoredRenderJob:
    render_job_id: str
    report_job_id: str
    render_package_version: str
    package_hash: str
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
    artifact_sha256: str | None
    mime_type: str | None
    output_size_bytes: int | None
    render_duration_ms: int | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class CreateOrGetRenderJobResult:
    job: StoredRenderJob
    created: bool


class RenderStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self.ensure_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS render_job (
                    render_job_id TEXT PRIMARY KEY,
                    report_job_id TEXT NOT NULL,
                    render_package_version TEXT NOT NULL,
                    package_hash TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    template_version TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    status TEXT NOT NULL,
                    failure_category TEXT,
                    failure_message TEXT,
                    runtime_engine TEXT NOT NULL,
                    runtime_engine_version TEXT NOT NULL,
                    determinism_mode TEXT,
                    determinism_statement TEXT,
                    bounded_determinism_fingerprint TEXT,
                    artifact_sha256 TEXT,
                    mime_type TEXT,
                    output_size_bytes INTEGER,
                    render_duration_ms INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )

    def check_ready(self) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'render_job'
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("render_store_schema_missing:render_job")

    def get(self, render_job_id: str) -> StoredRenderJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM render_job WHERE render_job_id = ?",
                (render_job_id,),
            ).fetchone()
        if row is None:
            raise RenderJobNotFoundError("render_job_not_found")
        return _row_to_job(row)

    def create_or_get(self, **kwargs: str) -> StoredRenderJob:
        return self.create_or_get_with_outcome(**kwargs).job

    def create_or_get_with_outcome(
        self,
        *,
        render_job_id: str,
        report_job_id: str,
        render_package_version: str,
        package_hash: str,
        report_type: str,
        template_id: str,
        template_version: str,
        output_format: str,
        runtime_engine: str,
        runtime_engine_version: str,
    ) -> CreateOrGetRenderJobResult:
        with self._lock:
            with self._connect() as connection:
                now = utc_now()
                now_text = _dt_to_text(now)
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO render_job (
                        render_job_id, report_job_id, render_package_version, package_hash,
                        report_type, template_id, template_version, output_format, status,
                        failure_category, failure_message, runtime_engine, runtime_engine_version,
                        determinism_mode, determinism_statement, bounded_determinism_fingerprint,
                        artifact_sha256, mime_type, output_size_bytes, render_duration_ms,
                        created_at, updated_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        render_job_id,
                        report_job_id,
                        render_package_version,
                        package_hash,
                        report_type,
                        template_id,
                        template_version,
                        output_format,
                        "accepted",
                        None,
                        None,
                        runtime_engine,
                        runtime_engine_version,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        now_text,
                        now_text,
                        None,
                    ),
                )
                created = cursor.rowcount == 1
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                assert row is not None
                job = _row_to_job(row)
                if job.package_hash != package_hash:
                    raise RenderJobConflictError("render_job_conflict")
                return CreateOrGetRenderJobResult(job=job, created=created)

    def mark_rendering(self, render_job_id: str) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="rendering",
            failure_category=None,
            failure_message=None,
            determinism_mode=None,
            determinism_statement=None,
            bounded_determinism_fingerprint=None,
            artifact_sha256=None,
            mime_type=None,
            output_size_bytes=None,
            render_duration_ms=None,
            completed_at=None,
            expected_statuses=("accepted",),
        )

    def mark_rendered(self, render_job_id: str, result: RenderResult) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="rendered",
            failure_category=None,
            failure_message=None,
            determinism_mode=result.diagnostic.determinism_mode,
            determinism_statement=result.diagnostic.determinism_statement,
            bounded_determinism_fingerprint=result.diagnostic.bounded_determinism_fingerprint,
            artifact_sha256=f"sha256:{result.diagnostic.artifact_sha256}",
            mime_type=result.diagnostic.mime_type,
            output_size_bytes=result.diagnostic.output_size_bytes,
            render_duration_ms=result.diagnostic.render_duration_ms,
            completed_at=utc_now(),
            expected_statuses=("rendering",),
        )

    def mark_failed(
        self,
        *,
        render_job_id: str,
        failure_category: RenderFailureCategory,
        failure_message: str,
    ) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="failed",
            failure_category=failure_category,
            failure_message=failure_message,
            determinism_mode=None,
            determinism_statement=None,
            bounded_determinism_fingerprint=None,
            artifact_sha256=None,
            mime_type=None,
            output_size_bytes=None,
            render_duration_ms=None,
            completed_at=utc_now(),
            expected_statuses=("accepted", "rendering"),
        )

    def _update(
        self,
        *,
        render_job_id: str,
        status: RenderJobStatus,
        failure_category: RenderFailureCategory | None,
        failure_message: str | None,
        determinism_mode: str | None,
        determinism_statement: str | None,
        bounded_determinism_fingerprint: str | None,
        artifact_sha256: str | None,
        mime_type: str | None,
        output_size_bytes: int | None,
        render_duration_ms: int | None,
        completed_at: datetime | None,
        expected_statuses: tuple[RenderJobStatus, ...],
    ) -> StoredRenderJob:
        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT status FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                if existing is None:
                    raise RenderJobNotFoundError("render_job_not_found")
                now_text = _dt_to_text(utc_now())
                completed_at_text = _dt_to_text(completed_at) if completed_at else None
                placeholders = ",".join("?" for _ in expected_statuses)
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET status = ?, failure_category = ?, failure_message = ?,
                        determinism_mode = ?, determinism_statement = ?,
                        bounded_determinism_fingerprint = ?, artifact_sha256 = ?, mime_type = ?,
                        output_size_bytes = ?, render_duration_ms = ?, updated_at = ?,
                        completed_at = ?
                    WHERE render_job_id = ? AND status IN (
                    """
                    + placeholders
                    + """
                    )
                    """,
                    (
                        status,
                        failure_category,
                        failure_message,
                        determinism_mode,
                        determinism_statement,
                        bounded_determinism_fingerprint,
                        artifact_sha256,
                        mime_type,
                        output_size_bytes,
                        render_duration_ms,
                        now_text,
                        completed_at_text,
                        render_job_id,
                        *expected_statuses,
                    ),
                )
                if cursor.rowcount != 1:
                    current_status = str(existing["status"])
                    raise RenderJobTransitionError(
                        f"invalid_render_job_transition:{current_status}->{status}"
                    )
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                assert row is not None
                return _row_to_job(row)


def _dt_to_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _dt_from_text(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_to_job(row: sqlite3.Row) -> StoredRenderJob:
    return StoredRenderJob(
        render_job_id=str(row["render_job_id"]),
        report_job_id=str(row["report_job_id"]),
        render_package_version=str(row["render_package_version"]),
        package_hash=str(row["package_hash"]),
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
        artifact_sha256=row["artifact_sha256"],
        mime_type=row["mime_type"],
        output_size_bytes=int(row["output_size_bytes"]) if row["output_size_bytes"] else None,
        render_duration_ms=int(row["render_duration_ms"]) if row["render_duration_ms"] else None,
        created_at=_dt_from_text(row["created_at"]) or utc_now(),
        updated_at=_dt_from_text(row["updated_at"]) or utc_now(),
        completed_at=_dt_from_text(row["completed_at"]),
    )
