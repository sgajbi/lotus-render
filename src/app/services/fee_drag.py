"""What the fees cost, said once under the period table -- never a gross column.

The decision on report#247, agreed between both services: the period table is the most
read table in the document, and a gross column widens every row to serve a fact that is
one number per period -- while inviting per-period reading of what is mostly fee-schedule
noise. The one number a fee-paying client acts on is the period drag, and one line under
the table states exactly that, in the same voice as the benchmark and completeness notes.

Report computes the figure (`performance_basis.fee_drag`, report#252) from the RAW
captured gross/net returns, because a difference of two rounded displayed numbers is a
different number than a rounding of the difference. Render states it and derives nothing:

- absent gross upstream means ``fee_drag: null`` -- no line, never a guessed drag;
- a genuine ``"0.00"`` is a finding ("fees cost you nothing this period") and draws;
- the SIGN is preserved: a rebate period arrives negative (net above gross) and the
  sentence follows the sign rather than clamping or hiding it;
- the wording says "approximately" because compounding means gross-minus-net is not
  exactly "fees" -- the field is named for what it is, and so is the sentence.

This module emits Typst string literals, so it escapes with `escape_typst_string`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from app.services.typst_values import escape_typst_string


def _signed_pp(value: object) -> Decimal | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def fee_drag_sentence(report_data: Mapping[str, object]) -> str | None:
    """The agreed one-line statement, or None when Report supplied no figure."""
    basis = report_data.get("performance_basis")
    if not isinstance(basis, Mapping):
        return None
    fee_drag = basis.get("fee_drag")
    if not isinstance(fee_drag, Mapping):
        return None
    drag = _signed_pp(fee_drag.get("gross_minus_net_pp"))
    if drag is None:
        return None
    if drag == 0:
        return "Net of fees; gross and net returns were equal over the period."
    direction = "higher" if drag > 0 else "lower"
    return (
        f"Net of fees; gross returns were {direction} by approximately "
        f"{abs(drag)}pp over the period."
    )


def render_fee_drag_note(report_data: Mapping[str, object]) -> str:
    sentence = fee_drag_sentence(report_data)
    if sentence is None:
        return ""
    return f'#panel-note("{escape_typst_string(sentence)}")'
