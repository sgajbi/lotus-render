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

from dataclasses import dataclass

from app.services.portfolio_charts import PerformancePoint, _chart_axis, _month_label

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
