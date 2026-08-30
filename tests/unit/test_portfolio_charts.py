import re
from decimal import Decimal
from pathlib import Path

from app.services.portfolio_charts import (
    CHART_BOTTOM,
    CHART_HEIGHT,
    CHART_TOP,
    AllocationSlice,
    PerformancePoint,
    _chart_axis,
    _chart_value_bounds,
    _compact_value,
    _donut_segment,
    _nice_ticks,
    _parse_currency_number,
    _parse_percent_or_number,
    _polyline,
    allocation_items_from_report_data,
    performance_series_from_report_data,
    render_allocation_donut_svg,
    render_performance_svg,
    render_portfolio_chart_assets,
)


def test_performance_series_uses_latest_12_months_and_benchmark_when_present() -> None:
    report_data = {
        "performance_series": [
            {
                "month": f"2025-{month:02d}",
                "cumulative_twr": month / 10,
                "benchmark_cumulative_twr": month / 20,
            }
            for month in range(1, 14)
        ]
    }

    series = performance_series_from_report_data(report_data)

    assert len(series) == 12
    assert series[0].month == "2025-02"
    assert series[-1].month == "2025-13"
    assert series[-1].cumulative_twr == 1.3
    assert series[-1].benchmark_cumulative_twr == 0.65


def test_allocation_items_sort_and_group_small_slices() -> None:
    report_data = {
        "allocation_breakdowns": {
            "by_asset_class": [
                {"name": "Cash", "weight_pct": "1.00%", "market_value": "100"},
                {"name": "Equity", "weight_pct": "60.00%", "market_value": "6000"},
                {"name": "Alternatives", "weight_pct": "1.50%", "market_value": "150"},
                {"name": "Fixed Income", "weight_pct": "28.00%", "market_value": "2800"},
                {"name": "Real Estate", "weight_pct": "9.50%", "market_value": "950"},
            ]
        }
    }

    items = allocation_items_from_report_data(report_data)

    assert [item.label for item in items] == ["Equity", "Fixed Income", "Real Estate", "Other"]
    assert items[-1].weight_pct == Decimal("2.50")
    assert items[-1].market_value == Decimal("250")


def test_svg_renderers_emit_enterprise_chart_primitives() -> None:
    report_data = {
        "performance_series": [
            {"month": "2025-05", "cumulative_twr": 0.44, "benchmark_cumulative_twr": 0.31},
            {"month": "2025-06", "cumulative_twr": 0.13, "benchmark_cumulative_twr": 0.22},
            {"month": "2025-07", "cumulative_twr": 0.98, "benchmark_cumulative_twr": 0.80},
        ],
        "allocation_breakdowns": {
            "by_asset_class": [
                {"name": "Equity", "weight_pct": "60.00%", "market_value": "9140740.73"},
                {"name": "Fixed Income", "weight_pct": "28.00%", "market_value": "4265680.61"},
            ]
        },
    }

    performance_svg = render_performance_svg(performance_series_from_report_data(report_data))
    allocation_svg = render_allocation_donut_svg(allocation_items_from_report_data(report_data))

    assert "Portfolio" in performance_svg
    assert "stroke-dasharray" in performance_svg
    assert "May 25" in performance_svg
    assert "<circle" in performance_svg
    assert "Invested value" in allocation_svg
    assert "A 54 54" in allocation_svg


def test_render_portfolio_chart_assets_writes_expected_svg_files(tmp_path: Path) -> None:
    report_data = {
        "performance_monthly_history": [
            {"period": "2025-05", "cumulative_twr_pct": "0.44%"},
            {"period": "2025-06", "cumulative_twr_pct": "0.13%"},
        ],
        "allocation_breakdowns": {
            "by_asset_class": [
                {"name": "Equity", "weight_pct": "60.00%", "market_value": "9140740.73"}
            ]
        },
    }

    assets = render_portfolio_chart_assets(report_data, tmp_path)

    assert assets.performance_svg == tmp_path / "performance_12m.svg"
    assert assets.allocation_svg == tmp_path / "allocation_asset_class.svg"
    assert assets.performance_svg.exists()
    assert assets.allocation_svg.exists()


def test_render_portfolio_chart_assets_degrades_without_chart_data(tmp_path: Path) -> None:
    assets = render_portfolio_chart_assets(
        {
            "performance_series": "not chart rows",
            "allocation_breakdowns": {"by_asset_class": "not allocation rows"},
        },
        tmp_path,
    )

    assert assets.performance_svg is None
    assert assets.allocation_svg is None
    assert list(tmp_path.iterdir()) == []


def test_performance_series_skips_invalid_rows_and_uses_period_fallback() -> None:
    series = performance_series_from_report_data(
        {
            "performance_monthly_history": [
                "bad row",
                {"period": "", "cumulative_twr_pct": "1.00%"},
                {"period": "2025-01", "cumulative_twr_pct": "not available"},
                {
                    "period": "2025-02",
                    "cumulative_twr_pct": "1.25%",
                    "benchmark_cumulative_twr_pct": "0.50%",
                },
            ]
        }
    )

    assert len(series) == 1
    assert series[0].month == "2025-02"
    assert series[0].cumulative_twr == 1.25
    assert series[0].benchmark_cumulative_twr == 0.5


def test_allocation_items_use_fallback_rows_and_skip_invalid_values() -> None:
    items = allocation_items_from_report_data(
        {
            "allocation_items": [
                "bad row",
                {"label": "", "weight_pct": "5.00%", "market_value": "500"},
                {"label": "Zero", "weight_pct": "0.00%", "market_value": "0"},
                {"label": "Invalid", "weight_pct": "n/a", "market_value": "100"},
                {"label": "Equity", "weight_pct": "70.00%", "market_value": "USD 7,000"},
                {"label": "Cash", "weight_pct": "1.00%", "market_value": ""},
            ]
        }
    )

    assert [item.label for item in items] == ["Equity", "Cash"]
    assert items[0].market_value == Decimal("7000")
    assert items[1].market_value == Decimal("0")


def test_allocation_items_wrap_palette_without_grouping_large_rows() -> None:
    items = allocation_items_from_report_data(
        {
            "allocation_breakdowns": {
                "by_asset_class": [
                    {"name": f"Class {index}", "weight_pct": "3.00%", "market_value": "300"}
                    for index in range(7)
                ]
            }
        }
    )

    assert len(items) == 7
    assert items[0].color == items[6].color


def test_allocation_donut_escapes_labels_and_formats_small_total() -> None:
    items = allocation_items_from_report_data(
        {
            "allocation_items": [
                {
                    "label": "Equity & Growth",
                    "weight_pct": "100.00%",
                    "market_value": "999",
                }
            ]
        }
    )

    svg = render_allocation_donut_svg(items)

    assert "Equity &amp; Growth" in svg
    assert ">999<" in svg


def test_performance_svg_handles_single_point_without_benchmark() -> None:
    svg = render_performance_svg(
        [
            performance_series_from_report_data(
                {"performance_series": [{"month": "bad-month", "cumulative_twr": "0.20%"}]}
            )[0]
        ]
    )

    assert "bad-month" in svg
    assert "Benchmark" not in svg
    assert 'cx="478.00"' in svg


def test_chart_helper_fallbacks_are_stable() -> None:
    assert _parse_percent_or_number(None) is None
    assert _parse_percent_or_number("n/a") is None
    assert _parse_percent_or_number("bad") is None
    assert _parse_percent_or_number("1,234.50%") == 1234.5

    assert _parse_currency_number(None) is None
    assert _parse_currency_number("") is None
    assert _parse_currency_number("bad") is None
    assert _parse_currency_number("USD 1,234.50") == Decimal("1234.50")

    assert _nice_ticks(1, 2, 1) == [1, 2]
    assert _polyline([]) == ""
    assert _compact_value(999) == "999"
    assert _compact_value(1_500) == "1.5K"
    assert _compact_value(2_500_000) == "2.5M"

    small_arc = _donut_segment(0, 0, 10, 5, 0, 90, "#000000")
    large_arc = _donut_segment(0, 0, 10, 5, 0, 270, "#000000")
    assert " 0 0 1 " in small_arc
    assert " 0 1 1 " in large_arc


def test_non_finite_numerics_degrade_charts_instead_of_crashing() -> None:
    """nan/inf in report data must be treated as absent, not reach chart maths.

    Regression for issue #104: Decimal("NaN") in a weight signalled InvalidOperation
    on its first comparison and stranded the render; float nan/inf crashed
    math.floor/ceil in the chart bounds.
    """

    assert _parse_percent_or_number("nan") is None
    assert _parse_percent_or_number("inf") is None
    assert _parse_currency_number("NaN") is None

    items = allocation_items_from_report_data(
        {
            "allocation_items": [
                {"label": "Bad", "weight_pct": "NaN", "market_value": "10"},
                {"label": "Good", "weight_pct": "40", "market_value": "20"},
            ]
        }
    )
    assert [item.label for item in items] == ["Good"]

    series = performance_series_from_report_data(
        {
            "performance_series": [
                {"month": "2026-01", "cumulative_twr": "inf"},
                {"month": "2026-02", "cumulative_twr": "1.5"},
            ]
        }
    )
    assert [point.month for point in series] == ["2026-02"]
    # Bounds must compute over the finite point without raising.
    assert render_performance_svg(series).startswith("<svg")


def test_a_single_full_circle_slice_renders_a_visible_ring() -> None:
    """A portfolio that is 100% one asset class must still draw a donut.

    A 360-degree arc starts and ends at the same point, and SVG omits an arc whose
    endpoints coincide, so the path collapsed to zero area and the white centre circle
    covered what was left: an empty donut for a perfectly ordinary portfolio.
    """

    svg = render_allocation_donut_svg(
        [AllocationSlice("Global Equity", Decimal("100.00"), Decimal("1000000"), "#1F5AA6")]
    )

    assert 'fill-rule="evenodd"' in svg, "the full-circle slice is not drawn as a ring"
    paths = re.findall(r'<path d="([^"]+)"', svg)
    assert paths, "no slice path was emitted at all"
    start = re.match(r"M ([\d.-]+) ([\d.-]+)", paths[0])
    assert start is not None
    # A ring is two sub-paths; a collapsed arc would return to its start immediately.
    assert paths[0].count("a ") >= 4, "the ring does not close over two arcs per edge"


def test_axis_gridlines_land_on_round_values_including_zero() -> None:
    """A line labelled 0% must be at zero; a performance axis that lies is not cosmetic.

    Linear interpolation between the bounds put ticks at arbitrary values and printed
    them with no decimals, so a 12-45% series drew gridlines labelled -7%, 8%, 22%,
    37%, 52% and a line labelled "0%" actually sat at +0.5.
    """

    points = [
        PerformancePoint(month="2026-01", cumulative_twr=12.0),
        PerformancePoint(month="2026-02", cumulative_twr=18.0),
        PerformancePoint(month="2026-03", cumulative_twr=45.0),
    ]
    low, high = _chart_value_bounds(points)
    ticks = _nice_ticks(low, high, 5)

    assert any(abs(tick) < 1e-9 for tick in ticks), "no gridline sits at zero"
    for tick in ticks:
        # Every tick must print exactly what it is, at the label's precision.
        assert abs(tick - round(tick)) < 1e-9, f"gridline {tick} is not a round value"


def test_every_legend_row_fits_on_the_canvas() -> None:
    """The palette wraps at six, so a seven-category allocation had colours for rows
    the canvas silently cut off."""

    items = [
        AllocationSlice(f"Class {index}", Decimal("12.5"), Decimal("100"), "#1F5AA6")
        for index in range(8)
    ]

    svg = render_allocation_donut_svg(items)

    canvas = re.search(r'height="(\d+)"', svg)
    assert canvas is not None, "the donut svg declares no height"
    height = int(canvas.group(1))
    rows = [int(y) for y in re.findall(r'y="(\d+)" class="legend-label"', svg)]
    assert len(rows) == len(items), "not every slice produced a legend row"
    assert all(y <= height for y in rows), (
        f"legend rows {[y for y in rows if y > height]} fall off a {height}pt canvas"
    )


def _gridline_label_positions(svg: str) -> list[tuple[str, float]]:
    """Every axis label the chart drew, with the y it was drawn at."""
    return [
        (match.group(2), float(match.group(1)))
        for match in re.finditer(
            r'<text x="\d+" y="([-\d.]+)" text-anchor="end" class="axis">([^<]+)</text>', svg
        )
    ]


def test_every_gridline_the_chart_draws_falls_inside_the_plot() -> None:
    """Axis bounds and tick values used to be derived independently and disagree.

    `_chart_value_bounds` rounds outward to integers and `_nice_ticks` rounds outward to
    its own step, so on the golden series -- bounds (-1, 5), ticks [-2, 0, 2, 4, 6] --
    two of the five gridlines fell outside the plot. The `-2%` label rendered 32px below
    the axis, orphaned beneath the month labels and attached to no line a reader could
    see; the `6%` gridline landed above the top of the canvas and was clipped away.

    The golden fingerprint was stable across every release containing this, because a
    misplaced gridline is byte-identical to itself. Only a property of the geometry
    catches it.
    """

    plot_top = CHART_TOP
    plot_bottom = CHART_HEIGHT - CHART_BOTTOM

    for series in (
        [
            PerformancePoint(month=f"2025-{index:02d}", cumulative_twr=value)
            for index, value in enumerate([0.13, 0.9, 2.4, 3.2, 4.19], start=1)
        ],
        [
            PerformancePoint(month="2025-01", cumulative_twr=-14.2),
            PerformancePoint(month="2025-02", cumulative_twr=-38.4),
            PerformancePoint(month="2025-03", cumulative_twr=18.4),
        ],
        [PerformancePoint(month="2025-01", cumulative_twr=0.0)],
    ):
        labels = _gridline_label_positions(render_performance_svg(series))
        assert labels, "the chart drew no axis labels at all"

        outside = [
            (label, y) for label, y in labels if not plot_top - 4.5 <= y <= plot_bottom + 4.5
        ]
        assert not outside, (
            f"these gridlines were drawn outside the plot rectangle "
            f"[{plot_top}, {plot_bottom}]: {outside}"
        )


def test_the_axis_ends_on_a_gridline() -> None:
    """The bounds and the ticks come from one decision, so they cannot disagree."""

    points = [
        PerformancePoint(month="2025-01", cumulative_twr=0.13),
        PerformancePoint(month="2025-02", cumulative_twr=4.19),
    ]
    low, high, ticks = _chart_axis(points)

    assert ticks[0] == low and ticks[-1] == high
    assert all(low <= tick <= high for tick in ticks), ticks


def test_a_degenerate_series_still_yields_an_axis() -> None:
    """`_nice_ticks` can return fewer than two ticks, and the axis must survive it.

    A chart with no usable span has no gridlines to end on, so the bounds fall back to
    the padded values rather than indexing an empty list.
    """

    single = [PerformancePoint(month="2025-01", cumulative_twr=0.0)]
    low, high, ticks = _chart_axis(single)

    assert low < high, "an axis with no span cannot be drawn against"
    assert len(ticks) >= 2


def test_the_step_chooser_handles_a_span_it_cannot_divide() -> None:
    """Guards on the tick-step maths, which decides every gridline on the page."""

    from app.services.portfolio_charts import _nice_step

    # No span, or nowhere to put ticks: fall back rather than divide by zero.
    assert _nice_step(0.0, 5) == 1.0
    assert _nice_step(10.0, 1) == 1.0
    # Inside the ladder, the step is the smallest 1/2/2.5/5 multiple that fits.
    assert _nice_step(100.0, 2) == 100.0
    assert _nice_step(6.0, 5) == 2.0
    # The trailing `return magnitude * 10.0` is unreachable for any finite positive span,
    # because magnitude <= rough < 10 * magnitude always satisfies the last multiplier.
    # It is left as a defensive tail rather than covered by a test that cannot reach it.
