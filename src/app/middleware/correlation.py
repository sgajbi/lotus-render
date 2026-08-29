from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.observability.log_context import bind_request_identity

_W3C_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        trace_id = _resolve_trace_id(request) or uuid.uuid4().hex
        span_id = _new_span_id()
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id
        request.state.span_id = span_id
        # Also bind it for code that never sees the request - the render service logs
        # from a threadpool and could not otherwise name this id (issue #130).
        bind_request_identity(correlation_id=correlation_id, trace_id=trace_id, span_id=span_id)
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["X-Trace-Id"] = trace_id
        traceparent = _traceparent_header(trace_id, span_id)
        if traceparent:
            response.headers["traceparent"] = traceparent
        response.headers["X-Service-Name"] = self._service_name
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.3f}"
        return response


def _resolve_trace_id(request: Request) -> str | None:
    traceparent = request.headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 4 and _is_w3c_trace_id(parts[1]):
            return parts[1]
    return request.headers.get("X-Trace-Id") or request.headers.get("X-Trace-ID")


def _is_w3c_trace_id(trace_id: str) -> bool:
    return bool(_W3C_TRACE_ID_PATTERN.fullmatch(trace_id))


def _new_span_id() -> str:
    """A fresh W3C `parent-id` for the span this request creates.

    The header used to carry a constant `0000000000000001`. W3C defines this field as
    the id of *this* span, and a tracing backend builds the call tree from it: with one
    value for every span in every service, there is no tree to build -- each response
    claims to be the same span its caller should attach to.

    Random rather than derived: unlike a rendered document, a span must be unique per
    request, and `uuid4` is already the service's source for the correlation and trace
    ids beside it. The all-zero id the spec forbids cannot occur here, because uuid4
    writes its version nibble at hex offset 12, inside the sixteen characters taken.
    """
    return uuid.uuid4().hex[:16]


def _traceparent_header(trace_id: str, span_id: str) -> str | None:
    if not _is_w3c_trace_id(trace_id):
        return None
    return f"00-{trace_id}-{span_id}-01"
