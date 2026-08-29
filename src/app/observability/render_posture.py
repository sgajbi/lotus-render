"""Publish the render posture gauges independently of who asks for them.

``lotus_render_supportability_total``, ``lotus_render_in_flight_jobs`` and
``lotus_render_oldest_in_flight_age_seconds`` were recorded only as a side effect of the
``GET /metadata`` handler. Prometheus scrapes ``/metrics``, and nothing in the shipped
deployment calls ``/metadata`` -- the compose healthcheck hits ``/health/ready`` and there
is no poller anywhere -- so those series carried **no samples** and the three alerts
written against them could never fire (issue #125).

They cover the stranded-job and supportability conditions this service treats as its most
serious failures, so they are exactly the alerts that must not be silently inert. The
posture is now refreshed on scrape, where the values are wanted, and ``/metadata`` reuses
the same function so the two surfaces cannot disagree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.observability.render_metrics import (
    record_render_in_flight_summary,
    record_render_supportability,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, the container imports services
    from app.dependencies.container import AppContainer


def refresh_render_posture_metrics(container: AppContainer) -> None:
    """Recompute the posture gauges from current state.

    Failures here must not break a scrape or a metadata read: an instance whose store has
    become unreadable is precisely when the remaining metrics matter most, and readiness
    already reports that condition through its own path.
    """
    try:
        supportability = container.render_foundation.supportability_status(
            is_draining=container.is_draining,
            render_store_ready=container.render_store_ready(),
            template_registry_ready=container.template_registry_ready(),
            render_runtime_available=container.render_runtime_available(),
        )
        record_render_supportability(
            state=supportability["state"],
            reason=supportability["reason"],
            freshness_bucket=supportability["freshnessBucket"],
        )
        for summary in container.render_store.in_flight_summaries(
            accepted_stale_seconds=container.settings.stale_accepted_seconds,
            rendering_stale_seconds=container.settings.stale_rendering_seconds,
        ):
            record_render_in_flight_summary(
                status=summary.status,
                fresh_count=summary.count - summary.stale_count,
                stale_count=summary.stale_count,
                oldest_age_seconds=summary.oldest_age_seconds,
            )
    except Exception:  # noqa: BLE001 - a scrape must not fail on a degraded instance
        return
