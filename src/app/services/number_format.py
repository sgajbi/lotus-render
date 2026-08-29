"""One convention for presenting numbers, used by every emitter.

The same figure was formatted two ways on the same page: the allocation donut's legend
read `9,140,741` while the table beneath it read `9140740.73`. Two independent regimes
had grown up -- `Decimal` with `quantize` and thousands separators in the chart module,
and bare f-string floats in the table emitters -- and nothing made them agree.

Precision can legitimately differ between a compact legend and a statement line. The
separator convention cannot: a client reading one page should not see two spellings of
the same amount.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

NOT_AVAILABLE = "Not available"


def _as_decimal(value: object) -> Decimal | None:
    """The amount, or None when the value is not a finite number."""
    try:
        amount = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ArithmeticError, ValueError):
        return None
    return amount if amount.is_finite() else None


def format_money(value: object, *, decimals: int = 2) -> str:
    """Group thousands and round half-up, or pass the value through unchanged.

    A value that is not a number is returned as its own text: report data owns the
    truth, and inventing a zero for something unparseable would be lotus-render
    recreating it.
    """
    amount = _as_decimal(value)
    if amount is None:
        return str(value)
    quantum = Decimal(1).scaleb(-decimals)
    return f"{amount.quantize(quantum, rounding=ROUND_HALF_UP):,.{decimals}f}"


def format_percent(value: object, *, decimals: int = 2) -> str:
    """The same convention, with a trailing percent sign.

    Whether the input already carried a `%` must not change the outcome, and a value
    that formats to its own text -- "60.00" -> "60.00" -- is still a number, so the
    suffix is decided by whether it parsed, never by comparing the strings.
    """
    text = str(value).strip().removesuffix("%").strip()
    if _as_decimal(text) is None:
        return str(value)
    return f"{format_money(text, decimals=decimals)}%"
