"""A composition looks like a whole thing, so it has to say when it is not one.

The allocation dimension list drew every bucket it was given and said nothing about what
that meant. Measured on the golden with a synthetic sector breakdown:

- **Thirty buckets drew thirty rows** and took the document from ten pages to twelve. The
  rows sit at a uniform 26.9pt pitch and nine fit beside the donut, so a realistic sector
  or country breakdown claimed two extra pages for a list nobody scans.
- **Twelve buckets summing to 62% of the portfolio said nothing about the other 38%.**
  The only coverage claim on that page read "Chart covers 89.64%" -- which belongs to the
  asset-class donut. One coverage statement on a page carrying two compositions is worse
  than none, because a reader will attach it to whichever they are looking at.

Both are the shape this repository keeps finding: correct arithmetic, honest components,
and a page that overstates what it knows.
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
from app.services.typst_tables import MAX_COMPOSITION_ROWS

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")


def _package(bucket_count: int, covered_pct: float = 100.0) -> dict[str, Any]:
    """A portfolio review presenting asset class and a synthetic sector breakdown."""
    package: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report_data = package["report_data"]
    each = covered_pct / bucket_count
    report_data["allocation_breakdowns"]["by_sector"] = [
        {
            "name": f"Sector {index:02d}",
            "weight_pct": f"{each:.2f}%",
            "market_value": f"{each * 1000:.2f}",
            "position_count": 1,
        }
        for index in range(bucket_count)
    ]
    report_data["allocation_presentation"] = {
        "resolved_by": "caller_request",
        "dimensions": [
            {"dimension": "asset_class", "package_key": "by_asset_class", "posture": "ready"},
            {"dimension": "sector", "package_key": "by_sector", "posture": "ready"},
        ],
    }
    return package


def _render(package: dict[str, Any]) -> list[str]:
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    return [page.extract_text() for page in reader.pages]


def _flat(pages: list[str]) -> str:
    return re.sub(r"\s+", " ", "\n".join(pages))


@pytest.mark.parametrize("buckets", [1, 6, 30, 120])
def test_a_composition_never_draws_more_rows_than_it_can_hold(buckets: int) -> None:
    """One, six, thirty and an absurd one-hundred-and-twenty.

    The bound is measured, not chosen: bucket rows sit at 26.9pt and nine fit beside the
    donut. A tenth is not a design decision, it is a page.
    """

    document = _flat(_render(_package(buckets)))
    drawn = len(re.findall(r"Sector \d\d", document))

    assert drawn <= MAX_COMPOSITION_ROWS, (
        f"{buckets} buckets drew {drawn} rows; the page holds {MAX_COMPOSITION_ROWS}"
    )
    assert drawn == min(buckets, MAX_COMPOSITION_ROWS - 1) or drawn == buckets, (
        f"{buckets} buckets drew {drawn} rows, which is neither all of them nor the folded shape"
    )


def test_thirty_buckets_do_not_claim_a_page() -> None:
    """The page economy this fold exists for, stated as a page count.

    Before the fold: ten pages at one bucket, twelve at thirty. The list grew the
    document by two pages, which is #184's defect arriving through a composition.
    """

    assert len(_render(_package(30))) == len(_render(_package(1))) + 1, (
        "a thirty-bucket breakdown costs more than the one page the section grew by"
    )


def test_a_folded_bucket_is_not_mistaken_for_a_real_one() -> None:
    """`Other` carries the number of groups it stands for.

    A row a reader tries to look up and cannot find is worse than a row that says it is a
    summary. The count is also the honest measure of how much was folded away.
    """

    document = _flat(_render(_package(30)))

    assert "Other (22 groups)" in document, "the folded row does not say what it stands for"
    assert "Sector 07" in document and "Sector 08" not in document, (
        "the fold did not start where the row budget ends"
    )


def test_a_grouping_that_covers_part_of_the_portfolio_says_so() -> None:
    """Twelve buckets covering 62% used to say nothing at all.

    The donut states its own coverage and the row lists did not, so a page carrying both
    had exactly one coverage claim on it -- belonging to the other composition.
    """

    document = _flat(_render(_package(12, covered_pct=62.0)))

    assert "This grouping covers" in document
    assert "of portfolio value" in document


def test_a_complete_unfolded_grouping_says_nothing_extra() -> None:
    """A note that always appears is furniture, and furniture stops being read.

    Six buckets covering the whole portfolio have nothing to disclose, so the block
    carries no note -- which is what makes the note mean something when it is there.
    """

    document = _flat(_render(_package(6)))
    sector = document[document.find("By sector") :]

    assert "This grouping covers" not in sector
    assert "shown together as Other" not in sector
    # And the asset-class grouping beside it does carry one, because the golden's slices
    # cover 89.64%. That block said nothing before this; only the donut did.
    assert "This grouping covers" in document


def test_a_composition_never_shows_rows_without_the_headings_that_name_them() -> None:
    """Six dimensions at once, so the blocks flow across pages.

    Column headings that stay behind on the previous page leave a reader four columns of
    numbers with no idea which is weight and which is value. The headings are sticky, the
    same way `labelled-table` learned it after a sixty-row table silently drew thirty-one.
    """

    package = _package(9)
    report_data = package["report_data"]
    breakdowns = report_data["allocation_breakdowns"]
    for key in ("by_currency", "by_region", "by_country", "by_product_type", "by_rating"):
        breakdowns[key] = breakdowns["by_sector"]
    report_data["allocation_presentation"]["dimensions"] = [
        {"dimension": name, "package_key": f"by_{name}", "posture": "ready"}
        for name in ("asset_class", "currency", "region", "sector", "country", "rating")
    ]

    pages = _render(package)
    offenders = [
        index
        for index, page in enumerate(pages, 1)
        if re.search(r"Sector \d\d", page) and "Group" not in page
    ]

    assert not offenders, (
        f"pages {offenders} carry composition rows with no column headings above them"
    )
