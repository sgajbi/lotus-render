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
from dataclasses import dataclass
from datetime import date

from app.services.reader_units import metric_reader_value, period_caption
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
    period_part = period_caption(window.get("period"))
    if period_part:
        parts.append(period_part)
    return " · ".join(parts)


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
    placed = _placed_series(metric.get("series"))
    if placed is None:
        return _stated_row(
            label,
            "The series could not be drawn from what the source supplied.",
        )
    first_value = _reader_value(placed.first_value, unit)
    last_value = _reader_value(placed.last_value, unit)
    if first_value is None or last_value is None:
        return _stated_row(
            label,
            "The series could not be drawn from what the source supplied.",
        )
    dots = _dot_markup(placed.dots)
    row = (
        "#grid(\n"
        "  columns: (110pt, 1fr, 100pt),\n"
        "  column-gutter: 10pt,\n"
        "  align: horizon,\n"
        f"  [#text(size: text-body, fill: ink)[{label}]],\n"
        "  [#pdf.artifact(block(\n"
        f"    width: 100%, height: {_BAND_HEIGHT + 2 * _BAND_INSET:.0f}pt,\n"
        # The hairline makes the band's boundary visible: page inspection showed
        # that against the near-white fill alone, a dot sitting on the bottom
        # edge reads as having escaped the strip.
        "    fill: mist, stroke: 0.5pt + rule, radius: 3pt,\n"
        f"  )[{dots}])],\n"
        "  [#align(right)[#text(size: text-micro, fill: slate)"
        f"[{first_value} #sym.arrow.r ]#text(size: text-micro, weight: 500, fill: ink)"
        f"[{last_value}]]],\n"
        ")"
    )
    # One atomic unit: a strip that breaks across a page boundary re-anchors
    # its placed dots in the continuation region and they land outside the
    # band -- found by inspecting a page where the risk section straddled the
    # break, invisible at any mid-page position.
    return (
        "#block(breakable: false)[\n"
        + row
        + _coverage_note(placed)
        + _quality_flags_note(metric)
        + "\n]"
    )


def _reader_value(stated: str, unit: str) -> str | None:
    """The endpoint as the reader means it, carrying its unit.

    Formatting itself lives in reader_units (promoted on its second consumer,
    risk attribution); the raw string is never replaced anywhere else --
    geometry and lineage keep the source value.
    """
    formatted = metric_reader_value(stated, unit)
    if formatted is None:
        return None
    return escape_typst_string(formatted)


def _coverage_note(placed: "_PlacedSeries") -> str:
    """What the strip actually covers, from source facts alone.

    The x-axis is the observation sequence, so the strip's width says nothing
    about the calendar. This line does: the slot count, how many of those slots
    the source stated it did not compute, and the observed first/last dates --
    which makes warm-up, partial coverage, and explicit gaps all legible without
    inferring anything from calendar distance.
    """
    counted = f"{placed.slot_count} observations"
    if placed.not_computed_count:
        counted += f", {placed.not_computed_count} not computed"
    first_date = escape_typst_string(placed.first_date)
    last_date = escape_typst_string(placed.last_date)
    return (
        "\n#grid(\n  columns: (110pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
        f"  [#text(size: text-micro, fill: slate)[{counted}, "
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


@dataclass(frozen=True, slots=True)
class _PlacedSeries:
    """A drawable series: dot geometry plus the coverage facts the row states."""

    dots: list[tuple[float, float]]
    first_value: str
    last_value: str
    first_date: str
    last_date: str
    slot_count: int
    not_computed_count: int


def _placed_series(series: object) -> _PlacedSeries | None:
    """The series placed on the observation-sequence axis, or None.

    Every source-stated slot -- computed or explicitly ``not_computed`` --
    occupies a position on the x-axis, so an explicit gap appears as a hole in
    an otherwise regular dot rhythm: spatial missingness from source-stated
    slots only, never from calendar classification. None means the series
    cannot be honestly placed: fewer than two slots, fewer than two COMPUTED
    points (one level cannot state a trend), a slot that parses as neither a
    computed point nor a well-formed gap, or dates out of order. Values are
    parsed ONLY to position dots; nothing derived is ever printed.
    """
    if not isinstance(series, Sequence) or isinstance(series, str) or len(series) < 2:
        return None
    slots: list[tuple[date, float | None, str | None]] = []
    for point in series:
        entry = _parsed_slot(point)
        if entry is None:
            return None
        slots.append(entry)
    dates = [when for when, _, _ in slots]
    if dates != sorted(dates):
        return None
    return _normalized(slots)


def _parsed_slot(point: object) -> tuple[date, float | None, str | None] | None:
    """One slot: (date, magnitude, stated) computed, (date, None, None) gap.

    The locked gap contract (report#255 addendum): an explicit gap carries BOTH
    facts -- ``value: null`` and ``point_posture: "not_computed"``. A posture
    beside a value, a null without a posture (the shape the producer used to
    drop), and an unknown posture word are each contradictions, and a series
    containing one is fail-visible rather than part-drawn.
    """
    if not isinstance(point, Mapping):
        return None
    raw_date = point.get("date")
    if not isinstance(raw_date, str):
        return None
    try:
        when = date.fromisoformat(raw_date)
    except ValueError:
        return None
    if "point_posture" in point or point.get("value") is None:
        return _gap_slot(when, point)
    return _computed_slot(when, point.get("value"))


def _gap_slot(when: date, point: Mapping[str, object]) -> tuple[date, None, None] | None:
    if point.get("point_posture") != "not_computed" or point.get("value") is not None:
        return None
    return (when, None, None)


def _computed_slot(when: date, stated: object) -> tuple[date, float, str] | None:
    if not isinstance(stated, str):
        return None
    try:
        # A risk ratio, parsed only to place a dot -- never monetary, never
        # re-printed: what the page quotes is the verbatim source string.
        magnitude = float(stated)
    except ValueError:
        return None
    if not math.isfinite(magnitude):
        return None
    return (when, magnitude, stated)


def _computed_only(
    slots: list[tuple[date, float | None, str | None]],
) -> list[tuple[int, float, str]]:
    computed = []
    for index, (_, magnitude, stated) in enumerate(slots):
        if magnitude is not None and stated is not None:
            computed.append((index, magnitude, stated))
    return computed


def _normalized(slots: list[tuple[date, float | None, str | None]]) -> _PlacedSeries | None:
    computed = _computed_only(slots)
    if len(computed) < 2:
        return None
    low = min(magnitude for _, magnitude, _ in computed)
    high = max(magnitude for _, magnitude, _ in computed)
    magnitude_span = high - low
    last_index = len(slots) - 1
    dots: list[tuple[float, float]] = []
    for index, magnitude, _ in computed:
        # The ordered observation sequence: the SLOT index places the dot, and a
        # not_computed slot keeps its position empty -- the hole is the source's
        # own statement, occupying exactly one slot of space.
        x = index / last_index
        # A flat series sits on the centre line: equal magnitudes, equal heights.
        y = 0.5 if magnitude_span == 0 else (high - magnitude) / magnitude_span
        dots.append((x, y))
    return _PlacedSeries(
        dots=dots,
        first_value=computed[0][2],
        last_value=computed[-1][2],
        first_date=slots[0][0].isoformat(),
        last_date=slots[-1][0].isoformat(),
        slot_count=len(slots),
        not_computed_count=len(slots) - len(computed),
    )


def _dot_markup(dots: Sequence[tuple[float, float]]) -> str:
    markup = []
    for x, y in dots:
        dy = _BAND_INSET + y * _BAND_HEIGHT
        markup.append(
            f"#place(dx: {x * 100:.2f}% - 0.9pt, dy: {dy:.2f}pt, circle(radius: 0.9pt, fill: ink))"
        )
    return "".join(markup)
