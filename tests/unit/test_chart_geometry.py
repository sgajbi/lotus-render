"""The performance chart's arithmetic, now that Typst does the drawing.

The chart used to be an SVG string assembled in Python. Moving the drawing into Typst
moves the invariants here, where they can be stated as arithmetic rather than inferred
from markup: a gridline is a fraction of the plot box, and a point is a fraction of the
plot box, so the geometry can be checked without rendering anything.
"""

from __future__ import annotations

from app.services.chart_geometry import performance_chart_geometry
from app.services.portfolio_charts import PerformancePoint


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


def test_the_performance_chart_ships_no_svg_and_therefore_no_embedded_text() -> None:
    """SVG containing `<text>` sits on an open Typst non-determinism bug.

    typst#6783: when an embedded SVG carries text in more than one font style, the PDF's
    font sections can swap order between otherwise identical renders. The performance
    chart emitted nine `<text>` elements, so every render was relying on luck — and the
    bounded fingerprint, which strips timestamps but not font-section order, would have
    reported the swap as a real change with no cause anyone could find.

    The allocation donut is still an SVG and still carries text. It is the next chart to
    convert (#150); this asserts the half that is done rather than a rule the repository
    does not yet keep.
    """

    from pathlib import Path

    from app.contracts.render_package import RenderPackage
    from app.services.typst_contexts import build_portfolio_review_context

    package = RenderPackage.model_validate_json(
        Path("tests/golden/portfolio-review/v1/render-package.json").read_text(encoding="utf-8")
    )
    section = build_portfolio_review_context(package)["PERFORMANCE_12M_CHART_SECTION"]

    assert "#line-chart(" in section, "the performance chart is no longer drawn natively"
    assert "<svg" not in section and "<text" not in section
    assert "assets/charts" not in section, "the chart is back to being an image asset"


def test_a_degenerate_axis_places_marks_in_the_middle() -> None:
    """An axis with no span has no meaningful position for anything on it.

    Half-height is the honest answer: it puts every mark on one line, which reads as
    "these are all the same" rather than as a slope the data does not have.
    """

    from app.services.chart_geometry import _fraction_down

    assert _fraction_down(5.0, low=2.0, high=2.0) == 0.5
    assert _fraction_down(5.0, low=3.0, high=2.0) == 0.5
    # A real axis still maps ends to ends.
    assert _fraction_down(2.0, low=2.0, high=6.0) == 1.0
    assert _fraction_down(6.0, low=2.0, high=6.0) == 0.0
