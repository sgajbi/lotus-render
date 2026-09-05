"""The v4 acceptance matrix: every adversarial package variant, page by page.

The #270 design overhaul was accepted page by page against a single golden
package -- exactly the arrangement that let single-instance goldens hide nine
defects once. This matrix renders every variant the golden tree carries
through v4: the advisory pages nobody looks at, the fully degraded snapshot,
and a composite where both risk families refuse.

The frame guarantee is proven PER PAGE, not per document: an earlier version
of this suite joined all pages before asserting the chrome, which proved only
that branding appeared somewhere -- a later page losing its footer passed.
Now every applicable content page independently shows the brand block, the
client and report identity, the reporting metadata, the classified footer and
its own correct N / M pagination; the cover is the one deliberate exception
(it sets its own stage). A negative control doctors a later page and proves
the checker fails it.

Variant content is verified by its own substance -- the approved commentary's
grounded figures, the narrative and memo disclosures -- never by the generic
document title alone.
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
from app.services.date_format import format_date
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_ROOT = Path("tests/golden/portfolio-review")
TREND_GALLERY = Path("tests/gallery/risk-trend")
ATTRIBUTION_GALLERY = Path("tests/gallery/risk-attribution")

#: Pages that deliberately do not carry the running frame: the cover sets its
#: own stage (classification eyebrow, side panel, registration line). Every
#: other page must be self-identifying -- a page separated from the document
#: still says whose review it is and how it must be handled.
FRAME_EXEMPT_PAGES = frozenset({1})


def _variant(name: str) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(
        (GOLDEN_ROOT / "v1" / name / "render-package.json").read_text(encoding="utf-8")
    )
    package["template_version"] = "v4"
    package["render_job_id"] = f"rdr_v4_matrix_{name.replace('-', '_')}"
    return package


def _benchmarked() -> dict[str, Any]:
    """The v4 golden with a READY stated benchmark series (report#288): the
    chart gains the dashed line, and the card names the benchmark with its
    differing currency."""

    package: dict[str, Any] = json.loads(
        (GOLDEN_ROOT / "v4" / "render-package.json").read_text(encoding="utf-8")
    )
    package["render_job_id"] = "rdr_v4_matrix_benchmarked"
    history = package["report_data"]["performance_monthly_history"]

    def _trailing(row: dict[str, Any]) -> str:
        portfolio = float(str(row["cumulative_twr_pct"]).rstrip("%"))
        return f"{portfolio - 1.1:.2f}%"

    package["report_data"]["benchmark_series"] = {
        "posture": "ready",
        "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
        "benchmark_currency": "EUR",
        "return_source": "calculated",
        "points": [
            {
                "period": row["period"],
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "twr_pct": "0.40%",
                "cumulative_twr_pct": _trailing(row),
            }
            for row in history[-12:]
        ],
    }
    return package


def _refusal_composite() -> dict[str, Any]:
    package: dict[str, Any] = json.loads(
        (GOLDEN_ROOT / "v4" / "render-package.json").read_text(encoding="utf-8")
    )
    package["render_job_id"] = "rdr_v4_matrix_refusals"
    # The benchmark refusal joins the composite (report#288): an expected
    # series the source refused must surface as a stated caption, never a
    # silently thinner chart.
    package["report_data"]["benchmark_series"] = {
        "posture": "unavailable",
        "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
        "points": [],
        "source_statement": "Benchmark return series was not sourced for this report.",
    }
    package["report_data"]["risk_trend"] = json.loads(
        (TREND_GALLERY / "warmup-partial-coverage.json").read_text(encoding="utf-8")
    )
    package["report_data"]["risk_attribution"] = json.loads(
        (ATTRIBUTION_GALLERY / "producer-refusals.json").read_text(encoding="utf-8")
    )
    return package


PACKAGE_BUILDERS: dict[str, Any] = {
    "advisory-narrative": lambda: _variant("advisory-narrative"),
    "advisor-memo": lambda: _variant("advisor-memo"),
    "degraded": lambda: _variant("degraded"),
    "advisor-commentary": lambda: _variant("advisor-commentary"),
    "benchmarked": _benchmarked,
    "refusal-postures": _refusal_composite,
}

#: Each variant's own substance: the statements that make it THIS document --
#: the approved commentary's grounded figures, the advisory disclosures, the
#: degraded absences -- never the generic document title alone.
CASES: dict[str, tuple[list[str], list[str]]] = {
    "advisory-narrative": (
        [
            "Reviewed advisory narrative",
            "APPROVED_FOR_ADVISOR_USE",
            "proposal_narrative.advisor_use_only.v1",
            "Advisor use only. Client distribution requires separate approval.",
        ],
        [],
    ),
    "advisor-memo": (
        [
            "Advisor proposal memo",
            "The advisor proposal memo is ready for advisor use.",
            "Client-ready memo publication remains blocked.",
            "BLOCKED",
        ],
        [],
    ),
    "degraded": (
        ["Not stated in the governed snapshot."],
        [
            "represents Not available",
            "contributed Not available",
            "Booking center Not available",
        ],
    ),
    "advisor-commentary": (
        [
            "The portfolio returned 7.93% year to date against a benchmark of 6.85%",
            "abr_run_0091",
        ],
        [],
    ),
    "benchmarked": (
        [
            "Benchmark: BMK_PB_GLOBAL_BALANCED_60_40 (EUR)",
        ],
        [],
    ),
    "refusal-postures": (
        [
            "Source quality flags: PARTIAL_COVERAGE",
            "Benchmark return series was not sourced for this report.",
            "The source did not state the full total",
            "Not included",
            "position_returns_unavailable",
        ],
        ["Bars are scaled"],
    ),
}


@pytest.fixture(scope="module")
def render_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


@pytest.fixture(scope="module")
def rendered_variants(render_service: TypstRenderService) -> dict[str, dict[str, Any]]:
    """Each variant rendered once: per-page text plus the identity facts the
    frame must state, taken from the package itself so every variant is held
    to ITS OWN identity."""

    rendered: dict[str, dict[str, Any]] = {}
    for name, build in PACKAGE_BUILDERS.items():
        package = build()
        report_data = package["report_data"]
        result = render_service.render(RenderPackage.model_validate(package))
        reader = pypdf.PdfReader(io.BytesIO(result.artifact_bytes))
        pages = [re.sub(r"\s+", " ", page.extract_text() or "") for page in reader.pages]
        rendered[name] = {
            "pages": pages,
            "client": str(report_data["client_name"]),
            "portfolio": str(report_data["portfolio_name"]),
            "as_of": format_date(report_data["as_of_date"]),
        }
    return rendered


def _spaceless(text: str) -> str:
    return text.replace(" ", "")


def frame_defects(pages: list[str], *, client: str, portfolio: str, as_of: str) -> list[str]:
    """Every missing frame element, named per page; empty means fully framed.

    Tracked uppercase extracts letter-spaced, so matching is space-blind.
    The pagination needle is a substring check by design: its job is to fail
    when a page stops stating its own position, not to parse the footer.
    """

    total = len(pages)
    identity = _spaceless(f"{client}, {portfolio}")
    defects: list[str] = []
    for number, page in enumerate(pages, start=1):
        if number in FRAME_EXEMPT_PAGES:
            continue
        spaceless = _spaceless(page)
        for label, needle in (
            ("brand block", "LOTUSPRIVATEBANKING"),
            ("classified footer", "Private&confidential|Portfolioreview|"),
            ("client/report identity", identity),
            ("as-of statement", _spaceless(f"As of {as_of}")),
            ("reporting currency", "Reportingcurrency"),
            ("pagination", f"{number}/{total}"),
        ):
            if needle not in spaceless:
                defects.append(f"page {number} of {total}: missing {label}")
    return defects


@pytest.mark.parametrize("name", sorted(PACKAGE_BUILDERS))
def test_every_content_page_of_every_variant_carries_the_frame(
    name: str, rendered_variants: dict[str, dict[str, Any]]
) -> None:
    variant = rendered_variants[name]
    defects = frame_defects(
        variant["pages"],
        client=variant["client"],
        portfolio=variant["portfolio"],
        as_of=variant["as_of"],
    )
    assert not defects, f"{name}: {defects}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_variant_states_its_own_substance(
    name: str, rendered_variants: dict[str, dict[str, Any]]
) -> None:
    needles, forbidden = CASES[name]
    document = " ".join(rendered_variants[name]["pages"])
    for needle in needles:
        assert needle in document, f"{name}: the rendered document must state {needle!r}"
    for needle in forbidden:
        assert needle not in document, f"{name}: {needle!r} must not reach a reader"


def test_a_later_page_losing_its_frame_fails_the_checker(
    rendered_variants: dict[str, dict[str, Any]],
) -> None:
    """The negative control: the checker must catch a SINGLE later page losing
    a single frame element -- the exact defect the old joined-document
    assertion could never see."""

    variant = rendered_variants["advisor-commentary"]
    pages = list(variant["pages"])
    target = len(pages) - 2  # a later content page; 1-based number is target + 1
    identity = dict(
        client=variant["client"], portfolio=variant["portfolio"], as_of=variant["as_of"]
    )

    assert not frame_defects(pages, **identity), "control precondition: fully framed"

    footerless = list(pages)
    footerless[target] = footerless[target].replace("Private & confidential", "")
    defects = frame_defects(footerless, **identity)
    assert defects == [f"page {target + 1} of {len(pages)}: missing classified footer"], defects

    anonymous = list(pages)
    anonymous[target] = anonymous[target].replace(variant["client"], "")
    defects = frame_defects(anonymous, **identity)
    assert any("client/report identity" in defect for defect in defects), defects

    unnumbered = list(pages)
    unnumbered[target] = unnumbered[target].replace(f"{target + 1} / {len(pages)}", "")
    defects = frame_defects(unnumbered, **identity)
    assert any("pagination" in defect for defect in defects), defects
