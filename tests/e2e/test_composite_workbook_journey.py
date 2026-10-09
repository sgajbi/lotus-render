"""Actual registered engine execution, durable lifecycle and independent workbook reconciliation."""

import base64
import hashlib
import io
import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app

FIXTURE = Path("tests/golden/composite-review/v1/render-package.json")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _text(value: object) -> str:
    assert isinstance(value, str), f"expected an exact literal text cell, received {type(value)}"
    return value


def _source_value(dataset: dict[str, Any], pointer: str) -> Any:
    # Independent pointer reader: no production projection or validation imports.
    value: Any = dataset
    for token in pointer[1:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _expected_display(column: dict[str, Any], cell: dict[str, Any]) -> str:
    # Consumer oracle reads the declared contract; it never invokes Render's presenter.
    if cell["canonical_value"] is None:
        return str(cell["availability"]) + ": " + ", ".join(cell["reason_codes"])
    if column["value_type"] == "TEXT":
        return str(cell["canonical_value"])
    with localcontext() as context:
        context.prec = 2048
        number = Decimal(cell["canonical_value"])
        if column["display_conversion"] == "RATIO_TO_PERCENT_DISPLAY":
            number *= 100
        places = column["display_decimal_places"]
        if places is not None:
            number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        value = format(number, "f")
    suffix = {"PERCENT": "%", "PERCENTAGE_POINTS": " pp"}.get(column["display_unit"], "")
    if column["value_type"] == "MONEY":
        suffix = " " + column["currency"]
    return value + suffix


def reconcile_workbook(artifact: bytes, payload: dict[str, Any]) -> None:
    workbook = openpyxl.load_workbook(io.BytesIO(artifact))
    data = payload["report_data"]
    pinned = "".join(str(row[1]) for row in list(workbook["PinnedData_1"].values)[1:])
    assert json.loads(pinned) == data
    evidence = list(workbook["CellEvidence_1"].values)[1:]
    expected_cells = {
        (table["table_id"], row["row_id"], column["column_id"]): row["cells"][column["column_id"]]
        for table in data["tables"]
        for row in table["rows"]
        for column in table["columns"]
    }
    assert len(evidence) == len(expected_cells)
    for table, row, column, canonical, availability, reasons, pointer in evidence:
        expected = expected_cells[(table, row, column)]
        actual = json.loads(_text(canonical))
        assert actual == expected["canonical_value"]
        source = _source_value(data, _text(pointer))
        assert actual == (None if source is None else str(source))
        assert availability == expected["availability"]
        assert json.loads(_text(reasons)) == expected["reason_codes"]
        assert pointer == expected["source_pointer"]
    for table in data["tables"]:
        sheet = workbook[table["table_id"] + "_1"]
        rows = list(sheet.values)
        assert rows[0] == ("Report row identity", *(column["label"] for column in table["columns"]))
        assert [row[0] for row in rows[1:]] == [row["row_id"] for row in table["rows"]]
        for actual, row in zip(rows[1:], table["rows"], strict=True):
            assert actual[1:] == tuple(
                _expected_display(column, row["cells"][column["column_id"]])
                for column in table["columns"]
            )
    expected_policy = [
        (
            table["table_id"],
            column["column_id"],
            column["label"],
            column["value_type"],
            column["unit"],
            column["display_unit"],
            column["display_conversion"],
            str(column["display_decimal_places"]),
            column.get("display_rounding_mode", "HALF_UP"),
            column["currency"] or "",
            column.get("scale", "1"),
            "LITERAL_TEXT",
        )
        for table in data["tables"]
        for column in table["columns"]
    ]
    assert list(workbook["ColumnPolicy_1"].values)[1:] == expected_policy
    # Independently specified OR-01/OR-02 displayed oracles, no investment math.
    monthly = list(workbook["MonthlyReturns_1"].values)
    assert monthly[1][4:6] == ("1.00%", "1.00%")
    assert monthly[2][4:6] == ("2.00%", "3.02%")
    contribution = list(workbook["Contribution_1"].values)
    assert contribution[1][1] == "00000000000000000001"
    assert contribution[2][1] == "=literal-identifier"
    assert contribution[1][4:8] == ("10.00%", "100.00 USD", "25.00%", "2.50 pp")
    assert contribution[2][4:8] == ("-2.00%", "300.00 USD", "75.00%", "-1.50 pp")
    assert _text(monthly[1][10]).startswith("UNAVAILABLE:")
    identity = {
        row[0]: json.loads(_text(row[1])) for row in list(workbook["ArtifactIdentity_1"].values)[1:]
    }
    assert identity["snapshot_id"] == payload["snapshot_id"]
    assert identity["report_job_id"] == payload["report_job_id"]
    assert identity["render_context"] == payload["render_context"]
    assert identity["template_id"] == "composite-review"
    for parsed_sheet in workbook:
        assert all(
            cell.data_type != "f" and cell.hyperlink is None for row in parsed_sheet for cell in row
        )
    workbook.close()


def test_registered_submit_executes_xlsx_and_reconciles_every_source_cell(tmp_path: Path) -> None:
    settings = Settings(render_store_path=str(tmp_path / "render.sqlite3"))
    payload = _payload()
    with TestClient(create_app(settings), headers={"X-Tenant-Id": "tenant-a"}) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "rendered"
        assert body["runtime_engine"] == "xlsxwriter"
        assert body["runtime_engine_version"] == "3.2.9"
        assert body["output_format"] == "xlsx"
        assert body["mime_type"] == XLSX_MIME
        artifact = base64.b64decode(body["artifact_base64"])
        assert artifact.startswith(b"PK")
        assert body["artifact_sha256"] == "sha256:" + hashlib.sha256(artifact).hexdigest()
        reconcile_workbook(artifact, payload)
        metadata = client.get(f"/renders/{payload['render_job_id']}/artifact-metadata")
        assert metadata.status_code == 200
        assert metadata.json()["mime_type"] == XLSX_MIME
        assert metadata.json()["output_size_bytes"] == len(artifact)
        replay = client.post("/renders", json=payload)
        assert replay.status_code == 200
        assert replay.json()["artifact_base64"] is None
        assert replay.json()["artifact_sha256"] == body["artifact_sha256"]
    # Real persistence restart adopts terminal truth instead of rerendering.
    with TestClient(create_app(settings), headers={"X-Tenant-Id": "tenant-a"}) as client:
        assert (
            client.get(f"/renders/{payload['render_job_id']}").json()["artifact_sha256"]
            == body["artifact_sha256"]
        )
        assert client.post("/renders", json=payload).json()["artifact_base64"] is None
        wrong_tenant = client.get(
            f"/renders/{payload['render_job_id']}", headers={"X-Tenant-Id": "tenant-b"}
        )
        assert wrong_tenant.status_code == 404
        collision = client.post("/renders", json=payload, headers={"X-Tenant-Id": "tenant-b"})
        assert collision.status_code == 422


def test_tenant_contradiction_refuses_before_creating_a_job(tmp_path: Path) -> None:
    payload = _payload()
    with TestClient(
        create_app(Settings(render_store_path=str(tmp_path / "store.sqlite3"))),
        headers={"X-Tenant-Id": "tenant-b"},
    ) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 422
        assert client.get(f"/renders/{payload['render_job_id']}").status_code == 404


@pytest.mark.parametrize(
    "change", ["financial_value", "missing_tables", "bad_pointer", "currency", "authority"]
)
def test_bad_composite_evidence_fails_truthfully_without_artifact(
    tmp_path: Path, change: str
) -> None:
    payload = _payload()
    data = payload["report_data"]
    if change == "financial_value":
        data["tables"][0]["rows"][0]["cells"]["return"]["canonical_value"] = (
            "ADVERSARIAL_PRIVATE_MARKER"
        )
    elif change == "missing_tables":
        data["tables"] = []
    elif change == "bad_pointer":
        data["tables"][0]["rows"][0]["cells"]["return"]["source_pointer"] = (
            "/report_facts/qualification"
        )
    elif change == "currency":
        data["tables"][1]["columns"][5]["currency"] = "SGD"
    else:
        data["report_facts"]["authority"]["receipt"] = "fabricated-authority"
    with TestClient(
        create_app(Settings(render_store_path=str(tmp_path / "store.sqlite3"))),
        headers={"X-Tenant-Id": "tenant-a"},
    ) as client:
        response = client.post("/renders", json=payload)
        assert response.status_code == 422, response.text
        assert "ADVERSARIAL_PRIVATE_MARKER" not in response.text
        status = client.get(f"/renders/{payload['render_job_id']}").json()
        assert status["status"] == "failed"
        assert status["failure_category"] == "package_validation_failed"
        assert status["artifact_sha256"] is None
        assert (
            client.get(f"/renders/{payload['render_job_id']}/artifact-metadata").status_code == 409
        )
