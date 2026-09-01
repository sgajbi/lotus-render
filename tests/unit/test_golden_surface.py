"""The banked golden surface must cover the paths most likely to break, not only the
default happy path.

Three of the four templates bank a single document built from single-element lists, and
the portfolio-review paths most exposed to change -- the two advisory sections and every
empty-data fallback -- had no compiled proof at all: they were asserted as `%PDF` magic
bytes or as Python strings, neither of which notices a layout regression (issue #118).

These tests pin what each added fixture is *for*, so a fixture cannot quietly drift into
a duplicate of the base document while still passing its fingerprint assertion.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_PRODUCER_FIXTURES = Path("tests/golden/producer-fixtures.v1.json")
BASE_SAMPLE = "golden-portfolio-review-en-SG-private-banking-v1"
ADVISORY_NARRATIVE_SAMPLE = "golden-portfolio-review-advisory-narrative-en-SG-private-banking-v1"
ADVISOR_MEMO_SAMPLE = "golden-portfolio-review-advisor-memo-en-SG-private-banking-v1"
DEGRADED_SAMPLE = "golden-portfolio-review-degraded-en-SG-private-banking-v1"


def _fixtures() -> dict[str, dict[str, str]]:
    manifest = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    return {fixture["golden_sample_id"]: fixture for fixture in manifest["fixtures"]}


def _service() -> TypstRenderService:
    settings = Settings()
    return TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )


def _package(sample_id: str) -> RenderPackage:
    return RenderPackage.model_validate_json(
        Path(_fixtures()[sample_id]["package_path"]).read_text(encoding="utf-8")
    )


def _template_context(sample_id: str) -> dict[str, str]:
    return _service()._build_template_context(_package(sample_id))


def _rendered_text(sample_id: str) -> str:
    """The text of the compiled document, which is the only thing a reader has."""
    rendered = _service().render(_package(sample_id))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_every_banked_fixture_carries_a_fingerprint_literal() -> None:
    """A fixture without a banked fingerprint has no independent oracle (issue #108)."""

    missing = [
        sample_id
        for sample_id, fixture in _fixtures().items()
        if not fixture.get("bounded_determinism_fingerprint")
    ]
    assert not missing, f"these fixtures bank no fingerprint literal: {missing}"


@pytest.mark.parametrize(
    "sample_id", [ADVISORY_NARRATIVE_SAMPLE, ADVISOR_MEMO_SAMPLE, DEGRADED_SAMPLE]
)
def test_added_fixtures_render_a_different_document_from_the_base(sample_id: str) -> None:
    """Each added fixture must exercise a path the base golden does not.

    A fixture that renders the same document as the base proves nothing about the path it
    was added for, and would still pass its own fingerprint assertion.
    """

    fixtures = _fixtures()
    assert (
        fixtures[sample_id]["bounded_determinism_fingerprint"]
        != fixtures[BASE_SAMPLE]["bounded_determinism_fingerprint"]
    )


def test_the_advisory_fixtures_actually_select_their_advisory_sections() -> None:
    narrative = _template_context(ADVISORY_NARRATIVE_SAMPLE)["REPORT_SECTIONS"]
    memo = _template_context(ADVISOR_MEMO_SAMPLE)["REPORT_SECTIONS"]
    base = _template_context(BASE_SAMPLE)["REPORT_SECTIONS"]

    assert "reviewed-advisory-narrative-page()" in narrative
    assert "advisor-proposal-memo-page()" in memo
    assert "reviewed-advisory-narrative-page()" not in base
    assert "advisor-proposal-memo-page()" not in base


def test_the_degraded_fixture_renders_the_empty_data_fallbacks() -> None:
    """Read off the page, because the context is not the document.

    The ~40 fallback strings were first asserted as Python strings; this then checked the
    built context, which is closer and still not it. A key can carry a fallback and reach
    no template -- "No governed holdings available." did exactly that, in `HOLDING_ROWS`,
    which nothing substituted. Passing on a string no reader could see is the failure this
    test exists to rule out, so it renders.
    """

    document = _rendered_text(DEGRADED_SAMPLE)

    for fallback in (
        "No position detail available.",
        "No transaction detail available.",
        "No allocation detail available.",
    ):
        assert fallback in document, f"the degraded document never shows {fallback!r}"


def test_the_golden_package_and_the_shipped_example_do_not_drift() -> None:
    """The portfolio-review package is committed twice, and both copies are load-bearing.

    `src/app/contracts/examples/` is the canonical example the OpenAPI gate publishes;
    `tests/golden/portfolio-review/v1/` is the fixture the governance gate requires at a
    fixed path. Shipping code must not import from `tests/`, so the duplication stands --
    but it must not become drift, which is what #55 was about for a different pair.
    """

    golden = Path("tests/golden/portfolio-review/v1/render-package.json").read_bytes()
    example = Path(
        "src/app/contracts/examples/portfolio-review-render-package.v1.json"
    ).read_bytes()

    assert golden == example, (
        "the golden portfolio-review package and the shipped OpenAPI example have diverged; "
        "they are the same document and must be updated together."
    )


def test_no_golden_fixture_carries_payload_no_template_reads() -> None:
    """Inert fixture payload misrepresents what the goldens prove.

    `portfolio_memory` sat in three packages while zero lines of `src/` or `templates/`
    referenced it: removing it left every banked fingerprint unchanged, which is the
    proof it was never rendered.
    """

    inert = "portfolio_memory"
    carriers = [
        str(path)
        for path in sorted(Path("tests/golden").rglob("render-package.json"))
        if inert in json.loads(path.read_text(encoding="utf-8")).get("report_data", {})
    ]

    assert not carriers, f"{inert} is read by no template but is carried by: {carriers}"


PORTFOLIO_TEMPLATE = Path("templates/typst/portfolio-review/v1")


def test_no_page_reference_is_a_literal_in_a_template() -> None:
    """The contents page must describe the document it is bound into.

    Its page references were string literals, and they were already wrong in every
    document carrying an advisory section: that section shifts everything after it, so a
    17-page render still claimed the appendix began on p. 11 (issue #137).
    """

    offenders: list[str] = []
    for path in sorted(PORTFOLIO_TEMPLATE.glob("*.typ")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r'"p\.\s*\d+"', line):
                offenders.append(f"{path.name}:{lineno} {line.strip()[:60]}")

    assert not offenders, (
        "these page references are hard-coded, so they cannot follow the sections the "
        f"document actually contains: {offenders}"
    )


def test_every_listed_section_plants_a_marker_for_the_contents_page() -> None:
    """A section with no marker is invisible to the computed contents page."""

    from app.services.typst_contexts import PORTFOLIO_REVIEW_SECTION_CALLS

    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PORTFOLIO_TEMPLATE.glob("*.typ"))
    )
    markers = re.findall(r'#section-marker\("([^"]+)"', sources)
    assert markers, "no section markers were found; the contents page would list nothing."

    # cover and contents are the front matter and are deliberately not listed.
    listed = {
        call
        for key, call in PORTFOLIO_REVIEW_SECTION_CALLS.items()
        if key not in {"cover", "contents"}
    }
    marked = {
        call
        for call in listed
        # Comment lines between the opening bracket and the marker are skipped: a
        # comment is not a statement, and requiring the marker on the very next line
        # made explaining a decision at the marker fail the check.
        if re.search(
            rf"#let {re.escape(call[:-2])}\(\) = \[\s*\n(?:\s*//[^\n]*\n)*\s*#section-marker",
            sources,
        )
    }
    assert marked == listed, (
        "these section pages plant no marker, so the contents page cannot list them: "
        f"{sorted(listed - marked)}"
    )


def test_no_emitter_hard_codes_a_colour() -> None:
    """Colour belongs to the template's palette, not to the Python that feeds it.

    Every "not available" line inlined `rgb(104, 118, 132)` -- a 21st colour matching no
    theme token (`slate` is `#5B6770`), so the empty state was an off-palette grey no
    template could restyle. The emitters now call an `empty-state` component and the
    theme owns the colour.
    """

    emitters = (
        Path("src/app/services/typst_tables.py"),
        Path("src/app/services/typst_fragments.py"),
        Path("src/app/services/typst_contexts.py"),
    )
    offenders: list[str] = []
    for path in emitters:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"rgb\(|#[0-9a-fA-F]{6}", line):
                offenders.append(f"{path.name}:{lineno} {line.strip()[:60]}")

    assert not offenders, (
        f"these emitters hard-code a colour instead of using a theme component: {offenders}"
    )
