"""No text is drawn over other text.

Every governance template declared its columns in millimetres, and the identifiers they
hold are longer than the guesses were. Typst does not clip an overfull cell; it draws it
across its neighbour. So a proof pack read **MANDATE_CONTEXTREADY** where two columns
met, and a rebalance wave read **PB_SG_GLOBAL_BAL_00HANDOFF_READY**. Both are byte-stable
and both survived every fingerprint.

The check needs no font metrics. The PDF says where each run of text begins; the page
image says where the ink is. Between two runs that begin at different places on the same
line there has to be at least one column of blank pixels, or the first has been drawn
into the second.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pypdf
import pytest
from PIL import Image

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_ROOT = Path("tests/golden")

# Anything darker than this is ink, matching the page-geometry helpers.
INK_THRESHOLD = 245
# Runs whose baselines sit within this many points share a line.
SAME_LINE_POINTS = 2.0


@dataclass(frozen=True)
class TextRun:
    """Where a run of text begins, in PDF points from the bottom-left."""

    x: float
    y: float
    size: float
    text: str


def _runs(page: pypdf.PageObject) -> list[TextRun]:
    found: list[TextRun] = []

    # pypdf calls this positionally, so the text matrix and font it also passes are
    # named for what they are and left unread: the current transformation matrix is
    # where Typst puts the position.
    def visit(text: str, cm: list[float], _tm: list[float], _font: object, size: float) -> None:
        if text.strip():
            found.append(TextRun(x=cm[4], y=cm[5], size=size or 8.0, text=text.strip()))

    page.extract_text(visitor_text=visit)
    return found


def _lines(runs: list[TextRun]) -> list[list[TextRun]]:
    lines: list[list[TextRun]] = []
    for run in sorted(runs, key=lambda item: (-item.y, item.x)):
        if lines and abs(lines[-1][0].y - run.y) <= SAME_LINE_POINTS:
            lines[-1].append(run)
        else:
            lines.append([run])
    return lines


def _has_blank_column(pixels: bytes, width: int, columns: range, rows: range) -> bool:
    return any(
        all(pixels[row * width + column] >= INK_THRESHOLD for row in rows) for column in columns
    )


def _collisions(page: pypdf.PageObject, image_bytes: bytes) -> list[str]:
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    width, height = image.size
    data = image.tobytes()
    scale_x = width / float(page.mediabox.width)
    scale_y = height / float(page.mediabox.height)

    found: list[str] = []
    for line in _lines(_runs(page)):
        for left, right in zip(line, line[1:]):
            columns = range(int(left.x * scale_x), max(int(right.x * scale_x), 1))
            # The band of the line itself: from the baseline up by the type size.
            top = int((height - (left.y + left.size) * scale_y))
            bottom = int(height - (left.y - left.size * 0.3) * scale_y)
            rows = range(max(top, 0), min(bottom, height))
            if not columns or not rows:
                continue
            if not _has_blank_column(data, width, columns, rows):
                found.append(f"{left.text[:34]!r} runs into {right.text[:34]!r}")
    return found


def _packages() -> list[Path]:
    return sorted(GOLDEN_ROOT.rglob("render-package.json"))


@pytest.fixture(scope="module")
def render_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


@pytest.mark.parametrize("package_path", _packages(), ids=lambda path: path.parent.name)
def test_no_run_of_text_is_drawn_over_the_next(
    package_path: Path, render_service: TypstRenderService
) -> None:
    """A cell wider than its column is drawn across the one beside it."""

    package = RenderPackage.model_validate_json(package_path.read_text(encoding="utf-8"))
    reader = pypdf.PdfReader(io.BytesIO(render_service.render(package).artifact_bytes))
    images = render_service.render_page_images(package)

    collisions: list[str] = []
    for number, (page, image) in enumerate(zip(reader.pages, images), 1):
        collisions.extend(f"page {number}: {report}" for report in _collisions(page, image))

    assert not collisions, (
        f"{package_path.parent.name} draws text over text: {collisions}. A column sized "
        "in millimetres is a guess about how long an identifier will be."
    )
