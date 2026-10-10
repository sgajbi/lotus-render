"""Exact Report r3 packages; unit transport IDs do not claim durable custody."""

import gzip
import json
from pathlib import Path
from typing import Any

ROOT = Path("tests/fixtures/composite-historical-v7")
CASES = [
    path.relative_to(ROOT).as_posix().removesuffix(".package.json.gz")
    for path in sorted(ROOT.rglob("*.package.json.gz"))
]


def historical_package(case: str = "v2-correction-3-published") -> dict[str, Any]:
    result: dict[str, Any] = json.loads(
        gzip.decompress((ROOT / f"{case}.package.json.gz").read_bytes())
    )
    return result
