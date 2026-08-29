"""Prove repository-native gates are reachable from blocking GitHub workflows."""

from __future__ import annotations

from pathlib import Path

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


def test_make_dependency_inventory_does_not_cross_target_boundaries() -> None:
    """A dependency parser must not consume recipe lines or the next target as dependencies."""

    parsed = make_dependencies(
        "first:\n\tpython first.py\n\nsecond: dependency\n\tpython second.py\n"
    )

    assert parsed == {"first": (), "second": ("dependency",)}
