"""The merged-PR dispatcher's shipped shell step, executed, with GitHub's answers scripted.

`merged-pr-main-releasability.yml` decides three things per landed revision: whether
its dispatch tag already exists, whether creating it was refused for the ONE reason a
fallback is permitted (GITHUB_TOKEN lacks the `workflows` scope: `Resource not
accessible by integration`, HTTP 403), and which ref to dispatch the gate on. #310 first
shipped that logic reading any HTTP 403 as the permitted refusal and any failed lookup
as "the tag is absent" -- a rate-limited or unauthenticated lookup would have led to a
tag-create attempt, and a rate-limited create would have quietly become a fallback.

These tests run the ACTUAL step text from the workflow file -- not a copy -- under bash
against real temporary Git history, with a `gh` on PATH that records every outbound
call and answers as GitHub would for one scenario. Assertions are on the recorded calls
and on the structured `dispatch-outcome` diagnostics the step emits, never on prose.

The step classifies on the body `gh api` leaves on stdout -- GitHub's own `status` and
`message`, or the ref's `object.sha` -- so the fake speaks that body contract, measured
against the live API. gh's stderr rendering is present for fidelity and read by nobody.

The identities Platform #772 asks to keep explicit are on every outcome line:
`tested_source` (the revision whose tree the gate tests, `expected_sha`) and
`workflow_definition` (the ref whose workflow text runs: the immutable tag, or `main`
under the permitted fallback).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "merged-pr-main-releasability.yml"
READER = ROOT / "scripts" / "read_github_api_answer.py"
STEP_NAME = "Dispatch main releasability gate for every commit this PR added"
REPOSITORY = "sgajbi/lotus-render"

# The step calls `python` -- the runner has it from actions/setup-python -- and the
# harness answers that name with the interpreter running the tests, so the reader the
# step exercises is the real script under a known interpreter, not whatever `python`
# happens to mean on a developer machine.
PYTHON_SHIM = f"""#!/usr/bin/env bash
exec "{Path(sys.executable).as_posix()}" "$@"
"""

# The recording GitHub boundary. One shell script on PATH ahead of the real `gh`:
# appends every invocation to CALLS (arguments tab-joined, one call per line) and
# answers by scenario, in the shapes gh really produces (measured against the live
# API). A refusal is the error BODY on stdout -- `status` is a JSON STRING -- plus the
# one-line rendering on stderr, exit 1. A found ref is the ref object on stdout, exit 0.
# A transport failure is stderr only: no body, because GitHub never answered.
FAKE_GH = """#!/usr/bin/env bash
printf '%s\\t' "$@" >> "$FAKE_GH_CALLS"
printf '\\n' >> "$FAKE_GH_CALLS"
case "$1 $2" in
  "api repos/$GITHUB_REPOSITORY")
    echo "false,false,true"
    exit 0
    ;;
esac
api_error() {
  printf '{"message":"%s",' "$1"
  printf '"documentation_url":"https://docs.github.com/rest","status":"%s"}\\n' "$2"
  echo "gh: $1 (HTTP $2)" >&2
  exit 1
}
ref_object() {
  printf '{"ref":"refs/tags/%s","node_id":"x","url":"u",' "$1"
  printf '"object":{"sha":"%s","type":"commit","url":"u"}}\\n' "$2"
  exit 0
}
transport_failure() {
  echo "error connecting to api.github.com: connection reset" >&2
  exit 1
}
case "$2" in
  repos/*/git/ref/tags/*)
    tag="${2##*/}"
    case "$FAKE_GH_SCENARIO" in
      tag-exists-match)           ref_object "$tag" "$FAKE_GH_REVISION" ;;
      tag-exists-mismatch)        ref_object "$tag" "0000000000000000000000000000000000000000" ;;
      lookup-answered-without-sha) echo '{"ref":"refs/tags/'"$tag"'"}'; exit 0 ;;
      lookup-rate-limited)        api_error "API rate limit exceeded for installation ID 1." 403 ;;
      lookup-unauthenticated)     api_error "Bad credentials" 401 ;;
      lookup-transport)           transport_failure ;;
      *)                          api_error "Not Found" 404 ;;
    esac
    ;;
  repos/*/git/refs)
    case "$FAKE_GH_SCENARIO" in
      tag-created)          ref_object "$FAKE_GH_TAG" "$FAKE_GH_REVISION" ;;
      fallback-permitted)   api_error "Resource not accessible by integration" 403 ;;
      create-rate-limited)  api_error "API rate limit exceeded for installation ID 1." 403 ;;
      create-unauthenticated) api_error "Bad credentials" 401 ;;
      create-server-error)  api_error "Server Error" 500 ;;
      create-transport)     transport_failure ;;
      *)                    echo "unexpected create in scenario $FAKE_GH_SCENARIO" >&2; exit 97 ;;
    esac
    ;;
esac
case "$1 $2" in
  "workflow run") exit 0 ;;
esac
echo "fake gh: unhandled call: $*" >&2
exit 98
"""


def _step_script() -> str:
    """The exact `run:` text of the shipped dispatch step -- the thing under test."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["dispatch-main-releasability"]["steps"]
    matching = [step for step in steps if step.get("name") == STEP_NAME]
    assert len(matching) == 1, "the dispatch step is located by its load-bearing name"
    return str(matching[0]["run"])


def _git(cwd: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
    )
    return completed.stdout.strip()


def _bash() -> str:
    """The POSIX shell GitHub Actions uses, including Git for Windows' bundled one.

    Windows can expose ``bash.exe`` as the WSL launcher even when no Linux
    distribution is installed.  That executable is discoverable, but cannot run the
    workflow step.  Git for Windows ships a real bash beside the ``git`` executable
    that this test already requires, so prefer that deterministic companion on
    Windows and retain the ordinary PATH lookup everywhere else.
    """

    git = shutil.which("git")
    if os.name == "nt" and git is not None:
        bundled_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if bundled_bash.is_file():
            return str(bundled_bash)
    bash = shutil.which("bash")
    assert bash is not None, "the step is a bash step; bash is required to execute it"
    return bash


def _history(tmp_path: Path) -> tuple[Path, str, str]:
    """A real repository with one commit on main and one rebased revision on top:
    the shape a single-commit rebase merge leaves behind. The checkout the runner
    works in is main, which carries the reader script the step calls."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "ci@example.invalid")
    _git(repo, "config", "user.name", "ci")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    shutil.copy(READER, repo / "scripts" / READER.name)
    _git(repo, "add", "README.md", "scripts")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("base\nmerged\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "merged revision")
    merge = _git(repo, "rev-parse", "HEAD")
    return repo, base, merge


Recorded = list[list[str]]
Outcomes = list[dict[str, str]]


def _run_step(
    tmp_path: Path, scenario: str
) -> tuple[subprocess.CompletedProcess[str], Recorded, Outcomes]:
    repo, base, merge = _history(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("gh", FAKE_GH), ("python", PYTHON_SHIM)):
        shim = bin_dir / name
        shim.write_text(text, encoding="utf-8", newline="\n")
        shim.chmod(0o755)
    calls = tmp_path / "gh-calls.log"
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    script = tmp_path / "dispatch-step.sh"
    script.write_text(_step_script(), encoding="utf-8", newline="\n")
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_TOKEN": "fake",
        "GITHUB_REPOSITORY": REPOSITORY,
        "MERGE_COMMIT_SHA": merge,
        "BASE_SHA": base,
        "COMMIT_COUNT": "1",
        "PR_NUMBER": "315",
        "RUNNER_TEMP": str(runner_temp),
        "FAKE_GH_CALLS": str(calls),
        "FAKE_GH_SCENARIO": scenario,
        "FAKE_GH_REVISION": merge,
        "FAKE_GH_TAG": f"main-releasability-{merge}",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    completed = subprocess.run(
        [_bash(), str(script)],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    recorded = (
        [
            line.rstrip("\t").split("\t")
            for line in calls.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if calls.exists()
        else []
    )
    outcomes = [
        dict(field.split("=", 1) for field in line.split()[1:])
        for line in completed.stdout.splitlines()
        if line.startswith("dispatch-outcome ")
    ]
    return completed, recorded, outcomes


def _kinds(recorded: list[list[str]]) -> list[str]:
    kinds: list[str] = []
    for call in recorded:
        if call[:2] == ["workflow", "run"]:
            kinds.append("workflow-run")
        elif call[0] == "api" and call[1].endswith("/git/refs"):
            kinds.append("create-ref")
        elif call[0] == "api" and "/git/ref/tags/" in call[1]:
            kinds.append("lookup-ref")
        elif call[0] == "api":
            kinds.append("merge-methods")
        else:
            kinds.append("other")
    return kinds


def _dispatched_ref(recorded: list[list[str]]) -> str:
    runs = [call for call in recorded if call[:2] == ["workflow", "run"]]
    assert len(runs) == 1
    return runs[0][runs[0].index("--ref") + 1]


def _expected_sha(recorded: list[list[str]]) -> str:
    runs = [call for call in recorded if call[:2] == ["workflow", "run"]]
    values = [
        arg.removeprefix("expected_sha=") for arg in runs[0] if arg.startswith("expected_sha=")
    ]
    assert len(values) == 1
    return values[0]


def test_a_created_tag_dispatches_the_gate_on_the_immutable_ref(tmp_path: Path) -> None:
    completed, recorded, outcomes = _run_step(tmp_path, "tag-created")
    merge = _history_merge(recorded)

    assert completed.returncode == 0, completed.stderr
    assert _kinds(recorded) == ["merge-methods", "lookup-ref", "create-ref", "workflow-run"]
    assert _dispatched_ref(recorded) == f"main-releasability-{merge}"
    assert _expected_sha(recorded) == merge
    assert outcomes == [
        {
            "revision": merge,
            "tested_source": merge,
            "workflow_definition": f"main-releasability-{merge}",
            "outcome": "tag-created",
        }
    ]


def test_the_workflows_scope_refusal_and_only_that_falls_back_to_main(tmp_path: Path) -> None:
    completed, recorded, outcomes = _run_step(tmp_path, "fallback-permitted")
    merge = _history_merge(recorded)

    assert completed.returncode == 0, completed.stderr
    assert _kinds(recorded) == ["merge-methods", "lookup-ref", "create-ref", "workflow-run"]
    assert _dispatched_ref(recorded) == "main", "the gate DEFINITION comes from main"
    assert _expected_sha(recorded) == merge, "the tree under test is still the revision"
    assert outcomes[-1]["outcome"] == "fallback-permitted"
    assert outcomes[-1]["tested_source"] == merge
    assert outcomes[-1]["workflow_definition"] == "main"


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        ("create-rate-limited", "403"),
        ("create-unauthenticated", "401"),
        ("create-server-error", "500"),
        ("create-transport", "none"),
    ],
)
def test_any_other_refusal_to_create_the_tag_is_fatal_and_dispatches_nothing(
    tmp_path: Path, scenario: str, status: str
) -> None:
    """A rate-limited create also answers HTTP 403; it is not a permission to run the
    gate off a mutable ref. Nor is a 401, a 500, or no answer at all. The diagnostic
    names the status GitHub actually gave, so the reader of a red run knows which."""

    completed, recorded, outcomes = _run_step(tmp_path, scenario)

    assert completed.returncode != 0
    assert _kinds(recorded) == ["merge-methods", "lookup-ref", "create-ref"]
    assert outcomes[-1]["outcome"] == "create-refused"
    assert outcomes[-1]["status"] == status
    assert "::error::" in completed.stdout


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        ("lookup-rate-limited", "403"),
        ("lookup-unauthenticated", "401"),
        ("lookup-transport", "none"),
        ("lookup-answered-without-sha", "answered"),
    ],
)
def test_a_lookup_that_did_not_answer_404_is_not_evidence_of_absence(
    tmp_path: Path, scenario: str, status: str
) -> None:
    """Only a 404 means the tag is absent. Anything else -- rate limit, bad
    credentials, transport, or an answer with no ref in it -- means the question was
    not answered, so creating a tag (or falling back) on the strength of it would act
    on a guess."""

    completed, recorded, outcomes = _run_step(tmp_path, scenario)

    assert completed.returncode != 0
    assert _kinds(recorded) == ["merge-methods", "lookup-ref"], "no create, no dispatch"
    assert outcomes[-1]["outcome"] == "lookup-failed"
    assert outcomes[-1]["status"] == status


def test_an_existing_tag_pointing_elsewhere_is_an_identity_mismatch(tmp_path: Path) -> None:
    completed, recorded, outcomes = _run_step(tmp_path, "tag-exists-mismatch")

    assert completed.returncode != 0
    assert _kinds(recorded) == ["merge-methods", "lookup-ref"]
    assert outcomes[-1]["outcome"] == "identity-mismatch"
    assert outcomes[-1]["existing"] == "0" * 40


def test_an_existing_tag_that_matches_is_reused_without_a_create(tmp_path: Path) -> None:
    completed, recorded, outcomes = _run_step(tmp_path, "tag-exists-match")
    merge = _history_merge(recorded)

    assert completed.returncode == 0, completed.stderr
    assert _kinds(recorded) == ["merge-methods", "lookup-ref", "workflow-run"]
    assert _dispatched_ref(recorded) == f"main-releasability-{merge}"
    assert outcomes[-1]["outcome"] == "tag-existing"


def _history_merge(recorded: list[list[str]]) -> str:
    """The revision the step enumerated, read back from its own lookup call."""
    lookups = [call for call in recorded if call[0] == "api" and "/git/ref/tags/" in call[1]]
    assert lookups, "the step must look the dispatch ref up before anything else"
    return lookups[0][1].rsplit("main-releasability-", 1)[1]
