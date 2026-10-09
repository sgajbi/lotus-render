"""Supplier constraint parity and exact frozen schema provenance."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts import composite_amendment as amendment
from app.main import create_app


def _semantic(value: Any) -> Any:
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {
        ("anyOf" if key == "oneOf" else key): _semantic(item)
        for key, item in value.items()
        if key not in {"title", "description", "$defs", "discriminator"}
    }
    for key in ("required", "anyOf"):
        if key in result:
            result[key] = sorted(result[key], key=lambda item: json.dumps(item, sort_keys=True))
    return result


@pytest.mark.parametrize(
    "name",
    [
        "MonthlyBinding",
        "AmendmentEvidenceBinding",
        "MonthlyAmendment",
        "AmendmentProposal",
        "AmendmentApproval",
        "AmendmentReceipt",
        "MonthlyReceiptPin",
        "AmendmentEvaluatedPin",
        "AmendmentPublishedPin",
        "AmendmentEligibilitySelection",
        "AmendmentEvaluatedMonth",
        "AmendmentPublishedMonth",
    ],
)
def test_monthly_consumer_models_preserve_frozen_supplier_constraints(name: str) -> None:
    raw = Path("contracts/report-data/composite_review.v6.schema.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "a2f07d927c2c181ad29b58d705d62e4db4df165a8cad5cd26c13143dadc72b5d"
    )
    model = getattr(amendment, name)
    assert _semantic(model.model_json_schema()) == _semantic(json.loads(raw)["$defs"][name])


def test_client_example_preserves_nulls_and_component_qualification() -> None:
    client = Path("src/app/contracts/examples/composite-review-render-package.v6.json").read_bytes()
    golden = Path("tests/golden/composite-review/v6/render-package.json").read_bytes()
    assert client == golden
    data = json.loads(client)
    assert data["report_data"]["report_facts"]["unavailable"] is None
    assert data["snapshot_id"] == "unit-monthly-amendment-v6"
    examples = create_app().openapi()["paths"]["/renders"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    example = examples["composite_amendment_xlsx_package"]
    assert "value" not in example
    assert example["externalValue"].endswith("composite-review-render-package.v6.json")
    assert "not a Report-emitted worker package" in example["description"]
    assert "no TWR, MWR, dispersion" in example["description"]


def test_complete_root_constraints_match_supplier_contract() -> None:
    frozen = json.loads(Path("contracts/report-data/composite_review.v6.schema.json").read_bytes())
    assert _semantic(amendment.CompositeAmendmentContent.model_json_schema()) == _semantic(frozen)
