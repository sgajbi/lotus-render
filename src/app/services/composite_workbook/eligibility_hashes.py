"""Frozen Manage content hashing and independent whole-response receipt binding."""

import hashlib
import json
from typing import Any


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def whole_response_digest(source: dict[str, Any]) -> str:
    """Include all nested hashes, metadata and exact source scalar spelling."""
    return _digest(source)


def _without_nested_hashes(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_nested_hashes(item)
            for key, item in value.items()
            if key != "content_hash"
        }
    if isinstance(value, list):
        return [_without_nested_hashes(item) for item in value]
    return value


def source_content_digest(source: dict[str, Any], *, recursive: bool = False) -> str:
    """Use only the product-specific exclusion policy frozen by the source owner."""
    retained = (
        _without_nested_hashes(source)
        if recursive
        else {key: item for key, item in source.items() if key != "content_hash"}
    )
    return _digest(retained)
