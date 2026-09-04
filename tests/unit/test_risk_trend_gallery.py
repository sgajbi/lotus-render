"""The risk-trend gallery: the primitive exercised at its edges, without a document.

This is #219's founding entry and the shape later primitives reuse: each case in
tests/gallery/risk-trend/ is a canonical producer emission (report#255's shipped
contract), and every assertion here fails on a WRONG result, not merely a changed
one. One test also compiles the primitive through the real engine inside the v2
template, so the evidence covers a really-rendered page and not only markup.
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


def _case(name: str) -> dict[str, Any]:
    return {"risk_trend": json.loads((GALLERY / f"{name}.json").read_text(encoding="utf-8"))}


def _dots(markup: str) -> int:
    return markup.count("circle(radius: 0.9pt, fill: ink)")


def test_absence_draws_nothing_at_all() -> None:
    """No block means the report did not order the section: no panel, no heading,
    not an empty frame -- absence must be indistinguishable from pre-#255 output."""

    assert render_risk_trend_panel({}) == ""
    assert render_risk_trend_panel({"risk_trend": {}}) == ""
    assert render_risk_trend_panel({"risk_trend": {"window": {}, "metrics": []}}) == ""


def test_ready_series_draw_every_point_and_print_the_endpoints_verbatim() -> None:
    markup = render_risk_trend_panel(_case("ready-three-metrics"))

    assert "Rolling volatility" in markup
    assert "Rolling beta" in markup
    assert "Rolling tracking error" in markup
    assert _dots(markup) == 4 + 3 + 5, "every source point is a dot; nothing invented"
    for endpoint in ("10.42", "12.63", "0.91", "1.02", "1.4", "1.5"):
        assert endpoint in markup, f"endpoint {endpoint} must be printed verbatim"
    assert "63-observation rolling window" in markup
    assert "daily" in markup
    assert "YTD 2026-01-02 to 2026-08-31" in markup
    assert "line(" not in markup, "nothing connects the dots -- a line would bridge gaps"


def test_a_source_gap_is_horizontal_space_in_proportion_to_its_duration() -> None:
    """Dates place the dots, not indices: a 19-day hole in a 25-day span leaves
    ~three quarters of the strip empty, which is the gap made visible."""

    markup = render_risk_trend_panel(_case("gap-in-series"))

    for dx in ("0.00%", "4.00%", "8.00%", "84.00%", "88.00%", "100.00%"):
        assert f"dx: {dx}" in markup
    between = re.findall(r"dx: (\d+\.\d+)%", markup)
    assert not [x for x in between if 8.0 < float(x) < 84.0], (
        "no dot may be placed inside the source's hole"
    )
    assert "Source quality flags: PARTIAL_COVERAGE" in markup


def test_a_flat_series_sits_on_the_centre_line_not_on_an_invented_scale() -> None:
    markup = render_risk_trend_panel(_case("flat-series"))

    dys = set(re.findall(r"dy: (\d+\.\d+)pt", markup))
    assert dys == {"12.00"}, "equal values must sit at equal height"
    assert markup.count("1.00") >= 2, "both endpoints print, even when equal"
    assert "weekly" in markup


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


def test_the_primitive_survives_the_real_engine_on_the_v2_page() -> None:
    """Markup assertions cannot prove the template scope resolves or the page
    carries the words -- one case compiles for real through portfolio-review v2."""

    package = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    package["template_version"] = "v2"
    package["report_data"]["risk_trend"] = json.loads(
        (GALLERY / "benchmark-not-applied.json").read_text(encoding="utf-8")
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
        "Risk trend",
        "Rolling volatility",
        "10.4",
        "12.6",
        "63-observation rolling window",
        "Rolling tracking error",
        "Not available",
        "BENCHMARK_SERIES_UNAVAILABLE",
    ):
        assert needle in text, f"the rendered page must state: {needle}"
    assert result.diagnostic.template_publication == "development", (
        "v2 is development until its own publication trigger fires"
    )


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
                        "quality_flags": "not-a-list",
                        "series": [
                            "not-a-mapping",
                            {"date": "2026-08-31", "value": "12.6"},
                        ],
                    },
                    {
                        "metric": "ROLLING_BETA",
                        "posture": "ready",
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
