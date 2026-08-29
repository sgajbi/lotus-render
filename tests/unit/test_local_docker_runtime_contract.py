from pathlib import Path

import yaml

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
