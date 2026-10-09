"""Lossless, bounded JSON identity cells; financial cells never use this encoding."""

import hashlib
import json
from collections.abc import Iterator
from typing import Any

from app.services.composite_workbook.literal_writer import MAX_CELL_UTF16_UNITS

IDENTITY_STORAGE = "ordered_json_text_v1"
JSON_CHUNK_CHARACTERS = 16_000


def identity_rows(fields: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Emit ordinary JSON or a descriptor followed by ordered JSON-string fragments.

    Field names belong to Render, not the supplied context. Reserved suffixes
    cannot therefore alias a caller value or an ordinary identity field.
    """
    if any("__chunks" in key or "__chunk_" in key for key in fields):
        raise ValueError("artifact_identity_reserved_field")
    for key, value in fields.items():
        canonical = json.dumps(value, ensure_ascii=True, sort_keys=True)
        if len(canonical) <= MAX_CELL_UTF16_UNITS:
            yield key, canonical
        else:
            yield from _fragment_rows(key, canonical)


def _fragment_rows(key: str, canonical: str) -> Iterator[tuple[str, str]]:
    encoded = canonical.encode("ascii")
    count = (len(canonical) + JSON_CHUNK_CHARACTERS - 1) // JSON_CHUNK_CHARACTERS
    descriptor = {
        "encoding": IDENTITY_STORAGE,
        "count": count,
        "utf8_bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    yield f"{key}__chunks", json.dumps(descriptor, sort_keys=True)
    for index in range(count):
        fragment = canonical[index * JSON_CHUNK_CHARACTERS : (index + 1) * JSON_CHUNK_CHARACTERS]
        yield f"{key}__chunk_{index:06d}", json.dumps(fragment, ensure_ascii=True)
