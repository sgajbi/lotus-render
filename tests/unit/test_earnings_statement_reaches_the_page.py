"""The earnings statement tells the truth about money, including what it does not know.

Report composes it (`earnings_statement`, report#251) and Render sums nothing. The test
that mattered most was committed when the contract was agreed: a truncated transaction
window makes the sums a floor, not a period total, and a floor presented as a total is a
false monetary statement on an archived document.
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
from app.services.earnings_statement import render_earnings_statement
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _document(statement: dict[str, Any] | None) -> str:
    package = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if statement is None:
        package["report_data"].pop("earnings_statement", None)
    else:
        package["report_data"]["earnings_statement"] = statement
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


def _ready_statement(**overrides: Any) -> dict[str, Any]:
    statement: dict[str, Any] = {
        "posture": "ready",
        "completeness": "complete",
        "income": {
            "transaction_count": 3,
            "gross": "48200.00",
            "withholding_tax": "-6100.00",
            "other_deductions": "-350.00",
            "net": "41750.00",
            "by_type": [
                {"income_type": "DIVIDEND", "net": "29450.00", "transaction_count": 2},
                {"income_type": "INTEREST", "net": "12300.00", "transaction_count": 1},
            ],
        },
        "realized_pnl": {
            "status": "present",
            "transaction_count": 2,
            "net": "40120.00",
            "gains": "52840.00",
            "losses": "-12720.00",
            "largest_gain": {
                "security_name": "ASML Holding NV",
                "amount": "38400.00",
                "transaction_date": "2026-03-12",
            },
            "largest_loss": None,
        },
        "methodology": {"basis": "settled", "tax_lot_jurisdiction_treatment": "not_sourced"},
        "notes": [],
    }
    statement.update(overrides)
    return statement


def test_the_statement_carries_both_halves_and_the_advisor_sentence() -> None:
    """Gross to net with the split, both realized sides, and the named largest gain --
    "you realized 38k, mostly from selling ASML in March" is the advisor sentence, and
    the name is Report's join, never Render's. The banked golden carries this shape."""

    document = _document(_ready_statement())

    assert "Period earnings" in document
    for fragment in (
        "Gross income 48,200.00",
        "Withholding tax -6,100.00",
        "Net income 41,750.00",
        "of which dividends 29,450.00",
        "Net realized 40,120.00",
        "Largest gain 38,400.00 ASML Holding NV (12 Mar 2026)",
    ):
        assert fragment in document, f"missing: {fragment}"


def test_a_truncated_window_renders_a_floor_and_never_a_total() -> None:
    """The committed test. The amounts are identical either way -- the posture is what
    changes their meaning, and presenting a floor as a period total would be a false
    monetary statement on an archived document."""

    document = _document(
        _ready_statement(
            completeness="window_truncated",
            reviewed_transaction_count=200,
            source_transaction_count=412,
        )
    )

    assert (
        "The portfolio earned at least the amounts shown, based on the 200 of 412 "
        "transactions reviewed." in document
    )
    statement_region = document.split("Period earnings")[1].split("Appendix")[0]
    assert "total" not in statement_region.lower(), (
        "a truncated statement used the word the floor sentence exists to forbid"
    )


def test_the_page_says_it_is_not_a_tax_document() -> None:
    """Tax-lot treatment is not sourced, so the statement must read as portfolio
    earnings -- a client who takes it to a tax adviser must find the disclaimer."""

    document = _document(_ready_statement())

    assert "not a tax document" in document
    assert "Figures are settled amounts in the reporting currency." in document


def test_a_pre_split_snapshot_draws_without_the_split_never_zero_dividends() -> None:
    """`income.by_type` absent on rerenders of pre-split snapshots: absent is not 0."""

    statement = _ready_statement()
    del statement["income"]["by_type"]

    document = _document(statement)

    assert "Gross income 48,200.00" in document
    assert "of which" not in document
    assert "dividends 0" not in document.lower()


def test_empty_and_unavailable_do_not_read_alike() -> None:
    """`empty` is a fact about the portfolio, `unavailable` about the data -- and per
    the contract, `empty` only ever arrives with `completeness: complete`, so the one
    sentence it draws is a whole-period claim Render never has to hedge."""

    empty = _document({"posture": "empty", "completeness": "complete", "notes": []})
    unavailable = _document({"posture": "unavailable", "notes": []})

    assert "received no income and realized no gains or losses" in empty
    assert "could not be composed" in unavailable
    assert "could not be composed" not in empty
    assert "received no income" not in unavailable


def test_a_package_without_the_block_draws_no_statement() -> None:
    """Older snapshots and undrdered sections: the page is exactly what it was."""

    assert render_earnings_statement({}) == ""
    document = _document(None)
    assert "Period earnings" not in document


def test_a_truncated_window_missing_its_counts_still_states_the_floor() -> None:
    """The truncation is the fact; the counts only size it. A malformed count must not
    quietly promote a floor back into a period statement."""

    emitted = render_earnings_statement(
        {
            "earnings_statement": _ready_statement(
                completeness="window_truncated", reviewed_transaction_count="many"
            )
        }
    )

    assert "earned at least the amounts shown; the transaction window was truncated" in emitted


def test_an_unknown_income_type_in_the_split_is_not_drawn() -> None:
    """The split's vocabulary is DIVIDEND and INTEREST; a row Render cannot label is
    dropped rather than drawn under a guessed heading -- and a sourced tax-lot treatment
    drops the not-a-tax-document sentence, which exists only while that is true."""

    statement = _ready_statement()
    statement["income"]["by_type"].append(
        {"income_type": "ROYALTY", "net": "5.00", "transaction_count": 1}
    )
    statement["methodology"] = {"basis": "settled", "tax_lot_jurisdiction_treatment": "sourced"}

    emitted = render_earnings_statement({"earnings_statement": statement})

    assert "ROYALTY" not in emitted and "royalty" not in emitted
    assert "not a tax document" not in emitted
