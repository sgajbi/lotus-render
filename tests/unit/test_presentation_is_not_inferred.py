"""A dimension is presented because the package named it, never because it has rows.

`allocation_breakdowns` ships all seven `by_*` dimensions unconditionally, deliberately:
the package is evidence, and an operator diagnosing "why no sector" should have the rows
to look at. That makes presence meaningless as a signal, and Render used to read it as
one -- a priority order of its own, taking the first breakdown with rows.

Because currency led that order and the package always carries it, **six of the seven
single-dimension orders drew a currency table**:

    ordered by_currency      -> shows By currency    correct, by luck of ordering
    ordered by_region        -> shows By currency    WRONG
    ordered by_sector        -> shows By currency    WRONG
    ordered by_country       -> shows By currency    WRONG
    ordered by_product_type  -> shows By currency    WRONG
    ordered by_rating        -> shows By currency    WRONG

Only currency was right, and only because it led the list -- which is why nobody saw it.
It was worse than a substitution: #211 had made the appendix define whichever dimension
was drawn, so an advisor who ordered sector exposure received a currency table, a currency
bar and a definition of "Currency exposure", with nothing on the page saying the request
had not been honoured. A correctness fix that made the wrong document more convincing.

Report sends the resolved list now. These are the two halves that keep it that way: the
rows may only be reached through it, and every dimension it names has to reach the page.
"""

from __future__ import annotations

import ast
import io
import json
import re
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.allocation_presentation import DIMENSION_TITLES
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

SOURCE_ROOT = Path("src/app/services")
PRESENTATION_MODULE = SOURCE_ROOT / "allocation_presentation.py"
GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")

BREAKDOWN_KEY = re.compile(r'"(by_[a-z_]+)"')


def _code_only(path: Path) -> str:
    """The module's code, with its comments and its docstrings removed.

    A structural rule must not be trippable by the prose that explains it. An earlier
    guard here matched `max(weight, 8.0)` inside the comment describing why that floor was
    removed; this one first matched a docstring saying which key the function no longer
    reads. Both directions are wrong: rewording should not satisfy a rule, and explaining
    should not break one.

    Docstrings are removed by AST node rather than by pattern, because a docstring is a
    specific thing and a triple-quoted string inside an expression is not.
    """
    source = path.read_text(encoding="utf-8")
    documentation: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and first.end_lineno is not None
        ):
            documentation.update(range(first.lineno, first.end_lineno + 1))

    lines = []
    for number, line in enumerate(source.splitlines(), 1):
        if number in documentation or line.lstrip().startswith("#"):
            continue
        lines.append(line.split("  # ")[0])
    return "\n".join(lines)


def test_no_emitter_reads_a_breakdown_key_directly() -> None:
    """One module resolves which dimension is drawn, so nothing else may name one.

    This is the rule that makes "all seven ship as evidence" safe. Without it, shipping
    rows Render must not draw is a standing invitation to read them -- and a governed
    decision that every site reads around is this repository's most repeated defect:
    `weight_width_token` bypassed by an inline floor, `supplied_text` by 31 `.get`
    defaults, the type scale by 118 literals.
    """

    offenders = {
        path.relative_to(SOURCE_ROOT).as_posix(): sorted(set(found))
        for path in sorted(Path("src").rglob("*.py"))
        if path != PRESENTATION_MODULE and (found := BREAKDOWN_KEY.findall(_code_only(path)))
    }

    assert not offenders, (
        f"these modules name a breakdown key themselves: {offenders}. Which dimensions a "
        "document presents is Report's decision, carried in allocation_presentation; the "
        "rows are reached through it or not at all."
    )


@pytest.mark.parametrize("dimension", sorted(DIMENSION_TITLES))
def test_the_document_presents_the_dimension_the_package_named(dimension: str) -> None:
    """Read off the page, for every dimension, not only the one that was right by luck.

    The package carries all seven either way. What changes is which one is named -- so a
    pass here means the named dimension was drawn *and* no unnamed one was.
    """

    package = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    package["report_data"]["allocation_presentation"] = {
        "resolved_by": "caller_request",
        "dimensions": [
            {
                "dimension": dimension,
                "package_key": f"by_{dimension}",
                "posture": "ready",
            }
        ],
    }

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    rendered = service.render(RenderPackage.model_validate(package))
    reader = pypdf.PdfReader(io.BytesIO(rendered.artifact_bytes))
    document = re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in reader.pages))

    expected = DIMENSION_TITLES[dimension]
    unordered = [
        title for name, title in DIMENSION_TITLES.items() if name != dimension and title in document
    ]

    assert expected in document, f"the caller asked for {expected!r} and the page omits it"
    assert not unordered, (
        f"the caller asked for {expected!r} and the page also drew {unordered}. The rows "
        "for every dimension ship as evidence; only the named one is presented."
    )


# Shapes a malformed or hostile package can take at this boundary. `allocation_presentation`
# arrives inside `report_data`, which is untrusted: the contract says what Report sends, not
# what will actually arrive.
MALFORMED = [
    pytest.param({}, id="no-key"),
    pytest.param({"allocation_presentation": "sector"}, id="key-is-a-string"),
    pytest.param({"allocation_presentation": {}}, id="no-dimensions"),
    pytest.param({"allocation_presentation": {"dimensions": "sector"}}, id="dimensions-a-string"),
    pytest.param({"allocation_presentation": {"dimensions": ["sector"]}}, id="entry-not-a-mapping"),
    pytest.param(
        {"allocation_presentation": {"dimensions": [{"dimension": "sector"}]}},
        id="entry-missing-key-and-posture",
    ),
    pytest.param(
        {
            "allocation_presentation": {
                "dimensions": [
                    {"dimension": "moon_phase", "package_key": "by_moon_phase", "posture": "ready"}
                ]
            }
        },
        id="dimension-render-cannot-draw",
    ),
    pytest.param(
        {
            "allocation_presentation": {
                "dimensions": [
                    {"dimension": "sector", "package_key": "by_sector", "posture": "probably"}
                ]
            }
        },
        id="posture-render-does-not-know",
    ),
]


@pytest.mark.parametrize("report_data", MALFORMED)
def test_a_package_render_cannot_read_presents_nothing(report_data: dict[str, object]) -> None:
    """Drop what cannot be drawn; never fall back to guessing which dimension was meant.

    Guessing is the defect this contract removed, so a malformed entry must not reopen it
    by any route. Dropping is visible rather than silent: the block is absent and the
    section says no dimensions were named.
    """

    from app.services.typst_tables import render_allocation_dimension_blocks

    blocks = render_allocation_dimension_blocks(report_data)

    assert "No allocation dimensions were named for this report." in blocks
    assert "allocation-dimension-block(" not in blocks


def test_a_presented_dimension_with_no_rows_behind_it_draws_an_empty_table() -> None:
    """`ready` is Report's word that the rows are there; Render still has to survive it.

    A package naming a dimension `ready` whose rows are missing is a contract violation on
    the other side. The block is drawn, because that is what was asked for, and it says
    the detail is absent rather than rendering a header over nothing at all.
    """

    from app.services.typst_tables import render_allocation_dimension_blocks

    blocks = render_allocation_dimension_blocks(
        {
            "allocation_presentation": {
                "dimensions": [
                    {"dimension": "sector", "package_key": "by_sector", "posture": "ready"}
                ]
            }
        }
    )

    assert "By sector" in blocks
    assert "No allocation detail available." in blocks


def test_the_donut_says_so_when_asset_class_is_presented_with_no_rows() -> None:
    """The chart's half of the same contract violation the block test covers.

    Report saying `ready` is Report's word that the rows are there. If they are not, the
    donut has nothing to draw -- and the honest statement is that the breakdown is
    unavailable, not that the report does not present one. It does present one; the rows
    are missing.
    """

    from app.services.typst_tables import render_allocation_chart_section

    section = render_allocation_chart_section(
        {
            "allocation_presentation": {
                "dimensions": [
                    {
                        "dimension": "asset_class",
                        "package_key": "by_asset_class",
                        "posture": "ready",
                    }
                ]
            }
        }
    )

    assert "No allocation breakdown is available for this report." in section
    assert "does not present an asset-class breakdown" not in section
