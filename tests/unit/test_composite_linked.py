"""Strict admission and adversarial controls over the sealed Report r4 dataset."""

import copy
import json
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from app.contracts.composite_linked import LinkedColumn
from app.contracts.composite_review import CompositeCell, CompositeColumn
from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.linked_tables import LINKED_TABLE_COLUMNS
from app.services.composite_workbook.presentation import display_cell
from app.services.composite_workbook.rendering import _validate_contract_axes, _validate_layout
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.composite_workbook.source_products import response_digest
from app.services.composite_workbook.source_values import decimal_value


def linked_data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        Path("tests/golden/composite-review/v3/report-data.json").read_bytes()
    )
    return data


def test_linked_candidate_admits_without_rewriting_any_source_text() -> None:
    data = linked_data()
    before = copy.deepcopy(data)
    content = validate_dataset(data)
    assert content.contract_version == "composite_review.v3"
    assert content.source_response == data["source_response"]
    assert data == before
    assert data["source_response"]["reconciliation_difference"] == "0E-81"


@pytest.mark.parametrize("field", ["scale", "display_rounding_mode"])
def test_source_required_column_policy_cannot_be_defaulted(field: str) -> None:
    data = linked_data()
    del data["tables"][0]["columns"][0][field]
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize("present", [False, True])
def test_optional_null_sequence_preserves_exact_absent_or_present_request_identity(
    present: bool,
) -> None:
    data = linked_data()
    if present:
        data["selection"]["source_request"]["restatement_sequence"] = None
    else:
        del data["selection"]["source_request"]["restatement_sequence"]
    before = copy.deepcopy(data)
    content = validate_dataset(data)
    assert content.selection == before["selection"]
    assert data == before
    assert ("restatement_sequence" in content.selection["source_request"]) == present


@pytest.mark.parametrize("value", [0, 1, True, "1", "null", []])
def test_competing_request_restatement_sequence_refuses(value: object) -> None:
    data = linked_data()
    data["selection"]["source_request"]["restatement_sequence"] = value
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_uncaptured_value_and_nullable_source_identity_have_distinct_reasons() -> None:
    data = linked_data()
    validate_dataset(data)
    identity = data["tables"][2]["rows"][0]["cells"]["calculation_id"]
    assert identity["canonical_value"] is None
    assert identity["reason_codes"] == ["SOURCE_IDENTITY_NOT_PROVIDED"]
    uncaptured = data["tables"][6]["rows"][0]["cells"]["value"]
    assert uncaptured["reason_codes"] == ["SOURCE_PRODUCT_NOT_CAPTURED"]
    uncaptured["reason_codes"] = ["SOURCE_IDENTITY_NOT_PROVIDED"]
    with pytest.raises(ValueError, match="availability_conflict"):
        validate_dataset(data)


def rehash(data: dict[str, Any]) -> None:
    digest = response_digest(data["source_response"])
    data["source_response_digest"] = data["selection"]["response_digest"] = digest


@pytest.mark.parametrize("index", range(7))
@pytest.mark.parametrize("change", ["table", "column", "row", "duplicate_row", "extra_column"])
def test_complete_table_matrix_refuses_omitted_or_extra_data(index: int, change: str) -> None:
    data = linked_data()
    table = data["tables"][index]
    if change == "table":
        del data["tables"][index]
    elif change == "column":
        del table["columns"][-1]
    elif change == "row":
        del table["rows"][-1]
    elif change == "duplicate_row":
        table["rows"].append(copy.deepcopy(table["rows"][0]))
    else:
        column = copy.deepcopy(table["columns"][0])
        column["column_id"] = "extra"
        table["columns"].append(column)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    [
        "tenant",
        "currency",
        "fee",
        "metric",
        "method",
        "calculation",
        "digest",
        "selection_digest",
        "fingerprint",
        "engine",
        "window_missing",
        "window_reordered",
        "materialization_duplicate",
        "window_pin",
        "member_missing",
        "member_duplicate",
        "period_missing",
        "period_duplicate",
        "participation",
        "period_horizon",
        "period_pin",
        "source_authority_missing_field",
        "source_authority_extra",
        "status",
        "source_extra",
        "numeric_return",
        "not_finite",
        "too_precise",
        "too_large_exponent",
        "old_selector",
        "return_products",
        "authority_claim",
        "uncaptured_zero",
        "uncaptured_missing",
    ],
)
def test_selector_source_and_authority_corruptions_refuse(change: str) -> None:
    data = linked_data()
    selection, source = data["selection"], data["source_response"]
    if change == "tenant":
        selection["tenant_id"] = "foreign"
    elif change in {"currency", "fee", "metric", "method", "calculation"}:
        field = {
            "currency": "reporting_currency",
            "fee": "return_view",
            "metric": "metric_id",
            "method": "method",
            "calculation": "calculation_id",
        }[change]
        selection["source_request"][field] = {
            "currency": "SGD",
            "fee": "NET_ACTUAL",
            "calculation": "00000000-0000-4000-8000-000000000001",
        }.get(change, "OTHER")
    elif change in {"digest", "selection_digest"}:
        if change == "digest":
            data["source_response_digest"] = "sha256:" + "0" * 64
        else:
            selection["response_digest"] = "sha256:" + "0" * 64
    elif change in {"fingerprint", "engine"}:
        field = "calculation_fingerprint" if change == "fingerprint" else "engine_version"
        selection[field] = "sha256:" + "0" * 64 if change == "fingerprint" else "OTHER"
    elif change == "window_missing":
        selection["windows"].pop()
    elif change == "window_reordered":
        selection["windows"].reverse()
    elif change == "materialization_duplicate":
        selection["source_request"]["materialization_ids"][1] = selection["source_request"][
            "materialization_ids"
        ][0]
    elif change == "window_pin":
        selection["windows"][0]["source_cut_id"] = "OTHER"
    elif change == "member_missing":
        source["members"].pop()
    elif change == "member_duplicate":
        source["members"].append(copy.deepcopy(source["members"][0]))
    elif change == "period_missing":
        source["periods"].pop()
    elif change == "period_duplicate":
        source["periods"].append(copy.deepcopy(source["periods"][0]))
    elif change == "participation":
        source["members"][0]["participating_period_count"] = 1
    elif change == "period_horizon":
        source["periods"][0]["period_end"] = "2026-01-30"
    elif change == "period_pin":
        source["periods"][0]["restatement_version"] = "OTHER"
    elif change == "source_authority_missing_field":
        del source["periods"][0]["source_authority_identity"]["source_digest"]
    elif change == "source_authority_extra":
        source["periods"][0]["source_authority_identity"]["official"] = True
    elif change in {"status", "source_extra"}:
        source["status" if change == "status" else "official"] = "READY"
    elif change in {"numeric_return", "not_finite", "too_precise", "too_large_exponent"}:
        source["cumulative_return"] = {
            "numeric_return": 0.0302,
            "not_finite": "NaN",
            "too_precise": "0." + "1" * 255,
            "too_large_exponent": "1E1001",
        }[change]
    elif change == "old_selector":
        selection["methodology"] = "TWR"
    elif change == "return_products":
        data["source_products"] = []
    elif change == "authority_claim":
        data["report_facts"]["authority"] = {"availability": "AVAILABLE"}
    elif change == "uncaptured_zero":
        data["report_facts"]["uncaptured"][0]["value"] = "0"
    else:
        data["report_facts"]["uncaptured"].pop()
    if change not in {"digest", "selection_digest"}:
        rehash(data)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    [
        "factor_text",
        "factor_percent",
        "count_portfolio",
        "money_currency",
        "double_conversion",
        "contribution_percent",
        "source_value",
        "source_pointer",
        "leading_zero",
        "out_of_range",
        "report_fact_financial",
        "extra_cell",
        "availability",
        "reasons",
        "canonical_zero",
    ],
)
def test_exact_pointer_and_unit_policy_refuses(change: str) -> None:
    data = linked_data()
    table = data["tables"][2]
    if change == "factor_text":
        table["columns"][7]["value_type"] = "TEXT"
    elif change == "factor_percent":
        table["columns"][7]["display_unit"] = "PERCENT"
    elif change == "count_portfolio":
        data["tables"][1]["columns"][2]["unit"] = "PORTFOLIO_COUNT"
    elif change == "money_currency":
        table["columns"][4]["currency"] = "SGD"
    elif change == "double_conversion":
        table["columns"][7]["display_conversion"] = "RATIO_TO_PERCENT_DISPLAY"
    elif change == "contribution_percent":
        table["columns"][6]["display_unit"] = "PERCENT"
    else:
        cell = table["rows"][0]["cells"]["linked_contribution"]
        if change == "source_value":
            cell["canonical_value"] = "0"
        elif change in {"source_pointer", "leading_zero", "out_of_range", "report_fact_financial"}:
            cell["source_pointer"] = {
                "source_pointer": "/source_response/periods/1/linked_contribution",
                "leading_zero": "/source_response/periods/00/linked_contribution",
                "out_of_range": "/source_response/periods/999/linked_contribution",
                "report_fact_financial": "/report_facts/disclosures/0/text",
            }[change]
        elif change == "extra_cell":
            table["rows"][0]["cells"]["extra"] = copy.deepcopy(cell)
        elif change == "availability":
            cell["availability"] = "UNAVAILABLE"
        elif change == "reasons":
            cell["reason_codes"] = ["OTHER"]
        else:
            data["tables"][0]["rows"][0]["cells"]["reconciliation_difference"][
                "canonical_value"
            ] = "0"
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "table,column,expected",
    [(2, 7, "1.009983579640"), (1, 2, "2"), (2, 4, "100.00 USD"), (2, 5, "50.00%")],
)
def test_linked_display_keeps_factor_count_money_and_return_units_distinct(
    table: int, column: int, expected: str
) -> None:
    data = linked_data()["tables"][table]
    policy = LinkedColumn.model_validate(data["columns"][column])
    cell = CompositeCell.model_validate(data["rows"][0]["cells"][policy.column_id])
    assert display_cell(policy, cell) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0E-81", "0.000000000000 pp"),
        ("-0E-81", "-0.000000000000 pp"),
        (".5", "50.000000000000 pp"),
        ("1.", "100.000000000000 pp"),
    ],
)
def test_linked_finite_decimal_grammar_preserves_source_and_declared_display(
    value: str, expected: str
) -> None:
    data = linked_data()["tables"][0]
    policy = LinkedColumn.model_validate(data["columns"][-2])
    raw = copy.deepcopy(data["rows"][0]["cells"]["reconciliation_difference"])
    raw["canonical_value"] = value
    cell = CompositeCell.model_validate(raw)
    assert display_cell(policy, cell) == expected
    assert cell.canonical_value == value


def test_new_column_units_do_not_leak_to_legacy_models() -> None:
    data = linked_data()
    for column in (data["tables"][1]["columns"][2], data["tables"][2]["columns"][7]):
        with pytest.raises(ValueError):
            CompositeColumn.model_validate(column)


@pytest.mark.parametrize("template,outer,embedded", list(product(("v1", "v2", "v3"), repeat=3)))
def test_contract_axes_never_relabel_another_version(
    template: str, outer: str, embedded: str
) -> None:
    # Controlled axis-only model; this is not a live Report order or render submission.
    payload = json.loads(Path("tests/golden/composite-review/v1/render-package.json").read_bytes())
    payload["template_version"] = template
    payload["report_data_contract_version"] = "composite_review." + outer
    payload["report_data"]["contract_version"] = "composite_review." + embedded
    package = RenderPackage.model_validate(payload)
    if template == outer == embedded:
        _validate_contract_axes(package)
    else:
        with pytest.raises(ValueError, match="contract_axes_conflict"):
            _validate_contract_axes(package)


def test_linked_layout_matches_the_same_finite_writer_and_exact_table_set() -> None:
    layout = json.loads(Path("templates/xlsx/composite-review/v3/layout.json").read_bytes())
    _validate_layout(layout, set(LINKED_TABLE_COLUMNS), version="v3")
    for name in LINKED_TABLE_COLUMNS:
        with pytest.raises(ValueError, match="table_set_invalid"):
            _validate_layout(layout, set(LINKED_TABLE_COLUMNS) - {name}, version="v3")
    with pytest.raises(ValueError, match="table_set_invalid"):
        _validate_layout(layout, set(LINKED_TABLE_COLUMNS) | {"TrailingReturns"}, version="v3")
    for field, value in (
        ("optional_tables", ["TrailingReturns"]),
        ("period_tables", ["MonthlyReturns"]),
        ("max_total_cells", 210001),
    ):
        changed = copy.deepcopy(layout)
        changed[field] = value
        with pytest.raises(TemplateRegistryError):
            _validate_layout(changed, set(LINKED_TABLE_COLUMNS), version="v3")


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        "1E1001",
        "1E-1001",
        "0." + "1" * 255,
        "1_000",
        " 1",
        "1 ",
        "١",
    ],
)
def test_linked_decimal_limits_and_ascii_grammar_fail_closed(value: str) -> None:
    with pytest.raises(ValueError, match="number_invalid"):
        decimal_value(value, linked=True)


@pytest.mark.parametrize("value", [".5", "1."])
def test_legacy_decimal_grammar_remains_unchanged(value: str) -> None:
    with pytest.raises(ValueError, match="number_invalid"):
        decimal_value(value)
    assert str(decimal_value(value, linked=True)) in {"0.5", "1"}


@pytest.mark.parametrize(
    "change", ["gap", "date_overflow", "horizon", "reverse", "empty_window_population"]
)
def test_coherent_forged_vectors_exercise_structural_guards_beyond_digest_checks(
    change: str,
) -> None:
    data = linked_data()
    selection, source = data["selection"], data["source_response"]
    if change == "gap":
        selection["windows"][1]["period_start"] = "2026-02-02"
    elif change == "date_overflow":
        selection["windows"][0]["period_end"] = "9999-12-31"
    elif change == "horizon":
        selection["source_request"]["period_end"] = source["period_end"] = "2026-03-01"
    elif change == "reverse":
        selection["windows"].reverse()
        selection["source_request"]["materialization_ids"].reverse()
        selection["source_request"]["period_start"] = source["period_start"] = "2026-02-01"
        selection["source_request"]["period_end"] = source["period_end"] = "2026-01-31"
    else:
        source["periods"] = source["periods"][:2]
        for member in source["members"]:
            member["participating_period_count"] = 1
    source["selection_manifest"]["windows"] = copy.deepcopy(selection["windows"])
    rehash(data)
    with pytest.raises(
        ValueError, match="horizon_conflict|window_order_invalid|window_population_incomplete"
    ):
        validate_dataset(data)


@pytest.mark.parametrize(
    "change",
    [
        "missing_disclosure",
        "duplicate_disclosure",
        "blank_text",
        "null_text",
        "duplicate_product",
        "false_availability",
        "unknown_product",
        "fact_extra",
    ],
)
def test_linked_facts_cannot_drop_limitations_or_create_authority(change: str) -> None:
    data = linked_data()
    facts = data["report_facts"]
    if change == "missing_disclosure":
        facts["disclosures"].pop()
    elif change == "duplicate_disclosure":
        facts["disclosures"].append(copy.deepcopy(facts["disclosures"][0]))
    elif change in {"blank_text", "null_text"}:
        facts["disclosures"][0]["text"] = " " if change == "blank_text" else None
    elif change == "duplicate_product":
        facts["uncaptured"][1] = copy.deepcopy(facts["uncaptured"][0])
    elif change == "false_availability":
        facts["uncaptured"][0]["availability"] = "AVAILABLE"
    elif change == "unknown_product":
        facts["uncaptured"][0]["product"] = "OfficialPublication"
    else:
        facts["official"] = True
    with pytest.raises(ValueError):
        validate_dataset(data)
