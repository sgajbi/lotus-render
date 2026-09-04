"""The risk-trend gallery: the primitive exercised at its edges, without a document.

This is #219's founding entry and the shape later primitives reuse: each case in
tests/gallery/risk-trend/ is a canonical producer emission with SOURCE-SHAPED
values (rolling volatility and tracking error arrive as annualized decimal
ratios; beta is unitless), and every assertion here fails on a WRONG result, not
merely a changed one. Real-engine tests compile cases through the actual v2
template page, including the cross-repo regression that 0.1374 -> 0.141 reaches
the reader as 13.74% -> 14.1%.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pypdf

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.risk_trend import render_risk_trend_panel
from app.services.typst_rendering import TypstRenderService

GALLERY = Path("tests/gallery/risk-trend")
SCALE_STATEMENT = "independently scaled"


def _case(name: str) -> dict[str, Any]:
    return {"risk_trend": json.loads((GALLERY / f"{name}.json").read_text(encoding="utf-8"))}


def _dots(markup: str) -> int:
    return markup.count("circle(radius: 0.9pt, fill: ink)")


def _page_text(package: dict[str, Any]) -> tuple[str, str]:
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
    return text, result.diagnostic.template_publication or ""


def _v2_package(case: str) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(
        PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8")
    )
    package["template_version"] = "v2"
    package["report_data"]["risk_trend"] = json.loads(
        (GALLERY / f"{case}.json").read_text(encoding="utf-8")
    )
    return package


def test_absence_draws_nothing_at_all() -> None:
    """No block means the report did not order the section: no panel, no heading,
    not an empty frame -- absence must be indistinguishable from pre-#255 output."""

    assert render_risk_trend_panel({}) == ""
    assert render_risk_trend_panel({"risk_trend": {}}) == ""
    assert render_risk_trend_panel({"risk_trend": {"window": {}, "metrics": []}}) == ""


def test_endpoints_reach_the_reader_in_their_units() -> None:
    """The P1: 0.1374 means 13.74%. A decimal_ratio endpoint is shifted exactly
    (no float, no rounding) and carries its percent sign; a unitless endpoint is
    the source string verbatim. The raw values stay untouched in the series."""

    markup = render_risk_trend_panel(_case("ready-three-metrics"))

    assert "13.74%" in markup and "14.1%" in markup, "volatility must read as percent"
    assert "1.9%" in markup and "2.06%" in markup, "tracking error must read as percent"
    assert "0.91" in markup and "1.02" in markup, "beta is unitless and verbatim"
    assert "0.1374" not in markup, "the raw ratio must not be printed as a reader value"
    assert _dots(markup) == 4 + 3 + 5, "every source point is a dot; nothing invented"
    assert "63-observation rolling window" in markup
    assert "YTD 2026-01-02 to 2026-08-31" in markup
    assert "line(" not in markup, "nothing connects the dots"


def test_a_ready_series_without_unit_semantics_is_not_stated() -> None:
    """Printing 0.1374 bare where the reader means 13.74% is confidently wrong:
    without the source's unit, the number is not stated and nothing is drawn."""

    markup = render_risk_trend_panel(_case("unit-missing"))

    assert _dots(markup) == 0
    assert "without unit semantics" in markup
    assert "0.1374" not in markup
    assert SCALE_STATEMENT not in markup, "no strip drawn, no convention to state"


def test_weekend_cadence_is_market_rhythm_not_missing_evidence() -> None:
    """Ten business days across two weeks: dots are placed by observation index,
    evenly spaced -- the weekend between the Friday and the Monday must not
    appear as a hole, because calendar distance is not data-quality evidence."""

    markup = render_risk_trend_panel(_case("weekend-cadence"))

    positions = [float(x) for x in re.findall(r"dx: (\d+\.\d+)%", markup)]
    assert len(positions) == 10
    for index, position in enumerate(positions):
        assert abs(position - index * 100 / 9) < 0.01, (
            f"dot {index} must sit at its observation index, not its calendar day"
        )


def test_partial_coverage_is_stated_never_implied_away() -> None:
    """The source computed from July while the stated period is the full YTD:
    the caption states the period, the coverage line states what was observed,
    and the two together make warm-up coverage explicit without spatial guessing."""

    markup = render_risk_trend_panel(_case("warmup-partial-coverage"))

    assert "YTD 2026-01-02 to 2026-08-31" in markup, "the stated period stays stated"
    assert "4 observations, 2026-07-01 to 2026-08-31" in markup, (
        "the observed span is the coverage fact"
    )
    assert "Source quality flags: PARTIAL_COVERAGE" in markup


def test_independent_scales_are_stated_wherever_a_strip_is_drawn() -> None:
    """The adversarial case: 10% -> 30% and 2% -> 2.06% normalize to similar
    shapes. Without the stated convention they would read as comparable moves;
    with it, the endpoint figures carry the actual levels."""

    markup = render_risk_trend_panel(_case("adversarial-scale"))

    assert markup.count(SCALE_STATEMENT) == 1
    assert "10%" in markup and "30%" in markup
    assert "2.00%" in markup and "2.06%" in markup, (
        "the source stated 0.0200; its precision survives the shift"
    )
    heights = {round(float(y), 2) for y in re.findall(r"dy: (\d+\.\d+)pt", markup)}
    assert 2.00 in heights and 22.00 in heights, (
        "both strips span the full band -- which is exactly why the statement exists"
    )


def test_a_flat_series_sits_on_the_centre_line_not_on_an_invented_scale() -> None:
    markup = render_risk_trend_panel(_case("flat-series"))

    dys = set(re.findall(r"dy: (\d+\.\d+)pt", markup))
    assert dys == {"12.00"}, "equal values must sit at equal height"
    assert markup.count("1.00") >= 2, "both endpoints print verbatim, even when equal"
    assert "3 observations, 2026-06-05 to 2026-08-07" in markup


def test_benchmark_relative_series_state_the_sources_reason_never_draw() -> None:
    """The #241 voice: a benchmark the source could not apply makes the series
    unavailable in the source's own words -- never invisible, never drawn flat."""

    markup = render_risk_trend_panel(_case("benchmark-not-applied"))

    assert _dots(markup) == 2, "only the ready volatility series draws"
    assert markup.count("Not available") == 2
    assert markup.count("BENCHMARK_SERIES_UNAVAILABLE") == 2
    assert "Rolling beta" in markup
    assert "Rolling tracking error" in markup


def test_empty_and_unavailable_are_different_statements() -> None:
    markup = render_risk_trend_panel(_case("empty-and-unavailable"))

    assert _dots(markup) == 0
    assert "Not included" in markup
    assert "NO_METRIC_SERIES" in markup
    assert "Not available" in markup
    assert "The source emitted no result for the requested window." in markup
    assert "Source quality flags: STALE_INPUT" in markup


def test_a_ready_claim_this_module_cannot_place_is_said_not_approximated() -> None:
    """A one-point trend, an unparseable value, a non-finite value, and dates out
    of order are four ways a 'ready' claim can be undrawable -- each is stated,
    and no dot is ever placed from a value that did not parse."""

    single = render_risk_trend_panel(_case("single-point-claims-ready"))
    assert _dots(single) == 0
    assert "could not be drawn" in single

    unplaceable = render_risk_trend_panel(_case("unplaceable-values"))
    assert _dots(unplaceable) == 0
    assert unplaceable.count("could not be drawn") == 3


def test_malformed_shapes_state_rather_than_crash_or_invent() -> None:
    """The producer contract is trusted but not assumed: every malformed shape a
    forwarding bug could produce lands on a stated row or a silent omission --
    never an exception, never a dot placed from data that did not parse."""

    markup = render_risk_trend_panel(
        {
            "risk_trend": {
                "window": None,
                "metrics": [
                    {"metric": None, "posture": "unknown-posture", "notes": "not-a-list"},
                    {
                        "metric": "ROLLING_VOLATILITY",
                        "posture": "ready",
                        "unit": "decimal_ratio",
                        "quality_flags": "not-a-list",
                        "series": [
                            "not-a-mapping",
                            {"date": "2026-08-31", "value": "0.141"},
                        ],
                    },
                    {
                        "metric": "ROLLING_BETA",
                        "posture": "ready",
                        "unit": "unitless",
                        "series": [
                            {"date": "31/08/2026", "value": "1.0"},
                            {"date": "2026-08-31", "value": "1.1"},
                        ],
                    },
                    {
                        "metric": "CUSTOM_METRIC_ID",
                        "posture": "unavailable",
                        "notes": [{"code": "x", "message": "   "}, {"message": "stated reason"}],
                    },
                ],
            }
        }
    )

    assert _dots(markup) == 0, "no dot may come from a series with unplaceable members"
    assert "Unnamed metric" in markup
    assert "The source stated no posture for this series." in markup
    assert markup.count("could not be drawn") == 2
    assert "CUSTOM_METRIC_ID" in markup, "an unknown id prints verbatim, never renamed"
    assert "stated reason" in markup, "the first non-blank note message is the one stated"
    assert "Source quality flags" not in markup


def test_partial_window_facts_are_stated_partially_never_invented() -> None:
    """A caption states exactly the facts present: frequency without a count,
    a period span without a name, and a window with nothing yields no caption."""

    frequency_only = render_risk_trend_panel(
        {
            "risk_trend": {
                "window": {"frequency": "weekly", "period": {"start_date": "2026-01-02"}},
                "metrics": [{"metric": "ROLLING_BETA", "posture": "empty"}],
            }
        }
    )
    assert "weekly · 2026-01-02" in frequency_only
    assert "rolling window" not in frequency_only

    nameless_span = render_risk_trend_panel(
        {
            "risk_trend": {
                "window": {"window_observations": 21, "period": {"name": "   "}},
                "metrics": [{"metric": "ROLLING_BETA", "posture": "empty"}],
            }
        }
    )
    assert "21-observation rolling window" in nameless_span

    bare = render_risk_trend_panel(
        {
            "risk_trend": {
                "window": {},
                "metrics": [{"metric": "ROLLING_BETA", "posture": "empty"}],
            }
        }
    )
    assert '#section-subtitle("Risk trend")\n#v(6pt)' in bare, (
        "an empty caption emits no caption line between the subtitle and the rows"
    )
    assert "Not included" in bare


def test_source_shaped_values_reach_the_reader_as_percentages_on_the_real_page() -> None:
    """The cross-repo regression the steering requires, with the same
    source-shaped values lotus-report tests: rolling volatility 0.1374 -> 0.141
    and tracking error around 0.02 must reach the RENDERED PAGE as percentage
    meaning, alongside the coverage fact and the scale convention."""

    text, publication = _page_text(_v2_package("ready-three-metrics"))

    for needle in (
        "Risk trend",
        "Rolling volatility",
        "13.74%",
        "14.1%",
        "1.9%",
        "2.06%",
        "0.91",
        "1.02",
        "63-observation rolling window",
        "4 observations, 2026-06-01 to 2026-08-31",
        "independently scaled",
    ):
        assert needle in text, f"the rendered page must state: {needle}"
    assert "0.1374" not in text, "the raw ratio must not reach the reader bare"
    assert publication == "development", "v2 stays development until its own trigger"


def test_the_benchmark_refusal_survives_the_real_engine_on_the_v2_page() -> None:
    text, _ = _page_text(_v2_package("benchmark-not-applied"))

    for needle in (
        "Rolling tracking error",
        "Not available",
        "BENCHMARK_SERIES_UNAVAILABLE",
        "13.74%",
    ):
        assert needle in text, f"the rendered page must state: {needle}"
