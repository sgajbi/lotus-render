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
            # Blocked: `performance-bar-row` still scales with `percent_width_token`,
            # which floors at 8% and drops the sign. Wiring it would put the defect
            # #151 removed from the other charts back on the page (#154).
            "PERFORMANCE_BAR_ROWS",
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
