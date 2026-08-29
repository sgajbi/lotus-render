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

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WIKI_HOME = ROOT / "wiki" / "Home.md"
WORKFLOW_FILES = tuple((ROOT / ".github" / "workflows").glob("*.yml"))


def _gate_targets() -> set[str]:
    """Every `*-gate` target actually reachable from a GitHub Actions workflow."""

    from scripts.ci_gate_inventory import gate_targets_reachable_from_workflows

    reachable = gate_targets_reachable_from_workflows(
        MAKEFILE.read_text(encoding="utf-8"),
        (path.read_text(encoding="utf-8") for path in WORKFLOW_FILES),
    )
    assert reachable, (
        "No gate targets are reachable from GitHub Actions; this check would assert nothing."
    )
    return reachable


# Gate names as the wiki actually writes them: inside backticks, usually behind `make `. The first
# version omitted the optional `make ` prefix and so matched NOTHING - 0 of 10 backticked gate
# spellings on this page - which made the reverse check pass for every possible page content.
# Requiring a hyphen before `gate` keeps prose words like "aggregate" out. See #77.
_WIKI_GATE_NAME = re.compile(r"`(?:make\s+)?([a-z0-9]+(?:-[a-z0-9]+)*-gates?)`")


def _wiki_gate_names(wiki: str) -> set[str]:
    named_in_wiki = {match.group(1) for match in _WIKI_GATE_NAME.finditer(wiki)}

    assert named_in_wiki, (
        "No gate names were found in the wiki page. Either the page stopped naming gates - which "
        "the forward check would also catch - or this pattern stopped matching how they are "
        "written, in which case this check asserts nothing. Both are failures."
    )
    return named_in_wiki


def test_the_wiki_names_every_gate_the_blocking_workflows_run() -> None:
    wiki = WIKI_HOME.read_text(encoding="utf-8")

    undocumented = sorted(target for target in _gate_targets() if target not in wiki)

    assert undocumented == [], (
        "wiki/Home.md publishes the repo-native validation commands but does not name these gates, "
        "which GitHub Actions runs and which can fail a contributor's build: "
        f"{undocumented}. See issue #72."
    )


def test_the_wiki_names_no_gate_the_blocking_lanes_have_stopped_running() -> None:
    """The reverse direction, which is the one that misleads.

    The check above fails when a gate is undocumented. It says nothing when a gate is REMOVED from
    `check`/`ci` and its wiki entry stays — leaving the page claiming a control that no longer runs.

    That is documentation overstating coverage, the same direction as a documented threshold looser
    than the enforced one (lotus-performance#476, `969` published against an enforced `879`). Both
    mislead toward believing a control exists. A reader cannot tell a stale entry from a live one,
    and the wiki is the citable page.

    Scoped to `*-gate` / `*-gates` names so it reads only what it can attribute: prose mentioning a
    gate in passing is not an entry, and this test does not try to judge prose.
    """

    wiki = WIKI_HOME.read_text(encoding="utf-8")
    live = _gate_targets()

    named_in_wiki = _wiki_gate_names(wiki)

    stale = sorted(name for name in named_in_wiki if name not in live)

    assert stale == [], (
        "wiki/Home.md names these gates, but no blocking lane in the Makefile runs them any more. "
        "A wiki entry outliving its gate claims a control that does not exist, which is the "
        f"direction that misleads: {stale}. Remove the entry or restore the gate. See issue #72."
    )


def test_the_wiki_gate_inventory_fails_closed_when_it_matches_nothing() -> None:
    """A markup change must not turn the reverse documentation check into a vacuous pass."""

    with pytest.raises(AssertionError, match="No gate names were found"):
        _wiki_gate_names("# Validation\n\nNo executable gates are documented here.\n")
