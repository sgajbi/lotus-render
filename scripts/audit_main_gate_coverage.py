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
ran and fails when the answer is "not lately" or "never" -- run from the merge-triggered
dispatcher, which is the only trigger driven by the activity the audit exists to check.
The audit's own outcome remains visible separately; a recent failed run proves the
schedule is alive, not that commit coverage or branch protection passed.

Usage::

    python scripts/audit_main_gate_coverage.py                    # report
    python scripts/audit_main_gate_coverage.py --fail-on-gap      # non-zero on a gap
    python scripts/audit_main_gate_coverage.py --assert-recent-audit 40
"""

from __future__ import annotations

import argparse
import json
import re
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
_TITLE_SOURCE = re.compile(r"^Main Releasability Gate for ([0-9a-f]{40})$")
_GATE_TITLE_PREFIX = "Main Releasability Gate for "


def _titled_runs(created_since: str) -> list[dict[str, object]] | None:
    """Gate runs in the window with the revision each one tested in its title, or None.

    A run dispatched at `main` -- the dispatcher's fallback when its per-revision tag
    write is refused for lack of the `workflows` scope (issue #310) -- carries main's
    tip as its head SHA while testing `expected_sha`, so `--commit` can never find it
    and the revision it gated would be reported as ungated. The gate writes the tested
    revision into its run title, and that is what is matched here. The window is a
    span of time, like the audit's own, not a count that ages out.
    """
    completed = subprocess.run(
        [
            "gh",
            "run",
            "list",
            f"--workflow={WORKFLOW}",
            "--created",
            f">={created_since}",
            # A ceiling, not the window: --created is the bound.
            "--limit",
            "1000",
            "--json",
            "databaseId,conclusion,displayTitle,headSha,status",
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
    return runs if isinstance(runs, list) else None


def _run_details(run_id: int) -> dict[str, object] | None:
    """Fetch one run's authoritative metadata before it becomes audit evidence.

    ``gh run list`` is a discovery index, not the identity boundary.  In particular,
    a fallback run has the *workflow definition* tree in ``headSha`` while the
    title names the immutable tree evaluated through ``expected_sha``.  Fetching by
    stable database id keeps that distinction explicit and prevents partial listing
    fields from being promoted into coverage evidence.
    """

    completed = subprocess.run(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--json",
            "databaseId,conclusion,displayTitle,headSha,status",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        detail = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return detail if isinstance(detail, dict) else None


def _candidate_run_ids(runs: list[dict[str, object]]) -> list[int] | None:
    """Deduplicate listing candidates before retrieving their complete metadata."""

    seen: set[int] = set()
    candidates: list[int] = []
    for run in runs:
        run_id = run.get("databaseId")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
            # A list row without a stable identity cannot be reconciled safely.  Do
            # not fall back to a title/head pair that could conflate distinct runs.
            return None
        if run_id not in seen:
            seen.add(run_id)
            candidates.append(run_id)
    return candidates


def _evaluated_source(run: dict[str, object]) -> str | None:
    """Return the exact tested source, never confusing it with workflow definition."""

    title = str(run.get("displayTitle") or "")
    match = _TITLE_SOURCE.fullmatch(title)
    if match:
        return match.group(1)
    if title.startswith(_GATE_TITLE_PREFIX):
        # It claims to be a governed run-name but does not carry a usable immutable
        # source identity.  Its head is the workflow-definition identity under the
        # fallback path, so it cannot be substituted as source evidence.
        return None
    if title:
        # An unrelated/malformed title is not source identity.  In particular, do
        # not let a fall-back run with a presentation change silently credit the
        # workflow-definition tree.  It stays visible in the queried history but
        # cannot erase a separate valid record for the same source.
        return None
    # Older tag-dispatched history can have no display title.  It is attributable
    # only in that narrow legacy case, through its immutable tag/head identity.
    head_sha = run.get("headSha")
    return head_sha if isinstance(head_sha, str) else None


def _run_count(sha: str, titled_runs: list[dict[str, object]] | None) -> int | None:
    """Gate runs that reached a verdict for this commit, or None if it cannot be asked.

    Two attributions, because two dispatch paths exist: a tag-dispatched run has the
    revision as its head SHA and `--commit` finds it; a main-dispatched run names the
    revision only in its title (issue #310). A titled run whose head SHA is the
    revision is the same run the first query returned, and is not counted twice.
    """
    completed = subprocess.run(
        [
            "gh",
            "run",
            "list",
            f"--workflow={WORKFLOW}",
            "--commit",
            sha,
            "--json",
            "databaseId,conclusion,displayTitle,headSha,status",
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
    if titled_runs is not None:
        runs = runs + titled_runs
    candidate_ids = _candidate_run_ids(runs)
    if candidate_ids is None:
        return None

    evidence: list[dict[str, object]] = []
    for run_id in candidate_ids:
        run = _run_details(run_id)
        if run is None:
            return None
        if _evaluated_source(run) == sha:
            evidence.append(run)
    verdicts = sum(1 for run in evidence if run.get("conclusion") in VERDICT_CONCLUSIONS)
    if verdicts:
        return verdicts
    # A run with no conclusion yet is in flight. It is not evidence, and it is not a
    # gap either -- reported as pending so a commit merged minutes ago is not called
    # ungated, and so a run that never finishes stays visible by name.
    if not evidence:
        return 0
    # Terminal cancelled/skipped/neutral outcomes did not produce a verdict and
    # cannot be deferred as live pending evidence.
    return -1 if any(str(run.get("status")) != "completed" for run in evidence) else 0


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
        help="check only that this audit itself ran within HOURS, and exit",
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

    # One time-bounded listing for the title attribution, from the oldest commit in
    # the window; per-commit `--commit` queries stay the primary evidence.
    titled_runs: list[dict[str, object]] | None = None
    if commits:
        oldest_sha = commits[-1].split(" ", 1)[0]
        oldest_date = _git("log", "-1", "--format=%cs", oldest_sha)[0]
        titled_runs = _titled_runs(oldest_date)

    pending: list[str] = []
    for entry in commits:
        sha, short, subject = entry.split(" ", 2)
        count = _run_count(sha, titled_runs)
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
            "  gh workflow run main-releasability.yml --ref main "
            "-f expected_sha=SHA -f triggering_pr=backfill\n"
            "main's gate definition checks out expected_sha in every job and titles the "
            "run with it, so the run is attributed to SHA; no tag is needed and the "
            "workflows-scope refusal that blocks GITHUB_TOKEN's tag write does not apply.\n"
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
    """Fail when this audit has not run lately, or has never run.

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
            "--limit=1",
            "--json",
            "createdAt,conclusion,databaseId,status,url",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"Cannot ask when {AUDIT_WORKFLOW} last ran: {completed.stderr.strip()}")
        print("Refusing to report success: an unanswerable liveness check is not a pass.")
        return 1
    try:
        runs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(f"{AUDIT_WORKFLOW} run list was not JSON; treating the check as failed.")
        return 1

    if not runs:
        print(f"{AUDIT_WORKFLOW} has never run, so its schedule has no execution evidence.")
        return 1

    run = runs[0]
    try:
        last = datetime.fromisoformat(str(run["createdAt"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        print(f"{AUDIT_WORKFLOW} returned no usable creation time; liveness is unknown.")
        return 1
    age_hours = (datetime.now(UTC) - last).total_seconds() / 3600
    if age_hours > max_age_hours:
        print(
            f"{AUDIT_WORKFLOW} last ran {age_hours:.1f}h ago, over the {max_age_hours}h "
            "bound. It runs daily, so it has stopped running -- and while it is stopped, an "
            "ungated commit on main reports nothing anywhere."
        )
        return 1

    status = str(run.get("status") or "unknown")
    conclusion = str(run.get("conclusion") or "pending")
    print(
        f"Execution freshness: {AUDIT_WORKFLOW} last ran {age_hours:.1f}h ago, within "
        f"the {max_age_hours}h bound."
    )
    print(f"Audit outcome: status={status}, conclusion={conclusion}.")
    if status == "completed":
        _print_audit_step_outcomes(run.get("databaseId"))
    return 0


def _print_audit_step_outcomes(run_id: object) -> None:
    """Name the two independent audit outcomes without changing liveness semantics."""
    if not isinstance(run_id, int):
        print("Audit step outcomes unavailable: the latest run carried no numeric run id.")
        return
    completed = subprocess.run(
        ["gh", "run", "view", str(run_id), "--json", "jobs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"Audit step outcomes unavailable: {completed.stderr.strip()}")
        return
    try:
        jobs = json.loads(completed.stdout).get("jobs", [])
    except (AttributeError, json.JSONDecodeError):
        print("Audit step outcomes unavailable: the run detail was not valid JSON.")
        return
    if not isinstance(jobs, list):
        print("Audit step outcomes unavailable: the run detail carried no job list.")
        return

    named_steps = {
        "Audit which commits on main were gated": "Commit coverage",
        "Enforce Branch Protection Policy": "Branch protection",
    }
    outcomes: dict[str, str] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            step_name = step.get("name")
            if not isinstance(step_name, str) or step_name not in named_steps:
                continue
            outcomes[named_steps[step_name]] = str(
                step.get("conclusion") or step.get("status") or "unknown"
            )
    for label in ("Commit coverage", "Branch protection"):
        print(f"{label}: {outcomes.get(label, 'not reported')}.")


if __name__ == "__main__":
    raise SystemExit(main())
