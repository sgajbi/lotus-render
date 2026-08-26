"""The wiki claims to list the repo-native gates, so it must list all of them.

`wiki/Home.md` publishes the validation commands contributors are told to run. When #72 added four
blocking code-health gates, that page still described the previous set - and nothing noticed,
because no check compares what the wiki claims against what `check` and `ci` actually run.

That is the same shape as the documented-versus-enforced drift found across this estate: a durable
document restating something the build owns, kept in step by hand. Here the fix has to be a check
rather than a citation, because the wiki is prose for people and cannot simply point at a Makefile
target.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WIKI_HOME = ROOT / "wiki" / "Home.md"


def _targets_in(lane: str) -> list[str]:
    match = re.search(rf"^{lane}: (.+)$", MAKEFILE.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"The {lane} lane is missing from the Makefile."
    return match.group(1).split()


def _is_gate(target: str) -> bool:
    return target.endswith("-gate") or target.endswith("-gates")


def _gate_targets() -> set[str]:
    """Every `*-gate` target reachable from the blocking lanes, including aggregate members."""

    makefile = MAKEFILE.read_text(encoding="utf-8")
    reachable: set[str] = set()
    for lane in ("check", "ci"):
        for target in _targets_in(lane):
            if not _is_gate(target):
                continue
            reachable.add(target)
            aggregate = re.search(rf"^{re.escape(target)}: (.+)$", makefile, re.M)
            if aggregate:
                reachable.update(m for m in aggregate.group(1).split() if _is_gate(m))
    assert reachable, (
        "No gate targets found in the blocking lanes; this check would assert nothing."
    )
    return reachable


def test_the_wiki_names_every_gate_the_blocking_lanes_run() -> None:
    wiki = WIKI_HOME.read_text(encoding="utf-8")

    undocumented = sorted(target for target in _gate_targets() if target not in wiki)

    assert undocumented == [], (
        "wiki/Home.md publishes the repo-native validation commands but does not name these gates, "
        "which `make check` or `make ci` runs and which can fail a contributor's build: "
        f"{undocumented}. See issue #72."
    )
