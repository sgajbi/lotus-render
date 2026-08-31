"""What an operator is told when a render fails, and whether retrying can help.

A table rather than a chain of branches, so the whole policy is readable at once and a
new category is a line rather than a branch. It lives apart from the submission service
because it is read by people deciding what to do about a failure, not by the code that
submits the work.

`resource_limit_exceeded` is the reason this became a table. It used to fall through to
the template-failure branch, so a document too large for the envelope was answered
"escalate template support" -- sending an operator to look for a template defect that
is not there, and inviting a retry that fails identically.
"""

from __future__ import annotations

from app.contracts.renders import (
    RenderFailureCategory,
    RenderHandoffOwner,
    RenderRecoveryAction,
)

_Advice = tuple[bool, RenderRecoveryAction, RenderHandoffOwner, str]

# Two categories each share their advice with another, so the sharing is named rather
# than copied: a runtime that is unreachable and one that ran out of time need the same
# check, and a template that would not compile and an artifact that would not validate
# are the same escalation.
_RUNTIME_ADVICE: _Advice = (
    True,
    "escalate_render_runtime",
    "reporting-platform-on-call",
    "Render runtime failed; check runtime availability, timeout posture, and retry envelope.",
)
_TEMPLATE_ADVICE: _Advice = (
    True,
    "escalate_template_support",
    "reporting-platform-on-call",
    "Template or artifact generation failed inside the governed runtime envelope.",
)

# What an operator is told for each way a render can fail: whether retrying can help,
# what to do, who owns it, and why. A table rather than a chain of branches, so the
# whole policy is readable at once and a new category is a line rather than a branch.
_RECOVERY_BY_CATEGORY: dict[str, _Advice] = {
    "package_validation_failed": (
        False,
        "fix_upstream_render_package",
        "lotus-report",
        "Render package validation failed; fix or replay the upstream report package.",
    ),
    "template_not_supported": (
        False,
        "fix_template_registry_or_package",
        "template-owner",
        "Template compatibility failed; align the package with the governed template registry.",
    ),
    "engine_unavailable": _RUNTIME_ADVICE,
    "timeout": _RUNTIME_ADVICE,
    # Not retryable and not a support case: the same document will exceed the same
    # envelope every time. It used to be answered as a template failure, which sent an
    # operator looking for a template defect that is not there.
    "resource_limit_exceeded": (
        False,
        "reduce_document_size_or_raise_envelope",
        "lotus-report",
        (
            "The document exceeded the governed render envelope. It will fail identically "
            "on retry: send fewer rows, or raise the envelope."
        ),
    ),
    "template_render_failed": _TEMPLATE_ADVICE,
    "artifact_validation_failed": _TEMPLATE_ADVICE,
}

_RECOVERY_UNKNOWN: _Advice = (
    True,
    "escalate_reporting_platform",
    "reporting-platform-on-call",
    "Render requires operator intervention inside the reporting platform support boundary.",
)


def diagnostic_recovery(
    *,
    status: str,
    failure_category: RenderFailureCategory | None,
    stale_state: str,
) -> tuple[bool, RenderRecoveryAction, RenderHandoffOwner, str]:
    if status == "rendered":
        return (
            False,
            "read_artifact_metadata",
            "lotus-render",
            "Render completed; use artifact metadata for deterministic proof.",
        )
    if status in {"accepted", "rendering"}:
        if stale_state == "stale":
            return (
                True,
                "resubmit_identical_package_or_escalate_runtime",
                "reporting-platform-on-call",
                (
                    "Render is stale; resubmit the identical package for idempotent recovery or "
                    "escalate runtime support if it remains non-terminal."
                ),
            )
        return (
            False,
            "wait_for_completion",
            "lotus-render",
            "Render is in progress inside the governed runtime envelope.",
        )
    return _RECOVERY_BY_CATEGORY.get(failure_category or "", _RECOVERY_UNKNOWN)
