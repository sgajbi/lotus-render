"""A component copied between template files under a new name is drift the digests bless.

The three governance row components were three copies of one component for months and
nothing said so -- the copies were found only because all three carried the same layout
defect (#213). The rule since is promote-on-second-consumer: chrome moves to `_shared`
when a second family needs it, the way `evidence-row` earned its place. This guard closes
the rule's silent failure mode (#150): a new family, or a new section in an existing one,
copies a component instead of importing it, and the copies drift the way the palettes did.

What counts as a copy is calibrated on the historical case, kept below as verbatim
fixtures: the detector must fire on the pre-#213 copies and stay silent on today's tree.
Adapters -- declarations whose body is a call to another declared component, carrying only
their family's field names and shares -- are the rule's intended end-state and are never
compared: `section-row` and `wave-item-row` are near-identical *as text* precisely
because both are thin field lists over `evidence-row`, and that is promotion, not drift.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

TEMPLATES = Path("templates/typst")

_DECLARATION = re.compile(r"^#let ([a-z][a-z0-9-]*)\(([^)]*)\) =", re.M)
_CALLEE = re.compile(r"^\s*([a-z][a-z0-9-]*)\(")

# Bodies shorter than this are one-line helpers whose similarity says nothing.
_MIN_BODY_TOKENS = 25

# Calibrated on the trees this guard exists for. The pre-#213 copies score 0.826, 0.907
# and 0.917 against each other; the most similar genuinely-different pair in today's tree
# (two page scaffolds sharing shape, not implementation) scores 0.787. The bound sits
# between: every historical copy-pair fires, and the known-innocent ceiling clears by
# 0.033. If a genuinely different pair ever crosses it, the failure names both components
# for the look; recalibrate with the measured pair recorded here, the way 0.787 is.
NEAR_IDENTICAL = 0.82


def _body(rest: str) -> str:
    """A declaration's right-hand side: lines until its brackets balance."""
    lines: list[str] = []
    balance = 0
    for line in rest.splitlines():
        code = line.split("//")[0]
        balance += sum(code.count(c) for c in "([{") - sum(code.count(c) for c in ")]}")
        lines.append(line)
        if balance <= 0:
            break
    return "\n".join(lines)


def _declarations(source: str) -> list[tuple[str, list[str], str]]:
    """Each top-level `#let name(params) = body` in a template file."""
    return [
        (
            match.group(1),
            [p.split(":")[0].strip() for p in match.group(2).split(",") if p.strip()],
            _body(source[match.end() :]),
        )
        for match in _DECLARATION.finditer(source)
    ]


def _collapse(tokens: list[str]) -> list[str]:
    """Drop consecutive repeated token runs, so arity does not distinguish a copy.

    The historical copies differ in column count -- four, five and six fields of the
    same cell -- not in chrome. After collapsing, each is one field of each shape.
    """
    changed = True
    while changed:
        changed = False
        for run in range(40, 0, -1):
            index = 0
            while index + 2 * run <= len(tokens):
                if tokens[index : index + run] == tokens[index + run : index + 2 * run]:
                    del tokens[index + run : index + 2 * run]
                    changed = True
                else:
                    index += 1
    return tokens


def _skeleton(body: str, params: list[str]) -> list[str]:
    """The implementation, with everything a copy-with-rename would change blurred out.

    String literals are the field labels a copier renames; parameter names follow the
    component's name. What survives is the chrome: geometry, sizes, structure.
    """
    text = re.sub(r'"[^"]*"', '""', body)
    for param in params:
        text = re.sub(rf"\b{re.escape(param)}\b", "P", text)
    return _collapse(re.findall(r"[a-zA-Z][\w-]*|\d+(?:\.\d+)?[a-z]*|[^\s\w]", text))


def _implementations(files: dict[str, str]) -> list[tuple[str, str, list[str]]]:
    """The declarations that carry an implementation of their own.

    A body that opens as a call to another declared component is an adapter over an
    already-promoted component: what it carries is its family's data, and two families'
    data being parallel is the shared component working, not a copy.
    """
    declared = [
        (path, name, params, body)
        for path, source in files.items()
        for name, params, body in _declarations(source)
    ]
    names = {name for _, name, _, _ in declared}
    skeletons = [
        (path, name, _skeleton(body, params))
        for path, name, params, body in declared
        if not ((callee := _CALLEE.match(body)) and callee.group(1) in names)
    ]
    return [entry for entry in skeletons if len(entry[2]) >= _MIN_BODY_TOKENS]


def _copies(files: dict[str, str]) -> list[str]:
    """Components in different files whose implementations are near-identical."""
    return [
        f"{name} ({path}) is {ratio:.1%} the implementation of {twin} ({twin_path})"
        for (path, name, skeleton), (twin_path, twin, twin_skeleton) in combinations(
            _implementations(files), 2
        )
        if path != twin_path
        and (ratio := SequenceMatcher(None, skeleton, twin_skeleton).ratio()) >= NEAR_IDENTICAL
    ]


def test_no_two_template_files_declare_the_same_component() -> None:
    """The guard. A hit is either a copy to delete in favour of an import, or the
    second consumer arriving -- in which case the component moves to `_shared` and both
    files adapt over it, which is how `evidence-row` earned its place."""

    files = {
        str(path): path.read_text(encoding="utf-8") for path in sorted(TEMPLATES.rglob("*.typ"))
    }

    assert files, "no template files found"
    assert _copies(files) == []


def test_the_detector_fires_on_the_copies_that_motivated_it() -> None:
    """Executable calibration: the pre-#213 governance rows, verbatim. All three must
    be implicated -- a detector these escape guards nothing."""

    copies = " ".join(
        _copies(
            {
                "proof-pack/v1/main.typ": _PRE_213_PROOF_PACK,
                "rebalance-wave/v1/main.typ": _PRE_213_REBALANCE_WAVE,
                "outcome-review/v1/main.typ": _PRE_213_OUTCOME_REVIEW,
            }
        )
    )

    for name in ("section-row", "wave-item-row", "dimension-row"):
        assert name in copies, f"{name} escaped the detector"


def test_adapters_over_a_promoted_component_are_not_copies() -> None:
    """The reward for following the rule must not trip the guard for it.

    Today's `section-row` and `wave-item-row` are the promoted end-state of the very
    fixtures above: thin field lists over the shared `evidence-row`. Without the adapter
    rule they score higher against each other than the historical copies do."""

    files = {
        path: (TEMPLATES / path).read_text(encoding="utf-8")
        for path in (
            "proof-pack/v1/main.typ",
            "rebalance-wave/v1/main.typ",
            "_shared/v1/_design.typ",
        )
    }

    assert _copies(files) == []


_PRE_213_PROOF_PACK = """
#let section-row(title, section-type, state, summary, reasons) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (auto, auto, auto, 1fr),
    gutter: 4mm,
    [#label("Section") #linebreak() #value(title)],
    [#label("Type") #linebreak() #value(section-type)],
    [#label("State") #linebreak() #value(state)],
    [#label("Summary") #linebreak() #summary #linebreak() #label("Reasons") #linebreak() #reasons],
  )
]
"""

_PRE_213_REBALANCE_WAVE = """
#let wave-item-row(portfolio, state, proof-pack, proof-state, alternative, reasons) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (auto, auto, auto, auto, 1fr),
    gutter: 4mm,
    [#label("Portfolio") #linebreak() #value(portfolio)],
    [#label("State") #linebreak() #value(state)],
    [#label("Proof pack") #linebreak() #value(proof-pack)],
    [#label("Proof state") #linebreak() #value(proof-state)],
    [#label("Alternative") #linebreak() #value(alternative) #linebreak() #label("Reasons") #linebreak() #reasons],
  )
]
"""

_PRE_213_OUTCOME_REVIEW = """
#let dimension-row(dimension, state, expected, realized, variance, explanation) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (auto, auto, auto, auto, auto, 1fr),
    gutter: 4mm,
    [#label("Dimension") #linebreak() #value(dimension)],
    [#label("State") #linebreak() #value(state)],
    [#label("Expected") #linebreak() #value(expected)],
    [#label("Realized") #linebreak() #value(realized)],
    [#label("Variance") #linebreak() #value(variance)],
    [#label("Explanation") #linebreak() #explanation],
  )
]
"""
