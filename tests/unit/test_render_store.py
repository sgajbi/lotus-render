from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.render_store import RenderJobNotFoundError, RenderStore


def _build_store(tmp_path: Path) -> RenderStore:
    return RenderStore(tmp_path / "render-store.sqlite3")


def test_render_store_check_ready_reports_missing_schema(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with sqlite3.connect(tmp_path / "render-store.sqlite3") as connection:
        connection.execute("DROP TABLE render_job")
        connection.commit()

    with pytest.raises(RuntimeError, match="render_store_schema_missing:render_job"):
        store.check_ready()


def test_render_store_get_unknown_job_raises_not_found(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with pytest.raises(RenderJobNotFoundError, match="render_job_not_found"):
        store.get("rdr_missing")


def test_render_store_mark_rendering_unknown_job_raises_not_found(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with pytest.raises(RenderJobNotFoundError, match="render_job_not_found"):
        store.mark_rendering("rdr_missing")
