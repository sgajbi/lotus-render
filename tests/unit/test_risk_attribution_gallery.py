"""The risk-attribution gallery: the v3 primitive at its edges, per #219's shape.

Each case in tests/gallery/risk-attribution/ is a canonical producer emission of
the locked #254 contract -- the ready vectors are the exact values the producer's
pinned tests use -- and every assertion fails on a WRONG result, not a changed
one. The real-engine test compiles the primitive on the real v3 page.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pypdf

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.risk_attribution import render_risk_attribution_panel
from app.services.typst_rendering import TypstRenderService

GALLERY = Path("tests/gallery/risk-attribution")


def _case(name: str) -> dict[str, Any]:
    return {"risk_attribution": json.loads((GALLERY / f"{name}.json").read_text(encoding="utf-8"))}


def _bars(markup: str) -> int:
    return markup.count("#diverging-track(")


def test_absence_draws_nothing_at_all() -> None:
    """RISK_ATTRIBUTION is a dedicated, default-off section: an unordered
    document carries no block and must show no panel, heading, or frame."""

    assert render_risk_attribution_panel({}) == ""
    assert render_risk_attribution_panel({"risk_attribution": {}}) == ""
    assert render_risk_attribution_panel({"risk_attribution": {"sets": []}}) == ""


def test_both_decompositions_draw_with_units_fractions_and_the_residual_rule() -> None:
    """The locked vectors, drawn: metric-unit values shift by the set's unit
    (0.0784 -> 7.84%), percent_contribution by the STRUCTURAL fraction rule
    (0.6258 -> 62.58%), optional stated facts print on their secondary line,
    and the residual is a value with no bar."""

    markup = render_risk_attribution_panel(_case("ready-both-sets"))

    assert "Total risk — volatility" in markup
    assert "Active risk — tracking error" in markup
    assert _bars(markup) == 4, "four contributor rows draw bars; residuals never do"
    for needle in ("7.84%", "62.58%", "-1.12%", "-8.94%", "1.41%", "67.14%"):
        assert needle in markup, f"missing formatted figure {needle}"
    assert "avg weight 24.5%" in markup, "a stated weight_average prints (fraction rule)"
    assert "marginal -3.1%" in markup, "a stated marginal_contribution prints (metric unit)"
    assert "Residual (unallocated)" in markup
    assert "0.04%" in markup and "0.02%" in markup, "residuals print, small or not"
    assert "Contributions sum to 12.49%; stated total 12.53%." in markup
    assert "Contributions sum to 2.08%; stated total 2.1%." in markup
    assert "Source quality flags: LOW_COVERAGE" in markup
    assert "by SECTOR · YTD 2026-01-02 to 2026-08-31" in markup
    assert markup.count("Bars are scaled within each decomposition") == 1
    assert "0.6258" not in markup, "raw fractions never reach the reader"
    tech = markup.index("SECTOR_TECH")
    fin = markup.index("SECTOR_FIN")
    assert tech < fin, "contributor order is the source's, never re-ranked"


def test_a_negative_contribution_draws_signed_never_clamped() -> None:
    markup = render_risk_attribution_panel(_case("ready-both-sets"))
    assert "#diverging-track(100.00%, false)" in markup, (
        "the largest absolute contribution fills the track"
    )
    assert re.search(r"#diverging-track\(14\.\d\d%, true\)", markup), (
        "the negative contributor draws at its proportion with the negative flag"
    )


def test_an_unbenchmarked_portfolio_states_the_active_set_in_place() -> None:
    markup = render_risk_attribution_panel(_case("benchmark-not-applied"))

    assert _bars(markup) == 2, "only the total-risk decomposition draws"
    assert "Active risk — tracking error" in markup
    assert "Not available — BENCHMARK_UNAVAILABLE" in markup


def test_producer_refusals_arrive_in_the_sources_voice() -> None:
    markup = render_risk_attribution_panel(_case("producer-refusals"))

    assert _bars(markup) == 0
    assert "Not available — The source did not state the full total" in markup
    assert "Source quality flags: LOW_COVERAGE" in markup, (
        "flags stated on the refusal are retained facts"
    )
    assert "Not included — position_returns_unavailable" in markup
    assert "Bars are scaled" not in markup, "no set drew, no convention to state"


def test_source_errors_and_missing_sets_are_stated() -> None:
    markup = render_risk_attribution_panel(_case("source-error"))

    assert markup.count("Not available") == 2
    assert "Insufficient data" in markup
    assert "The source emitted no result for the requested set." in markup


def test_a_ready_set_without_unit_semantics_is_the_drift_backstop() -> None:
    markup = render_risk_attribution_panel(_case("unit-missing"))

    assert _bars(markup) == 0
    assert "without unit semantics" in markup
    assert "0.0784" not in markup, "no raw ratio may reach the reader bare"


def test_contract_contradictions_refuse_the_whole_set() -> None:
    """The consumer's backstops behind the producer's own refusals: an
    incomplete triple, a malformed contributor, an unformattable stated fact,
    and an unknown combination each state the set, never part-draw it."""

    base = json.loads((GALLERY / "ready-both-sets.json").read_text(encoding="utf-8"))

    incomplete = json.loads(json.dumps(base))
    del incomplete["sets"][0]["residual"]
    markup = render_risk_attribution_panel({"risk_attribution": incomplete})
    assert "could not be drawn" in markup

    malformed = json.loads(json.dumps(base))
    del malformed["sets"][0]["contributors"][1]["percent_contribution"]
    markup = render_risk_attribution_panel({"risk_attribution": malformed})
    assert "could not be drawn" in markup

    unstatable = json.loads(json.dumps(base))
    unstatable["sets"][0]["contributors"][0]["weight_average"] = "not-a-number"
    markup = render_risk_attribution_panel({"risk_attribution": unstatable})
    assert "could not be drawn" in markup

    unknown = json.loads(json.dumps(base))
    unknown["sets"][0]["attribution_type"] = "MARGINAL_RISK"
    markup = render_risk_attribution_panel({"risk_attribution": unknown})
    assert "MARGINAL_RISK — VOLATILITY" in markup, "unknown combinations print verbatim"


def test_a_misdeclared_or_unlabelled_emission_is_stated_not_guessed() -> None:
    """Container and identity backstops: a sets value that is not a list draws
    nothing; a set with no recognisable identity, posture, notes, or flags is
    stated with exactly what the source supplied -- nothing invented."""

    assert render_risk_attribution_panel({"risk_attribution": {"sets": "misdeclared"}}) == ""

    bare = {
        "grouping_dimension": "   ",
        "posture": "unavailable",
        # A note that is not a row, and a note with no message: neither is a
        # statable reason, so the refusal stays bare.
        "notes": ["ignored", {"code": "reason_without_message"}],
    }
    markup = render_risk_attribution_panel({"risk_attribution": {"sets": [bare]}})
    assert "Unnamed decomposition" in markup
    assert "Not available." in markup, "no notes means the bare refusal, never an invented reason"
    assert "by " not in markup, "a whitespace grouping dimension is not a stated dimension"
    assert "text-micro, fill: slate)[by" not in markup
    assert "Source quality flags" not in markup, "absent flags state nothing"

    unknown = {"attribution_type": "TOTAL_RISK", "metric": "VOLATILITY", "posture": "draft"}
    markup = render_risk_attribution_panel({"risk_attribution": {"sets": [unknown]}})
    assert "The source stated no recognised posture for this decomposition." in markup


def test_ready_set_backstops_refuse_what_the_display_rules_cannot_state() -> None:
    """Each locked field the producer could drift on, refused whole-set: no
    contributors, a contributor that is not a row, an unformattable
    reconciliation value or percentage, and optional facts that are present
    but not statable strings."""

    base = json.loads((GALLERY / "ready-both-sets.json").read_text(encoding="utf-8"))

    def refused(mutate: Callable[[dict[str, Any]], object]) -> bool:
        case = json.loads(json.dumps(base))
        mutate(case["sets"][0])
        markup = render_risk_attribution_panel({"risk_attribution": case})
        return "could not be drawn" in markup and _bars(markup) == 2

    assert refused(lambda s: s.update(contributors=[]))
    assert refused(lambda s: s.update(contributors=["SECTOR_TECH"]))
    assert refused(lambda s: s.update(total_value="not-a-number"))
    assert refused(lambda s: s["contributors"][0].update(percent_contribution="n/a"))
    assert refused(lambda s: s["contributors"][0].update(weight_average=0.245))
    assert refused(lambda s: s["contributors"][1].update(marginal_contribution=-0.031))
    assert refused(lambda s: s["contributors"][1].update(marginal_contribution="x"))


def test_a_unitless_component_must_still_size_a_bar_or_the_set_refuses() -> None:
    """unitless passes strings verbatim to the page, but a bar still needs a
    finite magnitude: a component that does not parse, or parses infinite,
    refuses the whole set rather than drawing a wrong track."""

    def unitless_set(component: str) -> dict[str, object]:
        return {
            "attribution_type": "TOTAL_RISK",
            "metric": "VOLATILITY",
            "posture": "ready",
            "unit": "unitless",
            "total_value": "1.25",
            "reconciled_sum": "1.21",
            "residual": "0.04",
            "quality_flags": [],
            "contributors": [
                {
                    "group_key": "SECTOR_TECH",
                    "group_label": "SECTOR_TECH",
                    "component_contribution": component,
                    "percent_contribution": "1.0",
                }
            ],
        }

    for component in ("n/a", "Infinity"):
        markup = render_risk_attribution_panel(
            {"risk_attribution": {"sets": [unitless_set(component)]}}
        )
        assert "could not be drawn" in markup, f"component {component} must refuse"
        assert _bars(markup) == 0


def test_the_primitive_survives_the_real_engine_on_the_v3_page() -> None:
    package = json.loads(
        Path("tests/golden/portfolio-review/v3/render-package.json").read_text(encoding="utf-8")
    )
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )

    result = service.render(RenderPackage.model_validate(package))

    text = re.sub(
        r"\s+",
        " ",
        "\n".join(
            page.extract_text() for page in pypdf.PdfReader(io.BytesIO(result.artifact_bytes)).pages
        ),
    )
    for needle in (
        "Risk attribution",
        "by SECTOR · YTD 2026-01-02 to 2026-08-31",
        "Total risk — volatility",
        "7.84%",
        "62.58%",
        "avg weight 24.5%",
        "marginal −3.1%",
        "Residual (unallocated)",
        "Contributions sum to 12.49%; stated total 12.53%.",
        "Active risk — tracking error",
        "Source quality flags: LOW_COVERAGE",
        "Bars are scaled within each decomposition",
    ):
        assert needle in text, f"the rendered page must state: {needle}"
    assert result.diagnostic.template_publication == "development", (
        "v3 is development until its own publication trigger fires"
    )
