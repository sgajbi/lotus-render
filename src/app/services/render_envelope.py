"""Whether the governed runtime can render this document at all.

`MAX_PAYLOAD_LIST_ITEMS` admits 10,000 items per list. The compile envelope is 512 MB per
render. Nothing connected those two numbers, so a package could validate, be accepted with
`201`, hold one of two render slots for about twenty seconds, and always fail (#168).

Measured 2026-08-31 through the governed runtime, each section scaled on its own and then
together:

===============  =================  =================
shape            largest rendered   smallest failure
===============  =================  =================
positions                    3,125              3,250
transactions                 4,875              5,000
both                         1,875              2,000
===============  =================  =================

Two things follow.

**A per-list ceiling cannot express this.** The shapes differ by 2.6x, so any single item
count is either wrong for positions or wrong for transactions. The limit belongs to the
document; `MAX_PAYLOAD_LIST_ITEMS` is per list and stays, because it bounds every list
including the ones this model says nothing about.

**The costs add as reciprocals.** ``1/3125 + 1/4875`` gives 1,904, inside the measured
bracket for both together. Checked against five asymmetric mixes, two within 4% of the
boundary, and it held for all five. `scripts/capacity_probe.py --verify-model` re-runs it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

#: Rows of each shape the runtime was measured to *fail* at. Not a safe envelope: these
#: are the failure points themselves, found by doubling and then bisecting.
#:
#: Provenance -- the facts a future reader needs to judge staleness without archaeology:
#: measured 2026-08-31 by `scripts/capacity_probe.py` at 125-row bisect precision, on a
#: Windows 11 developer machine through the *docker* branch (`--memory 512m`,
#: ghcr.io/typst/typst:0.14.2); production takes the in-process branch under `ulimit -v`.
#: Cost per row is a function of how many sections draw that row, so any PR that adds a
#: section or materially changes a row emitter re-runs `--verify-model` and re-banks
#: these in the same change if the rule no longer holds. Sections added since the
#: measurement: contribution ranking, advisor commentary, allocation dimension blocks,
#: the panel note lines -- `--verify-model` re-confirmed the rule on 2026-08-31 and the
#: margin in `ADMITTED_COST` is what absorbs drift between re-measurements.
#:
#: Re-verified 2026-09-03 after the attribution bridge, the earnings statement, the
#: table conversions and enforced PDF/A-2a landed: the rule held on all five mixed
#: verification shapes, and the drift the margin exists for was observed for the first
#: time -- the positions-only boundary tightened one bisect step (3,000 now renders,
#: 3,125 fails; it was the reverse), while transactions (4,875/5,000) and the both
#: shape (1,875/2,000) did not move. Admission caps positions-only at 0.85 x 3,125 =
#: 2,656, comfortably under the tightened 3,000 -- the ceilings stay banked at the
#: original failure points and the margin keeps carrying the drift.
CEILING_POSITIONS = 3_125
CEILING_TRANSACTIONS = 4_875

#: The share of the measured ceiling this service admits.
#:
#: The ceilings were found by bisection with 125-row precision, which is 4% at 3,125, on
#: one machine through Docker's 512 MB bound -- while production takes the in-process
#: branch under `ulimit -v`. A template change moves the ceiling too, since cost per row
#: is a function of how many sections draw that row, and the model is re-verified on a
#: cadence rather than per render.
#:
#: So 15% covers the measurement precision plus machine and template variance that is
#: real and unquantified. The asymmetry is deliberate: refusing a document at 0.9 that
#: would have rendered costs the caller an actionable message, and admitting one at 1.0
#: that will not costs a render slot, twenty seconds of thrashing, and a failure the
#: caller discovers afterwards.
ADMITTED_COST = 0.85


def _row_count(value: object) -> int:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value)
    return 0


def document_cost(report_data: Mapping[str, object]) -> float:
    """This document's share of the render envelope, where 1.0 is the measured failure.

    Positions are counted from whichever key the position table draws from, so the cost
    matches what will actually be compiled rather than what the package happens to name.
    """
    positions = _row_count(report_data.get("positions")) or _row_count(
        report_data.get("top_holdings")
    )
    transactions = _row_count(report_data.get("transactions"))
    return positions / CEILING_POSITIONS + transactions / CEILING_TRANSACTIONS


def envelope_refusal(report_data: Mapping[str, object]) -> str | None:
    """Why this document cannot be rendered, or None when it can.

    The message names the numbers because "too large" is not actionable and this refusal
    is not retryable: the same document will exceed the same envelope every time, so the
    caller needs to know what to reduce and by how much.
    """
    cost = document_cost(report_data)
    if cost <= ADMITTED_COST:
        return None
    positions = _row_count(report_data.get("positions")) or _row_count(
        report_data.get("top_holdings")
    )
    transactions = _row_count(report_data.get("transactions"))
    return (
        f"This document is {cost / ADMITTED_COST:.2f} times the size the governed render "
        f"envelope accepts: {positions:,} positions and {transactions:,} transactions, "
        f"against measured ceilings of {CEILING_POSITIONS:,} positions or "
        f"{CEILING_TRANSACTIONS:,} transactions on their own. The two costs add, so "
        "reducing either helps. It will fail identically on retry."
    )
