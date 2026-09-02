"""A benchmark not requested and one requested-but-unavailable are different facts.

They never produce the same document. Render used to make them the same: it inferred
benchmarked-ness from whether any period row supplied a benchmark value, and
`is_supplied("Not available")` is False -- so a benchmarked mandate whose comparison
failed upstream drew exactly the document an unbenchmarked portfolio draws, with nothing
on the page to ask about.

Report states the posture now (`benchmark_presentation.posture`, report#242), and Render
reads it. The page-level halves of this live in `test_appendix_glossary`; these are the
module's own boundary cases.
"""

from __future__ import annotations

import pytest

from app.services.benchmark_presentation import (
    UNAVAILABLE,
    benchmark_note,
    benchmark_presentation,
)


@pytest.mark.parametrize(
    "report_data",
    [
        pytest.param({}, id="key-absent"),
        pytest.param({"benchmark_presentation": "available"}, id="key-is-a-string"),
        pytest.param({"benchmark_presentation": {"posture": "probably"}}, id="unknown-posture"),
        pytest.param({"benchmark_presentation": {}}, id="posture-missing"),
    ],
)
def test_an_unstated_posture_fails_toward_the_visible_document(
    report_data: dict[str, object],
) -> None:
    """Absent or unrecognised reads as `unavailable`, never as `not_requested`.

    The two failures are not symmetric. Hiding a benchmark that exists is invisible --
    the page looks like a complete unbenchmarked report. Drawing columns for one that was
    never ordered is visible, and a reader can ask about it. Fail toward what can be seen.
    """

    presentation = benchmark_presentation(report_data)

    assert presentation.posture == UNAVAILABLE
    assert presentation.columns_are_drawn
    note = benchmark_note(presentation)
    assert note is not None
    assert "cannot be relied on" in note


def test_an_unavailable_comparison_without_a_code_still_says_it_is_missing() -> None:
    """Report can state `unavailable` with no benchmark code recorded.

    The sentence loses the name and keeps the fact, because the fact is the part a
    reader acts on.
    """

    note = benchmark_note(
        benchmark_presentation(
            {"benchmark_presentation": {"posture": "unavailable", "reason_code": "timeout"}}
        )
    )

    assert note == "The comparison could not be sourced for this period."
