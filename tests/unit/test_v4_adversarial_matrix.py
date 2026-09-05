"""The v4 acceptance matrix: every adversarial package variant through the frame.

The #270 design overhaul was accepted page by page against a single golden
package -- exactly the arrangement that let single-instance goldens hide nine
defects once. This matrix renders every variant the golden tree carries
through v4 and reads the documents back: the advisory pages nobody looks at,
the fully degraded snapshot, and a composite where both risk families refuse.
It is the acceptance harness for any future v4 publication decision, kept in
the suite so it cannot go stale in a scratchpad.

Each case asserts two kinds of truth: the variant's own load-bearing
statements survive the frame, and the frame itself (brand block, classified
footer) is present on every variant -- a chrome regression on a page nobody
inspects fails here, not in production.
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
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_ROOT = Path("tests/golden/portfolio-review")
TREND_GALLERY = Path("tests/gallery/risk-trend")
ATTRIBUTION_GALLERY = Path("tests/gallery/risk-attribution")

#: The frame every variant must carry: a page separated from the document
#: still says whose review it is and how it must be handled. Tracked
#: uppercase extracts letter-spaced, so chrome is matched space-blind.
CHROME = (
    "LOTUSPRIVATEBANKING",
    "Private&confidential|Portfolioreview",
)


def _variant(name: str) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(
        (GOLDEN_ROOT / "v1" / name / "render-package.json").read_text(encoding="utf-8")
    )
    package["template_version"] = "v4"
    package["render_job_id"] = f"rdr_v4_matrix_{name.replace('-', '_')}"
    return package


def _refusal_composite() -> dict[str, Any]:
    package: dict[str, Any] = json.loads(
        (GOLDEN_ROOT / "v4" / "render-package.json").read_text(encoding="utf-8")
    )
    package["render_job_id"] = "rdr_v4_matrix_refusals"
    package["report_data"]["risk_trend"] = json.loads(
        (TREND_GALLERY / "warmup-partial-coverage.json").read_text(encoding="utf-8")
    )
    package["report_data"]["risk_attribution"] = json.loads(
        (ATTRIBUTION_GALLERY / "producer-refusals.json").read_text(encoding="utf-8")
    )
    return package


CASES: list[tuple[str, list[str], list[str]]] = [
    (
        "advisory-narrative",
        ["Reviewed advisory narrative", "APPROVED_FOR_ADVISOR_USE"],
        [],
    ),
    (
        "advisor-memo",
        ["Advisor proposal memo", "BLOCKED"],
        [],
    ),
    (
        "degraded",
        ["Not stated in the governed snapshot."],
        [
            "represents Not available",
            "contributed Not available",
            "Booking center Not available",
        ],
    ),
    (
        "advisor-commentary",
        ["Portfolio review"],
        [],
    ),
]


@pytest.fixture(scope="module")
def render_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


def _document(render_service: TypstRenderService, package: dict[str, Any]) -> str:
    result = render_service.render(RenderPackage.model_validate(package))
    return re.sub(
        r"\s+",
        " ",
        "\n".join(
            page.extract_text() for page in pypdf.PdfReader(io.BytesIO(result.artifact_bytes)).pages
        ),
    )


@pytest.mark.parametrize(("name", "needles", "forbidden"), CASES, ids=lambda case: str(case))
def test_every_package_variant_survives_the_v4_frame(
    name: str,
    needles: list[str],
    forbidden: list[str],
    render_service: TypstRenderService,
) -> None:
    document = _document(render_service, _variant(name))
    spaceless = document.replace(" ", "")
    for needle in CHROME:
        assert needle in spaceless, f"{name}: the frame must carry {needle!r}"
    for needle in needles:
        assert needle in document, f"{name}: the rendered document must state {needle!r}"
    for needle in forbidden:
        assert needle not in document, f"{name}: {needle!r} must not reach a reader"


def test_both_risk_families_refuse_inside_an_intact_frame(
    render_service: TypstRenderService,
) -> None:
    """A partial-coverage trend and a producer-refused attribution in one
    document: the strips that can draw draw with their stated flags, the sets
    that cannot state themselves in the source's voice, and no scale
    convention is claimed for bars that were never drawn."""

    document = _document(render_service, _refusal_composite())
    spaceless = document.replace(" ", "")
    for needle in CHROME:
        assert needle in spaceless, f"the frame must carry {needle!r}"
    for needle in (
        "Source quality flags: PARTIAL_COVERAGE",
        "The source did not state the full total",
        "Not included",
        "position_returns_unavailable",
    ):
        assert needle in document, f"the composite must state {needle!r}"
    assert "Bars are scaled" not in document, "no attribution set drew, no convention to state"
