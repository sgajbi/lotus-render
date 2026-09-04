"""Historical risk attribution: "what risk drove the result?", stated only.

The #254 contract locked with Report on 2026-09-04, rendered per Render's own
clauses. Every fact is source-owned and every rule mirrors the risk-trend
discipline:

- One panel, both sets stacked -- "Total risk — volatility" first, then
  "Active risk — tracking error"; a refused set is a stated row in place, so
  an unbenchmarked portfolio shows the absolute decomposition beside a named
  refusal, never an invisible set.
- Each contributor is a row: source-owned label, a signed diverging-track bar
  (sector contributions can be negative and the sign must draw, not clamp),
  the component contribution formatted from the set's source-stated unit, and
  percent_contribution formatted by the STRUCTURAL fraction-of-one rule the
  contract defines. Bars normalise within their set to the largest absolute
  component; contributor order is the source's, never re-ranked.
- The RESIDUAL is always its own labelled row with a value and NO bar -- a
  residual drawn as a bar would visually rank it against contributors, and a
  zero residual still prints (zero is a finding). The stated reconciliation
  facts print beside it; Render performs no arithmetic and verifies nothing.
- The scale convention is stated wherever a set draws.
- Fail-visible, never part-drawn: a ready set without its unit, an incomplete
  reconciliation triple, contributor rows missing the locked fields, or
  values the display rules cannot honestly state refuse the WHOLE set with a
  statement. The producer refuses most of these upstream; these rules are the
  backstop against drift.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from app.services.reader_units import (
    fraction_reader_value,
    metric_reader_value,
    period_caption,
)
from app.services.typst_values import escape_typst_string

_SET_LABELS = {
    ("TOTAL_RISK", "VOLATILITY"): "Total risk — volatility",
    ("ACTIVE_RISK", "TRACKING_ERROR"): "Active risk — tracking error",
}

_SCALE_STATEMENT = (
    "Bars are scaled within each decomposition; the figures show the actual contributions."
)


def render_risk_attribution_panel(report_data: Mapping[str, object]) -> str:
    """The attribution panel as Typst markup, or empty when not ordered."""
    attribution = report_data.get("risk_attribution")
    if not isinstance(attribution, Mapping) or not attribution:
        return ""
    entries = _set_mappings(attribution.get("sets"))
    blocks = [_set_block(entry) for entry in entries]
    if not blocks:
        return ""
    lines = [
        "#v(12pt)",
        '#section-subtitle("Risk attribution")',
    ]
    caption = _window_caption(attribution.get("window"), entries)
    if caption:
        lines.append(f"#text(size: text-micro, fill: slate)[{caption}]")
    lines.append("#v(6pt)")
    lines.extend(blocks)
    lines.extend(_scale_lines(blocks))
    return "\n".join(lines)


def _set_mappings(sets: object) -> list[Mapping[str, object]]:
    if not isinstance(sets, Sequence) or isinstance(sets, str):
        return []
    return [entry for entry in sets if isinstance(entry, Mapping)]


def _scale_lines(blocks: list[str]) -> list[str]:
    if not any("diverging-track(" in block for block in blocks):
        return []
    return ["#v(4pt)", f"#text(size: text-micro, fill: slate)[{_SCALE_STATEMENT}]"]


def _window_caption(window: object, entries: Sequence[Mapping[str, object]]) -> str:
    parts: list[str] = []
    grouping = _grouping_dimension(entries)
    if grouping:
        parts.append(f"by {escape_typst_string(grouping)}")
    period = window.get("period") if isinstance(window, Mapping) else None
    period_part = period_caption(period)
    if period_part:
        parts.append(period_part)
    return " · ".join(parts)


def _grouping_dimension(sets: Sequence[Mapping[str, object]]) -> str:
    # Entries arrive pre-filtered to mappings by _set_mappings.
    for entry in sets:
        grouping = entry.get("grouping_dimension")
        if isinstance(grouping, str) and grouping.strip():
            return grouping.strip()
    return ""


def _set_block(entry: Mapping[str, object]) -> str:
    label = _set_label(entry)
    posture = entry.get("posture")
    if posture == "ready":
        return _ready_set(label, entry)
    return _stated_set(label, _posture_statement(posture, entry)) + _quality_flags_note(entry)


def _set_label(entry: Mapping[str, object]) -> str:
    attribution_type = entry.get("attribution_type")
    metric = entry.get("metric")
    if isinstance(attribution_type, str) and isinstance(metric, str):
        fixed = _SET_LABELS.get((attribution_type, metric))
        if fixed:
            return fixed
        return escape_typst_string(f"{attribution_type} — {metric}")
    return "Unnamed decomposition"


def _ready_set(label: str, entry: Mapping[str, object]) -> str:
    unit = entry.get("unit")
    if not isinstance(unit, str) or unit not in ("decimal_ratio", "unitless"):
        return _stated_set(
            label, "The decomposition arrived without unit semantics and is not stated."
        )
    rows = _contributor_rows(entry, unit)
    triple = _reconciliation(entry, unit)
    if rows is None or triple is None:
        return _stated_set(
            label, "The decomposition could not be drawn from what the source supplied."
        )
    residual_value, reconciled_value, total_value = triple
    lines = [
        f"#v(6pt)\n#text(size: text-body, weight: 500, fill: ink)[{label}]",
        *rows,
        # The residual is a value, never a bar: drawn as one it would rank
        # against contributors, and it is the part the decomposition does NOT
        # explain. A zero residual still prints -- zero is a finding.
        "#grid(\n  columns: (150pt, 1fr, 92pt),\n  column-gutter: 10pt,\n"
        "  [#text(size: text-micro, fill: slate)[Residual (unallocated)]],\n  [],\n"
        f"  [#align(right)[#text(size: text-micro, fill: ink)[{residual_value}]]],\n)",
        "#grid(\n  columns: (150pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
        f"  [#text(size: text-micro, fill: slate)[Contributions sum to {reconciled_value}; "
        f"stated total {total_value}.]],\n)",
    ]
    flags = _quality_flags_note(entry)
    # Atomic for the same reason the trend rows are: a set split across a page
    # boundary separates bars from their figures and reconciliation.
    return "#block(breakable: false)[\n" + "\n".join(lines) + flags + "\n]"


def _reconciliation(entry: Mapping[str, object], unit: str) -> tuple[str, str, str] | None:
    values = []
    for key in ("residual", "reconciled_sum", "total_value"):
        stated = entry.get(key)
        if not isinstance(stated, str):
            return None
        formatted = metric_reader_value(stated, unit)
        if formatted is None:
            return None
        values.append(escape_typst_string(formatted))
    return (values[0], values[1], values[2])


def _contributor_rows(entry: Mapping[str, object], unit: str) -> list[str] | None:
    contributors = entry.get("contributors")
    if not isinstance(contributors, Sequence) or isinstance(contributors, str) or not contributors:
        return None
    parsed = []
    for row in contributors:
        item = _parsed_contributor(row, unit)
        if item is None:
            return None
        parsed.append(item)
    largest = max(magnitude for _, _, _, magnitude, _, _ in parsed)
    return [_row_markup(item, largest) for item in parsed]


def _row_markup(item: tuple[str, str, str, float, bool, str], largest: float) -> str:
    label, component, percent, magnitude, negative, extras = item
    # Normalised within the set: the largest absolute contribution fills the
    # track, and the sign draws through the diverging primitive.
    fraction = 0.0 if largest == 0 else magnitude / largest
    row_markup = (
        "#grid(\n  columns: (150pt, 1fr, 92pt, 70pt),\n  column-gutter: 10pt,\n"
        "  align: horizon,\n"
        f"  [#text(size: text-micro, fill: ink)[{label}]],\n"
        f"  [#diverging-track({fraction * 100:.2f}%, {'true' if negative else 'false'})],\n"
        f"  [#align(right)[#text(size: text-micro, fill: ink)[{component}]]],\n"
        f"  [#align(right)[#text(size: text-micro, fill: slate)[{percent}]]],\n)"
    )
    if extras:
        # Optional source facts print when stated -- dropping a stated fact
        # silently would misdescribe the source's own decomposition.
        row_markup += (
            "\n#grid(\n  columns: (150pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
            f"  [#text(size: text-micro, fill: slate)[{extras}]],\n)"
        )
    return row_markup


def _parsed_contributor(row: object, unit: str) -> tuple[str, str, str, float, bool, str] | None:
    fields = _required_row_fields(row)
    if fields is None:
        return None
    mapping_row, group_label, component, percent = fields
    component_value = metric_reader_value(component, unit)
    percent_value = fraction_reader_value(percent)
    if component_value is None or percent_value is None:
        return None
    try:
        # Parsed only to size the bar -- a risk ratio, never monetary, never
        # re-printed: the printed figures are the formatted source strings.
        magnitude = float(component)
    except ValueError:
        return None
    if not math.isfinite(magnitude):
        return None
    extras = _optional_facts(mapping_row, unit)
    if extras is None:
        return None
    return (
        escape_typst_string(group_label),
        escape_typst_string(component_value),
        escape_typst_string(percent_value),
        abs(magnitude),
        magnitude < 0,
        extras,
    )


def _required_row_fields(row: object) -> tuple[Mapping[str, object], str, str, str] | None:
    if not isinstance(row, Mapping):
        return None
    group_label = row.get("group_label")
    component = row.get("component_contribution")
    percent = row.get("percent_contribution")
    if (
        not isinstance(group_label, str)
        or not group_label.strip()
        or not isinstance(component, str)
        or not isinstance(percent, str)
    ):
        return None
    return (row, group_label.strip(), component, percent)


def _optional_facts(row: Mapping[str, object], unit: str) -> str | None:
    """The optional stated facts, formatted -- or None on an unstatable one.

    weight_average follows the structural fraction-of-one rule; marginal
    contribution follows the set's unit. Absent fields simply do not print;
    a PRESENT field that cannot be formatted refuses the set (backstop).
    """
    pieces: list[str] = []
    weight = row.get("weight_average")
    if weight is not None:
        if not isinstance(weight, str):
            return None
        formatted = fraction_reader_value(weight)
        if formatted is None:
            return None
        pieces.append(f"avg weight {escape_typst_string(formatted)}")
    marginal = row.get("marginal_contribution")
    if marginal is not None:
        if not isinstance(marginal, str):
            return None
        formatted = metric_reader_value(marginal, unit)
        if formatted is None:
            return None
        pieces.append(f"marginal {escape_typst_string(formatted)}")
    return " · ".join(pieces)


def _stated_set(label: str, statement: str) -> str:
    return (
        "#v(6pt)\n#grid(\n  columns: (150pt, 1fr),\n  column-gutter: 10pt,\n"
        f"  [#text(size: text-body, weight: 500, fill: ink)[{label}]],\n"
        f"  [#text(size: text-micro, fill: slate)[{statement}]],\n)"
    )


def _posture_statement(posture: object, entry: Mapping[str, object]) -> str:
    reason = _first_note_message(entry)
    if posture == "empty":
        prefix = "Not included"
    elif posture == "unavailable":
        prefix = "Not available"
    else:
        return "The source stated no recognised posture for this decomposition."
    return f"{prefix} — {reason}" if reason else f"{prefix}."


def _first_note_message(entry: Mapping[str, object]) -> str:
    notes = entry.get("notes")
    if not isinstance(notes, Sequence):
        return ""
    for note in notes:
        if isinstance(note, Mapping):
            message = note.get("message")
            if isinstance(message, str) and message.strip():
                return escape_typst_string(message.strip())
    return ""


def _quality_flags_note(entry: Mapping[str, object]) -> str:
    flags = entry.get("quality_flags")
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
        "\n#grid(\n  columns: (150pt, 1fr),\n  column-gutter: 10pt,\n  [],\n"
        f"  [#text(size: text-micro, fill: slate)[Source quality flags: {joined}]],\n)"
    )
