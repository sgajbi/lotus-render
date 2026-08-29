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

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

NOT_AVAILABLE = "Not available"

# An amount, optionally labelled with a currency and optionally a percentage. The number
# must run to the end, so `09.01.2026` and `TXN-20260109-BUY-001` do not match.
_PREFIXED_NUMBER = re.compile(
    r"(?P<prefix>[^\d+-]*?)(?P<number>[-+]?[\d,]*\d(?:\.\d+)?)(?P<suffix>%?)"
)


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


def _is_a_quantity(prefix: str, whole: str) -> bool:
    """Whether these digits are a figure to be read, rather than a code to be matched.

    A label stands apart from its amount ("USD 450000.00"); digits welded to letters are
    an identifier, and grouping one turned `ISIN US0378331005` into `US378,331,005`. A
    leading zero says the same thing, and grouping would also drop the zero.
    """
    if prefix and not prefix[-1].isspace() and prefix[-1].isalnum():
        return False
    if not whole.isdigit():
        return False
    return whole == "0" or whole == whole.lstrip("0")


def group_digits(value: object) -> str:
    """Group thousands without changing the number in any other way.

    :func:`format_money` quantizes to a fixed number of decimals. That is right for a
    figure Render decides the precision of, and wrong for one it is only passing
    through: rounding a quantity, a price or an exchange rate to two places would be
    Render altering a number an owning service decided, which is exactly the line the
    service is not supposed to cross.

    This changes presentation only. The integer part gains separators; the sign, the
    decimals as supplied, a currency prefix and a trailing percent sign all survive
    untouched, and a value that is not a number is returned as its own text.

    The prefix matters: producers send amounts both bare (``450000.00``) and labelled
    (``USD 450000.00``), and a grouping that only understood the bare form left every
    labelled amount on the page exactly as it arrived.
    """
    match = _PREFIXED_NUMBER.fullmatch(str(value).strip())
    if match is None:
        return str(value)

    number = match["number"]
    whole, separator, fraction = number.lstrip("+-").replace(",", "").partition(".")
    if not _is_a_quantity(match["prefix"], whole):
        return str(value)

    sign = "-" if number.startswith("-") else ""
    return f"{match['prefix']}{sign}{int(whole):,}{separator}{fraction}{match['suffix']}"
