"""AI-drafted narrative, accepted by a named reviewer, placed without being changed.

`lotus-report` refused PDF orders carrying this section rather than dropping it silently,
because Render had no template for it (report#166). This is that template, and these read
the rendered page rather than the context that built it.

Three things make this section different from the two advisory pages beside it:

- **The prose is the least trusted input the service takes.** It is drafted by lotus-ai,
  and even accepted it is not authored by anyone who knows what Typst markup does. The
  shared escaper covers every markup token, but this reads it back off a page rather than
  trusting it from here.
- **The provenance sentence is content, not chrome.** `lotus-report` composes it -- who
  accepted the commentary, when, and from which run -- and Render only places it. A
  provenance line orphaned onto the next page attributes narrative to whatever precedes
  it there, which is worse than no line at all.
- **Tone is a semantic, not a string to print.** It resolves through `TONE_PALETTE` at
  compile time, so an unrecognised tone fails the whole document rather than one point.
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

COMMENTARY_PACKAGE = Path("tests/golden/portfolio-review/v1/advisor-commentary/render-package.json")
BASE_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")


def _service() -> TypstRenderService:
    settings = Settings()
    return TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )


def _pages(package: dict[str, object]) -> list[str]:
    rendered = _service().render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return [page.extract_text() for page in reader.pages]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.fixture(scope="module")
def commentary_pages() -> list[str]:
    return _pages(json.loads(COMMENTARY_PACKAGE.read_text(encoding="utf-8")))


def test_the_section_carries_all_four_of_its_parts(commentary_pages: list[str]) -> None:
    """Summary, talking points, risks and provenance -- what Report agreed to send."""

    document = _flat("\n".join(commentary_pages))

    assert "Advisor commentary" in document
    assert "The portfolio returned 7.93% year to date" in document, "the summary is missing"
    assert "Equity selection carried the period" in document, "a talking point is missing"
    assert "Cash is below the operating floor" in document, "a risk is missing"
    assert "Commentary generated with AI assistance and reviewed by" in document, (
        "the provenance sentence is missing, and it is required output"
    )


def test_the_tone_survives_as_a_word_and_not_only_as_a_colour(
    commentary_pages: list[str],
) -> None:
    """These documents are printed, and a colour-only encoding says nothing in monochrome.

    All three tones in one fixture, because a vocabulary tested at one value is a
    vocabulary tested nowhere.
    """

    document = _flat("\n".join(commentary_pages))

    for tone in ("POSITIVE", "WARNING", "NEUTRAL"):
        assert tone in document, f"the {tone.lower()} tone is not readable without colour"


def test_the_grounding_of_a_claim_is_on_the_page(commentary_pages: list[str]) -> None:
    """An AI-drafted claim with no visible grounding is an assertion.

    lotus-ai supplies metric, value and source for each ref and lotus-report drops any
    that is incomplete, so what arrives is whole and can be shown as it stands.
    """

    document = _flat("\n".join(commentary_pages))

    assert "Grounded on:" in document
    assert "YTD TWR 7.93% (perf:ytd:twr)" in document
    # And the point that cites nothing is marked, not merely missing a line. This is the
    # half that was absent: the test passed while an ungrounded claim was distinguishable
    # only by contrast with the grounded ones beside it.
    assert "NOT CHECKABLE" in document


def test_the_page_names_lotus_ai_as_the_source(commentary_pages: list[str]) -> None:
    """The boundary panel was reused verbatim from the narrative page and said
    lotus-advise -- on a page whose content comes from lotus-ai. A provenance statement
    that names the wrong system is worse than none, because it will be believed."""

    document = _flat("\n".join(commentary_pages))

    assert "supplied by lotus-ai through lotus-report" in document
    assert "AI-assisted commentary accepted by a named reviewer" in document


MARKUP_PROBES = (
    "5~10bp",
    "*not bold*",
    "_not emphasis_",
    "= not a heading",
    "- not a bullet",
    "/ not a term",
    "a<label>b",
    "#panic",
    "$x$",
)


def test_commentary_markup_reaches_the_page_as_text() -> None:
    """The least trusted input the service takes, read back off the page.

    The shared escaper covers every markup token and is tested in its own right. This
    exists because accepted AI prose is where a regression would land first and be least
    visible: a `*` pair silently emboldens and disappears, and a line beginning `/ ` fails
    the compile outright.
    """

    package = json.loads(COMMENTARY_PACKAGE.read_text(encoding="utf-8"))
    commentary = package["report_data"]["advisor_commentary"]
    commentary["grounded_summary"] = " ".join(MARKUP_PROBES)
    commentary["talking_points"][0]["detail"] = "\n".join(MARKUP_PROBES)

    document = _flat("\n".join(_pages(package)))

    missing = [probe for probe in MARKUP_PROBES if _flat(probe) not in document]
    assert not missing, (
        f"the document does not say {missing}. Typst read them as markup and drew something else."
    )


def test_the_provenance_sentence_is_never_split_across_pages() -> None:
    """A provenance line orphaned from its commentary attributes it to the wrong run.

    Forced across a page boundary by twelve long talking points. The sentence is one
    unbreakable block, so it lands whole on one page -- the check is that no page holds
    only part of it.
    """

    package = json.loads(COMMENTARY_PACKAGE.read_text(encoding="utf-8"))
    commentary = package["report_data"]["advisor_commentary"]
    template = json.dumps(commentary["talking_points"][0])
    commentary["talking_points"] = [
        {**json.loads(template), "headline": f"Driver {index}"} for index in range(12)
    ]

    pages = _pages(package)
    opening = "Commentary generated with AI assistance"
    closing = "run abr_run_0091."
    carrying = [index for index, page in enumerate(pages, 1) if opening in _flat(page)]

    assert len(carrying) == 1, f"the provenance sentence appears on pages {carrying}"
    assert closing in _flat(pages[carrying[0] - 1]), (
        "the provenance sentence starts on one page and ends on another; a reader on the "
        "second page cannot tell which commentary it describes"
    )


def test_a_package_without_commentary_draws_no_section_and_no_disclosure() -> None:
    """An absent commentary is absent, not an empty frame with AI language in it.

    The base golden carries none. Nothing about AI assistance should appear on it -- a
    disclosure for content that is not there is the same defect as a definition for a
    dimension that is not drawn.
    """

    document = _flat("\n".join(_pages(json.loads(BASE_PACKAGE.read_text(encoding="utf-8")))))

    assert "Advisor commentary" not in document
    assert "AI assistance" not in document
    assert "Talking points" not in document


def test_a_package_carrying_two_optional_sections_draws_both() -> None:
    """The default section list enumerated combinations, and lost one.

    There was one hand-written tuple per optional section and an if/elif choosing between
    them, so a package with an approved advisory narrative AND an approved advisor memo
    drew only the memo -- the memo branch won and the narrative was not in its tuple:

        narrative only: [... 'advisory_narrative', 'appendix']
        memo only     : [... 'advisor_memo', 'appendix']
        BOTH included : [... 'advisor_memo', 'appendix']     <- the narrative is gone

    Nothing tested that combination, and adding commentary as a third optional section
    would have made it eight. One order filtered by what the package carries cannot lose
    a section, because it never chooses between them.
    """

    from app.services.typst_contexts import requested_section_keys

    both = requested_section_keys(None, included={"advisory_narrative", "advisor_memo"})
    all_three = requested_section_keys(
        None, included={"advisory_narrative", "advisor_memo", "advisor_commentary"}
    )

    assert both.index("advisory_narrative") < both.index("advisor_memo"), (
        "a package carrying both optional sections must draw both, in document order"
    )
    assert all_three[-4:] == [
        "advisory_narrative",
        "advisor_memo",
        "advisor_commentary",
        "appendix",
    ]


def test_an_accepted_commentary_with_nothing_in_it_says_so() -> None:
    """`included` with empty lists is not the same as absent, and both are real.

    Report sends `status: included` once a reviewer has accepted a run. A run can be
    accepted and carry no talking points -- coverage may be partial, or the reviewer may
    have removed them. The section is drawn because a reviewer accepted something, and it
    says what is not there rather than showing an empty frame.
    """

    from app.services.typst_fragments import render_commentary_points

    empty = render_commentary_points(
        {"status": "included", "talking_points": []},
        "talking_points",
        empty_message="No talking points were supplied with the accepted commentary.",
    )
    absent = render_commentary_points(
        {"status": "not_supplied"},
        "talking_points",
        empty_message="No talking points were supplied with the accepted commentary.",
    )

    assert "No talking points were supplied" in empty
    assert absent == "", (
        "a package with no commentary built a placeholder no document draws, which the "
        "empty-block metric then counted"
    )


def test_a_point_with_neither_headline_nor_detail_is_not_drawn() -> None:
    """An entry with no words is not a talking point, and drawing its tone bar would
    put a coloured rule on the page attached to nothing."""

    from app.services.typst_fragments import render_commentary_points

    rendered = render_commentary_points(
        {
            "status": "included",
            "talking_points": [
                {"headline": "", "detail": "", "tone": "warning"},
                {"headline": "Real point", "detail": "With a body.", "tone": "neutral"},
            ],
        },
        "talking_points",
        empty_message="none",
    )

    assert rendered.count("#commentary-point(") == 1
    assert "Real point" in rendered


def test_a_page_where_nothing_is_grounded_still_says_so() -> None:
    """The case contrast cannot signal, and the reason the posture exists.

    An ungrounded point drew exactly like a grounded one minus its "Grounded on:" line.
    A reader seeing three grounded points and one bare one notices; a reader seeing a
    page where none are grounded has nothing to compare against and cannot tell that
    grounding was ever expected. Absence is legible only beside presence -- the weakest
    possible signal, and it fails exactly when the problem is worst.

    Presence of a marker does not have that property.
    """

    package = json.loads(COMMENTARY_PACKAGE.read_text(encoding="utf-8"))
    commentary = package["report_data"]["advisor_commentary"]
    for key in ("talking_points", "risks_and_exceptions"):
        for point in commentary[key]:
            point["evidence_refs"] = []
            point["grounding"] = "ungrounded"

    document = _flat("\n".join(_pages(package)))

    assert "Grounded on:" not in document, "the fixture did not reach the all-ungrounded case"
    assert document.count("NOT CHECKABLE") == 4, (
        "a page where nothing is checkable has to say so on every claim, because there is "
        "no grounded point left to contrast against"
    )


def test_grounding_is_read_from_the_package_and_never_derived() -> None:
    """Report states it; Render must not work it out from the refs.

    If Render infers what Report states, the page can contradict the lineage archived
    beside it. A point carrying refs and a stated grounding of `ungrounded` draws as
    ungrounded: Report knows something about those refs that Render does not, and the
    archived record is the one a reader would be held to.
    """

    package = json.loads(COMMENTARY_PACKAGE.read_text(encoding="utf-8"))
    package["report_data"]["advisor_commentary"]["talking_points"][0]["grounding"] = "ungrounded"

    document = _flat("\n".join(_pages(package)))

    assert document.count("NOT CHECKABLE") == 2, (
        "the point Report called ungrounded is drawn as grounded, so Render counted its "
        "refs instead of reading the posture"
    )


def test_an_unrecognised_grounding_is_treated_as_not_checkable() -> None:
    """The conservative reading, because the two errors are not symmetric.

    Telling a reader a claim is checkable when it is not invites them to trust it;
    telling them it is not checkable when it is costs them a second look.
    """

    from app.services.typst_fragments import render_commentary_points

    rendered = render_commentary_points(
        {
            "status": "included",
            "talking_points": [
                {"headline": "H", "detail": "D", "tone": "neutral", "grounding": "probably"}
            ],
        },
        "talking_points",
        empty_message="none",
    )

    assert '"ungrounded"' in rendered
