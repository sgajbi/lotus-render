"""Every metric a prescribed alert reads must carry samples on a plain scrape.

`lotus_render_supportability_total`, `lotus_render_in_flight_jobs` and
`lotus_render_oldest_in_flight_age_seconds` were recorded only as a side effect of the
`GET /metadata` handler. Prometheus scrapes `/metrics`, and nothing in the shipped
deployment calls `/metadata` -- the compose healthcheck hits `/health/ready` and there is
no poller anywhere -- so those series carried no samples and the three alerts written
against them could never fire (issue #125).

The `# HELP`/`# TYPE` lines were present either way, because the metric objects are
declared at import. That is the trap: the metric *looks* published on a scrape. Only a
sample can satisfy an alert, so these tests assert samples.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
ALERT_METRICS = (
    "lotus_render_supportability_total",
    "lotus_render_in_flight_jobs",
    "lotus_render_oldest_in_flight_age_seconds",
)


def _samples(body: str, metric: str) -> list[str]:
    """Sample lines only; `# HELP`/`# TYPE` exist even when nothing has been recorded."""

    return [line for line in body.splitlines() if line.startswith(metric) and line[0] != "#"]


def _scrape(tmp_path: Path, name: str = "store") -> str:
    app = create_app(Settings(render_store_path=str(tmp_path / f"{name}.sqlite3")))
    with TestClient(app) as client:
        return client.get("/metrics").text


@pytest.mark.parametrize("metric", ALERT_METRICS)
def test_alert_metrics_carry_samples_without_a_metadata_call(metric: str, tmp_path: Path) -> None:
    body = _scrape(tmp_path, metric.replace("lotus_render_", ""))

    assert _samples(body, metric), (
        f"{metric} has no samples on a plain scrape, so any alert reading it evaluates over "
        "absent data and cannot fire. Its value must be published by the scrape path, not by "
        "a route the deployment never calls."
    )


def test_a_stale_in_flight_job_is_visible_to_its_alert(tmp_path: Path) -> None:
    """The alert that matters most: a job stranded past its window must be countable."""

    settings = Settings(render_store_path=str(tmp_path / "stale.sqlite3"))
    app = create_app(settings)

    with TestClient(app) as client:
        payload = Path("tests/golden/portfolio-review/v1/render-package.json").read_text(
            encoding="utf-8"
        )
        submitted = client.post(
            "/renders", content=payload, headers={"Content-Type": "application/json"}
        )
        assert submitted.status_code == 201, submitted.text

        # Strand the job the way a killed worker would, then age it past the window.
        with closing(sqlite3.connect(settings.render_store_path)) as connection, connection:
            connection.execute(
                "UPDATE render_job SET status = 'rendering', updated_at = ?",
                (
                    (datetime.now(UTC) - timedelta(seconds=settings.stale_rendering_seconds + 60))
                    .isoformat()
                    .replace("+00:00", "Z"),
                ),
            )

        body = client.get("/metrics").text

    stale = [
        line
        for line in _samples(body, "lotus_render_in_flight_jobs")
        if 'stale_state="stale"' in line and 'status="rendering"' in line
    ]
    assert stale, "no stale in-flight sample was published for a stranded job"
    value = float(stale[0].rsplit(" ", 1)[1])
    assert value == 1.0, f"expected the stranded job to be counted as stale, got {value}"

    oldest = _samples(body, "lotus_render_oldest_in_flight_age_seconds")
    rendering_age = [line for line in oldest if 'status="rendering"' in line]
    assert rendering_age, "no oldest-age sample was published for a stranded job"
    assert float(rendering_age[0].rsplit(" ", 1)[1]) >= settings.stale_rendering_seconds


def test_the_posture_metrics_are_published_by_the_scrape_path_not_a_handler() -> None:
    """Guard the class: a state metric must be refreshed where it is read.

    Scoped to the *state-describing* metrics deliberately. The operation counters are
    event-driven and legitimately carry no samples until traffic arrives, so requiring
    samples from them on a cold scrape would be wrong. The posture trio is different:
    it answers "what is true right now", so it must be published on every scrape, and
    recording it from an unrelated handler is what made its alerts inert (issue #125).
    """

    posture = (ROOT / "src" / "app" / "observability" / "render_posture.py").read_text(
        encoding="utf-8"
    )
    middleware = (ROOT / "src" / "app" / "middleware" / "metrics_posture.py").read_text(
        encoding="utf-8"
    )
    main = (ROOT / "src" / "app" / "main.py").read_text(encoding="utf-8")

    assert "record_render_supportability" in posture
    assert "record_render_in_flight_summary" in posture
    assert "refresh_render_posture_metrics" in middleware, (
        "the scrape path no longer refreshes the posture gauges, so they revert to being "
        "written only by whoever happens to call /metadata."
    )
    assert "MetricsPostureMiddleware" in main, (
        "the posture middleware is not installed, so /metrics publishes stale or absent "
        "posture samples."
    )

    routes = (ROOT / "src" / "app" / "api" / "routes" / "system.py").read_text(encoding="utf-8")
    assert "record_render_in_flight_summary" not in routes, (
        "the metadata handler records posture directly again; it must reuse the shared "
        "refresh so /metadata and /metrics cannot disagree."
    )
