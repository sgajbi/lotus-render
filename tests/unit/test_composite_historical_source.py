"""Version, hash, intent and custody refusals independent of transport integrity."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest
from historical_fixtures import CASES, ROOT, historical_package

from app.contracts.composite_historical import CompositeHistoricalContent
from app.contracts.render_package import RenderPackage
from app.main import create_app
from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)
from app.services.composite_workbook.historical_custody import validate_historical_custody
from app.services.composite_workbook.historical_source import validate_historical_source
from app.services.composite_workbook.source_cells import validate_dataset


@pytest.mark.parametrize("case", CASES)
def test_exact_producer_packages_and_sorted_replay(case: str) -> None:
    raw = gzip.decompress((ROOT / f"{case}.package.json.gz").read_bytes())
    manifest = json.loads((ROOT / Path(case).parent / "manifest.json").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == manifest["files"][f"{Path(case).name}.package.json"]
    package = RenderPackage.model_validate_json(raw)
    validate_historical_custody(package)
    for data in (package.report_data, json.loads(json.dumps(package.report_data, sort_keys=True))):
        assert validate_dataset(data).model_dump(mode="json") == data


@pytest.mark.parametrize(
    "change", ["intent", "tenant", "actor", "revision", "operation", "time", "raw"]
)
def test_rehashed_current_proof_cannot_change_binding(change: str) -> None:
    data = historical_package("v1-root-evaluated-only")["report_data"]
    proposal = data["source_months"][0]["proposal"]
    proof = proposal["operation_verification"]
    request = proof["request"]
    if change == "intent":
        request["intent_digest"] = "sha256:" + "0" * 64
    elif change == "tenant":
        request["scope"]["tenant_id"] = "foreign"
    elif change == "actor":
        request["actor_id"] = "foreign"
    elif change == "revision":
        request["revision"] = "foreign"
    elif change == "operation":
        request["operation"] = "POLICY_APPROVAL"
    elif change == "time":
        request["requested_at"] = "2026-10-10T05:00:01Z"
    else:
        proof["mapping"]["raw_original_base64"] = "eA=="
        proof["mapping"]["content_hash"] = source_content_digest(proof["mapping"])
    proof["content_hash"] = source_content_digest(proof)
    proposal["content_hash"] = source_content_digest(proposal)
    pin = data["selection"]["months"][0]
    pin["proposal_content_hash"] = proposal["content_hash"]
    pin["proposal_response_digest"] = whole_response_digest(proposal)
    data["source_months"][0]["response_digests"]["proposal"] = pin["proposal_response_digest"]
    # Test source admission before table validation so stale cells cannot explain refusal.
    typed = CompositeHistoricalContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError):
        validate_historical_source(typed, data)


@pytest.mark.parametrize(
    "change", ["null", "unknown", "mixed", "staged", "missing", "order", "duplicate"]
)
def test_incomplete_or_mixed_lineage_refused(change: str) -> None:
    data = historical_package()["report_data"]
    month = data["source_months"][0]
    proposal = month["receipt"]["approval"]["proposal"]
    if change == "null":
        proposal["operation_verification"] = None
    elif change == "unknown":
        data["selection"]["selection_version"] = "v99"
    elif change == "mixed":
        month["lineage_receipts"][-1]["product_version"] = "v1"
    elif change == "staged":
        proposal["publication_evidence_version"] = "v2"
    elif change == "missing":
        month["lineage_receipts"].pop()
    elif change == "order":
        month["lineage_receipts"].reverse()
    else:
        month["lineage_receipts"].append(month["lineage_receipts"][0])
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    ["boundary_missing", "boundary_false", "tenant", "selection", "scope", "retention", "lineage"],
)
def test_custody_scope_refusals(change: str) -> None:
    wire = historical_package()
    archive = wire["render_context"]["archive"]
    identity = archive["composite_report_identity"]
    if change == "boundary_missing":
        identity.pop("calculation_boundary")
    elif change == "boundary_false":
        identity["calculation_boundary"] = "Bank verified"
    elif change == "tenant":
        archive["tenant_id"] = "foreign"
    elif change == "selection":
        identity["selection"]["tenant_id"] = "foreign"
    elif change == "scope":
        archive["portfolio_scope"] = "portfolio"
    elif change == "retention":
        archive["retention_start_date"] = "2026-10-01"
    else:
        wire["lineage_refs"] = [wire["snapshot_id"]]
    with pytest.raises(ValueError):
        validate_historical_custody(RenderPackage.model_validate(wire))


def test_frozen_old_schema_and_layout_bytes() -> None:
    expected = {
        "contracts/report-data/composite_review.v4.schema.json": (
            "2214d2044980fc81007637e0504a46d13b2cbf10959fd2ca2198d2ed5f557e73"
        ),
        "contracts/report-data/composite_review.v6.schema.json": (
            "a2f07d927c2c181ad29b58d705d62e4db4df165a8cad5cd26c13143dadc72b5d"
        ),
        "templates/xlsx/composite-review/v4/layout.json": (
            "aa47a7d2654e44dddcbc219d02e866f7a3e3cd1bba1bfa6d54200b110aed3214"
        ),
        "templates/xlsx/composite-review/v6/layout.json": (
            "2f7a4ece866284522b52385b8181942a6c4a6b7f0e898dc9d90fb3e4ed14ec85"
        ),
    }
    for name, digest in expected.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest


def test_runtime_schema_is_exact_sealed_report_schema() -> None:
    contract = Path("contracts/report-data/composite_review.v7.schema.json").read_bytes()
    packaged = Path(
        "src/app/contracts/historical_schemas/composite_review.v7.schema.json"
    ).read_bytes()
    manifest = json.loads((ROOT / "schema-fit-r4-manifest.json").read_bytes())
    assert contract == packaged
    assert (
        hashlib.sha256(contract).hexdigest() == manifest["files"]["composite_review.v7.schema.json"]
    )


def test_external_client_example_preserves_exact_factory_bytes_and_boundary() -> None:
    client = Path("src/app/contracts/examples/composite-review-render-package.v7.json").read_bytes()
    assert client == gzip.decompress((ROOT / "v2-root-evaluated-only.package.json.gz").read_bytes())
    assert client == Path("tests/golden/composite-review/v7/render-package.json").read_bytes()
    examples = create_app().openapi()["paths"]["/renders"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    example = examples["composite_historical_xlsx_package"]
    assert "value" not in example
    assert example["externalValue"].endswith("composite-review-render-package.v7.json")
    assert "authored unit transport fixtures" in example["description"]
    assert "no durable capture" in example["description"]


def test_missing_archive_identity_refuses() -> None:
    wire = historical_package()
    wire["render_context"].pop("archive")
    with pytest.raises(ValueError, match="archive_identity_required"):
        validate_historical_custody(RenderPackage.model_validate(wire))
