"""Do not accept work the governed runtime predictably cannot execute.

`MAX_PAYLOAD_LIST_ITEMS` admits 10,000 items per list and the compile envelope is 512 MB
per render. Nothing connected them, so a package could validate, be accepted with `201`,
hold one of two render slots for the whole compile timeout, and always fail -- and the
caller learned nothing they could not have been told at admission (#168).

The envelope was measured, not assumed. Each section scaled on its own and then together:
positions fail at 3,250 and render at 3,125; transactions fail at 5,000 and render at
4,875; both together fail at 2,000 and render at 1,875. The shapes differ by 2.6x, so no
single per-list count expresses this -- the limit belongs to the document. The costs add
as reciprocals, and that rule was checked against five asymmetric mixes before it was
trusted.

These pin the two properties that matter: nothing the runtime was measured to fail on is
admitted, and the refusal happens before a render slot is taken. The second is the whole
point, because refusing after taking a slot spends exactly what refusing exists to save.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.rendering.models import RenderResult
from app.infrastructure.render_store import RenderStore
from app.services.render_envelope import (
    ADMITTED_COST,
    CEILING_POSITIONS,
    CEILING_TRANSACTIONS,
    document_cost,
    envelope_refusal,
)
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderRuntimeMetadata
from app.services.render_submission import (
    RenderPackageInvalidError,
    RenderSubmissionService,
)


def _package(*, positions: int = 0, **overrides: Any) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    report_data = payload["report_data"]
    row = (report_data.get("positions") or report_data["top_holdings"])[0]
    report_data["positions"] = [json.loads(json.dumps(row)) for _ in range(positions)]
    report_data["top_holdings"] = report_data["positions"][:5]
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


class _CountingLimiter(RenderExecutionLimiter):
    """A limiter that remembers whether anything ever asked it for a slot."""

    def __init__(self) -> None:
        super().__init__(Settings().render_execution_concurrency_limit)
        self.acquired = 0

    def acquire(self) -> bool:
        self.acquired += 1
        return super().acquire()


class _EngineThatMustNotRun:
    """Rendering an over-envelope document is the thing being prevented."""

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        raise AssertionError("the engine was asked to render a document over the envelope")


# Every shape the probe measured, with what the runtime actually did. A model that only
# predicts the easy cases predicts nothing, so the boundary rows are the point.
MEASURED = [
    pytest.param(0, 0, True, id="the-golden-fixture"),
    pytest.param(1_000, 1_000, True, id="1000-of-each-renders"),
    pytest.param(2_500, 0, True, id="2500-positions-renders"),
    pytest.param(4_000, 0, False, id="4000-positions-fails"),
    pytest.param(0, 5_000, False, id="5000-transactions-fails"),
    pytest.param(2_000, 2_000, False, id="2000-of-each-fails"),
    pytest.param(3_250, 0, False, id="3250-positions-fails"),
    pytest.param(10_000, 10_000, False, id="10000-of-each-was-admitted-before-this"),
]


@pytest.mark.parametrize(("positions", "transactions", "admitted"), MEASURED)
def test_the_envelope_admits_what_the_runtime_was_measured_to_render(
    positions: int, transactions: int, admitted: bool
) -> None:
    """Nothing measured to fail is admitted.

    The converse is deliberately weaker: a document at 0.98 of the measured ceiling is
    refused although it would render, because the ceilings are failure points found by
    bisection on one machine and a template change moves them. Refusing a document that
    would have rendered costs the caller a message; admitting one that will not costs a
    render slot and twenty seconds.
    """

    report_data: dict[str, Any] = {
        "positions": [{}] * positions,
        "transactions": [{}] * transactions,
    }
    refusal = envelope_refusal(report_data)

    assert (refusal is None) is admitted, (
        f"{positions} positions and {transactions} transactions cost "
        f"{document_cost(report_data):.2f} of the envelope, admitted up to {ADMITTED_COST}"
    )


def test_a_document_over_the_envelope_never_reaches_a_render_slot(tmp_path: Path) -> None:
    """The whole point. Refusing after taking a slot spends what refusing exists to save.

    Before this, an over-envelope package was accepted with `201`, held one of two slots
    for about twenty seconds, and was killed with empty stderr.
    """

    store = RenderStore(tmp_path / "render-store.sqlite3")
    limiter = _CountingLimiter()
    service = RenderSubmissionService(
        rendering_stale_seconds=Settings().stale_rendering_seconds,
        execution_limiter=limiter,
        render_store=store,
        render_engine=cast(Any, _EngineThatMustNotRun()),
    )

    with pytest.raises(RenderPackageInvalidError):
        service.submit(_package(positions=6_000, render_job_id="rdr_over_envelope"))

    assert limiter.acquired == 0, "a document that cannot render took a render slot"
    stored = store.get("rdr_over_envelope")
    assert stored.status == "failed"
    assert stored.failure_category == "resource_limit_exceeded"


def test_the_refusal_says_what_to_reduce_and_by_how_much() -> None:
    """A verdict of "too large" is not actionable, and this refusal is not retryable.

    The same document exceeds the same envelope every time, so the caller needs the
    numbers rather than the verdict.
    """

    refusal = envelope_refusal({"positions": [{}] * 6_000, "transactions": [{}] * 2_000})

    assert refusal is not None
    assert "6,000 positions" in refusal
    assert "2,000 transactions" in refusal
    assert f"{CEILING_POSITIONS:,} positions" in refusal
    assert f"{CEILING_TRANSACTIONS:,} transactions" in refusal
    assert "the two costs add" in refusal.lower()
    assert "fail identically on retry" in refusal


def test_the_cost_counts_the_rows_the_document_will_actually_draw() -> None:
    """The position table draws `positions or top_holdings`, so the cost counts the same.

    A package naming only `top_holdings` costs what its holdings cost; one naming both
    costs the full `positions` list, which is what gets compiled. Counting the other key
    would put the model and the renderer on different documents.
    """

    holdings_only: dict[str, Any] = {"top_holdings": [{}] * 2_000}
    both: dict[str, Any] = {"positions": [{}] * 2_000, "top_holdings": [{}] * 5}

    assert document_cost(holdings_only) == pytest.approx(2_000 / CEILING_POSITIONS)
    assert document_cost(both) == pytest.approx(2_000 / CEILING_POSITIONS)


def test_a_shape_the_model_says_nothing_about_is_not_counted() -> None:
    """The cost rule covers positions and transactions and claims nothing else.

    `MAX_PAYLOAD_LIST_ITEMS` still bounds every other list, which is why it stays: this
    model is narrower than that ceiling rather than a replacement for it. A cost of zero
    here is honest -- those axes have not been measured, so the model does not pretend to
    know them.
    """

    monthly: dict[str, Any] = {"performance_monthly_history": [{}] * 9_000}

    assert document_cost(monthly) == 0.0
    assert envelope_refusal(monthly) is None
