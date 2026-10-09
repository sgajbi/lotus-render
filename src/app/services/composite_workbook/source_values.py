"""Shared scalar resolution and bounded decimal parsing without source normalization."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_DECIMAL_TEXT = re.compile(r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d{1,4})?$")
_LINKED_DECIMAL_TEXT = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")


def resolve_pointer(dataset: dict[str, Any], pointer: str) -> Any:
    current: Any = dataset
    try:
        for token in pointer.split("/")[1:]:
            if re.search(r"~(?![01])", token):
                raise ValueError("invalid JSON pointer escape")
            key = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, list):
                if not re.fullmatch(r"0|[1-9]\d*", key):
                    raise ValueError("invalid array index")
                current = current[int(key)]
            elif isinstance(current, dict):
                current = current[key]
            else:
                raise ValueError("pointer does not name a scalar")
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("composite_cell_pointer_invalid") from exc
    return current


def decimal_value(value: str, *, linked: bool = False) -> Decimal:
    pattern = _LINKED_DECIMAL_TEXT if linked else _DECIMAL_TEXT
    if len(value) > 256 or not pattern.fullmatch(value):
        raise ValueError("composite_cell_number_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("composite_cell_number_invalid") from exc
    if not number.is_finite() or abs(number.adjusted()) > 1_000:
        raise ValueError("composite_cell_number_invalid")
    return number
