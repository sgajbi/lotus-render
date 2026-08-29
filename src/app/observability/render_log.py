"""Correlated, support-safe logging for the render path.

Before this, `src/` contained two log statements -- the request-access line and a shutdown
warning -- and neither was on a render path. Every failure was reduced to a counter
increment with a bounded `failure_category`, while the actual diagnostic (the Typst
stderr) was replaced by a support-safe message and discarded. The runbook told operators
to "inspect template/runtime change evidence" that did not exist (issue #129).

Two identifiers also existed and were never joined: the HTTP correlation from the request
header and the package correlation carried in the body. The store held one, the logs held
the other, so an identifier from an upstream ticket could not find a render's logs
(issue #130). Every line here carries both, keyed by `render_job_id`.
"""

from __future__ import annotations

import logging

from app.observability.log_context import (
    current_correlation_id,
    current_span_id,
    current_trace_id,
)

LOGGER = logging.getLogger("lotus_render.render")

# Typst frames a diagnostic as a structural first line, a location line, and then the
# offending source. That source is built from untrusted report_data, so the source lines
# are the ones that must never reach a log; the diagnosis is in the lines that remain.
_SOURCE_EXCERPT_MARKER = "│"  # the box-drawing bar that prefixes quoted source
_DIAGNOSTIC_LINE_LIMIT = 8
_DIAGNOSTIC_CHAR_LIMIT = 500


def support_safe_diagnostic(raw: str) -> str:
    """Keep the engine's diagnosis, drop the document content it quotes.

    ``error: expected comma`` and its ``file:line:col`` are what an operator needs. The
    lines beneath, which Typst prefixes with a box-drawing bar, reproduce the rendered
    source and therefore the client's data.
    """
    kept = [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and _SOURCE_EXCERPT_MARKER not in line
    ]
    return " | ".join(kept[:_DIAGNOSTIC_LINE_LIMIT])[:_DIAGNOSTIC_CHAR_LIMIT]


def _correlation_fields(package_correlation_id: str, package_trace_id: str) -> str:
    return (
        f"correlation_id={current_correlation_id()} "
        f"trace_id={current_trace_id()} "
        # The span the traceparent response advertised, so a log line joins to the
        # span a tracing backend holds rather than only to the trace.
        f"span_id={current_span_id()} "
        f"package_correlation_id={package_correlation_id} "
        f"package_trace_id={package_trace_id}"
    )


def log_render_accepted(
    *,
    render_job_id: str,
    template_id: str,
    template_version: str,
    package_correlation_id: str,
    package_trace_id: str,
) -> None:
    """The join line: one place where both identities and the job id appear together."""
    LOGGER.info(
        "event=render_accepted render_job_id=%s template_id=%s template_version=%s %s",
        render_job_id,
        template_id,
        template_version,
        _correlation_fields(package_correlation_id, package_trace_id),
    )


def log_render_failed(
    *,
    render_job_id: str,
    failure_category: str,
    diagnostic: str,
    package_correlation_id: str = "",
    package_trace_id: str = "",
) -> None:
    """Record why a render failed, in a form an operator can act on."""
    LOGGER.warning(
        "event=render_failed render_job_id=%s failure_category=%s %s diagnostic=%r",
        render_job_id,
        failure_category,
        _correlation_fields(package_correlation_id, package_trace_id),
        support_safe_diagnostic(diagnostic),
    )


def log_store_unavailable(reason: str) -> None:
    """Surface the store diagnostics the runbook names but nothing ever emitted.

    ``check_ready`` raises ``render_store_schema_missing:*`` and
    ``render_store_schema_version_outdated``; the readiness path caught them and returned
    a bare boolean, so the strings operators are told to look for were unobtainable.
    """
    LOGGER.error("event=render_store_unavailable reason=%s", reason)
