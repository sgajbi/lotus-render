"""Publication is a recorded governance act that every evidence surface states.

The trigger #216 recorded has fired: the #120 Archive handoff is live-proven, so
portfolio-review v1 is published -- its bytes frozen at the banked digest, the act
recorded as published_at + published_by, and (template_id, template_version) now a
valid semantic identity for external delivery. The posture is captured AT RENDER
TIME and rides every surface a consumer reads: the submit response, the status and
diagnostics surfaces, the artifact metadata, and the Archive custody overlay --
because archived_verified and published-for-client-use are distinct facts and
Report's external-publication gate needs both without ever learning a digest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.models import TemplateManifest
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

MANIFEST = Path("templates/registry/portfolio-review/v1.manifest.json")


def test_the_publication_act_is_recorded_not_implied() -> None:
    """The governance facts live in the manifest itself: date and approver, so the
    rule 'published bytes never change' needs no git archaeology to enforce."""

    manifest = TemplateManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.publication.value == "published"
    assert manifest.published_at == "2026-09-04"
    assert manifest.published_by == "lotus-platform-governance"


def test_a_published_manifest_without_its_facts_is_refused() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload.pop("published_at")
    with pytest.raises(ValueError, match="published_at and published_by"):
        TemplateManifest.model_validate(payload)


def test_a_development_manifest_claiming_publication_facts_is_refused() -> None:
    """A development version carrying published_at claims an approval that never
    happened -- the pair travels with the posture or not at all."""

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["publication"] = "development"
    payload.pop("published_by")
    with pytest.raises(ValueError, match="development version"):
        TemplateManifest.model_validate(payload)


def test_the_real_engine_stamps_the_posture_from_the_manifest() -> None:
    """Not a fake's promise: the actual render reads the actual manifest, so the
    recorded posture is whatever governed THIS render."""

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

    result = service.render(package)

    assert result.diagnostic.template_publication == "published"
