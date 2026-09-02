"""Once a template version is published, its bytes never change.

`v1`'s digest was re-recorded eleven times under `status: active` -- the affordance was
doing its development job, and nothing said whether development was still the truth. The
manifest states it now (#216): `publication` is required, all current versions are
`development`, and the `--write` affordance refuses a published version so the only path
past the digest gate for frozen bytes is the next version.

The trigger for publishing is recorded on the field's docstring: first delivery of an
artifact outside this repository's own test suite, at latest the Archive handoff (#120).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.domain.templates.models import TemplateManifest, TemplatePublication

REGISTRY = Path("templates/registry")


def test_every_manifest_states_its_publication_and_none_is_silently_published() -> None:
    """Explicit rather than defaulted: a manifest cannot be treated as development by
    omission, and nothing is published until the recorded trigger fires."""

    manifests = sorted(REGISTRY.rglob("*.json"))
    assert manifests, "no manifests were inspected; the rule would pass over anything"

    for path in manifests:
        manifest = TemplateManifest.model_validate_json(path.read_text(encoding="utf-8"))
        assert manifest.publication is TemplatePublication.DEVELOPMENT, (
            f"{path.as_posix()} is published; if that is deliberate, this test's "
            "expectation moves in the same change that publishes it"
        )


def test_the_write_affordance_refuses_a_published_version(tmp_path: Path) -> None:
    """The mutation is attempted for real, against a copied registry.

    A published manifest whose template bytes changed must fail `--write` with a message
    naming the next-version path -- asserting on the script's source would be satisfiable
    by a comment.
    """

    registry = tmp_path / "templates" / "registry" / "portfolio-review"
    registry.mkdir(parents=True)
    source_manifest = REGISTRY / "portfolio-review" / "v1.manifest.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    manifest["publication"] = "published"
    manifest["template_digest"] = "sha256:" + "0" * 64  # any frozen digest the bytes miss
    (registry / "v1.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    templates = tmp_path / "templates" / "typst"
    shutil.copytree(Path("templates/typst/portfolio-review"), templates / "portfolio-review")
    shutil.copytree(Path("templates/typst/_shared"), templates / "_shared")
    shutil.copytree(Path("src"), tmp_path / "src")
    shutil.copy(Path("scripts/validate_template_registry.py"), tmp_path / "validate.py")

    completed = subprocess.run(
        [sys.executable, str(tmp_path / "validate.py"), "--write"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "REFUSED" in completed.stdout
    assert "create the next template_version" in completed.stdout
