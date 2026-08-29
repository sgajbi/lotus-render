"""One palette, and a digest that notices when it changes.

The four template families each declared their own colours, and they had drifted. The
same token names carried different values -- `accent` was #1F5AA6, #286446, #21606f and
#315c8a; `ink` and `rule` had two values each -- and the same role went under two names,
`slate` in one family and `muted` in the other three. A client receiving a portfolio
review and an outcome review received two different brands, from one product.

Nothing made them agree, because nothing could: there was no shared file to disagree
with. These tests hold both halves of the fix -- a single source for the palette, and a
digest that reaches it.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.domain.templates.digest import template_digest
from app.domain.templates.registry import shared_design_directory

TEMPLATE_ROOT = Path("templates/typst")
DESIGN_MODULE = shared_design_directory() / "_design.typ"
FAMILIES = ("portfolio-review", "proof-pack", "outcome-review", "rebalance-wave")

COLOUR_DECLARATION = re.compile(r"#let\s+([a-z-]+)\s*=\s*rgb\(\"(#[0-9A-Fa-f]+)\"\)")


def _family_files(family: str) -> list[Path]:
    return sorted(p for p in (TEMPLATE_ROOT / family / "v1").rglob("*.typ"))


def test_no_family_declares_a_colour_of_its_own() -> None:
    """A palette that lives in four files is four palettes."""

    offenders: dict[str, list[str]] = {}
    for family in FAMILIES:
        declared = [
            f"{name} = {value} in {path.name}"
            for path in _family_files(family)
            for name, value in COLOUR_DECLARATION.findall(path.read_text(encoding="utf-8"))
        ]
        if declared:
            offenders[family] = declared

    assert not offenders, (
        "these families declare colours instead of importing them from the design "
        f"system, which is how the palettes diverged in the first place: {offenders}"
    )


def test_every_family_imports_the_design_system() -> None:
    for family in FAMILIES:
        sources = "\n".join(path.read_text(encoding="utf-8") for path in _family_files(family))
        assert '#import "_design.typ"' in sources, (
            f"{family} does not import the shared design system, so its colours come "
            "from nowhere the gate above can see"
        )


def test_the_design_system_gives_each_role_exactly_one_value() -> None:
    """Two names may share a value only where they are documented as the same role."""

    declarations = COLOUR_DECLARATION.findall(DESIGN_MODULE.read_text(encoding="utf-8"))
    assert declarations, "the design system declares no colours at all"

    names = [name for name, _ in declarations]
    assert len(names) == len(set(names)), f"a role is declared twice: {names}"


def test_a_palette_change_changes_the_digest_of_every_family(tmp_path: Path) -> None:
    """The shared module is compiled into every document, so it must be inside the seal.

    Left outside, a palette edit would restyle every document while every manifest
    digest stayed the same -- the digest would attest to bytes that were no longer the
    whole story, which is exactly the gap #139 exists to close.
    """

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "_design.typ").write_text('#let accent = rgb("#1F5AA6")\n', encoding="utf-8")

    family = TEMPLATE_ROOT / "portfolio-review" / "v1"
    before = template_digest(family, shared_directory=shared)

    (shared / "_design.typ").write_text('#let accent = rgb("#B00020")\n', encoding="utf-8")
    after = template_digest(family, shared_directory=shared)

    assert before != after, (
        "the palette changed and the template digest did not; a document could be "
        "restyled with its manifest still attesting to the old bytes"
    )


def test_a_shared_file_cannot_be_confused_with_a_family_file(tmp_path: Path) -> None:
    """Shared entries are namespaced, so identical names in the two trees stay distinct."""

    family = tmp_path / "family"
    shared = tmp_path / "shared"
    family.mkdir()
    shared.mkdir()
    (family / "_design.typ").write_text("A", encoding="utf-8")
    (shared / "_design.typ").write_text("B", encoding="utf-8")
    swapped_family = tmp_path / "swapped-family"
    swapped_shared = tmp_path / "swapped-shared"
    swapped_family.mkdir()
    swapped_shared.mkdir()
    (swapped_family / "_design.typ").write_text("B", encoding="utf-8")
    (swapped_shared / "_design.typ").write_text("A", encoding="utf-8")

    assert template_digest(family, shared_directory=shared) != template_digest(
        swapped_family, shared_directory=swapped_shared
    )
