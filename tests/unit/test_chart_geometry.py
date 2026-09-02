"""The performance chart's arithmetic, now that Typst does the drawing.

The chart used to be an SVG string assembled in Python. Moving the drawing into Typst
moves the invariants here, where they can be stated as arithmetic rather than inferred
from markup: a gridline is a fraction of the plot box, and a point is a fraction of the
plot box, so the geometry can be checked without rendering anything.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.chart_geometry import (
    UNCHARTED_COLOUR,
    DonutSegment,
    _fraction_down,
    donut_segments,
    performance_chart_geometry,
)
from app.services.portfolio_charts import AllocationSlice, PerformancePoint
from app.services.typst_tables import render_allocation_chart_section

# The swatch colour is the only thing joining a legend row to a wedge, and both
# halves spell it the same way: `colour: "series-N"`.
_COLOURS = re.compile(r'colour: "([^"]+)"')


def _series(*values: float) -> list[PerformancePoint]:
    return [
        PerformancePoint(month=f"2025-{index + 1:02d}", cumulative_twr=value)
        for index, value in enumerate(values)
    ]


def test_an_empty_series_has_no_geometry() -> None:
    """A chart with nothing to draw is a placeholder decision, not an empty plot."""

    assert performance_chart_geometry([]) is None


def test_every_gridline_falls_inside_the_plot() -> None:
    """Nothing is ever drawn outside the plot box, whatever the axis maths decides.

    This is the second line of defence, not the first. `_fraction_down` clamps, so a tick
    outside the axis lands on the plot edge rather than off the canvas -- which is why
    reinstating the #152 derivation does *not* fail this test. The invariant that catches
    that defect is `test_every_tick_lies_within_the_axis_bounds`, asserted on the values
    in `test_portfolio_charts.py`.

    Worth keeping both: this one holds even if the axis maths is later replaced.
    """

    for series in (
        _series(0.13, 0.9, 2.4, 3.2, 4.19),
        _series(-14.2, -38.4, 18.4),
        _series(0.0),
        _series(2.5, 2.5, 2.5),
    ):
        geometry = performance_chart_geometry(series)
        assert geometry is not None
        assert geometry.gridlines, "a chart with a series must have an axis"
        outside = [line for line in geometry.gridlines if not 0.0 <= line.at <= 1.0]
        assert not outside, f"gridlines outside the plot: {outside}"


def test_every_observation_falls_inside_the_plot() -> None:
    """The axis ends on its outermost ticks, so the series cannot escape the box."""

    geometry = performance_chart_geometry(_series(0.13, 0.9, 2.4, 3.2, 4.19))
    assert geometry is not None
    for point in geometry.points:
        assert 0.0 <= point.at <= 1.0 and 0.0 <= point.value <= 1.0, point


def test_exactly_one_gridline_is_the_zero_line() -> None:
    """The zero line is drawn darker because it is the one a reader looks for.

    A series that straddles zero must have it; the axis always includes zero because
    `_chart_value_bounds` seeds its values with 0.0.
    """

    geometry = performance_chart_geometry(_series(-14.2, -38.4, 18.4))
    assert geometry is not None
    zero_lines = [line for line in geometry.gridlines if line.zero]
    assert len(zero_lines) == 1, [line.label for line in geometry.gridlines]
    assert zero_lines[0].label == "0%"


def test_a_rising_series_is_drawn_rising() -> None:
    """`value` runs top to bottom, so a larger return is a smaller fraction.

    Getting this inverted would draw every chart upside down while every gridline stayed
    inside the plot, so it is asserted rather than assumed.
    """

    geometry = performance_chart_geometry(_series(1.0, 5.0))
    assert geometry is not None
    first, last = geometry.points[0], geometry.points[-1]
    assert last.value < first.value, "the higher return should sit higher on the page"
    assert first.at == 0.0 and last.at == 1.0


def test_a_single_observation_sits_in_the_middle() -> None:
    """One point has no span to spread across, and a mark at x=0 reads as a truncation."""

    geometry = performance_chart_geometry(_series(3.0))
    assert geometry is not None
    assert geometry.points[0].at == 0.5
    assert geometry.labels[0].at == 0.5


def test_a_benchmark_of_fewer_than_two_points_is_not_drawn() -> None:
    """A one-point dashed line says nothing about direction, which is why it is drawn."""

    one = [PerformancePoint(month="2025-01", cumulative_twr=1.0, benchmark_cumulative_twr=0.9)]
    geometry = performance_chart_geometry(one)
    assert geometry is not None
    assert geometry.benchmark == []

    two = one + [
        PerformancePoint(month="2025-02", cumulative_twr=2.0, benchmark_cumulative_twr=1.8)
    ]
    geometry = performance_chart_geometry(two)
    assert geometry is not None
    assert len(geometry.benchmark) == 2


def test_month_labels_are_carried_through_for_every_observation() -> None:
    """One label per point, positioned by the same fraction, so they cannot drift apart."""

    geometry = performance_chart_geometry(_series(1.0, 2.0, 3.0))
    assert geometry is not None
    assert len(geometry.labels) == len(geometry.points)
    assert [label.at for label in geometry.labels] == [point.at for point in geometry.points]
    assert geometry.labels[0].text == "Jan 25"


def test_no_document_embeds_an_svg_and_therefore_none_carries_its_text() -> None:
    """SVG containing `<text>` sits on an open Typst non-determinism bug.

    typst#6783: when an embedded SVG carries text in more than one font style, the PDF's
    font sections can swap order between otherwise identical renders. The two charts
    emitted fifteen `<text>` elements between them, so every render was relying on luck --
    and the bounded fingerprint, which strips timestamps but not font-section order, would
    have reported the swap as a real change with no cause anyone could find.

    Both charts are now drawn natively, so this is stated as a repository-wide rule rather
    than scoped to the half that was converted first.
    """

    from pathlib import Path

    from app.contracts.render_package import RenderPackage
    from app.services.typst_contexts import build_portfolio_review_context

    package = RenderPackage.model_validate_json(
        Path("tests/golden/portfolio-review/v1/render-package.json").read_text(encoding="utf-8")
    )
    context = build_portfolio_review_context(package)

    offenders = {
        key: value[:60]
        for key, value in context.items()
        if "<svg" in value or "<text" in value or "assets/charts" in value
    }
    assert not offenders, (
        f"these context values still ship SVG or reference an image asset: {offenders}. "
        "Charts are drawn with Typst primitives so they inherit the design system and "
        "stay clear of typst#6783."
    )

    assert "line-chart(" in context["PERFORMANCE_12M_CHART_SECTION"]
    assert "donut-chart(" in context["ALLOCATION_DONUT_CHART_SECTION"]


def _slice(
    label: str, weight: str, value: str = "1000", colour: str = "#1F5AA6"
) -> AllocationSlice:
    return AllocationSlice(
        label=label, weight_pct=Decimal(weight), market_value=Decimal(value), color=colour
    )


def test_a_single_full_slice_draws_a_complete_ring() -> None:
    """A portfolio that is 100% one asset class must still draw a donut.

    The old SVG needed a special-cased `_donut_ring`, because a 360-degree arc has the
    same start and end point and an arc command cannot say which way round to go. Split
    into quarter turns there is no special case: four segments trace the circle, and the
    path closes where it started.
    """

    segments = donut_segments([_slice("Equity", "100")])

    assert len(segments) == 1
    kinds = [kind for kind, _ in segments[0].commands]
    assert kinds[0] == "move" and kinds[-1] == "close"
    # A full turn is four quarter-turn cubics on the outer arc and four coming back.
    assert kinds.count("cubic") == 8
    assert kinds.count("line") == 1


def test_slices_sweep_in_proportion_to_their_weights() -> None:
    """The angle a reader compares must be the weight the number states.

    Counted in quarter-turn segments, which is the proportional quantity visible from the
    command list: a 75% slice spans three quarters out and three back, a 25% slice one
    each way.
    """

    segments = donut_segments([_slice("Big", "75"), _slice("Small", "25")])

    assert [[kind for kind, _ in segment.commands].count("cubic") for segment in segments] == [6, 2]


def test_slices_are_laid_out_end_to_end_from_twelve_oclock() -> None:
    """Each slice starts where the last one ended, or the ring has gaps in it."""

    segments = donut_segments([_slice("A", "50"), _slice("B", "30"), _slice("C", "20")])

    assert segments[0].commands[0] == ("move", (0.5, 0.0)), "the ring should open at twelve"
    for earlier, later in zip(segments, segments[1:], strict=False):
        kinds = [kind for kind, _ in earlier.commands]
        end_of_outer = earlier.commands[kinds.index("line") - 1][1][-2:]
        assert end_of_outer == pytest.approx(later.commands[0][1], abs=1e-9)


def test_a_breakdown_with_no_slices_draws_nothing() -> None:
    """No slices means no angles; the section falls back to a placeholder card.

    This used to also assert `donut_segments([_slice("Empty", "0")]) == []` -- the drop
    that left a legend row behind. A weightless slice no longer builds, so the empty
    list is the only emptiness left here.
    """

    assert donut_segments([]) == []


def test_a_flat_axis_places_its_values_mid_plot() -> None:
    """A series with no spread has no meaningful top or bottom to measure against.

    The axis is padded before it reaches here, so this is unreachable through the
    chart itself; it exists so a caller that ever hands over a degenerate axis gets a
    mark in the middle of the plot rather than a division by zero.
    """

    assert _fraction_down(5.0, 5.0, 5.0) == 0.5
    assert _fraction_down(0.0, 4.0, 1.0) == 0.5


def test_a_weightless_slice_cannot_be_built() -> None:
    """Dropping it here left its legend row behind, pointing at a wedge nobody drew.

    The ring and the legend come from one list joined only by position, so `donut_segments`
    skipping a slice was a decision the legend never heard about. This test asserted the
    skip and never looked at the legend. The slice refuses to exist instead, which is
    where the fact belongs -- and `_allocation_entry` has always dropped a weightless row
    before one is built, so nothing legitimate reaches this.
    """

    with pytest.raises(ValueError, match="pointing at nothing"):
        _slice("Dust", "0")


def test_the_legend_and_the_ring_name_the_same_slices() -> None:
    """Both halves render whatever they are given, so a disagreement is silent.

    Read back off the emitted markup rather than off the list they were built from: the
    swatch colour is the only thing tying a legend row to a wedge, and this is the check
    that would have caught either half dropping one.
    """

    for name, report_data in _allocation_cases():
        section = render_allocation_chart_section(report_data)
        if "chart-placeholder" in section:
            continue
        drawn, _, listed = section.partition("entries:")
        wedges = [colour for colour in _COLOURS.findall(drawn) if colour != UNCHARTED_COLOUR]
        rows = _COLOURS.findall(listed)
        assert wedges == rows, (
            f"{name}: the ring draws {wedges} and the legend names {rows}; a row with no "
            "wedge is a swatch naming nothing."
        )
        assert len(rows) == len(set(rows)), (
            f"{name}: two rows share a swatch, {rows}. Colour is the only key a donut has."
        )


def _allocation_cases() -> list[tuple[str, dict[str, object]]]:
    """Every shipped fixture, plus the crowded breakdown none of them is.

    All three fixtures with a real donut have three slices, so the goldens alone would
    have watched the two halves agree while never reaching the count at which they came
    apart. Nine asset classes is not exotic -- it is what a breakdown looks like once
    sub-classes are reported separately.
    """
    cases = [
        (
            path.parent.name,
            json.loads(path.read_text(encoding="utf-8")).get("report_data") or {},
        )
        for path in sorted(Path("tests/golden").rglob("render-package.json"))
    ]
    cases.append(
        (
            "nine asset classes",
            {
                "allocation_breakdowns": {
                    "by_asset_class": [
                        {
                            "name": f"Class {index}",
                            "weight_pct": f"{10 - index}.00%",
                            "market_value": "1000",
                        }
                        for index in range(9)
                    ]
                }
            },
        )
    )
    return cases


def _angle(point: tuple[float, ...]) -> float:
    """Clockwise from twelve, matching the frame the geometry is built in."""
    return math.atan2(point[0] - 0.5, 0.5 - point[1]) % math.tau


def _sweep_of(segment: DonutSegment) -> float:
    """The angle a wedge covers, read back off the ends of its outer arc.

    The outer arc runs from the opening `move` to the radial `line` inward, so the last
    cubic before that line ends where the wedge ends.
    """
    commands = segment.commands
    line_index = next(index for index, command in enumerate(commands) if command[0] == "line")
    start = commands[0][1]
    end = commands[line_index - 1][1][4:6]
    return (_angle(end) - _angle(start)) % math.tau


def test_a_partial_breakdown_sweeps_its_stated_weights_not_its_own_sum() -> None:
    """The ring has to agree with the legend printed beside it.

    Dividing each weight by the sum of the weights is the tempting normalisation, and
    on the golden package -- whose slices cover 89.64% -- it drew Equity as 67% of the
    ring under a label reading 60.00%. A chart that restates its own numbers is the
    same class of defect as a gridline drawn outside the plot.
    """

    segments = donut_segments([_slice("Equity", "60"), _slice("Fixed Income", "28")])

    assert _sweep_of(segments[0]) == pytest.approx(0.60 * math.tau, abs=1e-6)
    assert _sweep_of(segments[1]) == pytest.approx(0.28 * math.tau, abs=1e-6)


def test_the_uncharted_remainder_is_drawn_rather_than_left_blank() -> None:
    """A gap in the ring is the shortfall the coverage note describes, made visible.

    Left undrawn it reads as a rendering fault; drawn in the rule colour it reads as
    the absence it is.
    """

    segments = donut_segments([_slice("Equity", "60"), _slice("Fixed Income", "28")])

    assert segments[-1].colour == UNCHARTED_COLOUR
    assert _sweep_of(segments[-1]) == pytest.approx(0.12 * math.tau, abs=1e-6)
    assert UNCHARTED_COLOUR not in {segment.colour for segment in segments[:-1]}


def test_a_complete_breakdown_leaves_no_remainder() -> None:
    """Weights that already cover the portfolio get the whole ring and no gap."""

    segments = donut_segments([_slice("Equity", "70"), _slice("Fixed Income", "30")])

    assert [segment.colour for segment in segments] == ["#1F5AA6", "#1F5AA6"]
    assert UNCHARTED_COLOUR not in {segment.colour for segment in segments}


def test_weights_that_overshoot_a_circle_are_renormalised_rather_than_overlapped() -> None:
    """Bad upstream data must not draw slices on top of each other."""

    segments = donut_segments([_slice("A", "80"), _slice("B", "80")])

    assert len(segments) == 2, "an overshooting breakdown gained a remainder"
    assert _sweep_of(segments[0]) == pytest.approx(math.tau / 2, abs=1e-6)
    assert _sweep_of(segments[1]) == pytest.approx(math.tau / 2, abs=1e-6)
