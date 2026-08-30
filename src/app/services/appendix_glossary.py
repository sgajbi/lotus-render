"""Decide which reference entries a document actually needs to carry.

The appendix was six fixed pages of small print, identical in every document. It
defined ESG attributes, private markets, hedge funds, real estate, an income overview
and a portfolio health check -- none of which the portfolio review renders -- and
defined none of the risk measures it does render. A reader looking up "Tracking error"
found nothing; a reader looking up nothing found ten definitions of it.

So the appendix is now assembled from what the document contains. Each entry declares
the subject it explains, this module reports which subjects the report data carries,
and the template emits the intersection. An entry with no subject in the document is
not shrunk or moved: it is absent, because it explains nothing that is there.

The wording lives in the template beside the rest of the document's copy, so a change
to a definition moves the template digest and needs re-approval. This module holds only
the decision about which entries apply, which is where it can be tested.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.typst_values import row_sequence


@dataclass(frozen=True)
class GlossaryEntry:
    """One reference entry, and the thing whose presence makes it worth printing."""

    key: str
    subject: str


@dataclass(frozen=True)
class GlossaryGroup:
    """Entries a reader would look for together, under the heading they look under."""

    title: str
    entries: tuple[GlossaryEntry, ...]


def _entries(subject: str, *keys: str) -> tuple[GlossaryEntry, ...]:
    return tuple(GlossaryEntry(key=key, subject=subject) for key in keys)


# Ordered as the document is: a reader meets these terms in this sequence.
APPENDIX_GLOSSARY: tuple[GlossaryGroup, ...] = (
    GlossaryGroup(
        title="Performance measurement",
        entries=(
            *_entries(
                "performance",
                "net_performance",
                "time_weighted_return",
                "cumulative_return",
                "inflows_and_outflows",
                "annualisation",
            ),
            *_entries("benchmark", "benchmark", "relative_return"),
        ),
    ),
    GlossaryGroup(
        title="Risk measures",
        entries=(
            *_entries("risk.volatility", "volatility"),
            *_entries("risk.beta", "beta"),
            *_entries("risk.tracking_error", "tracking_error"),
            *_entries("risk.information_ratio", "information_ratio"),
            *_entries("risk.value_at_risk", "value_at_risk"),
        ),
    ),
    GlossaryGroup(
        title="Asset allocation",
        entries=(
            *_entries("allocation", "asset_class", "market_value", "weight", "invested_value"),
            *_entries("allocation.currency", "currency_exposure"),
        ),
    ),
    GlossaryGroup(
        title="Positions",
        entries=_entries(
            "positions",
            "cost_value",
            "unrealised_profit_and_loss",
            "market_gain",
            "exchange_gain",
            "accrued_interest",
        ),
    ),
    GlossaryGroup(
        title="Transactions",
        entries=_entries(
            "transactions",
            "trade_and_value_date",
            "transaction_value",
            "settlement_amount",
            "realised_profit_and_loss",
        ),
    ),
)

# Which risk_summary field decides that its measure is on the page. The document draws
# a card per field, so an absent field means an absent card and an absent definition.
_RISK_SUBJECT_FIELDS = {
    "risk.volatility": "volatility_pct",
    "risk.beta": "beta",
    "risk.tracking_error": "tracking_error_pct",
    "risk.information_ratio": "information_ratio",
    "risk.value_at_risk": "value_at_risk_pct",
}

# A benchmark column is drawn only where a period carries one of these.
_BENCHMARK_FIELDS = ("benchmark_return_pct", "benchmark_cumulative_twr", "relative_return_pct")


def _has_rows(value: object) -> bool:
    rows = row_sequence(value)
    return bool(rows)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _is_supplied(value: object) -> bool:
    """A field counts as supplied when it carries something a card could show.

    Report data spells an absent measure several ways -- the key missing, ``None``, an
    empty string, or the literal "Not available" the degraded fixture uses -- and all of
    them mean the same thing to a reader: no card, so no definition.
    """
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"not available", "n/a", "none", "-"}


def _benchmark_is_drawn(report_data: Mapping[str, object]) -> bool:
    for key in ("performance_periods", "performance_monthly_history", "performance_annual_history"):
        for row in row_sequence(report_data.get(key)) or ():
            if isinstance(row, Mapping) and any(
                _is_supplied(row.get(field)) for field in _BENCHMARK_FIELDS
            ):
                return True
    return False


def _performance_subjects(report_data: Mapping[str, object]) -> set[str]:
    subjects: set[str] = set()
    if any(
        _has_rows(report_data.get(key)) or _mapping(report_data.get(key))
        for key in (
            "performance_periods",
            "performance_summary_table",
            "performance_monthly_history",
            "performance_annual_history",
        )
    ):
        subjects.add("performance")
    if _benchmark_is_drawn(report_data):
        subjects.add("benchmark")
    return subjects


def _risk_subjects(report_data: Mapping[str, object]) -> set[str]:
    risk_summary = _mapping(report_data.get("risk_summary"))
    return {
        subject
        for subject, field in _RISK_SUBJECT_FIELDS.items()
        if _is_supplied(risk_summary.get(field))
    }


def _allocation_subjects(report_data: Mapping[str, object]) -> set[str]:
    breakdowns = _mapping(report_data.get("allocation_breakdowns"))
    subjects: set[str] = set()
    if _has_rows(breakdowns.get("by_asset_class")) or _has_rows(
        report_data.get("allocation_items")
    ):
        subjects.add("allocation")
    if any(_has_rows(rows) for key, rows in breakdowns.items() if key != "by_asset_class"):
        subjects.add("allocation.currency")
    return subjects


def _holding_subjects(report_data: Mapping[str, object]) -> set[str]:
    return {
        subject
        for subject, key in (("positions", "top_holdings"), ("transactions", "transactions"))
        if _has_rows(report_data.get(key))
    }


def present_subjects(report_data: Mapping[str, object]) -> frozenset[str]:
    """The subjects this report data puts on a page."""
    return frozenset(
        _performance_subjects(report_data)
        | _risk_subjects(report_data)
        | _allocation_subjects(report_data)
        | _holding_subjects(report_data)
    )


def applicable_glossary(report_data: Mapping[str, object]) -> list[GlossaryGroup]:
    """The glossary this document needs, with everything it does not need removed.

    A group whose entries all fall away is dropped rather than printed empty: a heading
    over nothing is one more thing for a reader to read and discard.
    """
    subjects = present_subjects(report_data)
    applicable: list[GlossaryGroup] = []
    for group in APPENDIX_GLOSSARY:
        entries = tuple(entry for entry in group.entries if entry.subject in subjects)
        if entries:
            applicable.append(GlossaryGroup(title=group.title, entries=entries))
    return applicable


def all_glossary_keys() -> Sequence[str]:
    """Every key this module can ask a template for."""
    return [entry.key for group in APPENDIX_GLOSSARY for entry in group.entries]
