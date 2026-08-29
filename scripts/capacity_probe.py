"""Measure where a render stops fitting in its envelope.

`MAX_PAYLOAD_LIST_ITEMS` admits 10,000 items per list. The compile envelope is 512 MB
per render (`--memory 512m`, and `ulimit -v` on the in-process branch). Nothing connected
those two numbers, so a package can validate, be accepted with 201, hold one of two
render slots, and always fail.

#168 asks which of three fixes to take -- lower the admission ceiling, raise the
envelope, or paginate -- and all three need a number. Measured on 2026-08-29, scaling
positions and transactions together against the golden portfolio review:

    1,000 rows of each   4.4s    5.4 MB   renders
    1,750 rows of each   5.5s    4.7 MB   renders
    2,406 rows of each   6.8s    6.4 MB   renders
    2,475 rows of each   6.8s    6.6 MB   renders
    2,500 rows of each  20.3s       --    killed, exit 137

The cliff is sharp enough to be worth stating plainly: 2,475 rows render comfortably in
under seven seconds, and one percent more rows spends twenty seconds thrashing before the
kernel takes the process. Nothing in the timings warns that the limit is close. That is
what exhausting memory looks like rather than a gradual slowdown, so a ceiling chosen
near 2,475 would sit directly under a wall, and wants real margin rather than a round
number just below the last success.

This is a tool, not a gate. The number moves whenever the templates, the envelope or the
concurrency limit change, and a measurement banked as an assertion would either go stale
or fail on hardware that is merely slower. Re-run it when any of those change::

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
# Rows are added to both the positions and the transactions table, so a reported figure
# is rows *of each*. A real document's ceiling depends on its section mix.
SCALED_SECTIONS = (("positions", "security_id"), ("transactions", "transaction_id"))


def _package_with(rows: int) -> RenderPackage:
    raw = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = raw["report_data"]
    for key, id_field in SCALED_SECTIONS:
        source = report.get(key) or []
        if source:
            report[key] = [
                {
                    **copy.deepcopy(source[index % len(source)]),
                    id_field: f"{id_field[:3].upper()}-{index:06d}",
                }
                for index in range(rows)
            ]
    raw["render_job_id"] = f"rdr_capacity_{rows}"
    return RenderPackage.model_validate(raw)


def _renders(service: TypstRenderService, rows: int) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        result = service.render(_package_with(rows))
    except Exception as exc:  # noqa: BLE001 - the probe reports whatever happens
        return False, time.perf_counter() - started, str(exc).splitlines()[0][:60]
    return True, time.perf_counter() - started, f"{len(result.artifact_bytes) / 1024:.0f} KB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--low", type=int, default=1000, help="rows known to render")
    parser.add_argument("--high", type=int, default=2500, help="rows known to fail")
    parser.add_argument("--precision", type=int, default=125, help="stop when the gap is this")
    arguments = parser.parse_args()

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )

    low, high = arguments.low, arguments.high
    print(f"{'rows':>6} {'outcome':>9} {'seconds':>8}  detail")
    while high - low > arguments.precision:
        middle = (low + high) // 2
        rendered, elapsed, detail = _renders(service, middle)
        print(f"{middle:>6} {'renders' if rendered else 'KILLED':>9} {elapsed:>8.1f}  {detail}")
        low, high = (middle, high) if rendered else (low, middle)

    print(f"\nlargest measured render: {low} rows of each")
    print(f"smallest measured failure: {high} rows of each")
    print(
        f"\nThe render package contract admits {MAX_ITEMS:,} items per list. Set a ceiling "
        "from this measurement with margin, and enforce it at admission so an impossible "
        "document is refused rather than attempted (#168)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
