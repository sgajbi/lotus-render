"""The registry projection for version-aware family supportability, consumer-shaped.

lotus-report resolves the exact (template_id, template_version) its family
definitions intend to order and needs exactly six facts per version -- identity,
renderable status, publication posture with its recorded governance facts, and
the supported report types/contract versions. Everything else was deliberately
excluded by the consumer: digests (never consumed), locales/brand variants (a
mismatch is a render-time refusal), output formats and runtime posture (the
/metadata surface states those). These tests pin the projection to that request:
what it must carry, what it must NOT carry, and that publication facts appear
exactly where a published version exists.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


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

    v2 = by_key[("portfolio-review", "v2")]
    assert v2["template_publication"] == "published"
    assert v2["published_at"] == "2026-09-04"
    assert v2["published_by"] == "lotus-platform-governance"


def test_the_excluded_facts_stay_excluded() -> None:
    """The consumer said never to send digests, locales, brand variants, output
    formats, or runtime posture through this surface -- absence is the contract."""

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
        }, f"unexpected projection keys: {sorted(entry)}"
