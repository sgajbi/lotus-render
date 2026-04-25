# ruff: noqa: E501

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHART_COLORS = {
    "navy": "#0B1F33",
    "blue": "#1F5AA6",
    "teal": "#2C7A7B",
    "gold": "#C38B2E",
    "slate": "#5B6770",
    "border": "#D9E1E8",
    "soft": "#F6F8FA",
    "text": "#16202A",
    "muted": "#8A96A3",
}
ALLOCATION_PALETTE = ("#1F5AA6", "#2C7A7B", "#C38B2E", "#6B7280", "#7C5C99", "#8AA6A3")


@dataclass(frozen=True)
class PerformancePoint:
    month: str
    cumulative_twr: float
    benchmark_cumulative_twr: float | None = None


@dataclass(frozen=True)
class AllocationSlice:
    label: str
    weight_pct: float
    market_value: float
    color: str


@dataclass(frozen=True)
class ChartAssets:
    performance_svg: Path | None
    allocation_svg: Path | None


def render_portfolio_chart_assets(
    report_data: Mapping[str, object], output_dir: Path
) -> ChartAssets:
    output_dir.mkdir(parents=True, exist_ok=True)
    performance_series = performance_series_from_report_data(report_data)
    allocation_items = allocation_items_from_report_data(report_data)

    performance_path = None
    allocation_path = None
    if performance_series:
        performance_path = output_dir / "performance_12m.svg"
        performance_path.write_text(render_performance_svg(performance_series), encoding="utf-8")
    if allocation_items:
        allocation_path = output_dir / "allocation_asset_class.svg"
        allocation_path.write_text(render_allocation_donut_svg(allocation_items), encoding="utf-8")
    return ChartAssets(performance_path, allocation_path)


def performance_series_from_report_data(
    report_data: Mapping[str, object],
) -> list[PerformancePoint]:
    rows = report_data.get("performance_series") or report_data.get("performance_monthly_history")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []
    points: list[PerformancePoint] = []
    for item in rows[-12:]:
        if not isinstance(item, Mapping):
            continue
        month = str(item.get("month") or item.get("period") or "").strip()
        cumulative = _parse_percent_or_number(
            item.get("cumulative_twr") or item.get("cumulative_twr_pct")
        )
        if not month or cumulative is None:
            continue
        benchmark = _parse_percent_or_number(
            item.get("benchmark_cumulative_twr") or item.get("benchmark_cumulative_twr_pct")
        )
        points.append(
            PerformancePoint(
                month=month, cumulative_twr=cumulative, benchmark_cumulative_twr=benchmark
            )
        )
    return points


def allocation_items_from_report_data(report_data: Mapping[str, object]) -> list[AllocationSlice]:
    breakdowns = report_data.get("allocation_breakdowns")
    rows = breakdowns.get("by_asset_class") if isinstance(breakdowns, Mapping) else None
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        rows = report_data.get("allocation_items")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []

    raw_items: list[tuple[str, float, float]] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        weight = _parse_percent_or_number(item.get("weight_pct"))
        value = _parse_currency_number(item.get("market_value"))
        if not label or weight is None or weight <= 0:
            continue
        raw_items.append((label, weight, value or 0.0))
    raw_items.sort(key=lambda entry: entry[1], reverse=True)

    grouped: list[tuple[str, float, float]] = []
    other_weight = 0.0
    other_value = 0.0
    for label, weight, value in raw_items:
        if weight < 2.0 and len(raw_items) > 4:
            other_weight += weight
            other_value += value
        else:
            grouped.append((label, weight, value))
    if other_weight:
        grouped.append(("Other", other_weight, other_value))

    return [
        AllocationSlice(
            label=label,
            weight_pct=weight,
            market_value=value,
            color=ALLOCATION_PALETTE[index % len(ALLOCATION_PALETTE)],
        )
        for index, (label, weight, value) in enumerate(grouped)
    ]


def render_performance_svg(points: Sequence[PerformancePoint]) -> str:
    width = 920
    height = 260
    left = 64
    right = 28
    top = 20
    bottom = 44
    plot_width = width - left - right
    plot_height = height - top - bottom

    values = [point.cumulative_twr for point in points]
    benchmark_values = [
        point.benchmark_cumulative_twr
        for point in points
        if point.benchmark_cumulative_twr is not None
    ]
    values.extend(value for value in benchmark_values if value is not None)
    values.append(0.0)
    min_value = min(values)
    max_value = max(values)
    padding = max((max_value - min_value) * 0.15, 0.8)
    y_min = math.floor(min_value - padding)
    y_max = math.ceil(max_value + padding)
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    def x_at(index: int) -> float:
        if len(points) == 1:
            return left + plot_width / 2
        return left + (plot_width * index / (len(points) - 1))

    def y_at(value: float) -> float:
        return top + ((y_max - value) / (y_max - y_min)) * plot_height

    grid_lines = []
    for tick in _nice_ticks(y_min, y_max, 5):
        y = y_at(tick)
        stroke = CHART_COLORS["slate"] if abs(tick) < 0.0001 else CHART_COLORS["border"]
        thickness = "1.1" if abs(tick) < 0.0001 else "0.7"
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="{stroke}" stroke-width="{thickness}" opacity="0.75" />'
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" class="axis">{tick:.0f}%</text>'
        )

    portfolio_path = _polyline(
        [(x_at(index), y_at(point.cumulative_twr)) for index, point in enumerate(points)]
    )
    benchmark_points = [
        (x_at(index), y_at(point.benchmark_cumulative_twr))
        for index, point in enumerate(points)
        if point.benchmark_cumulative_twr is not None
    ]
    benchmark_path = _polyline(benchmark_points) if len(benchmark_points) >= 2 else ""

    point_markers = "\n".join(
        f'<circle cx="{x_at(index):.2f}" cy="{y_at(point.cumulative_twr):.2f}" r="4" fill="#FFFFFF" stroke="{CHART_COLORS["blue"]}" stroke-width="2" />'
        for index, point in enumerate(points)
    )
    month_labels = "\n".join(
        f'<text x="{x_at(index):.2f}" y="{height - 18}" text-anchor="middle" class="axis">{_month_label(point.month)}</text>'
        for index, point in enumerate(points)
    )
    benchmark_markup = (
        f'<path d="{benchmark_path}" fill="none" stroke="{CHART_COLORS["teal"]}" stroke-width="1.8" stroke-dasharray="6 5" opacity="0.72" />'
        if benchmark_path
        else ""
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    text {{ font-family: Arial, Helvetica, sans-serif; }}
    .axis {{ fill: {CHART_COLORS["slate"]}; font-size: 11px; }}
    .legend {{ fill: {CHART_COLORS["text"]}; font-size: 12px; font-weight: 600; }}
  </style>
  <rect width="100%" height="100%" fill="#FFFFFF" />
  {"".join(grid_lines)}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="{CHART_COLORS["border"]}" stroke-width="0.8" />
  <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="{CHART_COLORS["border"]}" stroke-width="0.8" />
  {benchmark_markup}
  <path d="{portfolio_path}" fill="none" stroke="{CHART_COLORS["blue"]}" stroke-width="2.35" stroke-linecap="round" stroke-linejoin="round" />
  {point_markers}
  {month_labels}
  <circle cx="{width - 186}" cy="24" r="4" fill="#FFFFFF" stroke="{CHART_COLORS["blue"]}" stroke-width="2" />
  <text x="{width - 174}" y="28" class="legend">Portfolio</text>
  {('<line x1="' + str(width - 92) + '" y1="24" x2="' + str(width - 62) + '" y2="24" stroke="' + CHART_COLORS["teal"] + '" stroke-width="1.8" stroke-dasharray="6 5" opacity="0.72" /><text x="' + str(width - 54) + '" y="28" class="legend">Benchmark</text>') if benchmark_path else ""}
</svg>'''


def render_allocation_donut_svg(items: Sequence[AllocationSlice]) -> str:
    width = 520
    height = 180
    cx = 132
    cy = 91
    outer = 54
    inner = 33
    total_weight = sum(item.weight_pct for item in items) or 1.0
    total_value = sum(item.market_value for item in items)
    start_angle = -90.0
    slices: list[str] = []
    for item in items:
        sweep = (item.weight_pct / total_weight) * 360.0
        end_angle = start_angle + sweep
        slices.append(_donut_segment(cx, cy, outer, inner, start_angle, end_angle, item.color))
        start_angle = end_angle

    legend = []
    for index, item in enumerate(items):
        y = 38 + index * 26
        legend.append(
            f'<rect x="340" y="{y - 9}" width="11" height="11" rx="2" fill="{item.color}" />'
            f'<text x="360" y="{y}" class="legend-label">{html.escape(item.label)}</text>'
            f'<text x="360" y="{y + 15}" class="legend-meta">{item.weight_pct:.2f}%   {_format_currency(item.market_value)}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    text {{ font-family: Arial, Helvetica, sans-serif; }}
    .center-label {{ fill: {CHART_COLORS["slate"]}; font-size: 12px; }}
    .center-value {{ fill: {CHART_COLORS["navy"]}; font-size: 17px; font-weight: 700; }}
    .legend-title {{ fill: {CHART_COLORS["navy"]}; font-size: 12px; font-weight: 700; }}
    .legend-label {{ fill: {CHART_COLORS["text"]}; font-size: 12px; font-weight: 700; }}
    .legend-meta {{ fill: {CHART_COLORS["slate"]}; font-size: 11px; }}
  </style>
  <rect width="100%" height="100%" fill="#FFFFFF" />
  {"".join(slices)}
  <circle cx="{cx}" cy="{cy}" r="{inner - 2}" fill="#FFFFFF" />
  <text x="{cx}" y="{cy - 8}" text-anchor="middle" class="center-label">Invested value</text>
  <text x="{cx}" y="{cy + 14}" text-anchor="middle" class="center-value">{_compact_value(total_value)}</text>
  <text x="340" y="20" class="legend-title">Breakdown</text>
  {"".join(legend)}
</svg>'''


def _parse_percent_or_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"not available", "n/a", "none"}:
        return None
    text = text.removesuffix("%").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_currency_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("USD", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _month_label(value: str) -> str:
    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], fmt).strftime("%b %y")
        except ValueError:
            continue
    return html.escape(value)


def _nice_ticks(y_min: float, y_max: float, count: int) -> list[float]:
    if count <= 1:
        return [y_min, y_max]
    step = (y_max - y_min) / (count - 1)
    return [y_min + step * index for index in range(count)]


def _polyline(points: Sequence[tuple[float, float]]) -> str:
    if not points:
        return ""
    first_x, first_y = points[0]
    commands = [f"M {first_x:.2f} {first_y:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return " ".join(commands)


def _point_on_circle(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def _donut_segment(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
    color: str,
) -> str:
    large_arc = 1 if end_angle - start_angle > 180 else 0
    outer_start = _point_on_circle(cx, cy, outer_radius, start_angle)
    outer_end = _point_on_circle(cx, cy, outer_radius, end_angle)
    inner_end = _point_on_circle(cx, cy, inner_radius, end_angle)
    inner_start = _point_on_circle(cx, cy, inner_radius, start_angle)
    return (
        f'<path d="M {outer_start[0]:.2f} {outer_start[1]:.2f} '
        f"A {outer_radius} {outer_radius} 0 {large_arc} 1 {outer_end[0]:.2f} {outer_end[1]:.2f} "
        f"L {inner_end[0]:.2f} {inner_end[1]:.2f} "
        f'A {inner_radius} {inner_radius} 0 {large_arc} 0 {inner_start[0]:.2f} {inner_start[1]:.2f} Z" '
        f'fill="{color}" stroke="#FFFFFF" stroke-width="2" />'
    )


def _format_currency(value: float) -> str:
    return f"{value:,.0f}"


def _compact_value(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"
