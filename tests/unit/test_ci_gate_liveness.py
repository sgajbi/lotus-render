"""Prove repository-native gates are reachable from blocking GitHub workflows."""

from __future__ import annotations

from pathlib import Path

import yaml

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
    # Every revision the PR added, not only the one that ended up as head.
    assert 'git rev-list -n "$COMMIT_COUNT" "$MERGE_COMMIT_SHA"' in dispatcher
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
    asks when the audit last succeeded.

    It is a separate job, because a check that cannot fail the run is not a check, and
    one that blocks the dispatch it is watching would be worse than the gap.
    """

    source = (ROOT / "scripts/audit_main_gate_coverage.py").read_text(encoding="utf-8")
    dispatcher = (ROOT / ".github/workflows/merged-pr-main-releasability.yml").read_text(
        encoding="utf-8"
    )

    assert "--assert-recent-audit" in source
    assert "has never completed successfully" in source, "never-run is not distinguished"
    assert "Refusing to report success" in source, "an unanswerable check is not a pass"
    assert "audit-liveness:" in dispatcher, "nothing checks that the audit still runs"
    assert "--assert-recent-audit 40" in dispatcher
    assert "continue-on-error" not in dispatcher, "a check that cannot fail is not a check"
