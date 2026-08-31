"""A document too large to render says so where an operator will read it.

`_classify_compile_failure` tells a killed compile from a rejected template and returns
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
from typing import get_args

import pytest

from app.contracts.renders import RenderFailureCategory as ContractFailureCategory
from app.domain.render_attempts.models import RenderFailureCategory as RuntimeFailureCategory
from app.services.render_ports import RenderCompileFailedError
from app.services.render_recovery import diagnostic_recovery
from app.services.render_submission import _unexpected_failure_category
from app.services.typst_rendering import _classify_compile_failure


def _killed_process(signal_number: int = 9) -> subprocess.CompletedProcess[str]:
    """What a compile killed for exceeding its bound actually looks like.

    Non-zero exit, and both streams empty: the process never got to say anything.
    """
    return subprocess.CompletedProcess(["typst"], 128 + signal_number, "", "")


def test_the_classifier_still_names_a_killed_compile_for_what_it_is() -> None:
    category, summary = _classify_compile_failure(_killed_process())

    assert category == RuntimeFailureCategory.RESOURCE_LIMIT_EXCEEDED
    assert "too large" in summary


def test_the_category_survives_the_raise() -> None:
    """The step that was missing: it reached a local attempt and went no further."""

    category, summary = _classify_compile_failure(_killed_process())
    error = RenderCompileFailedError(category, summary)

    assert _unexpected_failure_category(error) == "resource_limit_exceeded"


def test_a_template_failure_is_still_a_template_failure() -> None:
    """The classification must discriminate, not relabel everything."""

    rejected = subprocess.CompletedProcess(["typst"], 1, "error: unknown variable", "")
    category, summary = _classify_compile_failure(rejected)

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
