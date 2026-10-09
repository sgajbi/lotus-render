"""Frozen source DTOs and exact producer example remain independently verifiable."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts import composite_pooled as pooled
from app.contracts.composite_pooled_selection import PooledAnalysisSelection, PooledSourcePin
from app.main import create_app


def _semantic(value: Any) -> Any:
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _semantic(item)
            for key, item in value.items()
            if key not in {"title", "description", "$defs"}
        }
    return value


@pytest.mark.parametrize(
    "model",
    [
        PooledAnalysisSelection,
        PooledSourcePin,
        pooled.PooledCell,
        pooled.PooledColumn,
        pooled.PooledTable,
        pooled.PooledRow,
        pooled.PooledResponse,
        pooled.PooledObservation,
        pooled.PooledCashFlow,
        pooled.PooledOutcome,
    ],
)
def test_source_dtos_match_frozen_producer_constraints(model: Any) -> None:
    raw = Path("contracts/report-data/composite_review.v5.schema.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "d067fd9b356a882c0ea24b4c9ba2738f7f179883bc0e7afd4c76f950ed0944ce"
    )
    assert _semantic(model.model_json_schema()) == _semantic(
        json.loads(raw)["$defs"][model.__name__]
    )


def test_client_golden_and_openapi_retain_original_worker_package_without_null_loss() -> None:
    for path in (
        "src/app/contracts/examples/composite-review-render-package.v5.json",
        "tests/golden/composite-review/v5/render-package.json",
    ):
        raw = Path(path).read_bytes()
        assert len(raw) == 227781
        assert (
            hashlib.sha256(raw).hexdigest()
            == "13516687f3c283cadffefb6bf4a330448767ed281875dc3b16c3d6e92ac265c7"
        )
    examples = create_app().openapi()["paths"]["/renders"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    published = examples["composite_pooled_xlsx_package"]
    assert "value" not in published
    assert published["externalValue"] == (
        "https://raw.githubusercontent.com/sgajbi/lotus-render/main/"
        "src/app/contracts/examples/composite-review-render-package.v5.json"
    )
