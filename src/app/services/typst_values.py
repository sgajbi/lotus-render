"""Scalar parsing, escaping and width helpers shared by Typst emitters.

Pure functions: deterministic output for the same input, no service state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def escape_typst_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for token in ("#", "{", "}", "[", "]", "$", "@"):
        escaped = escaped.replace(token, f"\\{token}")
    return escaped


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
