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


def test_push_to_main_workflows_key_concurrency_on_the_commit() -> None:
    """A run validating an immutable commit must never be cancelled by a later commit.

    On main, ``github.ref`` is the same for every run, so a ref-keyed group with
    cancel-in-progress lets each new commit silently destroy the only releasability
    evidence for the previous one. Cancellation is not failure, so nothing reports
    the loss (issue #79). Ref-keyed groups stay correct for PR and feature lanes,
    where a new push supersedes the head under validation.
    """

    push_main = _workflows_triggered_by_push_to_main()
    assert push_main, "No workflow is triggered by push to main; the gate itself is missing."

    for path in push_main:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        concurrency = document.get("concurrency") or {}
        group = str(concurrency.get("group", ""))
        assert "github.sha" in group and "github.ref" not in group, (
            f"{path.name}: push-to-main concurrency must key on the commit, not the ref; "
            f"got group={group!r}"
        )
        assert concurrency.get("cancel-in-progress") is False, (
            f"{path.name}: releasability evidence must never be cancelled; "
            "set cancel-in-progress: false"
        )


def test_make_dependency_inventory_does_not_cross_target_boundaries() -> None:
    """A dependency parser must not consume recipe lines or the next target as dependencies."""

    parsed = make_dependencies(
        "first:\n\tpython first.py\n\nsecond: dependency\n\tpython second.py\n"
    )

    assert parsed == {"first": (), "second": ("dependency",)}
