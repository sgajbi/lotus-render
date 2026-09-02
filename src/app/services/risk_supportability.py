"""Why a risk measure is missing, in the reader's terms rather than as "Not available".

One string stood for five different facts, and two of them point a reader in opposite
directions: `missing_benchmark` is permanent and expected -- a benchmark-relative measure
is meaningless for this mandate -- while `risk_upstream_failure` means the risk service
was down and the report is worth re-running. A reader seeing `Beta: Not available` could
not tell a statement about the mandate from a statement about the data.

Report states it now (`risk_posture`, report#238/#240) and Render reads it:

- ``posture`` is bounded and authoritative: ``ready`` / ``partial`` / ``unavailable``.
  Never inferred from whether values are present.
- ``notes`` carry Report's own sentences, forwarded rather than reconstructed. A note's
  ``affected_measures`` names the panel fields it concerns, from the constant that decides
  which metrics are benchmark-relative -- a list Render must not hold a copy of, because a
  copy goes stale the moment Report's requested metric set moves.
- ``affected_measures: []`` is a real answer distinct from absent: the note concerns only
  metrics this report does not present, so there is nothing on the page to say it about,
  and the line is dropped. Absent means section-wide, and the message stands alone.
- An empty ``notes`` on ``ready`` draws nothing. An absence of notes is not a reassurance
  the page has earned.

One line per fact, under the panel, not per-cell marking: `missing_benchmark` is one fact
about the mandate covering three measures, and three markers would invite a reader to
think three separate things went wrong.

This module emits Typst *string literals*, so it escapes with `escape_typst_string`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.services.typst_values import escape_typst_string

READY = "ready"
PARTIAL = "partial"
UNAVAILABLE = "unavailable"
POSTURES = frozenset({READY, PARTIAL, UNAVAILABLE})

# The label a reader sees for each risk_summary field the panel draws. Render's, for the
# same reason as DIMENSION_TITLES: the package sends field names and no labels, so a
# supplied label could never disagree with the panel's own headings.
MEASURE_LABELS = {
    "volatility_pct": "Volatility",
    "beta": "Beta",
    "tracking_error_pct": "Tracking error",
    "information_ratio": "Information ratio",
    "value_at_risk_pct": "Value at risk",
    "drawdown_pct": "Drawdown",
}


@dataclass(frozen=True)
class SupportabilityNote:
    """One of Report's sentences, with the measures it concerns where stated."""

    message: str
    period: str | None
    #: None means section-wide. An empty tuple means "about nothing this page shows",
    #: and the caller drops the note -- the two must never collapse into each other.
    affected_measures: tuple[str, ...] | None = field(default=None)


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _note(entry: object) -> SupportabilityNote | None:
    if not isinstance(entry, Mapping):
        return None
    message = _text(entry.get("message"))
    if message is None:
        # A note with no sentence has nothing to show a reader. The code is an
        # operator's join key, not page copy.
        return None
    measures = entry.get("affected_measures")
    affected: tuple[str, ...] | None
    if isinstance(measures, Sequence) and not isinstance(measures, (str, bytes, bytearray)):
        affected = tuple(str(m) for m in measures)
    else:
        affected = None
    return SupportabilityNote(
        message=message, period=_text(entry.get("period")), affected_measures=affected
    )


def _notes(block: Mapping[str, object]) -> list[SupportabilityNote]:
    entries = block.get("notes")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        return []
    return [note for entry in entries if (note := _note(entry)) is not None]


def _line(note: SupportabilityNote) -> str | None:
    """One sentence for the page, or None when the note concerns nothing shown.

    A note naming measures is prefixed with the reader's labels for them, so the
    sentence says *which* cells it explains -- Report's message states the why and does
    not repeat the which, precisely so this list cannot go stale in two places.
    """
    if note.affected_measures is not None:
        labels = [
            MEASURE_LABELS[measure]
            for measure in note.affected_measures
            if measure in MEASURE_LABELS
        ]
        if not labels:
            # [] from Report, or measures the panel does not draw: nothing on this page
            # to say it about.
            return None
        named = ", ".join(labels[:-1]) + (" and " if len(labels) > 1 else "") + labels[-1]
        sentence = f"{named}: {note.message}"
    else:
        sentence = note.message
    if note.period:
        sentence += f" (applies to the {note.period} period)"
    return sentence


def render_risk_supportability_notes(report_data: Mapping[str, object]) -> str:
    """The explanatory lines under the risk panel, as invoked Typst calls.

    Empty when there is nothing true to say: no `risk_posture` block (the section was
    not ordered -- report#236 stops drawing the panel too), or `ready` with no notes.
    An unrecognised posture is a contract violation, and the conservative reading is a
    line saying the supportability was not stated -- never silence that reads as
    everything-supported, and never an invented reason.
    """
    block = report_data.get("risk_posture")
    if not isinstance(block, Mapping):
        return ""
    posture = _text(block.get("posture"))
    lines = [line for note in _notes(block) if (line := _line(note)) is not None]
    if not lines and posture != READY:
        # `partial`/`unavailable` promise an explanation and none survived, or the
        # posture itself is unrecognised. Silence here recreates the original defect --
        # bare "Not available" cells -- so the page says the one thing that is true
        # without inventing a reason.
        lines = ["The supportability of these measures was not stated for this report."]
    return "\n".join(f'#panel-note("{escape_typst_string(line)}")' for line in lines)
