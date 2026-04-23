from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.render_attempts.models import (
    RenderAttempt,
    RenderFailureCategory,
)
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.services.render_intake import RenderIntakeService

DETERMINISM_MODE = "bounded_runtime_envelope"
DOCKER_TYPST_IMAGE = "ghcr.io/typst/typst:0.14.2"
PDF_MIME_TYPE = "application/pdf"


class TypstRenderService:
    def __init__(self, settings: Settings, intake_service: RenderIntakeService) -> None:
        self._settings = settings
        self._intake_service = intake_service

    def render(self, render_package: RenderPackage) -> RenderResult:
        attempt = RenderAttempt(
            render_job_id=render_package.render_job_id,
            report_job_id=render_package.report_job_id,
            attempt_number=1,
            template_id=render_package.template_id,
            template_version=render_package.template_version,
            output_format=render_package.output_format,
        )

        attempt.mark_validating_package()
        manifest = self._intake_service.validate_package(render_package)

        try:
            template_context = self._build_portfolio_review_context(render_package)
        except ValueError as exc:
            attempt.mark_failed(RenderFailureCategory.PACKAGE_VALIDATION_FAILED, str(exc))
            raise

        attempt.mark_rendering()
        started = perf_counter()
        deterministic_statement = (
            "Bounded determinism is guaranteed only within the governed lotus-render runtime "
            f"envelope using Typst {self._settings.runtime_engine_version}."
        )

        with TemporaryDirectory(prefix="lotus-render-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_path = self._materialize_template(
                template_root=Path("templates/typst")
                / manifest.template_id
                / manifest.template_version
                / "main.typ",
                workspace=temp_dir,
                render_package=render_package,
                template_context=template_context,
                determinism_statement=deterministic_statement,
            )
            output_path = temp_dir / "rendered.pdf"
            command = self._build_compile_command(
                workspace=temp_dir,
                source_path=source_path,
                output_path=output_path,
            )
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            if process.returncode != 0:
                diagnostic_summary = (
                    process.stderr.strip() or process.stdout.strip() or "typst compile failed"
                )
                attempt.mark_failed(
                    RenderFailureCategory.TEMPLATE_RENDER_FAILED,
                    diagnostic_summary,
                )
                raise RuntimeError(diagnostic_summary)

            artifact_bytes = output_path.read_bytes()

        duration_ms = int((perf_counter() - started) * 1000)
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        bounded_determinism_fingerprint = self._compute_bounded_determinism_fingerprint(
            artifact_bytes
        )
        attempt.mark_rendered(artifact_sha256)

        diagnostic = RenderDiagnostic(
            render_job_id=render_package.render_job_id,
            render_package_version=render_package.render_package_version,
            template_id=render_package.template_id,
            template_version=render_package.template_version,
            runtime_engine=self._settings.runtime_engine,
            runtime_engine_version=self._settings.runtime_engine_version,
            output_format=render_package.output_format,
            status=attempt.status.value,
            determinism_mode=DETERMINISM_MODE,
            determinism_statement=deterministic_statement,
            bounded_determinism_fingerprint=bounded_determinism_fingerprint,
            artifact_sha256=artifact_sha256,
            render_duration_ms=duration_ms,
            mime_type=PDF_MIME_TYPE,
            output_size_bytes=len(artifact_bytes),
        )
        return RenderResult(
            attempt=attempt,
            diagnostic=diagnostic,
            artifact_bytes=artifact_bytes,
        )

    def _build_portfolio_review_context(self, render_package: RenderPackage) -> dict[str, str]:
        report_data = render_package.report_data
        render_context = render_package.render_context

        required_report_fields = [
            "client_name",
            "portfolio_name",
            "as_of_date",
            "currency",
            "total_value",
            "summary_paragraph",
            "review_observations",
        ]
        for field_name in required_report_fields:
            if field_name not in report_data:
                raise ValueError(f"missing required report_data field: {field_name}")

        observations = report_data["review_observations"]
        if not isinstance(observations, list) or not observations:
            raise ValueError("review_observations must be a non-empty list")

        mandate = self._mapping(report_data.get("mandate"))
        portfolio_metrics = self._mapping(report_data.get("portfolio_metrics"))
        allocation_summary = self._mapping(report_data.get("allocation_summary"))
        performance_highlight = self._mapping(report_data.get("performance_highlight"))
        risk_summary = self._mapping(report_data.get("risk_summary"))
        governance_summary = self._mapping(report_data.get("governance_summary"))

        return {
            "CLIENT_NAME": self._escape_typst_text(str(report_data["client_name"])),
            "PORTFOLIO_NAME": self._escape_typst_text(str(report_data["portfolio_name"])),
            "AS_OF_DATE": self._escape_typst_text(str(report_data["as_of_date"])),
            "CURRENCY": self._escape_typst_text(str(report_data["currency"])),
            "TOTAL_VALUE": self._escape_typst_text(str(report_data["total_value"])),
            "SUMMARY_PARAGRAPH": self._escape_typst_text(str(report_data["summary_paragraph"])),
            "REVIEW_PERIOD_LABEL": self._escape_typst_text(
                str(report_data.get("review_period_label", "YTD"))
            ),
            "OBJECTIVE": self._escape_typst_text(
                str(mandate.get("objective", "Objective not available in the governed snapshot."))
            ),
            "RISK_EXPOSURE": self._escape_typst_text(
                str(mandate.get("risk_exposure", "not_available"))
            ),
            "BOOKING_CENTER": self._escape_typst_text(
                str(mandate.get("booking_center_code", "not_available"))
            ),
            "ADVISOR_ID": self._escape_typst_text(str(mandate.get("advisor_id", "not_available"))),
            "INVESTED_VALUE": self._escape_typst_text(
                str(portfolio_metrics.get("invested_value", "Not available"))
            ),
            "CASH_BALANCE": self._escape_typst_text(
                str(portfolio_metrics.get("cash_balance", "Not available"))
            ),
            "CASH_WEIGHT_PCT": self._escape_typst_text(
                str(portfolio_metrics.get("cash_weight_pct", "Not available"))
            ),
            "ALLOCATION_LARGEST_NAME": self._escape_typst_text(
                str(allocation_summary.get("largest_asset_class_name", "Not available"))
            ),
            "ALLOCATION_LARGEST_WEIGHT": self._escape_typst_text(
                str(allocation_summary.get("largest_asset_class_weight_pct", "Not available"))
            ),
            "ALLOCATION_LARGEST_VALUE": self._escape_typst_text(
                str(allocation_summary.get("largest_asset_class_market_value", "Not available"))
            ),
            "ALLOCATION_POSITION_COUNT": self._escape_typst_text(
                str(allocation_summary.get("largest_asset_class_position_count", "Not available"))
            ),
            "TOP_CONTRIBUTOR_NAME": self._escape_typst_text(
                str(
                    performance_highlight.get(
                        "largest_positive_contributor_name",
                        "Not available",
                    )
                )
            ),
            "TOP_CONTRIBUTOR_VALUE": self._escape_typst_text(
                str(
                    performance_highlight.get(
                        "largest_positive_contribution_pct",
                        "Not available",
                    )
                )
            ),
            "BENCHMARK_STATUS": self._escape_typst_text(
                str(performance_highlight.get("benchmark_comparison_status", "not_available"))
            ),
            "RISK_VOLATILITY": self._escape_typst_text(
                str(risk_summary.get("volatility_pct", "Not available"))
            ),
            "RISK_BETA": self._escape_typst_text(str(risk_summary.get("beta", "Not available"))),
            "RISK_TRACKING_ERROR": self._escape_typst_text(
                str(risk_summary.get("tracking_error_pct", "Not available"))
            ),
            "RISK_INFORMATION_RATIO": self._escape_typst_text(
                str(risk_summary.get("information_ratio", "Not available"))
            ),
            "RISK_VAR": self._escape_typst_text(
                str(risk_summary.get("value_at_risk_pct", "Not available"))
            ),
            "OBSERVATION_NOTES": self._render_observation_notes(observations),
            "PERFORMANCE_PERIOD_ROWS": self._render_performance_period_rows(
                report_data.get("performance_periods")
            ),
            "PERFORMANCE_BAR_ROWS": self._render_performance_bar_rows(
                report_data.get("performance_periods")
            ),
            "HOLDING_ROWS": self._render_holding_rows(report_data.get("top_holdings")),
            "HOLDING_BAR_ROWS": self._render_holding_bar_rows(report_data.get("top_holdings")),
            "SOURCE_SERVICES": self._escape_typst_text(
                ", ".join(self._string_list(governance_summary.get("source_services")))
                or "Not available"
            ),
            "COMPLETENESS_STATUS": self._escape_typst_text(
                str(governance_summary.get("completeness_status", "unknown"))
            ),
            "DATA_QUALITY_STATUS": self._escape_typst_text(
                str(governance_summary.get("data_quality_status", "unknown"))
            ),
            "READINESS_STATUS": self._escape_typst_text(
                str(governance_summary.get("readiness_status", "unknown"))
            ),
            "RENDER_JOB_ID": self._escape_typst_text(render_package.render_job_id),
            "TEMPLATE_ID": self._escape_typst_text(render_package.template_id),
            "TEMPLATE_VERSION": self._escape_typst_text(render_package.template_version),
            "REQUESTED_BY": self._escape_typst_text(str(render_package.requested_by)),
            "TIMEZONE": self._escape_typst_text(str(render_context.get("timezone", "unknown"))),
        }

    def _materialize_template(
        self,
        *,
        template_root: Path,
        workspace: Path,
        render_package: RenderPackage,
        template_context: dict[str, str],
        determinism_statement: str,
    ) -> Path:
        replacements = {
            **template_context,
            "DETERMINISM_STATEMENT": self._escape_typst_text(determinism_statement),
            "TRACE_ID": self._escape_typst_text(render_package.trace_id),
            "CORRELATION_ID": self._escape_typst_text(render_package.correlation_id),
        }
        template_directory = template_root.parent
        workspace_template_directory = workspace / "template"
        shutil.copytree(template_directory, workspace_template_directory, dirs_exist_ok=True)

        for template_file in workspace_template_directory.rglob("*.typ"):
            rendered_text = template_file.read_text(encoding="utf-8")
            for key, value in replacements.items():
                rendered_text = rendered_text.replace(f"${{{key}}}", value)
            template_file.write_text(rendered_text, encoding="utf-8")

        return workspace_template_directory / template_root.name

    def _build_compile_command(
        self,
        *,
        workspace: Path,
        source_path: Path,
        output_path: Path,
    ) -> list[str]:
        source_argument = source_path.relative_to(workspace).as_posix()
        output_argument = output_path.relative_to(workspace).as_posix()
        docker_binary = shutil.which("docker")
        if docker_binary is not None:
            return [
                docker_binary,
                "run",
                "--rm",
                "-v",
                f"{workspace.resolve()}:/workspace",
                "-w",
                "/workspace",
                DOCKER_TYPST_IMAGE,
                "compile",
                source_argument,
                output_argument,
            ]

        local_typst = shutil.which("typst")
        if local_typst is not None:
            return [local_typst, "compile", str(source_path), str(output_path)]

        raise RuntimeError("Typst runtime is unavailable: neither docker nor typst is installed")

    @staticmethod
    def _escape_typst_text(value: str) -> str:
        escaped = value.replace("\\", "\\\\")
        for token in ("#", "{", "}", "[", "]", "$", "@"):
            escaped = escaped.replace(token, f"\\{token}")
        return escaped

    @staticmethod
    def _compute_bounded_determinism_fingerprint(artifact_bytes: bytes) -> str:
        normalized_bytes = artifact_bytes
        for pattern in (
            rb"/CreationDate \(D:[^)]+\)",
            rb"/ModDate \(D:[^)]+\)",
            rb"/ID \[<[^>]+> <[^>]+>\]",
            rb"/ID \[\([^)]+\) \([^)]+\)\]",
            rb"xmp:CreateDate>[^<]+<",
            rb"xmp:ModifyDate>[^<]+<",
            rb"xmpMM:InstanceID>[^<]+<",
            rb"xmpMM:DocumentID>[^<]+<",
        ):
            normalized_bytes = re.sub(pattern, b"", normalized_bytes)
        return hashlib.sha256(normalized_bytes).hexdigest()

    @staticmethod
    def _mapping(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _render_observation_notes(self, observations: object) -> str:
        if not isinstance(observations, Sequence) or isinstance(
            observations, (str, bytes, bytearray)
        ):
            return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed observations available.]"
        rendered: list[str] = []
        for item in observations:
            text = self._escape_typst_text(str(item))
            rendered.append(f'#review-note("{text}")')
        return "\n#v(8pt)\n".join(rendered)

    def _render_performance_period_rows(self, periods: object) -> str:
        empty_message = (
            "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed performance periods available.]"
        )
        if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes, bytearray)):
            return empty_message
        rendered: list[str] = []
        for item in periods:
            if not isinstance(item, Mapping):
                continue
            rendered.append(
                '#period-row("'
                + self._escape_typst_text(str(item.get("period", "n/a")))
                + '", "'
                + self._escape_typst_text(str(item.get("net_return_pct", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("benchmark_return_pct", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("relative_return_pct", "Not available")))
                + '")'
            )
        if not rendered:
            return empty_message
        return "\n#v(8pt)\n".join(rendered)

    def _render_performance_bar_rows(self, periods: object) -> str:
        empty_message = (
            "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed performance bars available.]"
        )
        if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes, bytearray)):
            return empty_message
        rendered: list[str] = []
        for item in periods:
            if not isinstance(item, Mapping):
                continue
            rendered.append(
                '#performance-bar-row("'
                + self._escape_typst_text(str(item.get("period", "n/a")))
                + '", "'
                + self._escape_typst_text(str(item.get("net_return_pct", "Not available")))
                + '", '
                + self._percent_width_token(item.get("net_return_pct"))
                + ")"
            )
        if not rendered:
            return empty_message
        return "\n#v(8pt)\n".join(rendered)

    def _render_holding_rows(self, holdings: object) -> str:
        if not isinstance(holdings, Sequence) or isinstance(holdings, (str, bytes, bytearray)):
            return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed holdings available.]"
        rendered: list[str] = []
        for item in holdings:
            if not isinstance(item, Mapping):
                continue
            rendered.append(
                '#holding-row("'
                + self._escape_typst_text(str(item.get("security_name", "Unknown holding")))
                + '", "'
                + self._escape_typst_text(str(item.get("asset_class", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("weight_pct", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("market_value", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("unrealized_pnl", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("ytd_contribution_pct", "Not available")))
                + '")'
            )
        if not rendered:
            return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed holdings available.]"
        return "\n#v(8pt)\n".join(rendered)

    def _render_holding_bar_rows(self, holdings: object) -> str:
        if not isinstance(holdings, Sequence) or isinstance(holdings, (str, bytes, bytearray)):
            return (
                "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed allocation rows available.]"
            )
        rendered: list[str] = []
        for item in holdings:
            if not isinstance(item, Mapping):
                continue
            rendered.append(
                '#allocation-row("'
                + self._escape_typst_text(str(item.get("security_name", "Unknown holding")))
                + '", "'
                + self._escape_typst_text(str(item.get("weight_pct", "Not available")))
                + '", "'
                + self._escape_typst_text(str(item.get("market_value", "Not available")))
                + '", '
                + self._percent_width_token(item.get("weight_pct"))
                + ")"
            )
        if not rendered:
            return (
                "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed allocation rows available.]"
            )
        return "\n#v(8pt)\n".join(rendered)

    @staticmethod
    def _percent_width_token(value: object) -> str:
        raw = str(value).strip().replace("%", "")
        try:
            numeric = float(raw)
        except ValueError:
            return "8%"
        clamped = min(max(numeric, 8.0), 100.0)
        return f"{clamped:.2f}%"
