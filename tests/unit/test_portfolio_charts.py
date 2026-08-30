from decimal import Decimal

from app.services.chart_geometry import performance_chart_geometry
from app.services.portfolio_charts import (
    PerformancePoint,
    _chart_axis,
    _chart_value_bounds,
    _nice_ticks,
    _parse_currency_number,
    _parse_percent_or_number,
    allocation_items_from_report_data,
    performance_series_from_report_data,
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
    # Geometry must compute over the finite point without raising.
    geometry = performance_chart_geometry(series)
    assert geometry is not None and len(geometry.points) == 1


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


def test_every_tick_lies_within_the_axis_bounds() -> None:
    """#152's actual invariant: the bounds and the ticks come from one decision.

    They used to be derived independently -- `_chart_value_bounds` rounding outward to
    integers, `_nice_ticks` rounding outward to its own step -- so on the golden series
    the axis ran [-1, 5] while the ticks ran [-2 … 6], and two gridlines were drawn
    outside the plot.

    This is asserted on the values rather than on the drawn fractions because the native
    chart clamps a fraction into the plot box: under the old derivation the out-of-range
    ticks would land stacked on the plot edges instead of outside it, which is less
    obviously broken and just as wrong.
    """

    for values in ([0.13, 0.9, 2.4, 3.2, 4.19], [-14.2, -38.4, 18.4], [0.0], [2.5, 2.5]):
        series = [
            PerformancePoint(month=f"2025-{index + 1:02d}", cumulative_twr=value)
            for index, value in enumerate(values)
        ]
        low, high, ticks = _chart_axis(series)
        outside = [tick for tick in ticks if not low <= tick <= high]
        assert not outside, f"ticks outside the axis {low}..{high}: {outside}"
        assert ticks[0] == low and ticks[-1] == high, (
            "the axis must end on its outermost ticks, or the plot runs past the last "
            f"gridline: axis {low}..{high}, ticks {ticks[0]}..{ticks[-1]}"
        )


def test_month_labels_accept_both_date_shapes_and_pass_anything_else_through() -> None:
    """Producers send `2026-01` and `2026-01-15`; a label is a client-visible string.

    Anything that parses as neither is escaped rather than dropped: a month nobody can
    format is still a fact about the series, and a blank axis label would be a worse
    answer than an odd one.
    """

    from app.services.portfolio_charts import _month_label

    assert _month_label("2026-01") == "Jan 26"
    assert _month_label("2026-01-15") == "Jan 26"
    assert _month_label("Q1") == "Q1"
    assert _month_label("a<b") == "a&lt;b"
