"""The rolling-risk trend band: "is this portfolio's risk changing?", stated only.

The joint design (render#160 + report#255) settled the contract this module renders:
``report_data.risk_trend`` carries a window stated verbatim, per-metric posture, and
for ready metrics a source-owned series of ``{date, value}`` points. Render places,
scales, and states -- it derives nothing:

- The chart is a **date-proportional dot strip**: every source point is a dot placed
  by its own date and value, and nothing connects them. A hole in the source series
  is empty space on the page -- visible exactly in proportion to its duration --
  with no interpolation, no cadence heuristic, and no line bridging what the source
  did not state. Values are parsed only to place dots; what the reader can quote
  are the first and last values, printed verbatim at source precision.
- Posture is stated in the source's own words: an ``unavailable`` metric prints its
  note (the #241 voice for a benchmark the source could not apply), an ``empty``
  one prints why the source excluded it, and a ready series that this module cannot
  honestly place (fewer than two points, an unparseable or non-finite value, a
  broken date) is said to be undrawable -- fail-visible, never invented.
- No trend verdicts, deltas, or min/max: the source states or nobody does
  (`trend_statement` is source-owned or absent, and the source states none today).

The geometry lives here in Python where it is unit-tested; the Typst side places
what this emits and decides nothing (the chart_geometry precedent). The dot strip
itself is wrapped as a PDF artifact -- the printed endpoints carry the semantics in
the tag tree, per the #246 discipline.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date

from app.services.typst_values import escape_typst_string

#: Presentation names for the metric ids the producer emits today. An id this map
#: does not know is printed verbatim -- a made-up pretty name would claim knowledge
#: of a metric this module does not have.
_METRIC_LABELS = {
    "ROLLING_VOLATILITY": "Rolling volatility",
    "ROLLING_BETA": "Rolling beta",
    "ROLLING_TRACKING_ERROR": "Rolling tracking error",
}

#: Height of the dot strip's drawing band, in points.
_BAND_HEIGHT = 20.0
#: Vertical inset so an extreme dot is not clipped by the band edge.
_BAND_INSET = 2.0


def render_risk_trend_panel(report_data: Mapping[str, object]) -> str:
    """The trend band as Typst markup, or empty when the report did not order it."""
    trend = report_data.get("risk_trend")
    if not isinstance(trend, Mapping) or not trend:
        return ""
    rows = [_metric_row(metric) for metric in _metric_mappings(trend.get("metrics"))]
    if not rows:
        return ""
    caption = _window_caption(trend.get("window"))
    lines = [
        "#v(12pt)",
        '#section-subtitle("Risk trend")',
    ]
    if caption:
        lines.append(f"#text(size: text-micro, fill: slate)[{caption}]")
    lines.append("#v(6pt)")
    lines.extend(rows)
    return "\n".join(lines)


def _metric_mappings(metrics: object) -> list[Mapping[str, object]]:
    if not isinstance(metrics, Sequence) or isinstance(metrics, str):
        return []
    return [metric for metric in metrics if isinstance(metric, Mapping)]


def _window_caption(window: object) -> str:
    """The window stated verbatim -- a trend without its window is not interpretable."""
    if not isinstance(window, Mapping):
        return ""
    parts: list[str] = []
    observations = window.get("window_observations")
    if isinstance(observations, int) and not isinstance(observations, bool):
        parts.append(f"{observations}-observation rolling window")
    frequency = window.get("frequency")
    if isinstance(frequency, str) and frequency.strip():
        parts.append(escape_typst_string(frequency.strip()))
    period_part = _period_caption(window.get("period"))
    if period_part:
        parts.append(period_part)
    return " · ".join(parts)


def _period_caption(period: object) -> str:
    if not isinstance(period, Mapping):
        return ""
    pieces: list[str] = []
    name = period.get("name")
    if isinstance(name, str) and name.strip():
        pieces.append(escape_typst_string(name.strip()))
    span = " to ".join(
        escape_typst_string(value.strip())
        for value in (period.get("start_date"), period.get("end_date"))
        if isinstance(value, str) and value.strip()
    )
    if span:
        pieces.append(span)
    return " ".join(pieces)


def _metric_row(metric: Mapping[str, object]) -> str:
    label = _metric_label(metric.get("metric"))
    posture = metric.get("posture")
    if posture == "ready":
        return _ready_row(label, metric)
    # The source's quality flags are facts about the refusal too, not only about
    # a drawn series.
    return _stated_row(label, _posture_statement(posture, metric)) + _quality_flags_note(metric)


def _metric_label(metric_id: object) -> str:
    if not isinstance(metric_id, str) or not metric_id.strip():
        return "Unnamed metric"
    return _METRIC_LABELS.get(metric_id, escape_typst_string(metric_id))


def _ready_row(label: str, metric: Mapping[str, object]) -> str:
    points = _placeable_points(metric.get("series"))
    if points is None:
        return _stated_row(
            label,
            "The series could not be drawn from what the source supplied.",
        )
    dots = _dot_markup(points)
    first_value = escape_typst_string(points[0][2])
    last_value = escape_typst_string(points[-1][2])
    row = (
        "#grid(\n"
        "  columns: (110pt, 1fr, 92pt),\n"
        "  column-gutter: 10pt,\n"
        "  align: horizon,\n"
        f"  [#text(size: text-body, fill: ink)[{label}]],\n"
        "  [#pdf.artifact(block(\n"
        f"    width: 100%, height: {_BAND_HEIGHT + 2 * _BAND_INSET:.0f}pt,\n"
        "    fill: mist, radius: 3pt,\n"
        f"  )[{dots}])],\n"
        "  [#align(right)[#text(size: text-micro, fill: slate)"
        f"[{first_value} #sym.arrow.r ]#text(size: text-micro, weight: 500, fill: ink)"
        f"[{last_value}]]],\n"
        ")"
    )
    flags = _quality_flags_note(metric)
    return row + flags


def _stated_row(label: str, statement: str) -> str:
    return (
        "#grid(\n"
        "  columns: (110pt, 1fr),\n"
        "  column-gutter: 10pt,\n"
        f"  [#text(size: text-body, fill: ink)[{label}]],\n"
        f"  [#text(size: text-micro, fill: slate)[{statement}]],\n"
        ")"
    )


def _posture_statement(posture: object, metric: Mapping[str, object]) -> str:
    reason = _first_note_message(metric)
    if posture == "empty":
        prefix = "Not included"
    elif posture == "unavailable":
        prefix = "Not available"
    else:
        return "The source stated no posture for this series."
    return f"{prefix} — {reason}" if reason else f"{prefix}."


def _first_note_message(metric: Mapping[str, object]) -> str:
    notes = metric.get("notes")
    if not isinstance(notes, Sequence):
        return ""
    for note in notes:
        if isinstance(note, Mapping):
            message = note.get("message")
            if isinstance(message, str) and message.strip():
                return escape_typst_string(message.strip())
    return ""


def _quality_flags_note(metric: Mapping[str, object]) -> str:
    flags = metric.get("quality_flags")
    if not isinstance(flags, Sequence) or isinstance(flags, str):
        return ""
    stated = [
        escape_typst_string(flag.strip())
        for flag in flags
        if isinstance(flag, str) and flag.strip()
    ]
    if not stated:
        return ""
    joined = ", ".join(stated)
    return (
        "\n#grid(\n  columns: (110pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
        f"  [#text(size: text-micro, fill: slate)[Source quality flags: {joined}]],\n)"
    )


def _placeable_points(series: object) -> list[tuple[float, float, str]] | None:
    """(x fraction, y fraction from top, verbatim value) per point, or None.

    None means the series cannot be honestly placed: fewer than two points, a
    date or value the source's own format does not parse, a non-finite value,
    or dates out of order (a trend whose axis runs backwards is not a trend).
    Values are parsed ONLY to position dots; nothing derived is ever printed.
    """
    if not isinstance(series, Sequence) or isinstance(series, str) or len(series) < 2:
        return None
    parsed: list[tuple[date, float, str]] = []
    for point in series:
        entry = _parsed_point(point)
        if entry is None:
            return None
        parsed.append(entry)
    return _normalized(parsed)


def _parsed_point(point: object) -> tuple[date, float, str] | None:
    if not isinstance(point, Mapping):
        return None
    raw_date = point.get("date")
    stated = point.get("value")
    if not isinstance(raw_date, str) or not isinstance(stated, str):
        return None
    try:
        when = date.fromisoformat(raw_date)
        # A risk ratio, parsed only to place a dot -- never monetary, never
        # re-printed: what the page quotes is the verbatim source string.
        magnitude = float(stated)
    except ValueError:
        return None
    if not math.isfinite(magnitude):
        return None
    return (when, magnitude, stated)


def _normalized(parsed: list[tuple[date, float, str]]) -> list[tuple[float, float, str]] | None:
    dates = [when for when, _, _ in parsed]
    if dates != sorted(dates) or dates[0] == dates[-1]:
        return None
    span_days = (dates[-1] - dates[0]).days
    low = min(magnitude for _, magnitude, _ in parsed)
    high = max(magnitude for _, magnitude, _ in parsed)
    magnitude_span = high - low
    points: list[tuple[float, float, str]] = []
    for when, magnitude, raw in parsed:
        x = (when - dates[0]).days / span_days
        # A flat series sits on the centre line: equal magnitudes, equal heights.
        y = 0.5 if magnitude_span == 0 else (high - magnitude) / magnitude_span
        points.append((x, y, raw))
    return points


def _dot_markup(points: Sequence[tuple[float, float, str]]) -> str:
    dots = []
    for x, y, _ in points:
        dy = _BAND_INSET + y * _BAND_HEIGHT
        dots.append(
            f"#place(dx: {x * 100:.2f}% - 0.9pt, dy: {dy:.2f}pt, circle(radius: 0.9pt, fill: ink))"
        )
    return "".join(dots)
