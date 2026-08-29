"""Scalar parsing, escaping and width helpers shared by Typst emitters.

Pure functions: deterministic output for the same input, no service state.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


def escape_typst_text(value: str) -> str:
    """Escape a value for Typst *markup* (content-block) context: ``[ ... ]``.

    Neutralises the markup control tokens so report text cannot introduce
    functions, groups or math. Not valid for string-literal context -- use
    :func:`escape_typst_string` for a value emitted between ``"`` delimiters.
    """
    escaped = value.replace("\\", "\\\\")
    for token in ("#", "{", "}", "[", "]", "$", "@"):
        escaped = escaped.replace(token, f"\\{token}")
    return escaped


def escape_typst_string(value: str) -> str:
    """Escape a value for a Typst *string literal*: ``"..."``.

    Only backslash and double-quote can change a string literal's structure;
    everything else is data. Control characters are mapped to their Typst
    string escapes so the emitted argument stays single-line and valid. Using
    :func:`escape_typst_text` here instead would leave ``"`` live (the value
    breaks out of the literal into code) while mangling ordinary ``#``/``[``
    into invalid string escapes -- so the two contexts must not share an
    escaper.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def mapping_entries(value: object) -> list[Mapping[str, object]]:
    """The mappings in a sequence, or an empty list when there is no sequence.

    Fifteen emitters open with the same pair of guards -- reject a non-sequence,
    then reject the string types that *are* sequences -- and skip non-mapping items
    inside the loop. Stating the shape once also lets a caller ask "is there
    anything to draw?" without caring which of the two ways it was absent.
    """
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def percent_width_token(value: object) -> str:
    raw = str(value).strip().replace("%", "")
    try:
        numeric = float(raw)
    except ValueError:
        return "8%"
    clamped = min(max(numeric, 8.0), 100.0)
    return f"{clamped:.2f}%"


@dataclass(frozen=True)
class BarGeometry:
    """How far a bar reaches from the zero baseline, and which way."""

    magnitude: str
    is_negative: bool


# A series that only ever moves a few basis points should not be amplified into
# full-width bars, so the domain never falls below this.
MINIMUM_BAR_DOMAIN_PCT = 1.0


def optional_percent(value: object) -> float | None:
    """The percentage as a finite number, or None when it is absent or unusable."""
    raw = str(value).strip().replace("%", "").replace(",", "")
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def performance_bar_domain(values: Iterable[object]) -> float:
    """The symmetric domain a series of returns is drawn against.

    Bars used to be scaled by a fixed ``value * 8`` clamped into ``[8%, 100%]``,
    which destroyed the data at both ends. On the annual series -38.40%, -14.20%
    and +18.40% all saturated at 100% and drew as three identical bars; on a
    monthly series moving well under 1% every bar floored at 8% and the chart was
    flat whatever the returns. Scaling to the largest absolute move in the series
    makes bar length mean something within one chart.
    """
    magnitudes = [abs(parsed) for parsed in map(optional_percent, values) if parsed is not None]
    return max([*magnitudes, MINIMUM_BAR_DOMAIN_PCT])


def performance_bar_geometry(value: object, domain: float) -> BarGeometry:
    """Where the bar for one period sits on a track scaled to ``domain``.

    An absent value draws no bar rather than a minimum-width one: "no data" and
    "no movement" are different statements, and neither is a positive return.
    """
    parsed = optional_percent(value)
    if parsed is None or domain <= 0:
        return BarGeometry(magnitude="0%", is_negative=False)
    share = min(abs(parsed) / domain, 1.0) * 100
    return BarGeometry(magnitude=f"{share:.2f}%", is_negative=parsed < 0)


def parse_percent(value: object) -> float:
    raw = str(value).strip().replace("%", "")
    try:
        parsed = float(raw)
    except ValueError:
        return 0.0
    # nan/inf parse successfully but escape the downstream clamps as bare tokens
    # (`nan%`) or crash chart maths; treat them as absent, like an unparseable value.
    return parsed if math.isfinite(parsed) else 0.0


def parse_number(value: object) -> float:
    raw = str(value).strip().replace(",", "")
    try:
        parsed = float(raw)
    except ValueError:
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def row_sequence(value: object) -> Sequence[object] | None:
    """Rows are a real sequence; strings and bytes must not iterate as rows."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return None
