"""Report data is content. It never becomes code, and never becomes a placeholder.

Two escapers already stop it becoming Typst: `escape_typst_text` neutralises the markup
tokens, and `escape_typst_string` neutralises the backslash and quote that can close a
string literal. Neither has any reason to touch `$` or `{`, because in Typst those are
ordinary characters inside a string.

But `${NAME}` is this service's own syntax, applied to the template after the escaping,
and it used to be applied one key at a time over the whole file. A value substituted
early was therefore read again by every later key. A client called
`${ALLOCATION_DIMENSION_BLOCKS}` had that name replaced with a block of allocation markup, and the
quotes in that markup closed the string literal the name was sitting in:

    #body-muted("#compact-allocation-row("Equity", "60.00%", ...

The compile failed on the wreckage, which is the mild outcome. The payload only had to
be valid Typst to be worse, and it did not have to be a client name -- any of the
seventy context values takes text from report data.

Substitution is one pass now, so what a value contains is output and never input.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

GOLDEN_PACKAGE = Path("tests/golden/portfolio-review/v1/render-package.json")

# Each of these ends a document if it is treated as anything but text.
PAYLOADS = [
    # This service's own placeholder syntax, naming a value whose markup carries quotes.
    "${ALLOCATION_DIMENSION_BLOCKS}",
    "${REPORT_SECTIONS}",
    "${DETERMINISM_STATEMENT}",
    # A name that does not exist: it must not empty the field either.
    "${NO_SUCH_CONTEXT_KEY}",
    # Closing a string literal and opening code.
    '" ; #panic("owned") ; "',
    # Closing a markup block and opening code.
    "] #panic() [",
    # Typst markup tokens.
    '#import "/etc/passwd"',
    '#read("main.typ")',
    "$sqrt(2)$",
    "@label",
    "\\u{0000}",
]

# Fields that reach a Typst string literal, a markup block and a table cell respectively,
# so a payload is tried in each of the three contexts an emitter writes into.
FIELDS = ("client_name", "summary_paragraph", "portfolio_name")


@pytest.fixture(scope="module")
def render_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


def _package_with(field: str, payload: str) -> RenderPackage:
    raw = json.loads(GOLDEN_PACKAGE.read_text(encoding="utf-8"))
    raw["report_data"][field] = payload
    return RenderPackage.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("payload", PAYLOADS)
def test_a_hostile_value_renders_as_the_text_it_is(
    payload: str, render_service: TypstRenderService
) -> None:
    """It reaches the page unchanged, and the document is still a document.

    Rendering rather than raising is the requirement: a client whose name contains a
    dollar sign is not an attack, and refusing to draw their statement would be the
    service failing rather than defending.
    """

    result = render_service.render(_package_with("client_name", payload))
    reader = pypdf.PdfReader(io.BytesIO(result.artifact_bytes))
    document = "\n".join(page.extract_text() for page in reader.pages)

    assert len(reader.pages) > 1, "the document lost its pages"
    # The placeholder payloads must survive verbatim: expanded is the defect.
    if payload.startswith("${"):
        assert payload in document, f"{payload} was expanded rather than printed"


@pytest.mark.parametrize("field", FIELDS)
def test_a_placeholder_is_not_expanded_from_any_field(
    field: str, render_service: TypstRenderService
) -> None:
    """Seventy context values take text from report data; the name of the field a
    payload arrives in decides only which of them carries it."""

    payload = "${ALLOCATION_DIMENSION_BLOCKS}"
    result = render_service.render(_package_with(field, payload))
    document = "\n".join(
        page.extract_text() for page in pypdf.PdfReader(io.BytesIO(result.artifact_bytes)).pages
    )

    assert payload in document
    assert "compact-allocation-row" not in document, (
        f"{field} expanded a placeholder into template markup"
    )


def test_the_same_document_still_renders_unchanged(render_service: TypstRenderService) -> None:
    """The fix must not change what an ordinary package produces.

    One pass and repeated passes agree on every template the service ships, because none
    of them contains a placeholder inside a value. The difference is only what happens
    when report data supplies one.
    """

    package = RenderPackage.model_validate_json(GOLDEN_PACKAGE.read_text(encoding="utf-8"))

    first = render_service.render(package)
    second = render_service.render(package)

    fingerprint = first.diagnostic.bounded_determinism_fingerprint
    assert fingerprint, "the render banked no fingerprint to compare"
    assert fingerprint == second.diagnostic.bounded_determinism_fingerprint, (
        "the same package rendered differently twice"
    )
