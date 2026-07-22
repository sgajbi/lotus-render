from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.main import app
from app.observability.render_metrics import FORBIDDEN_METRIC_LABELS, RENDER_METRIC_CONTRACTS

CONTRACT_ROOT = Path("contracts")
GOLDEN_PRODUCER_FIXTURES = Path("tests/golden/producer-fixtures.v1.json")


def _load_contract(name: str) -> dict[str, Any]:
    payload = json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)


def test_supported_features_cover_template_registry_and_openapi_paths() -> None:
    contract = _load_contract("render-supported-features.v1.json")
    registry = TemplateRegistry.load_from_directory(Path(Settings().template_registry_path))
    manifests = registry.export_manifests()
    declared_templates = {
        (entry["template_id"], entry["template_version"]): entry for entry in contract["templates"]
    }

    assert set(contract["api_paths"]).issubset(set(app.openapi()["paths"]))
    assert len(declared_templates) == len(manifests)
    for manifest in manifests:
        key = (manifest["template_id"], manifest["template_version"])
        declared = declared_templates[key]
        assert declared["report_types"] == manifest["supported_report_types"]
        assert (
            declared["report_data_contract_versions"]
            == manifest["supported_report_data_contract_versions"]
        )
        assert declared["locales"] == manifest["supported_locales"]
        assert declared["brand_variants"] == manifest["supported_brand_variants"]
        assert declared["output_formats"] == manifest["supported_output_formats"]
        assert declared["status"] == manifest["status"]


def test_source_contracts_cover_all_manifest_contract_versions() -> None:
    source_contract = _load_contract("render-source-contracts.v1.json")
    contract_entries = cast(list[dict[str, str]], source_contract["contracts"])
    declared = {
        entry["report_data_contract_version"]
        for entry in contract_entries
        if entry["status"] == "active"
    }
    registry = TemplateRegistry.load_from_directory(Path(Settings().template_registry_path))
    required: set[str] = set()
    for manifest in registry.export_manifests():
        required.update(cast(list[str], manifest["supported_report_data_contract_versions"]))

    assert required == declared
    for entry in contract_entries:
        assert entry["source_owner"]
        assert entry["source_repository"]
        assert entry["source_path"]
        assert entry["compatibility_policy"] == "exact-version"


def test_golden_samples_resolve_to_committed_packages_and_artifacts() -> None:
    registry = TemplateRegistry.load_from_directory(Path(Settings().template_registry_path))
    fixture_manifest = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    fixtures = {
        (entry["template_id"], entry["template_version"], entry["golden_sample_id"]): entry
        for entry in fixture_manifest["fixtures"]
    }
    advertised_samples: set[tuple[str, str, str]] = set()

    for manifest in registry.export_manifests():
        template_id = cast(str, manifest["template_id"])
        template_version = cast(str, manifest["template_version"])
        for golden_sample_id in cast(list[str], manifest["golden_sample_ids"]):
            key = (template_id, template_version, golden_sample_id)
            advertised_samples.add(key)
            fixture = fixtures[key]
            package_path = Path(cast(str, fixture["package_path"]))
            expected_pdf_path = Path(cast(str, fixture["expected_pdf_path"]))

            sample_root = Path("tests/golden") / template_id / template_version
            assert package_path.is_relative_to(sample_root)
            assert expected_pdf_path.is_relative_to(sample_root)
            assert package_path.name == "render-package.json"
            assert expected_pdf_path.name == "expected.pdf"
            assert package_path.exists()
            assert expected_pdf_path.exists()
            assert (
                json.loads(package_path.read_text(encoding="utf-8"))["template_id"] == template_id
            )
            assert expected_pdf_path.read_bytes().startswith(b"%PDF")

    assert set(fixtures) == advertised_samples


def test_golden_producer_fixtures_cover_active_source_contracts() -> None:
    source_contract = _load_contract("render-source-contracts.v1.json")
    contract_entries = cast(list[dict[str, Any]], source_contract["contracts"])
    active_contract_versions = {
        entry["report_data_contract_version"]
        for entry in contract_entries
        if entry["status"] == "active"
    }
    fixture_manifest = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    fixture_contract_versions = {
        entry["report_data_contract_version"] for entry in fixture_manifest["fixtures"]
    }

    assert fixture_manifest["manifest_version"] == "render_golden_producer_fixtures.v1"
    assert fixture_contract_versions == active_contract_versions
    for fixture in fixture_manifest["fixtures"]:
        assert fixture["producer_repository"] == "sgajbi/lotus-report"
        assert fixture["producer_source_paths"]
        assert fixture["provenance"]

    for entry in contract_entries:
        if entry["status"] != "active" or "accepted_source_contract_versions" not in entry:
            continue
        fixture_source_versions = {
            fixture.get("source_contract_version", fixture["report_data_contract_version"])
            for fixture in fixture_manifest["fixtures"]
            if fixture["report_data_contract_version"] == entry["report_data_contract_version"]
        }
        assert set(entry["accepted_source_contract_versions"]) <= fixture_source_versions


def test_data_product_trust_contract_references_live_paths_and_metrics() -> None:
    trust_contract = _load_contract("render-data-product-trust.v1.json")
    paths = set(app.openapi()["paths"])
    implemented_metrics = {metric.name for metric in RENDER_METRIC_CONTRACTS if metric.implemented}

    for output in trust_contract["outputs"]:
        assert output["api_path"] in paths
        for metric_name in output.get("metric_families", []):
            assert metric_name in implemented_metrics
        forbidden = set(output.get("forbidden_labels", []))
        assert forbidden <= FORBIDDEN_METRIC_LABELS
    assert trust_contract["privacy_policy"]["raw_report_data_persisted"] is False
    assert trust_contract["privacy_policy"]["high_cardinality_metric_labels_allowed"] is False
