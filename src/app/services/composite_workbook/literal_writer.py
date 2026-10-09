"""Bounded literal-only XLSX output; no calculation, formulas or active links."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

# The pinned writer publishes no typing marker or stub distribution. Keep this
# single untyped dependency boundary in the literal adapter; its inputs and
# outputs are typed and independently parsed in the owning tests.
import xlsxwriter  # type: ignore[import-untyped]

from app.domain.render_attempts.models import RenderFailureCategory
from app.services.render_ports import RenderCompileFailedError, RenderEngineTimeoutError

MAX_ROWS_PER_SHEET = 1_000
MAX_TOTAL_ROWS = 20_000
MAX_TOTAL_CELLS = 200_000
MAX_TOTAL_TEXT_BYTES = 16_777_216
MAX_SHEETS = 64
MAX_COLUMNS = 100
MAX_CELL_UTF16_UNITS = 32_767
MAX_OUTPUT_BYTES = 16_777_216


@dataclass(frozen=True, slots=True)
class LiteralTable:
    name: str
    headers: tuple[str, ...]
    rows: Iterable[Sequence[str]]


def _resource_refusal() -> RenderCompileFailedError:
    return RenderCompileFailedError(
        RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED, "composite_workbook_resource_limit_exceeded"
    )


def validate_literal(value: str) -> None:
    if len(value.encode("utf-16-le")) // 2 > MAX_CELL_UTF16_UNITS:
        raise _resource_refusal()
    if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
        raise ValueError("composite_workbook_text_invalid")


class _WorkbookWriter:
    def __init__(
        self, workbook: xlsxwriter.Workbook, deadline: float, header_colors: tuple[str, str]
    ) -> None:
        self.workbook = workbook
        self.deadline = deadline
        self.rows = 0
        self.cells = 0
        self.text_bytes = 0
        self.sheets = 0
        self.header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": header_colors[0],
                "font_color": header_colors[1],
                "text_wrap": True,
            }
        )
        self.text_format = workbook.add_format({"num_format": "@", "valign": "top"})

    def _sheet(self, table: LiteralTable, partition: int) -> xlsxwriter.worksheet.Worksheet:
        self.sheets += 1
        if self.sheets > MAX_SHEETS:
            raise _resource_refusal()
        # Name is internal registry truth; source text never controls sheet names.
        sheet = self.workbook.add_worksheet(f"{table.name}_{partition}")
        sheet.freeze_panes(1, 1)
        sheet.set_column(0, len(table.headers) - 1, 24)
        sheet.set_row(0, 42)
        sheet.repeat_rows(0)
        sheet.hide_gridlines(2)
        self._write_row(sheet, 0, table.headers, header=True)
        return sheet

    def _write_row(
        self,
        sheet: xlsxwriter.worksheet.Worksheet,
        row: int,
        values: Sequence[str],
        *,
        header: bool,
    ) -> None:
        self.cells += len(values)
        if self.cells > MAX_TOTAL_CELLS:
            raise _resource_refusal()
        for column, value in enumerate(values):
            validate_literal(value)
            self.text_bytes += len(value.encode("utf-8"))
            if self.text_bytes > MAX_TOTAL_TEXT_BYTES:
                raise _resource_refusal()
            cell_format = self.header_format if header else self.text_format
            if sheet.write_string(row, column, value, cell_format) != 0:
                raise _resource_refusal()

    def write_table(self, table: LiteralTable) -> None:
        if not table.headers or len(table.headers) > MAX_COLUMNS:
            raise _resource_refusal()
        partition, row_index = 1, 0
        sheet = self._sheet(table, partition)
        for values in table.rows:
            _check_deadline(self.deadline)
            self.rows += 1
            if self.rows > MAX_TOTAL_ROWS or len(values) != len(table.headers):
                raise _resource_refusal()
            if row_index == MAX_ROWS_PER_SHEET:
                sheet.autofilter(0, 0, row_index, len(table.headers) - 1)
                partition += 1
                row_index = 0
                sheet = self._sheet(table, partition)
            row_index += 1
            self._write_row(sheet, row_index, values, header=False)
        sheet.autofilter(0, 0, row_index, len(table.headers) - 1)


def _check_deadline(deadline: float) -> None:
    if monotonic() >= deadline:
        raise RenderEngineTimeoutError("composite_workbook_timeout")


def write_literal_workbook(
    tables: Iterable[LiteralTable],
    *,
    timeout_seconds: float = 60,
    header_colors: tuple[str, str] = ("black", "white"),
) -> bytes:
    """Temporary files are isolated and cleaned even when validation or writing refuses."""
    deadline = monotonic() + timeout_seconds
    with TemporaryDirectory(prefix="lotus-composite-xlsx-") as directory:
        path = Path(directory) / "rendered.xlsx"
        with xlsxwriter.Workbook(
            path,
            {
                # Shared strings keep standard independent readers faithful for
                # literal OOXML escape-shaped identifiers. Aggregate text/cell
                # limits bound the in-memory dictionary, not just the final ZIP.
                "constant_memory": False,
                # StringIO serialization emits identical XML line endings on
                # Windows and Linux. The same aggregate bounds cover these buffers.
                "in_memory": True,
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "strings_to_numbers": False,
                "tmpdir": directory,
            },
        ) as workbook:
            workbook.set_properties(
                {"title": "Composite Review", "author": "Lotus", "created": datetime(2000, 1, 1)}
            )
            writer = _WorkbookWriter(workbook, deadline, header_colors)
            for table in tables:
                writer.write_table(table)
            if writer.sheets == 0:
                raise ValueError("composite_workbook_tables_missing")
        if path.stat().st_size > MAX_OUTPUT_BYTES:
            raise _resource_refusal()
        _check_deadline(deadline)
        return path.read_bytes()
