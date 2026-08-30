"""One way to write a date, so a document does not write it four ways.

A single portfolio review carried four: ISO ``2026-04-23`` on the positions page,
dotted ``23.04.2026`` on the transactions page, long ``1 Jan 2026`` in the running
header, and ``Apr 26`` on the chart axis. The running header managed two of them in one
phrase -- "Reporting period 1 Jan 2026 - 2026-04-23" -- which is the same defect the
palette had when it held four values of ``accent``.

Report data supplies both ISO and dotted forms in one package: holdings carry
``held_since_date`` as ``2024-01-15`` and transactions carry ``trade_date`` as
``09.01.2026``. Which of them a reader sees is not report's decision to make, so both
are normalised here.

``23 Apr 2026`` is the house form. It is unambiguous in every locale, which neither
``04/23`` nor ``23.04`` is, and it reads as a date rather than as a key.

The chart axis keeps its own short form. It is not an exception to the rule so much as a
different problem: twelve labels have to fit across a plot, and ``Apr 26`` is what fits.
"""

from __future__ import annotations

import re
from datetime import date, datetime

# Formats report data is known to use. Dotted dates are day-first: the golden package's
# transaction period runs to `23.04.2026`, which can only be a day.
_ACCEPTED = ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y")

DISPLAY_FORMAT = "%d %b %Y"


def _parse(value: str) -> date | None:
    for accepted in _ACCEPTED:
        try:
            return datetime.strptime(value, accepted).date()
        except ValueError:
            continue
    return None


def format_date(value: object) -> str:
    """A date in the document's own form, or the value unchanged if it is not one.

    Anything unrecognised is passed through rather than replaced or dropped: a value
    render cannot read is still a value report meant a reader to see, and guessing at it
    would be worse than showing it.
    """
    text = str(value).strip()
    parsed = _parse(text)
    if parsed is None:
        return text
    # `%d` zero-pads, and a leading zero in prose reads as a serial number.
    return parsed.strftime(DISPLAY_FORMAT).lstrip("0")


def is_a_date(value: object) -> bool:
    """Whether this is something `format_date` will actually reformat."""
    return _parse(str(value).strip()) is not None


# Date-shaped tokens inside prose: report supplies some labels ready-made, such as the
# transaction period's "From 01.01.2026 to 23.04.2026".
_IN_TEXT = re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[./]\d{2}[./]\d{4})\b")


def format_dates_in_text(value: object) -> str:
    """Rewrite every date inside a label, leaving the words around them alone.

    Report composes some labels itself. Reformatting the dates inside one changes how it
    reads, not what it says, and leaves the document consistent with itself.
    """
    return _IN_TEXT.sub(lambda match: format_date(match.group(0)), str(value))
