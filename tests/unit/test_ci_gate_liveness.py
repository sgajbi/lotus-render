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
