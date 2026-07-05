from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.main import app
from app.observability.render_metrics import FORBIDDEN_METRIC_LABELS, RENDER_METRIC_CONTRACTS

CONTRACT_ROOT = Path("contracts")


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
