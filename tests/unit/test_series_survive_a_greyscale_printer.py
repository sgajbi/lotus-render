"""Any two series one chart can draw stay distinguishable on a greyscale printer.

Colour is the only key a donut has, and in greyscale the key IS the luminance. Three of
the six series used to sit inside a 0.04 gamma-space Rec.709 band -- identical keys to a
printer (#217, #207's finding arriving through print). The palette is now a luminance
ladder; this guard measures it from the design tokens themselves, so a future palette
edit that quietly collapses two rungs fails here with the pair named.

`series-uncharted` is in the set because it is drawn in the same ring as the series --
a remainder a reader cannot tell from a slice would claim an allocation nobody stated.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

DESIGN = Path("templates/typst/_shared/v1/_design.typ")

# Measured 0.0884 between the two brand accents (which did not move -- brand identity
# outranks a wider rung) after #217's re-spacing set every other gap at 0.09 or more.
# A floor rather than an exact bank: widening the ladder is improvement, not drift.
MIN_GREYSCALE_SEPARATION = 0.085

SERIES = ("series-1", "series-2", "series-3", "series-4", "series-5", "series-6")


def _tokens() -> dict[str, str]:
    """Every `#let name = ...` in the design system, aliases resolved to hex."""
    source = DESIGN.read_text(encoding="utf-8")
    direct = dict(re.findall(r'#let ([a-z0-9-]+) = rgb\("(#[0-9A-Fa-f]{6})"\)', source))
    aliases = dict(re.findall(r"#let ([a-z0-9-]+) = ([a-z0-9-]+)$", source, re.M))
    resolved = dict(direct)
    for name, target in aliases.items():
        seen = {name}
        while target in aliases and target not in seen:
            seen.add(target)
            target = aliases[target]
        if target in direct:
            resolved[name] = direct[target]
    return resolved


def _luminance(hex_value: str) -> float:
    red, green, blue = (int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def test_series_survive_a_greyscale_printer() -> None:
    tokens = _tokens()
    ring = {name: _luminance(tokens[name]) for name in (*SERIES, "series-uncharted")}

    too_close = [
        f"{a} ({ring[a]:.3f}) vs {b} ({ring[b]:.3f}): delta {abs(ring[a] - ring[b]):.3f}"
        for a, b in combinations(ring, 2)
        if abs(ring[a] - ring[b]) < MIN_GREYSCALE_SEPARATION
    ]

    assert not too_close, (
        "these palette entries print as the same grey; re-space the luminance ladder "
        f"(floor {MIN_GREYSCALE_SEPARATION}): " + "; ".join(too_close)
    )


def test_the_ladder_is_measured_from_the_real_tokens() -> None:
    """The guard reads the design system, not a copy of it: every series resolves to a
    hex, including the two that are aliases of the brand accents."""

    tokens = _tokens()

    for name in (*SERIES, "series-uncharted"):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", tokens.get(name, "")), (
            f"{name} did not resolve to a hex colour in _design.typ"
        )
