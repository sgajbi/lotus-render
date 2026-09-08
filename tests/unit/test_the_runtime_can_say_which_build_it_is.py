"""#300: the render runtime states the build it is, on both build paths.

Every rendered document asserts bounded determinism "within the governed lotus-render
runtime envelope", and the runtime could not name the commit that produced it. Two
artifacts built from different code carried identical envelope statements, and #270's
visual acceptance evidence was attributable to nothing.

These tests target the two things that can silently stop being true: the composition
(an ARG declared but never converted to ENV, or supplied by one build path and not the
other) and the honesty of the value (a modified tree reporting a clean commit, or a
branch name being executed instead of recorded).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.release_metadata import build_release_metadata
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]

PROVENANCE_ARGS = (
    "LOTUS_BUILD_COMMIT_SHA",
    "LOTUS_BUILD_GIT_BRANCH",
    "LOTUS_BUILD_REPO_URL",
    "LOTUS_BUILD_VERSION",
    "LOTUS_BUILD_TIMESTAMP",
    "LOTUS_CI_PIPELINE_ID",
    "LOTUS_IMAGE_DIGEST",
)


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _make_expansion(target: str, *overrides: str, cwd: Path | None = None) -> str:
    """What `make` would actually run, without running it."""

    result = subprocess.run(
        ["make", "-n", target, *overrides],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# --- The surface ----------------------------------------------------------------


def test_version_reports_every_provenance_field_as_a_string() -> None:
    """Unknown is an answer, so no field may be absent or null.

    An operator reading this should never have to tell a missing key apart from an
    unidentifiable build. The endpoint answers both cases with a value, and the value
    says which case it is.
    """

    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "service_name",
        "service_version",
        "git_commit_sha",
        "git_branch",
        "repository_url",
        "build_timestamp_utc",
        "ci_pipeline_run_id",
        "image_digest",
    }
    assert body["service_name"] == "lotus-render"
    for field, value in body.items():
        assert isinstance(value, str) and value, f"{field} is not a non-empty string"


@pytest.mark.parametrize("absent", ["", "   ", None])
def test_a_blank_build_argument_reports_unknown_rather_than_empty(
    monkeypatch: pytest.MonkeyPatch, absent: str | None
) -> None:
    """A present-but-blank variable means the same as an unset one.

    That is the shape an unset shell variable takes by the time it reaches Compose and
    then the image, so it is the likely failure rather than an exotic one. Publishing
    it would report a build as identified with nothing in the field.
    """

    if absent is None:
        monkeypatch.delenv("LOTUS_BUILD_COMMIT_SHA", raising=False)
    else:
        monkeypatch.setenv("LOTUS_BUILD_COMMIT_SHA", absent)

    assert build_release_metadata().git_commit_sha == "unknown"


def test_readiness_names_the_service_that_answered() -> None:
    """`{"status": "ready", "service": null}` could not say who replied.

    The field was declared on `HealthResponse` and populated nowhere in
    `readiness_status`, so it was a write-only key. It matters most when several
    services are unhealthy at once, which is exactly when the answer gets read.
    """

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.json()["service"] == "lotus-render"


# --- The composition ------------------------------------------------------------


def test_every_declared_build_argument_becomes_an_environment_variable() -> None:
    """An ARG the running process cannot read is provenance that exists nowhere.

    This is the sibling failure mode rather than a hypothetical: `lotus-advise`
    declared its arguments correctly and the composition dropped them, so `/version`
    answered `unknown` from an image whose metadata carried the real commit.
    """

    dockerfile = _read("Dockerfile")

    for name in PROVENANCE_ARGS:
        assert re.search(rf"^ARG {name}=", dockerfile, re.M), f"{name} is not declared"
        assert re.search(rf'{name}="\${{{name}}}"', dockerfile), f"{name} never reaches ENV"


def test_both_build_paths_supply_the_same_arguments() -> None:
    """Two paths that disagree can state different commits for one tree.

    `make docker-build` and `docker compose up --build` are both documented, and
    lotus-performance#511 is the case where only the Make path carries provenance, so
    the documented Compose bring-up silently produces an image reporting the defaults.
    """

    compose = _read("docker-compose.yml")
    make_build = _make_expansion("docker-build")
    make_up = _make_expansion("docker-up")

    for name in PROVENANCE_ARGS:
        assert f"{name}: ${{{name}:-" in compose, f"compose does not forward {name}"
        assert f"--build-arg {name}=" in make_build, f"docker-build omits {name}"
        assert f"{name}=" in make_up, f"docker-up omits {name}"


# --- The honesty of the value ---------------------------------------------------


def test_the_commit_is_the_real_head_not_merely_a_non_empty_string() -> None:
    """Asserted against `git rev-parse HEAD`, because non-emptiness passes for anything.

    A test that only checks the field is populated is satisfied by `unknown`, which is
    the exact state this issue exists to end.
    """

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    reported = re.search(r"LOTUS_BUILD_COMMIT_SHA='([^']*)'", _make_expansion("docker-build"))
    assert reported is not None
    assert reported.group(1).removesuffix("-dirty") == head


def test_a_modified_tree_is_marked_and_a_clean_one_is_not() -> None:
    """Both directions driven, because a marker that is always on says nothing.

    A build from a modified tree is not the commit it names, and an unmarked sha would
    attribute rendered output to source that never produced it. The clean case is
    asserted by overriding the tree state rather than by requiring a clean checkout, so
    the test states its own precondition instead of depending on the developer's.
    """

    dirty = _make_expansion("docker-build", "GIT_TREE_STATE=dirty", "GIT_SHA=abc123")
    clean = _make_expansion("docker-build", "GIT_TREE_STATE=clean", "GIT_SHA=abc123")

    assert "LOTUS_BUILD_COMMIT_SHA='abc123-dirty'" in dirty
    assert "LOTUS_BUILD_COMMIT_SHA='abc123'" in clean
    assert "-dirty" not in clean


def test_a_branch_name_is_recorded_as_data_and_never_executed(tmp_path: Path) -> None:
    """git accepts `;`, `$`, backticks and quotes in a branch name.

    Unquoted, `feature/foo;echo-PWN` would end the docker command and start another.
    The value has to survive into the build argument literally, character for
    character -- a stronger claim than the command merely not misbehaving.

    Driven from a real branch rather than through `make GIT_BRANCH=...`. A value given
    on Make's command line is a Make expression, so Make consumes `$(id)` itself before
    any quoting happens: that measures Make's expansion of an override, not the safety
    of the production path, where the value arrives from `$(shell git rev-parse ...)`
    and is not re-expanded. Getting that wrong reports the guard as broken when it
    holds, and never establishes whether it holds at all.

    A worktree rather than a checkout, so the developer's own HEAD is never moved and a
    mid-test failure cannot strand the repository on a branch named like this one.
    """

    hostile = "feature/foo;echo-PWN$(id)`whoami`"
    worktree = tmp_path / "hostile-branch"

    # `--no-checkout` because the only file this needs is the Makefile it writes below,
    # and a materialised worktree puts a second copy of every module under a temporary
    # path. Coverage traces those copies and the combined report then fails with
    # `No source for code: /tmp/.../hostile-branch/...` once the worktree is removed --
    # a test breaking a gate that has nothing to do with it, and only where the lanes
    # are combined. Found in the sibling repository (lotus-performance#511), where the
    # same test shape failed the combined coverage gate in CI while passing locally.
    # The branch still resolves: HEAD is set even with no working files.
    subprocess.run(
        ["git", "worktree", "add", "--no-checkout", "-b", hostile, str(worktree), "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        # The Makefile under test, not the committed one: a checked-out worktree carries
        # HEAD's copy, so without this the test would pass only once the change is
        # already committed and silently measure the previous revision until then.
        (worktree / "Makefile").write_text(_read("Makefile"), encoding="utf-8", newline="")
        expansion = _make_expansion("docker-build", cwd=worktree)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            ["git", "branch", "-D", hostile],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    branch_argument = re.search(r"--build-arg LOTUS_BUILD_GIT_BRANCH=(\S.*?)(?= \\)", expansion)
    assert branch_argument is not None

    # Round-trip through the shell's own parser: what a shell hands to docker has to be
    # the original string, not an approximation of it.
    delivered = subprocess.run(
        ["sh", "-c", f"printf '%s' {branch_argument.group(1)}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert delivered == hostile


def test_the_image_digest_says_why_it_is_absent_rather_than_calling_it_unknown() -> None:
    """A digest is not unknown before push -- it does not exist.

    Every other provenance field defaults to `unknown`, which is correct for them: a
    build that supplied no commit genuinely has one and did not say so. A digest is
    different in kind, because an image cannot contain its own digest -- it exists only
    once the image does. Reporting `unknown` puts a structural impossibility and a
    genuine gap behind the same word, which invites someone to supply a value through a
    build argument that cannot carry it, and lets an acceptance check flag a field that
    is behaving correctly.

    Raised by the lotus-gateway owner (#304), who hit the harder version: their digest
    reads `unknown` for CI-built images too, from a second independent cause.
    """

    from app.core.release_metadata import build_release_metadata

    assert build_release_metadata().image_digest == "unavailable-before-push"

    dockerfile = _read("Dockerfile")
    assert "ARG LOTUS_IMAGE_DIGEST=unavailable-before-push" in dockerfile
    assert "ARG LOTUS_IMAGE_DIGEST=unknown" not in dockerfile

    # Both build paths must agree, or a Compose build and a Make build would disagree
    # about a field whose whole purpose is to be unambiguous.
    assert "LOTUS_IMAGE_DIGEST: ${LOTUS_IMAGE_DIGEST:-unavailable-before-push}" in _read(
        "docker-compose.yml"
    )
    assert "IMAGE_DIGEST ?= unavailable-before-push" in _read("Makefile")
