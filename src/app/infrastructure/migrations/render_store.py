from __future__ import annotations

import sqlite3
from collections.abc import Callable

CURRENT_RENDER_STORE_SCHEMA_VERSION = 2

Migration = Callable[[sqlite3.Connection], None]


def apply_render_store_migrations(connection: sqlite3.Connection) -> None:
    current_version = _current_version(connection)
    for version, migration in _MIGRATIONS:
        if current_version < version:
            migration(connection)
            connection.execute(f"PRAGMA user_version = {version}")
            current_version = version


def render_store_columns(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("PRAGMA table_info(render_job)").fetchall()
    return {str(row[1]) for row in rows}


def _current_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _create_base_schema(connection: sqlite3.Connection) -> None:
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


def _add_lineage_columns(connection: sqlite3.Connection) -> None:
    columns = render_store_columns(connection)
    _add_column_if_missing(connection, columns, "snapshot_id", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(connection, columns, "lineage_refs_json", "TEXT NOT NULL DEFAULT '[]'")
    _add_column_if_missing(
        connection,
        columns,
        "disclosure_refs_json",
        "TEXT NOT NULL DEFAULT '[]'",
    )
    _add_column_if_missing(connection, columns, "requested_by", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(
        connection,
        columns,
        "package_correlation_id",
        "TEXT NOT NULL DEFAULT ''",
    )
    _add_column_if_missing(connection, columns, "package_trace_id", "TEXT NOT NULL DEFAULT ''")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_render_job_status_updated_at
        ON render_job(status, updated_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_render_job_snapshot_id
        ON render_job(snapshot_id)
        """
    )


def _add_column_if_missing(
    connection: sqlite3.Connection,
    columns: set[str],
    name: str,
    definition: str,
) -> None:
    if name in columns:
        return
    connection.execute(f"ALTER TABLE render_job ADD COLUMN {name} {definition}")
    columns.add(name)


_MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _create_base_schema),
    (2, _add_lineage_columns),
)
