"""Exact schema/custody/pointer refusals, isolated from source availability."""

import hashlib
import json
from pathlib import Path

import pytest
from source_context_fixtures import source_context_package

from app.contracts.composite_source_context import CompositeSourceContextContent
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.composite_workbook.source_context import (
    _validate_capture_capacity,
    _validate_definition,
    _validate_intervals,
    _validate_membership_capture,
    _validate_memberships,
    _validate_parent,
    validate_source_context,
)
from app.services.composite_workbook.source_context_custody import validate_source_context_custody


@pytest.mark.parametrize("case", ["original", "corrected"])
def test_exact_packages_and_sorted_retained_data(case: str) -> None:
    package = RenderPackage.model_validate(source_context_package(case))
    validate_source_context_custody(package)
    for data in (package.report_data, json.loads(json.dumps(package.report_data, sort_keys=True))):
        assert validate_dataset(data).model_dump(mode="json") == data
    assert len(package.report_data["tables"]) == 15


def test_packaged_schema_equals_public_frozen_schema() -> None:
    public = Path("contracts/report-data/composite_review.v8.schema.json").read_bytes()
    packaged = Path(
        "src/app/contracts/source_context_schemas/composite_review.v8.schema.json"
    ).read_bytes()
    assert public == packaged
    assert (
        hashlib.sha256(public).hexdigest()
        == "d64d0f3cd782b5c8a65c06c82ddc22f9ff23ec98709435fd7676908ccb5cd2f4"
    )


def test_later_window_keeps_truthful_unavailable_si_without_products_or_history() -> None:
    wire = source_context_package("later-window")
    content = validate_dataset(wire["report_data"])
    assert isinstance(content, CompositeSourceContextContent)
    validate_source_context_custody(RenderPackage.model_validate(wire))
    si = next(t for t in content.tables if t.table_id == "SinceInception")
    cell = si.rows[0].cells["return"]
    assert cell.canonical_value is None
    assert cell.availability == "UNAVAILABLE"
    assert cell.reason_codes == ["SOURCE_VECTOR_BEGINS_AFTER_PINNED_INCEPTION"]
    assert not content.source_products and not content.supplied_memberships


def test_history_without_si_is_same_contract() -> None:
    wire = source_context_package()
    data = wire["report_data"]
    data["source_context"]["since_inception"] = False
    wire["render_context"]["archive"]["composite_report_identity"]["source_context"][
        "since_inception"
    ] = False
    data["report_facts"].pop("since_inception")
    data["tables"] = [t for t in data["tables"] if t["table_id"] != "SinceInception"]
    validate_dataset(data)
    validate_source_context_custody(RenderPackage.model_validate(wire))


def test_positive_si_without_supplemental_products_or_history() -> None:
    wire = source_context_package("si-positive")
    content = validate_dataset(wire["report_data"])
    assert isinstance(content, CompositeSourceContextContent)
    validate_source_context_custody(RenderPackage.model_validate(wire))
    assert content.report_facts["since_inception"]["availability"] == "AVAILABLE"
    assert not content.source_products and not content.supplied_memberships


@pytest.mark.parametrize("change", ["tenant", "definition", "revision", "endpoint", "digest"])
def test_rehashed_membership_still_requires_exact_capture_binding(change: str) -> None:
    typed = CompositeSourceContextContent.model_validate_json(
        json.dumps(source_context_package()["report_data"])
    )
    capture = typed.supplied_memberships[0]
    _validate_membership_capture(typed, capture)
    if change == "endpoint":
        capture.endpoint += "?latest=true"
    elif change == "digest":
        capture.pin.response_digest = "sha256:" + "0" * 64
    else:
        field = {
            "tenant": "tenant_id",
            "definition": "definition_version",
            "revision": "membership_revision",
        }[change]
        capture.source_response[field] = "foreign"
        capture.source_response["content_hash"] = source_content_digest(capture.source_response)
        capture.pin.content_hash = capture.source_response["content_hash"]
        capture.source_response_digest = whole_response_digest(capture.source_response)
        capture.pin.response_digest = capture.source_response_digest
    with pytest.raises(ValueError):
        _validate_membership_capture(typed, capture)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_every_window_history_join_and_no_unreferenced_attachment(change: str) -> None:
    typed = CompositeSourceContextContent.model_validate_json(
        json.dumps(source_context_package("corrected")["report_data"])
    )
    vectors = [typed.selection, *(p.pin.selection for p in typed.source_products)]
    _validate_memberships(typed, vectors)
    if change == "missing":
        vectors[0]["windows"][0]["membership_content_hash"] = "sha256:" + "0" * 64
    elif change == "extra":
        for vector in vectors:
            for window in vector["windows"]:
                window["membership_content_hash"] = typed.supplied_memberships[0].pin.content_hash
    else:
        typed.supplied_memberships[1] = typed.supplied_memberships[0]
    with pytest.raises(ValueError):
        _validate_memberships(typed, vectors)


def test_definition_v1_recursive_hash_exclusion_does_not_become_membership_policy() -> None:
    typed = CompositeSourceContextContent.model_validate_json(
        json.dumps(source_context_package()["report_data"])
    )
    capture = typed.definition
    capture.source_response["retained_extra"] = {
        "content_hash": "sha256:" + "a" * 64,
        "value": "literal",
    }
    capture.source_response["content_hash"] = source_content_digest(
        capture.source_response, recursive=True
    )
    capture.pin.content_hash = capture.source_response["content_hash"]
    capture.source_response_digest = whole_response_digest(capture.source_response)
    capture.pin.response_digest = capture.source_response_digest
    _validate_definition(typed)
    capture.source_response["content_hash"] = source_content_digest(capture.source_response)
    capture.pin.content_hash = capture.source_response["content_hash"]
    capture.source_response_digest = whole_response_digest(capture.source_response)
    capture.pin.response_digest = capture.source_response_digest
    with pytest.raises(ValueError):
        _validate_definition(typed)


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "bool",
        "definition_v2",
        "product_kind",
        "raw_number",
        "context_pin",
        "membership_pin",
        "product_digest",
        "engine",
    ],
)
def test_source_tampering_refuses_before_projection(change: str) -> None:
    data = source_context_package()["report_data"]
    if change == "unknown":
        data["inferred_authority"] = True
    elif change == "bool":
        data["source_context"]["since_inception"] = "true"
    elif change == "definition_v2":
        data["definition"]["source_response"]["product_version"] = "v2"
    elif change == "product_kind":
        data["source_products"][0]["pin"]["kind"] = "SINCE_INCEPTION_RETURN"
    elif change == "raw_number":
        data["source_response"]["cumulative_return"] = 1
    elif change == "context_pin":
        data["source_context"]["definition"]["definition_version"] = "latest"
    elif change == "membership_pin":
        data["source_context"]["memberships"][0]["content_hash"] = "sha256:" + "0" * 64
    elif change == "product_digest":
        data["source_products"][0]["source_response_digest"] = "sha256:" + "0" * 64
    else:
        data["source_products"][0]["pin"]["selection"]["engine_version"] = "foreign"
    with pytest.raises(ValueError):
        typed = CompositeSourceContextContent.model_validate_json(json.dumps(data))
        validate_source_context(typed, data)


@pytest.mark.parametrize(
    "change", ["tenant", "currency", "version", "endpoint", "inception", "termination"]
)
def test_rehashed_definition_still_requires_original_scope_and_horizon(change: str) -> None:
    data = source_context_package()["report_data"]
    capture = data["definition"]
    raw = capture["source_response"]
    if change == "endpoint":
        capture["endpoint"] += "?latest=true"
    else:
        field, value = {
            "tenant": ("tenant_id", "foreign"),
            "currency": ("reporting_currency", "SGD"),
            "version": ("definition_version", "d2"),
            "inception": ("inception_date", "2026-01-02"),
            "termination": ("termination_date", "2026-11-30"),
        }[change]
        raw[field] = value
    raw["content_hash"] = source_content_digest(raw, recursive=True)
    capture["pin"]["content_hash"] = raw["content_hash"]
    capture["source_response_digest"] = whole_response_digest(raw)
    capture["pin"]["response_digest"] = capture["source_response_digest"]
    typed = CompositeSourceContextContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError):
        _validate_definition(typed)


@pytest.mark.parametrize(
    "change", ["missing_parent", "self_parent", "nested_parent", "missing_impact", "reverse_impact"]
)
def test_direct_parent_boundary(change: str) -> None:
    typed = CompositeSourceContextContent.model_validate_json(
        json.dumps(source_context_package("corrected")["report_data"])
    )
    by_revision = {m.pin.membership_revision: m for m in typed.supplied_memberships}
    raw = typed.supplied_memberships[1].source_response
    _validate_parent(raw, by_revision)
    if change == "missing_parent":
        by_revision.clear()
    elif change == "self_parent":
        raw["supersedes_membership_revision"] = raw["membership_revision"]
    elif change == "nested_parent":
        typed.supplied_memberships[0].source_response["supersedes_membership_revision"] = "older"
    elif change == "missing_impact":
        raw["affected_from"] = None
    else:
        raw["affected_from"], raw["affected_to"] = "2026-02-01", "2026-01-01"
    with pytest.raises(ValueError):
        _validate_parent(raw, by_revision)


def test_original_intervals_and_aggregate_capture_budget() -> None:
    typed = CompositeSourceContextContent.model_validate_json(
        json.dumps(source_context_package()["report_data"])
    )
    raw = typed.supplied_memberships[0].source_response
    _validate_intervals(raw)
    raw["decisions"][0]["effective_to"] = "1900-01-01"
    with pytest.raises(ValueError):
        _validate_intervals(raw)
    _validate_capture_capacity(typed)
    typed.definition.source_response["oversized_original"] = "x" * 8_388_608
    with pytest.raises(ValueError):
        _validate_capture_capacity(typed)


@pytest.mark.parametrize(
    "change",
    [
        "si_value",
        "si_unit",
        "si_rounding",
        "si_pointer",
        "si_missing",
        "history_row",
        "history_parent",
        "history_bool",
        "history_null",
        "product_pointer",
        "primary_row",
    ],
)
def test_exact_recipe_refuses_cell_or_population_substitution(change: str) -> None:
    data = source_context_package("corrected")["report_data"]
    tables = {t["table_id"]: t for t in data["tables"]}
    si, history = tables["SinceInception"], tables["MembershipHistory"]
    if change == "si_value":
        si["rows"][0]["cells"]["return"]["canonical_value"] = "0.03"
    elif change == "si_unit":
        si["columns"][3]["display_unit"] = "PERCENTAGE_POINTS"
    elif change == "si_rounding":
        si["columns"][3]["display_decimal_places"] = 3
    elif change == "si_pointer":
        si["rows"][0]["cells"]["return"]["source_pointer"] = (
            "/source_products/0/source_response/cumulative_return"
        )
    elif change == "si_missing":
        data["tables"].remove(si)
    elif change == "history_row":
        history["rows"].pop()
    elif change == "history_parent":
        history["rows"][0]["cells"]["membership_revision"]["source_pointer"] = (
            "/supplied_memberships/1/source_response/membership_revision"
        )
    elif change == "history_bool":
        history["rows"][0]["cells"]["discretionary"]["canonical_value"] = "True"
    elif change == "history_null":
        history["rows"][0]["cells"]["effective_to"]["availability"] = "UNAVAILABLE"
    elif change == "product_pointer":
        tables["TrailingReturns"]["rows"][0]["cells"]["return"]["source_pointer"] = (
            "/source_response/cumulative_return"
        )
    else:
        tables["MonthlyReturns"]["rows"].pop()
    with pytest.raises((ValueError, KeyError)):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    ["definition", "context", "product", "revision", "tenant", "period", "lineage", "extra"],
)
def test_mixed_custody_cannot_be_substituted(change: str) -> None:
    wire = source_context_package()
    archive = wire["render_context"]["archive"]
    identity = archive["composite_report_identity"]
    if change == "definition":
        identity["definition"]["source_response_digest"] = "sha256:" + "0" * 64
    elif change == "context":
        identity["source_context"]["since_inception"] = False
    elif change == "product":
        identity["source_products"].pop()
    elif change == "revision":
        archive["report_revision_id"] = "foreign"
    elif change == "tenant":
        archive["tenant_id"] = "foreign"
    elif change == "period":
        archive["reporting_period_start"] = "2026-02-01"
    elif change == "lineage":
        wire["lineage_refs"].reverse()
    else:
        identity["approval_inferred"] = True
    with pytest.raises(ValueError):
        validate_source_context_custody(RenderPackage.model_validate(wire))
