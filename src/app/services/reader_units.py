"""Reader-value formatting from source-stated unit semantics.

Promoted on its second consumer (risk attribution joined the risk trend): one
place turns a source-precision string into the value a reader means, and the
rules never fork. A ``decimal_ratio`` is shifted two decimal places exactly
(``Decimal.scaleb`` -- digits preserved, nothing rounded, no float) and shown
as a percentage; ``unitless`` is the source string verbatim. Fields the
contract defines STRUCTURALLY as fractions of one (weight_average,
percent_contribution -- the #254 lock) shift the same way without a per-row
unit, because the contract itself is their unit statement.

Raw source strings are never replaced anywhere else: geometry and lineage keep
the source value; these helpers produce only what is printed.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from app.services.typst_values import escape_typst_string


def metric_reader_value(stated: str, unit: str) -> str | None:
    """The value as the reader means it, or None when it cannot be stated."""
    if unit == "unitless":
        return stated
    if unit != "decimal_ratio":
        return None
    return fraction_reader_value(stated)


def fraction_reader_value(stated: str) -> str | None:
    """A fraction of one as a percentage, exactly -- 0.1374 becomes 13.74%."""
    try:
        shifted = Decimal(stated).scaleb(2)
    except InvalidOperation:
        return None
    return f"{format(shifted, 'f')}%"


def period_caption(period: object) -> str:
    """The source-stated period, verbatim: name and date span, present parts only."""
    if not isinstance(period, Mapping):
        return ""
    name = stated_text(period.get("name"))
    span = " to ".join(
        text
        for text in (stated_text(period.get("start_date")), stated_text(period.get("end_date")))
        if text
    )
    return " ".join(piece for piece in (name, span) if piece)


def stated_text(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return escape_typst_string(value.strip())
    return ""
