"""The appendix carries what the document uses, and no figures of its own.

It used to be six fixed pages printed identically in every document: definitions of ESG
attributes, private markets, hedge funds, real estate, an income overview and a
portfolio health check that this report does not render, and none of the risk measures
it does. A reader looking up "Tracking error" found nothing.

It also published six exchange rates and a table of expected returns, volatilities and
drawdowns that appear nowhere in the render package -- figures no one supplied, carrying
a validity date two years before the reports that printed them. Those are the assertions
at the bottom of this file: not that the appendix is shorter, but that it invents
nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.services.appendix_glossary import (
    APPENDIX_GLOSSARY,
    all_glossary_keys,
    applicable_glossary,
)
from app.services.typst_contexts import requested_section_keys
from app.services.typst_tables import render_appendix_glossary_groups

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")
TEMPLATE_ROOT = Path("templates/typst/portfolio-review/v1")
GLOSSARY_COPY = TEMPLATE_ROOT / "_appendix_text.typ"
APPENDIX_TEMPLATE = TEMPLATE_ROOT / "_appendix.typ"


def _golden_report_data() -> dict[str, Any]:
    package: dict[str, Any] = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    report_data: dict[str, Any] = package["report_data"]
    return report_data


def _titles(report_data: dict[str, Any]) -> list[str]:
    return [group.title for group in applicable_glossary(report_data)]


def _keys(report_data: dict[str, Any]) -> set[str]:
    return {entry.key for group in applicable_glossary(report_data) for entry in group.entries}


def test_every_key_the_selection_can_ask_for_exists_in_the_template() -> None:
    """A key with no copy behind it is a failed render, not a missing paragraph.

    The selection lives in Python and the wording in the template, so nothing but a test
    holds the two together. Typst resolves `GLOSSARY.at(key)` at compile time and a
    missing key fails the whole document, not just its appendix.
    """

    copy = GLOSSARY_COPY.read_text(encoding="utf-8")
    declared = set(re.findall(r"^  ([a-z_]+): \(", copy, re.M))
    selectable = set(all_glossary_keys())

    assert declared, "no glossary entries were parsed out of the template copy"
    assert not selectable - declared, (
        "these keys can be selected but have no copy in the template: "
        f"{sorted(selectable - declared)}"
    )
    assert not declared - selectable, (
        f"these entries are written but can never be selected: {sorted(declared - selectable)}"
    )


def test_the_golden_report_takes_the_terms_it_uses() -> None:
    """The document draws performance, risk, allocation, positions and transactions."""

    assert _titles(_golden_report_data()) == [
        "Performance measurement",
        "Risk measures",
        "Asset allocation",
        "Positions",
        "Transactions",
    ]


def test_a_section_the_document_omits_takes_no_definitions_with_it() -> None:
    """The whole point: an entry explains something on a page, or it is not printed."""

    report_data = _golden_report_data()
    report_data["transactions"] = []
    report_data["top_holdings"] = []

    titles = _titles(report_data)

    assert "Transactions" not in titles
    assert "Positions" not in titles
    assert "Performance measurement" in titles, "unrelated groups were dropped too"


def test_a_portfolio_with_no_benchmark_is_not_told_what_a_benchmark_is() -> None:
    """Benchmark, relative return, beta, tracking error and the information ratio are
    all drawn only against a benchmark, so all of them go together."""

    report_data = _golden_report_data()
    report_data["performance_periods"] = [{"label": "YTD", "portfolio_return_pct": "3.93%"}]
    report_data["performance_monthly_history"] = []
    report_data["performance_annual_history"] = []
    report_data["risk_summary"] = {"volatility_pct": "12.00%", "value_at_risk_pct": "-2.00%"}

    keys = _keys(report_data)

    assert {
        "benchmark",
        "relative_return",
        "beta",
        "tracking_error",
        "information_ratio",
    } & keys == set()
    assert {"volatility", "value_at_risk"} <= keys, "the measures that are shown lost their notes"


def test_a_measure_reported_as_absent_takes_no_definition() -> None:
    """Report data spells an absent measure several ways and they all mean no card."""

    report_data = _golden_report_data()
    report_data["risk_summary"] = {
        "volatility_pct": "12.00%",
        "beta": "",
        "tracking_error_pct": None,
        "information_ratio": "Not available",
        "value_at_risk_pct": "-",
    }

    keys = _keys(report_data)

    assert "volatility" in keys
    assert {"beta", "tracking_error", "information_ratio", "value_at_risk"} & keys == set()


def test_a_report_with_nothing_to_explain_produces_no_groups() -> None:
    """An empty array, so the template shows its empty state rather than a bare heading."""

    assert applicable_glossary({}) == []
    assert render_appendix_glossary_groups({}) == "()"


def test_the_emitted_groups_carry_only_titles_and_keys() -> None:
    """The wording stays in the template; only the selection crosses the boundary."""

    emitted = render_appendix_glossary_groups(_golden_report_data())

    assert emitted.startswith("(") and emitted.endswith(")")
    assert '(title: "Risk measures", keys: ("volatility", "beta"' in emitted
    # A definition's text would be a governance problem: it would change without moving
    # the template digest.
    assert "annualised standard deviation" not in emitted


def test_a_group_is_never_emitted_empty() -> None:
    """A heading over nothing is one more thing for a reader to read and discard."""

    for report_data in ({}, {"transactions": [{"a": 1}]}, _golden_report_data()):
        assert all(group.entries for group in applicable_glossary(report_data))


def test_the_glossary_declares_no_duplicate_keys() -> None:
    """A key in two groups would print the same definition twice."""

    keys = all_glossary_keys()

    assert len(keys) == len(set(keys)), "a glossary key appears in more than one group"


def test_every_group_is_reachable() -> None:
    """A group no report data can trigger is copy that ships and never renders."""

    for group in APPENDIX_GLOSSARY:
        subjects = {entry.subject for entry in group.entries}
        assert subjects, f"group '{group.title}' declares no entries"


# A rate carries more decimals than prose ever does; a percentage in the copy is a
# figure about a portfolio. `100%` in the layout file is a column width, so the
# percentage rule applies only to the copy, where every number is editorial.
@pytest.mark.parametrize(
    ("pattern", "what", "templates"),
    [
        (r"\d+\.\d{4,}", "an exchange rate", (GLOSSARY_COPY, APPENDIX_TEMPLATE)),
        (r"\d+(?:\.\d+)?\s?%", "a percentage figure", (GLOSSARY_COPY,)),
    ],
)
def test_the_appendix_publishes_no_figure_of_its_own(
    pattern: str, what: str, templates: tuple[Path, ...]
) -> None:
    """The appendix must not carry data. It used to carry six exchange rates and a table
    of expected returns, volatilities and drawdowns -- none of them in the render
    package, and dated two years before the reports that printed them.

    Render does not have those numbers, so it cannot publish them. If they are ever
    wanted again they arrive as report data and are drawn from it.
    """

    for template in templates:
        found = re.findall(pattern, template.read_text(encoding="utf-8"))
        assert not found, (
            f"{template.name} contains what looks like {what}: {found[:5]}. The appendix "
            "explains the document's terms and publishes none of its own figures."
        )


def test_an_explicitly_requested_appendix_is_still_dropped_when_it_explains_nothing() -> None:
    """Asking for the section does not create something for it to say.

    The report may name the sections it wants, and "additional-information" is one of
    them. A report whose optional collections are all empty selects no entries, and the
    section would be a page stating that no notes apply.
    """

    requested = ["cover", "contents", "overview", "appendix"]

    assert "appendix" in requested_section_keys(requested, include_appendix=True)
    assert "appendix" not in requested_section_keys(requested, include_appendix=False)
    assert requested_section_keys(requested, include_appendix=False) == [
        "cover",
        "contents",
        "overview",
    ], "dropping the appendix disturbed the sections around it"
