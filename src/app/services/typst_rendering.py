from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
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

        return {
            "CLIENT_NAME": self._escape_typst_text(str(report_data["client_name"])),
            "PORTFOLIO_NAME": self._escape_typst_text(str(report_data["portfolio_name"])),
            "AS_OF_DATE": self._escape_typst_text(str(report_data["as_of_date"])),
            "CURRENCY": self._escape_typst_text(str(report_data["currency"])),
            "TOTAL_VALUE": self._escape_typst_text(str(report_data["total_value"])),
            "SUMMARY_PARAGRAPH": self._escape_typst_text(str(report_data["summary_paragraph"])),
            "OBSERVATIONS": "\n".join(
                f"- {self._escape_typst_text(str(item))}" for item in observations
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
        template_text = template_root.read_text(encoding="utf-8")
        replacements = {
            **template_context,
            "DETERMINISM_STATEMENT": self._escape_typst_text(determinism_statement),
            "TRACE_ID": self._escape_typst_text(render_package.trace_id),
            "CORRELATION_ID": self._escape_typst_text(render_package.correlation_id),
        }

        rendered_text = template_text
        for key, value in replacements.items():
            rendered_text = rendered_text.replace(f"${{{key}}}", value)

        source_path = workspace / "render.typ"
        source_path.write_text(rendered_text, encoding="utf-8")
        return source_path

    def _build_compile_command(
        self,
        *,
        workspace: Path,
        source_path: Path,
        output_path: Path,
    ) -> list[str]:
        local_typst = shutil.which("typst")
        if local_typst is not None:
            return [local_typst, "compile", str(source_path), str(output_path)]

        docker_binary = shutil.which("docker")
        if docker_binary is None:
            raise RuntimeError(
                "Typst runtime is unavailable: neither typst nor docker is installed"
            )

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
            source_path.name,
            output_path.name,
        ]

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
