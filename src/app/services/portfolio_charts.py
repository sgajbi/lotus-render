"""Read a chart's inputs out of governed report data, and decide its axis.

This module used to build SVG. Both charts are now drawn natively in Typst, so what is
left is the part that was always the interesting half: turning `report_data` into series
and slices, and choosing an axis whose ticks a reader can trust. `chart_geometry` turns
these into positions; `_charts.typ` draws them.

The `# ruff: noqa: E501` that used to head this file went with the SVG string literals.
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.services.typst_values import row_sequence

# Series names, not colours: what they look like is decided in `_design.typ` with the
# rest of the document's palette. Six is the whole palette, and `_grouped_with_other`
# holds the slice count to it, so the index into it needs no modulo. It used to have
# one, and the comment here claimed the grouping folded everything past the fifth
# slice -- it folded everything under 2%, so a seventh slice above 2% took `series-1`
# back from the first.
ALLOCATION_PALETTE = (
    "series-1",
    "series-2",
    "series-3",
    "series-4",
    "series-5",
    "series-6",
)
# How many gridlines the axis aims for. `_nice_ticks` may return one more or one fewer,
# because it rounds to a round step rather than to a count.
CHART_TICK_COUNT = 5


@dataclass(frozen=True)
class PerformancePoint:
    month: str
    cumulative_twr: float
    benchmark_cumulative_twr: float | None = None


@dataclass(frozen=True)
class AllocationSlice:
    """One wedge of the donut, and the one legend row beside it.

    Both are drawn from the same list and joined only by position, so a slice the ring
    declines to draw leaves a legend row naming nothing. The ring declined exactly one
    thing -- a wedge with no sweep, which is a hairline at the twelve o'clock seam --
    so that is refused here instead, where it is a fact about the slice rather than a
    decision taken halfway down the drawing.
    """

    label: str
    weight_pct: Decimal
    market_value: Decimal
    color: str

    def __post_init__(self) -> None:
        if self.weight_pct <= 0:
            raise ValueError(
                f"{self.label!r} has weight {self.weight_pct}: a slice with no sweep "
                "draws a hairline and a legend row pointing at nothing."
            )


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
            color=ALLOCATION_PALETTE[index],
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


# A slice under this is a hairline the eye cannot separate from the seam beside it. It
# only applies once there are enough slices for that to be crowding: four or fewer, and
# a 1% slice has the room to be itself.
NAMEABLE_SLICE_PCT = Decimal("2.0")
UNCROWDED_SLICE_COUNT = 4


def _nameable_count(entries: Sequence[tuple[str, Decimal, Decimal]]) -> int:
    """How many of the leading slices the donut can name.

    Both cuts land on a prefix because the entries are sorted largest first. The second
    is the palette bound, and it takes a colour back whenever anything will be folded,
    because "Other" needs one too.
    """
    named = len(entries)
    if len(entries) > UNCROWDED_SLICE_COUNT:
        named = sum(1 for _, weight, _ in entries if weight >= NAMEABLE_SLICE_PCT)
    if named < len(entries) or named > len(ALLOCATION_PALETTE):
        return min(named, len(ALLOCATION_PALETTE) - 1)
    return named


def _grouped_with_other(
    entries: Sequence[tuple[str, Decimal, Decimal]],
) -> list[tuple[str, Decimal, Decimal]]:
    """The slices the donut can name, with everything else summed into "Other".

    Two things stop a slice being nameable and both end in the same place: it can be too
    small to see, and it can be past the end of the palette. Colour is the only key a
    donut has, so the count is held to `ALLOCATION_PALETTE` -- and "Other" takes a
    colour of its own, so whenever anything is folded there is one fewer to give out.

    Entries arrive sorted largest first, so both rules cut at a prefix and what gets
    folded is always the tail. Which is what "Other" means. Nothing is lost from the
    document: the allocation breakdown below itemises every row in full.
    """
    named = _nameable_count(entries)
    grouped = list(entries[:named])
    folded = entries[named:]
    if folded:
        grouped.append(
            (
                "Other",
                sum((weight for _, weight, _ in folded), Decimal("0")),
                sum((value for _, _, value in folded), Decimal("0")),
            )
        )
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
