"""Turn a performance series into plot-box fractions a Typst chart can place.

The chart used to be assembled here as an SVG string. Three problems came with that, and
all three are removed by emitting geometry instead of markup:

- An SVG containing ``<text>`` sits on an open Typst non-determinism bug (typst#6783),
  and the performance chart emitted nine text elements.
- The chrome went wrong quietly. #152 shipped two of five gridlines outside the plot,
  and the byte-identical golden was green over it for as long as it existed.
- An SVG carries its own fonts and colours, so it cannot inherit the design system. That
  is how the palette came to hold four values of ``accent``.

The arithmetic stays here, in Python, where it is unit-tested. The Typst side places what
this produces and decides nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from app.services.portfolio_charts import (
    AllocationSlice,
    PerformancePoint,
    _chart_axis,
    _month_label,
)

# How near the zero line a tick has to be before it *is* the zero line. The axis is in
# percent and ticks are chosen on a round step, so this only ever catches exact zero and
# floating-point noise around it.
ZERO_TOLERANCE = 1e-9


@dataclass(frozen=True)
class ChartGridline:
    """One horizontal rule, as a fraction of the plot height from the top."""

    label: str
    at: float
    zero: bool


@dataclass(frozen=True)
class ChartPoint:
    """One observation, as fractions of the plot box."""

    at: float
    value: float


@dataclass(frozen=True)
class ChartLabel:
    """One x-axis label, positioned by the same fraction as its observation."""

    text: str
    at: float


@dataclass(frozen=True)
class ChartGeometry:
    gridlines: list[ChartGridline]
    points: list[ChartPoint]
    labels: list[ChartLabel]
    benchmark: list[ChartPoint]


def _fraction_across(index: int, count: int) -> float:
    """Where an observation sits left to right. A single point sits in the middle."""
    if count <= 1:
        return 0.5
    return index / (count - 1)


def _fraction_down(value: float, low: float, high: float) -> float:
    """Where a value sits top to bottom, with the axis top at 0.

    The axis ends on its outermost ticks, so a value inside the series is inside [0, 1]
    by construction. It is clamped anyway: a caller that ever hands over an out-of-range
    value should get a mark on the plot edge rather than one drawn outside it, which is
    the defect #152 was.
    """
    if high <= low:
        return 0.5
    return min(max((high - value) / (high - low), 0.0), 1.0)


def performance_chart_geometry(points: list[PerformancePoint]) -> ChartGeometry | None:
    """Plot-box fractions for a cumulative performance series, or None when empty."""
    if not points:
        return None

    low, high, ticks = _chart_axis(points)
    count = len(points)

    gridlines = [
        ChartGridline(
            label=f"{tick:.0f}%",
            at=_fraction_down(tick, low, high),
            zero=abs(tick) < ZERO_TOLERANCE,
        )
        for tick in ticks
    ]
    plotted = [
        ChartPoint(
            at=_fraction_across(index, count), value=_fraction_down(point.cumulative_twr, low, high)
        )
        for index, point in enumerate(points)
    ]
    labels = [
        ChartLabel(text=_month_label(point.month), at=_fraction_across(index, count))
        for index, point in enumerate(points)
    ]
    benchmark = [
        ChartPoint(
            at=_fraction_across(index, count),
            value=_fraction_down(point.benchmark_cumulative_twr, low, high),
        )
        for index, point in enumerate(points)
        if point.benchmark_cumulative_twr is not None
    ]
    # A single benchmark observation is a dot with no line; two are the minimum that can
    # say anything about direction, which is the only reason the series is drawn.
    if len(benchmark) < 2:
        benchmark = []

    return ChartGeometry(gridlines=gridlines, points=plotted, labels=labels, benchmark=benchmark)


# A circular arc is approximated by cubic Béziers, one per quarter turn or less. The
# control-point distance below is the standard constant for that approximation.
#
# Measured across sweeps of 30, 90, 180, 216 and 359 degrees: the worst radial error is
# 1.4e-4 of the unit box, about three parts in ten thousand of the radius, which at a
# 54pt donut is 0.015pt -- roughly a fiftieth of a dot at 300dpi. Splitting at 90 deg
# rather than fitting one curve to a whole slice is what keeps that true for a slice of
# any size; a single cubic across 216 deg is visibly not a circle.
MAX_ARC_SEGMENT_RADIANS = math.pi / 2


@dataclass(frozen=True)
class DonutSegment:
    """One slice, as a closed path in a unit box with the centre at (0.5, 0.5).

    The path is emitted as Typst curve commands rather than as coordinates alone,
    because a donut slice is an outer arc, a radial line, an inner arc back, and a
    close -- and which is which cannot be recovered from a list of points.
    """

    colour: str
    commands: list[tuple[str, tuple[float, ...]]]


def _point(angle: float, radius: float) -> tuple[float, float]:
    """A point on a circle centred in the unit box. Angles run clockwise from twelve."""
    return (0.5 + radius * math.sin(angle), 0.5 - radius * math.cos(angle))


def _arc_commands(start: float, end: float, radius: float) -> list[tuple[str, tuple[float, ...]]]:
    """Cubic segments tracing an arc, split so no segment exceeds a quarter turn."""
    commands: list[tuple[str, tuple[float, ...]]] = []
    span = end - start
    steps = max(1, math.ceil(abs(span) / MAX_ARC_SEGMENT_RADIANS))
    step = span / steps
    handle = 4.0 / 3.0 * math.tan(step / 4.0) * radius
    for index in range(steps):
        segment_start = start + step * index
        segment_end = segment_start + step
        x0, y0 = _point(segment_start, radius)
        x1, y1 = _point(segment_end, radius)
        # Tangents at the endpoints, in the same clockwise-from-twelve frame.
        c0 = (x0 + handle * math.cos(segment_start), y0 + handle * math.sin(segment_start))
        c1 = (x1 - handle * math.cos(segment_end), y1 - handle * math.sin(segment_end))
        commands.append(("cubic", (c0[0], c0[1], c1[0], c1[1], x1, y1)))
    return commands


# The unfilled remainder of a breakdown that does not add up to the whole portfolio.
# `rule`, so it reads as an absence against the palette rather than as a sixth holding.
UNCHARTED_COLOUR = "#D9E1E8"


def _ring_commands(
    start: float, end: float, outer: float, inner: float
) -> list[tuple[str, tuple[float, ...]]]:
    """One wedge of a ring: out along the outer arc, in, back along the inner arc."""
    commands: list[tuple[str, tuple[float, ...]]] = [("move", _point(start, outer))]
    commands.extend(_arc_commands(start, end, outer))
    commands.append(("line", _point(end, inner)))
    commands.extend(_arc_commands(end, start, inner))
    commands.append(("close", ()))
    return commands


def donut_segments(
    slices: list[AllocationSlice], *, outer: float = 0.5, inner: float = 0.3
) -> list[DonutSegment]:
    """Closed paths for an allocation donut, in a unit box.

    Weights are shares of the whole portfolio, so they sweep against a full circle and
    not against their own sum. Renormalising is the tempting alternative and it makes
    the ring contradict the labels printed beside it: the golden package's slices cover
    89.64%, and dividing by that drew Equity as 67% of the ring under a legend reading
    60.00%. Whatever is left over is drawn as an uncharted remainder, so the shortfall
    the coverage note describes is also visible.

    Weights that overshoot a full circle are renormalised, because slices that overlap
    are worse than slices that are individually understated.

    A slice that rounds to no sweep is dropped rather than drawn: a zero-width wedge
    contributes a hairline artefact at the twelve o'clock seam and nothing else.
    """
    total = sum((item.weight_pct for item in slices), Decimal("0"))
    if total <= 0:
        return []
    whole = max(total, Decimal("100"))

    segments: list[DonutSegment] = []
    angle = 0.0
    for item in slices:
        sweep = float(item.weight_pct / whole) * math.tau
        if sweep <= 0:
            continue
        end = angle + sweep
        commands = _ring_commands(angle, end, outer, inner)
        segments.append(DonutSegment(colour=item.color, commands=commands))
        angle = end

    remainder = math.tau - angle
    if remainder > ZERO_TOLERANCE:
        segments.append(
            DonutSegment(
                colour=UNCHARTED_COLOUR, commands=_ring_commands(angle, math.tau, outer, inner)
            )
        )
    return segments
