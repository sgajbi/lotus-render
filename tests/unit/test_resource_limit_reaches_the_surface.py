"""A document too large to render says so where an operator will read it.

`classify_compile_failure` tells a killed compile from a rejected template and returns
`resource_limit_exceeded` for the first. It stamped that on a local attempt and then
raised a bare `RuntimeError`, and `_unexpected_failure_category` re-derived the category
from `str(exc)` -- a matcher that knows only `engine_unavailable` and
`template_render_failed`. So every memory-killed compile was stored, metered and
answered as a template failure, with the recovery action "escalate template support".

The two need opposite responses. A template error needs a fix and fails identically for
ever; an oversized document needs a smaller document or a larger envelope, and no
amount of template support will help.

The contract could not have carried it in any case: the domain enum had
`RESOURCE_LIMIT_EXCEEDED` and the contract `Literal` of the same name did not. Two
spellings of one closed set, drifted apart, with nothing holding them together.

The classifier's own unit tests passed throughout, because they test the classifier.
These test the surface a caller sees.
"""

from __future__ import annotations

import subprocess
from typing import cast, get_args

import pytest

from app.contracts.renders import RenderFailureCategory as ContractFailureCategory
from app.domain.render_attempts.models import RenderFailureCategory as RuntimeFailureCategory
from app.services.compile_failures import classify_compile_failure
from app.services.render_ports import RenderCompileFailedError
from app.services.render_recovery import diagnostic_recovery
from app.services.render_submission import _unexpected_failure_category


def _killed_process(signal_number: int = 9) -> subprocess.CompletedProcess[str]:
    """What a compile killed for exceeding its bound actually looks like.

    Non-zero exit, and both streams empty: the process never got to say anything.
    """
    return subprocess.CompletedProcess(["typst"], 128 + signal_number, "", "")


def test_the_classifier_still_names_a_killed_compile_for_what_it_is() -> None:
    category, summary = classify_compile_failure(_killed_process())

    assert category == RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED
    assert "too large" in summary


def test_the_category_survives_the_raise() -> None:
    """The step that was missing: it reached a local attempt and went no further."""

    category, summary = classify_compile_failure(_killed_process())
    error = RenderCompileFailedError(category, summary)

    assert _unexpected_failure_category(error) == "resource_limit_exceeded"


def test_a_template_failure_is_still_a_template_failure() -> None:
    """The classification must discriminate, not relabel everything."""

    rejected = subprocess.CompletedProcess(["typst"], 1, "error: unknown variable", "")
    category, summary = classify_compile_failure(rejected)

    assert _unexpected_failure_category(RenderCompileFailedError(category, summary)) == (
        "template_render_failed"
    )


def test_an_unclassified_runtime_error_is_unchanged() -> None:
    """Everything that does not carry a category keeps the old message matching."""

    assert _unexpected_failure_category(RuntimeError("neither docker nor typst is installed")) == (
        "engine_unavailable"
    )
    assert _unexpected_failure_category(RuntimeError("something else")) == (
        "template_render_failed"
    )


def test_the_recovery_advice_does_not_send_an_operator_to_template_support() -> None:
    """A document too large is not a support case, and it is not retryable.

    It was answered "escalate template support", which is the advice for a broken
    template: a person would look for a template defect that is not there, and a retry
    would fail in exactly the same way.
    """

    retryable, action, owner, message = diagnostic_recovery(
        status="failed",
        failure_category="resource_limit_exceeded",
        stale_state="not_applicable",
    )

    assert retryable is False, "the same document will exceed the same envelope again"
    assert action == "reduce_document_size_or_raise_envelope"
    assert owner == "lotus-report", "the document is the caller's to make smaller"
    assert "escalate" not in message.lower()


def test_the_two_failure_category_spellings_agree() -> None:
    """One closed set with two definitions, and nothing had held them together.

    The domain enum gained `resource_limit_exceeded` when the classifier learnt to
    produce it. The contract Literal did not, so the response had no way to say it --
    and the conversion at the submission boundary is only safe while these match.
    """

    runtime = {member.value for member in RuntimeFailureCategory}
    contract = set(get_args(ContractFailureCategory))

    assert runtime == contract, (
        "the runtime and the contract disagree about which failure categories exist: "
        f"only in the runtime {sorted(runtime - contract)}, "
        f"only in the contract {sorted(contract - runtime)}"
    )


@pytest.mark.parametrize("category", sorted(member.value for member in RuntimeFailureCategory))
def test_every_category_the_runtime_can_produce_has_recovery_advice(
    category: ContractFailureCategory,
) -> None:
    """A category with no branch falls to the generic one, which says nothing useful."""

    _, action, _, message = diagnostic_recovery(
        status="failed", failure_category=category, stale_state="not_applicable"
    )

    if category in {"operator_intervention_required", "unexpected_render_error"}:
        # These two mean "we do not know", so the generic advice is the honest answer.
        return
    assert action != "escalate_reporting_platform", (
        f"{category} falls through to the generic recovery action, so an operator is "
        f"told only to escalate: {message}"
    )


# What each signal can and cannot mean. Only the first group is reachable from a resource
# bound: SIGXCPU and SIGXFSZ exist for no other reason, and SIGKILL and SIGABRT are how
# the container's memory limit and this service's own `ulimit -v` are measured to arrive.
SIGNAL_CLASSIFICATION = [
    pytest.param(9, RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED, id="SIGKILL-container-oom"),
    pytest.param(6, RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED, id="SIGABRT-ulimit-v"),
    pytest.param(24, RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED, id="SIGXCPU-ulimit-t"),
    pytest.param(15, RuntimeFailureCategory.ENGINE_UNAVAILABLE, id="SIGTERM-deploy"),
    pytest.param(2, RuntimeFailureCategory.ENGINE_UNAVAILABLE, id="SIGINT"),
    pytest.param(11, RuntimeFailureCategory.UNEXPECTED_RENDER_ERROR, id="SIGSEGV-engine-crash"),
    pytest.param(7, RuntimeFailureCategory.UNEXPECTED_RENDER_ERROR, id="SIGBUS"),
    pytest.param(30, RuntimeFailureCategory.UNEXPECTED_RENDER_ERROR, id="unrecognised-signal"),
]


@pytest.mark.parametrize(("signal_number", "expected"), SIGNAL_CLASSIFICATION)
def test_a_signal_death_is_read_for_what_that_signal_can_mean(
    signal_number: int, expected: RuntimeFailureCategory
) -> None:
    """Every silent kill used to be `resource_limit_exceeded`, whatever killed it.

    Both streams are empty on all of these, so the number is the only evidence there is
    -- and it is enough to rule the bound out for most of them.
    """

    category, _ = classify_compile_failure(_killed_process(signal_number))

    assert category == expected


@pytest.mark.parametrize(
    ("signal_number", "expected"),
    [
        case
        for case in SIGNAL_CLASSIFICATION
        if case.values[1] is not RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED
    ],
)
def test_a_death_no_bound_can_cause_is_not_answered_with_send_fewer_rows(
    signal_number: int, expected: RuntimeFailureCategory
) -> None:
    """The consequence, which is what makes the misclassification cost something.

    `resource_limit_exceeded` is not retryable, is owned by lotus-report, and its action
    is `reduce_document_size_or_raise_envelope`. A deploy's SIGTERM therefore told a
    caller its document was permanently over the envelope, when in fact resubmitting the
    identical package would have rendered it. A segfault told it the same, and no
    package is small enough to stop the compiler crashing.
    """

    category, summary = classify_compile_failure(_killed_process(signal_number))
    retryable, action, owner, _ = diagnostic_recovery(
        # The classifier returns the runtime enum and the recovery table takes the
        # contract Literal. `test_the_two_failure_category_spellings_agree` is what
        # holds the two spellings equal; this cast is that fact, written down.
        status="failed",
        failure_category=cast(ContractFailureCategory, str(category)),
        stale_state="fresh",
    )

    assert retryable, f"{summary}: a transient death was reported as permanent"
    assert action != "reduce_document_size_or_raise_envelope"
    assert owner != "lotus-report", "the caller was handed a failure it cannot act on"
