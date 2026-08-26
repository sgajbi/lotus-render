"""Hold the code-health baselines at the measured tree.

`lotus-render` had no code-health gates at all before issue #72: complexity, dead code, module size
and dependency hygiene could all regress indefinitely without CI noticing.

The gates were introduced at the *measured* values rather than at aspirational ones, deliberately.
Introducing a stricter bar would have meant either turning `main` red or refactoring nine functions
inside a CI change - a large behavioural diff riding along with a governance one. Banking the
measurement lands green, prevents regression immediately, and leaves the reduction as its own
reviewable work.

That only holds while the banked value equals the measurement. A threshold above the tree is slack
the next change spends, and an improvement that is not banked is an improvement that can be undone
for free. These tests assert the equality in both directions.

They also assert each gate is *capable of failing*. A target named `*-gate` that always exits zero
is worse than no gate, because a green lane then proves nothing and looks identical to one that
proves something - see lotus-risk#225, where `complexity-gate` was two `radon` report commands that
could not fail, and lotus-performance#477, where a blocking scanner was wired to nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"


def _declared(name: str) -> int:
    match = re.search(rf"^{name} \?= (\d+)$", MAKEFILE.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"{name} is no longer declared in the Makefile."
    return int(match.group(1))


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def _measured_complexity() -> tuple[int, int]:
    sys.path.insert(0, str(ROOT))
    from scripts.python_complexity_inventory import collect_complexity

    findings = collect_complexity(("src",))
    assert findings, "The complexity inventory measured nothing; a gate that inspected zero files."
    max_cc = max(finding.complexity for finding in findings)
    high = sum(1 for finding in findings if finding.rank in {"D", "E", "F"})
    return max_cc, high


def _measured_max_source_lines() -> int:
    sizes = [
        len(path.read_text(encoding="utf-8").splitlines()) for path in (ROOT / "src").rglob("*.py")
    ]
    assert sizes, "No Python sources found under src/."
    return max(sizes)


def test_the_complexity_baselines_equal_the_measured_tree() -> None:
    max_cc, high = _measured_complexity()

    assert _declared("MAX_CYCLOMATIC_COMPLEXITY") == max_cc, (
        f"MAX_CYCLOMATIC_COMPLEXITY is {_declared('MAX_CYCLOMATIC_COMPLEXITY')} but the tree "
        f"measures {max_cc}. Above the measurement is unearned slack; below it, main is already "
        "red. Re-bank it in the change that moves it."
    )
    assert _declared("MAX_HIGH_COMPLEXITY_FUNCTIONS") == high, (
        f"MAX_HIGH_COMPLEXITY_FUNCTIONS is {_declared('MAX_HIGH_COMPLEXITY_FUNCTIONS')} but the "
        f"tree measures {high} rank D-F functions."
    )


def test_the_source_size_baseline_equals_the_largest_module() -> None:
    measured = _measured_max_source_lines()

    assert _declared("SOURCE_FILE_MAX_LINES") == measured, (
        f"SOURCE_FILE_MAX_LINES is {_declared('SOURCE_FILE_MAX_LINES')} but the largest module is "
        f"{measured} lines."
    )


def test_the_complexity_gate_can_actually_fail() -> None:
    """A gate that cannot fail is not a gate. lotus-risk#225 is what that looks like in practice."""

    max_cc, _ = _measured_complexity()

    passing = _run(
        "scripts/python_complexity_inventory.py",
        "--max-cc",
        str(max_cc),
        "--max-high-complexity",
        "0",
    )
    assert passing.returncode == 0, passing.stdout + passing.stderr

    failing = _run(
        "scripts/python_complexity_inventory.py",
        "--max-cc",
        str(max_cc - 1),
        "--max-high-complexity",
        "0",
    )
    assert failing.returncode != 0, (
        "The complexity gate passed one below the measured maximum, so it cannot fail on a "
        "regression: " + failing.stdout + failing.stderr
    )


def test_the_source_size_gate_can_actually_fail() -> None:
    measured = _measured_max_source_lines()

    assert _run("scripts/source_size_gate.py", f"--max-lines={measured}").returncode == 0
    assert _run("scripts/source_size_gate.py", f"--max-lines={measured - 1}").returncode != 0


def test_every_code_health_gate_is_in_the_blocking_lanes() -> None:
    """A gate nobody runs is the other way to have no gate - lotus-performance#477."""

    makefile = MAKEFILE.read_text(encoding="utf-8")

    aggregate = re.search(r"^code-health-gates: (.+)$", makefile, re.M)
    assert aggregate is not None, "The code-health aggregate target is missing."
    gates = aggregate.group(1).split()
    assert set(gates) == {
        "complexity-gate",
        "source-size-gate",
        "dead-code-gate",
        "dependency-hygiene-gate",
    }, gates

    for lane in ("check", "ci"):
        target = re.search(rf"^{lane}: (.+)$", makefile, re.M)
        assert target is not None, f"The {lane} target is missing."
        assert "code-health-gates" in target.group(1).split(), (
            f"code-health-gates is not in the {lane} lane, so the gates would never run."
        )


# Tools the code-health gates shell out to. A gate whose tool is not declared passes locally, where
# the developer installed it by hand, and fails in CI, which installs from pyproject.toml only.
GATE_TOOLS = ("radon", "vulture", "deptry")


def test_every_tool_the_gates_invoke_is_declared_as_a_dev_dependency() -> None:
    """Local validation must be evidence about CI, and it is not when a tool is undeclared.

    This is not hypothetical: the first push of this change installed radon, vulture and deptry into
    the local virtualenv by hand and never declared them. Every gate passed locally and
    `PR Merge Gate / Tests (unit)` failed with `No module named radon`. Same defect class as
    lotus-risk#218, committed while adding the gates that were supposed to prevent it.
    """

    import tomllib

    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]["dev"]
    declared = {re.split(r"[=<>!~]", entry, maxsplit=1)[0].strip().lower() for entry in dev}

    missing = sorted(tool for tool in GATE_TOOLS if tool not in declared)
    assert missing == [], (
        f"These tools are invoked by the code-health gates but are not declared in the dev extras: "
        f"{missing}. The gates would pass locally and fail in CI."
    )


def test_the_declared_gate_tools_are_pinned_exactly() -> None:
    """A floored analyser changes the gate's verdict with no commit - lotus-risk#218."""

    import tomllib

    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]["dev"]

    floored = sorted(
        entry
        for entry in dev
        if re.split(r"[=<>!~]", entry, maxsplit=1)[0].strip().lower() in GATE_TOOLS
        and "==" not in entry
    )
    assert floored == [], f"These gate tools are floored rather than pinned: {floored}"
