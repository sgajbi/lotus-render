"""A failed render must be diagnosable from logs, without leaking the document.

`src/` previously held two log statements, neither on a render path. Every failure became
a counter increment with a bounded `failure_category`, while the engine's own diagnostic
was replaced by a support-safe message and discarded -- so the runbook's instruction to
"inspect template/runtime change evidence" referred to evidence that did not exist
(issue #129). Separately, the HTTP correlation id and the package correlation id were
never written down together, so an identifier from an upstream ticket could not find a
render's logs (issue #130).

The tension these tests hold: the Typst diagnostic is exactly what an operator needs, and
it quotes the rendered source, which is built from untrusted client data. Both halves are
asserted here -- the diagnosis survives, the content does not.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from app.observability.log_context import bind_request_identity
from app.observability.render_log import (
    log_render_failed,
    support_safe_diagnostic,
)

# The exact shape Typst emits: a structural first line, a location, then the offending
# source. Captured from typst 0.14.2.
TYPST_DIAGNOSTIC = (
    "error: expected comma\n"
    "  ┌─ t.typ:2:24\n"
    "  │\n"
    '2 │ #f("CLIENT_SENTINEL_NAME "unclosed, "x")\n'
    "  │                         ^\n"
)


def test_the_diagnostic_keeps_the_diagnosis() -> None:
    sanitised = support_safe_diagnostic(TYPST_DIAGNOSTIC)

    assert "expected comma" in sanitised, "the operator loses the reason the compile failed"
    assert "t.typ:2:24" in sanitised, "the operator loses where the compile failed"


def test_the_diagnostic_drops_the_document_content() -> None:
    """Typst quotes the rendered source, which is built from untrusted report data."""

    sanitised = support_safe_diagnostic(TYPST_DIAGNOSTIC)

    assert "CLIENT_SENTINEL_NAME" not in sanitised, (
        "the sanitised diagnostic reproduces the client's data; #33 removed exactly this "
        "from the store and it must not return through the log."
    )


def test_the_diagnostic_is_bounded() -> None:
    """A pathological document must not push an unbounded string into the log."""

    sanitised = support_safe_diagnostic("error: broken\n" * 5000)

    assert len(sanitised) <= 500


def test_a_failed_render_logs_a_correlated_line(caplog: pytest.LogCaptureFixture) -> None:
    bind_request_identity(correlation_id="corr-http-1", trace_id="trace-http-1")

    with caplog.at_level(logging.WARNING, logger="lotus_render.render"):
        log_render_failed(
            render_job_id="rdr_1",
            failure_category="template_render_failed",
            diagnostic=TYPST_DIAGNOSTIC,
            package_correlation_id="corr-package-1",
            package_trace_id="trace-package-1",
        )

    line = caplog.messages[-1]
    assert "render_job_id=rdr_1" in line
    assert "failure_category=template_render_failed" in line
    assert "expected comma" in line
    assert "CLIENT_SENTINEL_NAME" not in line


def test_an_upstream_correlation_id_finds_the_render(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """The join #130 was missing: one line carrying both identities and the job id.

    Given only a `package_correlation_id` from a lotus-report ticket, an operator must be
    able to reach the render's logs -- which means the HTTP correlation id used by every
    other line has to appear alongside it at least once.
    """

    app = create_app(Settings(render_store_path=str(tmp_path / "store.sqlite3")))

    payload = Path("tests/golden/portfolio-review/v1/render-package.json").read_text(
        encoding="utf-8"
    )
    with caplog.at_level(logging.INFO, logger="lotus_render.render"):
        with TestClient(app) as client:
            client.post(
                "/renders",
                content=payload,
                headers={"Content-Type": "application/json", "X-Correlation-Id": "corr-http-9"},
            )

    accepted = [line for line in caplog.messages if "event=render_accepted" in line]
    assert accepted, "no join line was emitted for the submitted render"
    line = accepted[-1]
    assert "render_job_id=rdr_golden_portfolio_review_v1" in line
    assert "correlation_id=corr-http-9" in line, "the HTTP identity is missing from the join"
    assert "package_correlation_id=corr-golden-portfolio-review-v1" in line, (
        "the package identity is missing from the join, so an upstream ticket cannot "
        "reach this render's logs"
    )
