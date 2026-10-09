"""Bounded selector examples for v4 contract and custody tests; not live source proof."""

import base64
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

DIGEST = "sha256:" + "a" * 64


def producer_package(kind: str = "evaluated_only") -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "composite-eligibility-v4"
    if kind.startswith("actual_"):
        receipt = json.loads((path / "actual-published-worker-packages.json").read_bytes())
        version = kind.removeprefix("actual_")
        item = next(
            item for item in receipt["packages"] if item["definition_product_version"] == version
        )
        raw = gzip.decompress(base64.b64decode(item["payload"]))
        expected = {
            "v1": (282381, "2bec5a2d759201c7bd85bbe0d22d1f58855c755fc10e7d7996d3abfbbfac59bd"),
            "v2": (300045, "6658fbc94eff3a076292a54b41e1261709629ea54dd4aed2590327e8461a7f4a"),
        }[version]
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == expected
        actual: dict[str, Any] = json.loads(raw)
        return actual
    package: dict[str, Any] = json.loads(
        (path / f"{kind}-render-package.json").read_text(encoding="utf-8")
    )
    return package


def selector(kind: str = "EVALUATED_ONLY") -> dict[str, Any]:
    pin: dict[str, Any] = {
        "evidence_kind": kind,
        "month": "2026-08",
        "evaluation_revision": "evaluation-august",
        "proposal_content_hash": DIGEST,
        "parent_membership_revision": "membership-parent",
        "parent_membership_content_hash": DIGEST,
        "source_cut_id": "cut-august",
    }
    if kind == "EVALUATED_ONLY":
        pin["proposal_response_digest"] = DIGEST
    else:
        pin.update(
            approval_content_hash=DIGEST,
            receipt_content_hash=DIGEST,
            receipt_response_digest=DIGEST,
            membership_revision="membership-august",
            membership_content_hash=DIGEST,
            membership_response_digest=DIGEST,
            attestation_version="universe-august",
            universe_content_hash=DIGEST,
            universe_response_digest=DIGEST,
            parent_response_digest=DIGEST,
            publication_sequence=1,
            publication_response_digest=DIGEST,
        )
    return {
        "tenant_id": "tenant-test",
        "composite_id": "composite-test",
        "definition_version": "definition-test",
        "reporting_currency": "USD",
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "months": [pin],
    }
