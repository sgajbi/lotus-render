"""XLSX source admission must be as strict as the existing PDF source graph."""

import json
from pathlib import Path

import pytest

from app.domain.templates.digest import template_digest
from app.domain.templates.registry import TemplateRegistry, TemplateRegistryError
from scripts.validate_template_registry import _rerecord_digests


def _registry_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "templates" / "xlsx" / "composite-review" / "v1"
    source.mkdir(parents=True)
    (source / "layout.json").write_text('{"layout_version":"v1"}\n', encoding="utf-8")
    manifest = json.loads(Path("templates/registry/portfolio-review/v1.manifest.json").read_text())
    manifest.update(
        template_id="composite-review",
        runtime_engine="xlsxwriter",
        runtime_engine_version="3.2.9",
        shared_design_version="none",
        template_digest=template_digest(source),
        supported_output_formats=["xlsx"],
        publication="development",
        published_at=None,
        published_by=None,
    )
    registry = tmp_path / "registry"
    registry.mkdir()
    path = registry / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return registry, source, path


def test_xlsx_registry_verifies_its_own_source_without_typst_shared_design(tmp_path: Path) -> None:
    registry, source, _ = _registry_tree(tmp_path)
    loaded = TemplateRegistry.load_from_directory(
        registry, template_source_root=source.parents[2] / "typst"
    )
    assert loaded.registered_manifests()[0].runtime_engine == "xlsxwriter"


def test_xlsx_source_drift_refuses_and_development_reapproval_restores_it(tmp_path: Path) -> None:
    registry, source, _ = _registry_tree(tmp_path)
    typst_root = source.parents[2] / "typst"
    (source / "layout.json").write_text('{"layout_version":"changed"}', encoding="utf-8")
    with pytest.raises(TemplateRegistryError, match="digest mismatch"):
        TemplateRegistry.load_from_directory(registry, template_source_root=typst_root)
    assert _rerecord_digests(registry, typst_root) == 0
    assert TemplateRegistry.load_from_directory(registry, template_source_root=typst_root)


def test_published_xlsx_drift_is_never_reapproved_in_place(tmp_path: Path) -> None:
    registry, source, path = _registry_tree(tmp_path)
    manifest = json.loads(path.read_text())
    manifest.update(publication="published", published_at="2026-10-09", published_by="governance")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = path.read_bytes()
    (source / "layout.json").write_text('{"layout_version":"changed"}', encoding="utf-8")
    assert _rerecord_digests(registry, source.parents[2] / "typst") == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("engine,shared", [("unknown", "none"), ("xlsxwriter", "v1")])
def test_unknown_engine_or_xlsx_shared_graph_refuses(
    tmp_path: Path, engine: str, shared: str
) -> None:
    registry, source, path = _registry_tree(tmp_path)
    manifest = json.loads(path.read_text())
    manifest.update(runtime_engine=engine, shared_design_version=shared)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(TemplateRegistryError, match="unsupported_template_source_engine"):
        TemplateRegistry.load_from_directory(
            registry, template_source_root=source.parents[2] / "typst"
        )
