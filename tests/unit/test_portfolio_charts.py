from decimal import Decimal
from pathlib import Path

from app.services.portfolio_charts import (
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
