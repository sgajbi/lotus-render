"""Versioned source-product authority, pin coherence and unchanged v1 admission."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.composite_products import CompositeProductsContent
from app.contracts.composite_review import CompositeReviewContent
from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.rendering import _validate_contract_axes, _validate_layout
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.composite_workbook.source_products import response_digest


def _data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        Path("tests/golden/composite-review/v2/report-data.json").read_text()
    )
    return data


def _product(data: dict[str, Any]) -> dict[str, Any]:
    product: dict[str, Any] = data["source_products"][0]
    return product


def _rehash_product(data: dict[str, Any]) -> None:
    product = _product(data)
    digest = response_digest(product["source_response"])
    product["source_response_digest"] = digest
    product["pin"]["selection"]["response_digest"] = digest


def test_v2_preserves_raw_sources_and_v1_has_no_product_semantics() -> None:
    data = _data()
    before = copy.deepcopy(data)
    content = validate_dataset(data)
    assert isinstance(content, CompositeProductsContent)
    assert data == before
    assert content.source_products[0].source_response == data["source_response"]
    legacy = json.loads(Path("tests/golden/composite-review/v1/report-data.json").read_text())
    assert isinstance(validate_dataset(legacy), CompositeReviewContent)
    legacy["source_products"] = data["source_products"]
    with pytest.raises(ValueError):
        validate_dataset(legacy)


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "excess",
        "duplicate",
        "kind",
        "endpoint",
        "method",
        "digest",
        "selection_digest",
        "tenant",
        "currency",
        "fee",
        "methodology",
        "months",
        "calendar",
        "year_bool",
        "old_pin",
        "missing_period",
        "source_status",
        "numeric_return",
        "text_return",
    ],
)
def test_bad_product_admission_refuses(change: str) -> None:
    data = _data()
    product = _product(data)
    selection = product["pin"]["selection"]
    if change == "empty":
        data["source_products"] = []
    elif change == "excess":
        data["source_products"] *= 9
    elif change == "duplicate":
        data["source_products"].append(copy.deepcopy(product))
    elif change in {"kind", "endpoint", "method"}:
        (product["pin"] if change == "kind" else product)[change] = "UNKNOWN"
    elif change == "digest":
        product["source_response_digest"] = "sha256:" + "0" * 64
    elif change == "selection_digest":
        selection["response_digest"] = "sha256:" + "0" * 64
    elif change == "tenant":
        selection["tenant_id"] = "another-tenant"
    elif change == "currency":
        selection["reporting_currency"] = "SGD"
    elif change == "fee":
        selection["return_view"] = "NET_MODEL_FEE"
    elif change == "methodology":
        selection["methodology"] = "another-method"
    elif change == "months":
        product["pin"]["months"] = 1
    elif change in {"calendar", "year_bool"}:
        product["pin"] = {
            "kind": "CALENDAR_RETURN",
            "product_key": "calendar",
            "year": True if change == "year_bool" else 2026,
            "selection": selection,
        }
    elif change == "old_pin":
        selection["windows"][0]["definition_content_hash"] = "sha256:" + "1" * 64
        product["source_response"]["selection_manifest"]["windows"] = copy.deepcopy(
            selection["windows"]
        )
        _rehash_product(data)
    elif change == "missing_period":
        product["source_response"]["periods"].pop()
        _rehash_product(data)
    elif change == "source_status":
        product["source_response"]["status"] = "UNKNOWN"
        _rehash_product(data)
    elif change == "numeric_return":
        product["source_response"]["cumulative_return"] = 0
        product["source_response"]["periods"][-1]["cumulative_return"] = 0
        _rehash_product(data)
    else:
        column = next(c for c in data["tables"][-1]["columns"] if c["column_id"] == "return")
        column.update(
            value_type="TEXT",
            unit="TEXT",
            display_unit="TEXT",
            display_conversion="IDENTITY",
            display_decimal_places=None,
        )
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "pointer",
    [
        "/source_products/00/source_response/cumulative_return",
        "/source_products/1/source_response/cumulative_return",
        "/source_products/-1/source_response/cumulative_return",
        "/source_products/0/source_response/periods/0/return_value",
        "/source_products/0/source_response/selection_manifest/calculation_fingerprint",
        "/source_products/0/source_response/extra/cumulative_return",
    ],
)
def test_only_exact_admitted_product_return_pointer_is_financial(pointer: str) -> None:
    data = _data()
    data["tables"][-1]["rows"][0]["cells"]["return"]["source_pointer"] = pointer
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_product_financial_value_cannot_be_laundered_through_report_facts() -> None:
    data = _data()
    cell = data["tables"][-1]["rows"][0]["cells"]["return"]
    data["report_facts"]["cumulative_return"] = cell["canonical_value"]
    cell["source_pointer"] = "/report_facts/cumulative_return"
    column = next(c for c in data["tables"][-1]["columns"] if c["column_id"] == "return")
    column.update(
        value_type="TEXT",
        unit="TEXT",
        display_unit="TEXT",
        display_conversion="IDENTITY",
        display_decimal_places=None,
    )
    with pytest.raises(ValueError, match="financial_path_not_authorized"):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    [
        "label",
        "row_id",
        "missing",
        "duplicate_row",
        "pointer_matrix",
        "reasons",
        "rounding",
        "unit",
        "absent_annual",
        "false_annual_value",
    ],
)
def test_product_table_contract_cannot_hide_or_relabel_evidence(change: str) -> None:
    data = _data()
    table = data["tables"][-1]
    if change == "label":
        table["columns"][0]["label"] = "Different financial meaning"
    elif change == "row_id":
        table["rows"][0]["row_id"] = "another-product"
    elif change == "missing":
        data["tables"].pop()
    elif change == "duplicate_row":
        table["rows"].append(copy.deepcopy(table["rows"][0]))
    elif change == "pointer_matrix":
        # Same scalar and permitted text type, but wrong agreed column provenance.
        cell = table["rows"][0]["cells"]["product"]
        cell["source_pointer"] = "/source_products/0/pin/kind"
        cell["canonical_value"] = "TRAILING_RETURN"
    elif change == "reasons":
        table["rows"][0]["cells"]["return"]["reason_codes"] = ["INVENTED_REASON"]
    elif change in {"rounding", "unit"}:
        column = next(c for c in table["columns"] if c["column_id"] == "return")
        column["display_decimal_places" if change == "rounding" else "display_unit"] = (
            3 if change == "rounding" else "PERCENTAGE_POINTS"
        )
    elif change == "absent_annual":
        data["tables"] = [t for t in data["tables"] if t["table_id"] != "AnnualReturns"]
    else:
        data["report_facts"]["uncaptured"]["AnnualReturns"]["value"] = "0.12"
        annual = next(t for t in data["tables"] if t["table_id"] == "AnnualReturns")
        annual["rows"][0]["cells"]["value"].update(
            canonical_value="0.12", availability="AVAILABLE", reason_codes=[]
        )
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_eight_products_with_full_evidence_are_accepted_and_ninth_refuses() -> None:
    data = _data()
    product = copy.deepcopy(_product(data))
    row = copy.deepcopy(data["tables"][-1]["rows"][0])
    data["source_products"] = []
    data["tables"][-1]["rows"] = []
    for index in range(8):
        item, evidence = copy.deepcopy(product), copy.deepcopy(row)
        key = f"trailing_{index}"
        item["pin"]["product_key"] = key
        evidence["row_id"] = key
        evidence["cells"]["product"]["canonical_value"] = key
        for cell in evidence["cells"].values():
            cell["source_pointer"] = cell["source_pointer"].replace(
                "/source_products/0/", f"/source_products/{index}/"
            )
        data["source_products"].append(item)
        data["tables"][-1]["rows"].append(evidence)
    content = validate_dataset(data)
    assert isinstance(content, CompositeProductsContent)
    assert len(content.source_products) == 8
    data["source_products"].append(copy.deepcopy(product))
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_product_month_must_be_complete_even_with_rehashed_consistent_source() -> None:
    data = _data()
    product = _product(data)
    selection, source = product["pin"]["selection"], product["source_response"]
    start = selection["period_start"][:8] + "02"
    selection["period_start"] = source["period_start"] = start
    selection["windows"][0]["period_start"] = start
    source["selection_manifest"]["windows"] = copy.deepcopy(selection["windows"])
    source["periods"][0]["period_start"] = start
    for member in source["periods"][0]["member_contributions"]:
        member["period_start"] = start
    _rehash_product(data)
    with pytest.raises(ValueError, match="product_month_incomplete"):
        validate_dataset(data)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_mixed_embedded_contract_template_axes_refuse(version: str) -> None:
    payload = json.loads(
        Path(f"tests/golden/composite-review/{version}/render-package.json").read_text()
    )
    _validate_contract_axes(RenderPackage.model_validate(payload))
    payload["report_data"]["contract_version"] = (
        "composite_review.v2" if version == "v1" else "composite_review.v1"
    )
    with pytest.raises(ValueError, match="contract_axes_conflict"):
        _validate_contract_axes(RenderPackage.model_validate(payload))


def test_v2_conditional_table_layout_retains_all_current_resource_limits() -> None:
    layout = json.loads(Path("templates/xlsx/composite-review/v2/layout.json").read_text())
    names = set(layout["required_tables"]) | {"MonthlyReturns"}
    _validate_layout(layout, names, version="v2")
    _validate_layout(layout, names | {"TrailingReturns"}, version="v2")
    with pytest.raises(ValueError):
        _validate_layout(layout, names | {"CalendarReturns"}, version="v2")
    layout["optional_tables"] = ["Anything"]
    with pytest.raises(TemplateRegistryError):
        _validate_layout(layout, names, version="v2")


def test_supplier_agreement_and_example_preserve_exact_provenance_bytes() -> None:
    contract = json.loads(Path("contracts/render-source-contracts.v1.json").read_text())
    entry = next(
        item
        for item in contract["contracts"]
        if item["report_data_contract_version"] == "composite_review.v2"
    )
    for path_key, digest_key in (
        ("consumer_schema_path", "agreed_schema_sha256"),
        ("agreed_layout_path", "agreed_layout_sha256"),
    ):
        raw = Path(entry[path_key]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry[digest_key]
    golden = Path("tests/golden/composite-review/v2/render-package.json").read_bytes()
    example = Path("src/app/contracts/examples/composite-review-render-package.v2.json")
    assert example.read_bytes() == golden
    assert hashlib.sha256(golden).hexdigest() == (
        "0fdda487da8db5bd651526761da2157b2adfdb1d539d1b347741a647219813b8"
    )
