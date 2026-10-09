"""XLSX engine adapter inside the registered Render submission and custody lifecycle."""

import hashlib
import json
from time import perf_counter
from typing import Any

import xlsxwriter  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.contracts.render_package import RenderPackage
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.domain.templates.digest import template_digest
from app.domain.templates.registry import TemplateRegistryError, template_source_directories
from app.services.composite_workbook import literal_writer
from app.services.composite_workbook.literal_writer import write_literal_workbook
from app.services.composite_workbook.projection import workbook_tables
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderRuntimeMetadata

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _validate_layout(layout: dict[str, Any], table_names: set[str]) -> None:
    for name, expected in (
        ("layout_version", "composite_workbook.v1"),
        ("financial_storage", "literal_text_with_exact_canonical_companion"),
        ("display_rounding_mode", "HALF_UP"),
        ("metadata_created", "2000-01-01T00:00:00"),
    ):
        if layout.get(name) != expected:
            raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    for name in (
        "max_rows_per_sheet",
        "max_total_rows",
        "max_total_cells",
        "max_total_text_bytes",
        "max_sheets",
        "max_columns",
        "max_cell_utf16_units",
        "max_output_bytes",
    ):
        if layout.get(name) != getattr(literal_writer, name.upper()):
            raise TemplateRegistryError("composite_workbook_layout_limit_mismatch")
    required = set(layout["required_tables"])
    periods = set(layout["period_tables"])
    selected = table_names & periods
    if len(selected) != 1 or table_names != required | selected:
        raise ValueError("composite_workbook_table_set_invalid")


class CompositeWorkbookRenderService:
    def __init__(self, intake: RenderIntakeService, *, timeout_seconds: float = 60) -> None:
        self._intake = intake
        self._timeout_seconds = timeout_seconds

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata("xlsxwriter", xlsxwriter.__version__)

    def render(self, render_package: RenderPackage) -> RenderResult:
        started = perf_counter()
        manifest = self._intake.validate_package(render_package)
        if manifest.runtime_engine_version != self.runtime_metadata.runtime_engine_version:
            raise TemplateRegistryError("composite_workbook_runtime_version_mismatch")
        directory, shared = template_source_directories(manifest)
        digest = template_digest(directory, shared_directory=shared)
        if digest != manifest.template_digest:
            raise TemplateRegistryError("composite_workbook_template_changed")
        layout = json.loads((directory / "layout.json").read_text(encoding="utf-8"))
        try:
            content = validate_dataset(render_package.report_data)
            _validate_layout(layout, {table.table_id for table in content.tables})
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            # Product diagnostics must not echo source content or arbitrary parser text.
            raise ValueError("composite_review_content_invalid") from exc
        attempt = RenderAttempt(
            render_package.render_job_id,
            render_package.report_job_id,
            1,
            render_package.template_id,
            render_package.template_version,
            render_package.output_format,
        )
        attempt.mark_validating_package()
        attempt.mark_rendering()
        artifact = write_literal_workbook(
            workbook_tables(render_package, content, digest),
            timeout_seconds=self._timeout_seconds,
            header_colors=(layout["header_background"], layout["header_foreground"]),
        )
        sha256 = hashlib.sha256(artifact).hexdigest()
        attempt.mark_rendered(sha256)
        metadata = self.runtime_metadata
        diagnostic = RenderDiagnostic(
            render_job_id=render_package.render_job_id,
            render_package_version=render_package.render_package_version,
            template_id=render_package.template_id,
            template_version=render_package.template_version,
            runtime_engine=metadata.runtime_engine,
            runtime_engine_version=metadata.runtime_engine_version,
            output_format="xlsx",
            status="rendered",
            determinism_mode="bounded",
            determinism_statement=(
                "Exact XLSX bytes for the same package, approved layout and pinned XlsxWriter "
                "runtime. Fixed 2000-01-01 metadata; canonical source and display cells "
                "are literal text."
            ),
            bounded_determinism_fingerprint=sha256,
            template_digest=digest,
            template_publication=manifest.publication.value,
            artifact_sha256=sha256,
            render_duration_ms=int((perf_counter() - started) * 1000),
            mime_type=XLSX_MIME_TYPE,
            output_size_bytes=len(artifact),
        )
        return RenderResult(attempt, diagnostic, artifact)
