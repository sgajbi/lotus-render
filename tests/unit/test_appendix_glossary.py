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
from app.services.appendix_glossary import (
    APPENDIX_GLOSSARY,
    all_glossary_keys,
    applicable_glossary,
)
from app.services.render_intake import RenderIntakeService
from app.services.typst_contexts import requested_section_keys
from app.services.typst_rendering import TypstRenderService
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


def _rendered_text(package: dict[str, Any]) -> str:
    """The compiled document's text. The appendix and the table only meet on the page."""
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


# Every supplemental view the page can draw, and the term the appendix owes a reader who
# meets it. The page has room for exactly one, chosen by priority, so these are the six
# documents this fixture family can produce.
SUPPLEMENTAL_VIEW_CASES = [
    pytest.param("by_currency", "By currency", "Currency exposure", id="by-currency"),
    pytest.param("by_region", "By region", "Regional exposure", id="by-region"),
    pytest.param("by_sector", "By sector", "Sector exposure", id="by-sector"),
    pytest.param("by_country", "By country", "Country exposure", id="by-country"),
    pytest.param("by_product_type", "By product type", "Product type exposure", id="by-product"),
    pytest.param("by_rating", "By rating", "Credit rating exposure", id="by-rating"),
]


@pytest.mark.parametrize(("key", "title", "term"), SUPPLEMENTAL_VIEW_CASES)
def test_the_appendix_defines_the_supplemental_view_the_page_drew(
    key: str, title: str, term: str
) -> None:
    """Which view is drawn and which is defined used to be decided separately.

    The table took the first breakdown with rows, in a priority order Render held. The
    glossary added the currency subject whenever *any* non-asset-class breakdown had rows
    and always named currency -- so a package carrying only `by_sector` drew a sector
    table and defined "Currency exposure". Both halves were internally consistent; only
    the page showed the disagreement.

    Both now read `allocation_presentation`, so they cannot disagree by construction.
    This drives it through the package, which is also what a caller ordering that
    dimension produces: the rows for every dimension still ship, and only the named one
    is presented.
    """

    package = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    package["report_data"]["allocation_breakdowns"][key] = [
        {"name": "Alpha", "weight_pct": "60.00%", "market_value": "6000"},
        {"name": "Beta", "weight_pct": "40.00%", "market_value": "4000"},
    ]
    package["report_data"]["allocation_presentation"] = {
        "resolved_by": "caller_request",
        "dimensions": [
            {
                "dimension": key.removeprefix("by_"),
                "package_key": key,
                "posture": "ready",
            }
        ],
    }

    document = _rendered_text(package)
    strays = [
        str(case.values[2])
        for case in SUPPLEMENTAL_VIEW_CASES
        if str(case.values[2]) != term and str(case.values[2]) in document
    ]

    assert title in document, f"the page does not draw the {title!r} table"
    assert term in document, f"the page draws {title!r} and the appendix never defines {term!r}"
    assert not strays, f"the appendix defines a view the page did not draw: {strays}"


BENCHMARK_TERMS = ("Benchmark", "Relative return")


def _without_benchmark(package: dict[str, Any]) -> dict[str, Any]:
    for key in ("performance_periods", "performance_monthly_history", "performance_annual_history"):
        for row in package["report_data"].get(key) or ():
            for field in (
                "benchmark_return_pct",
                "benchmark_cumulative_twr",
                "benchmark_cumulative_twr_pct",
                "relative_return_pct",
            ):
                row.pop(field, None)
    return package


def test_a_document_with_no_benchmark_draws_no_benchmark_columns() -> None:
    """A column that is "Not available" on every line is a promise the data cannot keep.

    The table drew Period / Portfolio / Benchmark / Relative whenever there were periods
    at all, under the heading "Performance against benchmark (TWR)". With no benchmark
    that rendered three rows of "Not available Not available" -- while the appendix, which
    asked the stricter question, withheld both definitions for the same document. The
    mismatch was the symptom; the table was the fault.

    Both now read `benchmark_columns_are_drawn`, so the columns and their definitions
    appear together or not at all.
    """

    package = _without_benchmark(json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8")))

    document = _rendered_text(package)
    periods = document[document.find("Period returns (TWR)") :][:200]

    assert "Period returns (TWR)" in document, "the period returns are gone, not just the columns"
    assert "Performance against benchmark" not in document
    assert "Not available" not in periods, f"a column of nothing was drawn: {periods!r}"
    assert "Period returns and return history" in document, "the marker still promises a benchmark"
    for term in BENCHMARK_TERMS:
        assert term not in document, f"the appendix defines {term!r} for a document without one"


def test_a_document_with_a_benchmark_draws_the_columns_and_defines_them() -> None:
    """The other direction, so the fix cannot be "never draw a benchmark"."""

    document = _rendered_text(json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8")))
    periods = document[document.find("Performance against benchmark") :][:200]

    assert "Performance against benchmark (TWR)" in document
    assert "Not available" not in periods, f"the benchmark columns are empty: {periods!r}"
    for term in BENCHMARK_TERMS:
        assert term in document, f"the page draws a benchmark and never defines {term!r}"


def test_a_benchmark_on_the_chart_alone_defines_the_term_and_not_the_relative_return() -> None:
    """The boundary between the two questions, which is why there are two of them.

    The chart plots a benchmark line from the monthly series; the table draws Benchmark
    and Relative from the period rows. A package can carry one and not the other, and
    then "Benchmark" is on the page and "Relative return" is not -- the chart has no
    relative line to explain.

    Asking one question for both is what defined "Benchmark" off the back of
    `performance_annual_history`, which draws no benchmark at all: `_performance_chart_row`
    reads `twr_pct` and `cumulative_twr_pct` and nothing else.
    """

    package = _without_benchmark(json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8")))
    for row in package["report_data"]["performance_monthly_history"]:
        row["benchmark_cumulative_twr"] = row["cumulative_twr_pct"]

    document = _rendered_text(package)

    assert "Period returns (TWR)" in document, "the table has no benchmark and drew one"
    assert "Benchmark" in document, "the chart plots a benchmark line and never defines it"
    assert "Relative return" not in document, "nothing on the page draws a relative return"
