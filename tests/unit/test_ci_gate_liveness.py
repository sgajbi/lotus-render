"""Prove repository-native gates are reachable from blocking GitHub workflows."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from scripts import audit_main_gate_coverage
from scripts.ci_gate_inventory import (
    gate_targets_reachable_from_lanes,
    gate_targets_reachable_from_workflows,
    make_dependencies,
)

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WORKFLOW_FILES = (
    ROOT / ".github" / "workflows" / "feature-lane.yml",
    ROOT / ".github" / "workflows" / "pr-merge-gate.yml",
    ROOT / ".github" / "workflows" / "main-releasability.yml",
)


def test_every_local_gate_is_reachable_from_blocking_workflows() -> None:
    """Local aggregate membership is not evidence that GitHub ever invokes the gate."""

    makefile = MAKEFILE.read_text(encoding="utf-8")
    workflow_texts = [path.read_text(encoding="utf-8") for path in WORKFLOW_FILES]
    advertised = gate_targets_reachable_from_lanes(makefile)
    enforced = gate_targets_reachable_from_workflows(makefile, workflow_texts)

    assert advertised, "The local check/ci lanes advertise no gates; this test would prove nothing."
    assert enforced, "GitHub Actions invokes no reachable gate target; green CI proves no gates."
    assert advertised <= enforced, (
        "These gates are advertised by make check/ci but unreachable from GitHub Actions: "
        f"{sorted(advertised - enforced)}"
    )

    for workflow in WORKFLOW_FILES:
        assert "make code-health-gates" in workflow.read_text(encoding="utf-8"), (
            f"{workflow.relative_to(ROOT)} must invoke the code-health aggregate explicitly."
        )


def _workflows_triggered_by_push_to_main() -> list[Path]:
    """Return workflow files whose push trigger includes main.

    yaml parses the bare ``on:`` key as boolean True, so both spellings are read.
    """

    triggered = []
    for path in WORKFLOW_FILES:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        push = (document.get("on") or document.get(True) or {}).get("push") or {}
        if "main" in (push.get("branches") or []):
            triggered.append(path)
    return triggered


def test_merged_pr_dispatch_binds_main_releasability_to_exact_sha() -> None:
    """A merged PR must dispatch one gate for every revision it puts on main.

    It dispatched one, for `merge_commit_sha`. This repository merges by rebase, so a
    pull request holding N commits puts N on main and only the last was the merge SHA:
    PR #189 held two, and 762a401 -- the earlier -- was never evaluated by any run. That
    is not a failure anywhere, which is why it went unnoticed; the loss is on rollback
    and bisect, where a commit that was never head becomes the deployed tree (#174).
    """

    dispatcher = (ROOT / ".github/workflows/merged-pr-main-releasability.yml").read_text(
        encoding="utf-8"
    )
    main_gate = (ROOT / ".github/workflows/main-releasability.yml").read_text(encoding="utf-8")

    assert not _workflows_triggered_by_push_to_main()
    assert "MERGE_COMMIT_SHA: ${{ github.event.pull_request.merge_commit_sha }}" in dispatcher
    assert "COMMIT_COUNT: ${{ github.event.pull_request.commits }}" in dispatcher
    # Every revision the PR added, bounded by what actually landed: base..merge. The
    # count-bounded `rev-list -n COMMIT_COUNT` form walked off the end of the PR's own
    # history whenever a rebase dropped a commit already on main, because
    # pull_request.commits describes the branch when the event fired, not what landed
    # (lotus-platform#859, #310). The count survives only as a cross-check.
    assert "BASE_SHA: ${{ github.event.pull_request.base.sha }}" in dispatcher
    assert 'revisions="$(git rev-list --reverse "$BASE_SHA..$MERGE_COMMIT_SHA")"' in dispatcher
    assert 'git rev-list -n "$COMMIT_COUNT"' not in dispatcher
    assert "for revision in $revisions; do" in dispatcher
    assert 'dispatch_ref="main-releasability-${revision}"' in dispatcher
    assert '-f expected_sha="$revision"' in dispatcher
    # The whole history has to be present for the earlier revisions to be enumerable.
    assert "fetch-depth: 0" in dispatcher
    assert "expected_sha:" in main_gate
    assert 'actual_sha="$(git rev-parse HEAD)"' in main_gate
    assert "inputs.expected_sha || github.sha" in main_gate
    parsed = yaml.safe_load(main_gate)
    roots = {
        name
        for name, job in parsed["jobs"].items()
        if name != "exact-revision-assertion" and "needs" not in job
    }
    assert roots == set()


def test_make_dependency_inventory_does_not_cross_target_boundaries() -> None:
    """A dependency parser must not consume recipe lines or the next target as dependencies."""

    parsed = make_dependencies(
        "first:\n\tpython first.py\n\nsecond: dependency\n\tpython second.py\n"
    )

    assert parsed == {"first": (), "second": ("dependency",)}


def test_every_compiling_test_job_declares_the_render_runtime() -> None:
    """The golden suites compile real PDFs; that dependency must be declared, not assumed.

    Before issue #109 no workflow installed or checked for Typst or Docker: the compiles
    happened only because GitHub's runner image ships Docker on PATH. A runner image
    change would have turned real rendering into confusing collection errors, and a
    change that stopped reaching the runtime would have looked like a faster green lane.
    """

    for path in WORKFLOW_FILES:
        text = path.read_text(encoding="utf-8")
        if "pytest" not in text:
            continue
        assert "make render-runtime-gate" in text, (
            f"{path.name} runs pytest but never verifies the render runtime is present, so a "
            "runner without docker or typst would fail confusingly instead of by name."
        )


def test_the_commit_enumeration_states_the_merge_method_it_depends_on() -> None:
    """ "The last N commits ending at the merge SHA" is true of a rebase merge only.

    A squash adds one commit however many the PR held, so N-1 of the dispatches would
    name revisions belonging to earlier pull requests. A merge commit adds a second
    parent, so `rev-list -n N` walks into main's own history. Either would gate the
    wrong set of trees and report success, which is worse than the gap it replaces, so
    the dispatcher asserts the setting rather than assuming it.
    """

    dispatcher = (ROOT / ".github/workflows/merged-pr-main-releasability.yml").read_text(
        encoding="utf-8"
    )

    assert "allow_squash_merge, .allow_merge_commit, .allow_rebase_merge" in dispatcher
    assert "rebase-only merging" in dispatcher


def test_the_gate_coverage_audit_runs_and_can_fail() -> None:
    """A gap in gate coverage is not a failure anywhere, so something must look for it.

    The dispatcher fires a run per revision a pull request adds (#174); this audit is
    what proves it kept doing so. Configured is not running, so this asserts the
    schedule exists and that the invocation passes `--fail-on-gap` -- reporting a gap
    without failing on it is the arrangement that let the first one sit unnoticed.

    It cannot be in `make check`, which runs offline, and it cannot be inside the
    releasability gate: the runs for a multi-commit pull request are dispatched
    together, so an audit within one of them would race the others.
    """

    workflow_path = ROOT / ".github/workflows/main-gate-coverage-audit.yml"
    assert workflow_path.exists(), "nothing audits which commits the gate evaluated"

    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    # `on` is parsed as the boolean True by YAML 1.1, which is what PyYAML implements.
    triggers = workflow.get("on", workflow.get(True))

    assert "schedule" in triggers, "the audit is dispatch-only, so nothing runs it"
    assert triggers["schedule"], "the schedule declares no cron entry"

    steps = workflow["jobs"]["audit"]["steps"]
    invocation = "\n".join(step.get("run", "") for step in steps)
    assert "audit_main_gate_coverage.py" in invocation
    assert "--fail-on-gap" in invocation, (
        "the audit reports gaps without failing on them, which is how the first one sat unnoticed"
    )


def test_the_gate_coverage_audit_cannot_pass_by_inspecting_nothing() -> None:
    """The audit is itself a gate, and it had all three ways of verifying nothing.

    `gh` missing printed a line and returned 0. Any API failure marked a commit
    "unknown" and unknowns never failed, so a fully rate-limited run printed
    "audited 0 commit(s); 0 with no run" and exited green. And it asked for each run's
    conclusion, then counted rows -- so a cancelled dispatch, which evaluated nothing,
    counted as evidence that the commit was gated.

    That is the same liveness class the script exists to catch, in the script.
    """

    source = (ROOT / "scripts/audit_main_gate_coverage.py").read_text(encoding="utf-8")

    # Only a run that reached a verdict is evidence.
    assert 'VERDICT_CONCLUSIONS = frozenset({"success", "failure"})' in source
    assert 'run.get("conclusion") in VERDICT_CONCLUSIONS' in source
    # A commit that could not be checked is not a commit that is fine, and a window the
    # audit stopped part-way through is not a window it inspected.
    assert (
        "return 1 if ((ungated or unknown or truncated) and arguments.fail_on_gap) else 0" in source
    )
    # And an audit that could not run at all must not report success.
    assert "Refusing to report success" in source


def test_the_audit_separates_a_run_in_flight_from_no_run_at_all() -> None:
    """Counting only verdicts made a commit merged two minutes ago look ungated.

    Pending is neither evidence nor a gap. Failing on it would make the daily audit
    report a false gap whenever a merge lands near the schedule, so it is named instead
    -- which is also how a run that never finishes stays visible.
    """

    source = (ROOT / "scripts/audit_main_gate_coverage.py").read_text(encoding="utf-8")

    assert "PENDING" in source
    assert "still going" in source
    # Pending is deliberately not part of the failure condition.
    assert "ungated or unknown" in source
    assert "pending or" not in source


def test_the_audit_window_is_a_span_of_time_rather_than_a_count() -> None:
    """A count narrows exactly when the repository is busiest.

    The audit looked at the last 40 commits, once a day. At this repository's rate that
    is about a day, so a busy day pushed the earliest out of sight before the next run
    looked -- and eleven commits from 2026-08-29, by then 71 to 92 behind head, had aged
    past it ungated and unreported by anything. Three of them turned out to fail their
    own releasability gate.

    The count survives as a ceiling on the loop, and reaching it is reported as a gap:
    a prefix of the window is not the window.
    """

    source = (ROOT / "scripts/audit_main_gate_coverage.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/main-gate-coverage-audit.yml").read_text(encoding="utf-8")

    assert "--since=" in source, "the window is not selected by time"
    assert "truncated = len(commits) >= arguments.limit" in source
    assert "--since" in workflow, "the scheduled run still passes a commit count"
    assert "--limit" not in workflow, "a count in the workflow is a window that ages out"


def test_the_scheduled_audit_is_watched_by_something_that_is_not_a_schedule() -> None:
    """A cron that stops firing fails nowhere, which is the class the audit exists for.

    GitHub disables scheduled workflows after sixty days of repository inactivity, and an
    edit that breaks the cron expression stops it silently. So the merge dispatcher --
    the one trigger driven by the activity that creates the commits the audit checks --
    asks when the audit last ran. Success is a different question: a failed protection
    step still proves the schedule executed, and must remain visible under its own name.

    It is a separate job, because a check that cannot fail the run is not a check, and
    one that blocks the dispatch it is watching would be worse than the gap.
    """

    source = (ROOT / "scripts/audit_main_gate_coverage.py").read_text(encoding="utf-8")
    dispatcher = (ROOT / ".github/workflows/merged-pr-main-releasability.yml").read_text(
        encoding="utf-8"
    )

    assert "--assert-recent-audit" in source
    assert "has never run" in source, "never-run is not distinguished"
    assert "Refusing to report success" in source, "an unanswerable check is not a pass"
    assert "audit-liveness:" in dispatcher, "nothing checks that the audit still runs"
    assert "--assert-recent-audit 40" in dispatcher
    assert "continue-on-error" not in dispatcher, "a check that cannot fail is not a check"


def test_a_recent_failed_audit_is_live_and_names_the_independent_outcomes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A protection failure is not evidence that the daily schedule stopped running."""

    created_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    answers = iter(
        [
            subprocess.CompletedProcess(
                [],
                0,
                stdout=json.dumps(
                    [
                        {
                            "createdAt": created_at,
                            "conclusion": "failure",
                            "databaseId": 123,
                            "status": "completed",
                            "url": "https://example.invalid/run/123",
                        }
                    ]
                ),
                stderr="",
            ),
            subprocess.CompletedProcess(
                [],
                0,
                stdout=json.dumps(
                    {
                        "jobs": [
                            {
                                "steps": [
                                    {
                                        "name": "Audit which commits on main were gated",
                                        "conclusion": "success",
                                    },
                                    {
                                        "name": "Enforce Branch Protection Policy",
                                        "conclusion": "failure",
                                    },
                                ]
                            }
                        ]
                    }
                ),
                stderr="",
            ),
        ]
    )
    commands: list[list[str]] = []

    def _run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return next(answers)

    monkeypatch.setattr("scripts.audit_main_gate_coverage.subprocess.run", _run)

    assert audit_main_gate_coverage._assert_recent_audit(40) == 0
    output = capsys.readouterr().out
    assert "Execution freshness:" in output
    assert "Commit coverage: success." in output
    assert "Branch protection: failure." in output
    assert "stopped running" not in output
    assert "--status=success" not in commands[0]
    assert commands[1][:4] == ["gh", "run", "view", "123"]


def test_a_refused_dispatch_tag_falls_back_to_a_pinned_main_dispatch() -> None:
    """GITHUB_TOKEN cannot tag a revision whose tree changes .github/workflows (#310).

    The refusal lacks the `workflows` scope, so every workflow-touching merge used to
    dispatch nothing and main showed no run at all -- which reads as success in every
    interface. Only that refusal falls back to dispatching main's gate definition; the
    tree under test stays the revision because every checkout in the gate is pinned
    to `expected_sha`, and the gate titles the run with it so the audit can find it.
    """

    dispatcher = (ROOT / ".github/workflows/merged-pr-main-releasability.yml").read_text(
        encoding="utf-8"
    )
    main_gate = (ROOT / ".github/workflows/main-releasability.yml").read_text(encoding="utf-8")

    # Only the scope refusal is tolerated, classified on the API's own status and
    # message fields rather than on gh's prose; any other failure is fatal.
    assert '[ "$create_status" = "403" ]' in dispatcher
    assert '[ "$create_message" = "Resource not accessible by integration" ]' in dispatcher
    assert '[ "$lookup_status" != "404" ]' in dispatcher
    assert 'dispatch_ref="main"' in dispatcher
    # The ref lookup's own failure is never masked (a masked lookup creates a tag it
    # should have refused, which the platform validator rejects by name).
    assert "|| true" not in dispatcher
    parsed = yaml.safe_load(main_gate)
    checkouts = [
        step
        for job in parsed["jobs"].values()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, "the gate must check the repository out somewhere"
    for step in checkouts:
        assert step.get("with", {}).get("ref") == "${{ inputs.expected_sha || github.sha }}", (
            "a checkout without the pin tests the dispatch ref's tip -- main's, under the "
            "fallback -- and reports it as this revision's verdict"
        )
    expected_title = "Main Releasability Gate for ${{ inputs.expected_sha || github.sha }}"
    assert parsed["run-name"] == expected_title
    # Release evidence names the tree that was built, not the ref's tip.
    assert "TESTED_SHA: ${{ inputs.expected_sha || github.sha }}" in main_gate
    assert '"commit_sha": os.environ["TESTED_SHA"]' in main_gate


def test_a_run_dispatched_at_main_is_attributed_to_the_revision_in_its_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fallback run carries main's tip as head SHA, so `--commit` cannot find it (#310).

    Before the title attribution every revision gated through the fallback was
    reported UNGATED -- the audit inverting the dispatcher's own recovery. The title,
    and only the title, attributes such a run; a tag-dispatched run is found by
    `--commit` and must not be counted a second time by its title.
    """

    revision = "a" * 40
    main_tip = "b" * 40
    titled: list[dict[str, object]] = [
        {
            "databaseId": 6,
            "conclusion": "success",
            "displayTitle": f"Main Releasability Gate for {revision}",
            "headSha": main_tip,
        },
        {
            "databaseId": 7,
            "conclusion": "success",
            "displayTitle": f"Main Releasability Gate for {main_tip}",
            "headSha": main_tip,
        },
    ]
    commands: list[list[str]] = []

    def _nothing_by_commit(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess([], 0, stdout="[]", stderr="")

    monkeypatch.setattr("scripts.audit_main_gate_coverage.subprocess.run", _nothing_by_commit)
    monkeypatch.setattr(
        audit_main_gate_coverage,
        "_run_details",
        lambda run_id: next(run for run in titled if run["databaseId"] == run_id),
    )

    assert audit_main_gate_coverage._run_count(revision, titled) == 1
    assert "--commit" in commands[0], "the per-revision query remains the primary evidence"
    # A title naming a different revision is not evidence for this one.
    assert audit_main_gate_coverage._run_count("c" * 40, titled) == 0
    # Without the title index the fallback run is invisible, exactly the old gap.
    assert audit_main_gate_coverage._run_count(revision, None) == 0

    def _one_by_commit(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                [
                    {
                        "databaseId": 7,
                        "conclusion": "failure",
                        "displayTitle": f"Main Releasability Gate for {main_tip}",
                        "headSha": main_tip,
                        "status": "completed",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr("scripts.audit_main_gate_coverage.subprocess.run", _one_by_commit)
    monkeypatch.setattr(
        audit_main_gate_coverage,
        "_run_details",
        lambda run_id: (
            {
                "databaseId": 7,
                "conclusion": "failure",
                "displayTitle": f"Main Releasability Gate for {main_tip}",
                "headSha": main_tip,
                "status": "completed",
            }
            if run_id == 7
            else titled[0]
        ),
    )
    assert audit_main_gate_coverage._run_count(main_tip, titled) == 1, (
        "the tag-dispatched run was found by --commit; its own title must not double it"
    )


def test_a_fallback_run_never_credits_its_workflow_definition_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback definition/head B can execute tested source A, never both."""

    source = "a" * 40
    definition = "b" * 40
    fallback = {
        "databaseId": 17,
        "conclusion": "success",
        "displayTitle": f"Main Releasability Gate for {source}",
        "headSha": definition,
        "status": "completed",
    }
    monkeypatch.setattr(
        "scripts.audit_main_gate_coverage.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, stdout=json.dumps([fallback]), stderr=""
        ),
    )
    monkeypatch.setattr(audit_main_gate_coverage, "_run_details", lambda _run_id: fallback)

    assert audit_main_gate_coverage._run_count(source, [fallback]) == 1
    assert audit_main_gate_coverage._run_count(definition, [fallback]) == 0


@pytest.mark.parametrize(
    ("status", "conclusion", "expected_exit", "expected_label"),
    [
        ("completed", "cancelled", 1, "UNGATED"),
        ("completed", "skipped", 1, "UNGATED"),
        ("in_progress", None, 0, "PENDING"),
    ],
)
def test_shipped_audit_cli_distinguishes_terminal_nonverdicts_from_live_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    conclusion: str | None,
    expected_exit: int,
    expected_label: str,
) -> None:
    """`--fail-on-gap` must not let cancelled/skipped histories masquerade as pending."""

    revision = "d" * 40
    monkeypatch.setattr(
        audit_main_gate_coverage,
        "_git",
        lambda *args: (
            [f"{revision} deadbee controlled temporary history"]
            if args[0] == "log" and "--format=%H %h %s" in args
            else ["2026-09-13"]
        ),
    )
    run = {
        "databaseId": 91,
        "displayTitle": f"Main Releasability Gate for {revision}",
        "headSha": revision,
        "status": status,
        "conclusion": conclusion,
    }
    monkeypatch.setattr(
        "scripts.audit_main_gate_coverage.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                run
                if command[1:3] == ["run", "view"]
                else ([] if "--created" in command else [run])
            ),
            stderr="",
        ),
    )
    monkeypatch.setattr("sys.argv", ["audit", "--since", "1 day ago", "--fail-on-gap"])

    assert audit_main_gate_coverage.main() == expected_exit
    assert expected_label in capsys.readouterr().out


def _audit_history(tmp_path: Path) -> tuple[Path, str, str]:
    """Create two real immutable main revisions for the shipped audit CLI."""

    repository = tmp_path / "audit-history"
    repository.mkdir()
    commands = (
        ("init", "-q", "-b", "main"),
        ("config", "user.email", "audit@example.invalid"),
        ("config", "user.name", "audit"),
    )
    for command in commands:
        subprocess.run(["git", *command], cwd=repository, check=True)
    document = repository / "evidence.txt"
    document.write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "add", "evidence.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "revision A"], cwd=repository, check=True)
    source_a = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    document.write_text("A\nB\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "revision B"], cwd=repository, check=True)
    source_b = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", source_b], cwd=repository, check=True
    )
    return repository, source_a, source_b


def _write_recording_gh(tmp_path: Path, fixture: dict[str, object]) -> tuple[Path, Path]:
    """Install a recording GitHub CLI boundary for the child-process audit exercise."""

    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    fixture_path = tmp_path / "github-runs.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    calls_path = tmp_path / "github-calls.jsonl"
    boundary = binary_directory / "recording_gh.py"
    boundary.write_text(
        "\n".join(
            (
                "import json, os, sys",
                "arguments = sys.argv[1:]",
                "with open(os.environ['AUDIT_GH_CALLS'], 'a', encoding='utf-8') as calls:",
                "    calls.write(json.dumps(arguments) + '\\n')",
                "with open(os.environ['AUDIT_GH_FIXTURE'], encoding='utf-8') as source:",
                "    fixture = json.load(source)",
                "if arguments[:2] == ['run', 'view']:",
                "    answer = fixture['details'][arguments[2]]",
                "elif arguments[:2] == ['run', 'list'] and '--created' in arguments:",
                "    answer = fixture['titled']",
                "elif arguments[:2] == ['run', 'list']:",
                "    sha = arguments[arguments.index('--commit') + 1]",
                "    answer = fixture['by_commit'].get(sha, [])",
                "else:",
                "    raise SystemExit('unexpected gh command: ' + repr(arguments))",
                "print(json.dumps(answer))",
            )
        ),
        encoding="utf-8",
    )
    # Windows' CreateProcess only discovers real executable extensions for a bare
    # ``gh`` argv[0], while the shipped audit deliberately invokes the ordinary CLI
    # name.  A process-startup hook gives both Windows and Linux the same recording
    # boundary without replacing the actual Git subprocesses that build the history.
    # The audit still runs as its own process and performs its normal gh list/view
    # calls; only the unavailable external network is replaced.
    (binary_directory / "sitecustomize.py").write_text(
        "\n".join(
            (
                "import json, os, shutil, subprocess",
                "_real_run = subprocess.run",
                "_real_which = shutil.which",
                "def _run(command, *args, **kwargs):",
                "    if isinstance(command, list) and command and command[0] == 'gh':",
                "        with open(os.environ['AUDIT_GH_CALLS'], 'a', encoding='utf-8') as calls:",
                "            calls.write(json.dumps(command[1:]) + '\\n')",
                "        with open(os.environ['AUDIT_GH_FIXTURE'], encoding='utf-8') as source:",
                "            fixture = json.load(source)",
                "        arguments = command[1:]",
                "        if arguments[:2] == ['run', 'view']:",
                "            answer = fixture['details'][arguments[2]]",
                "        elif arguments[:2] == ['run', 'list'] and '--created' in arguments:",
                "            answer = fixture['titled']",
                "        elif arguments[:2] == ['run', 'list']:",
                "            sha = arguments[arguments.index('--commit') + 1]",
                "            answer = fixture['by_commit'].get(sha, [])",
                "        else:",
                "            raise AssertionError('unexpected gh command: ' + repr(arguments))",
                "        result = subprocess.CompletedProcess(command, 0,",
                "            stdout=json.dumps(answer), stderr='')",
                "        return result",
                "    return _real_run(command, *args, **kwargs)",
                "subprocess.run = _run",
                "def _which(name, *args, **kwargs):",
                "    return 'recording-gh' if name == 'gh' else _real_which(name, *args, **kwargs)",
                "shutil.which = _which",
            )
        ),
        encoding="utf-8",
    )
    return binary_directory, calls_path


def _run_shipped_audit(
    tmp_path: Path, fixture_for_sources: Callable[[str, str], dict[str, object]]
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], str, str]:
    repository, source_a, source_b = _audit_history(tmp_path)
    fixture = fixture_for_sources(source_a, source_b)
    binary_directory, calls_path = _write_recording_gh(tmp_path, fixture)
    git = shutil.which("git")
    assert git is not None, "the shipped audit CLI requires Git to inspect main history"
    constrained_path = os.pathsep.join(
        (str(binary_directory), str(Path(git).parent), str(Path(sys.executable).parent))
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_main_gate_coverage.py"),
            "--since",
            "2000-01-01",
            "--fail-on-gap",
        ],
        cwd=repository,
        env={
            **os.environ,
            "PATH": constrained_path,
            "AUDIT_GH_CALLS": str(calls_path),
            "AUDIT_GH_FIXTURE": str(tmp_path / "github-runs.json"),
            "PYTHONPATH": str(binary_directory),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = (
        [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()]
        if calls_path.exists()
        else []
    )
    return completed, calls, source_a, source_b


def test_shipped_audit_cli_keeps_fallback_source_separate_from_definition_head(
    tmp_path: Path,
) -> None:
    """A real Git history plus GitHub boundary proves A is covered and B is not."""

    def fixture(source_a: str, source_b: str) -> dict[str, object]:
        fallback = {
            "databaseId": 101,
            "displayTitle": f"Main Releasability Gate for {source_a}",
            "headSha": source_b,
            "status": "completed",
            "conclusion": "success",
        }
        malformed = {
            "databaseId": 102,
            "displayTitle": "Main Releasability Gate for not-an-immutable-sha",
            "headSha": source_b,
            "status": "completed",
            "conclusion": "success",
        }
        unrelated = {
            "databaseId": 103,
            "displayTitle": "manual historical entry",
            "headSha": source_b,
            "status": "completed",
            "conclusion": "success",
        }
        return {
            "titled": [fallback, malformed, unrelated],
            "by_commit": {source_a: [fallback], source_b: []},
            "details": {str(run["databaseId"]): run for run in (fallback, malformed, unrelated)},
        }

    completed, calls, audit_a, audit_b = _run_shipped_audit(tmp_path, fixture)
    assert calls, (completed.stdout, completed.stderr)
    assert completed.returncode == 1
    assert f"UNGATED  {audit_b[:7]}" in completed.stdout
    assert f"UNGATED  {audit_a[:7]}" not in completed.stdout
    assert any(call[:2] == ["run", "view"] for call in calls)


@pytest.mark.parametrize("conclusion", ["success", "failure"])
def test_shipped_audit_cli_accepts_legacy_tag_history_with_each_terminal_verdict(
    tmp_path: Path, conclusion: str
) -> None:
    """An old tag run still uses its immutable head, whether it passed or failed."""

    def fixture(source_a: str, source_b: str) -> dict[str, object]:
        fallback = {
            "databaseId": 201,
            "displayTitle": f"Main Releasability Gate for {source_a}",
            "headSha": source_b,
            "status": "completed",
            "conclusion": "success",
        }
        legacy_tag = {
            "databaseId": 202,
            "displayTitle": "",
            "headSha": source_b,
            "status": "completed",
            "conclusion": conclusion,
        }
        return {
            "titled": [fallback, legacy_tag],
            "by_commit": {source_a: [fallback], source_b: [legacy_tag]},
            "details": {"201": fallback, "202": legacy_tag},
        }

    completed, calls, source_a, source_b = _run_shipped_audit(tmp_path, fixture)
    assert completed.returncode == 0, completed.stdout
    assert "UNGATED" not in completed.stdout
    assert source_a and source_b
    assert [call[2] for call in calls if call[:2] == ["run", "view"]].count("201") == 2
    assert [call[2] for call in calls if call[:2] == ["run", "view"]].count("202") == 2


@pytest.mark.parametrize(
    ("status", "conclusion", "expected_exit", "expected_label"),
    [
        ("completed", "cancelled", 1, "UNGATED"),
        ("completed", "skipped", 1, "UNGATED"),
        ("in_progress", None, 0, "PENDING"),
    ],
)
def test_shipped_audit_cli_classifies_terminal_nonverdicts_and_live_runs(
    tmp_path: Path,
    status: str,
    conclusion: str | None,
    expected_exit: int,
    expected_label: str,
) -> None:
    """The actual CLI reserves PENDING for live work, not completed non-verdicts."""

    def fixture(source_a: str, source_b: str) -> dict[str, object]:
        valid = {
            "databaseId": 301,
            "displayTitle": "",
            "headSha": source_a,
            "status": "completed",
            "conclusion": "success",
        }
        candidate = {
            "databaseId": 302,
            "displayTitle": "",
            "headSha": source_b,
            "status": status,
            "conclusion": conclusion,
        }
        return {
            "titled": [valid, candidate],
            "by_commit": {source_a: [valid], source_b: [candidate]},
            "details": {"301": valid, "302": candidate},
        }

    completed, _calls, _source_a, source_b = _run_shipped_audit(tmp_path, fixture)
    assert completed.returncode == expected_exit, completed.stdout
    assert f"{expected_label}  {source_b[:7]}" in completed.stdout


def test_run_detail_fetches_are_deduplicated_by_stable_run_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The listing overlap is discovery-only; each run is resolved exactly once."""

    source = "a" * 40
    run = {
        "databaseId": 404,
        "displayTitle": f"Main Releasability Gate for {source}",
        "headSha": "b" * 40,
        "status": "completed",
        "conclusion": "success",
    }
    monkeypatch.setattr(
        "scripts.audit_main_gate_coverage.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, stdout=json.dumps([run]), stderr=""
        ),
    )
    fetched: list[int] = []

    def detail(run_id: int) -> dict[str, object]:
        fetched.append(run_id)
        return run

    monkeypatch.setattr(
        audit_main_gate_coverage,
        "_run_details",
        detail,
    )

    assert audit_main_gate_coverage._run_count(source, [run]) == 1
    assert fetched == [404]


def test_the_title_index_is_bounded_by_time_rather_than_by_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same lesson as the audit window: a count is a window that ages out."""

    commands: list[list[str]] = []

    def _run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess([], 0, stdout="[]", stderr="")

    monkeypatch.setattr("scripts.audit_main_gate_coverage.subprocess.run", _run)

    assert audit_main_gate_coverage._titled_runs("2026-09-10") == []
    assert "--created" in commands[0]
    assert ">=2026-09-10" in commands[0]
    assert "displayTitle" in ",".join(commands[0])


def test_an_audit_that_really_has_not_run_lately_fails_liveness(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    created_at = (datetime.now(UTC) - timedelta(hours=41)).isoformat().replace("+00:00", "Z")
    answer = subprocess.CompletedProcess(
        [],
        0,
        stdout=json.dumps(
            [
                {
                    "createdAt": created_at,
                    "conclusion": "failure",
                    "databaseId": 456,
                    "status": "completed",
                    "url": "https://example.invalid/run/456",
                }
            ]
        ),
        stderr="",
    )
    monkeypatch.setattr(
        "scripts.audit_main_gate_coverage.subprocess.run", lambda *args, **kwargs: answer
    )

    assert audit_main_gate_coverage._assert_recent_audit(40) == 1
    output = capsys.readouterr().out
    assert "last ran 41.0h ago" in output
    assert "stopped running" in output


# Two classes of run, and the concurrency policy is the difference between them.
#
# A lane run is evidence about "this branch as it stands", so a newer push supersedes it
# and cancelling is right. A releasability run is evidence about one immutable tree, and
# it is the only such evidence there is (#79) -- so it keys on the revision and must not
# be cancelled by anything that lands after it.
EVIDENCE_WORKFLOWS = ("main-releasability.yml", "main-gate-coverage-audit.yml")
SUPERSEDABLE_WORKFLOWS = ("feature-lane.yml", "pr-merge-gate.yml")


def _concurrency(workflow: str) -> dict[str, object]:
    parsed = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    concurrency = parsed.get("concurrency")
    assert isinstance(concurrency, dict), f"{workflow} declares no concurrency policy"
    return concurrency


def test_a_run_that_is_the_only_evidence_for_a_tree_is_never_cancelled() -> None:
    """Parsed, not grepped, and asserted rather than assumed.

    The property is correct in both workflows and nothing checked it, so an edit could
    flip it back and no test would fail -- which is the same shape as the gaps in this
    file: a policy that is right today and unguarded tomorrow.

    Cancellation does not merely lose the evidence, it inverts the report.
    `audit_main_gate_coverage.py` counts only `success` and `failure` as a verdict,
    because a cancelled run evaluated nothing -- so a cancelled releasability run makes
    its commit read as **ungated**, and the audit says so. The two mechanisms are the
    same guarantee approached from opposite ends, and this is what holds them together.
    """

    for workflow in EVIDENCE_WORKFLOWS:
        concurrency = _concurrency(workflow)
        assert concurrency.get("cancel-in-progress") is False, (
            f"{workflow} allows a run in flight to be cancelled. That run is the only "
            "evidence its commit has, and a cancelled run reaches no verdict -- so the "
            "coverage audit reports the commit as ungated rather than as interrupted."
        )


def test_releasability_is_keyed_on_the_revision_rather_than_on_the_ref() -> None:
    """A ref-keyed group lets the next commit cancel the run proving the previous one.

    That is #79 exactly: the group has to name the immutable thing the run is evidence
    about. `expected_sha` leads because a dispatched backfill names the revision it was
    asked to gate; `github.sha` is the fallback, and on a tag ref it is that same
    revision.
    """

    group = str(_concurrency("main-releasability.yml").get("group", ""))

    assert "github.sha" in group or "expected_sha" in group, (
        f"the releasability concurrency group is {group!r} and names no revision."
    )
    assert "github.ref" not in group, (
        f"the releasability concurrency group is {group!r}. Keyed on a ref, a push to "
        "main cancels the run that is the previous commit's only releasability evidence."
    )


def test_the_two_concurrency_policies_stay_distinguishable() -> None:
    """Stated as a test so "make them all the same" has to confront the difference.

    The lanes should cancel: a superseded branch state is not something anyone needs a
    verdict on, and keeping those runs alive would only spend CI on trees nobody will
    ship. Asserting both halves keeps the rule readable as a rule rather than as two
    unexplained settings.
    """

    for workflow in SUPERSEDABLE_WORKFLOWS:
        concurrency = _concurrency(workflow)
        assert concurrency.get("cancel-in-progress") is True, (
            f"{workflow} keeps superseded branch runs alive; only the runs that are a "
            "commit's sole evidence need that."
        )
        assert "github.ref" in str(concurrency.get("group", "")), (
            f"{workflow} is not keyed on the ref it supersedes."
        )


def _image_building_jobs() -> list[tuple[str, str, dict[str, Any]]]:
    """Every job in every workflow that builds the release image.

    Discovered rather than listed: a third workflow that builds the image would
    otherwise inherit the defect this test exists to catch, and nothing would say so.
    """

    found = []
    for workflow in ROOT.glob(".github/workflows/*.yml"):
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            steps = job.get("steps") or []
            if any("make docker-build" in str(step.get("run", "")) for step in steps):
                found.append((workflow.name, job_name, job))
    return found


def test_every_image_build_states_the_pipeline_that_produced_it() -> None:
    """A CI build must not inherit the Makefile's workstation defaults.

    `CI_PIPELINE_ID ?= local` and a branch derived from `git rev-parse --abbrev-ref
    HEAD` are correct for a developer and wrong for CI, where `actions/checkout`
    leaves a detached HEAD. Nothing overrode them, so every image built by this
    repository reported `ci_pipeline_run_id=local` and `git_branch=HEAD` -- the
    running service asserted it was not a CI build, and the field an operator would
    use to find the pipeline named no pipeline.

    Asserted on the values rather than on presence: an override that is itself
    `local` would satisfy a presence check and reintroduce the defect.
    """

    jobs = _image_building_jobs()

    assert jobs, "no job builds the image; this test is no longer measuring anything"
    for workflow_name, job_name, job in jobs:
        build = next(
            step for step in job["steps"] if "make docker-build" in str(step.get("run", ""))
        )
        environment = build.get("env") or {}
        where = f"{workflow_name}:{job_name}"

        assert "CI_PIPELINE_ID" in environment, f"{where} builds the image without a pipeline id"
        assert "github.run_id" in environment["CI_PIPELINE_ID"], (
            f"{where} supplies a pipeline id that does not come from the run"
        )
        assert environment["CI_PIPELINE_ID"] != "local", f"{where} names the workstation default"

        assert "GIT_BRANCH" in environment, f"{where} lets the detached HEAD name the branch"
        assert "head_ref" in environment["GIT_BRANCH"], (
            f"{where} supplies a branch that is not the ref being built"
        )


def test_every_image_build_verifies_what_it_built() -> None:
    """Supplying provenance and checking it arrived are different claims.

    The build arguments were correct in the sense that they were passed; what was
    never checked is that the running image reports them. A build argument silently
    dropped by a Dockerfile edit, or an ENV overwritten later in the image, looks
    identical to a correct build from the workflow's side.
    """

    for workflow_name, job_name, job in _image_building_jobs():
        runs = " ".join(str(step.get("run", "")) for step in job["steps"])
        assert "image-provenance-check" in runs, (
            f"{workflow_name}:{job_name} builds an image and never asks it what it is"
        )
