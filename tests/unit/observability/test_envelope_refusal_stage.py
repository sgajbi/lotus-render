"""An admission refusal and a runtime kill must be distinguishable to an operator.

`resource_limit_exceeded` is recorded for two different events. An admission
refusal means the envelope model predicted a document would not fit and refused
it before it took a render slot -- the model worked. A runtime kill on an
*admitted* document means the model predicted it would fit and it did not, which
is a mispredict and the trigger to re-measure the ceilings.

Both are correct for the caller and both must stay `resource_limit_exceeded`,
because the action is identical either way. That identity is exactly why the
operator cannot currently tell them apart, and why the separation belongs in a
metric rather than in the caller-facing category.

The tests that matter here are the two that force each path and observe the
counter move. A test asserting the counter exists would pass against a counter
nothing increments, which is indistinguishable from one that cannot.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from prometheus_client import REGISTRY

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.rendering.models import RenderResult
from app.domain.templates.registry import TemplateRegistry
from app.infrastructure.render_store import RenderStore
from app.observability.render_metrics import (
    ENVELOPE_REFUSAL_STAGES,
    METRIC_ENVELOPE_STAGE_LABEL,
    RENDER_METRIC_CONTRACTS,
    RENDER_METRIC_LABELS,
    record_envelope_limit_refusal,
    validate_render_metric_contracts,
)
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderCompileFailedError, RenderRuntimeMetadata
from app.services.render_submission import (
    RenderPackageInvalidError,
    RenderSubmissionService,
    _unexpected_failure_category,
)
from app.services.typst_rendering import TypstRenderService

_METRIC = "lotus_render_envelope_limit_refusals_total"


def _over_envelope_package(render_job_id: str) -> RenderPackage:
    """A package the measured envelope model refuses: 6,000 positions against a 3,125 ceiling."""

    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    report_data = payload["report_data"]
    row = (report_data.get("positions") or report_data["top_holdings"])[0]
    report_data["positions"] = [json.loads(json.dumps(row)) for _ in range(6_000)]
    report_data["top_holdings"] = report_data["positions"][:5]
    payload["render_job_id"] = render_job_id
    return RenderPackage.model_validate(payload)


def _load_golden_package() -> RenderPackage:
    """Well inside the envelope, so it is admitted and reaches the compile."""

    root = Path("tests/golden/portfolio-review/v1")
    source = (root / "render-package.json").read_text(encoding="utf-8")
    return RenderPackage.model_validate_json(source)


def _build_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


class _EngineThatMustNotRun:
    """An admission refusal that reached the engine did not refuse at admission."""

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        raise AssertionError("the engine was asked to render a document over the envelope")


def _count(stage: str) -> float:
    value = REGISTRY.get_sample_value(_METRIC, {METRIC_ENVELOPE_STAGE_LABEL: stage})
    return 0.0 if value is None else value


def test_the_two_stages_are_counted_independently() -> None:
    """The load-bearing behaviour: each stage moves its own series and not the other.

    Asserting only that both increment would pass if one call incremented both,
    which would make the ratio between them meaningless -- and the ratio is the
    entire purpose.
    """

    before_admission = _count("admission")
    before_runtime = _count("runtime")

    record_envelope_limit_refusal(stage="admission")

    assert _count("admission") == before_admission + 1
    assert _count("runtime") == before_runtime, "an admission refusal is not a model miss"

    record_envelope_limit_refusal(stage="runtime")

    assert _count("runtime") == before_runtime + 1
    assert _count("admission") == before_admission + 1, "a runtime kill is not an admission refusal"


def test_the_stage_label_is_bounded_to_exactly_two_values() -> None:
    """A third value would make the ratio unreadable, so it is refused rather than bucketed.

    Unlike a caller-supplied label, this value is written by this repository, so an
    unrecognised one is a bug. Recording it under a fallback would hide that bug in
    the very counter meant to expose model error.
    """

    assert ENVELOPE_REFUSAL_STAGES == {"admission", "runtime"}

    with pytest.raises(ValueError, match="unsupported envelope refusal stage"):
        record_envelope_limit_refusal(stage="other")

    assert REGISTRY.get_sample_value(_METRIC, {METRIC_ENVELOPE_STAGE_LABEL: "other"}) is None


def test_the_stage_label_was_added_to_the_allowlist_deliberately() -> None:
    """The allowlist is the bound; a counter using an unlisted label is a widening
    nobody reviewed."""

    assert METRIC_ENVELOPE_STAGE_LABEL in RENDER_METRIC_LABELS
    validate_render_metric_contracts()

    contract = next(c for c in RENDER_METRIC_CONTRACTS if c.name == _METRIC)
    assert contract.labels == (METRIC_ENVELOPE_STAGE_LABEL,), (
        "the counter exists to answer one question; every additional label multiplies its "
        "series for a signal specific to one failure category"
    )
    assert contract.implemented is True


def test_the_shared_operations_counter_did_not_gain_the_stage_label() -> None:
    """Where this signal deliberately did NOT go.

    `lotus_render_operations_total` carries operation, status and failure category.
    Adding `stage` there would multiply every series it holds, including the
    overwhelming majority for which stage is meaningless. Two series in a separate
    counter answer the question; a label on the shared counter would not.
    """

    operations = next(
        contract
        for contract in RENDER_METRIC_CONTRACTS
        if contract.name == "lotus_render_operations_total"
    )
    assert METRIC_ENVELOPE_STAGE_LABEL not in operations.labels


# --- The failure paths, forced. -------------------------------------------------------
#
# Everything above tests the recording helper. A helper that nothing calls would pass all
# of it, and a counter that has never been observed incrementing is indistinguishable
# from one that cannot. These drive the two real paths instead.


def test_forcing_an_admission_refusal_increments_admission_and_not_runtime(tmp_path: Path) -> None:
    """A document the model refuses, submitted through the real service.

    `RenderSubmissionService.submit` is what refuses before a render slot is taken; the
    engine here fails the test if it is ever reached, so an increment recorded on this
    path can only have come from the admission branch.
    """

    store = RenderStore(tmp_path / "render-store.sqlite3")
    service = RenderSubmissionService(
        rendering_stale_seconds=Settings().stale_rendering_seconds,
        execution_limiter=RenderExecutionLimiter(Settings().render_execution_concurrency_limit),
        render_store=store,
        render_engine=cast(Any, _EngineThatMustNotRun()),
    )
    before_admission = _count("admission")
    before_runtime = _count("runtime")

    with pytest.raises(RenderPackageInvalidError):
        service.submit(_over_envelope_package("rdr_stage_admission"))

    assert _count("admission") == before_admission + 1
    assert _count("runtime") == before_runtime, (
        "an admission refusal was counted as a runtime kill, which would read as the "
        "envelope model mispredicting when it in fact worked"
    )
    assert store.get("rdr_stage_admission").failure_category == "resource_limit_exceeded", (
        "the caller-facing category must not change; the separation is for the operator"
    )


def test_forcing_a_runtime_kill_increments_runtime_and_not_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A document the model ADMITTED, killed by the runtime bound anyway.

    This is the case the counter exists for and the one that cannot be reached from the
    admission branch: the golden package is well inside the envelope, so it passes
    admission and is compiled, and the compile is forced to come back killed.
    """

    service = _build_service()
    # `typst_rendering` calls `subprocess.run` through the module object imported here,
    # so patching it there is patching what the service actually calls.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(["typst"], 137, "", ""),
    )
    before_admission = _count("admission")
    before_runtime = _count("runtime")

    with pytest.raises(RenderCompileFailedError) as raised:
        service.render(_load_golden_package())

    assert _count("runtime") == before_runtime + 1
    assert _count("admission") == before_admission, (
        "a model miss was counted as an admission refusal, which is the exact inversion "
        "this issue exists to prevent"
    )
    assert _unexpected_failure_category(raised.value) == "resource_limit_exceeded", (
        "the caller sees the same category either way, which is correct: the action is "
        "identical. That is precisely why the operator needs the stage recorded here."
    )


def test_a_compile_failure_that_is_not_a_bound_counts_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counter must discriminate, or a rising runtime count means nothing.

    A rejected template is a non-zero exit from the same branch. Counting it here would
    make `runtime` a count of compile failures, and an operator re-measuring ceilings in
    response to a template defect is worse off than one with no metric.
    """

    service = _build_service()
    # `typst_rendering` calls `subprocess.run` through the module object imported here,
    # so patching it there is patching what the service actually calls.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["typst"], 1, "", "error: unknown variable"
        ),
    )
    before_admission = _count("admission")
    before_runtime = _count("runtime")

    with pytest.raises(RenderCompileFailedError) as raised:
        service.render(_load_golden_package())

    assert _unexpected_failure_category(raised.value) == "template_render_failed"
    assert _count("runtime") == before_runtime
    assert _count("admission") == before_admission


def test_every_registered_metric_carries_its_own_contract_description() -> None:
    """The contracts are indexed by position and consumed by position.

    Each counter takes its help text as `RENDER_METRIC_CONTRACTS[n].description`,
    so the list order is load-bearing for eight metrics and is asserted nowhere.
    Inserting a contract anywhere but the end silently shifts every later metric
    onto the wrong description, and `validate_render_metric_contracts()` cannot
    see it -- it checks that names are unique and labels are allowed, both of
    which stay true after the shift.

    This change added the eighth such coupling, which is why the pin belongs with
    it. Matching by **name** is the point: the contract and the registered metric
    are two statements about one metric, and comparing them by the index that
    joined them would only restate the assumption.
    """

    registered = {
        metric.name: metric.documentation
        for metric in REGISTRY.collect()
        if metric.name.startswith("lotus_render")
    }

    for contract in RENDER_METRIC_CONTRACTS:
        if not contract.implemented:
            continue
        # prometheus_client strips the `_total` suffix when exposing a Counter.
        exposed = contract.name.removesuffix("_total")
        assert exposed in registered, (
            f"{contract.name} is declared implemented but no metric of that name is registered"
        )
        assert registered[exposed] == contract.description, (
            f"{contract.name} is registered with a description belonging to another contract. "
            f"The counters take their help text by list index, so an insertion into "
            f"RENDER_METRIC_CONTRACTS shifts every later metric onto the wrong text.\n"
            f"  registered: {registered[exposed]!r}\n"
            f"  contract:   {contract.description!r}"
        )
