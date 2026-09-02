"""Why the portfolio out- or underperformed its benchmark, drawn as a bridge.

lotus-performance computes multi-level Brinson attribution and it had zero rendering
surface (#160) -- the standard "why did we beat the benchmark" page of a private-banking
review. Report composes the block (``attribution_bridge``, report#254): effects by group
at one hierarchy level, the source's authoritative level totals, and a reconciliation
whose residual the source itself classifies. Render places segments and computes no
financial figure -- the only arithmetic here is layout, turning stated values into track
positions.

The rules carried from the contract:

- **Totals are authoritative fields, never sums of rows.** The total bar is drawn from
  ``total_active_return_pp``. If the named parts do not visually reach it, the gap is a
  truth about the data, and the reconciliation sentence attributes the arithmetic to the
  source rather than claiming it closes.
- **The residual is presented, never allocated away.** It is a labelled segment of its
  own, and whether it is small is the source's classification, forwarded in prose.
- **``pending`` is said, not waited for.** The calculation exists upstream; the page
  states that regenerating the report collects the finished result.
- **Only Report prose reaches the reader.** Notes draw only when they carry a message.

This module emits Typst *string literals*, so it escapes with `escape_typst_string`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.typst_values import escape_typst_string, optional_percent

READY = "ready"
PENDING = "pending"
UNAVAILABLE = "unavailable"

SECTION_TITLE = "Performance attribution"


@dataclass(frozen=True)
class BridgeSpan:
    """Where one segment sits on the shared track, as percentages of its width."""

    offset_pct: str
    width_pct: str
    is_negative: bool


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


def _span(low: float, high: float, start: float, value: float) -> BridgeSpan:
    """One segment of the bridge, placed at its cumulative position."""
    width = high - low
    left = (min(start, start + value) - low) / width * 100
    return BridgeSpan(
        offset_pct=f"{left:.2f}%",
        width_pct=f"{abs(value) / width * 100:.2f}%",
        is_negative=value < 0,
    )


def _bridge_spans(parts: list[float], total: float) -> tuple[list[BridgeSpan], BridgeSpan, str]:
    """Cumulative placement of the parts, the total's own span, and where zero falls.

    The domain covers zero, every intermediate position and the stated total, so an
    overshoot -- parts climbing past where the total lands -- stays on the track. The
    total's span starts at zero and ends at the authoritative figure: it is never the
    parts' endpoint, which is the whole point of drawing both.
    """
    positions = [0.0]
    for value in parts:
        positions.append(positions[-1] + value)
    low = min(*positions, total)
    high = max(*positions, total)
    if high == low:
        high = low + 1.0
    spans = [_span(low, high, start, value) for start, value in zip(positions, parts, strict=False)]
    zero = (0.0 - low) / (high - low) * 100
    return spans, _span(low, high, 0.0, total), f"{zero:.2f}%"


def _bridge_row(label: str, amount: str, span: BridgeSpan, kind: str, zero: str) -> str:
    return (
        f'#bridge-row("{escape_typst_string(label)}", "{escape_typst_string(amount)}", '
        f"{span.offset_pct}, {span.width_pct}, "
        f'{"true" if span.is_negative else "false"}, "{kind}", {zero})'
    )


def _note(message: str) -> str:
    return f'#panel-note("{escape_typst_string(message)}")'


def _report_notes(block: Mapping[str, object]) -> list[str]:
    """Report-composed prose, and nothing else: a note without a message is not drawn."""
    return [
        _note(message)
        for note in [*_rows(block.get("notes")), *_rows(block.get("period_notes"))]
        if (message := _text(note.get("message")))
    ]


def _heading(body: str) -> str:
    return (
        "#block(sticky: true, breakable: false, width: 100%)["
        f'#section-subtitle("{SECTION_TITLE}") #v(7pt)]\n{body}'
    )


def _humanized(value: object) -> str:
    return _text(value).replace("_", " ") or "not stated"


def _reconciliation_sentence(reconciliation: Mapping[str, object]) -> str | None:
    """The source's arithmetic, attributed to the source.

    Render never claims the parts close to the total -- it repeats the reconciliation
    lotus-performance stated, and forwards the source's own verdict on its residual.
    """
    total = _text(reconciliation.get("total_active_return_pp"))
    sum_of_effects = _text(reconciliation.get("sum_of_effects_pp"))
    residual = _text(reconciliation.get("residual_pp"))
    if not (total and sum_of_effects and residual):
        return None
    sentence = (
        f"The source reconciles its {total}pp total active return as "
        f"{sum_of_effects}pp of named effects and a {residual}pp residual."
    )
    classification = _text(reconciliation.get("residual_classification"))
    treatment = _text(reconciliation.get("residual_treatment"))
    if classification:
        verdict = f" The source classifies the residual as {classification}"
        sentence += f"{verdict} ({treatment})." if treatment else f"{verdict}."
    return sentence


def _totals_line(totals: Mapping[str, object]) -> str | None:
    """The effect-type composition, from the authoritative level totals only."""
    named = [
        (label, _text(totals.get(key)))
        for label, key in (
            ("allocation", "allocation_pp"),
            ("selection", "selection_pp"),
            ("interaction", "interaction_pp"),
        )
        if _text(totals.get(key))
    ]
    if not named:
        return None
    stated = ", ".join(f"{label} {value}pp" for label, value in named)
    return f"Of the total effect, the source states {stated}."


def _dropped_line(dropped: int) -> str | None:
    if not dropped:
        return None
    plural = "effects" if dropped > 1 else "effect"
    verb = "are" if dropped > 1 else "is"
    return f"{dropped} {plural} could not be read and {verb} not drawn."


def _methodology_line(block: Mapping[str, object]) -> str:
    model = _humanized(block.get("model"))
    linking = _humanized(block.get("linking"))
    basis = _text(block.get("metric_basis")) or "not stated"
    benchmark = _text(block.get("benchmark_code")) or "not stated"
    return (
        f"Attribution is {model} with {linking} linking, on a {basis} basis, "
        f"against benchmark {benchmark}."
    )


def _segments(block: Mapping[str, object]) -> tuple[list[tuple[str, str, float, str]], int]:
    """The drawable segments -- parts then residual -- and how many rows could not be.

    A row Render cannot place is dropped from the chart and counted, so the page can
    say so: silently absent is the one thing a named part must never be.
    """
    segments: list[tuple[str, str, float, str]] = []
    dropped = 0
    for effect in _rows(block.get("effects")):
        value = optional_percent(effect.get("total_effect_pp"))
        if value is None:
            dropped += 1
            continue
        label = _text(effect.get("group_label")) or "Not available"
        segments.append((label, f"{_text(effect.get('total_effect_pp'))}pp", value, "part"))
    reconciliation = _mapping(block.get("reconciliation"))
    residual = optional_percent(reconciliation.get("residual_pp"))
    if residual is not None:
        label = f"{_text(reconciliation.get('residual_pp'))}pp"
        segments.append(("Residual", label, residual, "residual"))
    return segments, dropped


def _ready_bridge(block: Mapping[str, object]) -> str:
    """The bridge itself: parts at cumulative positions, residual, authoritative total."""
    reconciliation = _mapping(block.get("reconciliation"))
    total = optional_percent(reconciliation.get("total_active_return_pp"))
    if total is None:
        # Without a stated destination there is no bridge to draw; the fact is said.
        return _heading('#empty-state("Attribution figures could not be read for this period.")')

    segments, dropped = _segments(block)
    spans, total_span, zero = _bridge_spans([value for _, _, value, _ in segments], total)
    total_text = _text(reconciliation.get("total_active_return_pp"))
    rows = [
        _bridge_row(label, amount, span, kind, zero)
        for (label, amount, _, kind), span in zip(segments, spans, strict=True)
    ]
    rows.append(_bridge_row("Total active return", f"{total_text}pp", total_span, "total", zero))

    lines = [
        _reconciliation_sentence(reconciliation),
        _totals_line(_mapping(block.get("totals"))),
        _dropped_line(dropped),
        _methodology_line(block),
    ]
    return (
        f'#labelled-table("{SECTION_TITLE}", '
        "grid(columns: (1.5fr, 1.6fr, 0.62fr), column-gutter: 7pt, "
        '[#table-label("Effect")], [#table-label("Bridge")], '
        '[#table-label("Active", placement: right)]), [\n'
        + "\n#v(2pt)\n".join(rows)
        + "\n])\n"
        + "\n".join([_note(line) for line in lines if line is not None] + _report_notes(block))
    )


def render_attribution_bridge(report_data: Mapping[str, object]) -> str:
    """The bridge as invoked Typst calls, a posture statement, or nothing.

    Nothing when the package carries no block: the section is opt-in upstream, and an
    absent key promises nothing -- the golden carries the key so this branch is never
    the only one exercised (the positions-fixture lesson).
    """
    block = report_data.get("attribution_bridge")
    if not isinstance(block, Mapping) or not block:
        return ""
    posture = _text(block.get("posture"))
    if posture == PENDING:
        calculation = _text(block.get("calculation_id"))
        identity = f" (calculation {calculation})" if calculation else ""
        return _heading(
            _note(
                f"Performance attribution is still computing for this report{identity}; "
                "regenerating the report collects the finished result."
            )
        )
    if posture != READY:
        return _heading(
            "\n".join(
                [
                    '#empty-state("Performance attribution could not be sourced for this period.")',
                    *_report_notes(block),
                ]
            )
        )
    return _ready_bridge(block)
