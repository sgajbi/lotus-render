"""Content-hash exclusion must never weaken independent whole-response identity."""

import copy
import hashlib
from typing import Any

import pytest

from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)


def test_product_specific_hash_exclusion_and_whole_response_are_distinct() -> None:
    source: dict[str, Any] = {
        "content_hash": "outer",
        "nested": {"content_hash": "inner", "value": "0E-81"},
    }
    before = copy.deepcopy(source)
    expected_root = b'{"nested":{"content_hash":"inner","value":"0E-81"}}'
    expected_recursive = b'{"nested":{"value":"0E-81"}}'
    assert source_content_digest(source) == "sha256:" + hashlib.sha256(expected_root).hexdigest()
    assert source_content_digest(source, recursive=True) == (
        "sha256:" + hashlib.sha256(expected_recursive).hexdigest()
    )
    changed = copy.deepcopy(source)
    changed["nested"]["content_hash"] = "tampered"
    assert source_content_digest(changed, recursive=True) == source_content_digest(
        source, recursive=True
    )
    assert source_content_digest(changed) != source_content_digest(source)
    assert whole_response_digest(changed) != whole_response_digest(source)
    assert source == before


def test_raw_decimal_spelling_null_boolean_and_integer_do_not_collide() -> None:
    alternatives = ["0.0", "0E-81", 0, None, False]
    observed = {whole_response_digest({"value": item}) for item in alternatives}
    assert len(observed) == len(alternatives)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_json_numbers_cannot_acquire_a_receipt_identity(value: float) -> None:
    with pytest.raises(ValueError):
        whole_response_digest({"nested": {"value": value}})
