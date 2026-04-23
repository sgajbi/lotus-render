from __future__ import annotations

from pathlib import Path

from app.domain.templates.registry import TemplateRegistry


def main() -> int:
    registry_root = Path("templates/registry")
    registry = TemplateRegistry.load_from_directory(registry_root)
    manifest_count = len(registry.export_manifests())
    print(f"Template registry validation passed: {manifest_count} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
