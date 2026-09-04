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
    shared_design_directory,
)

REGISTRY_ROOT = Path("templates/registry")


def _rerecord_digests(
    registry_root: Path = REGISTRY_ROOT,
    source_root: Path = DEFAULT_TEMPLATE_SOURCE_ROOT,
) -> int:
    """Re-approve changed development digests -- atomically at the file level.

    Two phases, because one shared-design change can affect several manifests: first
    every manifest is measured against ITS OWN pinned shared design and every
    proposed mutation is validated in memory; only if no published version would
    change does anything reach disk. Walk-and-write ordering used to mean an early
    development manifest could be rewritten before a later published dependent
    refused the command, leaving a failed run with partial modifications.
    """
    proposed: list[tuple[Path, dict[str, object], str, str]] = []
    refused: list[str] = []
    for manifest_path in sorted(registry_root.rglob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        directory = source_root / manifest["template_id"] / manifest["template_version"]
        shared = shared_design_directory(manifest["shared_design_version"], source_root)
        measured = template_digest(directory, shared_directory=shared)
        if manifest.get("template_digest") == measured:
            continue
        identity = (
            f"{manifest['template_id']} {manifest['template_version']} "
            f"(shared design {manifest['shared_design_version']})"
        )
        if manifest.get("publication") == "published":
            refused.append(identity)
        else:
            proposed.append((manifest_path, manifest, measured, identity))

    if refused:
        # A published version's bytes are its identity: an archived artifact names
        # this dependency graph forever. Nothing was written -- not even the
        # development manifests measured before the refusal -- because a partial
        # re-approval is a lie about what was approved.
        for identity in refused:
            print(
                f"REFUSED: {identity} is published and its dependency graph changed. "
                "Published bytes never change -- create the next template_version "
                "(scripts/create_template_version.py) and re-point the change at it."
            )
        print("Zero files were written.")
        return 1

    for manifest_path, manifest, measured, identity in proposed:
        print(f"re-approved {identity}")
        print(f"            {manifest.get('template_digest')} -> {measured}")
        manifest["template_digest"] = measured
        # newline="" keeps LF on every platform. The digest this script records is
        # taken over the working-tree bytes, so a CRLF rewrite here would bank a
        # digest that no LF checkout could ever reproduce.
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline=""
        )
    if not proposed:
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
