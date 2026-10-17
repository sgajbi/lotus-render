"""V9 evidence extensions; visible financial cells use the unchanged literal display path."""

import json
from collections.abc import Iterator

from app.contracts.composite_notice import CompositeNoticeContent
from app.services.composite_workbook.literal_writer import LiteralTable

EVIDENCE_HEADERS = (
    "Table",
    "Row",
    "Column",
    "Canonical JSON scalar",
    "Availability",
    "Reasons JSON",
    "Source pointer",
    "Generation",
    "Original data contract",
    "Original source table",
    "Original source row",
    "Original source column",
    "Original source pointer",
)


def _evidence_rows(content: CompositeNoticeContent) -> Iterator[tuple[str, ...]]:
    for table in content.tables:
        prefix, _, source_table = table.table_id.partition("_")
        side = {"Before": "before", "After": "after"}.get(prefix)
        for row in table.rows:
            for column in table.columns:
                cell = row.cells[column.column_id]
                original = (
                    side or "NOTICE",
                    "composite_review.v8",
                    source_table,
                    row.row_id,
                    column.column_id,
                    cell.source_pointer.removeprefix(f"/generations/{side}/payload"),
                )
                if side is None:
                    original = ("NOTICE", "", "", "", "", "")
                yield (
                    table.table_id,
                    row.row_id,
                    column.column_id,
                    json.dumps(cell.canonical_value, ensure_ascii=True),
                    cell.availability,
                    json.dumps(cell.reason_codes, ensure_ascii=True),
                    cell.source_pointer,
                    *original,
                )


def notice_cell_evidence(content: CompositeNoticeContent) -> LiteralTable:
    return LiteralTable("CellEvidence", EVIDENCE_HEADERS, _evidence_rows(content))
