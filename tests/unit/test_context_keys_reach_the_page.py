"""Every context key a builder produces should end up on a page.

A key that no template substitutes is work done on every render and thrown away, and
nothing in the suite noticed: the tests assert the context *dictionary*, so

    assert "#period-row(" in template_context["PERFORMANCE_PERIOD_ROWS"]

passed for as long as that key reached no template at all. That is the same gap as the
determinism fingerprint -- a check on an intermediate proves the intermediate is
well-formed, never that it reached the output.

The reverse direction is already visible: a `${TOKEN}` no builder produces survives
substitution and shows up in the document as literal `${TOKEN}`. This side is silent,
so it needs a gate.

The inventory below is a ratchet, not a wish. It records what is orphaned today, with
why, so the number cannot grow quietly. Removing an entry -- by drawing the key or by
deleting the work that computes it -- is the progress; the test fails on drift in either
direction so the list has to stay honest.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.services.typst_contexts import (
    build_outcome_review_context,
    build_portfolio_review_context,
    build_proof_pack_context,
    build_wave_context,
)

TEMPLATE_ROOT = Path("templates/typst")
FIXTURES_PATH = Path("tests/golden/producer-fixtures.v1.json")

CONTEXT_BUILDERS = {
    "portfolio-review": build_portfolio_review_context,
    "proof-pack": build_proof_pack_context,
    "outcome-review": build_outcome_review_context,
    "rebalance-wave": build_wave_context,
}

# Keys the render service adds after the builder runs, in `_materialize_template`.
SERVICE_KEYS = frozenset({"DETERMINISM_STATEMENT", "TRACE_ID", "CORRELATION_ID"})

# Produced today, drawn nowhere. Each line is a debt with an owner, not an exemption.
ORPHANED_KEYS: dict[str, frozenset[str]] = {
    "portfolio-review": frozenset(
        {
            # Governance signals computed per render and shown on no page (#158).
            "BENCHMARK_STATUS",
            "COMPLETENESS_STATUS",
            "DATA_QUALITY_STATUS",
            "READINESS_STATUS",
            # Provenance. The other three families print trace and template identity in
            # their footer; the client-facing review prints none of it (#158).
            "RENDER_JOB_ID",
            "REQUESTED_BY",
            "SOURCE_SERVICES",
            "TEMPLATE_ID",
            "TEMPLATE_VERSION",
            # Content built and discarded (#154).
            "HOLDING_ROWS",
            "OBSERVATION_NOTES",
            "PERFORMANCE_MONTHLY_CHART_ROWS",
        }
    ),
    # All four families compute who asked for the document and print it on none of them
    # (#158). That it is the same key everywhere makes it one decision, not four.
    "proof-pack": frozenset({"REQUESTED_BY"}),
    "outcome-review": frozenset({"REQUESTED_BY"}),
    "rebalance-wave": frozenset({"REQUESTED_BY"}),
}


def _referenced_keys(template_id: str, template_version: str) -> set[str]:
    directory = TEMPLATE_ROOT / template_id / template_version
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(directory.rglob("*.typ"))
    )
    return set(re.findall(r"\$\{([A-Z0-9_]+)\}", source))


def _fixtures() -> list[dict[str, str]]:
    manifest = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    seen: dict[str, dict[str, str]] = {}
    for fixture in manifest["fixtures"]:
        seen.setdefault(fixture["template_id"], fixture)
    return list(seen.values())


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda fixture: fixture["template_id"])
def test_no_new_context_key_is_built_and_then_drawn_nowhere(fixture: dict[str, str]) -> None:
    template_id = fixture["template_id"]
    package = RenderPackage.model_validate_json(
        Path(fixture["package_path"]).read_text(encoding="utf-8")
    )

    produced = set(CONTEXT_BUILDERS[template_id](package))
    referenced = _referenced_keys(template_id, fixture["template_version"])
    orphaned = produced - referenced

    assert orphaned == ORPHANED_KEYS[template_id], (
        f"the set of {template_id} context keys that reach no template has changed.\n"
        f"  newly orphaned: {sorted(orphaned - ORPHANED_KEYS[template_id])}\n"
        f"  now drawn:      {sorted(ORPHANED_KEYS[template_id] - orphaned)}\n"
        "A key nothing substitutes is computed on every render and discarded. Draw it, "
        "delete the work that builds it, or re-bank this inventory with the reason."
    )


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda fixture: fixture["template_id"])
def test_every_token_a_template_references_is_produced(fixture: dict[str, str]) -> None:
    """The other direction: an unsubstituted `${TOKEN}` reaches the client verbatim."""

    template_id = fixture["template_id"]
    package = RenderPackage.model_validate_json(
        Path(fixture["package_path"]).read_text(encoding="utf-8")
    )

    produced = set(CONTEXT_BUILDERS[template_id](package)) | SERVICE_KEYS
    missing = _referenced_keys(template_id, fixture["template_version"]) - produced

    assert not missing, (
        f"{template_id} templates reference tokens nothing produces: {sorted(missing)}. "
        "These survive substitution and print as literal ${TOKEN} in the document."
    )


CALL_FRAGMENT = re.compile(r"^[a-z][a-z0-9-]*\(")


def _substitution_contexts(template_id: str, template_version: str) -> dict[str, set[str]]:
    """Where each key is substituted: Typst markup, or inside a code expression.

    A key spliced into `..( ... ).flatten()` sits in code, where a call is written bare.
    Anywhere else is markup, where a bare call is text.
    """
    directory = TEMPLATE_ROOT / template_id / template_version
    found: dict[str, set[str]] = {}
    for path in sorted(directory.rglob("*.typ")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            for match in re.finditer(r"\$\{([A-Z0-9_]+)\}", line):
                before = line[: match.start()].strip()
                previous = next(
                    (lines[i].strip() for i in range(index - 1, -1, -1) if lines[i].strip()),
                    "",
                )
                in_code = before.endswith(("(", ",")) or (
                    not before and previous.endswith(("(", ","))
                )
                found.setdefault(match.group(1), set()).add("code" if in_code else "markup")
    return found


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda fixture: fixture["template_id"])
def test_a_fragment_is_invoked_where_it_lands_rather_than_printed(
    fixture: dict[str, str],
) -> None:
    """In Typst markup a bare `name(...)` is text, so the page prints the source.

    Three families shipped that way. The outcome review's dimension evidence -- the
    substance of the document -- read on the page as

        dimension-row([PERFORMANCE], [READY], [4.10], [4.22], [0.12], [...])

    and every golden fingerprint was green over it, because a document that prints its
    own source is byte-identical to itself.

    The rule runs both ways: a `#` is equally wrong in a code context, where it is a
    syntax error rather than a cosmetic problem.
    """

    template_id = fixture["template_id"]
    package = RenderPackage.model_validate_json(
        Path(fixture["package_path"]).read_text(encoding="utf-8")
    )
    context = CONTEXT_BUILDERS[template_id](package)
    contexts = _substitution_contexts(template_id, fixture["template_version"])

    printed_as_text: list[str] = []
    invalid_in_code: list[str] = []
    for key, where in contexts.items():
        fragment = context.get(key, "").lstrip()
        if not fragment:
            continue
        if "markup" in where and CALL_FRAGMENT.match(fragment):
            printed_as_text.append(f"{key}: {fragment[:60]}")
        if "code" in where and fragment.startswith("#"):
            invalid_in_code.append(f"{key}: {fragment[:60]}")

    assert not printed_as_text, (
        f"{template_id} substitutes these into markup as bare calls, so the document "
        f"prints them as its own source: {printed_as_text}"
    )
    assert not invalid_in_code, (
        f"{template_id} substitutes these into a code context with a leading '#', "
        f"which will not compile: {invalid_in_code}"
    )


SEQUENCE_GUARD = re.compile(r"isinstance\(\w+, Sequence\) or isinstance\(")
EMITTER_MODULES = ("typst_tables.py", "typst_fragments.py")


def test_the_sequence_guard_is_written_once() -> None:
    """Fifteen emitters opened with the same two-line guard, copied by hand each time.

    Copies do not stay in step -- that is what produced four values of `accent` and three
    definitions of `key-value-row`. `mapping_entries` states the shape once, and
    `string_list` is its sibling for emitters whose items are plain strings.

    `typst_values.py` is excluded because it is where both helpers are defined.
    """

    offenders = {
        name: len(SEQUENCE_GUARD.findall((Path("src/app/services") / name).read_text("utf-8")))
        for name in EMITTER_MODULES
    }
    offenders = {name: count for name, count in offenders.items() if count}

    assert not offenders, (
        f"these modules still write the sequence guard out longhand: {offenders}. Use "
        "mapping_entries for mappings, or string_list for plain strings."
    )


def test_an_empty_collection_says_so_rather_than_rendering_nothing() -> None:
    """ "Absent" and "empty" mean the same thing to a reader, so they must look the same.

    `render_observation_notes` was the one emitter where they diverged: an absent list
    said "No governed observations available", and an empty list rendered nothing at all
    -- a blank region on the page indistinguishable from a layout fault.

    The other emitters named in #155 turned out already to agree; the issue overstated
    the divergence, and this test is what pins the corrected claim.
    """

    from app.services.typst_tables import (
        render_holding_rows,
        render_observation_notes,
        render_performance_period_rows,
    )

    for emitter in (render_observation_notes, render_holding_rows, render_performance_period_rows):
        absent = emitter(None)
        empty = emitter([])
        assert "empty-state(" in absent, f"{emitter.__name__} says nothing when the list is absent"
        assert "empty-state(" in empty, (
            f"{emitter.__name__} renders nothing at all for an empty list, which reads as a "
            "layout fault rather than as an absence of data"
        )


def test_a_section_is_present_only_when_it_has_content() -> None:
    """`HAS_*` flags gate whole pages, so an empty collection must read as absent.

    A page guarded by a flag that says "yes" for an empty list ships near-blank, which is
    what #138 removed for the performance and allocation sections.
    """

    from app.services.typst_contexts import _presence_flag

    assert _presence_flag([{"row": 1}]) == "yes"
    assert _presence_flag([]) == "no"
    assert _presence_flag({"key": "value"}) == "yes"
    assert _presence_flag({}) == "no"
    assert _presence_flag(None) == "no"
    assert _presence_flag("text") == "yes"
