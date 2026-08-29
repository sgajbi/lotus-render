"""Inventory Make gate targets that are reachable from GitHub Actions workflows."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_MAKE_TARGET = re.compile(r"^([A-Za-z0-9_.-]+):[ \t]*([^\r\n]*)$", re.MULTILINE)
_MAKE_INVOCATION = re.compile(r"\bmake\s+([A-Za-z0-9_.-]+)\b")


def make_dependencies(makefile: str) -> dict[str, tuple[str, ...]]:
    """Return declared Make target dependencies from a Makefile."""

    return {
        match.group(1): tuple((match.group(2) or "").split())
        for match in _MAKE_TARGET.finditer(makefile)
    }


def reachable_targets(
    roots: Iterable[str], dependencies: Mapping[str, tuple[str, ...]]
) -> set[str]:
    """Expand Make dependencies transitively without treating recipe text as a target."""

    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        target = pending.pop()
        if target in reachable:
            continue
        reachable.add(target)
        pending.extend(dependencies.get(target, ()))
    return reachable


def gate_targets_reachable_from_lanes(
    makefile: str, lanes: Iterable[str] = ("check", "ci")
) -> set[str]:
    """Return gate targets advertised by the repository-native aggregate lanes."""

    targets = reachable_targets(lanes, make_dependencies(makefile))
    return {target for target in targets if target.endswith(("-gate", "-gates"))}


def workflow_make_targets(workflows: Iterable[str]) -> set[str]:
    """Return Make targets invoked directly by one or more workflow documents."""

    return {
        match.group(1) for workflow in workflows for match in _MAKE_INVOCATION.finditer(workflow)
    }


def gate_targets_reachable_from_workflows(makefile: str, workflows: Iterable[str]) -> set[str]:
    """Return gates actually reachable from GitHub Actions, including aggregate dependencies."""

    dependencies = make_dependencies(makefile)
    targets = reachable_targets(workflow_make_targets(workflows), dependencies)
    return {target for target in targets if target.endswith(("-gate", "-gates"))}
