"""Report-owned cells cannot forge financial facts, source pins, units or availability."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.composite_review import CompositeCell, CompositeColumn
from app.contracts.composite_selection import CompositePinnedSelection
from app.services.composite_workbook.presentation import display_cell
from app.services.composite_workbook.source_cells import (
    decimal_value,
    resolve_pointer,
    validate_dataset,
)


def _data() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        Path("tests/golden/composite-review/v1/report-data.json").read_text(encoding="utf-8")
    )
    return value


def _rehash(data: dict[str, Any]) -> None:
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(data["source_response"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    data["source_response_digest"] = digest
    data["selection"]["response_digest"] = digest


def test_exact_report_producer_example_is_admitted_without_rewriting_source() -> None:
    data = _data()
    content = validate_dataset(data)
    assert content.source_response == data["source_response"]
    assert content.tables[0].rows[0].cells["return"].canonical_value == "0.030200000000"


def test_contradictory_source_authority_qualification_never_reaches_pinned_evidence() -> None:
    data = _data()
    data["source_response"]["selection_manifest"]["qualification"] = "OFFICIAL_ATTESTED"
    for table in data["tables"]:
        for row in table["rows"]:
            for cell in row["cells"].values():
                if cell["source_pointer"] == "/source_response/selection_manifest/qualification":
                    cell["canonical_value"] = "OFFICIAL_ATTESTED"
    _rehash(data)
    with pytest.raises(ValueError, match="source_qualification_conflict"):
        validate_dataset(data)


def test_exact_selection_wire_shape_preserves_all_pins() -> None:
    selection = _data()["selection"]
    model = CompositePinnedSelection.model_validate_json(json.dumps(selection))
    assert model.model_dump(mode="json") == selection


@pytest.mark.parametrize(
    "change", ["extra", "uuid", "date", "fee", "hash", "binding", "duplicate", "gap", "sequence"]
)
def test_invalid_selector_wire_or_vector_refuses(change: str) -> None:
    selection = _data()["selection"]
    window = selection["windows"][0]
    if change == "extra":
        selection["inferred_authority"] = "official"
    elif change == "uuid":
        selection["calculation_id"] = "fabricated"
    elif change == "date":
        selection["period_start"] = "2026-02-30"
    elif change == "fee":
        selection["return_view"] = "INFERRED"
    elif change == "hash":
        window["retained_receipt_fingerprint"] = "unhashed"
    elif change == "binding":
        window["method_binding"] = {"method_id": " "}
    elif change == "duplicate":
        selection["windows"][1]["materialization_id"] = window["materialization_id"]
    elif change == "gap":
        selection["windows"][1]["period_start"] = "2026-02-02"
    else:
        window["restatement_sequence"] = True
    with pytest.raises(ValueError):
        CompositePinnedSelection.model_validate_json(json.dumps(selection))


@pytest.mark.parametrize(
    "change",
    [
        "digest",
        "tenant",
        "series",
        "window",
        "engine",
        "missing_period",
        "missing_member",
        "duplicate_member",
        "member_period",
        "member_version",
        "member_fingerprint",
        "source_currency",
        "old_cumulative",
        "fabricated_authority",
        "duplicate_table",
        "duplicate_column",
        "duplicate_row",
        "missing_cell",
        "wrong_value",
        "bad_pointer",
        "array_leading_zero",
        "pointer_escape",
        "unavailable_zero",
        "available_null",
        "missing_reason",
        "unsafe_reason",
        "text_financial",
        "injected_financial_field",
        "wrong_source_unit",
        "wrong_display_unit",
        "wrong_currency",
        "wrong_scale",
        "double_conversion",
        "rounding_missing",
        "wrong_rounding",
    ],
)
def test_bad_evidence_is_refused_even_when_raw_response_is_rehashed(change: str) -> None:
    data = _data()
    table = data["tables"][0]
    column = next(item for item in table["columns"] if item["column_id"] == "return")
    cell = table["rows"][0]["cells"]["return"]
    period = data["source_response"]["periods"][0]
    member = period["member_contributions"][0]
    if change == "digest":
        data["source_response_digest"] = "sha256:" + "f" * 64
    elif change == "tenant":
        data["tenant_id"] = "tenant-b"
    elif change == "series":
        data["selection"]["composite_id"] = "changed"
    elif change == "window":
        data["selection"]["windows"][0]["source_cut_id"] = "changed"
    elif change == "engine":
        data["selection"]["engine_version"] = "changed"
    elif change == "missing_period":
        data["source_response"]["periods"].pop()
    elif change == "missing_member":
        period["member_contributions"].pop()
    elif change == "duplicate_member":
        period["member_contributions"][1]["portfolio_id"] = member["portfolio_id"]
    elif change == "member_period":
        member["period_start"] = "2025-01-01"
    elif change == "member_version":
        member["restatement_version"] = "changed"
    elif change == "member_fingerprint":
        member["source_fingerprint"] = "changed"
    elif change == "source_currency":
        period["reporting_currency"] = "SGD"
    elif change == "old_cumulative":
        data["source_response"]["cumulative_return"] = "0.01"
    elif change == "fabricated_authority":
        data["report_facts"]["authority"]["receipt"] = "fabricated"
    elif change == "duplicate_table":
        data["tables"].append(table)
    elif change == "duplicate_column":
        table["columns"].append(column)
    elif change == "duplicate_row":
        table["rows"].append(table["rows"][0])
    elif change == "missing_cell":
        table["rows"][0]["cells"].pop("return")
    elif change == "wrong_value":
        cell["canonical_value"] = "0"
    elif change == "bad_pointer":
        cell["source_pointer"] = "/source_response/absent"
    elif change == "array_leading_zero":
        cell["source_pointer"] = "/source_response/periods/00/return_value"
    elif change == "pointer_escape":
        cell["source_pointer"] = "/source_response/periods~2/return_value"
    elif change == "unavailable_zero":
        cell.update(canonical_value="0", availability="UNAVAILABLE", reason_codes=["MISSING"])
    elif change == "available_null":
        cell["canonical_value"] = None
    elif change == "missing_reason":
        cell.update(canonical_value=None, availability="UNAVAILABLE", reason_codes=[])
    elif change == "unsafe_reason":
        cell["reason_codes"] = ["private content with spaces"]
    elif change == "text_financial":
        column.update(
            value_type="TEXT", unit="TEXT", display_unit="TEXT", display_conversion="IDENTITY"
        )
    elif change == "injected_financial_field":
        data["source_response"]["injected"] = {"cumulative_return": "0.030200000000"}
        cell["source_pointer"] = "/source_response/injected/cumulative_return"
    elif change == "wrong_source_unit":
        column["unit"] = "CURRENCY_UNITS"
    elif change == "wrong_display_unit":
        column["display_unit"] = "PERCENTAGE_POINTS"
    elif change == "wrong_currency":
        data["tables"][1]["columns"][5]["currency"] = "SGD"
    elif change == "wrong_scale":
        column["scale"] = "100"
    elif change == "double_conversion":
        column["display_conversion"] = "IDENTITY"
    elif change == "rounding_missing":
        column["display_decimal_places"] = None
    else:
        column["display_rounding_mode"] = "HALF_EVEN"
    if change != "digest":
        _rehash(data)
    with pytest.raises(ValueError):
        validate_dataset(data)


@pytest.mark.parametrize(
    "number", ["NaN", "Infinity", "-Infinity", "1_000", "1e1001", "1e-1001", "1" * 257]
)
def test_financial_text_outside_declared_finite_envelope_refuses(number: str) -> None:
    with pytest.raises(ValueError, match="composite_cell_number_invalid"):
        decimal_value(number)


@pytest.mark.parametrize(
    "value,display,expected",
    [
        ("0.01", "PERCENT", "1.00%"),
        ("0.0302", "PERCENT", "3.02%"),
        ("-0.015", "PERCENTAGE_POINTS", "-1.50 pp"),
        ("0", "PERCENT", "0.00%"),
        ("0.00005", "PERCENT", "0.01%"),
    ],
)
def test_presentation_uses_declared_units_once_and_half_up_only(
    value: str, display: str, expected: str
) -> None:
    column = CompositeColumn.model_validate(
        {
            "column_id": "return",
            "label": "Return",
            "value_type": "DECIMAL_RETURN",
            "unit": "DECIMAL_RATIO",
            "display_unit": display,
            "display_conversion": "RATIO_TO_PERCENT_DISPLAY",
            "display_decimal_places": 2,
            "display_rounding_mode": "HALF_UP",
            "currency": None,
            "scale": "1",
        }
    )
    cell = CompositeCell(
        canonical_value=value,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/source_response/cumulative_return",
    )
    assert display_cell(column, cell) == expected
    assert cell.canonical_value == value


def test_large_money_displays_without_excel_precision_loss_and_keeps_exact_text() -> None:
    column = CompositeColumn.model_validate(
        {
            "column_id": "assets",
            "label": "Assets",
            "value_type": "MONEY",
            "unit": "CURRENCY_UNITS",
            "display_unit": "CURRENCY_UNITS",
            "display_conversion": "IDENTITY",
            "display_decimal_places": 2,
            "display_rounding_mode": "HALF_UP",
            "currency": "USD",
            "scale": "1",
        }
    )
    canonical = "999999999999999999999999.1234567890123456789"
    cell = CompositeCell(
        canonical_value=canonical,
        availability="AVAILABLE",
        reason_codes=[],
        source_pointer="/source_response/periods/0/beginning_market_value",
    )
    assert display_cell(column, cell) == "999999999999999999999999.12 USD"
    assert cell.canonical_value == canonical


def test_escaped_pointer_keys_resolve_without_treating_escape_as_path_separator() -> None:
    assert resolve_pointer({"selection": {"a/b~c": "literal"}}, "/selection/a~1b~0c") == "literal"
