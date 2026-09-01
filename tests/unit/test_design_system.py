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


COMPONENT_DEFINITION = re.compile(r"#let\s+([a-z][a-z0-9-]*)\s*\(")


def test_no_component_is_defined_by_more_than_one_family() -> None:
    """Three copies of a primitive is the arrangement that produced four palettes.

    `key-value-row`, `label` and `value` were each defined three times -- once in each
    single-file family -- byte-identical, with nothing keeping them in step. They had
    not drifted yet. The colours in the same files had.
    """

    defined_in: dict[str, set[str]] = {}
    for family in FAMILIES:
        for path in _family_files(family):
            for name in COMPONENT_DEFINITION.findall(path.read_text(encoding="utf-8")):
                defined_in.setdefault(name, set()).add(family)

    duplicated = {
        name: sorted(families) for name, families in defined_in.items() if len(families) > 1
    }
    assert not duplicated, (
        "these components are defined by more than one family, so nothing keeps the "
        f"copies in step: {duplicated}. Move them into the design system."
    )

    # Shadowing is the same defect arriving one family at a time, and the check above
    # cannot see it: a single family redefining a shared primitive is not "duplicated
    # across families" until a second one does the same.
    shared_names = set(COMPONENT_DEFINITION.findall(DESIGN_MODULE.read_text(encoding="utf-8")))
    shadowed = {
        name: sorted(families) for name, families in defined_in.items() if name in shared_names
    }
    assert not shadowed, (
        f"these families redefine a primitive the design system already owns: {shadowed}. "
        "A local copy is free to drift from the shared one, which is how this started."
    )


def test_a_shared_file_cannot_overwrite_a_family_file() -> None:
    """The shared module is copied into the workspace *beside* the family's own files.

    `shutil.copytree(shared, workspace_template_directory, dirs_exist_ok=True)` means a
    shared file whose name matches a family file silently replaces it at render time --
    and portfolio-review already has a `_components.typ`. The digest would not notice:
    it hashes both trees, so the bytes are all accounted for, while the document
    compiled against only one of them.
    """

    shared_names = {path.name for path in shared_design_directory().rglob("*") if path.is_file()}
    for family in FAMILIES:
        clashes = shared_names & {path.name for path in _family_files(family)}
        assert not clashes, (
            f"{family} has files whose names collide with the shared module: {sorted(clashes)}. "
            "At render time the shared copy would silently replace the family's own."
        )


SIZE_DECLARATION = re.compile(r"size:\s*([0-9.]+)pt")
SCALE_STEP = re.compile(r"#let (text-[a-z-]+) = ([0-9.]+)pt")

# Chosen for specific furniture rather than drawn from a range: cover titles and section
# headings. Eight declarations, each the first thing a reader looks at on its page.
DISPLAY_SIZES = frozenset({16.0, 17.0, 18.0, 19.0, 20.5, 28.0})


def _declared_scale() -> set[float]:
    source = DESIGN_MODULE.read_text(encoding="utf-8")
    return {float(size) for _, size in SCALE_STEP.findall(source)}


def test_every_size_on_a_page_comes_from_the_scale() -> None:
    """159 declarations across 53 values is an accumulation, not a scale.

    Values sat less than a tenth of a point apart -- 6.55, 6.6, 6.75, 6.8, 6.85, 6.9 all
    appeared -- so no reader could tell them apart and "make the small text larger" meant
    searching fifty numbers. Nine steps now cover the body range.
    """

    scale = _declared_scale()
    assert scale, "the design system declares no type scale"

    offenders: dict[str, set[float]] = {}
    for family in FAMILIES:
        for path in _family_files(family):
            sizes = {float(size) for size in SIZE_DECLARATION.findall(path.read_text("utf-8"))}
            stray = sizes - scale - DISPLAY_SIZES
            if stray:
                offenders.setdefault(family, set()).update(stray)

    assert not offenders, (
        f"these sizes are on no step of the scale: {offenders}. Add a step deliberately, "
        "or use the nearest one -- a value chosen ad hoc is how the previous 53 accrued."
    )


def test_the_scale_steps_are_far_enough_apart_to_be_choices() -> None:
    """A step a reader cannot perceive is duplication wearing a name.

    Optimising purely for how little the documents moved produced steps 0.2pt apart --
    which minimises change and consolidates nothing, because it preserves exactly the
    near-duplicates the scale exists to remove.
    """

    steps = sorted(_declared_scale())
    # Not strict: an offset zip is meant to be one shorter.
    gaps = [round(b - a, 4) for a, b in zip(steps, steps[1:])]  # noqa: B905
    assert min(gaps) >= 0.6, f"these steps are closer than 0.6pt apart: {list(zip(steps, gaps))}"


DESIGN_TOKENS = Path("templates/typst/_shared/v1/_design.typ")


def _palette_keys(name: str) -> set[str]:
    """The keys of one named lookup in the design system.

    Scoped to the block rather than to every `"key":` line in the file. There are two
    lookups now -- series colours and narrative tones -- and a whole-file scan read the
    tone names as undeclared series.
    """
    source = DESIGN_TOKENS.read_text(encoding="utf-8")
    block = source.split(f"#let {name} = (", 1)[1].split(")", 1)[0]
    return set(re.findall(r'"([a-z0-9-]+)":', block))


def test_every_series_a_chart_can_name_is_declared_in_the_design_system() -> None:
    """A name with no colour behind it fails the whole document, not just its chart.

    Typst resolves `SERIES_PALETTE.at(name)` at compile time. The palette lives in the
    design system and the emitters name a series, so nothing but this holds the two
    together.
    """

    from app.services.chart_geometry import UNCHARTED_COLOUR
    from app.services.portfolio_charts import ALLOCATION_PALETTE

    declared = _palette_keys("SERIES_PALETTE")
    named = {*ALLOCATION_PALETTE, UNCHARTED_COLOUR}

    assert declared, "no series were parsed out of the design system"
    assert not named - declared, (
        f"these series are named and undeclared: {sorted(named - declared)}"
    )
    assert not declared - named, (
        f"these series are declared and unreachable: {sorted(declared - named)}"
    )


def test_no_emitter_decides_what_a_colour_is() -> None:
    """Colour is the design system's to decide, so a hex literal in Python is a palette
    the templates cannot restyle. `ALLOCATION_PALETTE` was six of them, four duplicating
    tokens that could drift from their own copies without anything noticing."""

    offenders = {
        path.as_posix(): found
        for path in Path("src").rglob("*.py")
        if (found := re.findall(r'"#[0-9A-Fa-f]{3,8}"', path.read_text(encoding="utf-8")))
    }

    assert not offenders, (
        f"these modules name a colour instead of naming a series: {offenders}. Declare it "
        "in _design.typ and emit the name."
    )


SIZE_LITERAL = re.compile(r"size:\s*([\d.]+)pt")
# The declarations in the design module are where the numbers are allowed to be.
SIZE_DECLARATION = re.compile(r"#let\s+(text-[a-z-]+)\s*=\s*([\d.]+)pt")


def test_no_template_spells_a_text_size() -> None:
    """A scale nothing references is a record of the sizes in use, not a scale.

    `_design.typ` declared nine steps and `TYPE_SCALE` beside them, and **no template
    referenced either**: 118 inline `size: Npt` literals against zero uses of a token. The
    convergence from 53 distinct sizes to 12 had been done by hand, so the scale described
    the result rather than governing it -- and "make the small text slightly larger" was
    still a search across twelve numbers in twelve files.

    That is the shape this repository keeps producing: a governed helper exists, and every
    site reads around it. `weight_width_token` and `supplied_text` were the same defect in
    Python in the same week.
    """

    offenders = {
        path.relative_to(TEMPLATE_ROOT).as_posix(): SIZE_LITERAL.findall(
            path.read_text(encoding="utf-8")
        )
        for path in sorted(TEMPLATE_ROOT.rglob("*.typ"))
        if path != DESIGN_MODULE and SIZE_LITERAL.search(path.read_text(encoding="utf-8"))
    }

    assert not offenders, (
        f"these templates spell a text size instead of naming one: {offenders}. Sizes are "
        "declared in _design.typ; a literal here is a twelfth value nobody can find."
    )


def test_the_scale_is_used_rather_than_merely_declared() -> None:
    """The other half, so the rule above cannot be satisfied by drawing no text.

    A guard that only forbids literals is satisfied by a template that sets no sizes at
    all. This one requires every declared step to be reachable and actually asked for --
    a step nothing uses is a size that was retired without being deleted.
    """

    design = DESIGN_MODULE.read_text(encoding="utf-8")
    declared = {name for name, _ in SIZE_DECLARATION.findall(design)}
    assert declared, "the design module declares no text sizes"

    used: set[str] = set()
    for path in sorted(TEMPLATE_ROOT.rglob("*.typ")):
        text = path.read_text(encoding="utf-8") if path != DESIGN_MODULE else ""
        used |= {name for name in declared if re.search(rf"size:\s*{re.escape(name)}\b", text)}

    assert used, "no template names a single scale step; the scale is decorative"
    assert declared == used, (
        f"declared but never asked for: {sorted(declared - used)}. A step nothing sets is "
        "a size that was retired without being deleted, and it will be picked up again by "
        "someone reading the scale as a menu."
    )


def test_every_tone_a_commentary_can_carry_is_declared_in_the_design_system() -> None:
    """The same compile-time lookup as the series palette, one analytic later.

    `TONE_PALETTE.at(tone)` resolves when the template compiles, so a tone with no colour
    behind it fails the whole document rather than one talking point. lotus-report
    normalises the vocabulary before the package is built and Render falls back to
    `neutral` for anything else, but neither of those helps if the two lists drift: the
    fallback is only safe while `neutral` itself is declared.
    """

    from app.services.typst_fragments import COMMENTARY_TONES, NEUTRAL_TONE

    declared = _palette_keys("TONE_PALETTE")

    assert declared, "no tones were parsed out of the design system"
    assert COMMENTARY_TONES == declared, (
        f"the emitter and the palette disagree about the tone vocabulary: "
        f"only in the emitter {sorted(COMMENTARY_TONES - declared)}, "
        f"only in the palette {sorted(declared - COMMENTARY_TONES)}"
    )
    assert NEUTRAL_TONE in declared, "the fallback tone has no colour behind it"
