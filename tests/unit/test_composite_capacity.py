"""The genuine controlled six-year package fits the registered bounded writer on every CI host."""

import gzip
import hashlib
import io
import json
from pathlib import Path

import openpyxl

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.composite_workbook.rendering import CompositeWorkbookRenderService
from app.services.render_intake import RenderIntakeService


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def test_actual_six_year_package_preserves_all_evidence_pins_and_large_context() -> None:
    raw = gzip.decompress(
        Path("tests/golden/composite-review/v1/six-year-render-package.json.gz").read_bytes()
    )
    assert (
        hashlib.sha256(raw).hexdigest()
        == "a66e8cb356ccb1dba335e874494cb584e827b086316f3684a26114da50d1355a"
    )
    payload = json.loads(raw)
    wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    assert len(wire) == 6_893_642 < Settings().max_request_body_bytes
    package = RenderPackage.model_validate(payload)
    service = CompositeWorkbookRenderService(
        RenderIntakeService(TemplateRegistry.load_from_directory(Path("templates/registry")))
    )
    result = service.render(package)
    assert len(result.artifact_bytes) < 16_777_216
    workbook = openpyxl.load_workbook(io.BytesIO(result.artifact_bytes), read_only=True)
    assert len(workbook.sheetnames) == 43
    assert sum(sheet.max_row - 1 for sheet in workbook) == 27_939
    assert sum(sheet.max_row * sheet.max_column for sheet in workbook) == 201_586
    pinned = "".join(
        _text(row[1])
        for sheet in workbook
        if sheet.title.startswith("PinnedData_")
        for row in list(sheet.values)[1:]
    )
    assert json.loads(pinned) == payload["report_data"]
    expected = {
        (table["table_id"], row["row_id"], column["column_id"]): row["cells"][column["column_id"]]
        for table in payload["report_data"]["tables"]
        for row in table["rows"]
        for column in table["columns"]
    }
    actual = [
        row
        for sheet in workbook
        if sheet.title.startswith("CellEvidence_")
        for row in list(sheet.values)[1:]
    ]
    assert len(actual) == len(expected) == 24_604
    assert len({row[:3] for row in actual}) == len(expected)
    for table, row, column, canonical, availability, reasons, pointer in actual:
        cell = expected[(table, row, column)]
        assert json.loads(_text(canonical)) == cell["canonical_value"]
        assert availability == cell["availability"]
        assert json.loads(_text(reasons)) == cell["reason_codes"]
        assert pointer == cell["source_pointer"]
    identity = list(workbook["ArtifactIdentity_1"].values)[1:]
    assert identity[-5][0] == "render_context__chunks"
    descriptor = json.loads(_text(identity[-5][1]))
    assert descriptor["count"] == 4
    assert [row[0] for row in identity[-4:]] == [
        f"render_context__chunk_{index:06d}" for index in range(4)
    ]
    canonical = "".join(json.loads(_text(row[1])) for row in identity[-4:])
    assert len(canonical.encode()) == descriptor["utf8_bytes"] == 60_148
    assert hashlib.sha256(canonical.encode()).hexdigest() == descriptor["sha256"]
    assert json.loads(canonical) == payload["render_context"]
    workbook.close()
