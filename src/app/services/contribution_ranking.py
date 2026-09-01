"""Which holdings explained the period's return, and which worked against it.

Report resolves the whole answer and Render draws it. The ranking is ordered by the size
of the effect, both signs are represented, and the names are already joined -- contribution
rows carry only identifiers upstream, and the readable name lives in holdings. Render ranks
nothing, joins nothing and computes no financial figure.

`presented_contribution_pct` is the reason the count is Report's rather than a layout
decision here: that number *describes the presented set*. Truncating downstream would leave
a true-looking figure describing a set no longer on the page.

The three postures are authoritative, and the third exists because of a distinction Report
found while implementing:

``ready``
    Contributors to draw.
``empty``
    Contribution was computed and there is nothing to rank -- a period with no movement.
    A fact about the portfolio.
``unavailable``
    Either the source did not compute it, or it returned rows none of which carry a usable
    value. A fact about the data. Calling the second case ``empty`` would tell a reader the
    portfolio did nothing when the truth is that the evidence could not be read.

Both halves live here: how Render reads the block, and how Render draws it. They change
together, and `typst_tables.py` was at its banked size ceiling with a dozen more analytics
coming -- one module per analytic is the shape that scales.

This module emits Typst *string literals*, so it escapes with `escape_typst_string`;
`test_a_string_literal_emitter_never_uses_the_markup_escaper` holds that line.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.absence import supplied_text
from app.services.number_format import group_digits
from app.services.typst_values import (
    escape_typst_string,
    performance_bar_domain,
    performance_bar_geometry,
)

READY = "ready"
EMPTY = "empty"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Contributor:
    """One row of the ranking, exactly as Report published it."""

    name: str
    contribution_pct: str
    average_weight_pct: str
    return_pct: str


@dataclass(frozen=True)
class ContributionRanking:
    """The block as Render reads it: a posture, and what may be drawn under it."""

    posture: str
    period: str
    contributors: tuple[Contributor, ...]
    total_portfolio_return_pct: str
    explained_contribution_pct: str
    unexplained_residual_pct: str
    presented_contribution_pct: str
    presented_count: int
    available_count: int
    unusable_row_count: int
    basis: str | None
    weighting_scheme: str | None
    residual_allocation_applied: bool | None


def _text(value: object) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _optional_text(value: object) -> str | None:
    """An absent methodology field stays absent.

    Report publishes `None` rather than defaulting, because NET and GROSS change what
    every number on the page means and there is no inferring it from a value. Render must
    not fill it in either.
    """
    text = _text(value)
    return text or None


def contribution_ranking(report_data: Mapping[str, object]) -> ContributionRanking | None:
    """The ranking this document presents, or None when the package carries none."""
    block = report_data.get("contribution_ranking")
    if not isinstance(block, Mapping):
        return None
    posture = _text(block.get("posture"))
    if posture not in {READY, EMPTY, UNAVAILABLE}:
        return None
    methodology = block.get("methodology")
    methodology = methodology if isinstance(methodology, Mapping) else {}
    applied = methodology.get("residual_allocation_applied")
    return ContributionRanking(
        posture=posture,
        period=_text(block.get("period")),
        contributors=_contributors(block.get("contributors")),
        total_portfolio_return_pct=_text(block.get("total_portfolio_return_pct")),
        explained_contribution_pct=_text(block.get("explained_contribution_pct")),
        unexplained_residual_pct=_text(block.get("unexplained_residual_pct")),
        presented_contribution_pct=_text(block.get("presented_contribution_pct")),
        presented_count=_count(block.get("presented_count")),
        available_count=_count(block.get("available_count")),
        unusable_row_count=_count(block.get("unusable_row_count")),
        basis=_optional_text(methodology.get("basis")),
        weighting_scheme=_optional_text(methodology.get("weighting_scheme")),
        residual_allocation_applied=applied if isinstance(applied, bool) else None,
    )


def _contributors(value: object) -> tuple[Contributor, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    rows = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        name = _text(entry.get("name"))
        contribution = _text(entry.get("contribution_pct"))
        if not name or not contribution:
            continue
        rows.append(
            Contributor(
                name=name,
                contribution_pct=contribution,
                average_weight_pct=_text(entry.get("average_weight_pct")),
                return_pct=_text(entry.get("return_pct")),
            )
        )
    return tuple(rows)


def _contribution_percent(value: str) -> str:
    """A decimal string as a percentage, or the absence it actually is.

    All three columns are percentages and Report sends them without units. One carrying a
    `%` while the others do not invites a reader to read weight and return as something
    else -- and a missing value must not become "0%", which is a number.
    """
    text = supplied_text(value)
    return f"{group_digits(text)}%" if value else text


# What the reconciliation says when the presented set is not the whole story. Report sends
# every number in it; Render states them and computes none. A top ten of forty-two
# explaining 6.10pp of 7.93pp is a different claim from a ranking that adds up, and a
# reader who cannot see which one they are looking at will assume the second.
def render_contribution_reconciliation(ranking: ContributionRanking) -> str:
    sentences: list[str] = []
    if ranking.available_count > ranking.presented_count:
        sentences.append(
            f"These {ranking.presented_count} of {ranking.available_count} contributors "
            f"explain {ranking.presented_contribution_pct}% of the portfolio's "
            f"{ranking.total_portfolio_return_pct}% return."
        )
    else:
        sentences.append(
            f"These {ranking.presented_count} contributors explain "
            f"{ranking.presented_contribution_pct}% of the portfolio's "
            f"{ranking.total_portfolio_return_pct}% return."
        )
    residual = ranking.unexplained_residual_pct
    if residual and residual not in {"0", "0.00", "-0.00"}:
        sentences.append(f"{residual}% of the return is unexplained by contribution.")
    if ranking.unusable_row_count:
        sentences.append(
            f"{ranking.unusable_row_count} further contributors could not be read and are "
            "not ranked."
        )
    return " ".join(sentences)


# NET or GROSS changes what every number above means, and unlike a scalar there is no
# inferring it from the value -- so it is required output, and an absent field says it is
# absent rather than being filled in. `residual_allocation_applied` decides whether the
# rows can be read as summing to the portfolio return, so where it is absent the line
# claims neither reading.
def render_contribution_methodology(ranking: ContributionRanking) -> str:
    basis = ranking.basis or "not stated"
    weighting = ranking.weighting_scheme or "not stated"
    line = f"Contributions are {basis} of fees, weighted by {weighting}."
    if ranking.residual_allocation_applied is True:
        line += " The residual is allocated across contributors, so they sum to the total."
    elif ranking.residual_allocation_applied is False:
        line += " The residual is not allocated, so contributors do not sum to the total."
    return line


def _contribution_row(row: Contributor, domain: float) -> str:
    """One row on the shared track, with its bar sized against the whole ranking."""
    geometry = performance_bar_geometry(row.contribution_pct, domain)
    return (
        '#contribution-row("'
        + escape_typst_string(row.name)
        + '", "'
        + escape_typst_string(_contribution_percent(row.contribution_pct))
        + '", "'
        + escape_typst_string(_contribution_percent(row.average_weight_pct))
        + '", "'
        + escape_typst_string(_contribution_percent(row.return_pct))
        + '", '
        + geometry.magnitude
        + ", "
        + ("true" if geometry.is_negative else "false")
        + ")"
    )


def render_contribution_ranking_section(report_data: Mapping[str, object]) -> str:
    """The ranking, drawn on one shared domain with a zero line a reader can see.

    `diverging-track` and `performance_bar_domain` already existed for the annual return
    bars: a signed magnitude against a domain shared by the whole series. A contribution
    ranking is that primitive with a security name where the period label goes, which is
    why this was the cheapest row on the roadmap for both services.
    """
    ranking = contribution_ranking(report_data)
    if ranking is None:
        return ""
    if ranking.posture == UNAVAILABLE:
        message = "Contribution could not be sourced for this period."
        if ranking.unusable_row_count:
            message = (
                f"Contribution was returned for {ranking.unusable_row_count} holdings and "
                "none of it could be read."
            )
        return f'#empty-state("{escape_typst_string(message)}")'
    if ranking.posture == EMPTY or not ranking.contributors:
        return '#empty-state("No holding moved the portfolio measurably over this period.")'

    domain = performance_bar_domain(row.contribution_pct for row in ranking.contributors)
    rows = [_contribution_row(row, domain) for row in ranking.contributors]
    return (
        "\n#v(2pt)\n".join(rows)
        + f'\n#v(5pt)\n#chart-scale-note("{domain:.2f}%")'
        + '\n#v(6pt)\n#contribution-reconciliation("'
        + escape_typst_string(render_contribution_reconciliation(ranking))
        + '", "'
        + escape_typst_string(render_contribution_methodology(ranking))
        + '")'
    )
