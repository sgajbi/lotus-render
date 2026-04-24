from pathlib import Path

from app.services.portfolio_charts import (
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
    assert items[-1].weight_pct == 2.5
    assert items[-1].market_value == 250


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
