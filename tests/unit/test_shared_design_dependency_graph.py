"""A published template pins its COMPLETE dependency graph -- proven, not asserted.

Every family compiles against a shared design module, so the artifact a template
produces is determined by (template_id, template_version, shared_design_version),
and portfolio-review v1's publication froze its shared design along with its own
bytes. These tests prove the whole lifecycle over a REAL registry and the REAL
materialisation path -- isolated fixture trees, no mocked resolver:

- a published family pinned to shared v1 loads and materialises;
- a second shared version can exist and EVOLVE without touching any digest
  pinned to shared v1, while a family pinned to shared v2 materialises against
  shared v2's actual bytes;
- mutating a published version's shared dependency is refused with ZERO file
  writes, even when development manifests measured earlier in the same run had
  changes to record;
- a historical family render still materialises against the shared version it
  pinned, however many newer shared versions exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.digest import template_digest
from app.domain.templates.registry import (
    TemplateRegistry,
    TemplateRegistryError,
    shared_design_directory,
)
from app.domain.templates.registry import (
    TemplateRegistry as _Registry,
)
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService
from scripts.validate_template_registry import _rerecord_digests


def _manifest_payload(
    *,
    template_id: str,
    template_version: str,
    shared_design_version: str,
    publication: str,
    digest: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "template_id": template_id,
        "template_version": template_version,
        "supported_report_types": ["portfolio_review"],
        "supported_report_data_contract_versions": ["portfolio_review.v1"],
        "supported_locales": ["en-SG"],
        "supported_brand_variants": ["private_banking"],
        "supported_output_formats": ["pdf"],
        "required_disclosure_fragments": [],
        "owner_team": "lotus-reporting",
        "approver": "lotus-platform-governance",
        "approved_at": "2026-09-01",
        "status": "active",
        "publication": publication,
        "golden_sample_ids": [],
        "shared_design_version": shared_design_version,
        "template_digest": digest,
        "runtime_engine": "typst",
        "runtime_engine_version": "0.14.2",
    }
    if publication == "published":
        payload["published_at"] = "2026-09-01"
        payload["published_by"] = "lotus-platform-governance"
    return payload


def _write_manifest(registry_root: Path, payload: dict[str, Any]) -> None:
    directory = registry_root / payload["template_id"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{payload['template_version']}.manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline=""
    )


def _measured(source_root: Path, template_id: str, version: str, shared: str) -> str:
    return template_digest(
        source_root / template_id / version,
        shared_directory=shared_design_directory(shared, source_root),
    )


@pytest.fixture()
def fixture_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Two shared versions, three family versions, real bytes on disk."""
    source_root = tmp_path / "typst"
    registry_root = tmp_path / "registry"
    (source_root / "_shared" / "v1").mkdir(parents=True)
    (source_root / "_shared" / "v1" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V1"\n', encoding="utf-8"
    )
    (source_root / "_shared" / "v2").mkdir(parents=True)
    (source_root / "_shared" / "v2" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V2"\n', encoding="utf-8"
    )
    for family, version in (("fam", "v1"), ("fam", "v2"), ("famb", "v1")):
        directory = source_root / family / version
        directory.mkdir(parents=True)
        (directory / "main.typ").write_text(
            '#import "_design.typ": shared-marker\n#shared-marker\n', encoding="utf-8"
        )
    _write_manifest(
        registry_root,
        _manifest_payload(
            template_id="fam",
            template_version="v1",
            shared_design_version="v1",
            publication="published",
            digest=_measured(source_root, "fam", "v1", "v1"),
        ),
    )
    _write_manifest(
        registry_root,
        _manifest_payload(
            template_id="fam",
            template_version="v2",
            shared_design_version="v1",
            publication="development",
            digest=_measured(source_root, "fam", "v2", "v1"),
        ),
    )
    _write_manifest(
        registry_root,
        _manifest_payload(
            template_id="famb",
            template_version="v1",
            shared_design_version="v2",
            publication="development",
            digest=_measured(source_root, "famb", "v1", "v2"),
        ),
    )
    return registry_root, source_root


def _load(registry_root: Path, source_root: Path) -> TemplateRegistry:
    return _Registry.load_from_directory(registry_root, template_source_root=source_root)


def _materialise(
    source_root: Path, template_id: str, version: str, shared: str, workspace: Path
) -> str:
    """The REAL materialisation path over the fixture tree, no mocked resolver."""
    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    package = RenderPackage.model_validate(
        json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    )
    source_path = service._materialize_template(
        template_root=source_root / template_id / version / "main.typ",
        workspace=workspace,
        render_package=package,
        template_context={},
        determinism_statement="",
        shared_design_version=shared,
        template_source_root=source_root,
    )
    return (source_path.parent / "_design.typ").read_text(encoding="utf-8")


def test_published_v1_and_dev_v2_load_and_materialise_on_shared_v1(
    fixture_tree: tuple[Path, Path], tmp_path: Path
) -> None:
    registry_root, source_root = fixture_tree

    registry = _load(registry_root, source_root)
    keys = [(m.template_id, m.template_version) for m in registry.registered_manifests()]
    assert keys == [("fam", "v1"), ("fam", "v2"), ("famb", "v1")]

    materialised = _materialise(source_root, "fam", "v1", "v1", tmp_path / "w1")
    assert "SHARED-DESIGN-V1" in materialised


def test_shared_v2_evolves_without_touching_any_shared_v1_digest(
    fixture_tree: tuple[Path, Path],
) -> None:
    registry_root, source_root = fixture_tree
    v1_before = _measured(source_root, "fam", "v1", "v1")
    famb_before = _measured(source_root, "famb", "v1", "v2")

    (source_root / "_shared" / "v2" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V2-EVOLVED"\n', encoding="utf-8"
    )

    assert _measured(source_root, "fam", "v1", "v1") == v1_before, (
        "a shared version the manifest does not pin must be invisible to its digest"
    )
    assert _measured(source_root, "famb", "v1", "v2") != famb_before
    with pytest.raises(TemplateRegistryError, match="famb"):
        _load(registry_root, source_root)


def test_a_family_pinned_to_shared_v2_materialises_against_shared_v2(
    fixture_tree: tuple[Path, Path], tmp_path: Path
) -> None:
    _, source_root = fixture_tree
    materialised = _materialise(source_root, "famb", "v1", "v2", tmp_path / "w2")
    assert "SHARED-DESIGN-V2" in materialised
    assert "SHARED-DESIGN-V1" not in materialised


def test_mutating_shared_v1_changes_the_published_digest_and_load_refuses(
    fixture_tree: tuple[Path, Path],
) -> None:
    registry_root, source_root = fixture_tree
    (source_root / "_shared" / "v1" / "_design.typ").write_text(
        '#let shared-marker = "TAMPERED"\n', encoding="utf-8"
    )
    with pytest.raises(TemplateRegistryError, match="digest mismatch"):
        _load(registry_root, source_root)


def test_reapproval_refuses_with_zero_writes_when_any_published_dependency_changed(
    fixture_tree: tuple[Path, Path],
) -> None:
    """The atomicity proof: shared v1 changed, which touches BOTH the development
    fam/v2 (re-recordable) and the published fam/v1 (refusable). The command must
    refuse and the development manifest on disk must be byte-identical to before
    -- a partial re-approval is a lie about what was approved."""

    registry_root, source_root = fixture_tree
    dev_manifest_path = registry_root / "fam" / "v2.manifest.json"
    dev_before = dev_manifest_path.read_bytes()

    (source_root / "_shared" / "v1" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V1-CHANGED"\n', encoding="utf-8"
    )

    exit_code = _rerecord_digests(registry_root, source_root)

    assert exit_code == 1
    assert dev_manifest_path.read_bytes() == dev_before, (
        "zero files may be written when any published dependency would change"
    )


def test_reapproval_records_development_changes_when_no_published_version_moves(
    fixture_tree: tuple[Path, Path],
) -> None:
    registry_root, source_root = fixture_tree
    (source_root / "_shared" / "v2" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V2-EVOLVED"\n', encoding="utf-8"
    )

    exit_code = _rerecord_digests(registry_root, source_root)

    assert exit_code == 0
    famb = json.loads((registry_root / "famb" / "v1.manifest.json").read_text(encoding="utf-8"))
    assert famb["template_digest"] == _measured(source_root, "famb", "v1", "v2")
    assert _load(registry_root, source_root)


def test_a_published_family_on_shared_v2_freezes_shared_v2_too(
    fixture_tree: tuple[Path, Path],
) -> None:
    registry_root, source_root = fixture_tree
    famb_path = registry_root / "famb" / "v1.manifest.json"
    famb = json.loads(famb_path.read_text(encoding="utf-8"))
    famb["publication"] = "published"
    famb["published_at"] = "2026-09-02"
    famb["published_by"] = "lotus-platform-governance"
    famb_path.write_text(json.dumps(famb, indent=2) + "\n", encoding="utf-8", newline="")

    (source_root / "_shared" / "v2" / "_design.typ").write_text(
        '#let shared-marker = "MUTATED-AFTER-PUBLICATION"\n', encoding="utf-8"
    )

    assert _rerecord_digests(registry_root, source_root) == 1
    with pytest.raises(TemplateRegistryError, match="famb"):
        _load(registry_root, source_root)


def test_a_historical_v1_render_still_uses_shared_v1_after_v2_exists(
    fixture_tree: tuple[Path, Path], tmp_path: Path
) -> None:
    """However many shared versions exist, a family materialises against the one
    its manifest pinned when it was approved -- which is what makes an archived
    document's dependency graph reproducible."""

    _, source_root = fixture_tree
    (source_root / "_shared" / "v2" / "_design.typ").write_text(
        '#let shared-marker = "SHARED-DESIGN-V2-EVOLVED-TWICE"\n', encoding="utf-8"
    )

    materialised = _materialise(source_root, "fam", "v1", "v1", tmp_path / "w3")
    assert "SHARED-DESIGN-V1" in materialised
    assert "V2" not in materialised
