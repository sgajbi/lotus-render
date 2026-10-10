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
from app.services.composite_workbook.amendment_custody import validate_amendment_custody
from app.services.composite_workbook.amendment_tables import validate_amendment_table_set
from app.services.composite_workbook.capacity import preflight_workbook
from app.services.composite_workbook.eligibility_custody import validate_eligibility_custody
from app.services.composite_workbook.eligibility_policy import validate_eligibility_table_set
from app.services.composite_workbook.fingerprint import workbook_content_fingerprint
from app.services.composite_workbook.historical_custody import validate_historical_custody
from app.services.composite_workbook.historical_tables import validate_historical_table_set
from app.services.composite_workbook.identity import IDENTITY_STORAGE
from app.services.composite_workbook.linked_custody import validate_linked_custody
from app.services.composite_workbook.linked_tables import LINKED_TABLE_COLUMNS
from app.services.composite_workbook.literal_writer import write_literal_workbook
from app.services.composite_workbook.pooled_custody import validate_pooled_custody
from app.services.composite_workbook.pooled_policy import validate_pooled_table_set
from app.services.composite_workbook.projection import workbook_tables
from app.services.composite_workbook.source_cells import validate_dataset
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderRuntimeMetadata

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _validate_contract_axes(package: RenderPackage) -> None:
    expected = f"composite_review.{package.template_version}"
    if (
        package.template_id != "composite-review"
        or package.template_version not in {"v1", "v2", "v3", "v4", "v5", "v6", "v7"}
        or package.report_data_contract_version != expected
        or package.report_data.get("contract_version") != expected
    ):
        raise ValueError("composite_workbook_contract_axes_conflict")


def _validate_layout(layout: dict[str, Any], table_names: set[str], *, version: str = "v1") -> None:
    for name, expected in (
        ("layout_version", f"composite_workbook.{version}"),
        ("financial_storage", "literal_text_with_exact_canonical_companion"),
        ("display_rounding_mode", "HALF_UP"),
        ("metadata_created", "2000-01-01T00:00:00"),
        ("identity_storage", IDENTITY_STORAGE),
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
    _validate_table_set(layout, table_names, version)


def _validate_table_set(layout: dict[str, Any], table_names: set[str], version: str) -> None:
    if version == "v7":
        validate_historical_table_set(layout, table_names)
        return
    if version == "v6":
        validate_amendment_table_set(layout, table_names)
        return
    if version == "v5":
        validate_pooled_table_set(layout, table_names)
        return
    if version == "v4":
        validate_eligibility_table_set(layout, table_names)
        return
    if version == "v3":
        _validate_linked_table_set(layout, table_names)
        return
    _validate_return_table_set(layout, table_names, version)


def _validate_linked_table_set(layout: dict[str, Any], table_names: set[str]) -> None:
    if (
        layout.get("required_tables") != list(LINKED_TABLE_COLUMNS)
        or layout.get("period_tables") != []
        or layout.get("optional_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if table_names != set(LINKED_TABLE_COLUMNS):
        raise ValueError("composite_workbook_table_set_invalid")


def _validate_return_table_set(layout: dict[str, Any], table_names: set[str], version: str) -> None:
    required = set(layout["required_tables"])
    periods = set(layout["period_tables"])
    selected = table_names & periods
    optional = {"TrailingReturns"} if version == "v2" else set()
    if version == "v2" and layout.get("optional_tables") != ["TrailingReturns"]:
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if len(selected) != 1 or table_names != required | selected | (table_names & optional):
        raise ValueError("composite_workbook_table_set_invalid")


def _validate_custody(package: RenderPackage) -> None:
    validate = {
        "v3": validate_linked_custody,
        "v4": validate_eligibility_custody,
        "v5": validate_pooled_custody,
        "v6": validate_amendment_custody,
        "v7": validate_historical_custody,
    }.get(package.template_version)
    if validate is not None:
        validate(package)


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
            _validate_contract_axes(render_package)
            content = validate_dataset(render_package.report_data)
            _validate_custody(render_package)
            _validate_layout(
                layout,
                {table.table_id for table in content.tables},
                version=render_package.template_version,
            )
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
        tables = workbook_tables(render_package, content, digest)
        if render_package.template_version in {"v4", "v5", "v6", "v7"}:
            retained, _ = preflight_workbook(render_package, tables)
            tables = iter(retained)
        artifact = write_literal_workbook(
            tables,
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
                "Exact package-member names and payloads under composite-xlsx-members/v1 "
                "for the same package, layout and pinned XlsxWriter. ZIP container metadata "
                "and compression may vary by host; raw artifact SHA names actual custody bytes. "
                "Fixed 2000-01-01 workbook metadata; literal canonical and display text."
            ),
            bounded_determinism_fingerprint=workbook_content_fingerprint(artifact),
            template_digest=digest,
            template_publication=manifest.publication.value,
            artifact_sha256=sha256,
            render_duration_ms=int((perf_counter() - started) * 1000),
            mime_type=XLSX_MIME_TYPE,
            output_size_bytes=len(artifact),
        )
        return RenderResult(attempt, diagnostic, artifact)
