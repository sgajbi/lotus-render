"""What the Portfolio scope panel does not say for itself: how much of the portfolio it is.

The panel draws five holdings with weights and values, and nothing said the five were the
five largest of forty-two. For a concentrated portfolio the rows nearly account for the
whole; for a diversified one they may cover a third -- and the only signal was that the
weights do not sum to 100%, which asks a reader to do arithmetic. The same subset-implying-
completeness shape the contribution ranking had before #225.

The quieter defect: holdings sourced from an unreconciled or restated position set drew a
byte-identical panel to clean holdings. Reconciliation status is a data-quality statement
about a client's own positions.

Report states both now (`holdings_presentation`, report#246) and Render reads them:

- ``posture`` -- authoritative: ``empty`` is a fact about the portfolio (drawn as a
  statement), ``unavailable`` about the data (said). Both used to produce an identical
  empty list.
- ``supportability_status`` -- Core's verdict, forwarded verbatim. ``partial`` means the
  panel is complete but the evidence behind it is unreconciled or restated. Read from the
  field, never from ``len(notes)`` -- inferring partial from a note count is the inference
  this contract removes.
- ``presented_count`` / ``available_count`` / ``presented_weight_pct`` describe exactly
  the drawn rows, from one shared ordering on Report's side.
- ``presented_weight_pct`` **may be absent while the counts are present**: "these five
  cover 0%" is false when weights simply were not stated. Absent means could-not-be-
  established, and the count line draws without it.

This module emits Typst *string literals*, so it escapes with `escape_typst_string`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.typst_values import escape_typst_string

READY = "ready"
EMPTY = "empty"
UNAVAILABLE = "unavailable"
POSTURES = frozenset({READY, EMPTY, UNAVAILABLE})


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _reconciliation(block: Mapping[str, object]) -> str | None:
    """These N of M holdings, covering X% -- or as much of that as Report established.

    Nothing when the panel is the whole portfolio: "5 of 5" is furniture, and a line
    that is always there stops being read. The two halves fail independently -- counts
    without a weight draw the counts alone, never a false 0%.
    """
    presented = _count(block.get("presented_count"))
    available = _count(block.get("available_count"))
    if presented is None or available is None or presented >= available:
        return None
    weight = _text(block.get("presented_weight_pct"))
    if weight is not None:
        return f"These {presented} of {available} holdings cover {weight}% of the portfolio."
    return f"These are the {presented} largest of {available} holdings."


def _notes(block: Mapping[str, object]) -> list[str]:
    entries = block.get("notes")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        return []
    return [
        message
        for entry in entries
        if isinstance(entry, Mapping) and (message := _text(entry.get("message"))) is not None
    ]


def render_holdings_scope_notes(report_data: Mapping[str, object]) -> str:
    """The lines under the Portfolio scope panel, as invoked Typst calls.

    Empty when the package predates the contract (nothing true to add), or when there is
    genuinely nothing to say -- a complete, reconciled panel showing every holding.

    `unavailable` says the data could not be sourced; `empty` states the portfolio holds
    no positions. `partial` supportability adds Report's own note prose, read from
    `supportability_status` and drawn even if the notes list is empty -- the verdict is
    Core's, and a missing sentence does not soften it.
    """
    block = report_data.get("holdings_presentation")
    if not isinstance(block, Mapping):
        return ""
    lines = [*_posture_lines(block), *_supportability_lines(block)]
    return "\n".join(f'#panel-note("{escape_typst_string(line)}")' for line in lines)


def _posture_lines(block: Mapping[str, object]) -> list[str]:
    """What the posture says about the rows.

    Anything unrecognised falls through to the reconciliation, which draws only what the
    counts themselves establish -- never an invented posture sentence.
    """
    posture = _text(block.get("posture"))
    if posture == UNAVAILABLE:
        return ["Holdings could not be sourced for this report."]
    if posture == EMPTY:
        return ["The portfolio holds no positions as of the review date."]
    reconciliation = _reconciliation(block)
    return [reconciliation] if reconciliation is not None else []


def _supportability_lines(block: Mapping[str, object]) -> list[str]:
    """Core's verdict, in Report's prose where any arrived.

    The verdict is read from the field, and a missing sentence does not soften it.
    """
    if _text(block.get("supportability_status")) != "partial":
        return []
    messages = _notes(block)
    if messages:
        return messages
    return ["The positions behind this panel have not been fully reconciled."]
