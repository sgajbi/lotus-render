# ruff: noqa: E501

from __future__ import annotations

import html
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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
    weight_pct: Decimal
    market_value: Decimal
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
    rows = _row_sequence(
        report_data.get("performance_series") or report_data.get("performance_monthly_history")
    )
    if rows is None:
        return []
    points: list[PerformancePoint] = []
    for item in rows[-12:]:
        point = _performance_point(item)
        if point is not None:
            points.append(point)
    return points


def _performance_point(item: object) -> PerformancePoint | None:
    if not isinstance(item, Mapping):
        return None
    month = str(item.get("month") or item.get("period") or "").strip()
    cumulative = _parse_percent_or_number(
        item.get("cumulative_twr") or item.get("cumulative_twr_pct")
    )
    if not month or cumulative is None:
        return None
    benchmark = _parse_percent_or_number(
        item.get("benchmark_cumulative_twr") or item.get("benchmark_cumulative_twr_pct")
    )
    return PerformancePoint(
        month=month, cumulative_twr=cumulative, benchmark_cumulative_twr=benchmark
    )


def allocation_items_from_report_data(report_data: Mapping[str, object]) -> list[AllocationSlice]:
    breakdowns = report_data.get("allocation_breakdowns")
    nested = breakdowns.get("by_asset_class") if isinstance(breakdowns, Mapping) else None
    rows = _row_sequence(nested)
    if rows is None:
        rows = _row_sequence(report_data.get("allocation_items"))
    if rows is None:
        return []

    grouped = _grouped_with_other(_parsed_allocation_entries(rows))
    return [
        AllocationSlice(
            label=label,
            weight_pct=weight,
            market_value=value,
            color=ALLOCATION_PALETTE[index % len(ALLOCATION_PALETTE)],
        )
        for index, (label, weight, value) in enumerate(grouped)
    ]


def _row_sequence(value: object) -> Sequence[object] | None:
    """Rows are a real sequence; strings and bytes must not iterate as rows."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return None


def _allocation_entry(item: object) -> tuple[str, Decimal, Decimal] | None:
    if not isinstance(item, Mapping):
        return None
    label = str(item.get("label") or item.get("name") or "").strip()
    weight = _parse_decimal_number(item.get("weight_pct"), strip_percent=True)
    if not label or weight is None or weight <= 0:
        return None
    value = _parse_currency_number(item.get("market_value"))
    return label, weight, value or Decimal("0")


def _parsed_allocation_entries(rows: Sequence[object]) -> list[tuple[str, Decimal, Decimal]]:
    entries: list[tuple[str, Decimal, Decimal]] = []
    for item in rows:
        entry = _allocation_entry(item)
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda entry: entry[1], reverse=True)
    return entries


def _grouped_with_other(
    entries: Sequence[tuple[str, Decimal, Decimal]],
) -> list[tuple[str, Decimal, Decimal]]:
    grouped: list[tuple[str, Decimal, Decimal]] = []
    other_weight = Decimal("0")
    other_value = Decimal("0")
    for label, weight, value in entries:
        if weight < Decimal("2.0") and len(entries) > 4:
            other_weight += weight
            other_value += value
        else:
            grouped.append((label, weight, value))
    if other_weight:
        grouped.append(("Other", other_weight, other_value))
    return grouped


def render_performance_svg(points: Sequence[PerformancePoint]) -> str:
    width = 920
    height = 260
    left = 64
    right = 28
    top = 20
    bottom = 44
    plot_width = width - left - right
    plot_height = height - top - bottom
    y_min, y_max = _chart_value_bounds(points)

    def x_at(index: int) -> float:
        if len(points) == 1:
            return left + plot_width / 2
        return left + (plot_width * index / (len(points) - 1))

    def y_at(value: float) -> float:
        return top + ((y_max - value) / (y_max - y_min)) * plot_height

    grid_lines = _grid_line_markup(y_min, y_max, y_at=y_at, left=left, right_edge=width - right)
    portfolio_path = _polyline(
        [(x_at(index), y_at(point.cumulative_twr)) for index, point in enumerate(points)]
    )
    point_markers = "\n".join(
        f'<circle cx="{x_at(index):.2f}" cy="{y_at(point.cumulative_twr):.2f}" r="4" fill="#FFFFFF" stroke="{CHART_COLORS["blue"]}" stroke-width="2" />'
        for index, point in enumerate(points)
    )
    month_labels = "\n".join(
        f'<text x="{x_at(index):.2f}" y="{height - 18}" text-anchor="middle" class="axis">{_month_label(point.month)}</text>'
        for index, point in enumerate(points)
    )
    benchmark_markup, benchmark_legend = _benchmark_layer(points, x_at=x_at, y_at=y_at, width=width)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    text {{ font-family: Arial, Helvetica, sans-serif; }}
    .axis {{ fill: {CHART_COLORS["slate"]}; font-size: 11px; }}
    .legend {{ fill: {CHART_COLORS["text"]}; font-size: 12px; font-weight: 600; }}
  </style>
  <rect width="100%" height="100%" fill="#FFFFFF" />
  {grid_lines}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="{CHART_COLORS["border"]}" stroke-width="0.8" />
  <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="{CHART_COLORS["border"]}" stroke-width="0.8" />
  {benchmark_markup}
  <path d="{portfolio_path}" fill="none" stroke="{CHART_COLORS["blue"]}" stroke-width="2.35" stroke-linecap="round" stroke-linejoin="round" />
  {point_markers}
  {month_labels}
  <circle cx="{width - 186}" cy="24" r="4" fill="#FFFFFF" stroke="{CHART_COLORS["blue"]}" stroke-width="2" />
  <text x="{width - 174}" y="28" class="legend">Portfolio</text>
  {benchmark_legend}
</svg>'''


def _chart_value_bounds(points: Sequence[PerformancePoint]) -> tuple[int, int]:
    """Integer axis bounds padded so the series never touches the plot edge."""
    values = [point.cumulative_twr for point in points]
    values.extend(
        point.benchmark_cumulative_twr
        for point in points
        if point.benchmark_cumulative_twr is not None
    )
    values.append(0.0)
    min_value = min(values)
    max_value = max(values)
    padding = max((max_value - min_value) * 0.15, 0.8)
    return math.floor(min_value - padding), math.ceil(max_value + padding)


def _grid_line_markup(
    y_min: float, y_max: float, *, y_at: Callable[[float], float], left: int, right_edge: int
) -> str:
    grid_lines = []
    for tick in _nice_ticks(y_min, y_max, 5):
        y = y_at(tick)
        stroke = CHART_COLORS["slate"] if abs(tick) < 0.0001 else CHART_COLORS["border"]
        thickness = "1.1" if abs(tick) < 0.0001 else "0.7"
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{right_edge}" y2="{y:.2f}" stroke="{stroke}" stroke-width="{thickness}" opacity="0.75" />'
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" class="axis">{tick:.0f}%</text>'
        )
    return "".join(grid_lines)


def _benchmark_layer(
    points: Sequence[PerformancePoint],
    *,
    x_at: Callable[[int], float],
    y_at: Callable[[float], float],
    width: int,
) -> tuple[str, str]:
    """Dashed benchmark path and its legend entry, or empty strings without one."""
    benchmark_points = [
        (x_at(index), y_at(point.benchmark_cumulative_twr))
        for index, point in enumerate(points)
        if point.benchmark_cumulative_twr is not None
    ]
    if len(benchmark_points) < 2:
        return "", ""
    benchmark_path = _polyline(benchmark_points)
    markup = f'<path d="{benchmark_path}" fill="none" stroke="{CHART_COLORS["teal"]}" stroke-width="1.8" stroke-dasharray="6 5" opacity="0.72" />'
    legend = (
        f'<line x1="{width - 92}" y1="24" x2="{width - 62}" y2="24" stroke="{CHART_COLORS["teal"]}" stroke-width="1.8" stroke-dasharray="6 5" opacity="0.72" />'
        f'<text x="{width - 54}" y="28" class="legend">Benchmark</text>'
    )
    return markup, legend


def render_allocation_donut_svg(items: Sequence[AllocationSlice]) -> str:
    width = 520
    height = 180
    cx = 132
    cy = 91
    outer = 54
    inner = 33
    total_weight = sum((item.weight_pct for item in items), Decimal("0")) or Decimal("1.0")
    total_value = sum((item.market_value for item in items), Decimal("0"))
    start_angle = -90.0
    slices: list[str] = []
    for item in items:
        sweep = float((item.weight_pct / total_weight) * Decimal("360.0"))
        end_angle = start_angle + sweep
        slices.append(_donut_segment(cx, cy, outer, inner, start_angle, end_angle, item.color))
        start_angle = end_angle

    legend = []
    for index, item in enumerate(items):
        y = 38 + index * 26
        legend.append(
            f'<rect x="340" y="{y - 9}" width="11" height="11" rx="2" fill="{item.color}" />'
            f'<text x="360" y="{y}" class="legend-label">{html.escape(item.label)}</text>'
            f'<text x="360" y="{y + 15}" class="legend-meta">{_format_decimal(item.weight_pct)}%   {_format_currency(item.market_value)}</text>'
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
        parsed = float(text)
    except ValueError:
        return None
    # nan/inf would crash the chart bounds (math.floor(nan) / math.ceil(inf));
    # treat non-finite as absent so the chart degrades instead of failing the render.
    return parsed if math.isfinite(parsed) else None


def _parse_currency_number(value: object) -> Decimal | None:
    return _parse_decimal_number(value, strip_percent=False)


def _parse_decimal_number(value: object, *, strip_percent: bool) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("USD", "").strip()
    if strip_percent:
        text = text.removesuffix("%").strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    # Decimal("NaN")/("Infinity") construct fine but signal InvalidOperation on the
    # first comparison downstream, stranding the render; treat non-finite as absent.
    return parsed if parsed.is_finite() else None


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


def _format_currency(value: Decimal) -> str:
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,.0f}"


def _compact_value(value: Decimal | int) -> str:
    decimal_value = Decimal(value)
    absolute = abs(decimal_value)
    if absolute >= Decimal("1000000"):
        return f"{_format_one_decimal(decimal_value / Decimal('1000000'))}M"
    if absolute >= Decimal("1000"):
        return f"{_format_one_decimal(decimal_value / Decimal('1000'))}K"
    return _format_currency(decimal_value)


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _format_one_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):,.1f}"
