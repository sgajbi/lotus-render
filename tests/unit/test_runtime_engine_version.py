"""What compiled a document, measured rather than declared.

Provenance carried `runtime_engine_version` from a settings default. In the shipped
image that value happens to be true, because the Dockerfile pins the binary it copies --
but nothing compared the two. The record was only ever as good as a coincidence between
a `FROM` tag, a constant in the render service, and a default in settings, any one of
which could be bumped alone (#157).

These tests hold the three together, and hold the measured engine against them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.settings import Settings
from app.services.typst_rendering import (
    DOCKER_TYPST_IMAGE,
    RUNTIME_VERSION_UNMEASURED,
    measured_runtime_engine_version,
)

DOCKERFILE = Path("Dockerfile")
PINNED_IMAGE = re.compile(r"ghcr\.io/typst/typst:(\d+\.\d+\.\d+)")


def _dockerfile_pins() -> list[str]:
    return PINNED_IMAGE.findall(DOCKERFILE.read_text(encoding="utf-8"))


def test_the_image_the_service_compiles_with_is_the_image_the_runtime_ships() -> None:
    """One version, named in three places, which must not drift apart.

    The service compiles in `DOCKER_TYPST_IMAGE` when Docker is present; the shipped
    image copies its binary out of the `FROM` pin; and every document's provenance is
    stamped from settings. Bump any one alone and documents keep asserting a version
    nothing checked.
    """

    pins = _dockerfile_pins()
    assert pins, f"no pinned Typst image found in {DOCKERFILE}"

    configured = Settings().runtime_engine_version
    compile_image_version = PINNED_IMAGE.search(DOCKER_TYPST_IMAGE)
    assert compile_image_version is not None, DOCKER_TYPST_IMAGE

    assert set(pins) == {configured}, (
        f"{DOCKERFILE} pins Typst {sorted(set(pins))} but settings declare {configured}; "
        "the shipped binary and the version stamped on every document disagree"
    )
    assert compile_image_version.group(1) == configured, (
        f"the service compiles with {DOCKER_TYPST_IMAGE} but stamps {configured}"
    )


@pytest.mark.skipif(
    shutil.which("docker") is None and shutil.which("typst") is None,
    reason="no Typst engine available to measure",
)
def test_the_engine_that_compiles_is_the_engine_documents_claim() -> None:
    """The declared value is the claim; this is the measurement that tests it."""

    measured = measured_runtime_engine_version()
    if measured == RUNTIME_VERSION_UNMEASURED:
        pytest.skip("the engine could not be probed on this host")

    assert measured == Settings().runtime_engine_version, (
        f"documents are stamped {Settings().runtime_engine_version} and the engine that "
        f"compiles them reports {measured}"
    )


def test_an_unprobeable_engine_is_named_rather_than_guessed() -> None:
    """A record that cannot be measured must not quietly become a guess."""

    assert RUNTIME_VERSION_UNMEASURED == "unmeasured"


def test_the_version_is_asked_through_whichever_path_a_compile_would_take(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe must follow the same branch the compile does, or it measures nothing."""

    from app.services.typst_rendering import _version_command

    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "/usr/bin/docker" if binary == "docker" else None,
    )
    command = _version_command()
    assert command is not None and command[0] == "/usr/bin/docker"
    assert DOCKER_TYPST_IMAGE in command and "--version" in command

    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "/usr/local/bin/typst" if binary == "typst" else None,
    )
    assert _version_command() == ["/usr/local/bin/typst", "--version"]


def test_an_engine_that_cannot_be_asked_is_named_unmeasured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Better an explicit "unmeasured" than a version nothing checked.

    Three ways the question can go unanswered, and none of them may quietly become a
    plausible-looking version string.
    """

    from app.services.typst_rendering import (
        _measure_runtime_engine_version,
        measured_runtime_engine_version,
    )

    # 1. No engine on the host at all.
    monkeypatch.setattr("app.services.typst_rendering.shutil.which", lambda binary: None)
    assert measured_runtime_engine_version() == RUNTIME_VERSION_UNMEASURED

    # 2. The probe itself fails to launch.
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "/nonexistent/typst" if binary == "typst" else None,
    )

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise OSError("no such binary")

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _explode)
    assert measured_runtime_engine_version() == RUNTIME_VERSION_UNMEASURED

    # 3. It answers, but with something that is not a version.
    def _answers_nonsense(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout="not a version", stderr=""
        )

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _answers_nonsense)
    assert _measure_runtime_engine_version(("probe-that-answers-nonsense",)) == (
        RUNTIME_VERSION_UNMEASURED
    )
