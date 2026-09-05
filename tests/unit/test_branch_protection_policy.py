"""The documented branch-protection policy must stay complete and self-consistent.

The live comparison runs in CI where a token exists; these offline checks keep
the policy document itself honest so the live gate always has a valid table to
compare against, and so the zero-approval exception cannot be silently deleted
while the configuration stays weak.
"""

import copy
from typing import Any

from scripts.check_branch_protection_policy import (
    compare_live_to_policy,
    load_policy,
    validate_policy_document,
)


def _live_matching_policy(policy: dict[str, Any]) -> dict[str, Any]:
    expected = policy["expected"]
    return {
        "enforce_admins": {"enabled": expected["enforce_admins"]},
        "required_linear_history": {"enabled": expected["required_linear_history"]},
        "allow_force_pushes": {"enabled": expected["allow_force_pushes"]},
        "allow_deletions": {"enabled": expected["allow_deletions"]},
        "required_conversation_resolution": {
            "enabled": expected["required_conversation_resolution"]
        },
        "restrictions": {"users": []} if expected["restrictions_present"] else None,
        "required_status_checks": {
            "strict": expected["required_status_checks"]["strict"],
            "contexts": list(expected["required_status_checks"]["contexts"]),
        },
        "required_pull_request_reviews": (
            {
                key: expected["required_pull_request_reviews"][key]
                for key in (
                    "required_approving_review_count",
                    "dismiss_stale_reviews",
                    "require_code_owner_reviews",
                    "require_last_push_approval",
                )
            }
            if expected["required_pull_request_reviews"]["present"]
            else None
        ),
    }


def test_policy_document_is_complete() -> None:
    assert validate_policy_document(load_policy()) == []


def test_zero_approval_count_requires_a_documented_exception() -> None:
    policy = copy.deepcopy(load_policy())
    policy["documented_exceptions"] = []

    issues = validate_policy_document(policy)

    assert any("documented exception" in issue for issue in issues)


def test_matching_live_configuration_passes() -> None:
    policy = load_policy()

    assert compare_live_to_policy(policy, _live_matching_policy(policy)) == []


def test_weakened_live_protection_fails() -> None:
    policy = load_policy()
    live = _live_matching_policy(policy)
    live["enforce_admins"] = {"enabled": False}
    live["required_status_checks"]["contexts"] = live["required_status_checks"]["contexts"][:-1]

    issues = compare_live_to_policy(policy, live)

    assert any(issue.startswith("enforce_admins") for issue in issues)
    assert any("contexts differ" in issue for issue in issues)


def test_absent_reviews_block_is_distinguished_from_zero_count() -> None:
    # The render#66 drift class: a missing required_pull_request_reviews block
    # must be reported as ABSENT, never conflated with a present zero-count.
    policy = load_policy()
    live = _live_matching_policy(policy)
    live["required_pull_request_reviews"] = None

    issues = compare_live_to_policy(policy, live)

    assert any("ABSENT" in issue for issue in issues)
