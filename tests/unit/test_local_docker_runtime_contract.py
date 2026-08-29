import re
from pathlib import Path

import yaml

from app.core.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_local_compose_does_not_require_untracked_env_file() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    env_file = compose["services"]["lotus-render"]["env_file"]

    assert env_file == [{"path": ".env", "required": False}]


def test_service_image_does_not_run_as_root() -> None:
    """The compile child inherits the API process identity in the shipped image.

    Without a USER directive both run as root, so untrusted Typst source is compiled with
    full privileges inside the API container, sharing its network namespace, environment
    and render-store volume (issue #106).
    """

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    user_directives = [
        line.split(maxsplit=1)[1].strip()
        for line in dockerfile.splitlines()
        if line.strip().startswith("USER ")
    ]
    assert user_directives, "Dockerfile has no USER directive, so the service runs as root."
    assert user_directives[-1] != "root", (
        f"the final USER directive is {user_directives[-1]!r}; the service must not run as root."
    )


def _duration_seconds(value: str) -> float:
    """Parse the compose duration forms this file uses (e.g. '75s', '2m')."""

    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value.strip())
    assert match, f"unrecognised compose duration {value!r}"
    magnitude, unit = float(match.group(1)), match.group(2)
    return magnitude * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]


def test_shutdown_grace_period_outlasts_a_render_in_flight() -> None:
    """A grace period below the compile timeout silently defeats the drain.

    Shutdown marks the instance draining and waits for in-flight renders for up to
    `render_compile_timeout_seconds` before exiting (issue #105). Compose's default grace
    period is 10 seconds, so without this the platform SIGKILLs the very render the drain
    is waiting for and strands its job -- the exact failure the drain exists to prevent.
    """

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    grace = compose["services"]["lotus-render"].get("stop_grace_period")
    assert grace, (
        "docker-compose.yml sets no stop_grace_period, so the 10s default applies and the "
        "shutdown drain cannot complete."
    )

    # Honour a compose-level override: Configuration.md tells operators to raise the
    # compile timeout for large documents, and doing so must not silently outgrow the
    # grace period while this test keeps reading the default.
    service = compose["services"]["lotus-render"]
    configured = (service.get("environment") or {}).get(
        "LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS"
    )
    compile_timeout = (
        int(configured) if configured is not None else Settings().render_compile_timeout_seconds
    )
    assert _duration_seconds(str(grace)) > compile_timeout, (
        f"stop_grace_period {grace!r} does not outlast the {compile_timeout}s compile "
        "timeout, so a render in flight is killed rather than drained."
    )


def test_the_production_image_installs_runtime_dependencies_only() -> None:
    """The CI toolchain must not ship in the container that compiles untrusted input.

    `pip install -e ".[dev]"` put pip-audit and its HTTP/resolver stack, a second HTTP
    client, a YAML parser, mypy, ruff and pytest into the runtime image. No module under
    `src/` imports any of them, so each was pure CVE surface and patch burden in a
    container whose job is to compile Typst source built from untrusted report data.
    Removing the extra also took the image from 481 MB to 306 MB.
    """

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    install_lines = [line for line in dockerfile.splitlines() if "pip install" in line]
    assert install_lines, "the Dockerfile no longer installs the project."
    for line in install_lines:
        assert "[dev]" not in line, (
            f"the production image installs the dev extra: {line.strip()!r}. "
            "The CI toolchain belongs in CI, not in the runtime container."
        )
        assert " -e " not in line, (
            f"the production image installs editable: {line.strip()!r}. The service should "
            "run from an installed distribution, not a source tree its own user can rewrite."
        )


def test_the_container_has_a_resource_ceiling() -> None:
    """Untrusted report_data compiles in this container; it must not be unbounded.

    The confinement flags added in #106 sit on the `docker run` branch, and the shipped
    image installs no Docker CLI, so production never reaches them. Without a container
    limit there was no ceiling at any layer: a burst was bounded only by host RAM, and the
    OOM killer took the whole service including jobs the shutdown drain would have saved.
    """

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["lotus-render"]

    for key in ("mem_limit", "cpus", "pids_limit"):
        assert service.get(key), (
            f"docker-compose.yml sets no {key}, so the container that compiles untrusted "
            "input has no ceiling at that dimension."
        )

    # The ceiling must cover every concurrent compile, or one render can take the service.
    memory_mb = _duration_free_megabytes(str(service["mem_limit"]))
    per_compile_mb = 512
    concurrency = Settings().render_execution_concurrency_limit
    assert memory_mb > per_compile_mb * concurrency, (
        f"mem_limit {service['mem_limit']!r} does not cover {concurrency} concurrent "
        f"{per_compile_mb}m compiles plus the service itself."
    )


def _duration_free_megabytes(value: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kmg]?)b?", value.strip().lower())
    assert match, f"unrecognised compose memory value {value!r}"
    magnitude, unit = float(match.group(1)), match.group(2)
    return magnitude * {"": 1 / 1_048_576, "k": 1 / 1024, "m": 1.0, "g": 1024.0}[unit]
