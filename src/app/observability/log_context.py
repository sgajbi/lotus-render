"""Carry the request's correlation identity to code that has no access to the request.

The render service takes no correlation parameter, so its log lines could not name the
HTTP correlation id the access log uses, and the two identities were never joined
(issue #130). A context variable carries it without threading a parameter through every
service signature -- and it survives ``run_in_threadpool``, which is how the render
actually executes.
"""

from __future__ import annotations

from contextvars import ContextVar

_MISSING = "missing"

_correlation_id: ContextVar[str] = ContextVar("lotus_render_correlation_id", default=_MISSING)
_trace_id: ContextVar[str] = ContextVar("lotus_render_trace_id", default=_MISSING)
_span_id: ContextVar[str] = ContextVar("lotus_render_span_id", default=_MISSING)


def bind_request_identity(*, correlation_id: str, trace_id: str, span_id: str) -> None:
    _correlation_id.set(correlation_id)
    _trace_id.set(trace_id)
    _span_id.set(span_id)


def current_correlation_id() -> str:
    return _correlation_id.get()


def current_trace_id() -> str:
    return _trace_id.get()


def current_span_id() -> str:
    """The span this request created, as advertised in its `traceparent` response.

    A span id nobody can join to is only a header. Carrying it here is what lets a log
    line name the same span a tracing backend holds.
    """
    return _span_id.get()
