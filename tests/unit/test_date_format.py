"""A document writes a date one way, and writes no date it was not given.

A single portfolio review carried four forms: ISO `2026-04-23` on the positions page,
dotted `23.04.2026` on the transactions page, long `1 Jan 2026` in the running header,
and `Apr 26` on the chart axis. The header managed two of them in one phrase.

Two of the four came straight from report data, which supplies ISO dates for holdings
and dotted ones for transactions in the same package. The third was worse: `1 Jan 2026`
was a literal in two templates, so every page of every document claimed the review began
on that date. It happened to be right for the banked fixture -- whose transaction period
does start on 1 January -- which is why nothing caught it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.date_format import format_date, format_dates_in_text, is_a_date

TEMPLATE_ROOT = Path("templates/typst")


@pytest.mark.parametrize(
    ("supplied", "shown"),
    [
        ("2026-04-23", "23 Apr 2026"),
        ("23.04.2026", "23 Apr 2026"),
        ("2026/04/23", "23 Apr 2026"),
        ("23/04/2026", "23 Apr 2026"),
        # A single-digit day reads as a date, not a serial number.
        ("2026-01-09", "9 Jan 2026"),
        ("09.01.2026", "9 Jan 2026"),
    ],
)
def test_every_form_report_supplies_reaches_the_page_the_same_way(
    supplied: str, shown: str
) -> None:
    """Which form a reader sees is not report's decision to make."""

    assert format_date(supplied) == shown
    assert is_a_date(supplied)


@pytest.mark.parametrize("value", ["YTD", "", "Not available", "Q1", "2026", "since inception"])
def test_something_that_is_not_a_date_is_left_exactly_as_it_came(value: str) -> None:
    """Passed through rather than replaced or dropped.

    A value render cannot read is still a value report meant a reader to see, and
    guessing at it would be worse than showing it.
    """

    assert format_date(value) == value
    assert not is_a_date(value)


def test_a_label_report_composed_itself_keeps_its_words_and_loses_its_format() -> None:
    """The transaction period arrives ready-made, with dates in report's own form."""

    assert format_dates_in_text("From 01.01.2026 to 23.04.2026") == "From 1 Jan 2026 to 23 Apr 2026"
    assert format_dates_in_text("Transaction activity") == "Transaction activity"


def test_no_template_writes_a_date_of_its_own() -> None:
    """`1 Jan 2026` was a literal in the page header and on the cover, so every document
    stated a reporting period start that no render package supplies.

    It matched the banked fixture, whose transactions do begin on 1 January, which is
    exactly why it survived: the one document anyone looked at was the one it was right
    for. A review of any other period would have said so anyway.
    """

    months = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    patterns = {
        "a long-form date": rf"\b\d{{1,2}} (?:{months}) \d{{4}}\b",
        "an ISO date": r"\b\d{4}-\d{2}-\d{2}\b",
        "a dotted date": r"\b\d{2}\.\d{2}\.\d{4}\b",
    }
    offenders: dict[str, list[str]] = {}
    for template in sorted(TEMPLATE_ROOT.rglob("*.typ")):
        source = template.read_text(encoding="utf-8")
        for what, pattern in patterns.items():
            if found := re.findall(pattern, source):
                offenders[f"{template.as_posix()} ({what})"] = found

    assert not offenders, (
        f"these templates state a date of their own: {offenders}. A date belongs to the "
        "render package; a template that writes one is right only by coincidence."
    )


@pytest.mark.parametrize(
    ("report_data", "expected"),
    [
        ({"as_of_date": "2026-04-23", "review_period_label": "YTD"}, "YTD to 23 Apr 2026"),
        # No label: the as-of date alone is still true, and still says something.
        ({"as_of_date": "2026-04-23"}, "As of 23 Apr 2026"),
        # No as-of date: the label alone, rather than a dangling "to".
        ({"review_period_label": "Since inception"}, "Since inception"),
        ({}, ""),
    ],
)
def test_the_period_is_described_by_whatever_the_package_carries(
    report_data: dict[str, str], expected: str
) -> None:
    """No package carries a period start, so none is stated.

    Each of these combinations is a document someone could order; none of them may
    produce a sentence with a hole in it.
    """

    from app.services.typst_contexts import _reporting_period_label

    assert _reporting_period_label(report_data) == expected


def test_a_table_with_no_columns_still_declares_a_shape() -> None:
    """Typst needs a column tuple even when there is nothing to put in it."""

    from app.services.statement_tables import render_widths

    assert render_widths([]) == "()"
