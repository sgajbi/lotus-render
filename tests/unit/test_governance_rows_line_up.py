"""A column that moves between rows is not a column.

Each governance row was its own ``#grid(columns: (auto, auto, ...))``, sized to whatever
that row happened to contain. Measured on a four-item rebalance wave with ordinary
portfolio ids and states:

    PORTFOLIO    56.0, 56.0, 56.0, 56.0        spread   0.0mm
    STATE       103.7, 258.4, 103.7, 221.4     spread  54.6mm
    PROOF PACK  144.3, 311.1, 268.9, 309.4     spread  58.8mm
    PROOF STATE 195.7, 362.6, 320.3, 360.8     spread  58.9mm
    ALTERNATIVE 249.6, 416.4, 374.2, 414.7     spread  58.8mm

A third of the page width, between one row and the next, on a page a reader is meant to
scan down.

Every banked fixture in the three governance families carries exactly one item, so all
of these documents were a single row and no golden could show it. That is why this test
builds its own multi-row packages rather than reading the fixtures.
"""

from __future__ import annotations

import io
import json
from collections import defaultdict
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

# A label is drawn once per row, so its x positions across a document are the column's
# positions. Upper-case because `label()` upper-cases what it is given.
GOVERNANCE_LISTS = [
    pytest.param(
        "tests/golden/rebalance-wave/v1/render-package.json",
        "items",
        "portfolio_id",
        ("PORTFOLIO", "STATE", "PROOF PACK", "PROOF STATE", "ALTERNATIVE"),
        id="rebalance-wave",
    ),
    pytest.param(
        "tests/golden/proof-pack/v1/render-package.json",
        "sections",
        "title",
        ("SECTION", "TYPE", "STATE", "SUMMARY"),
        id="proof-pack",
    ),
    pytest.param(
        "tests/golden/outcome-review/v1/render-package.json",
        "dimensions",
        "dimension",
        ("DIMENSION", "STATE", "EXPECTED", "REALIZED", "VARIANCE", "EXPLANATION"),
        id="outcome-review",
    ),
]

# Values of the length a real governed list carries: an id that is nearly a sentence, and
# one that is four characters. Under `auto` columns these two rows disagreed the most.
VARIED_VALUES = (
    "A_1",
    "PB_SG_GLOBAL_BALANCED_MANDATE_0002",
    "X_3",
    "PB_SG_LONG_NAME_DISCRETIONARY_004",
)


def _squeezed(text: str) -> str:
    """Spaces removed, because a kerning pair splits a word in the text layer.

    "VARIANCE" comes back as "V ARIANCE" -- one fragment, drawn at one x, spelled with a
    gap the page does not have. Matching on the squeezed form keeps the label lookup on
    what was drawn rather than on how it was encoded.
    """
    return "".join(text.split())


def _label_positions(pdf_bytes: bytes, labels: tuple[str, ...]) -> dict[str, list[float]]:
    positions: dict[str, list[float]] = defaultdict(list)
    wanted = {_squeezed(label): label for label in labels}

    # pypdf calls the visitor with a fixed signature; the two it does not read are
    # underscored, as the other page-reading tests do.
    def visit(text: str, cm: list[float], tm: list[float], _font: object, _size: float) -> None:
        name = wanted.get(_squeezed(text))
        if name is not None:
            positions[name].append(round(cm[0] * tm[4] + cm[2] * tm[5] + cm[4], 1))

    for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages:
        page.extract_text(visitor_text=visit)
    return positions


@pytest.mark.parametrize(("package_path", "collection", "field", "labels"), GOVERNANCE_LISTS)
def test_every_row_of_a_governed_list_puts_its_labels_in_one_column(
    package_path: str, collection: str, field: str, labels: tuple[str, ...]
) -> None:
    """Read the x of each label off the page, once per row, and require one value.

    Exactly, not approximately: the rows are laid out by one grid geometry now, so
    identical columns produce identical coordinates. A tolerance here would be a place
    for the defect to come back a millimetre at a time.
    """

    package = json.loads(Path(package_path).read_text(encoding="utf-8"))
    rows = package["report_data"][collection]
    template = json.dumps(rows[0])
    package["report_data"][collection] = [
        {**json.loads(template), field: value} for value in VARIED_VALUES
    ]

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    positions = _label_positions(rendered.artifact_bytes, labels)

    for name in labels:
        drawn = positions.get(name, [])
        assert len(drawn) == len(VARIED_VALUES), (
            f"{name} was drawn {len(drawn)} times for {len(VARIED_VALUES)} rows; the "
            "measurement is not reading one label per row."
        )
        spread = max(drawn) - min(drawn)
        assert spread == 0, (
            f"the {name} column lands at {sorted(set(drawn))} across {len(drawn)} rows -- "
            f"a spread of {spread * 25.4 / 72:.1f}mm. Each row is being sized to its own "
            "content, so there is no column to read down."
        )
