"""The rolling-risk trend band: "is this portfolio's risk changing?", stated only.

The joint design (render#160 + report#255) settled the contract this module renders;
the 2026-09-04 steering corrected two semantics before external publication:

- **Units come from the source, or the number is not stated.** lotus-risk's rolling
  volatility and tracking error are annualized decimal ratios (0.1374 means 13.74%),
  while beta is unitless. The producer states each metric's ``unit``
  (``decimal_ratio`` or ``unitless``); Render formats the reader value from that
  semantic -- an exact decimal shift, never a float, never a hard-coded
  metric-specific multiplier -- and a ready series that arrives without unit
  semantics is fail-visible, because printing ``0.1374`` where the reader means
  13.74% is a wrong statement with confident typography. The raw source strings
  stay untouched in the series for lineage and geometry.

- **The strip is the ordered observation sequence, not a calendar.** Dots are placed
  by observation index: a Friday-to-Monday interval is normal trading cadence, not
  missing evidence, and calendar-proportional spacing was inferring data quality
  from weekends. Render does not invent missing dates and nothing connects the
  dots; coverage is communicated by facts instead -- each drawn strip states its
  observation count and observed first/last dates beside the window caption, so a
  warm-up or partial series is visibly narrower than the stated period without any
  spatial guessing. Genuine gap evidence, if a source ever states it, arrives as
  source facts (notes/quality flags), which are printed.

- **The scale convention is stated.** Each strip is independently normalized to its
  own observed range -- right for a compact trend, misleading if unsaid, so the
  band states it once: independent scales, endpoint figures show the actual level.
  Render owns no thresholds and no reference levels.

Posture stays in the source's words (#241 voice for benchmark refusals; ``empty``
prints why the source excluded a series), and no verdicts exist anywhere:
``trend_statement`` is source-owned or absent, and the source states none today.
The geometry lives here in Python where it is unit-tested; the Typst side places
what this emits and decides nothing. The dot strip itself is a PDF artifact -- the
printed endpoints carry the semantics in the tag tree, per the #246 discipline.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

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

_SCALE_STATEMENT = (
    "Each trend strip is independently scaled; the endpoint figures show the actual level."
)


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
    if any("circle(" in row for row in rows):
        # The convention is stated only where a strip was actually drawn.
        lines.append("#v(4pt)")
        lines.append(f"#text(size: text-micro, fill: slate)[{_SCALE_STATEMENT}]")
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
    unit = metric.get("unit")
    if not isinstance(unit, str) or unit not in ("decimal_ratio", "unitless"):
        # A number without its unit is not a statement a reader can use: 0.1374
        # printed bare where the meaning is 13.74% would be confidently wrong.
        return _stated_row(
            label,
            "The series arrived without unit semantics and is not stated.",
        )
    points = _placeable_points(metric.get("series"))
    if points is None:
        return _stated_row(
            label,
            "The series could not be drawn from what the source supplied.",
        )
    first_value = _reader_value(points[0][2], unit)
    last_value = _reader_value(points[-1][2], unit)
    if first_value is None or last_value is None:
        return _stated_row(
            label,
            "The series could not be drawn from what the source supplied.",
        )
    dots = _dot_markup(points)
    row = (
        "#grid(\n"
        "  columns: (110pt, 1fr, 100pt),\n"
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
    return row + _coverage_note(points) + _quality_flags_note(metric)


def _reader_value(stated: str, unit: str) -> str | None:
    """The endpoint as the reader means it, carrying its unit.

    A ``decimal_ratio`` is shifted two decimal places exactly (Decimal.scaleb --
    digits preserved, nothing rounded, no float) and shown as a percentage; a
    ``unitless`` value is the source string verbatim. The raw string itself is
    never replaced anywhere else -- geometry and lineage keep the source value.
    """
    if unit == "unitless":
        return escape_typst_string(stated)
    try:
        shifted = Decimal(stated).scaleb(2)
    except InvalidOperation:
        return None
    return escape_typst_string(f"{format(shifted, 'f')}%")


def _coverage_note(points: Sequence[tuple[float, float, str, str]]) -> str:
    """What the strip actually covers, from source facts alone.

    The x-axis is the observation sequence, so the strip's width says nothing
    about the calendar. This line does: observation count and observed first/last
    dates, which makes a warm-up or partial series visibly narrower than the
    stated period without inferring anything from calendar distance.
    """
    first_date = escape_typst_string(points[0][3])
    last_date = escape_typst_string(points[-1][3])
    return (
        "\n#grid(\n  columns: (110pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
        f"  [#text(size: text-micro, fill: slate)[{len(points)} observations, "
        f"{first_date} to {last_date}]],\n)"
    )


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


def _placeable_points(series: object) -> list[tuple[float, float, str, str]] | None:
    """(x fraction, y fraction from top, verbatim value, date) per point, or None.

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


def _normalized(
    parsed: list[tuple[date, float, str]],
) -> list[tuple[float, float, str, str]] | None:
    dates = [when for when, _, _ in parsed]
    if dates != sorted(dates):
        return None
    low = min(magnitude for _, magnitude, _ in parsed)
    high = max(magnitude for _, magnitude, _ in parsed)
    magnitude_span = high - low
    last_index = len(parsed) - 1
    points: list[tuple[float, float, str, str]] = []
    for index, (when, magnitude, raw) in enumerate(parsed):
        # The ordered observation sequence: index places the dot. Calendar
        # distance is NOT data-quality evidence (a weekend is not a gap), so it
        # does not shape the strip; coverage is stated as facts beside it.
        x = index / last_index
        # A flat series sits on the centre line: equal magnitudes, equal heights.
        y = 0.5 if magnitude_span == 0 else (high - magnitude) / magnitude_span
        points.append((x, y, raw, when.isoformat()))
    return points


def _dot_markup(points: Sequence[tuple[float, float, str, str]]) -> str:
    dots = []
    for x, y, _, _ in points:
        dy = _BAND_INSET + y * _BAND_HEIGHT
        dots.append(
            f"#place(dx: {x * 100:.2f}% - 0.9pt, dy: {dy:.2f}pt, circle(radius: 0.9pt, fill: ink))"
        )
    return "".join(dots)
