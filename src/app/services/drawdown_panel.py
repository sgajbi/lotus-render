"""The drawdown panel (report#289): "how bad did it get, how long to recover?"

Renders the stated ``report_data.drawdown`` block onto the risk page. The
posture grammar per the locked contract: ``ready`` draws the underwater
chart (episodes may be empty -- visible calm, no caption); ``empty`` states
the one-line document fact -- the panel IS the visualization, and a blank
panel is a design hole; ``unavailable`` states the source's sentence; an
absent block (pre-#289 packages) makes no panel claim at all.

Values arrive as verbatim decimal-fraction strings under a stated
``value_unit`` -- the percent presentation here is grounded in that stated
unit, never in a description sentence. Episodes arrive COMPLETE; the top
three by depth are presented and the drop count is stated when more exist.
A null ``recovery_date`` is an OPEN episode and is worded as such -- an
unrecovered drawdown never reads closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.date_format import format_date
from app.services.typst_values import escape_typst_string

#: How many episodes the panel presents, deepest first. The emission is
#: complete by contract; capping is presentation-side and always stated.
PRESENTED_EPISODE_LIMIT = 3

_DURATION_LABELS = {"BUSINESS_DAYS": "business days", "CALENDAR_DAYS": "calendar days"}


def render_drawdown_panel(report_data: Mapping[str, object]) -> str:
    """The panel as Typst markup, or empty when the package makes no claim."""

    block = report_data.get("drawdown")
    if not isinstance(block, Mapping):
        return ""
    posture = str(block.get("posture") or "").strip()
    if not posture:
        return ""
    header = ["#v(12pt)", '#section-subtitle("Drawdown (1Y)")', "#v(6pt)"]
    if posture == "ready":
        return "\n".join([*header, *_ready_panel_lines(block)])
    statement = _stated_posture_line(block, posture)
    if statement is None:
        return ""
    return "\n".join([*header, statement])


def _stated_posture_line(block: Mapping[str, object], posture: str) -> str | None:
    if posture == "empty":
        return _micro_text("No drawdown recorded for the period.")
    if posture == "unavailable":
        statement = str(block.get("source_statement") or "").strip()
        if statement:
            return f'#panel-note("{escape_typst_string(statement)}")'
    return None


def _ready_panel_lines(block: Mapping[str, object]) -> list[str]:
    points = _underwater_points(block.get("underwater"))
    duration_unit = str(block.get("duration_unit") or "").strip()
    lines: list[str] = []
    if len(points) >= 2:
        lines.append(_underwater_chart(points))
    summary_line = _summary_line(block.get("summary"))
    if summary_line:
        lines.append("#v(6pt)")
        lines.append(summary_line)
    lines.extend(_episode_lines(block.get("episodes"), duration_unit))
    return lines


def _underwater_points(raw: object) -> list[tuple[str, float]]:
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return []
    points: list[tuple[str, float]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        date = str(item.get("date") or "").strip()
        value = _decimal_fraction(item.get("drawdown"))
        if date and value is not None:
            points.append((date, value))
    return points


def _decimal_fraction(stated: object) -> float | None:
    """A stated decimal-fraction string parsed for geometry and presentation.

    The emission states value_unit: decimal_fraction, which is what grounds
    the percent conversion here -- a unit error in this formatter would be a
    100x lie, so the conversion leans on stated data, never on prose.
    """

    try:
        parsed = float(str(stated))
    except (TypeError, ValueError):
        return None
    if parsed > 0:
        # Drawdowns are depths at or below zero; a positive value is not a
        # drawdown fact and drawing it would invent a recovery overshoot.
        return None
    return parsed


def _percent_text(value: float) -> str:
    # `+ 0.0` folds negative zero, so the top gridline reads 0.00%, not -0.00%.
    return f"{value * 100 + 0.0:.2f}%"


def _axis_step(low: float) -> float:
    """A round gridline step covering the deepest value in at most four steps."""

    for step in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0):
        if abs(low) <= step * 4:
            return step
    return 1.0


def _underwater_chart(points: list[tuple[str, float]]) -> str:
    low = min(value for _, value in points)
    step = _axis_step(low)
    gridline_count = max(1, int(abs(low) / step) + (1 if abs(low) % step else 0))
    axis_low = -step * gridline_count
    gridlines = ",\n".join(
        f'    (label: "{_percent_text(-step * index)}", '
        f"at: {(-step * index) / axis_low:.5f}, zero: {'true' if index == 0 else 'false'})"
        for index in range(gridline_count + 1)
    )
    span = max(len(points) - 1, 1)
    plotted = ",\n".join(
        f"    (at: {index / span:.5f}, value: {value / axis_low:.5f})"
        for index, (_, value) in enumerate(points)
    )
    labels = ",\n".join(
        f'    (text: "{escape_typst_string(format_date(date))}", at: {fraction:.5f})'
        for date, fraction in ((points[0][0], 0.0), (points[-1][0], 1.0))
    )
    deepest = _percent_text(low)
    alt = escape_typst_string(
        f"Underwater chart of portfolio drawdown, {format_date(points[0][0])} to "
        f"{format_date(points[-1][0])}, deepest {deepest}."
    )
    return (
        '#chart-card("Underwater profile", subtitle: "Depth below the running peak, net")[\n'
        f'  #figure(alt: "{alt}", line-chart(\n'
        "    gridlines: (\n" + gridlines + ",\n    ),\n"
        "    points: (\n" + plotted + ",\n    ),\n"
        "    labels: (\n" + labels + ",\n    ),\n"
        '    series-label: "Drawdown",\n'
        "  ))\n"
        "]"
    )


def _summary_line(raw: object) -> str:
    if not isinstance(raw, Mapping):
        return ""
    depth = _decimal_fraction(raw.get("max_drawdown"))
    if depth is None:
        return ""
    peak = str(raw.get("max_drawdown_peak_date") or "").strip()
    trough = str(raw.get("max_drawdown_trough_date") or "").strip()
    recovery = raw.get("max_drawdown_recovery_date")
    recovered = f"recovered {format_date(str(recovery))}" if recovery else "not yet recovered"
    statement = (
        f"Maximum drawdown {_percent_text(depth)} (peak {format_date(peak)}, "
        f"trough {format_date(trough)}, {recovered})."
    )
    return _body_text(statement)


def _episode_lines(raw: object, duration_unit: str) -> list[str]:
    episodes = _sorted_episodes(raw)
    if not episodes:
        return []
    lines = ["#v(4pt)"]
    for episode in episodes[:PRESENTED_EPISODE_LIMIT]:
        lines.append(_episode_line(episode, duration_unit))
    if len(episodes) > PRESENTED_EPISODE_LIMIT:
        lines.append(
            _micro_text(
                f"Showing the {PRESENTED_EPISODE_LIMIT} deepest of {len(episodes)} episodes."
            )
        )
    return lines


def _sorted_episodes(raw: object) -> list[Mapping[str, object]]:
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return []
    episodes = [
        (depth, item)
        for item in raw
        if isinstance(item, Mapping) and (depth := _decimal_fraction(item.get("depth"))) is not None
    ]
    episodes.sort(key=lambda entry: entry[0])
    return [item for _, item in episodes]


def _episode_line(episode: Mapping[str, object], duration_unit: str) -> str:
    depth = _decimal_fraction(episode.get("depth"))
    peak = format_date(str(episode.get("peak_date") or ""))
    trough = format_date(str(episode.get("trough_date") or ""))
    recovery = episode.get("recovery_date")
    recovered = f"recovered {format_date(str(recovery))}" if recovery else "not yet recovered"
    parts = [
        f"Peak {peak}, trough {trough}",
        _percent_text(depth) if depth is not None else "depth not stated",
    ]
    days = episode.get("days_to_trough")
    if isinstance(days, int):
        unit = _DURATION_LABELS.get(duration_unit, duration_unit.lower() or "days")
        parts.append(f"{days} {unit} to trough")
    parts.append(recovered)
    return _body_text(" · ".join(parts))


def _body_text(statement: str) -> str:
    return f"#text(size: text-body, fill: ink)[{escape_typst_string(statement)}]"


def _micro_text(statement: str) -> str:
    return f"#text(size: text-micro, fill: slate)[{escape_typst_string(statement)}]"
