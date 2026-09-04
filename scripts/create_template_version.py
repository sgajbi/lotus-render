"""Scaffold the next version of a template family -- the #216 affordance.

A published version's bytes never change; a change creates the next version. This
script is that path made mechanical and nothing more: it copies the source
version's template directory to the new version, carries the manifest's
compatibility facts and shared-design pin forward, returns publication to
development with the publication facts cleared, records the fresh approval facts
the caller must supply, and computes the new version's digest over its actual
dependency graph.

Deliberately NOT done here, because they are governance and product decisions:
publishing the new version, changing which version lotus-report orders, and
re-pointing golden samples (the new version starts with none -- goldens are
per-version evidence and earn their place with the version's first banked
proof).

Usage::

    python scripts/create_template_version.py \\
        --template-id portfolio-review --source-version v2 --new-version v3 \\
        --approved-at 2026-09-10 --approver lotus-platform-governance
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.templates.digest import template_digest  # noqa: E402
from app.domain.templates.registry import (  # noqa: E402
    DEFAULT_TEMPLATE_SOURCE_ROOT,
    shared_design_directory,
)

REGISTRY_ROOT = Path("templates/registry")


def create_template_version(
    *,
    template_id: str,
    source_version: str,
    new_version: str,
    approved_at: str,
    approver: str,
    registry_root: Path = REGISTRY_ROOT,
    source_root: Path = DEFAULT_TEMPLATE_SOURCE_ROOT,
) -> Path:
    source_manifest_path = registry_root / template_id / f"{source_version}.manifest.json"
    if not source_manifest_path.is_file():
        raise SystemExit(f"REFUSED: no manifest at {source_manifest_path}")
    new_manifest_path = registry_root / template_id / f"{new_version}.manifest.json"
    if new_manifest_path.exists():
        raise SystemExit(f"REFUSED: {new_manifest_path} already exists")
    source_directory = source_root / template_id / source_version
    if not source_directory.is_dir():
        raise SystemExit(f"REFUSED: no template source at {source_directory}")
    new_directory = source_root / template_id / new_version
    if new_directory.exists():
        raise SystemExit(f"REFUSED: {new_directory} already exists")

    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    shutil.copytree(source_directory, new_directory)

    manifest["template_version"] = new_version
    manifest["publication"] = "development"
    manifest.pop("published_at", None)
    manifest.pop("published_by", None)
    manifest["approved_at"] = approved_at
    manifest["approver"] = approver
    # Goldens are per-version evidence; the new version earns its own with its
    # first banked proof rather than inheriting pointers into the source's.
    manifest["golden_sample_ids"] = []
    manifest["template_digest"] = template_digest(
        new_directory,
        shared_directory=shared_design_directory(manifest["shared_design_version"], source_root),
    )
    new_manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline=""
    )
    print(
        f"created {template_id} {new_version} from {source_version}: "
        f"development, shared design {manifest['shared_design_version']}, "
        f"digest {manifest['template_digest'][:23]}..."
    )
    print("Not done here, on purpose: publishing, Report's version order, goldens.")
    return new_manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--new-version", required=True)
    parser.add_argument(
        "--approved-at", required=True, help="the actual date of this approval (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--approver", required=True, help="governance identity approving the scaffold"
    )
    arguments = parser.parse_args()
    create_template_version(
        template_id=arguments.template_id,
        source_version=arguments.source_version,
        new_version=arguments.new_version,
        approved_at=arguments.approved_at,
        approver=arguments.approver,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
