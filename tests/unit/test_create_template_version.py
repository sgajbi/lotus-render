"""The #216 next-version affordance: mechanical scaffold, explicit governance.

The script copies a family version forward without touching the source version,
carries compatibility and the shared-design pin, returns publication to
development with the publication facts cleared, records the fresh approval facts
the caller supplies, computes the new digest over the actual dependency graph --
and deliberately does NOT publish, does NOT change Report's ordering, and does
NOT carry golden pointers (a new version earns its own evidence).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.templates.digest import template_digest
from app.domain.templates.registry import shared_design_directory
from scripts.create_template_version import create_template_version


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "typst"
    registry_root = tmp_path / "registry"
    (source_root / "_shared" / "v1").mkdir(parents=True)
    (source_root / "_shared" / "v1" / "_design.typ").write_text(
        '#let shared-marker = "S1"\n', encoding="utf-8"
    )
    (source_root / "fam" / "v1").mkdir(parents=True)
    (source_root / "fam" / "v1" / "main.typ").write_text("#lorem(3)\n", encoding="utf-8")
    manifest = {
        "template_id": "fam",
        "template_version": "v1",
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
        "publication": "published",
        "published_at": "2026-09-02",
        "published_by": "lotus-platform-governance",
        "golden_sample_ids": ["golden-fam-v1"],
        "shared_design_version": "v1",
        "template_digest": template_digest(
            source_root / "fam" / "v1",
            shared_directory=shared_design_directory("v1", source_root),
        ),
        "runtime_engine": "typst",
        "runtime_engine_version": "0.14.2",
    }
    (registry_root / "fam").mkdir(parents=True)
    (registry_root / "fam" / "v1.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline=""
    )
    return registry_root, source_root


def test_the_scaffold_carries_the_pin_and_resets_the_governance_facts(
    tmp_path: Path,
) -> None:
    registry_root, source_root = _tree(tmp_path)
    source_manifest_before = (registry_root / "fam" / "v1.manifest.json").read_bytes()
    source_template_before = (source_root / "fam" / "v1" / "main.typ").read_bytes()

    created = create_template_version(
        template_id="fam",
        source_version="v1",
        new_version="v2",
        approved_at="2026-09-10",
        approver="lotus-platform-governance",
        registry_root=registry_root,
        source_root=source_root,
    )

    scaffold = json.loads(created.read_text(encoding="utf-8"))
    assert scaffold["template_version"] == "v2"
    assert scaffold["publication"] == "development"
    assert "published_at" not in scaffold and "published_by" not in scaffold
    assert scaffold["approved_at"] == "2026-09-10"
    assert scaffold["shared_design_version"] == "v1", "the dependency pin carries forward"
    assert scaffold["golden_sample_ids"] == [], "goldens are per-version evidence, not inherited"
    assert scaffold["supported_report_types"] == ["portfolio_review"]
    assert scaffold["template_digest"] == template_digest(
        source_root / "fam" / "v2",
        shared_directory=shared_design_directory("v1", source_root),
    )
    assert (source_root / "fam" / "v2" / "main.typ").read_bytes() == source_template_before
    assert (registry_root / "fam" / "v1.manifest.json").read_bytes() == source_manifest_before, (
        "the source version is never modified"
    )


def test_the_scaffold_refuses_to_overwrite_anything(tmp_path: Path) -> None:
    registry_root, source_root = _tree(tmp_path)

    with pytest.raises(SystemExit, match="no manifest"):
        create_template_version(
            template_id="fam",
            source_version="v9",
            new_version="v10",
            approved_at="2026-09-10",
            approver="lotus-platform-governance",
            registry_root=registry_root,
            source_root=source_root,
        )
    with pytest.raises(SystemExit, match="already exists"):
        create_template_version(
            template_id="fam",
            source_version="v1",
            new_version="v1",
            approved_at="2026-09-10",
            approver="lotus-platform-governance",
            registry_root=registry_root,
            source_root=source_root,
        )
