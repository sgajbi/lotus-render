"""The registry projection for version-aware family supportability, consumer-shaped.

lotus-report resolves the exact (template_id, template_version) its family
definitions intend to order and needs the registry facts per version -- identity,
renderable status, publication posture with its recorded governance facts, and
the supported report types/contract versions and output formats. Other facts are
excluded by the consumer: digests (never consumed), locales/brand variants (a
mismatch is a render-time refusal) and runtime posture (the /metadata surface states it).
Template format capability must never inherit global runtime support or another template's list.
These tests pin the projection to that request:
what it must carry, what it must NOT carry, and that publication facts appear
exactly where a published version exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts.examples import load_portfolio_review_render_package_example
from app.contracts.system import TemplateProjectionEntry
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.main import create_app
from app.services.render_runtime import RenderRuntimeAvailability, RenderRuntimeProbe


def _templates() -> list[dict[str, object]]:
    with TestClient(create_app()) as client:
        response = client.get("/system/templates")
    assert response.status_code == 200
    payload = response.json()
    templates = payload["templates"]
    assert isinstance(templates, list) and templates
    return templates


def test_every_registered_version_appears_ordered_and_versioned() -> None:
    templates = _templates()

    keys = [(entry["template_id"], entry["template_version"]) for entry in templates]
    assert keys == sorted(keys), "deterministic order is part of the contract"
    assert ("portfolio-review", "v1") in keys
    assert ("portfolio-review", "v2") in keys, (
        "both versions of a family are distinct entries -- the consumer resolves exact pairs"
    )


def test_publication_facts_travel_exactly_with_the_published_version() -> None:
    """Both portfolio-review versions are published with their governance facts
    recorded; the projection states the facts, never implies them."""

    by_key = {(entry["template_id"], entry["template_version"]): entry for entry in _templates()}
    v1 = by_key[("portfolio-review", "v1")]
    assert v1["status"] == "active"
    assert v1["template_publication"] == "published"
    assert v1["published_at"] == "2026-09-04"
    assert v1["published_by"] == "lotus-platform-governance"
    assert v1["supported_report_types"] == ["portfolio_review"]
    assert v1["supported_report_data_contract_versions"] == ["portfolio_review.v1"]
    assert v1["supported_output_formats"] == ["pdf"]

    v2 = by_key[("portfolio-review", "v2")]
    assert v2["template_publication"] == "published"
    assert v2["published_at"] == "2026-09-04"
    assert v2["published_by"] == "lotus-platform-governance"


def test_the_excluded_facts_stay_excluded() -> None:
    """Internal digests, locales, brand variants and runtime posture remain excluded."""

    for entry in _templates():
        assert set(entry) == {
            "template_id",
            "template_version",
            "status",
            "template_publication",
            "published_at",
            "published_by",
            "supported_report_types",
            "supported_report_data_contract_versions",
            "supported_output_formats",
        }, f"unexpected projection keys: {sorted(entry)}"


def test_every_version_projects_its_own_registered_formats_without_global_inheritance() -> None:
    manifests = TemplateRegistry.load_from_directory(Path("templates/registry"))
    expected = {
        (manifest.template_id, manifest.template_version): manifest.supported_output_formats
        for manifest in manifests.registered_manifests()
    }
    actual = {
        (entry["template_id"], entry["template_version"]): entry["supported_output_formats"]
        for entry in _templates()
    }
    assert actual == expected
    assert actual[("portfolio-review", "v1")] == ["pdf"]
    assert actual[("composite-review", "v1")] == ["xlsx"]


def _isolated_settings(tmp_path: Path, formats: list[str], status: str = "active") -> Settings:
    manifest = json.loads(Path("templates/registry/portfolio-review/v1.manifest.json").read_text())
    manifest["supported_output_formats"] = formats
    manifest["status"] = status
    directory = tmp_path / "registry"
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return Settings(
        template_registry_path=str(directory), render_store_path=str(tmp_path / "render.sqlite3")
    )


@pytest.mark.parametrize("formats", [["pdf"], ["xlsx"], ["xlsx", "pdf"]])
def test_isolated_version_projects_exact_declared_formats_and_order(
    tmp_path: Path, formats: list[str]
) -> None:
    with TestClient(create_app(_isolated_settings(tmp_path, formats))) as client:
        response = client.get("/system/templates")
    assert response.status_code == 200
    entry = response.json()["templates"][0]
    assert entry["supported_output_formats"] == formats
    assert entry["template_id"] == "portfolio-review" and entry["template_version"] == "v1"
    assert entry["template_publication"] == "published"


@pytest.mark.parametrize("formats", [None, [], "xlsx", [1]])
def test_missing_or_malformed_format_evidence_never_defaults_to_runtime(formats: object) -> None:
    entry = _templates()[0]
    if formats is None:
        entry.pop("supported_output_formats")
    else:
        entry["supported_output_formats"] = formats
    with pytest.raises(ValidationError):
        TemplateProjectionEntry.model_validate(entry)


def test_registry_projection_does_not_admit_an_unimplemented_runtime_format(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path, ["csv"])
    package = load_portfolio_review_render_package_example()
    package["output_format"] = "csv"
    with TestClient(create_app(settings), headers={"X-Tenant-Id": "tenant-a"}) as client:
        projection = client.get("/system/templates").json()["templates"][0]
        assert projection["supported_output_formats"] == ["csv"]
        assert "csv" not in settings.supported_output_formats
        response = client.post("/renders", json=package)
        job = client.get("/renders/" + package["render_job_id"]).json()
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "render_package_invalid"
    assert job["status"] == "failed" and job["failure_category"] == "template_not_supported"
    assert job["artifact_sha256"] is None


def test_pdf_template_still_refuses_xlsx_even_when_runtime_supports_it(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path, ["pdf"])
    package = load_portfolio_review_render_package_example()
    package["output_format"] = "xlsx"
    with TestClient(create_app(settings), headers={"X-Tenant-Id": "tenant-a"}) as client:
        assert "xlsx" in settings.supported_output_formats
        assert client.get("/system/templates").json()["templates"][0][
            "supported_output_formats"
        ] == ["pdf"]
        response = client.post("/renders", json=package)
        job = client.get("/renders/" + package["render_job_id"]).json()
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "render_package_invalid"
    assert job["status"] == "failed" and job["failure_category"] == "template_not_supported"
    assert job["artifact_sha256"] is None


def test_openapi_declares_required_nonempty_formats_with_pdf_xlsx_examples() -> None:
    schema = create_app().openapi()["components"]["schemas"]["TemplateProjectionEntry"]
    assert "supported_output_formats" in schema["required"]
    field = schema["properties"]["supported_output_formats"]
    assert field["minItems"] == 1 and field["items"]["type"] == "string"
    assert field["examples"] == [["pdf"], ["xlsx"], ["pdf", "xlsx"]]


@pytest.mark.parametrize(
    "status", ["deprecated_rerenderable", "blocked_for_new_renders", "blocked"]
)
def test_projected_formats_do_not_override_registry_lifecycle_refusal(
    tmp_path: Path, status: str
) -> None:
    settings = _isolated_settings(tmp_path, ["pdf"], status)
    package = load_portfolio_review_render_package_example()
    with TestClient(create_app(settings), headers={"X-Tenant-Id": "tenant-a"}) as client:
        entry = client.get("/system/templates").json()["templates"][0]
        assert entry["supported_output_formats"] == ["pdf"] and entry["status"] == status
        response = client.post("/renders", json=package)
        job = client.get("/renders/" + package["render_job_id"]).json()
    assert response.status_code == 422
    assert job["status"] == "failed" and job["artifact_sha256"] is None


@pytest.mark.parametrize("field", ["report_type", "report_data_contract_version"])
def test_projected_formats_do_not_override_incompatible_content_contract(
    tmp_path: Path, field: str
) -> None:
    package = load_portfolio_review_render_package_example()
    package[field] = "unsupported"
    with TestClient(
        create_app(_isolated_settings(tmp_path, ["pdf"])), headers={"X-Tenant-Id": "tenant-a"}
    ) as client:
        assert client.get("/system/templates").json()["templates"][0][
            "supported_output_formats"
        ] == ["pdf"]
        response = client.post("/renders", json=package)
        job = client.get("/renders/" + package["render_job_id"]).json()
    assert response.status_code == 422
    assert job["status"] == "failed" and job["artifact_sha256"] is None


def test_projection_keeps_declared_formats_distinct_from_unavailable_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        RenderRuntimeProbe,
        "check_available",
        lambda self: RenderRuntimeAvailability(False, "runtime_configuration_unavailable"),
    )
    with TestClient(create_app(_isolated_settings(tmp_path, ["pdf"]))) as client:
        assert client.get("/system/templates").json()["templates"][0][
            "supported_output_formats"
        ] == ["pdf"]
        metadata = client.get("/metadata").json()
    assert metadata["supportability"]["runtimeAvailable"] is False
    assert metadata["supportability"]["state"] == "unavailable"
