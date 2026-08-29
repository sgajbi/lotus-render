"""Refresh the posture gauges before a scrape reads them."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.render_posture import refresh_render_posture_metrics

METRICS_PATH = "/metrics"


class MetricsPostureMiddleware(BaseHTTPMiddleware):
    """Compute the render posture on the request that publishes it.

    Without this the supportability and in-flight gauges are only written when someone
    calls ``GET /metadata``, which nothing in the shipped deployment does, so the three
    alerts written against them evaluate over absent samples and never fire (issue #125).
    Refreshing here keeps the values as fresh as the scrape that reads them and needs no
    scheduler, which this service deliberately does not have.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path == METRICS_PATH:
            container = getattr(request.app.state, "container", None)
            if container is not None:
                refresh_render_posture_metrics(container)
        return await call_next(request)
