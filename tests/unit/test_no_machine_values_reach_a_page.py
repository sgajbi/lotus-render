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
