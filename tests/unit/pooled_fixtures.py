"""Actual emitted Report packages with immutable byte provenance."""

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

CASES = (
    "original",
    "corrected",
    "ambiguous",
    "elected_fallback",
    "one_sided",
    "work_limit",
    "zero",
)


def producer_package(kind: str = "original") -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1] / "fixtures/composite-pooled-v5/producer-packages.json"
    )
    bundle = json.loads(path.read_bytes())
    assert (
        bundle["packet_sha256"]
        == "67a5da54d746051b5318cf8d856f804b4e8d3daa05cd3418e2e5aff0ee4cd87f"
    )
    item = bundle["packages"][kind]
    raw = gzip.decompress(base64.b64decode(item["gzip_base64"]))
    assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
    data: dict[str, Any] = json.loads(raw)
    return data
