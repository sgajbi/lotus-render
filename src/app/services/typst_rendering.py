from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
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
from app.domain.templates.digest import template_digest
from app.domain.templates.registry import shared_design_directory
from app.observability.render_metrics import record_render_empty_content_blocks
from app.services.compile_failures import classify_compile_failure
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import (
    RenderCompileFailedError,
    RenderEngineTimeoutError,
    RenderRuntimeMetadata,
)
from app.services.template_context import TemplateContextRegistry, TemplateContextRenderer
from app.services.typst_contexts import (
    build_outcome_review_context,
    build_portfolio_review_context,
    build_proof_pack_context,
    build_wave_context,
    count_empty_content_blocks,
)
from app.services.typst_values import escape_typst_string

DETERMINISM_MODE = "bounded_runtime_envelope"
DOCKER_TYPST_IMAGE = "ghcr.io/typst/typst:0.14.2"

# The selected bank-grade output standard (#246 phase 5): PDF/A-2a -- archival custody
# is what the evidence chain exists for, and the "a" level carries the tagged-structure
# requirements phases 2-4 built. Typst 0.14 enforces one substandard at a time, so
# PDF/UA-1 (which the document also compiles clean under, checked in the phase-1 audit)
# is deferred to an out-of-band check rather than weakened into a comment. Conformance
# is an executable property: the compiler refuses a violating document, so every render
# is the certification gate.
PDF_STANDARD = "a-2a"
PDF_MIME_TYPE = "application/pdf"
# `typst 0.14.2 (b33de9de)` -- the version, without the build hash.
_VERSION_OUTPUT = re.compile(r"typst\s+(\d+\.\d+\.\d+)")
RUNTIME_VERSION_UNMEASURED = "unmeasured"

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

# Per-compile ceiling for the in-process branch, matching the 512m the container branch
# already uses. Address space rather than RSS because that is what ulimit -v bounds, and
# CPU seconds so a pathological document cannot burn a core for the whole wall-clock
# timeout. Raise these together with DOCKER_ISOLATION_FLAGS so both branches agree.
COMPILE_ADDRESS_SPACE_LIMIT_KB = 512 * 1024
COMPILE_CPU_SECONDS = 60


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


def _version_command() -> list[str] | None:
    """Ask for the version through whichever path a compile would take."""
    docker_binary = shutil.which("docker")
    if docker_binary is not None:
        return [docker_binary, "run", "--rm", DOCKER_TYPST_IMAGE, "--version"]
    local_typst = shutil.which("typst")
    if local_typst is not None:
        return [local_typst, "--version"]
    return None


@lru_cache(maxsize=4)
def _measure_runtime_engine_version(command: tuple[str, ...]) -> str:
    completed = subprocess.run(  # noqa: S603
        list(command), capture_output=True, text=True, timeout=60, check=False
    )
    match = _VERSION_OUTPUT.search(f"{completed.stdout}\n{completed.stderr}")
    return match.group(1) if match else RUNTIME_VERSION_UNMEASURED


def measured_runtime_engine_version() -> str:
    """The version of the engine that will actually compile, not the one configured.

    Provenance carried a settings constant. In the shipped image that constant happens
    to be true, because the Dockerfile pins the binary it copies -- but nothing compared
    the two, so the record was only ever as good as a coincidence between a `FROM` tag
    and a default value. Change either without the other and every document keeps
    asserting a version nothing checked (#157).

    Cached per resolved command: a version probe costs a container start, and the engine
    cannot change under a running process.
    """
    command = _version_command()
    if command is None:
        return RUNTIME_VERSION_UNMEASURED
    try:
        return _measure_runtime_engine_version(tuple(command))
    except (OSError, subprocess.SubprocessError):
        return RUNTIME_VERSION_UNMEASURED


def ungoverned_runtime_reason() -> str | None:
    """Why this host cannot produce banked evidence, or None when it can.

    The pinned container and the shipped image render identically -- the same source
    compiled by ``ghcr.io/typst/typst:0.14.2`` and by that image's binary copied into
    ``python:3.12-slim`` produces the same bytes, which is what makes a golden banked
    in CI describe what production emits.

    A local binary on another platform does not. Typst 0.14.2 on Windows renders the
    golden portfolio review to a different document than Typst 0.14.2 on Linux, so a
    fingerprint banked there is evidence about a machine rather than about the service,
    and CI could never reproduce it.
    """
    if shutil.which("docker") is not None:
        return None
    if sys.platform.startswith("linux"):
        return None
    return (
        f"this host compiles with a local Typst binary on {sys.platform}, and the shipped "
        "runtime is Linux. The same Typst version renders a different document on each, so "
        "a fingerprint banked here would be evidence CI cannot reproduce. Re-bank where "
        "Docker is available, or on Linux."
    )


def page_image_hashes(service: "TypstRenderService", render_package: RenderPackage) -> list[str]:
    """One hash per page, in page order.

    PNG export carries no timestamp, so unlike the PDF this needs no patterns stripped
    before it is stable -- what is hashed is exactly what a reader would see.
    """
    return [hashlib.sha256(page).hexdigest() for page in service.render_page_images(render_package)]


def _bounded_local_command(command: list[str]) -> list[str]:
    """Bound a compile that runs as a child of this process rather than in a container.

    The shipped image installs no Docker CLI, so production always takes this branch and
    the container isolation flags never apply. Without a bound, a compile of untrusted
    report_data is limited only by the container, and exceeding it kills the whole
    service - including the renders the shutdown drain would otherwise have saved
    (issue #128). Bounding here fails the offending render instead.

    The limits are applied by the shell rather than a ``preexec_fn``: renders run on a
    threadpool, and running Python between fork and exec in a threaded process is exactly
    the case the standard library warns is unsafe.

    Windows has no ``ulimit``, so the command is returned unchanged there; the deployment
    that matters is Linux. The test is the platform, not whether a shell can be found:
    Git Bash puts an ``sh`` on PATH on Windows, and that shell reports
    ``ulimit: cpu time: cannot modify limit: Invalid argument`` and fails the compile
    outright rather than bounding it.
    """
    if sys.platform == "win32":
        return command
    shell = shutil.which("sh")
    if shell is None:
        return command
    limits = f"ulimit -v {COMPILE_ADDRESS_SPACE_LIMIT_KB} && ulimit -t {COMPILE_CPU_SECONDS}"
    return [shell, "-c", f'{limits} && exec "$0" "$@"', *command]


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


_PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _supplied_document_reference(render_package: RenderPackage) -> str:
    """The reference Report minted, or nothing. Never invented, never coerced."""
    reference = render_package.render_context.get("document_reference")
    return reference.strip() if isinstance(reference, str) else ""


def _substitute(text: str, replacements: Mapping[str, str]) -> str:
    """Fill every placeholder in one pass, so no value is ever rescanned.

    Replacing one key at a time over the whole file meant a value substituted early was
    read again by every later key, and report data reaches this point with its own
    `${...}` intact: the escapers neutralise what can break a Typst string literal, and
    `$` and `{` cannot. A client name of `${ASSET_CLASS_ROWS}` was expanded into markup
    whose quotes then closed the literal the name was sitting in.

    A name with no value is left as it stands rather than emptied, so a template that
    asks for something this service does not supply is visible in the output instead of
    silently blank.
    """
    return _PLACEHOLDER.sub(lambda match: replacements.get(match.group(1), match.group(0)), text)


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
    def runtime_engine_version(self) -> str:
        """What a document should say compiled it: the measured engine, where measurable.

        Falls back to the configured value only when the engine cannot be probed at all,
        so a record is never silently downgraded to a guess without saying so.
        """
        measured = measured_runtime_engine_version()
        if measured == RUNTIME_VERSION_UNMEASURED:
            return self._settings.runtime_engine_version
        return measured

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(
            runtime_engine=self._settings.runtime_engine,
            runtime_engine_version=self.runtime_engine_version,
        )

    def render_page_images(self, render_package: RenderPackage) -> list[bytes]:
        """One PNG per page of the document this package would produce.

        The artifact fingerprint answers "did anything change". It cannot answer "what
        changed", and it cannot answer "is this right" -- a sign-blind bar, a gridline
        drawn off-canvas, a chart card severed from its title and a document printing its
        own source were all byte-identical to themselves, so every golden was green over
        them for as long as they existed. Each was found by looking at a page.

        Page images give the missing granularity: banked per page, a moved golden names
        the pages that moved instead of only the document. They are exported by the same
        pinned Typst container that produces the PDF, so this adds no dependency, and PNG
        output carries no timestamp -- a plain hash is stable where the PDF needs eight
        patterns stripped from it first.
        """
        manifest = self._intake_service.validate_package(render_package)
        template_context = self._build_template_context(render_package)

        with TemporaryDirectory(prefix="lotus-render-pages-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_path = self._materialize_template(
                template_root=Path("templates/typst")
                / manifest.template_id
                / manifest.template_version
                / "main.typ",
                workspace=temp_dir,
                render_package=render_package,
                template_context=template_context,
                determinism_statement="",
            )
            command = self._build_compile_command(
                workspace=temp_dir,
                source_path=source_path,
                output_path=temp_dir / "page-{p}.png",
            )
            # `--format png` sits between `compile` and its arguments.
            command.insert(command.index("compile") + 1, "--format")
            command.insert(command.index("--format") + 1, "png")
            process = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                timeout=self._settings.render_compile_timeout_seconds,
                check=False,
            )
            if process.returncode != 0:
                _, summary = classify_compile_failure(process)
                raise RuntimeError(f"page image export failed: {summary}")
            pages = sorted(
                temp_dir.glob("page-*.png"),
                key=lambda path: int(path.stem.removeprefix("page-")),
            )
            return [page.read_bytes() for page in pages]

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

        # A document assembled from thin report data succeeds and reports `rendered`
        # exactly like a complete one. Measure how much of it was a placeholder so that
        # is visible; whether it is publishable stays the caller's judgement.
        record_render_empty_content_blocks(
            template_id=render_package.template_id,
            empty_blocks=count_empty_content_blocks(template_context),
        )

        # What the template actually contained for this render. template_version names
        # a mutable directory, so the version alone cannot explain an output (#139).
        rendered_template_digest = template_digest(
            Path("templates/typst") / manifest.template_id / manifest.template_version,
            shared_directory=shared_design_directory(),
        )
        attempt.mark_rendering()
        started = perf_counter()
        deterministic_statement = (
            "Bounded determinism is guaranteed only within the governed lotus-render runtime "
            f"envelope using Typst {self.runtime_engine_version}."
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
                category, diagnostic_summary = classify_compile_failure(process)
                attempt.mark_failed(category, diagnostic_summary)
                # The category rides on the exception. Raised bare, it was re-derived
                # downstream by matching the message, and a killed compile came back as
                # a template failure.
                raise RenderCompileFailedError(category, diagnostic_summary)

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
            runtime_engine_version=self.runtime_engine_version,
            output_format=render_package.output_format,
            status=attempt.status.value,
            determinism_mode=DETERMINISM_MODE,
            determinism_statement=deterministic_statement,
            bounded_determinism_fingerprint=bounded_determinism_fingerprint,
            template_digest=rendered_template_digest,
            template_publication=manifest.publication.value,
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
            # The governed document reference (#158): minted by Report before render,
            # placed verbatim by every family's footer, invented by nobody. Absent --
            # or anything but text -- draws nothing: Render must not turn a malformed
            # identity into a printed one.
            "DOCUMENT_REFERENCE": escape_typst_string(_supplied_document_reference(render_package)),
        }
        template_directory = template_root.parent
        workspace_template_directory = workspace / "template"
        shutil.copytree(template_directory, workspace_template_directory, dirs_exist_ok=True)
        # The shared design module lands beside the family's own files so a template
        # imports it by name, exactly as it imports a sibling. It is hashed into every
        # family's digest, so what compiles here is what the manifest attests to.
        shutil.copytree(
            shared_design_directory(),
            workspace_template_directory,
            dirs_exist_ok=True,
        )

        for template_file in workspace_template_directory.rglob("*.typ"):
            rendered_text = _substitute(template_file.read_text(encoding="utf-8"), replacements)
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
                "--pdf-standard",
                PDF_STANDARD,
                source_argument,
                output_argument,
            ]

        local_typst = shutil.which("typst")
        if local_typst is not None:
            return _bounded_local_command(
                [
                    local_typst,
                    "compile",
                    "--pdf-standard",
                    PDF_STANDARD,
                    str(source_path),
                    str(output_path),
                ]
            )

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
            # PDF/A writes an XMP revision-history event per save; its timestamp and
            # instance id differ between two renders of the identical package, exactly
            # like the creation dates above (#246 phase 5).
            rb"stEvt:when>[^<]+<",
            rb"stEvt:instanceID>[^<]+<",
            rb"xmpMM:DocumentID>[^<]+<",
        ):
            normalized_bytes = re.sub(pattern, b"", normalized_bytes)
        return hashlib.sha256(normalized_bytes).hexdigest()
