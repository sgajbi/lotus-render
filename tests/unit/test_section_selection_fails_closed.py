"""An explicit scope can narrow a document or fail; it can never silently widen it.

Before this contract, an unknown requested section was silently dropped, and a request
whose every token was unknown or unavailable -- or an explicit empty list -- fell back to
the DEFAULT FULL REPORT: a caller who asked for one page received eleven. The old tests
asserted that fallback, which is how a defect survives -- they proved the behaviour, not
the intent.

The refusal happens at admission, before a render slot is taken, through the same typed
`RenderPackageInvalidError` surface as the envelope: the same selection refuses
identically on retry, so the caller learns everything at submit time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.rendering.models import RenderResult
from app.infrastructure.render_store import RenderStore
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderRuntimeMetadata
from app.services.render_submission import (
    RenderPackageInvalidError,
    RenderSubmissionService,
)
from app.services.section_selection import (
    SectionSelectionError,
    resolve_section_keys,
    section_selection_refusal,
)

FULL_DEFAULT = [
    "cover",
    "contents",
    "overview",
    "performance",
    "allocation",
    "positions",
    "transactions",
    "appendix",
]


def _package(sections: object, **overrides: Any) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload["render_context"]["sections"] = sections
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


def test_an_omitted_selection_is_the_documented_default() -> None:
    """Absent means "the default composition" -- the one path that may reach it."""

    assert resolve_section_keys(None) == FULL_DEFAULT


def test_aliases_duplicates_and_caller_order_are_honoured() -> None:
    """Normalisation is not validation: an alias resolves, a duplicate draws once at
    its first position, and the order stays the caller's."""

    assert resolve_section_keys(
        ["transaction-list", "detailed-positions", "asset_allocation", "transactions"]
    ) == ["transactions", "positions", "allocation"]


@pytest.mark.parametrize(
    "sections",
    [
        pytest.param(["performence"], id="typo-only"),
        pytest.param(["performance", "unknown"], id="mixed-valid-and-invalid"),
        pytest.param(["unknown", "also-unknown"], id="all-invalid"),
    ],
)
def test_an_unknown_token_refuses_the_whole_selection(sections: list[str]) -> None:
    """Mixed requests are not partially honoured: drawing the valid remainder answers
    a request nobody made, and the all-invalid case used to widen to the full report."""

    with pytest.raises(SectionSelectionError) as refusal:
        resolve_section_keys(sections)

    message = str(refusal.value)
    for token in sections:
        if token not in FULL_DEFAULT:
            assert repr(token) in message, "the refusal must name the token to fix"


def test_a_recognised_but_unavailable_optional_section_refuses() -> None:
    """A section the package does not carry cannot be requested into existence -- and
    the old behaviour, the full default report, answered the request by ignoring it."""

    with pytest.raises(SectionSelectionError) as refusal:
        resolve_section_keys(["performance", "advisor-proposal-memo"], included=set())

    assert "'advisor-proposal-memo'" in str(refusal.value)
    assert "not available in this package" in str(refusal.value)

    # The same token resolves the moment the package carries the section.
    assert resolve_section_keys(
        ["performance", "advisor-proposal-memo"], included={"advisor_memo"}
    ) == ["performance", "advisor_memo"]


def test_an_explicit_empty_list_is_refused_not_defaulted() -> None:
    """`[]` used to reach the default composition -- the silent widening itself."""

    with pytest.raises(SectionSelectionError, match="empty"):
        resolve_section_keys([])


def test_a_selection_that_is_not_a_list_is_refused() -> None:
    """A string is explicit intent Render cannot validate token by token."""

    with pytest.raises(SectionSelectionError, match="must be a list"):
        resolve_section_keys("performance")


def test_the_appendix_is_the_one_documented_narrowing() -> None:
    """Requested but explaining nothing, the appendix drops under its own contract:
    its applicability is Render's presentation logic, unknowable at order time, so
    "include it if there are terms to explain" is the only orderable meaning."""

    assert resolve_section_keys(["overview", "appendix"], include_appendix=False) == ["overview"]
    assert resolve_section_keys(["overview", "appendix"], include_appendix=True) == [
        "overview",
        "appendix",
    ]


class _CountingLimiter(RenderExecutionLimiter):
    def __init__(self) -> None:
        super().__init__(Settings().render_execution_concurrency_limit)
        self.acquired = 0

    def acquire(self) -> bool:
        self.acquired += 1
        return super().acquire()


class _EngineThatMustNotRun:
    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        raise AssertionError("a refused section selection was compiled anyway")


def test_a_refused_selection_never_reaches_a_render_slot(tmp_path: Path) -> None:
    """The refusal is typed, at admission, and names the token -- the same surface as
    the envelope, for the same reason: the caller learns everything at submit time."""

    store = RenderStore(tmp_path / "render-store.sqlite3")
    limiter = _CountingLimiter()
    service = RenderSubmissionService(
        rendering_stale_seconds=Settings().stale_rendering_seconds,
        execution_limiter=limiter,
        render_store=store,
        render_engine=cast(Any, _EngineThatMustNotRun()),
    )

    with pytest.raises(RenderPackageInvalidError) as refusal:
        service.submit(_package(["performance", "unknown"], render_job_id="rdr_sections_refused"))

    assert "'unknown'" in str(refusal.value)
    assert limiter.acquired == 0, "a selection that cannot render took a render slot"
    stored = store.get("rdr_sections_refused")
    assert stored.status == "failed"
    assert stored.failure_category == "package_validation_failed"


def test_admission_passes_what_rendering_will_honour() -> None:
    """The two layers answer from the same module: an omitted field, a valid narrow
    request and an alias all pass admission untouched."""

    assert section_selection_refusal(_package(None)) is None
    assert section_selection_refusal(_package(["performance", "transaction-list"])) is None


def test_a_sectionless_family_refuses_an_explicit_selection() -> None:
    """Only the portfolio review defines a section-selection surface. Silently ignoring
    the field on another family is the same fail-open with a different face."""

    payload = json.loads(
        Path("tests/golden/proof-pack/v1/render-package.json").read_text(encoding="utf-8")
    )
    payload["render_context"]["sections"] = ["performance"]
    refusal = section_selection_refusal(RenderPackage.model_validate(payload))

    assert refusal is not None
    assert "defines no section selection" in refusal


def test_malformed_content_is_not_preempted_by_a_selection_refusal() -> None:
    """A package whose content cannot parse fails with the content's own typed error;
    this check must not replace that message with a worse one."""

    package = _package(["performance"])
    broken = package.model_copy(update={"report_data": {}})

    assert section_selection_refusal(broken) is None
