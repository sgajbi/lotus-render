"""Preflight physical composite cells, partition headers and retained JSON fragments."""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.contracts.render_package import RenderPackage
from app.domain.render_attempts.models import RenderFailureCategory
from app.services.composite_workbook import literal_writer as limits
from app.services.composite_workbook.literal_writer import LiteralTable
from app.services.render_ports import RenderCompileFailedError

MAX_REQUEST_BODY_BYTES = 8_388_608


def _refuse() -> None:
    raise RenderCompileFailedError(
        RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED, "composite_workbook_resource_limit_exceeded"
    )


@dataclass
class WorkbookCapacity:
    request_body_bytes: int
    total_rows: int = 0
    total_cells: int = 0
    total_text_bytes: int = 0
    sheets: int = 0

    def add_values(self, values: Sequence[str]) -> None:
        self.total_cells += len(values)
        for value in values:
            limits.validate_literal(value)
            self.total_text_bytes += len(value.encode("utf-8"))
        if (
            self.total_cells > limits.MAX_TOTAL_CELLS
            or self.total_text_bytes > limits.MAX_TOTAL_TEXT_BYTES
        ):
            _refuse()

    def add_sheet(self, headers: tuple[str, ...]) -> None:
        self.sheets += 1
        if self.sheets > limits.MAX_SHEETS:
            _refuse()
        self.add_values(headers)


def preflight_workbook(
    package: RenderPackage, tables: Iterable[LiteralTable]
) -> tuple[list[LiteralTable], WorkbookCapacity]:
    wire = json.dumps(
        package.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    capacity = WorkbookCapacity(request_body_bytes=len(wire))
    if capacity.request_body_bytes > MAX_REQUEST_BODY_BYTES:
        _refuse()
    retained = [_retain_table(table, capacity) for table in tables]
    return retained, capacity


def _retain_table(table: LiteralTable, capacity: WorkbookCapacity) -> LiteralTable:
    if not table.headers or len(table.headers) > limits.MAX_COLUMNS:
        _refuse()
    capacity.add_sheet(table.headers)
    rows: list[tuple[str, ...]] = []
    for index, values in enumerate(table.rows):
        capacity.total_rows += 1
        if capacity.total_rows > limits.MAX_TOTAL_ROWS or len(values) != len(table.headers):
            _refuse()
        if index and index % limits.MAX_ROWS_PER_SHEET == 0:
            capacity.add_sheet(table.headers)
        capacity.add_values(values)
        rows.append(tuple(values))
    return LiteralTable(table.name, table.headers, rows)
