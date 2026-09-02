"""The Portfolio scope panel says how much of the portfolio it is showing.

Five holdings drawn with weights and values, and nothing said the five were the largest of
forty-two. A concentrated and a diversified portfolio with the same five rows read the
same, and the only signal was weights not summing to 100% -- arithmetic the reader had to
do. The same subset-implying-completeness shape the contribution ranking had before #225.

And holdings from an unreconciled position set drew a byte-identical panel to clean ones.

Report states both (`holdings_presentation`, report#246); Render reads and infers nothing.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pypdf

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.holdings_presentation import render_holdings_scope_notes
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _document(holdings_presentation: dict[str, Any]) -> str:
    package = json.loads(GOLDEN.read_text(encoding="utf-8"))
    package["report_data"]["holdings_presentation"] = holdings_presentation
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


def test_a_subset_says_it_is_one_and_the_whole_says_nothing() -> None:
    """The pair from the contract: concentrated and diversified must not read alike.

    Five of forty-two covering 35.2% is a different panel from five of five -- and the
    complete panel draws no line, because "5 of 5" is furniture and furniture stops
    being read.
    """

    subset = _document(
        {
            "posture": "ready",
            "supportability_status": "ready",
            "presented_count": 3,
            "available_count": 42,
            "presented_weight_pct": "35.20",
            "notes": [],
        }
    )
    whole = _document(
        {
            "posture": "ready",
            "supportability_status": "ready",
            "presented_count": 3,
            "available_count": 3,
            "presented_weight_pct": "89.64",
            "notes": [],
        }
    )

    assert "These 3 of 42 holdings cover 35.20% of the portfolio." in subset
    assert "of the portfolio." not in whole
    assert "3 of 3" not in whole


def test_an_unestablished_weight_is_absent_from_the_sentence_never_zero() -> None:
    """`presented_weight_pct` absent means could-not-establish -- the two halves of the
    reconciliation fail independently, and a false "cover 0%" is worse than no figure."""

    document = _document(
        {
            "posture": "ready",
            "supportability_status": "ready",
            "presented_count": 3,
            "available_count": 42,
            "notes": [],
        }
    )

    assert "These are the 3 largest of 42 holdings." in document
    # The sentence carries no coverage clause at all -- not a zero, not a blank.
    assert "cover" not in document.split("These are the 3 largest")[1][:60]
    assert "cover 0" not in document


def test_empty_and_unavailable_do_not_produce_the_same_page() -> None:
    """A portfolio with no positions and holdings that could not be sourced are
    different facts, and both used to render as an identical empty list."""

    empty = _document({"posture": "empty", "supportability_status": "ready", "notes": []})
    unavailable = _document(
        {"posture": "unavailable", "supportability_status": "ready", "notes": []}
    )

    assert "The portfolio holds no positions as of the review date." in empty
    assert "Holdings could not be sourced for this report." in unavailable
    assert "could not be sourced" not in empty
    assert "holds no positions" not in unavailable


def test_unreconciled_holdings_do_not_read_like_clean_ones() -> None:
    """The defect with no visual difference today.

    `supportability_status` is Core's verdict, read from the field -- never inferred
    from the note count. Report's own prose carries the why.
    """

    partial = _document(
        {
            "posture": "ready",
            "supportability_status": "partial",
            "presented_count": 3,
            "available_count": 3,
            "presented_weight_pct": "89.64",
            "notes": [
                {
                    "code": "holdings_not_reconciled",
                    "severity": "warning",
                    "message": (
                        "Positions are drawn from an unreconciled intraday set and may be restated."
                    ),
                }
            ],
        }
    )

    assert "unreconciled intraday set" in partial


def test_a_partial_verdict_with_no_prose_is_still_said() -> None:
    """The verdict is Core's; a missing sentence does not soften it."""

    emitted = render_holdings_scope_notes(
        {
            "holdings_presentation": {
                "posture": "ready",
                "supportability_status": "partial",
                "presented_count": 3,
                "available_count": 3,
                "notes": [],
            }
        }
    )

    assert "have not been fully reconciled" in emitted


def test_a_package_predating_the_contract_adds_nothing() -> None:
    """Absent key means an older snapshot: the panel draws as it always did, and no
    line is invented about coverage nobody stated."""

    assert render_holdings_scope_notes({}) == ""
