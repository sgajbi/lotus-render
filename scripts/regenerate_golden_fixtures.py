"""Re-render banked golden artefacts and re-bank their determinism fingerprints.

Golden proof is a byte comparison: each fixture's `expected.pdf` is the document the
governed template produced, and `producer-fixtures.v1.json` carries the fingerprint of
that document as a literal, so a weakened fingerprint function cannot quietly agree with
itself (issue #108).

That only stays workable if re-banking is cheap and reviewable. Without a regeneration
path, a legitimate template change tempts whoever makes it to weaken the comparison
instead of restating the proof (issue #118).

Usage::

    python scripts/regenerate_golden_fixtures.py            # report drift, change nothing
    python scripts/regenerate_golden_fixtures.py --write    # re-render and re-bank

`--write` rewrites artefacts and fingerprints; the diff it produces *is* the review
surface, so a change nobody intended shows up as a changed PDF in the pull request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.contracts.render_package import RenderPackage  # noqa: E402
from app.core.settings import Settings  # noqa: E402
from app.domain.templates.registry import TemplateRegistry  # noqa: E402
from app.services.render_intake import RenderIntakeService  # noqa: E402
from app.services.typst_rendering import TypstRenderService  # noqa: E402

FIXTURES_PATH = Path("tests/golden/producer-fixtures.v1.json")


def _build_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite expected.pdf and the banked fingerprints instead of only reporting",
    )
    arguments = parser.parse_args()

    service = _build_service()
    manifest = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    drifted: list[str] = []

    for fixture in manifest["fixtures"]:
        package = RenderPackage.model_validate_json(
            Path(fixture["package_path"]).read_text(encoding="utf-8")
        )
        result = service.render(package)
        fingerprint = result.diagnostic.bounded_determinism_fingerprint
        banked = fixture.get("bounded_determinism_fingerprint")
        sample_id = fixture["golden_sample_id"]

        if fingerprint == banked:
            print(f"unchanged  {sample_id}")
            continue

        drifted.append(sample_id)
        if arguments.write:
            Path(fixture["expected_pdf_path"]).write_bytes(result.artifact_bytes)
            fixture["bounded_determinism_fingerprint"] = fingerprint
            print(f"re-banked  {sample_id}\n           {banked} -> {fingerprint}")
        else:
            print(f"DRIFTED    {sample_id}")
            print(f"           banked={banked}")
            print(f"           actual={fingerprint}")

    if arguments.write:
        FIXTURES_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return 0

    if drifted:
        print(
            f"\n{len(drifted)} golden fixture(s) no longer match their banked proof. If the "
            "change is intended, re-run with --write and review the resulting PDF diff.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
