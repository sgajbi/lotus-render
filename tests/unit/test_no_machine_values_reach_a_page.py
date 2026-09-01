"""No document shows a reader a value meant for a machine.

Three fixtures did. A governed proof pack carried the literal **None**, because
`str(report_data.get("source_contract_version", "not_available"))` takes its default
only when the key is missing and that field is declared `str | None`: it was present and
empty, and `str()` did the rest. The degraded portfolio review and every rebalance wave
carried **not_available**, a sentinel in snake case, from twenty-two call sites that
spelled absence that way.

None of it was visible, because every test that touched those values asserted the
context dictionary rather than the document. This one reads the documents.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_ROOT = Path("tests/golden")

# Values that mean something to a program and nothing to a reader. "Not available" is
# what the document says instead, so the cased sentence is not in this list.
MACHINE_VALUES = (
    "None",
    "not_available",
    "null",
    "NaN",
    "undefined",
    "Ellipsis",
    "dict_keys",
    "dict_values",
    "<object",
    "object at 0x",
)

# Template source that reached the page instead of drawing anything. In Typst markup a
# bare `name(...)` is text, not a call, so an emitter that forgets the leading `#`
# prints the call. That happened to the advisory disclosures: a governed advisor memo
# carried `advisory-disclosure-block([memo.advisor_use_only.v1], [Advisor use only...])`
# under the heading "Disclosures" -- the compliance line rendered as its own source.
#
# The values above are all words. This is a shape, so it needs a pattern.
CALL_SYNTAX = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+\(\[")


def _packages() -> list[Path]:
    return sorted(GOLDEN_ROOT.rglob("render-package.json"))


@pytest.fixture(scope="module")
def render_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


@pytest.mark.parametrize("package_path", _packages(), ids=lambda path: path.parent.name)
def test_no_banked_document_shows_a_machine_value(
    package_path: Path, render_service: TypstRenderService
) -> None:
    """Read back the document, not the context that built it.

    Every fixture, because the three that leaked were not the ones anyone looked at:
    the proof pack, the degraded review and the rebalance wave.
    """

    package = RenderPackage.model_validate_json(package_path.read_text(encoding="utf-8"))
    reader = pypdf.PdfReader(io.BytesIO(render_service.render(package).artifact_bytes))
    document = "\n".join(page.extract_text() for page in reader.pages)

    found = {value: document.count(value) for value in MACHINE_VALUES if value in document}
    printed_calls = sorted(set(CALL_SYNTAX.findall(document)))

    assert not found, (
        f"{package_path.parent.name} shows values meant for a program: {found}. A field "
        "that did not arrive reads 'Not available'."
    )
    assert not printed_calls, (
        f"{package_path.parent.name} prints template source instead of drawing it: "
        f"{printed_calls}. A bare `name(...)` in Typst markup is text; `markup_calls` "
        "adds the `#` that invokes it."
    )


def test_no_emitter_spells_absence_for_itself() -> None:
    """One decision about what absence is, so the modules cannot disagree about it.

    Two already had: `appendix_glossary` counted four spellings absent, `statement_tables`
    counted seven, and `typst_contexts` counted none at all -- it took the key's presence
    as proof there was something behind it, which is how `None` reached a proof pack.
    """

    emitters = sorted(Path("src").rglob("*.py"))
    shared = Path("src/app/services/absence.py")
    offenders = {
        path.as_posix(): "not_available"
        for path in emitters
        if path != shared and "not_available" in path.read_text(encoding="utf-8")
    }

    assert not offenders, (
        f"these modules carry the sentinel themselves: {sorted(offenders)}. Absence is "
        "decided in absence.py, and what a reader sees is 'Not available'."
    )


def _code_without_comments(path: Path) -> str:
    """The module's code with comment text removed.

    A structural rule that scans raw source also reads the comment explaining the defect
    it forbids, so writing the explanation trips the rule and deleting the explanation
    satisfies it. Both of those are the wrong way round.
    """
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line.split("  # ")[0])
    return "\n".join(lines)


def test_no_emitter_takes_a_default_where_the_value_may_be_null() -> None:
    """`x.get(key, "Not available")` fires only when the key is *missing*.

    A key present with a null value takes the value, and `str(None)` is "None". That is
    how the literal reached a governed proof pack, and ten more sites still had the
    shape afterwards -- five of them the risk panel of the client-facing review, where a
    volatility of null would have printed "None" beside "Beta" and "Tracking error".

    `supplied_text` asks whether the value is there rather than whether the key is.
    """

    offenders = {
        path.as_posix(): found
        for path in sorted(Path("src").rglob("*.py"))
        if (
            found := re.findall(
                r'\w+\.get\([^)]*,\s*"Not available"\)', _code_without_comments(path)
            )
        )
    }

    assert not offenders, (
        f"these sites default on a missing key rather than on an absent value: "
        f"{offenders}. A key present and null renders 'None'; use supplied_text."
    )


def test_no_emitter_sizes_a_bar_for_itself() -> None:
    """`weight_width_token` is the governed width and floors nothing.

    It says so in its own docstring: flooring at 8% drew a 1.64% liquidity sleeve five
    times its true length. `render_allocation_breakdown_rows` kept its own
    `max(weight, 8.0)` inline, so the allocation page drew Cash at 8% beside the donut
    that shows it honestly at 1.64% -- two pictures of one number on one page.
    """

    offenders = {
        path.as_posix(): found
        for path in sorted(Path("src").rglob("*.py"))
        if path.name != "typst_values.py"
        and (
            found := re.findall(
                r"max\(\s*[\w\[\]'\"]+\[?'?\w*'?\]?,\s*[1-9][\d.]*\s*\)",
                _code_without_comments(path),
            )
        )
    }

    assert not offenders, (
        f"these sites floor a bar width themselves: {offenders}. The floor is what made "
        "a negligible weight look like a real one; weight_width_token has none."
    )
