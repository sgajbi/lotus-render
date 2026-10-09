"""Component XLSX proof from pinned controlled examples, not Report-emitted packages."""

import io
import json
from pathlib import Path

import openpyxl
import pytest
from amendment_fixtures import unit_amendment_package

from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistry
from app.services.composite_workbook.rendering import CompositeWorkbookRenderService
from app.services.render_intake import RenderIntakeService


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("kind", ["evaluated", "published"])
def test_workbook_retains_all_source_correction_evidence(version: str, kind: str) -> None:
    wire = unit_amendment_package(version, kind)
    package = RenderPackage.model_validate(wire)
    service = CompositeWorkbookRenderService(
        RenderIntakeService(TemplateRegistry.load_from_directory(Path("templates/registry")))
    )
    result = service.render(package)
    assert service.render(package).artifact_bytes == result.artifact_bytes
    workbook = openpyxl.load_workbook(io.BytesIO(result.artifact_bytes))
    assert len(workbook.sheetnames) == 13
    pinned = "".join(_text(row[1]) for row in list(workbook["PinnedData_1"].values)[1:])
    assert json.loads(pinned) == wire["report_data"]
    expected = {
        (table["table_id"], row["row_id"], key): cell
        for table in wire["report_data"]["tables"]
        for row in table["rows"]
        for key, cell in row["cells"].items()
    }
    evidence = list(workbook["CellEvidence_1"].values)[1:]
    assert len(evidence) == len(expected)
    for table, row, column, canonical, availability, reasons, pointer in evidence:
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
    identity = {
        _text(row[0]): _text(row[1]) for row in list(workbook["ArtifactIdentity_1"].values)[1:]
    }
    assert "no TWR, MWR, dispersion" in json.loads(_text(identity["calculation_boundary"]))
    assessments = list(workbook["EligibilityAssessments_1"].values)
    assert assessments[1][7] == "0.050000000000"
    assert assessments[1][5] == "50.00 USD"
    assert not any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row)
    # Rerender after canonical sorted JSON reconstruction uses the same occurrence policy.
    reconstructed = json.loads(json.dumps(wire, sort_keys=True))
    replay = service.render(RenderPackage.model_validate(reconstructed))
    assert (
        replay.diagnostic.bounded_determinism_fingerprint
        == result.diagnostic.bounded_determinism_fingerprint
    )
