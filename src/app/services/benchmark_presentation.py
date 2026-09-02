"""Whether this document compares the portfolio to a benchmark, and what it says if not.

Report decides. It is a fact about the mandate and the order -- was a benchmark asked for,
and did the comparison arrive -- and Render's part is to draw what it is told.

Render used to infer it, and the inference had a hole that mattered. `is_supplied` treats
the string ``"Not available"`` as absent, so a benchmarked mandate whose comparison failed
upstream had no supplied benchmark value in any period row, and the columns were removed
entirely. **During an upstream outage a benchmarked client received a report indis-
tinguishable from an unbenchmarked portfolio's**, with nothing on the page to ask about.

That inference was itself a fix for a real defect -- a benchmarked column reading
"Not available" on every row, under a heading promising a comparison. Removing the visible
symptom was right; deciding the question was not. Report carried the answer all along in
`comparison_status` and dropped it at the boundary.

The three postures:

``available``
    The comparison arrived. Draw it.
``unavailable``
    A benchmark was ordered and the comparison did not arrive. **Draw the columns
    anyway** and say why: the mandate has a benchmark, and a reader who cannot see that
    the comparison is missing cannot ask for it.
``not_requested``
    No benchmark was ordered. This is the genuinely unbenchmarked portfolio, and it is
    the only case where the columns are absent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
NOT_REQUESTED = "not_requested"
POSTURES = frozenset({AVAILABLE, UNAVAILABLE, NOT_REQUESTED})

#: Report's reason code for a capture taken before benchmark status was recorded. The
#: order asked for a comparison, so the columns stay; the comparison cannot be proven to
#: have been sourced, so it is not claimed.
UNPROVEN_ON_REPLAY = "benchmark_comparison_unproven_for_capture"


@dataclass(frozen=True)
class BenchmarkPresentation:
    """What the document says about its benchmark comparison."""

    posture: str
    benchmark_code: str | None
    reason_code: str | None

    @property
    def columns_are_drawn(self) -> bool:
        """Everything except an order that never asked for a benchmark.

        `unavailable` draws them: the comparison is missing and the page has to show
        that it is missing, which is the whole finding.
        """
        return self.posture != NOT_REQUESTED


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def benchmark_presentation(report_data: Mapping[str, object]) -> BenchmarkPresentation:
    """The posture Report resolved, or the unstated case.

    An absent or unrecognised posture is drawn as `unavailable` rather than
    `not_requested`, because the two failures are not symmetric. Hiding a benchmark that
    exists is invisible to a reader -- the page looks like a complete unbenchmarked
    report. Drawing columns for a benchmark that was never ordered is visible, and a
    reader can ask about it. Fail toward the one that can be seen.
    """
    block = report_data.get("benchmark_presentation")
    if not isinstance(block, Mapping):
        return BenchmarkPresentation(posture=UNAVAILABLE, benchmark_code=None, reason_code=None)
    posture = _text(block.get("posture"))
    if posture not in POSTURES:
        return BenchmarkPresentation(posture=UNAVAILABLE, benchmark_code=None, reason_code=None)
    return BenchmarkPresentation(
        posture=posture,
        benchmark_code=_text(block.get("benchmark_code")),
        reason_code=_text(block.get("reason_code")),
    )


def benchmark_note(presentation: BenchmarkPresentation) -> str | None:
    """What the page says when the comparison is not there, or None when it is.

    Named rather than generic: "Not available" in two cells says nothing a reader can act
    on, and the difference between "we could not get it" and "this was re-rendered from a
    capture that predates the record" is the difference between chasing a data feed and
    chasing nothing.
    """
    if presentation.posture != UNAVAILABLE:
        return None
    against = f" against {presentation.benchmark_code}" if presentation.benchmark_code else ""
    if presentation.reason_code == UNPROVEN_ON_REPLAY:
        return (
            f"This report was re-rendered from a capture taken before benchmark status "
            f"was recorded. A comparison{against} was ordered and cannot be confirmed."
        )
    if presentation.benchmark_code is None and presentation.reason_code is None:
        return (
            "The benchmark posture was not stated for this report, so the comparison "
            "below cannot be relied on either way."
        )
    return f"The comparison{against} could not be sourced for this period."
