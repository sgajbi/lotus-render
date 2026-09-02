"""The attribution bridge answers "why did we beat the benchmark" without computing why.

Report composes the block (`attribution_bridge`, report#254) from lotus-performance's
Brinson attribution -- the largest computed analytic in the ecosystem with zero rendering
surface until this primitive (#160). The tests that matter most were committed with the
contract:

- the total bar is drawn from the authoritative ``total_active_return_pp``, never from
  the parts' endpoint -- the twin of Report's parts-deliberately-do-not-sum regression;
- ``pending`` is a stated sentence, never a wait and never an empty chart;
- the residual is a labelled segment with the source's own classification in prose.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pypdf

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.attribution_bridge import render_attribution_bridge
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _document(bridge: dict[str, Any] | None) -> str:
    package = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if bridge is None:
        package["report_data"].pop("attribution_bridge", None)
    else:
        package["report_data"]["attribution_bridge"] = bridge
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in reader.pages))


def _golden_bridge() -> dict[str, Any]:
    bridge: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))["report_data"][
        "attribution_bridge"
    ]
    return bridge


def test_the_bridge_carries_named_parts_residual_and_the_stated_total() -> None:
    """The banked golden's shape reaches the page: every group in the allocation
    page's vocabulary, the residual as a labelled row, the total from its own field,
    and the reconciliation attributed to the source rather than claimed by Render."""

    document = _document(_golden_bridge())

    assert "Performance attribution" in document
    for fragment in (
        "Equity 0.92pp",
        "Fixed Income 0.38pp",
        "Cash -0.05pp",
        "Residual 0.03pp",
        "Total active return 1.24pp",
        "The source reconciles its 1.24pp total active return as 1.21pp of named "
        "effects and a 0.03pp residual.",
        "The source classifies the residual as immaterial (disclose).",
        "allocation 0.45pp, selection 0.71pp, interaction 0.05pp",
        "against benchmark SPX_TR",
    ):
        assert fragment in document, f"missing: {fragment}"


def test_the_total_bar_is_the_authoritative_field_never_the_parts_endpoint() -> None:
    """The twin of Report's parts-deliberately-do-not-sum regression.

    The parts end at 1.24pp cumulative but the source states 1.32pp; the total bar must
    be sized by the stated figure (1.32/1.32 of the track: the domain grows to hold it),
    and the sentence must repeat the source's arithmetic, gap and all.
    """
    bridge = _golden_bridge()
    bridge["reconciliation"]["total_active_return_pp"] = "1.32"

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert '#bridge-row("Total active return", "1.32pp", 0.00%, 100.00%' in emitted
    # The parts' spans are scaled to the same widened domain: Equity is 0.92/1.32.
    assert '#bridge-row("Equity", "0.92pp", 0.00%, 69.70%, false, "part"' in emitted
    assert (
        "reconciles its 1.32pp total active return as 1.21pp of named effects "
        "and a 0.03pp residual" in emitted
    )


def test_segments_climb_cumulatively_and_a_negative_steps_back() -> None:
    """Fixed Income starts where Equity ended; Cash's segment is the step back from
    the running position, drawn leftward of it."""

    emitted = render_attribution_bridge({"attribution_bridge": _golden_bridge()})

    # Domain is [0, 1.30] -- the parts overshoot the 1.24 total and the track holds it.
    assert '#bridge-row("Equity", "0.92pp", 0.00%, 70.77%, false, "part", 0.00%)' in emitted
    assert '#bridge-row("Fixed Income", "0.38pp", 70.77%, 29.23%, false, "part", 0.00%)' in emitted
    assert '#bridge-row("Cash", "-0.05pp", 96.15%, 3.85%, true, "part", 0.00%)' in emitted
    # The residual departs the parts' endpoint (1.21), not the total.
    assert '#bridge-row("Residual", "0.03pp", 93.08%, 2.31%, false, "residual", 0.00%)' in emitted
    assert (
        '#bridge-row("Total active return", "1.24pp", 0.00%, 95.38%, false, "total", 0.00%)'
        in emitted
    )


def test_pending_states_the_calculation_and_draws_no_chart() -> None:
    """The calculation exists upstream; the page says regenerating collects it. An
    empty chart would read as a computed nothing."""

    document = _document(
        {
            "period": "YTD",
            "benchmark_code": "SPX_TR",
            "metric_basis": "NET",
            "notes": [],
            "posture": "pending",
            "calculation_id": "calc-20260423-0042",
        }
    )

    assert (
        "Performance attribution is still computing for this report "
        "(calculation calc-20260423-0042); regenerating the report collects the "
        "finished result." in document
    )
    assert "Total active return" not in document.split("Performance attribution")[1][:600]

    # Without the identity the fact is still said, unsized.
    emitted = render_attribution_bridge({"attribution_bridge": {"posture": "pending", "notes": []}})
    assert "still computing for this report;" in emitted
    assert "#bridge-row" not in emitted


def test_unavailable_is_said_with_only_the_sources_prose() -> None:
    """A note with a message is Report-composed reader prose; one without is operator
    telemetry and never reaches the page."""

    document = _document(
        {
            "period": "YTD",
            "benchmark_code": None,
            "metric_basis": None,
            "posture": "unavailable",
            "notes": [
                {
                    "code": "benchmark_missing",
                    "severity": "warning",
                    "message": "No benchmark is assigned, so attribution was not requested.",
                },
                {"code": "internal_marker", "severity": "info", "message": None},
            ],
        }
    )

    assert "Performance attribution could not be sourced for this period." in document
    assert "No benchmark is assigned, so attribution was not requested." in document
    assert "internal_marker" not in document


def test_an_absent_block_draws_nothing() -> None:
    """The section is opt-in upstream: golden packages from default orders carry no
    key, and no heading may promise a section nobody ordered."""

    assert render_attribution_bridge({}) == ""
    assert render_attribution_bridge({"attribution_bridge": {}}) == ""
    document = _document(None)
    assert "Performance attribution" not in document


def test_unreadable_effects_are_dropped_and_said() -> None:
    """A row Render cannot place is not silently absent from the bridge."""

    bridge = _golden_bridge()
    bridge["effects"][1]["total_effect_pp"] = "not-a-number"

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert "Fixed Income" not in emitted
    assert "1 effect could not be read and is not drawn." in emitted


def test_a_bridge_without_a_stated_total_is_refused_not_guessed() -> None:
    """No authoritative destination, no bridge -- summing the parts to invent one is
    the exact move the contract forbids."""

    bridge = _golden_bridge()
    del bridge["reconciliation"]["total_active_return_pp"]

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert "#bridge-row" not in emitted
    assert "Attribution figures could not be read for this period." in emitted


def test_an_underperforming_bridge_holds_zero_inside_the_track() -> None:
    """Negative territory: the domain covers the dip and zero sits where it falls."""

    bridge = _golden_bridge()
    bridge["effects"] = bridge["effects"][:2]
    bridge["effects"][0]["total_effect_pp"] = "-0.80"
    bridge["effects"][1]["total_effect_pp"] = "0.20"
    bridge["reconciliation"] = {
        "total_active_return_pp": "-0.55",
        "sum_of_effects_pp": "-0.60",
        "residual_pp": "0.05",
        "residual_classification": "immaterial",
        "residual_treatment": "disclose",
    }

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    # Every position is at or below zero, so the domain is [-0.80, 0] and zero sits at
    # the track's right edge -- the +0.20 recovery climbs toward it without crossing.
    assert '#bridge-row("Equity", "-0.80pp", 0.00%, 100.00%, true, "part", 100.00%)' in emitted
    assert (
        '#bridge-row("Total active return", "-0.55pp", 31.25%, 68.75%, true, "total", 100.00%)'
        in emitted
    )


def test_a_flat_bridge_still_draws() -> None:
    """All-zero figures are a statement, not a division by zero."""

    bridge = _golden_bridge()
    for effect in bridge["effects"]:
        effect["total_effect_pp"] = "0.00"
    bridge["reconciliation"].update(
        {"total_active_return_pp": "0.00", "sum_of_effects_pp": "0.00", "residual_pp": "0.00"}
    )

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert '#bridge-row("Total active return", "0.00pp"' in emitted


def test_a_sparse_reconciliation_claims_only_what_was_stated() -> None:
    """Total stated, everything else absent: the bridge draws to its authoritative
    destination, and no residual segment, reconciliation sentence or effect-type line
    is invented from fields nobody supplied."""

    bridge = _golden_bridge()
    bridge["reconciliation"] = {"total_active_return_pp": "1.24"}
    bridge["totals"] = {}

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert '"Total active return", "1.24pp"' in emitted
    assert "Residual" not in emitted
    assert "reconciles" not in emitted
    assert "Of the total effect" not in emitted


def test_a_classified_residual_without_a_treatment_is_still_classified() -> None:
    """The classification is a verdict on its own; a missing treatment drops the
    parenthesis, not the sentence."""

    bridge = _golden_bridge()
    del bridge["reconciliation"]["residual_treatment"]

    emitted = render_attribution_bridge({"attribution_bridge": bridge})

    assert "The source classifies the residual as immaterial." in emitted
    assert "(disclose)" not in emitted
