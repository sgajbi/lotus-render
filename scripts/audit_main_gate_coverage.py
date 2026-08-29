"""Which commits on main were never evaluated by the releasability gate.

`main-releasability.yml` is triggered by `push` to main, and GitHub fires a push event
**once per push, for the head commit**. A push carrying two commits therefore produces
one run, and the earlier commit has no releasability evidence of its own.

Measured on this repository:

    a05b22f  committed 2026-08-29T09:37:10Z   runs: 0
    3fcd307  committed 2026-08-29T09:37:10Z   runs: 1   created 09:37:13Z

Identical commit timestamps, one run, for the head. `a05b22f` is the commit that bound
each template manifest to the bytes it describes -- a gate in its own right -- and
nothing ever validated the tree at that commit.

#79 established that per-commit evidence is the intent: the concurrency group is keyed
on `github.sha` precisely so a newer commit cannot cancel the run that is "the only
releasability evidence for the previous one". This is the same requirement failing the
other way -- the run is not cancelled, it is never created.

The gap matters on rollback and bisect, where a commit that was never head becomes the
deployed tree.

Usage::

    python scripts/audit_main_gate_coverage.py              # report
    python scripts/audit_main_gate_coverage.py --fail-on-gap  # exit non-zero on a gap
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess

WORKFLOW = "main-releasability.yml"


def _git(*arguments: str) -> list[str]:
    completed = subprocess.run(["git", *arguments], capture_output=True, text=True, check=True)
    return [line for line in completed.stdout.splitlines() if line]


def _run_count(sha: str) -> int | None:
    """How many gate runs exist for this exact commit, or None if it cannot be asked."""
    completed = subprocess.run(
        [
            "gh",
            "run",
            "list",
            f"--workflow={WORKFLOW}",
            "--commit",
            sha,
            "--json",
            "conclusion",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        return len(json.loads(completed.stdout))
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="commits to audit (default 20)")
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="exit non-zero when a commit on main has no releasability run",
    )
    arguments = parser.parse_args()

    if shutil.which("gh") is None:
        print("gh is not available; cannot ask which commits the gate evaluated.")
        return 0

    commits = _git("log", f"-{arguments.limit}", "--format=%H %h %s", "origin/main")
    ungated: list[str] = []
    unknown = 0

    for entry in commits:
        sha, short, subject = entry.split(" ", 2)
        count = _run_count(sha)
        if count is None:
            unknown += 1
            continue
        if count == 0:
            ungated.append(f"{short}  {subject[:70]}")
            print(f"UNGATED  {short}  {subject[:70]}")

    print(
        f"\naudited {len(commits) - unknown} commit(s) on main; "
        f"{len(ungated)} with no {WORKFLOW} run."
    )
    if ungated:
        print(
            "A push carrying more than one commit fires the gate once, for the head. The "
            "commits above were never head, so no run evaluated their tree -- which "
            "matters on rollback and bisect, where such a commit becomes the deployed one."
        )
    return 1 if (ungated and arguments.fail_on_gap) else 0


if __name__ == "__main__":
    raise SystemExit(main())
