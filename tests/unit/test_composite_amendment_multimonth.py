"""Retained Report ASGI/worker/SQLite dataset; Render envelope remains artificial."""

import io
import json
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from amendment_fixtures import unit_amendment_package

from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistry
from app.services.composite_workbook.rendering import CompositeWorkbookRenderService
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.render_intake import RenderIntakeService


def retained_data() -> dict[str, Any]:
    path = Path("tests/fixtures/composite-amendment-v6/two-month-retained-report-dataset.json")
    data: dict[str, Any] = json.loads(path.read_bytes())
    return data


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


@pytest.mark.parametrize("sorted_keys", [False, True])
def test_retained_two_month_dataset_is_admitted(sorted_keys: bool) -> None:
    data = json.loads(json.dumps(retained_data(), sort_keys=sorted_keys))
    assert [month["month"] for month in data["selection"]["months"]] == ["2026-09", "2026-10"]
    rows = data["tables"][-1]["rows"]
    assert len(rows) == 68
    assert rows[34]["row_id"] == "m1:a34"
    assert validate_dataset(data).model_dump(mode="json") == data


def test_month_local_row_ids_are_refused() -> None:
    data = retained_data()
    for ordinal, row in enumerate(data["tables"][-1]["rows"][34:]):
        row["row_id"] = f"m1:a{ordinal}"
    with pytest.raises(ValueError, match="composite_amendment_row_population_conflict"):
        validate_dataset(data)


def test_two_month_workbook_retains_exact_evidence_and_sorted_replay() -> None:
    wire = unit_amendment_package(dataset=retained_data())
    service = CompositeWorkbookRenderService(
        RenderIntakeService(TemplateRegistry.load_from_directory(Path("templates/registry")))
    )
    result = service.render(RenderPackage.model_validate(wire))
    workbook = openpyxl.load_workbook(io.BytesIO(result.artifact_bytes))
    pinned = "".join(_text(row[1]) for row in list(workbook["PinnedData_1"].values)[1:])
    assert json.loads(pinned) == wire["report_data"]
    expected = {
        (table["table_id"], row["row_id"], key): cell
        for table in wire["report_data"]["tables"]
        for row in table["rows"]
        for key, cell in row["cells"].items()
    }
    for table, row, column, canonical, availability, reasons, pointer in list(
        workbook["CellEvidence_1"].values
    )[1:]:
        cell = expected.pop((table, row, column))
        assert (
            json.loads(_text(canonical)),
            availability,
            json.loads(_text(reasons)),
            pointer,
        ) == (
            cell["canonical_value"],
            cell["availability"],
            cell["reason_codes"],
            cell["source_pointer"],
        )
    assert not expected
    assert not any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row)
    replay = json.loads(json.dumps(wire, sort_keys=True))
    assert (
        service.render(RenderPackage.model_validate(replay)).artifact_bytes == result.artifact_bytes
    )
