"""Focused source fragments exercise population guards, not producer acceptance."""

import copy
import json
from typing import Any

import pytest
from eligibility_fixtures import selector

from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.services.composite_workbook.eligibility_population import (
    validate_eligibility_horizon,
    validate_eligibility_population,
)


def population() -> tuple[dict[str, Any], dict[str, Any]]:
    observations: dict[str, Any] = {
        "expected_portfolio_ids": ["portfolio-a", "portfolio-b", "portfolio-c"],
        "portfolios": [{"portfolio_id": "portfolio-a"}, {"portfolio_id": "portfolio-b"}],
    }
    evaluation: dict[str, Any] = {
        "expected_count": 3,
        "observed_count": 2,
        "included_count": 1,
        "excluded_count": 1,
        "pending_review_count": 1,
        "portfolios": [
            {
                "portfolio_id": identity,
                "observations_present": index < 2,
                "status": status,
                "assessments": [
                    {"rule": rule} for rule in ["SIGNIFICANT_FLOW", "CASH", "READINESS"]
                ],
            }
            for index, (identity, status) in enumerate(
                zip(
                    observations["expected_portfolio_ids"],
                    ["INCLUDED", "EXCLUDED", "PENDING_REVIEW"],
                )
            )
        ],
    }
    return observations, evaluation


def test_complete_population_retains_missing_observations_without_deciding_status() -> None:
    observations, evaluation = population()
    original = copy.deepcopy((observations, evaluation))
    validate_eligibility_population(observations, evaluation)
    assert (observations, evaluation) == original


@pytest.mark.parametrize(
    "change", ["missing", "extra", "duplicate", "reordered", "expected_duplicate"]
)
def test_refuses_incomplete_or_relabelled_evaluated_population(change: str) -> None:
    observations, evaluation = population()
    members = evaluation["portfolios"]
    if change == "missing":
        members.pop()
    elif change == "extra":
        members.append(copy.deepcopy(members[0]))
    elif change == "duplicate":
        members[1]["portfolio_id"] = members[0]["portfolio_id"]
    elif change == "reordered":
        members.reverse()
    else:
        observations["expected_portfolio_ids"][1] = "portfolio-a"
    with pytest.raises(ValueError, match="member_population_conflict"):
        validate_eligibility_population(observations, evaluation)


@pytest.mark.parametrize("identity", ["portfolio-a", "foreign-portfolio"])
def test_refuses_duplicate_or_outside_observed_population(identity: str) -> None:
    observations, evaluation = population()
    observations["portfolios"].append({"portfolio_id": identity})
    with pytest.raises(ValueError, match="observed_population_conflict"):
        validate_eligibility_population(observations, evaluation)


def test_refuses_false_observation_presence() -> None:
    observations, evaluation = population()
    evaluation["portfolios"][2]["observations_present"] = True
    with pytest.raises(ValueError, match="observation_presence_conflict"):
        validate_eligibility_population(observations, evaluation)


@pytest.mark.parametrize("rules", [["CASH", "SIGNIFICANT_FLOW", "READINESS"], ["CASH"] * 3, []])
def test_refuses_missing_duplicate_or_reordered_assessments(rules: list[str]) -> None:
    observations, evaluation = population()
    evaluation["portfolios"][0]["assessments"] = [{"rule": rule} for rule in rules]
    with pytest.raises(ValueError, match="assessment_population_conflict"):
        validate_eligibility_population(observations, evaluation)


@pytest.mark.parametrize(
    "field",
    [
        "expected_count",
        "observed_count",
        "included_count",
        "excluded_count",
        "pending_review_count",
    ],
)
def test_refuses_inconsistent_source_counts(field: str) -> None:
    observations, evaluation = population()
    evaluation[field] += 1
    with pytest.raises(ValueError, match="population_count_conflict"):
        validate_eligibility_population(observations, evaluation)


def horizon() -> dict[str, Any]:
    wire = selector()
    wire.update(period_start="2025-12-01", period_end="2026-02-28")
    wire["months"] = [
        dict(wire["months"][0], month=month) for month in ["2025-12", "2026-01", "2026-02"]
    ]
    return wire


def test_complete_calendar_horizon_crosses_year_boundary() -> None:
    validate_eligibility_horizon(EligibilitySelection.model_validate_json(json.dumps(horizon())))


@pytest.mark.parametrize("change", ["gap", "duplicate", "reordered", "outside", "reversed"])
def test_refuses_incomplete_month_horizon(change: str) -> None:
    wire = horizon()
    if change == "gap":
        wire["months"].pop(1)
    elif change == "duplicate":
        wire["months"][1]["month"] = "2025-12"
    elif change == "reordered":
        wire["months"].reverse()
    elif change == "outside":
        wire["months"][2]["month"] = "2026-03"
    else:
        wire["period_start"] = "2026-03-01"
    with pytest.raises(ValueError, match="composite_eligibility_.*conflict"):
        validate_eligibility_horizon(EligibilitySelection.model_validate_json(json.dumps(wire)))
