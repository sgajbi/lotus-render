"""Exact registered Report worker packages around controlled literal sources."""

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "composite-source-context-v8"
HASHES = {
    "si-positive": "36f3566b900c7237d07eadd537c424ebbb8dcdcbd93c05643edf7a626c75a4cd",
    "later-window": "24eba46610dc73eb296633277522f90cbf284e63d932926498688264e1cd6082",
    "original": "2f5c478efbd069359544acc0a705715832b1f41ce4ae76b89fa3552848f2b351",
    "corrected": "147d8b71ffcd9d0aca1aa99485abf2860aa54c8b6e03b43b0a9a7f6fba011fdd",
}


def source_context_package(case: str = "original") -> dict[str, Any]:
    raw = (ROOT / f"{case}.package.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HASHES[case]
    result: dict[str, Any] = json.loads(raw)
    return result
