"""Every key an emitter reads is exercised by some banked package.

A fixture built from what a document happened to need, rather than from what the producer
actually sends, cannot fail when the producer sends something the fixture omits. The
lotus-report session found that shape on their side -- a render-package fixture supplying
only the five forwarded risk fields, so it could not fail when the boundary dropped the
rest -- and warned that any fixture of ours derived the same way has the same blind spot.

It does. `report_data.get("positions")` is read by the position table, `_positions` is a
key lotus-report emits on every portfolio review, and no golden carried it: the table has
only ever been rendered through its `or report_data.get("top_holdings")` fallback.

`top_holdings` is `positions[:5]`, so on a three-holding fixture the two are the same rows
and the document does not change. What changes is which branch has ever run.

This is the general form: a key Render reads and no fixture supplies is a path that cannot
be tested by any golden, however many goldens there are.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SERVICES = Path("src/app/services")
GOLDEN_ROOT = Path("tests/golden")

READS_KEY = re.compile(r'report_data\.get\(\s*"([a-z_]+)"')

# Keys an emitter reads that no package is expected to carry, each with the reason. An
# entry here is a standing claim that the key is dead or unreachable, not a way past the
# rule -- so it should shrink.
UNEXERCISED: dict[str, str] = {
    # Alternative spellings lotus-report does not emit; kept because `row_sequence` accepts
    # either and the contract has carried both names.
    "performance_series": "alias of performance_monthly_history",
    "allocation_items": "alias of allocation_breakdowns.by_asset_class",
}


def _keys_read() -> set[str]:
    return {
        key
        for path in sorted(SERVICES.rglob("*.py"))
        for key in READS_KEY.findall(path.read_text(encoding="utf-8"))
    }


def _keys_supplied() -> set[str]:
    supplied: set[str] = set()
    for path in sorted(GOLDEN_ROOT.rglob("render-package.json")):
        package = json.loads(path.read_text(encoding="utf-8"))
        report_data = package.get("report_data")
        if isinstance(report_data, dict):
            supplied |= set(report_data)
    return supplied


def test_every_key_an_emitter_reads_is_supplied_by_some_fixture() -> None:
    """Otherwise the branch that reads it has never run against a banked package."""

    unexercised = _keys_read() - _keys_supplied() - set(UNEXERCISED)

    assert not unexercised, (
        f"these keys are read by an emitter and supplied by no fixture: "
        f"{sorted(unexercised)}. A key no package carries is a path no golden can "
        "exercise -- add it to a fixture, or record here why no package sends it."
    )


def test_the_unexercised_list_names_only_keys_that_are_really_unexercised() -> None:
    """The list is a ratchet, not a place to leave things.

    An entry that a fixture now supplies is a stale exemption, and a stale exemption is
    how an allow-list stops describing anything.
    """

    stale = sorted(set(UNEXERCISED) & _keys_supplied())

    assert not stale, (
        f"these keys are exempted as unexercised and a fixture now supplies them: {stale}. "
        "Remove the exemption; the rule covers them."
    )
