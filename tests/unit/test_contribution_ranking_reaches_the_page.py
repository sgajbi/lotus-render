"""Which holdings explained the period, and what the ranking does not say.

Report captures a ranked contribution set, and Render surfaced one scalar of it:
`TOP_CONTRIBUTOR_NAME`. The data round-tripped and was thrown away.

Two things make this primitive different from the table it replaces:

- **A top-N is not the whole story, and looks like one.** Ten of forty-two contributors
  explaining 6.10% of a 7.93% return is a different claim from a ranking that adds up.
  Report sends every number needed to say which; Render states them and computes none.
- **NET or GROSS changes what every number means**, and unlike a scalar there is no
  inferring it from the value. So the methodology line is required output, and an absent
  field says it is absent rather than being filled in.

The bars are `diverging-track` -- the primitive the annual return rows already used, with
a shared domain and a drawn zero because without a zero a short loss looks like a short
gain. A contribution ranking is that primitive with a security name where the period
label goes, which is why this was the cheapest analytic on the roadmap for both services.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.contribution_ranking import (
    render_contribution_ranking_section,
)
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _package(**overrides: Any) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    package["report_data"]["contribution_ranking"].update(overrides)
    return package


def _document(package: dict[str, Any]) -> str:
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in reader.pages))


@pytest.fixture(scope="module")
def golden_document() -> str:
    return _document(json.loads(GOLDEN.read_text(encoding="utf-8")))


def test_both_signs_are_ranked_on_one_track(golden_document: str) -> None:
    """A ranking that shows only winners reads as an explanation while omitting half the
    cause. Report never filters to winners; this is the page proving it arrives that way."""

    assert "Contribution to return" in golden_document
    assert "Alphabet Inc Class A" in golden_document, "the largest positive is missing"
    assert "Vodafone Group PLC" in golden_document, "the largest negative is missing"
    assert "-0.85%" in golden_document, "a negative contribution lost its sign"


def test_the_shared_domain_is_stated(golden_document: str) -> None:
    """An auto-scaled bar with an unstated domain is half-honest.

    Two charts in one document can share a visual language and not share a scale, so the
    track says what it is scaled to -- the same note the annual bars carry.
    """

    assert "Bars scaled to" in golden_document
    assert "the largest move in this series" in golden_document


def test_the_reconciliation_says_what_the_ranking_leaves_out(golden_document: str) -> None:
    """Presented count, available count, the share explained, and the residual.

    Without it a reader takes the list for the whole story. Every number in the sentence
    is Report's; Render arranges them.
    """

    assert "These 8 of 42 contributors explain" in golden_document
    assert "6.10% of the portfolio's 7.93% return" in golden_document
    assert "0.40% of the return is unexplained by contribution" in golden_document
    assert "3 further contributors could not be read" in golden_document


def test_the_methodology_is_on_the_page(golden_document: str) -> None:
    """NET or GROSS changes what every number above it means."""

    assert "Contributions are NET of fees, weighted by average weight." in golden_document
    assert "The residual is not allocated, so contributors do not sum to the total." in (
        golden_document
    )


def test_an_absent_methodology_field_says_so_rather_than_being_filled_in() -> None:
    """Report publishes an absent basis as absent and never guesses NET.

    Render must not guess either. The ranking still draws -- the contributions are real
    and correctly ranked whatever the basis -- and the line says what is not known, so a
    reader can see the gap instead of assuming a default.

    Not in the shipped example: the published OpenAPI example round-trips through the
    model, which drops nulls, so an example carrying one could never equal its canonical
    file. The behaviour is proved here instead.
    """

    ranking = render_contribution_ranking_section(
        {
            "contribution_ranking": {
                "posture": "ready",
                "methodology": {"basis": None, "weighting_scheme": None},
                "total_portfolio_return_pct": "7.93",
                "presented_contribution_pct": "6.10",
                "presented_count": 1,
                "available_count": 1,
                "contributors": [
                    {"name": "Alphabet Inc Class A", "contribution_pct": "1.20"},
                ],
            }
        }
    )

    assert "#contribution-row(" in ranking, "the ranking stopped drawing over a missing basis"
    assert "not stated of fees" in ranking
    assert "weighted by not stated" in ranking
    assert "sum to the total" not in ranking, (
        "with the residual flag absent the line must claim neither reading"
    )


@pytest.mark.parametrize(
    ("posture", "extra", "expected"),
    [
        pytest.param(
            "empty",
            {},
            "No holding moved the portfolio measurably over this period.",
            id="empty-is-a-fact-about-the-portfolio",
        ),
        pytest.param(
            "unavailable",
            {},
            "Contribution could not be sourced for this period.",
            id="unavailable-is-a-fact-about-the-data",
        ),
        pytest.param(
            "unavailable",
            {"unusable_row_count": 7},
            "returned for 7 holdings and none of it could be read",
            id="unavailable-with-unreadable-rows-says-how-many",
        ),
    ],
)
def test_the_postures_do_not_read_alike(posture: str, extra: dict[str, Any], expected: str) -> None:
    """`empty` and `unavailable` are different statements and Report distinguishes them.

    Report found the third case while implementing: rows returned that none of which
    carry a usable value. Calling that `empty` would tell a reader the portfolio did
    nothing, when what happened is that the evidence could not be read.
    """

    section = render_contribution_ranking_section(
        {"contribution_ranking": {"posture": posture, "contributors": [], **extra}}
    )

    assert expected in section
    assert "#contribution-row(" not in section


def test_render_neither_ranks_nor_reconciles() -> None:
    """The ownership line, asserted rather than trusted.

    Report ranks, joins the names, chooses how many are presented and computes every
    figure in the reconciliation. Render reads them in the order given and states them.
    """

    ranking = {
        "posture": "ready",
        "methodology": {"basis": "GROSS", "weighting_scheme": "beginning weight"},
        "total_portfolio_return_pct": "5.00",
        "presented_contribution_pct": "9.99",
        "presented_count": 2,
        "available_count": 2,
        "contributors": [
            {"name": "Smaller effect", "contribution_pct": "0.10"},
            {"name": "Larger effect", "contribution_pct": "4.00"},
        ],
    }
    section = render_contribution_ranking_section({"contribution_ranking": ranking})

    # Report's order is kept even where Render could "improve" it, because the order is
    # a reporting decision and re-sorting here would silently disagree with the counts.
    assert section.index("Smaller effect") < section.index("Larger effect")
    # And the reconciliation states 9.99% even though the rows sum to 4.10%: the figure
    # describes the set Report presented, and recomputing it here would be Render doing
    # arithmetic on financial data.
    assert "9.99%" in section
    assert "GROSS" in section


MALFORMED_CONTRIBUTORS = [
    pytest.param("not a list", id="contributors-is-a-string"),
    pytest.param([["Alphabet", "1.20"]], id="entry-is-a-list"),
    pytest.param([{"contribution_pct": "1.20"}], id="entry-has-no-name"),
    pytest.param([{"name": "Alphabet Inc Class A"}], id="entry-has-no-contribution"),
]


@pytest.mark.parametrize("contributors", MALFORMED_CONTRIBUTORS)
def test_a_row_render_cannot_draw_is_dropped_rather_than_guessed_at(contributors: Any) -> None:
    """A contributor with no value cannot be ranked and must not be drawn as a zero.

    Report already drops those upstream -- "no data" and "no movement" are different
    statements and neither is a contribution of nothing. This is the boundary holding the
    same line for a package that arrives malformed anyway: `report_data` is untrusted,
    and the contract says what Report sends, not what will actually arrive.
    """

    section = render_contribution_ranking_section(
        {
            "contribution_ranking": {
                "posture": "ready",
                "contributors": contributors,
                "presented_count": 0,
                "available_count": 0,
            }
        }
    )

    assert "#contribution-row(" not in section
    assert "No holding moved the portfolio measurably" in section


def test_a_package_with_a_posture_render_does_not_know_presents_nothing() -> None:
    """Three postures are the contract. A fourth is a contract violation, not a default.

    Silence is right here rather than an empty state: Render cannot say whether the
    section is absent, empty or unreadable, and inventing one of the three would be a
    claim about the portfolio it has no basis for.
    """

    assert render_contribution_ranking_section({"contribution_ranking": {"posture": "maybe"}}) == ""
    assert render_contribution_ranking_section({"contribution_ranking": "ready"}) == ""
    assert render_contribution_ranking_section({}) == ""


def test_an_allocated_residual_says_the_rows_sum_to_the_total() -> None:
    """The other side of the flag. `residual_allocation_applied` is the only thing
    distinguishing "this ranking adds up" from "this ranking falls short", and both
    claims have to be sayable."""

    section = render_contribution_ranking_section(
        {
            "contribution_ranking": {
                "posture": "ready",
                "methodology": {
                    "basis": "NET",
                    "weighting_scheme": "average weight",
                    "residual_allocation_applied": True,
                },
                "total_portfolio_return_pct": "7.93",
                "presented_contribution_pct": "7.93",
                "presented_count": 1,
                "available_count": 1,
                "contributors": [{"name": "Alphabet Inc Class A", "contribution_pct": "1.20"}],
            }
        }
    )

    assert "The residual is allocated across contributors, so they sum to the total." in section
