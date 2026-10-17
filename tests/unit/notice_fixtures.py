"""Exact native Report2275b3f bytes; controlled historical fixtures, not live authority."""

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "fixtures/composite-notice-v9"


def native_bytes(name: str) -> bytes:
    raw = gzip.decompress((ROOT / (name + ".gz")).read_bytes())
    expected = json.loads((ROOT / "manifest.json").read_bytes())["files"][name]
    assert len(raw) == expected["bytes"]
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
    return raw


def native_json(name: str) -> Any:
    return json.loads(native_bytes(name))


def notice_package() -> dict[str, Any]:
    return native_json("valid-full-render-package.json")  # type: ignore[no-any-return]
