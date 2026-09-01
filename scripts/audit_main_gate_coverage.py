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

It also answers for itself. `--assert-recent-audit HOURS` asks when this workflow last
succeeded and fails when the answer is "not lately" or "never" -- run from the
merge-triggered dispatcher, which is the only trigger driven by the activity the audit
exists to check.

Usage::

    python scripts/audit_main_gate_coverage.py                    # report
    python scripts/audit_main_gate_coverage.py --fail-on-gap      # non-zero on a gap
    python scripts/audit_main_gate_coverage.py --assert-recent-audit 40
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime

WORKFLOW = "main-releasability.yml"
AUDIT_WORKFLOW = "main-gate-coverage-audit.yml"

# How far back a daily audit looks. Three days rather than one so two consecutive missed
# runs still leave every commit inspected by the third, and a time window rather than a
# commit count so a busy day cannot push a commit out of it unexamined.
DEFAULT_SINCE = "3 days ago"

# A ceiling on the loop, not a window. Reaching it means the window held more commits
# than this and the audit saw a prefix of it, which is reported as a gap rather than
# quietly treated as the whole.
DEFAULT_LIMIT = 300


def _git(*arguments: str) -> list[str]:
    completed = subprocess.run(["git", *arguments], capture_output=True, text=True, check=True)
    return [line for line in completed.stdout.splitlines() if line]


# A run only counts as evidence if it reached a verdict. A cancelled or skipped run
# evaluated nothing, and counting it says a commit was gated when the gate did not
# finish -- which is the failure this script exists to find.
VERDICT_CONCLUSIONS = frozenset({"success", "failure"})


def _run_count(sha: str) -> int | None:
    """Gate runs that reached a verdict for this commit, or None if it cannot be asked."""
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
        runs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    verdicts = sum(1 for run in runs if run.get("conclusion") in VERDICT_CONCLUSIONS)
    if verdicts:
        return verdicts
    # A run with no conclusion yet is in flight. It is not evidence, and it is not a
    # gap either -- reported as pending so a commit merged minutes ago is not called
    # ungated, and so a run that never finishes stays visible by name.
    return -1 if runs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=f"how far back to audit, as a git date expression (default {DEFAULT_SINCE!r})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"ceiling on commits inspected (default {DEFAULT_LIMIT}); reaching it is a gap",
    )
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="exit non-zero when a commit on main has no releasability run",
    )
    parser.add_argument(
        "--assert-recent-audit",
        type=int,
        metavar="HOURS",
        help="check only that this audit itself succeeded within HOURS, and exit",
    )
    arguments = parser.parse_args()

    if arguments.assert_recent_audit is not None:
        return _assert_recent_audit(arguments.assert_recent_audit)

    if shutil.which("gh") is None:
        print("gh is not available, so which commits the gate evaluated cannot be asked.")
        if arguments.fail_on_gap:
            print(
                "Refusing to report success: an audit that inspected nothing is the "
                "condition it exists to detect."
            )
            return 1
        return 0

    commits = _git(
        "log",
        f"-{arguments.limit}",
        f"--since={arguments.since}",
        "--format=%H %h %s",
        "origin/main",
    )
    truncated = len(commits) >= arguments.limit
    ungated: list[str] = []
    unknown = 0

    pending: list[str] = []
    for entry in commits:
        sha, short, subject = entry.split(" ", 2)
        count = _run_count(sha)
        if count is None:
            unknown += 1
            continue
        if count < 0:
            pending.append(f"{short}  {subject[:70]}")
            print(f"PENDING  {short}  {subject[:70]}")
            continue
        if count == 0:
            ungated.append(f"{short}  {subject[:70]}")
            print(f"UNGATED  {short}  {subject[:70]}")

    print(
        f"\naudited {len(commits) - unknown} commit(s) on main since {arguments.since}; "
        f"{len(ungated)} with no {WORKFLOW} run."
    )
    if truncated:
        print(
            f"The window held at least {arguments.limit} commits and the audit stopped "
            "there, so anything older inside it went unexamined. Raise --limit and run "
            "again: a prefix of the window is not the window."
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
    if pending:
        print(
            f"{len(pending)} commit(s) have a run still going, so they are neither gated "
            "nor a gap yet. This does not fail: a merge landing near the schedule would "
            "otherwise report one every time. A commit still pending on the next daily "
            "run is worth looking at, and is named above so it can be."
        )
    if unknown:
        print(
            f"{unknown} commit(s) could not be checked at all -- the API did not answer. "
            "Their gate coverage is unknown, which is not the same as fine."
        )
    return 1 if ((ungated or unknown or truncated) and arguments.fail_on_gap) else 0


def _assert_recent_audit(max_age_hours: int) -> int:
    """Fail when this audit has not succeeded lately, or has never succeeded.

    A schedule is not a guarantee that anything runs. GitHub disables scheduled workflows
    after sixty days of repository inactivity, and an edit that breaks the cron expression
    stops it with no failure anywhere -- the exact shape the audit itself exists to catch,
    one level up.

    Run from the merge dispatcher, because a merge is the event that creates the commits
    the audit checks. A repository quiet enough to have its schedule disabled has no new
    commits to gate, so silence there is not a gap.
    """
    completed = subprocess.run(
        [
            "gh",
            "run",
            "list",
            f"--workflow={AUDIT_WORKFLOW}",
            "--status=success",
            "--limit=1",
            "--json",
            "createdAt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"Cannot ask when {AUDIT_WORKFLOW} last succeeded: {completed.stderr.strip()}")
        print("Refusing to report success: an unanswerable liveness check is not a pass.")
        return 1
    try:
        runs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(f"{AUDIT_WORKFLOW} run list was not JSON; treating the check as failed.")
        return 1

    if not runs:
        print(
            f"{AUDIT_WORKFLOW} has never completed successfully, so no commit on main has "
            "been audited for gate coverage at all."
        )
        return 1

    last = datetime.fromisoformat(runs[0]["createdAt"].replace("Z", "+00:00"))
    age_hours = (datetime.now(UTC) - last).total_seconds() / 3600
    if age_hours > max_age_hours:
        print(
            f"{AUDIT_WORKFLOW} last succeeded {age_hours:.1f}h ago, over the {max_age_hours}h "
            "bound. It runs daily, so it has stopped running -- and while it is stopped, an "
            "ungated commit on main reports nothing anywhere."
        )
        return 1

    print(f"{AUDIT_WORKFLOW} last succeeded {age_hours:.1f}h ago, within {max_age_hours}h.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
