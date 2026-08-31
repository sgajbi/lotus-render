"""Measure where a render stops fitting in its envelope, per document shape.

`MAX_PAYLOAD_LIST_ITEMS` admits 10,000 items per list. The compile envelope is 512 MB per
render (`--memory 512m`, and `ulimit -v` on the in-process branch). Nothing connected
those two numbers, so a package can validate, be accepted with 201, hold one of two
render slots, and always fail (#168).

The earlier form of this probe reported "rows of each" while scaling only transactions.
It listed `positions` among the sections to grow, and the golden package has no
`positions` key -- it supplies holdings under `top_holdings` -- so that half was skipped
silently. The banked figure of 2,475 was 2,475 transactions against three holdings.

Measured on 2026-08-31, each section scaled on its own and then together:

    shape          largest rendered   smallest failure
    positions                 3,125              3,250
    transactions              4,875              5,000
    both                      1,875              2,000

Two things follow, and they decide which of #168's three options is available.

**A per-list ceiling cannot express this constraint.** The shapes differ by 2.6x, so any
single item count is either wrong for positions or wrong for transactions. The limit
belongs to the document, and `MAX_PAYLOAD_LIST_ITEMS` is per list.

**The costs add as reciprocals.** 1/3125 + 1/4875 gives 1,904, which is inside the
measured bracket for `both`. Stated as a rule::

    positions / 3125  +  transactions / 4875  <=  1

Checked against five asymmetric mixes, including two just under the boundary:

    positions  transactions   cost   predicted    actual
        3,000           500   1.06      KILLED    KILLED
        2,500           500   0.90     renders   renders
          500         4,000   0.98     renders   renders
        1,500         1,500   0.79     renders   renders
        2,800           300   0.96     renders   renders

Five for five. `--verify-model` re-runs that table, so the rule stays falsifiable rather
than becoming a remembered claim.

The cliff is sharp. 3,125 positions render in fourteen seconds and 3,250 spend seventeen
being killed; nothing in the timings warns that the limit is close. That is what
exhausting memory looks like, so a ceiling wants real margin rather than a round number
just below the last success.

This is a tool, not a gate. Every number here moves when the templates, the envelope or
the concurrency limit change -- the transactions ceiling rose when the statement tables
stopped drawing five fields no transaction supplies, because a cheaper row buys more
rows. A measurement banked as an assertion would go stale or fail on slower hardware.
Re-run it when any of those change::

    make capacity-probe
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.contracts.render_package import (  # noqa: E402
    MAX_PAYLOAD_LIST_ITEMS as MAX_ITEMS,
)
from app.contracts.render_package import RenderPackage  # noqa: E402
from app.core.settings import Settings  # noqa: E402
from app.domain.templates.registry import TemplateRegistry  # noqa: E402
from app.services.render_intake import RenderIntakeService  # noqa: E402
from app.services.typst_rendering import TypstRenderService  # noqa: E402

GOLDEN = Path("tests/golden/portfolio-review/v1/render-package.json")

# A holding and a transaction are not the same size on the page: a position row carries
# more fields and wraps into more lines than a transaction row. Scaling them together
# reports a figure true of neither alone, so each shape is measured on its own too.
# The positions table reads `positions` and falls back to `top_holdings`, which is the
# name the golden package uses, so both are scaled to keep the two in step.
SHAPES = {
    "positions": (("positions", "security_id"), ("top_holdings", "security_id")),
    "transactions": (("transactions", "transaction_id"),),
    "both": (
        ("positions", "security_id"),
        ("top_holdings", "security_id"),
        ("transactions", "transaction_id"),
    ),
}


def _package_with(rows: int, shape: str) -> RenderPackage:
    raw = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = raw["report_data"]
    for key, id_field in SHAPES[shape]:
        source = report.get(key) or []
        if source:
            report[key] = [
                {
                    **copy.deepcopy(source[index % len(source)]),
                    id_field: f"{id_field[:3].upper()}-{index:06d}",
                }
                for index in range(rows)
            ]
    raw["render_job_id"] = f"rdr_capacity_{shape}_{rows}"
    return RenderPackage.model_validate(raw)


def _renders(service: TypstRenderService, rows: int, shape: str) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        result = service.render(_package_with(rows, shape))
    except Exception as exc:  # noqa: BLE001 - the probe reports whatever happens
        return False, time.perf_counter() - started, str(exc).splitlines()[0][:60]
    return True, time.perf_counter() - started, f"{len(result.artifact_bytes) / 1024:.0f} KB"


def _ceiling(service: TypstRenderService, shape: str, low: int, precision: int) -> tuple[int, int]:
    """Double until it fails, then bisect.

    The ceiling differs by shape, so a fixed upper bound would either miss a taller one
    or spend a kill -- twenty seconds of thrashing -- finding out it was set too high.
    """
    print(f"\n--- {shape} ---")
    print(f"{'rows':>7} {'outcome':>9} {'seconds':>8}  detail")
    probe = low
    high = 0
    while True:
        rendered, elapsed, detail = _renders(service, probe, shape)
        print(f"{probe:>7} {'renders' if rendered else 'KILLED':>9} {elapsed:>8.1f}  {detail}")
        if not rendered:
            high = probe
            break
        low = probe
        probe *= 2
        if probe > MAX_ITEMS:
            print(f"{'':>7} {'':>9} {'':>8}  the contract stops at {MAX_ITEMS:,}")
            return low, MAX_ITEMS

    while high - low > precision:
        middle = (low + high) // 2
        rendered, elapsed, detail = _renders(service, middle, shape)
        print(f"{middle:>7} {'renders' if rendered else 'KILLED':>9} {elapsed:>8.1f}  {detail}")
        low, high = (middle, high) if rendered else (low, middle)
    return low, high


# The single-shape ceilings the cost rule is built from. They are inputs to
# `--verify-model`, not assertions: re-measure with a plain run when anything changes.
MODEL_CEILINGS = {"positions": 3125, "transactions": 4875}
# Mixes chosen to sit either side of the boundary, two of them within 4% of it, because
# a rule that only predicts the easy cases predicts nothing.
MODEL_MIXES = ((3000, 500), (2500, 500), (500, 4000), (1500, 1500), (2800, 300))


def _verify_model(service: TypstRenderService, precision_note: str = "") -> bool:
    """Check the additive rule against mixes neither ceiling was measured from."""
    del precision_note
    print(
        "\nverifying  positions/{positions} + transactions/{transactions} <= 1".format(
            **MODEL_CEILINGS
        )
    )
    print(f"{'positions':>10} {'txns':>7} {'cost':>6} {'predicted':>10} {'actual':>9} {'':>6}")
    agreed = True
    for positions, transactions in MODEL_MIXES:
        cost = (
            positions / MODEL_CEILINGS["positions"] + transactions / MODEL_CEILINGS["transactions"]
        )
        predicted = "renders" if cost <= 1.0 else "KILLED"
        package = _mixed_package(positions, transactions)
        try:
            service.render(package)
            actual = "renders"
        except Exception:  # noqa: BLE001 - the probe reports whatever happens
            actual = "KILLED"
        agreed = agreed and predicted == actual
        mark = "" if predicted == actual else "  <-- the rule is wrong here"
        print(f"{positions:>10,} {transactions:>7,} {cost:>6.2f} {predicted:>10} {actual:>9}{mark}")
    print("the rule held" if agreed else "the rule did not hold; re-derive the ceilings")
    return agreed


def _mixed_package(positions: int, transactions: int) -> RenderPackage:
    raw = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = raw["report_data"]
    counts = {"positions": positions, "top_holdings": positions, "transactions": transactions}
    for key, id_field in SHAPES["both"]:
        source = report.get(key) or []
        if source:
            report[key] = [
                {
                    **copy.deepcopy(source[index % len(source)]),
                    id_field: f"{id_field[:3].upper()}-{index:06d}",
                }
                for index in range(counts[key])
            ]
    raw["render_job_id"] = f"rdr_mix_{positions}_{transactions}"
    return RenderPackage.model_validate(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--low", type=int, default=1000, help="rows known to render")
    parser.add_argument("--precision", type=int, default=125, help="stop when the gap is this")
    parser.add_argument(
        "--shapes",
        nargs="+",
        default=list(SHAPES),
        choices=list(SHAPES),
        help="which sections to scale (default: all three)",
    )
    parser.add_argument(
        "--verify-model",
        action="store_true",
        help="re-check the additive cost rule against asymmetric mixes",
    )
    arguments = parser.parse_args()

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )

    results: dict[str, tuple[int, int]] = {}
    for shape in arguments.shapes:
        results[shape] = _ceiling(service, shape, arguments.low, arguments.precision)

    print(f"\n{'shape':>13} {'largest rendered':>18} {'smallest failure':>18}")
    for shape, (rendered, failed) in results.items():
        print(f"{shape:>13} {rendered:>18,} {failed:>18,}")

    ceilings = {shape: rendered for shape, (rendered, _) in results.items()}
    if len(set(ceilings.values())) > 1:
        lowest = min(ceilings, key=lambda key: ceilings[key])
        print(
            f"\nThe ceiling is not one number: {lowest} breaks first, at "
            f"{ceilings[lowest]:,} rows. A limit set from any other shape admits a "
            "document that cannot render."
        )

    if arguments.verify_model:
        _verify_model(service)

    print(
        f"\nThe render package contract admits {MAX_ITEMS:,} items per list, and this "
        "constraint does not live in any one list: the shapes differ by 2.6x and their "
        "costs add. Set the limit on the document, with margin, and enforce it at "
        "admission so an impossible document is refused rather than attempted (#168)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
