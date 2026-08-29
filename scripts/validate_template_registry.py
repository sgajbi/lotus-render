"""Validate the template registry, and re-record digests after an intended change.

`load_from_directory` verifies every manifest against the bytes of the template it
describes, so a published template changed without its manifest being updated fails here
rather than being served (issue #139). Before that, this gate loaded manifests and
counted them without ever reading `templates/typst`.

A gate needs an affordance for the legitimate case, or the cheapest way past it becomes
weakening it. `--write` re-records the measured digest, which is an explicit act of
re-approval: the diff shows which template changed, and the reviewer decides whether that
change should have been a new `template_version`.

Usage::

    python scripts/validate_template_registry.py            # verify, change nothing
    python scripts/validate_template_registry.py --write    # re-approve changed templates
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.templates.digest import template_digest  # noqa: E402
from app.domain.templates.registry import (  # noqa: E402
    DEFAULT_TEMPLATE_SOURCE_ROOT,
    TemplateRegistry,
    TemplateRegistryError,
)

REGISTRY_ROOT = Path("templates/registry")


def _rerecord_digests() -> int:
    changed = 0
    for manifest_path in sorted(REGISTRY_ROOT.rglob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        directory = (
            DEFAULT_TEMPLATE_SOURCE_ROOT / manifest["template_id"] / manifest["template_version"]
        )
        measured = template_digest(directory)
        if manifest.get("template_digest") == measured:
            continue
        print(f"re-approved {manifest['template_id']} {manifest['template_version']}")
        print(f"            {manifest.get('template_digest')} -> {measured}")
        manifest["template_digest"] = measured
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        changed += 1
    if not changed:
        print("No template digest changed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="re-record the measured digest for any changed template (an act of re-approval)",
    )
    if parser.parse_args().write:
        return _rerecord_digests()

    try:
        registry = TemplateRegistry.load_from_directory(REGISTRY_ROOT)
    except TemplateRegistryError as exc:
        print(f"Template registry validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Template registry validation passed: {len(registry.export_manifests())} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
