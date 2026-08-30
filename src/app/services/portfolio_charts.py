# ruff: noqa: E501

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.number_format import format_money
from app.services.typst_values import row_sequence

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
# The 12-month chart's canvas. Named rather than inline so a test can state the
# invariant that every gridline the chart emits falls inside the plot rectangle.
CHART_WIDTH = 920
CHART_HEIGHT = 260
CHART_LEFT = 64
CHART_RIGHT = 28
CHART_TOP = 20
CHART_BOTTOM = 44
CHART_TICK_COUNT = 5

LEGEND_TOP = 38
LEGEND_ROW_HEIGHT = 26
LEGEND_BOTTOM_MARGIN = 12


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
    """Write the SVG assets a document still needs.

    Only the allocation donut remains. The performance chart is drawn natively in Typst
    (`chart_geometry` plus `_charts.typ`), so it needs no asset and no longer carries the
    `<text>` elements that put it on typst#6783. The donut is the next one (#150).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    allocation_items = allocation_items_from_report_data(report_data)

    allocation_path = None
    if allocation_items:
        allocation_path = output_dir / "allocation_asset_class.svg"
        allocation_path.write_text(render_allocation_donut_svg(allocation_items), encoding="utf-8")
    return ChartAssets(performance_svg=None, allocation_svg=allocation_path)


def performance_series_from_report_data(
    report_data: Mapping[str, object],
) -> list[PerformancePoint]:
    rows = row_sequence(
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
    rows = row_sequence(nested)
    if rows is None:
        rows = row_sequence(report_data.get("allocation_items"))
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


def _chart_axis(points: Sequence[PerformancePoint]) -> tuple[float, float, list[float]]:
    """Axis bounds and gridlines decided together, so every tick lands inside the plot.

    They used to be derived independently and disagreed by construction:
    :func:`_chart_value_bounds` rounds outward to integers, :func:`_nice_ticks` rounds
    outward to its own step, and the two only coincide when the padded bound happens to
    be a multiple of that step. On the golden series -- bounds (-1, 5), ticks
    [-2, 0, 2, 4, 6] -- two of the five gridlines fell outside the plot: the `-2%` label
    rendered 32px below the axis, orphaned under the month labels, and the `6%` gridline
    landed above the top of the canvas and was clipped away entirely.

    Ending the axis on the outermost tick removes the disagreement rather than clamping
    it away, and is the usual convention: the plot runs exactly from one gridline to
    another.
    """
    low, high = _chart_value_bounds(points)
    ticks = _nice_ticks(low, high, CHART_TICK_COUNT)
    if len(ticks) < 2:
        return float(low), float(high), [float(low), float(high)]
    return ticks[0], ticks[-1], ticks


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


def render_allocation_donut_svg(items: Sequence[AllocationSlice]) -> str:
    width = 520
    # The legend lists one row per slice at LEGEND_ROW_HEIGHT apart. A fixed 180pt canvas
    # dropped every row past the fifth off the bottom, silently - and the palette wraps at
    # six, so a seven-category allocation lost legend entries it had colours for. Grow the
    # canvas to fit what there is instead.
    height = max(180, LEGEND_TOP + LEGEND_ROW_HEIGHT * len(items) + LEGEND_BOTTOM_MARGIN)
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
        y = LEGEND_TOP + index * LEGEND_ROW_HEIGHT
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


def _nice_step(span: float, count: int) -> float:
    """The smallest 1/2/2.5/5 x 10^n step that fits the span in `count` gridlines."""
    if span <= 0 or count <= 1:
        return 1.0
    rough = span / (count - 1)
    magnitude = 10.0 ** math.floor(math.log10(rough))
    for multiplier in (1.0, 2.0, 2.5, 5.0, 10.0):
        if rough <= magnitude * multiplier:
            return magnitude * multiplier
    return magnitude * 10.0


def _nice_ticks(y_min: float, y_max: float, count: int) -> list[float]:
    """Gridlines at round multiples, so a line labelled 0% is actually at zero.

    Interpolating linearly between the bounds put ticks at arbitrary values and then
    printed them with no decimals: a series of 12-45% produced gridlines labelled
    -7%, 8%, 22%, 37%, 52%, and a line labelled "0%" sat at +0.5. On a performance
    chart that is not a cosmetic problem - the axis was misstating the numbers.
    """
    if count <= 1:
        return [y_min, y_max]
    step = _nice_step(y_max - y_min, count)
    first = math.floor(y_min / step) * step
    ticks: list[float] = []
    tick = first
    while tick <= y_max + step * 0.5:
        # Snap values that are zero to within floating error, so the baseline test and
        # the printed label agree on which line is the zero line.
        ticks.append(0.0 if abs(tick) < step * 1e-9 else tick)
        tick += step
    return ticks


def _point_on_circle(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def _donut_ring(cx: float, cy: float, outer_radius: float, inner_radius: float, color: str) -> str:
    """A closed ring, for the case where one slice is the whole circle."""
    return (
        f'<path d="M {cx - outer_radius:.2f} {cy:.2f} '
        f"a {outer_radius} {outer_radius} 0 1 0 {outer_radius * 2} 0 "
        f"a {outer_radius} {outer_radius} 0 1 0 {-outer_radius * 2} 0 Z "
        f"M {cx - inner_radius:.2f} {cy:.2f} "
        f"a {inner_radius} {inner_radius} 0 1 1 {inner_radius * 2} 0 "
        f'a {inner_radius} {inner_radius} 0 1 1 {-inner_radius * 2} 0 Z" '
        f'fill="{color}" fill-rule="evenodd" stroke="#FFFFFF" stroke-width="2" />'
    )


def _donut_segment(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
    color: str,
) -> str:
    sweep = end_angle - start_angle
    if sweep >= 359.999:
        # A single 100% holding: start and end coincide, and SVG omits an arc whose
        # endpoints are identical, so the donut rendered blank. Draw it as a ring.
        return _donut_ring(cx, cy, outer_radius, inner_radius, color)
    large_arc = 1 if sweep > 180 else 0
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
    return format_money(value, decimals=0)


def _compact_value(value: Decimal | int) -> str:
    decimal_value = Decimal(value)
    absolute = abs(decimal_value)
    if absolute >= Decimal("1000000"):
        return f"{_format_one_decimal(decimal_value / Decimal('1000000'))}M"
    if absolute >= Decimal("1000"):
        return f"{_format_one_decimal(decimal_value / Decimal('1000'))}K"
    return _format_currency(decimal_value)


def _format_decimal(value: Decimal) -> str:
    return format_money(value, decimals=2)


def _format_one_decimal(value: Decimal) -> str:
    return format_money(value, decimals=1)
