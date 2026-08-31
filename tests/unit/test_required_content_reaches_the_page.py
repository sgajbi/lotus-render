"""What the contract makes mandatory has to arrive on the page.

`review_observations` is required by `PortfolioReviewRenderContent` -- `min_length=1`, so
a package cannot be accepted without at least one. `render_observation_notes` built the
markup for them on every render. No template had referenced `OBSERVATION_NOTES` since
2026-04-24, so the reviewer's own commentary on the review was dropped from every
portfolio review the service produced for four months.

It was not unnoticed, exactly. The context-key inventory (#159) listed it as an orphan --
"content built and discarded" -- and passed, because the inventory governs *keys* and
treats a recorded orphan as a debt rather than a defect. That is the right shape for a
derived nicety and the wrong shape for a field the contract refuses a package without.
Nothing separated the two.

So this asserts the other end: not that a key is referenced, but that the value a caller
was required to supply is somewhere in the document. A key can be renamed, split or
inlined and this still holds; a required field can only pass it by being on the page.
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

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")


@pytest.fixture(scope="module")
def golden_document() -> str:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    service = TypstRenderService(settings, RenderIntakeService(registry))
    package = RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    reader = pypdf.PdfReader(io.BytesIO(service.render(package).artifact_bytes))
    # Collapsed, because a PDF text layer breaks lines wherever the layout did and a
    # sentence that wrapped is still the sentence that was supplied.
    return re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in reader.pages))


@pytest.fixture(scope="module")
def golden_report_data() -> dict[str, object]:
    package: dict[str, object] = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    report_data: dict[str, object] = package["report_data"]  # type: ignore[assignment]
    return report_data


def test_every_review_observation_reaches_the_page(
    golden_report_data: dict[str, object], golden_document: str
) -> None:
    """The reviewer's commentary is the one thing on the document a person wrote.

    Everything else is a figure the platform computed. A review that drops it is a
    statement of holdings with the review taken out.
    """

    observations = golden_report_data["review_observations"]
    assert isinstance(observations, list) and observations, "the fixture supplies none"

    missing = [
        sentence
        for observation in observations
        if (sentence := re.sub(r"\s+", " ", str(observation)).strip()) not in golden_document
    ]

    assert not missing, f"these observations were supplied and are on no page: {missing}"


@pytest.mark.parametrize("field", ["client_name", "portfolio_name", "summary_paragraph"])
def test_required_prose_reaches_the_page(
    field: str, golden_report_data: dict[str, object], golden_document: str
) -> None:
    """Each of these is required by the contract and is carried verbatim.

    The other required fields -- `as_of_date`, `currency`, `total_value` -- are formatted
    before they are drawn, so they are checked by the tests that own that formatting
    rather than compared to their raw form here.
    """

    supplied = re.sub(r"\s+", " ", str(golden_report_data[field])).strip()

    assert supplied in golden_document, f"{field} was required, supplied, and is on no page"


def test_a_required_field_cannot_be_recorded_as_an_orphan(
    golden_report_data: dict[str, object],
) -> None:
    """The inventory records what is built and not drawn. It cannot record this.

    `OBSERVATION_NOTES` sat in that list for four months as an accepted debt while the
    field behind it was one the contract will not let a caller omit. A key whose only
    source is a required field is not a debt to be carried; it is content missing from
    the document.
    """

    # Read from the source rather than imported: the inventory is a test module, and a
    # test that imports another test binds the two together for no gain.
    inventory = Path("tests/unit/test_context_keys_reach_the_page.py").read_text(encoding="utf-8")
    orphans = inventory[inventory.index("ORPHANED_KEYS") : inventory.index("def _referenced_keys")]

    assert '"OBSERVATION_NOTES"' not in orphans, (
        "OBSERVATION_NOTES carries review_observations, which the contract requires; it "
        "cannot be an accepted orphan"
    )
    assert golden_report_data["review_observations"], "the fixture stopped supplying them"
