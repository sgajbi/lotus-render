"""Fail-closed tests reach semantic guards after recomputing transport digests."""

import copy
from typing import Any

import pytest
from pooled_fixtures import producer_package

from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.pooled_custody import validate_pooled_custody
from app.services.composite_workbook.pooled_source import response_digest
from app.services.composite_workbook.pooled_tables import pooled_tables
from app.services.composite_workbook.source_cells import validate_dataset


def repin(data: dict[str, Any]) -> None:
    source = data["source_response"]
    data["selection"]["source_bundle_digest"] = response_digest(
        source["observation"]["source_bundle"]
    )
    data["selection"]["response_digest"] = data["source_response_digest"] = response_digest(source)
    data["tables"] = pooled_tables(data)


def assign(data: dict[str, Any], pointer: str, value: Any) -> None:
    parts = pointer.split("/")
    target: Any = data
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if isinstance(target, list):
        target[int(parts[-1])] = value
    else:
        target[parts[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        ("tenant_id", "foreign"),
        ("source_response/composite_id", "other"),
        ("source_response/calculation_engine_version", "other"),
        ("source_response/input_manifest_digest", "sha256:" + "a" * 64),
        ("source_response/observation/tenant_id", "foreign"),
        ("source_response/observation/period_end", "2026-01-02"),
        ("source_response/observation/reporting_currency", "EUR"),
        ("source_response/observation/source_bundle/population_complete", False),
        ("source_response/observation/source_bundle/expected_population_count", True),
        ("source_response/observation/source_bundle/expected_portfolio_ids", ["other"]),
        ("source_response/observation/source_bundle/qualification", "INSTITUTIONAL"),
        ("source_response/observation/source_bundle/institutional_attestation", "APPROVED"),
        ("source_response/observation/source_bundle/definition_hash", ""),
        (
            "source_response/observation/source_bundle/source_pins/0/payload_digest",
            "sha256:" + "b" * 64,
        ),
        ("source_response/observation/source_bundle/compatible_pin_ids", []),
        ("source_response/observation/source_bundle/raw_source_bodies", {}),
        ("source_response/observation/source_bundle/policy/return_view", "NET_ACTUAL"),
        ("source_response/observation/source_bundle/policy/day_count_basis", "ACT/ACT"),
        ("source_response/observation/source_bundle/membership/0/status", "APPROVED"),
        ("source_response/observation/source_bundle/membership/0/effective_to", "2020-01-01"),
        ("source_response/observation/source_bundle/valuations/0/currency", "EUR"),
        ("source_response/observation/source_bundle/valuations/0/units", "PERCENT"),
        ("source_response/observation/source_bundle/valuations/0/amount", True),
        ("source_response/observation/source_bundle/valuations/0/amount", 0.1),
        ("source_response/observation/source_bundle/valuations/0/amount", "NaN"),
        ("source_response/observation/source_bundle/valuations/0/amount", "invalid-number"),
        ("source_response/observation/source_bundle/flow_coverage/0/complete", False),
        ("source_response/observation/source_bundle/flow_coverage/0/coverage_to", "2025-06-01"),
        ("source_response/observation/investor_cash_flows/0/economic_date", "2024-12-31"),
        ("source_response/outcome/diagnostics/actual_interval_end", "2026-01-02"),
        ("source_response/outcome/diagnostics/day_count_basis", "BUS/252"),
        ("source_response/outcome/diagnostics/output_units", "PERCENT"),
        ("source_response/outcome/diagnostics/convergence/converged", False),
        ("source_response/outcome/diagnostics/convergence/uniqueness_supported", False),
        ("source_response/outcome/diagnostics/convergence/non_simple_root_detected", True),
        ("source_response/outcome/diagnostics/convergence/root_count_detected", 2),
        ("source_response/outcome/diagnostics/convergence/root_count_detected", True),
        ("source_response/outcome/diagnostics/convergence/iterations", 1000000),
        ("source_response/outcome/diagnostics/convergence/rate_upper_bound", -1),
        ("source_response/outcome/original_solver_result/status", "FALLBACK_USED"),
        ("source_response/outcome/return_value", None),
    ],
)
def test_rehashed_source_conflicts_do_not_become_authority(path: str, value: Any) -> None:
    data = producer_package()["report_data"]
    assign(data, path, value)
    repin(data)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "path,value",
    [
        ("period_end", "2025-01-01"),
        ("expected_portfolio_ids", ["member-a", "member-a"]),
        ("source_pins", []),
        ("source_pins/0/expected_page_count", 2),
        ("source_pins/0/page_ids", ["page", "page"]),
        ("source_pins/0/coverage_to", "2020-01-01"),
        ("correction_of_calculation_id", "6a7fd1c2-31ba-4597-9422-36c4cee79700"),
        ("predecessor_response_digest", "sha256:" + "a" * 64),
    ],
)
def test_selector_requires_unique_complete_population_pages_and_correction_pair(
    path: str, value: Any
) -> None:
    data = producer_package()["report_data"]
    assign(data["selection"], path, value)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize("field", ["return_value", "annualized_return", "holding_period_return"])
def test_numerical_failure_is_null_never_zero(field: str) -> None:
    data = producer_package("zero")["report_data"]
    data["source_response"]["outcome"][field] = "0"
    repin(data)
    with pytest.raises(ValueError, match="REJECTED_RETURN_PRESENT"):
        validate_dataset(data)


@pytest.mark.parametrize(
    "path,value",
    [
        ("selection/fallback_policy", "REQUIRE_XIRR"),
        ("source_response/outcome/actual_method", "XIRR"),
        ("source_response/outcome/return_value", None),
        ("source_response/outcome/original_solver_result/status", "CALCULATED"),
        ("source_response/outcome/diagnostics/fallback_reason", ""),
    ],
)
def test_fallback_cannot_masquerade_as_success_or_unelected_return(path: str, value: Any) -> None:
    data = producer_package("elected_fallback")["report_data"]
    assign(data, path, value)
    repin(data)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "path,value",
    [
        ("predecessor_source_response", None),
        ("predecessor_source_response/composite_id", "other"),
        ("predecessor_source_response/observation/tenant_id", "foreign"),
        ("predecessor_source_response/observation/source_bundle/period_end", "2026-01-02"),
        ("predecessor_source_response/observation/source_bundle/raw_source_bodies", {}),
    ],
)
def test_corrected_result_cannot_drop_or_swap_full_original(path: str, value: Any) -> None:
    data = producer_package("corrected")["report_data"]
    assign(data, path, value)
    if data["predecessor_source_response"] is not None:
        data["selection"]["predecessor_response_digest"] = response_digest(
            data["predecessor_source_response"]
        )
    data["tables"] = pooled_tables(data)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "shape",
    [
        "drop_table",
        "duplicate_table",
        "drop_row",
        "duplicate_row",
        "drop_column",
        "wrong_unit",
        "wrong_pointer",
        "wrong_canonical",
        "wrong_null",
        "drop_leaf",
    ],
)
def test_complete_table_contract_refuses_omission_duplication_or_relabeling(shape: str) -> None:
    data = producer_package("corrected")["report_data"]
    table = data["tables"][0]
    if shape == "drop_table":
        data["tables"].pop()
    elif shape == "duplicate_table":
        data["tables"].append(copy.deepcopy(table))
    elif shape == "drop_row":
        table["rows"].pop()
    elif shape == "duplicate_row":
        table["rows"].append(copy.deepcopy(table["rows"][0]))
    elif shape == "drop_column":
        table["columns"].pop()
    elif shape == "wrong_unit":
        data["tables"][1]["columns"][-1]["value_type"] = "TEXT"
    elif shape == "wrong_pointer":
        table["rows"][0]["cells"]["method"]["source_pointer"] = "/source_response/schema_version"
    elif shape == "wrong_canonical":
        table["rows"][0]["cells"]["method"]["canonical_value"] = "DIETZ"
    elif shape == "wrong_null":
        table["rows"][0]["cells"]["method"]["canonical_value"] = None
    else:
        data["tables"][-1]["rows"].pop()
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "path,value",
    [
        ("render_context/archive", None),
        ("render_context/archive/composite_report_identity/selection/tenant_id", "foreign"),
        ("render_context/archive/composite_report_identity/series_digest", "wrong"),
        ("render_context/report_revision_id", ""),
        ("lineage_refs", ["other"]),
        ("render_context/archive/report_revision_id", "other"),
        ("render_context/archive/portfolio_id", "portfolio-substitute"),
        ("render_context/archive/tenant_id", "foreign"),
        ("render_context/archive/reporting_period_end", "2026-01-02"),
    ],
)
def test_custody_opaque_report_identity_and_scope_cannot_drift(path: str, value: Any) -> None:
    package = producer_package()
    assign(package, path, value)
    with pytest.raises(ValueError):
        validate_pooled_custody(RenderPackage.model_validate(package))


def test_source_hash_and_dataset_hash_are_separate_pins() -> None:
    data = producer_package()["report_data"]
    data["source_response_digest"] = "sha256:" + "a" * 64
    with pytest.raises(ValueError, match="DATASET_DIGEST_CONFLICT"):
        validate_dataset(data)
    data = producer_package()["report_data"]
    data["source_response"]["outcome"]["diagnostics"]["extra"] = float("nan")
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_additive_finite_json_booleans_null_empty_and_hostile_text_are_complete_evidence() -> None:
    data = producer_package()["report_data"]
    data["source_response"]["outcome"]["diagnostics"]["a~/b"] = {
        "flag": True,
        "empty_list": [],
        "empty_object": {},
        "null": None,
        "text": '=HYPERLINK("bad")',
        "float": 0.25,
    }
    repin(data)
    assert (
        validate_dataset(data).model_dump(mode="json")["source_response"] == data["source_response"]
    )
    evidence = next(t for t in data["tables"] if t["table_id"] == "SourceEvidence")
    cells = [
        r["cells"]["value"]
        for r in evidence["rows"]
        if "a~0~1b" in r["cells"]["value"]["source_pointer"]
    ]
    assert len(cells) == 6
    assert {c["canonical_value"] for c in cells} >= {"true", "[]", "{}", None, "0.25"}


def test_duplicate_source_pin_is_refused_before_source_admission() -> None:
    data = producer_package()["report_data"]
    data["selection"]["source_pins"].append(copy.deepcopy(data["selection"]["source_pins"][0]))
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE_PIN"):
        validate_dataset(data)


@pytest.mark.parametrize("change", ["required", "optional", "period", "missing", "unknown"])
def test_v5_layout_inventory_is_closed_and_required_tables_cannot_be_dropped(change: str) -> None:
    import json
    from pathlib import Path

    from app.services.composite_workbook.pooled_policy import validate_pooled_table_set

    layout = json.loads(Path("templates/xlsx/composite-review/v5/layout.json").read_bytes())
    names = {table["table_id"] for table in producer_package()["report_data"]["tables"]}
    validate_pooled_table_set(layout, names)
    if change in {"required", "optional", "period"}:
        layout[change + "_tables"] = ["unknown"]
    elif change == "missing":
        names.remove("Summary")
    else:
        names.add("unknown")
    with pytest.raises((ValueError, TemplateRegistryError)):
        validate_pooled_table_set(layout, names)
