from __future__ import annotations

import hashlib
import os
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
from app.services.portfolio_charts import render_portfolio_chart_assets
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderEngineTimeoutError, RenderRuntimeMetadata
from app.services.template_context import TemplateContextRegistry, TemplateContextRenderer
from app.services.typst_contexts import (
    build_outcome_review_context,
    build_portfolio_review_context,
    build_proof_pack_context,
    build_wave_context,
)
from app.services.typst_values import escape_typst_string

DETERMINISM_MODE = "bounded_runtime_envelope"
DOCKER_TYPST_IMAGE = "ghcr.io/typst/typst:0.14.2"
PDF_MIME_TYPE = "application/pdf"

# Confinement for the compile container. The Typst source is built from untrusted
# report_data, so the process that compiles it gets no network, no capabilities, no
# privilege escalation, and bounded memory and process count (issue #106). A compile
# needs none of them: fonts and assets are materialised into the mounted workspace.
DOCKER_ISOLATION_FLAGS = (
    "--network",
    "none",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--memory",
    "512m",
    "--pids-limit",
    "256",
)
# Killing `docker run` reaps the client, not the container it started, so a timed-out
# compile would keep burning CPU with the workspace bind-mounted while Python deletes it.
# The run is named so the timeout path can stop the container itself.
DOCKER_CONTAINER_NAME_PREFIX = "lotus-render-compile-"
DOCKER_KILL_TIMEOUT_SECONDS = 10


def _compile_container_name(workspace: Path) -> str:
    """Name the run after its workspace so the timeout path can stop that container.

    The workspace is a per-render ``TemporaryDirectory``, so the name is unique for the
    lifetime of the container and needs no clock or random source.
    """
    return f"{DOCKER_CONTAINER_NAME_PREFIX}{workspace.name}"


def _docker_user_flags() -> tuple[str, ...]:
    """Run the compile as the invoking user where the platform has one.

    Without this the container runs as root and writes root-owned files into the
    bind-mounted workspace. Windows has no uid/gid to map, so the flag is omitted there.
    """
    get_uid = getattr(os, "getuid", None)
    get_gid = getattr(os, "getgid", None)
    if get_uid is None or get_gid is None:
        return ()
    return ("--user", f"{get_uid()}:{get_gid()}")


def _kill_compile_container(workspace: Path) -> None:
    """Stop a container left running by a timed-out ``docker run``.

    Best effort: the container may already be gone, and the compile has failed either
    way, so a failure here must not mask the timeout being reported to the caller.
    """
    docker_binary = shutil.which("docker")
    if docker_binary is None:
        return
    try:
        subprocess.run(
            [docker_binary, "kill", _compile_container_name(workspace)],
            capture_output=True,
            check=False,
            timeout=DOCKER_KILL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return


class TypstRenderService:
    def __init__(self, settings: Settings, intake_service: RenderIntakeService) -> None:
        self._settings = settings
        self._intake_service = intake_service
        self._template_context_registry = TemplateContextRegistry(
            (
                TemplateContextRenderer(
                    report_type="portfolio_review",
                    template_id="portfolio-review",
                    template_version="v1",
                    build_context=build_portfolio_review_context,
                ),
                TemplateContextRenderer(
                    report_type="proof_pack",
                    template_id="proof-pack",
                    template_version="v1",
                    build_context=build_proof_pack_context,
                ),
                TemplateContextRenderer(
                    report_type="outcome_review",
                    template_id="outcome-review",
                    template_version="v1",
                    build_context=build_outcome_review_context,
                ),
                TemplateContextRenderer(
                    report_type="rebalance_wave",
                    template_id="rebalance-wave",
                    template_version="v1",
                    build_context=build_wave_context,
                ),
            )
        )

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(
            runtime_engine=self._settings.runtime_engine,
            runtime_engine_version=self._settings.runtime_engine_version,
        )

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
            template_context = self._build_template_context(render_package)
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
            try:
                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self._settings.render_compile_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                # subprocess reaped the `docker run` client; the container it started is
                # still compiling with this workspace bind-mounted, so stop it before the
                # TemporaryDirectory is torn down underneath it.
                _kill_compile_container(temp_dir)
                attempt.mark_failed(
                    RenderFailureCategory.TIMEOUT,
                    "Render execution timed out in the governed runtime envelope.",
                )
                raise RenderEngineTimeoutError("render_timeout") from exc
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
            # Scalars are substituted into string-literal placeholders, so they carry the
            # string escaper; composed markup blocks in template_context carry their own.
            "DETERMINISM_STATEMENT": escape_typst_string(determinism_statement),
            "TRACE_ID": escape_typst_string(render_package.trace_id),
            "CORRELATION_ID": escape_typst_string(render_package.correlation_id),
        }
        template_directory = template_root.parent
        workspace_template_directory = workspace / "template"
        shutil.copytree(template_directory, workspace_template_directory, dirs_exist_ok=True)
        if render_package.report_type == "portfolio_review":
            render_portfolio_chart_assets(
                render_package.report_data,
                workspace_template_directory / "assets" / "charts",
            )

        for template_file in workspace_template_directory.rglob("*.typ"):
            rendered_text = template_file.read_text(encoding="utf-8")
            for key, value in replacements.items():
                rendered_text = rendered_text.replace(f"${{{key}}}", value)
            template_file.write_text(rendered_text, encoding="utf-8")

        return workspace_template_directory / template_root.name

    def _build_template_context(self, render_package: RenderPackage) -> dict[str, str]:
        return self._template_context_registry.build_context(render_package)

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
                "--name",
                _compile_container_name(workspace),
                *DOCKER_ISOLATION_FLAGS,
                *_docker_user_flags(),
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
