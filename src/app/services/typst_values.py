"""Scalar parsing, escaping and width helpers shared by Typst emitters.

Pure functions: deterministic output for the same input, no service state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


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


def percent_width_token(value: object) -> str:
    raw = str(value).strip().replace("%", "")
    try:
        numeric = float(raw)
    except ValueError:
        return "8%"
    clamped = min(max(numeric, 8.0), 100.0)
    return f"{clamped:.2f}%"


def performance_width_token(value: object) -> str:
    raw = str(value).strip().replace("%", "")
    try:
        numeric = abs(float(raw))
    except ValueError:
        return "8%"
    clamped = min(max(numeric * 8, 8.0), 100.0)
    return f"{clamped:.2f}%"


def parse_percent(value: object) -> float:
    raw = str(value).strip().replace("%", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def parse_number(value: object) -> float:
    raw = str(value).strip().replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def row_sequence(value: object) -> Sequence[object] | None:
    """Rows are a real sequence; strings and bytes must not iterate as rows."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return None
