"""Reconcile declared eligibility populations; never determine eligibility outcomes."""

from collections import Counter
from typing import Any

from app.contracts.composite_eligibility_selection import EligibilitySelection

ASSESSMENT_ORDER = ["SIGNIFICANT_FLOW", "CASH", "READINESS"]


def validate_eligibility_horizon(selection: EligibilitySelection) -> None:
    start, end = selection.period_start, selection.period_end
    if start > end:
        raise ValueError("composite_eligibility_horizon_conflict")
    first = start.year * 12 + start.month - 1
    last = end.year * 12 + end.month - 1
    expected = [f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}" for ordinal in range(first, last + 1)]
    if [pin.month for pin in selection.months] != expected:
        raise ValueError("composite_eligibility_month_population_conflict")


def validate_eligibility_population(
    observations: dict[str, Any], evaluation: dict[str, Any]
) -> None:
    expected = observations["expected_portfolio_ids"]
    observed = [item["portfolio_id"] for item in observations["portfolios"]]
    evaluated = [item["portfolio_id"] for item in evaluation["portfolios"]]
    if len(set(expected)) != len(expected) or evaluated != expected:
        raise ValueError("composite_eligibility_member_population_conflict")
    if len(set(observed)) != len(observed) or not set(observed).issubset(expected):
        raise ValueError("composite_eligibility_observed_population_conflict")
    _validate_members(evaluation["portfolios"], set(observed))
    _validate_counts(evaluation, len(expected), len(observed))


def _validate_members(members: list[dict[str, Any]], observed: set[str]) -> None:
    for member in members:
        if member["observations_present"] != (member["portfolio_id"] in observed):
            raise ValueError("composite_eligibility_observation_presence_conflict")
        if [item["rule"] for item in member["assessments"]] != ASSESSMENT_ORDER:
            raise ValueError("composite_eligibility_assessment_population_conflict")


def _validate_counts(evaluation: dict[str, Any], expected: int, observed: int) -> None:
    statuses = Counter(item["status"] for item in evaluation["portfolios"])
    counts = {
        "expected_count": expected,
        "observed_count": observed,
        "included_count": statuses["INCLUDED"],
        "excluded_count": statuses["EXCLUDED"],
        "pending_review_count": statuses["PENDING_REVIEW"],
    }
    if any(evaluation[key] != value for key, value in counts.items()):
        raise ValueError("composite_eligibility_population_count_conflict")
