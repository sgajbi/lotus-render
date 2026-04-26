from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

LOGGER = logging.getLogger("lotus_render.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        correlation_id = getattr(request.state, "correlation_id", "missing")
        trace_id = getattr(request.state, "trace_id", "missing")
        LOGGER.info(
            "service=%s method=%s path=%s status=%s correlation_id=%s trace_id=%s duration_ms=%.3f",
            self._service_name,
            request.method,
            request.url.path,
            response.status_code,
            correlation_id,
            trace_id,
            duration_ms,
        )
        return response
