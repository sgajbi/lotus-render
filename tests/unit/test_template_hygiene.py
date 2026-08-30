"""The templates get the dead-code gate the Python already has.

`dead_code_gate.py` runs vulture over `src`, so an unused Python helper fails CI. The
templates had no equivalent, and four helpers had accumulated that nothing called --
`block-gap`, `section-gap`, `metric-value` and `content-item` -- alongside three the
appendix rewrite orphaned. None of them could have been noticed.

Reachability in a template is not just "another template calls it". Much of what a
document contains is written by an emitter in `src` and substituted into a placeholder,
so `#line-chart(...)` never appears in a `.typ` file at all. And `_theme.typ` exists to
re-export design tokens, so a name it imports and never uses itself is still doing its
job. Both are counted.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE_ROOT = Path("templates/typst")
SOURCE_ROOT = Path("src")

# `#let name(...)` and `#let name = ...`, anchored so a binding inside a function body
# is not mistaken for an exported helper.
_DECLARATION = re.compile(r"^#let ([a-z][a-z0-9-]*)\s*[(=]", re.M)
_IMPORT = re.compile(r'^#import "([^"]+)":\s*(.+)$', re.M)


def _templates() -> list[Path]:
    return sorted(TEMPLATE_ROOT.rglob("*.typ"))


def _emitter_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SOURCE_ROOT.rglob("*.py"))


def _references(name: str, text: str) -> int:
    # `-` is not a word character, so a plain boundary would find `chart-card` inside
    # `image-chart-card`. Require a non-name character on each side.
    return len(re.findall(rf"(?<![a-z0-9-]){re.escape(name)}(?![a-z0-9-])", text))


def _imported_names(text: str) -> list[tuple[str, str]]:
    """(module, name) for every name a template imports."""
    return [
        (module, name.strip())
        for module, names in _IMPORT.findall(text)
        for name in names.split(",")
        if name.strip()
    ]


def test_every_template_helper_is_reachable() -> None:
    """A helper nothing calls is worse than dead Python: it sits inside the bytes the
    template manifest digest covers, so it is re-approved on every change around it."""

    templates = _templates()
    assert templates, "no templates were inspected; the gate would pass over anything"

    all_template_text = "\n".join(path.read_text(encoding="utf-8") for path in templates)
    emitters = _emitter_text()

    unreachable = [
        f"{path.as_posix()}:{name}"
        for path in templates
        for name in _DECLARATION.findall(path.read_text(encoding="utf-8"))
        # One reference is the declaration itself.
        if _references(name, all_template_text) <= 1 and not _references(name, emitters)
    ]

    assert not unreachable, (
        "these template helpers are declared and never called, by a template or by an "
        f"emitter: {unreachable}"
    )


def test_no_template_imports_a_name_it_neither_uses_nor_passes_on() -> None:
    """An import that nothing uses outlives whatever needed it.

    Moving the section header out of the flow left five templates importing
    `page-header` and `_performance.typ` importing `section-title` and `soft-rule`. All
    of it compiles, and each stale import says the file still draws its own header.
    """

    templates = _templates()
    emitters = _emitter_text()
    # A name is passed on when another template imports it from this one, which is what
    # `_theme.typ` is for.
    re_exported: set[tuple[str, str]] = set()
    for path in templates:
        for module, name in _imported_names(path.read_text(encoding="utf-8")):
            re_exported.add((Path(module).stem, name))

    unused: list[str] = []
    for path in templates:
        text = path.read_text(encoding="utf-8")
        body = "\n".join(line for line in text.splitlines() if not line.startswith("#import"))
        for _, name in _imported_names(text):
            if _references(name, body):
                continue
            # Emitted content is substituted into this file's placeholders, so a name
            # only an emitter writes is still used here.
            if _references(name, emitters):
                continue
            if (path.stem, name) in re_exported:
                continue
            unused.append(f"{path.as_posix()}:{name}")

    assert not unused, f"these imports are never used: {unused}"
