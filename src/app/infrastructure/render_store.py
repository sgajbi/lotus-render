from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Literal, cast

from app.contracts.renders import RenderFailureCategory, RenderJobStatus
from app.domain.rendering.models import RenderResult
from app.infrastructure.migrations.render_store import (
    CURRENT_RENDER_STORE_SCHEMA_VERSION,
    apply_render_store_migrations,
    render_store_columns,
)
from app.infrastructure.render_store_rows import (
    REQUIRED_RENDER_JOB_COLUMNS,
    StoredRenderJob,
    dt_from_text,
    dt_to_text,
    row_to_job,
    utc_now,
)


class RenderJobNotFoundError(ValueError):
    pass


class RenderJobConflictError(ValueError):
    pass


class RenderJobTransitionError(RuntimeError):
    pass


InFlightRenderJobStatus = Literal["accepted", "rendering"]


@dataclass(slots=True)
class CreateOrGetRenderJobResult:
    job: StoredRenderJob
    created: bool


@dataclass(frozen=True, slots=True)
class InFlightRenderJobSummary:
    status: InFlightRenderJobStatus
    count: int
    stale_count: int
    oldest_age_seconds: int | None
    stale_threshold_seconds: int


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
            apply_render_store_migrations(connection)

    def check_ready(self) -> None:
        with self._connect() as connection:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'render_job'
                """
            ).fetchone()
            columns = render_store_columns(connection)
        if row is None:
            raise RuntimeError("render_store_schema_missing:render_job")
        if schema_version < CURRENT_RENDER_STORE_SCHEMA_VERSION:
            raise RuntimeError("render_store_schema_version_outdated")
        missing_columns = REQUIRED_RENDER_JOB_COLUMNS - columns
        if missing_columns:
            raise RuntimeError(f"render_store_schema_missing:{sorted(missing_columns)[0]}")

    def get(self, render_job_id: str) -> StoredRenderJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM render_job WHERE render_job_id = ?",
                (render_job_id,),
            ).fetchone()
        if row is None:
            raise RenderJobNotFoundError("render_job_not_found")
        return row_to_job(row)

    def in_flight_summaries(
        self,
        *,
        accepted_stale_seconds: int,
        rendering_stale_seconds: int,
        now: datetime | None = None,
    ) -> tuple[InFlightRenderJobSummary, ...]:
        observed_at = now or utc_now()
        thresholds = {
            "accepted": accepted_stale_seconds,
            "rendering": rendering_stale_seconds,
        }
        counts: dict[RenderJobStatus, int] = {"accepted": 0, "rendering": 0}
        stale_counts: dict[RenderJobStatus, int] = {"accepted": 0, "rendering": 0}
        oldest_ages: dict[RenderJobStatus, int | None] = {"accepted": None, "rendering": None}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, updated_at
                FROM render_job
                WHERE status IN ('accepted', 'rendering')
                """
            ).fetchall()
        for row in rows:
            status = cast(InFlightRenderJobStatus, row["status"])
            updated_at = dt_from_text(row["updated_at"]) or observed_at
            age_seconds = _age_seconds(updated_at, observed_at)
            counts[status] += 1
            if age_seconds >= thresholds[status]:
                stale_counts[status] += 1
            current_oldest = oldest_ages[status]
            if current_oldest is None or age_seconds > current_oldest:
                oldest_ages[status] = age_seconds
        return (
            InFlightRenderJobSummary(
                status="accepted",
                count=counts["accepted"],
                stale_count=stale_counts["accepted"],
                oldest_age_seconds=oldest_ages["accepted"],
                stale_threshold_seconds=accepted_stale_seconds,
            ),
            InFlightRenderJobSummary(
                status="rendering",
                count=counts["rendering"],
                stale_count=stale_counts["rendering"],
                oldest_age_seconds=oldest_ages["rendering"],
                stale_threshold_seconds=rendering_stale_seconds,
            ),
        )

    def create_or_get(self, **kwargs: Any) -> StoredRenderJob:
        return self.create_or_get_with_outcome(**kwargs).job

    def create_or_get_with_outcome(
        self,
        *,
        render_job_id: str,
        report_job_id: str,
        render_package_version: str,
        package_hash: str,
        snapshot_id: str = "",
        lineage_refs: tuple[str, ...] = (),
        disclosure_refs: tuple[str, ...] = (),
        requested_by: str = "",
        package_correlation_id: str = "",
        package_trace_id: str = "",
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
                now_text = dt_to_text(now)
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO render_job (
                        render_job_id, report_job_id, render_package_version, package_hash,
                        snapshot_id, lineage_refs_json, disclosure_refs_json, requested_by,
                        package_correlation_id, package_trace_id, report_type, template_id,
                        template_version, output_format, status, failure_category,
                        failure_message, runtime_engine, runtime_engine_version,
                        determinism_mode, determinism_statement, bounded_determinism_fingerprint,
                        artifact_sha256, mime_type, output_size_bytes, render_duration_ms,
                        created_at, updated_at, completed_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?
                    )
                    """,
                    (
                        render_job_id,
                        report_job_id,
                        render_package_version,
                        package_hash,
                        snapshot_id,
                        json.dumps(list(lineage_refs), separators=(",", ":")),
                        json.dumps(list(disclosure_refs), separators=(",", ":")),
                        requested_by,
                        package_correlation_id,
                        package_trace_id,
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
                job = row_to_job(row)
                if job.package_hash != package_hash:
                    raise RenderJobConflictError("render_job_conflict")
                return CreateOrGetRenderJobResult(job=job, created=created)

    def claim_for_rendering(
        self,
        render_job_id: str,
        *,
        rendering_stale_seconds: int,
        now: datetime | None = None,
    ) -> StoredRenderJob | None:
        """Take exclusive ownership of a job so this caller may render it.

        A job sitting at ``accepted`` is always claimable: nobody is rendering it yet.
        A job at ``rendering`` is claimable only once it is stale, which means the worker
        that owned it died without reaching a terminal state -- before this, such a row
        stayed at ``rendering`` forever because resubmission short-circuited (issue #105).

        Returns ``None`` when the job is not claimable, which is the ordinary outcome for
        a concurrent duplicate submission of a render that is genuinely still running.
        The claim is a single conditional UPDATE, so exactly one caller can win it.
        """
        observed_at = now or utc_now()
        stale_cutoff = dt_to_text(observed_at - timedelta(seconds=rendering_stale_seconds))
        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT status FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                if existing is None:
                    raise RenderJobNotFoundError("render_job_not_found")
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET status = 'rendering', updated_at = ?
                    WHERE render_job_id = ?
                      AND (
                        status = 'accepted'
                        OR (status = 'rendering' AND updated_at <= ?)
                      )
                    """,
                    (dt_to_text(observed_at), render_job_id, stale_cutoff),
                )
                if cursor.rowcount != 1:
                    return None
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
        return row_to_job(row)

    def mark_rendering(self, render_job_id: str) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="rendering",
            failure_category=None,
            failure_message=None,
            determinism_mode=None,
            determinism_statement=None,
            bounded_determinism_fingerprint=None,
            template_digest=None,
            artifact_sha256=None,
            mime_type=None,
            output_size_bytes=None,
            render_duration_ms=None,
            completed_at=None,
            template_publication=None,
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
            template_digest=result.diagnostic.template_digest,
            template_publication=result.diagnostic.template_publication,
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
            template_digest=None,
            artifact_sha256=None,
            mime_type=None,
            output_size_bytes=None,
            render_duration_ms=None,
            completed_at=utc_now(),
            template_publication=None,
            expected_statuses=("accepted", "rendering"),
        )

    def record_archive_outcome(
        self,
        render_job_id: str,
        *,
        archive_state: str,
        archive_document_id: str | None,
        archive_request_id: str | None,
        archive_detail: str | None,
    ) -> StoredRenderJob:
        """Record the custody truth for a rendered artifact without touching status.

        The render outcome and the archive outcome are different facts with different
        authorities: the job stays 'rendered' whatever Archive said (issue #120), so
        this write deliberately bypasses the status-transition machinery.
        """
        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET archive_state = ?,
                        archive_document_id = ?,
                        archive_request_id = ?,
                        archive_detail = ?,
                        updated_at = ?
                    WHERE render_job_id = ?
                    """,
                    (
                        archive_state,
                        archive_document_id,
                        archive_request_id,
                        archive_detail,
                        dt_to_text(utc_now()),
                        render_job_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise RenderJobNotFoundError("render_job_not_found")
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                return row_to_job(row)

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
        template_digest: str | None,
        template_publication: str | None,
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
                now_text = dt_to_text(utc_now())
                completed_at_text = dt_to_text(completed_at) if completed_at else None
                placeholders = ",".join("?" for _ in expected_statuses)
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET status = ?, failure_category = ?, failure_message = ?,
                        determinism_mode = ?, determinism_statement = ?,
                        bounded_determinism_fingerprint = ?, template_digest = ?,
                        template_publication = ?,
                        artifact_sha256 = ?, mime_type = ?,
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
                        template_digest or "",
                        template_publication,
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
                return row_to_job(row)


def _age_seconds(updated_at: datetime, observed_at: datetime) -> int:
    elapsed = observed_at.astimezone(UTC) - updated_at.astimezone(UTC)
    return max(0, int(elapsed.total_seconds()))
