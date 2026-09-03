"""The fee-drag line reaches the page in the agreed voice -- and never as a column.

report#247's decision, both halves: Report computes `performance_basis.fee_drag` from
raw captured returns (report#252); Render states it once under the period table. The
tests that matter were agreed with the contract: the sign is followed (a rebate period
must not be clamped into a cost), a genuine zero is a finding, an absent figure draws
nothing rather than a guessed drag, and the wording says "approximately" because
gross-minus-net is not exactly "fees".
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
from app.services.fee_drag import fee_drag_sentence, render_fee_drag_note
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _document(performance_basis: dict[str, Any] | None) -> str:
    package = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if performance_basis is None:
        package["report_data"].pop("performance_basis", None)
    else:
        package["report_data"]["performance_basis"] = performance_basis
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


def _basis(drag: str | None) -> dict[str, Any]:
    return {
        "return_basis": "NET",
        "fee_drag": None if drag is None else {"period": "YTD", "gross_minus_net_pp": drag},
    }


def test_the_banked_golden_states_the_drag_under_the_period_table() -> None:
    """The agreed sentence, on the performance page, after the period table and never
    as a table column -- the whole point of the decision was no gross column."""

    document = _document(_basis("0.42"))

    assert (
        "Net of fees; gross returns were higher by approximately 0.42pp over the period."
        in document
    )
    performance_page = document.split("Performance against benchmark")[1]
    table_region = performance_page.split("12-Month Cumulative Performance")[0]
    assert "Gross" not in table_region, "a gross column crept into the period table"


def test_the_sign_is_followed_never_clamped() -> None:
    """A rebate period (net above gross) arrives negative and must read as lower --
    silently hiding or flipping it would be a confident wrong statement about money."""

    assert fee_drag_sentence({"performance_basis": _basis("-0.15")}) == (
        "Net of fees; gross returns were lower by approximately 0.15pp over the period."
    )


def test_a_genuine_zero_is_a_finding() -> None:
    """ "Fees cost you nothing this period" is a statement; "we cannot say" is not."""

    assert fee_drag_sentence({"performance_basis": _basis("0.00")}) == (
        "Net of fees; gross and net returns were equal over the period."
    )


def test_an_absent_figure_draws_nothing_never_a_guess() -> None:
    """Absent gross upstream means fee_drag null; older packages carry no block at
    all. Both draw no line -- Render must not derive a drag from displayed numbers."""

    assert render_fee_drag_note({}) == ""
    assert render_fee_drag_note({"performance_basis": _basis(None)}) == ""
    assert render_fee_drag_note({"performance_basis": {"return_basis": "NET"}}) == ""
    document = _document({"return_basis": "NET", "fee_drag": None})
    assert "Net of fees; gross" not in document


def test_an_unreadable_figure_is_not_stated() -> None:
    assert render_fee_drag_note({"performance_basis": _basis("n/a")}) == ""
    assert render_fee_drag_note({"performance_basis": _basis("")}) == ""
