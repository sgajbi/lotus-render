"""Why a risk measure is missing, said on the page instead of "Not available" five ways.

`missing_benchmark` is permanent -- a benchmark-relative measure is meaningless for this
mandate -- and `risk_upstream_failure` means re-run the report. One string stood for both,
and a reader could not tell a statement about the mandate from one about the data (#227).

Report states `risk_posture` (report#238) with `affected_measures` per note (report#240),
derived from the constant that decides which metrics are benchmark-relative -- a list
Render must not copy, because a copy goes stale when the requested metric set moves.
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
from app.services.render_intake import RenderIntakeService
from app.services.risk_supportability import render_risk_supportability_notes
from app.services.typst_rendering import TypstRenderService

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _document(risk_posture: dict[str, Any] | None) -> str:
    package = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if risk_posture is None:
        package["report_data"].pop("risk_posture", None)
    else:
        package["report_data"]["risk_posture"] = risk_posture
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


def test_a_mandate_fact_names_the_measures_it_covers_once() -> None:
    """One fact about the mandate covering three measures reads as one sentence.

    Per-cell marking would repeat it three times and invite a reader to think three
    separate things went wrong. The measure names come from Report's `affected_measures`
    and Render's own panel labels -- Render holds no copy of which metrics are
    benchmark-relative.
    """

    document = _document(
        {
            "posture": "partial",
            "notes": [
                {
                    "code": "missing_benchmark",
                    "severity": "informational",
                    "message": (
                        "Benchmark-relative risk posture is unavailable because no "
                        "benchmark code was provided."
                    ),
                    "affected_measures": ["beta", "tracking_error_pct", "information_ratio"],
                }
            ],
        }
    )

    sentence = "Beta, Tracking error and Information ratio: Benchmark-relative risk posture"
    assert sentence in document, "the mandate fact does not name its measures"
    assert document.count("Benchmark-relative risk posture") == 1, (
        "one fact is stated more than once"
    )


def test_a_transient_failure_reads_differently_from_a_mandate_fact() -> None:
    """The pair that pointed readers in opposite directions.

    `risk_upstream_failure` is section-wide (no `affected_measures`), so Report's
    sentence stands alone -- and it is a different sentence from the mandate case,
    which is the entire point of #227.
    """

    document = _document(
        {
            "posture": "unavailable",
            "notes": [
                {
                    "code": "risk_upstream_failure",
                    "severity": "warning",
                    "message": "Risk analytics could not be sourced; re-run the report.",
                }
            ],
        }
    )

    assert "Risk analytics could not be sourced; re-run the report." in document
    assert "Benchmark-relative" not in document


def test_a_note_about_nothing_on_the_page_draws_nothing() -> None:
    """`affected_measures: []` is a real answer distinct from absent.

    Empty means the note concerns only metrics this report does not present -- Sharpe,
    say -- so there is nothing on the page to say it about, and a sentence about an
    invisible measure would confuse rather than explain. Absent means section-wide.
    The two must never collapse into each other.
    """

    document = _document(
        {
            "posture": "ready",
            "notes": [
                {
                    "code": "missing_risk_free_rate",
                    "message": "Zero-rate convention applied.",
                    "affected_measures": [],
                }
            ],
        }
    )

    assert "Zero-rate convention" not in document


def test_a_period_scoped_note_says_which_period() -> None:
    """A section-wide reading of a one-period fault overstates the fault."""

    document = _document(
        {
            "posture": "partial",
            "notes": [
                {
                    "code": "risk_period_upstream_failure",
                    "message": "The comparison period could not be computed.",
                    "period": "1Y",
                }
            ],
        }
    )

    assert "could not be computed. (applies to the 1Y period)" in document


def test_ready_with_no_notes_earns_no_reassurance() -> None:
    """An absence of notes is not a statement the page may make.

    "All risk measures supported" would be Render asserting something Report did not
    say. The banked golden is exactly this case, so the assertion runs against it.
    """

    document = _document({"posture": "ready", "notes": []})

    assert "supportability" not in document.lower()
    assert "supported" not in document.lower()


def test_a_promised_explanation_that_never_arrived_is_said_not_silenced() -> None:
    """`unavailable` promises a note; a package violating that must not recreate the
    original defect -- bare "Not available" cells with nothing to explain them."""

    document = _document({"posture": "unavailable", "notes": []})

    assert "The supportability of these measures was not stated for this report." in document


def test_an_unrecognised_code_still_shows_its_message() -> None:
    """The code is the operator's join key, forwarded verbatim; the message is the page
    copy. A code Render does not know must not drop a sentence Report wrote."""

    emitted = render_risk_supportability_notes(
        {
            "risk_posture": {
                "posture": "partial",
                "notes": [
                    {"code": "some_future_reason", "message": "A future fact about this data."}
                ],
            }
        }
    )

    assert "A future fact about this data." in emitted


def test_a_note_render_cannot_read_is_dropped_not_guessed_at() -> None:
    """`report_data` is untrusted; the contract says what Report sends, not what arrives.

    A note that is not a mapping, or has no message, carries nothing showable -- the
    code is an operator join key, not page copy. And a `notes` that is not a list means
    the block is malformed; with a stated posture of `partial`, the promised explanation
    never arrived, so the unstated line fires rather than silence.
    """

    emitted = render_risk_supportability_notes(
        {
            "risk_posture": {
                "posture": "partial",
                "notes": ["bare string", {"code": "x"}, 7],
            }
        }
    )
    assert "not stated for this report" in emitted

    malformed = render_risk_supportability_notes(
        {"risk_posture": {"posture": "partial", "notes": "missing_benchmark"}}
    )
    assert "not stated for this report" in malformed
