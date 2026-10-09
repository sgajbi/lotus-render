"""Frozen producer outcomes and independent full workbook reconciliation."""

import io
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from pooled_fixtures import CASES, producer_package

from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistry
from app.services.composite_workbook.rendering import CompositeWorkbookRenderService
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.render_intake import RenderIntakeService


def service() -> CompositeWorkbookRenderService:
    return CompositeWorkbookRenderService(
        RenderIntakeService(TemplateRegistry.load_from_directory(Path("templates/registry")))
    )


@pytest.mark.parametrize("kind", CASES)
def test_seven_actual_worker_packages_admit_complete_source_without_rewriting(kind: str) -> None:
    package = producer_package(kind)
    data = package["report_data"]
    assert validate_dataset(data).model_dump(mode="json") == data


def expected_display(column: dict[str, Any], cell: dict[str, Any]) -> str:
    value = cell["canonical_value"]
    if value is None:
        return str(cell["availability"]) + ": " + ", ".join(cell["reason_codes"])
    if column["value_type"] == "TEXT":
        return str(value)
    number = Decimal(value)
    if column["display_conversion"] == "RATIO_TO_PERCENT_DISPLAY":
        number *= 100
    number = number.quantize(
        Decimal(1).scaleb(-column["display_decimal_places"]), rounding=ROUND_HALF_UP
    )
    return format(number, "f") + (
        "%" if column["display_unit"] == "PERCENT" else " " + column["currency"]
    )


def text_value(value: object) -> str:
    assert isinstance(value, str)
    return value


@pytest.mark.parametrize("kind", CASES)
def test_all_actual_workbook_cells_policies_pinned_source_and_identity(kind: str) -> None:
    wire = producer_package(kind)
    artifact = service().render(RenderPackage.model_validate(wire)).artifact_bytes
    book = openpyxl.load_workbook(io.BytesIO(artifact))
    data = wire["report_data"]
    expected = {}
    for table in data["tables"]:
        rows = list(book[table["table_id"] + "_1"].values)
        assert rows[0] == ("Report row identity", *(c["label"] for c in table["columns"]))
        assert rows[1:] == [
            (
                r["row_id"],
                *(expected_display(c, r["cells"][c["column_id"]]) for c in table["columns"]),
            )
            for r in table["rows"]
        ]
        for row in table["rows"]:
            for column in table["columns"]:
                expected[(table["table_id"], row["row_id"], column["column_id"])] = row["cells"][
                    column["column_id"]
                ]
    for table, row, column, canonical, availability, reasons, pointer in list(
        book["CellEvidence_1"].values
    )[1:]:
        cell = expected.pop((table, row, column))
        assert (
            json.loads(text_value(canonical)),
            availability,
            json.loads(text_value(reasons)),
            pointer,
        ) == (
            cell["canonical_value"],
            cell["availability"],
            cell["reason_codes"],
            cell["source_pointer"],
        )
    assert not expected
    assert (
        json.loads("".join(text_value(r[1]) for r in list(book["PinnedData_1"].values)[1:])) == data
    )
    identity = {
        k: json.loads(text_value(v)) for k, v in list(book["ArtifactIdentity_1"].values)[1:]
    }
    assert identity["render_context"] == wire["render_context"]
    assert identity["lineage_refs"] == wire["lineage_refs"]
    assert list(book["ColumnPolicy_1"].values)[1:] == [
        (
            t["table_id"],
            c["column_id"],
            c["label"],
            c["value_type"],
            c["unit"],
            c["display_unit"],
            c["display_conversion"],
            str(c["display_decimal_places"]),
            c["display_rounding_mode"],
            c["currency"] or "",
            c["scale"],
            "LITERAL_TEXT",
        )
        for t in data["tables"]
        for c in t["columns"]
    ]
    assert all(c.data_type == "s" and c.hyperlink is None for s in book for row in s for c in row)
    outcome = data["source_response"]["outcome"]
    if outcome["availability"] == "NOT_CALCULABLE":
        assert all(
            outcome[k] is None
            for k in ("return_value", "annualized_return", "holding_period_return")
        )
        assert "UNAVAILABLE" in text_value(book["Outcome_1"].cell(2, 7).value)
    book.close()
