"""What the portfolio paid and what it locked in, said instead of left to be summed.

The document answered "what did this portfolio earn me this period" only by making the
reader scan the transaction table and sum it themselves. Report composes the statement now
(`earnings_statement`, report#251): income as gross → withholding → net with the
dividend/interest split, realized P&L with both sides plus the largest single gain and
loss already named -- Report joins the names from holdings exactly as contribution does,
so Render joins nothing and sums nothing.

The load-bearing field is `completeness`, because these are money sums over a **capped**
transaction read. A truncated window makes them a floor, not a period total, and a floor
presented as a total is a false monetary statement on an archived document. So:

- ``window_truncated`` renders the floor sentence -- "at least the amounts shown, based on
  the N of M transactions reviewed" -- and the statement never uses the word "total".
- ``empty`` only ever co-occurs with ``complete``: "nothing happened" cannot be claimed
  from a partial read, and Render must never synthesise an empty statement from a
  truncated one.
- ``income.by_type`` may be absent on rerenders of pre-split snapshots: the statement
  draws without the split, never as zero dividends. Absent is not 0.

Methodology is required output: tax-lot treatment is `not_sourced`, so the page says it
is portfolio earnings and not a tax document.

This module emits Typst *string literals*, so it escapes with `escape_typst_string`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.absence import supplied_text
from app.services.date_format import format_date
from app.services.number_format import group_digits
from app.services.typst_values import escape_typst_string

READY = "ready"
EMPTY = "empty"
UNAVAILABLE = "unavailable"

COMPLETE = "complete"
WINDOW_TRUNCATED = "window_truncated"

_INCOME_TYPE_LABELS = {"DIVIDEND": "Dividends", "INTEREST": "Interest"}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _money(value: object) -> str:
    text = _text(value)
    return group_digits(supplied_text(text)) if text is not None else supplied_text(None)


def _line(label: str, amount: str) -> str:
    return f'#earnings-line("{escape_typst_string(label)}", "{escape_typst_string(amount)}")'


def _income_lines(income: Mapping[str, object]) -> list[str]:
    lines = [
        _line("Gross income", _money(income.get("gross"))),
        _line("Withholding tax", _money(income.get("withholding_tax"))),
        _line("Other deductions", _money(income.get("other_deductions"))),
        _line("Net income", _money(income.get("net"))),
    ]
    # Present only when the capture carries the split; a pre-split snapshot draws the
    # statement without it rather than as zero dividends.
    by_type = income.get("by_type")
    if isinstance(by_type, Sequence) and not isinstance(by_type, (str, bytes, bytearray)):
        for entry in by_type:
            row = _mapping(entry)
            label = _INCOME_TYPE_LABELS.get(str(row.get("income_type")))
            if label is not None:
                lines.append(_line(f"of which {label.lower()}", _money(row.get("net"))))
    return lines


def _key_figure_line(label: str, figure: object) -> str | None:
    row = _mapping(figure)
    name = _text(row.get("security_name"))
    amount = _text(row.get("amount"))
    if name is None or amount is None:
        return None
    date = _text(row.get("transaction_date"))
    # The document writes a date one way everywhere; a raw ISO date here would be the
    # #150 date-forms defect returning through a new section.
    suffix = f" ({format_date(date)})" if date else ""
    return _line(label, f"{group_digits(amount)} {name}{suffix}")


def _realized_lines(realized: Mapping[str, object]) -> list[str]:
    lines = [
        _line("Net realized", _money(realized.get("net"))),
        _line("Realized gains", _money(realized.get("gains"))),
        _line("Realized losses", _money(realized.get("losses"))),
    ]
    for label, key in (("Largest gain", "largest_gain"), ("Largest loss", "largest_loss")):
        figure = _key_figure_line(label, realized.get(key))
        if figure is not None:
            lines.append(figure)
    return lines


def _completeness_line(block: Mapping[str, object]) -> str | None:
    """The claim the sums make. A floor is not a total, and the page says which.

    The counts are Report's; where either is missing on a truncated read, the floor is
    still stated -- the truncation is the fact, the counts only size it.
    """
    if _text(block.get("completeness")) != WINDOW_TRUNCATED:
        return None
    reviewed = _count(block.get("reviewed_transaction_count"))
    source = _count(block.get("source_transaction_count"))
    if reviewed is not None and source is not None:
        return (
            f"The portfolio earned at least the amounts shown, based on the {reviewed} "
            f"of {source} transactions reviewed."
        )
    return "The portfolio earned at least the amounts shown; the transaction window was truncated."


def _methodology_line(block: Mapping[str, object]) -> str:
    methodology = _mapping(block.get("methodology"))
    basis = _text(methodology.get("basis")) or "not stated"
    line = f"Figures are {basis} amounts in the reporting currency."
    if _text(methodology.get("tax_lot_jurisdiction_treatment")) != "sourced":
        line += (
            " This is a statement of portfolio earnings, not a tax document: "
            "jurisdiction tax-lot treatment was not sourced."
        )
    return line


def render_earnings_statement(report_data: Mapping[str, object]) -> str:
    """The statement as invoked Typst calls, or a posture line, or nothing.

    Nothing when the package carries no block (the section was not ordered, or the
    snapshot predates the contract). `empty` is one true sentence about the portfolio;
    `unavailable` says the evidence was not there to compose -- the two never read alike.
    """
    block = report_data.get("earnings_statement")
    if not isinstance(block, Mapping) or not block:
        return ""
    posture = _text(block.get("posture"))
    if posture == EMPTY:
        return (
            '#panel-note("The portfolio received no income and realized no gains or '
            'losses over this period.")'
        )
    if posture != READY:
        return '#panel-note("Income and realized figures could not be composed for this report.")'

    caveat = _completeness_line(block)
    notes = [line for line in (caveat, _methodology_line(block)) if line is not None]
    income = "\n".join(_income_lines(_mapping(block.get("income"))))
    realized = "\n".join(_realized_lines(_mapping(block.get("realized_pnl"))))
    return (
        '#earnings-statement("Income", "Realized gains and losses")[\n'
        f"{income}\n][\n{realized}\n]\n"
        + "\n".join(f'#panel-note("{escape_typst_string(note)}")' for note in notes)
    )
