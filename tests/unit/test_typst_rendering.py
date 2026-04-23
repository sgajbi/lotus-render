import hashlib
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import DOCKER_TYPST_IMAGE, TypstRenderService

GOLDEN_ROOT = Path("tests/golden/portfolio-review/v1")


def _load_golden_package() -> RenderPackage:
    return RenderPackage.model_validate_json(
        (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    )


def _build_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


def test_typst_render_service_renders_golden_portfolio_review_pdf() -> None:
    service = _build_service()
    expected_pdf = (GOLDEN_ROOT / "expected.pdf").read_bytes()

    result = service.render(_load_golden_package())

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.artifact_sha256 == hashlib.sha256(result.artifact_bytes).hexdigest()
    assert (
        result.diagnostic.bounded_determinism_fingerprint
        == service._compute_bounded_determinism_fingerprint(expected_pdf)
    )
    assert result.diagnostic.mime_type == "application/pdf"
    assert result.diagnostic.output_size_bytes == len(result.artifact_bytes)
    assert result.diagnostic.determinism_mode == "bounded_runtime_envelope"


def test_typst_render_service_is_deterministic_within_runtime_envelope() -> None:
    service = _build_service()
    render_package = _load_golden_package()

    first = service.render(render_package)
    second = service.render(render_package)

    assert (
        first.diagnostic.bounded_determinism_fingerprint
        == second.diagnostic.bounded_determinism_fingerprint
    )


def test_typst_render_service_rejects_missing_required_report_data() -> None:
    service = _build_service()
    render_package = _load_golden_package()
    incomplete_report_data = dict(render_package.report_data)
    incomplete_report_data.pop("client_name")

    invalid_package = render_package.model_copy(update={"report_data": incomplete_report_data})

    with pytest.raises(ValueError, match="missing required report_data field: client_name"):
        service.render(invalid_package)


def test_typst_render_service_rejects_empty_review_observations() -> None:
    service = _build_service()
    render_package = _load_golden_package()
    invalid_package = render_package.model_copy(
        update={
            "report_data": {
                **render_package.report_data,
                "review_observations": [],
            }
        }
    )

    with pytest.raises(ValueError, match="review_observations must be a non-empty list"):
        service.render(invalid_package)


def test_typst_render_service_marks_template_failure_when_typst_compile_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service()
    render_package = _load_golden_package()

    class _FailedProcess:
        returncode = 1
        stderr = "compile failed"
        stdout = ""

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["typst", "compile", "render.typ", "rendered.pdf"],
    )
    monkeypatch.setattr(
        "app.services.typst_rendering.subprocess.run",
        lambda *_, **__: _FailedProcess(),
    )

    with pytest.raises(RuntimeError, match="compile failed"):
        service.render(render_package)


def test_typst_render_service_uses_docker_fallback_when_local_typst_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "typst":
            return None
        if binary == "docker":
            return "/usr/bin/docker"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command[:5] == [
        "/usr/bin/docker",
        "run",
        "--rm",
        "-v",
        f"{tmp_path.resolve()}:/workspace",
    ]
    assert DOCKER_TYPST_IMAGE in command


def test_typst_render_service_prefers_docker_governed_runtime_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "docker":
            return "/usr/bin/docker"
        if binary == "typst":
            return "/usr/local/bin/typst"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command[:2] == ["/usr/bin/docker", "run"]
    assert DOCKER_TYPST_IMAGE in command


def test_typst_render_service_uses_local_typst_when_docker_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "docker":
            return None
        if binary == "typst":
            return "/usr/local/bin/typst"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command == [
        "/usr/local/bin/typst",
        "compile",
        str(source_path),
        str(output_path),
    ]


def test_typst_render_service_raises_when_no_runtime_is_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="Typst runtime is unavailable"):
        service._build_compile_command(
            workspace=tmp_path,
            source_path=tmp_path / "render.typ",
            output_path=tmp_path / "rendered.pdf",
        )
