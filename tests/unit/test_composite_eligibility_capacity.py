"""Physical v4 preflight includes evidence, metadata, identities and partition headers."""

from dataclasses import asdict

import pytest
from eligibility_fixtures import producer_package

from app.contracts.render_package import RenderPackage
from app.services.composite_workbook import eligibility_capacity, literal_writer
from app.services.composite_workbook.eligibility_capacity import preflight_eligibility_workbook
from app.services.composite_workbook.literal_writer import LiteralTable
from app.services.composite_workbook.projection import workbook_tables
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.render_ports import RenderCompileFailedError

DIGEST = "sha256:ad67662bd2ce9d3d2f65ec88f9db3c326c729c7c0b8d98c5c4284de8fb37413e"


@pytest.mark.parametrize(
    "kind,wire_bytes,cells,text",
    [
        ("evaluated_only", 55423, 2064, 85372),
        ("published", 62984, 2071, 93119),
    ],
)
def test_exact_complete_fixture_capacity(kind: str, wire_bytes: int, cells: int, text: int) -> None:
    package = RenderPackage.model_validate(producer_package(kind))
    tables, capacity = preflight_eligibility_workbook(
        package, workbook_tables(package, validate_dataset(package.report_data), DIGEST)
    )
    assert asdict(capacity) == dict(
        request_body_bytes=wire_bytes,
        total_rows=254,
        total_cells=cells,
        total_text_bytes=text,
        sheets=12,
    )
    assert len(tables) == 12


def test_partition_overhead_counts_each_repeated_header() -> None:
    package = RenderPackage.model_validate(producer_package())
    table = LiteralTable("Evidence", ("Header",), [("value",)] * 1001)
    _, capacity = preflight_eligibility_workbook(package, [table])
    assert capacity.total_rows == 1001
    assert capacity.total_cells == 1003
    assert capacity.sheets == 2
    assert capacity.total_text_bytes == 1001 * len("value") + 2 * len("Header")


@pytest.mark.parametrize(
    "bound,measured",
    [
        ("MAX_TOTAL_ROWS", 254),
        ("MAX_TOTAL_CELLS", 2064),
        ("MAX_TOTAL_TEXT_BYTES", 85372),
        ("MAX_SHEETS", 12),
        ("MAX_COLUMNS", 14),
        ("MAX_CELL_UTF16_UNITS", 16000),
    ],
)
def test_every_physical_guard_accepts_exact_boundary_and_refuses_one_below(
    monkeypatch: pytest.MonkeyPatch, bound: str, measured: int
) -> None:
    package = RenderPackage.model_validate(producer_package())
    content = validate_dataset(package.report_data)
    monkeypatch.setattr(literal_writer, bound, measured)
    preflight_eligibility_workbook(package, workbook_tables(package, content, DIGEST))
    monkeypatch.setattr(literal_writer, bound, measured - 1)
    with pytest.raises(RenderCompileFailedError, match="resource_limit_exceeded"):
        preflight_eligibility_workbook(package, workbook_tables(package, content, DIGEST))


def test_complete_serialized_request_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    package = RenderPackage.model_validate(producer_package())
    monkeypatch.setattr(eligibility_capacity, "MAX_REQUEST_BODY_BYTES", 55423)
    preflight_eligibility_workbook(package, [])
    monkeypatch.setattr(eligibility_capacity, "MAX_REQUEST_BODY_BYTES", 55422)
    with pytest.raises(RenderCompileFailedError, match="resource_limit_exceeded"):
        preflight_eligibility_workbook(package, [])


@pytest.mark.parametrize(
    "kind,expected",
    [
        (
            "actual_v1",
            dict(
                request_body_bytes=177244,
                total_rows=601,
                total_cells=4574,
                total_text_bytes=255163,
                sheets=12,
            ),
        ),
        (
            "actual_v2",
            dict(
                request_body_bytes=188461,
                total_rows=602,
                total_cells=4576,
                total_text_bytes=266382,
                sheets=12,
            ),
        ),
    ],
)
def test_actual_controlled_source_package_measured_envelope(
    kind: str, expected: dict[str, int]
) -> None:
    package = RenderPackage.model_validate(producer_package(kind))
    _, capacity = preflight_eligibility_workbook(
        package, workbook_tables(package, validate_dataset(package.report_data), DIGEST)
    )
    assert asdict(capacity) == expected
