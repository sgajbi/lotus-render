"""Source-owned semantic tables and transparent evidence dictionaries in one workbook."""

import json
from collections.abc import Iterator
from typing import Any

from app.contracts.composite_products import CompositeContent, CompositeOutputTable
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.identity import JSON_CHUNK_CHARACTERS, identity_rows
from app.services.composite_workbook.literal_writer import LiteralTable
from app.services.composite_workbook.presentation import display_cell


def _visible_table(table: CompositeOutputTable) -> LiteralTable:
    return LiteralTable(
        table.table_id,
        ("Report row identity", *(column.label for column in table.columns)),
        (
            (
                row.row_id,
                *(display_cell(column, row.cells[column.column_id]) for column in table.columns),
            )
            for row in table.rows
        ),
    )


def _cell_evidence(content: CompositeContent) -> LiteralTable:
    rows = (
        (
            table.table_id,
            row.row_id,
            column.column_id,
            json.dumps(row.cells[column.column_id].canonical_value, ensure_ascii=True),
            row.cells[column.column_id].availability,
            json.dumps(row.cells[column.column_id].reason_codes, ensure_ascii=True),
            row.cells[column.column_id].source_pointer,
        )
        for table in content.tables
        for row in table.rows
        for column in table.columns
    )
    return LiteralTable(
        "CellEvidence",
        (
            "Table",
            "Row",
            "Column",
            "Canonical JSON scalar",
            "Availability",
            "Reasons JSON",
            "Source pointer",
        ),
        rows,
    )


def _column_policy(content: CompositeContent) -> LiteralTable:
    return LiteralTable(
        "ColumnPolicy",
        (
            "Table",
            "Column",
            "Label",
            "Type",
            "Source unit",
            "Display unit",
            "Conversion",
            "Decimal places",
            "Rounding",
            "Currency",
            "Scale",
            "Storage",
        ),
        (
            (
                table.table_id,
                column.column_id,
                column.label,
                column.value_type,
                column.unit,
                column.display_unit,
                column.display_conversion,
                str(column.display_decimal_places),
                column.display_rounding_mode,
                column.currency or "",
                column.scale,
                "LITERAL_TEXT",
            )
            for table in content.tables
            for column in table.columns
        ),
    )


def _artifact_identity(package: RenderPackage, template_digest: str) -> LiteralTable:
    fields: dict[str, Any] = {
        "render_package_version": package.render_package_version,
        "render_job_id": package.render_job_id,
        "report_job_id": package.report_job_id,
        "snapshot_id": package.snapshot_id,
        "template_id": package.template_id,
        "template_version": package.template_version,
        "template_digest": template_digest,
        "report_data_contract_version": package.report_data_contract_version,
        "output_format": package.output_format,
        "canonical_precision": "Exact source text; never Excel numeric storage",
        "display_rounding": "Declared column decimal places; HALF_UP; ratio times 100 once",
        "metadata_policy": "Fixed creation date 2000-01-01; no wall-clock content",
        "lineage_refs": package.lineage_refs,
        "disclosure_refs": package.disclosure_refs,
        "render_context": package.render_context,
    }
    if package.template_version in {"v4", "v6"}:
        fields["display_rounding"] = (
            "Declared column decimal places; HALF_UP; source ratios remain ratios"
        )
    if package.template_version == "v6":
        fields["calculation_boundary"] = (
            "Source-correction eligibility evidence only; no TWR, MWR, dispersion, "
            "contribution or model-fee calculation. CONTROLLED / NOT_ATTESTED."
        )
    return LiteralTable(
        "ArtifactIdentity",
        ("Field", "Exact JSON value"),
        identity_rows(fields),
    )


def workbook_tables(
    package: RenderPackage, content: CompositeContent, template_digest: str
) -> Iterator[LiteralTable]:
    for table in content.tables:
        yield _visible_table(table)
    yield _cell_evidence(content)
    yield _column_policy(content)
    yield _artifact_identity(package, template_digest)
    # The canonical JSON is chunked, never shortened. Reassembly preserves raw
    # source spelling, all exact pins, semantic cells and unsupported slots.
    canonical = json.dumps(
        package.report_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    yield LiteralTable(
        "PinnedData",
        ("Chunk", "Canonical pinned dataset JSON"),
        (
            (str(index // JSON_CHUNK_CHARACTERS), canonical[index : index + JSON_CHUNK_CHARACTERS])
            for index in range(0, len(canonical), JSON_CHUNK_CHARACTERS)
        ),
    )
