"""Which commits on main were never evaluated by the releasability gate.

The gate is dispatched once per merged pull request. This repository merges by rebase,
so a pull request holding N commits puts N on main, and only the last of them is the
`merge_commit_sha` the dispatch names. The earlier ones had no releasability evidence of
their own.

Measured on this repository, PR #189:

    63dd973  fix(ci): gate release jobs on revision proof   runs: 1
    762a401  fix(ci): preserve exact-main release proof     runs: 0

#79 established that per-commit evidence is the intent: the concurrency group is keyed
on the revision precisely so a newer commit cannot cancel the run that is "the only
releasability evidence for the previous one". This is the same requirement failing the
other way -- the run is not cancelled, it is never created, and a run that never exists
reports nothing.

The gap matters on rollback and bisect, where a commit that was never head becomes the
deployed tree, and where `git bisect` cannot tell "broken" from "never validated".

The dispatcher enumerates every revision a pull request adds (#174). This script is what
proves it kept doing so, and runs daily from `main-gate-coverage-audit.yml`. It is not in
`make check`, which must run offline: it asks the API which runs exist.

Usage::

    python scripts/audit_main_gate_coverage.py               # report
    python scripts/audit_main_gate_coverage.py --fail-on-gap # exit non-zero on a gap
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
            "The gate is dispatched per merged pull request, and this repository merges "
            "by rebase, so a pull request holding N commits puts N on main. The commits "
            "above were not the one the dispatch named, so no run evaluated their tree "
            "-- which matters on rollback and bisect, where such a commit becomes the "
            "deployed one.\n"
            "\n"
            "Backfill one with:\n"
            "  gh api repos/OWNER/REPO/git/refs "
            "-f ref=refs/tags/main-releasability-SHA -f sha=SHA\n"
            "  gh workflow run main-releasability.yml --ref main-releasability-SHA "
            "-f expected_sha=SHA -f triggering_pr=backfill\n"
            "\n"
            "A commit predating those inputs takes a bare dispatch instead: the workflow "
            "that runs is the one defined at that revision, not this one."
        )
    return 1 if (ungated and arguments.fail_on_gap) else 0


if __name__ == "__main__":
    raise SystemExit(main())
