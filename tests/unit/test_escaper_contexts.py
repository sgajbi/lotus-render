"""Report data is untrusted, and it reaches the compiler in two different contexts.

Typst has two escaping contexts and they are not interchangeable:

- a **string literal**, ``"..."``, where only ``\\`` and ``"`` can change the structure;
- **markup**, ``[...]``, where every token in ``MARKUP_TOKENS`` can change the page.

That second list used to stop at ``#``, ``[``, ``]``, ``{``, ``}``, ``$`` and ``@`` --
the tokens that introduce code -- and so did the escaper. The rest of Typst's markup
stayed live, which cost a rendered narrative its tildes and its asterisks and drew
headings the data never asked for. ``test_report_text_survives_the_page`` reads that
back off a page; what is here is the two contexts staying distinguishable.

#103 was the first half going wrong: the markup escaper leaves ``"`` live, so a quote in
a security name closed the literal and broke the compile. The gate written then checks
`typst_tables.py` only, and only in that direction.

The other half is worse and unguarded. ``escape_typst_string`` leaves ``#`` untouched --
``#panic("owned")`` survives it verbatim -- so a value escaped for a string literal and
emitted into markup is **live Typst code supplied by the report producer**. It is correct
today by convention; nothing enforced it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.typst_fragments import (
    render_advisory_disclosure_blocks,
    render_advisory_narrative_blocks,
    render_key_value_rows,
    render_outcome_dimension_rows,
    render_proof_pack_section_rows,
    render_wave_event_rows,
    render_wave_item_rows,
)

SERVICES = Path("src/app/services")

# Emitters that build `name([value], ...)`, where the value sits in markup.
MARKUP_EMITTERS = ("typst_fragments.py",)
# Emitters that build `name("value", ...)`, where the value sits in a string literal.
STRING_LITERAL_EMITTERS = (
    "typst_tables.py",
    "typst_contexts.py",
    # One module per analytic, holding both how Render reads it and how it draws it.
    "contribution_ranking.py",
)

# Would execute if it reached markup unescaped: `#panic` aborts the compile outright, and
# the brackets and braces would restructure whatever contains them.
HOSTILE = '#panic("owned") [x] {y} $z$ @ref \\ "quote"'


def test_a_markup_emitter_never_uses_the_string_literal_escaper() -> None:
    """`escape_typst_string` leaves `#` live, which in markup is a code expression."""

    for name in MARKUP_EMITTERS:
        source = (SERVICES / name).read_text(encoding="utf-8")
        assert "escape_typst_text" in source, f"{name} should escape for markup"
        assert "escape_typst_string(" not in source, (
            f"{name} emits values into markup, where escape_typst_string leaves '#', '[' "
            "and '$' live -- report data would become Typst code. Use escape_typst_text."
        )


def test_a_string_literal_emitter_never_uses_the_markup_escaper() -> None:
    """The #103 direction, extended to every module that emits string literals.

    The original gate covered `typst_tables.py` alone. `typst_contexts.py` emits about a
    hundred scalars into the same `"..."` context and was never checked.
    """

    for name in STRING_LITERAL_EMITTERS:
        source = (SERVICES / name).read_text(encoding="utf-8")
        assert "escape_typst_string" in source, f"{name} should escape for string literals"
        assert "escape_typst_text(" not in source, (
            f"{name} emits Typst string literals; escape_typst_text leaves the closing "
            'quote live, so a value containing " breaks out of the literal into code.'
        )


@pytest.mark.parametrize(
    "emitted",
    [
        pytest.param(render_wave_item_rows([{"portfolio_id": HOSTILE}]), id="wave-item"),
        pytest.param(render_wave_event_rows([{"event_type": HOSTILE}]), id="wave-event"),
        pytest.param(render_outcome_dimension_rows([{"dimension": HOSTILE}]), id="dimension"),
        pytest.param(render_proof_pack_section_rows([{"title": HOSTILE}]), id="proof-section"),
        pytest.param(render_key_value_rows({"k": HOSTILE}), id="key-value"),
        pytest.param(
            render_advisory_narrative_blocks([{"title": "t", "body": HOSTILE}]), id="narrative"
        ),
        pytest.param(
            render_advisory_disclosure_blocks([{"disclosure_id": "d", "text": HOSTILE}]),
            id="disclosure",
        ),
    ],
)
def test_no_markup_emitter_lets_report_data_become_code(emitted: str) -> None:
    """A property of what is emitted, which a source scan cannot establish.

    Asserted as "the value appears in its escaped form" rather than "the dangerous
    characters are absent": an escaped token still contains the raw one as a substring
    (`\\@ref` contains `@ref`), and the fragment legitimately contains the emitter's own
    `#name(` and brackets. Presence of the escaped form is the unambiguous property.
    """

    from app.services.typst_values import escape_typst_text

    defanged = escape_typst_text(HOSTILE)
    assert defanged in emitted, (
        "the value was not escaped for markup, so report data reaches Typst as code.\n"
        f"  expected: {defanged}\n"
        f"  emitted:  {emitted}"
    )


def test_the_two_escapers_disagree_about_exactly_what_makes_them_different() -> None:
    """Neither escaper is a superset of the other, which is why the context decides.

    Stated as a test so a future simplification to "one escaper" has to confront it.
    """

    from app.services.typst_values import escape_typst_string, escape_typst_text

    # The markup escaper neutralises '#'; the string escaper deliberately does not.
    assert escape_typst_text("#a") == "\\#a"
    assert escape_typst_string("#a") == "#a"
    # The string escaper neutralises '"'; the markup escaper deliberately does not.
    assert escape_typst_string('a"b') == 'a\\"b'
    assert escape_typst_text('a"b') == 'a"b'


def test_the_original_one_directional_gate_is_now_redundant() -> None:
    """#103's gate checked one file in one direction; both directions are covered above.

    Kept as a pointer rather than deleted quietly, so the reason the older test can go is
    written down where someone removing it will read it.
    """

    original = Path("tests/unit/test_code_health_gates.py").read_text(encoding="utf-8")
    assert re.search(r"def test_string_literal_emitters_do_not_use_the_markup_escaper", original), (
        "the #103 gate has moved or gone; make sure both directions are still covered here"
    )
