from pathlib import Path
from time import sleep

from app.contracts.render_package import SUPPORTED_RENDER_PACKAGE_VERSION, RenderPackage
from app.core.settings import Settings
from app.domain.render_attempts.models import RenderAttempt, RenderFailureCategory
from app.domain.templates.models import TemplateLifecycleStatus, TemplateManifest
from app.domain.templates.registry import (
    TemplateCompatibilityError,
    TemplateRegistry,
    TemplateRegistryError,
)
from app.main import SERVICE_NAME
from app.services.render_foundation import RenderFoundationService
from app.services.render_intake import RenderIntakeService


def _build_render_package(**overrides: object) -> RenderPackage:
    payload: dict[str, object] = {
        "render_package_version": SUPPORTED_RENDER_PACKAGE_VERSION,
        "render_job_id": "rdr_123",
        "report_job_id": "rjob_456",
        "snapshot_id": "rsnap_789",
        "report_type": "portfolio_review",
        "report_data_contract_version": "portfolio_review.v1",
        "template_id": "portfolio-review",
        "template_version": "v1",
        "locale": "en-SG",
        "brand_variant": "private_banking",
        "output_format": "pdf",
        "render_context": {"as_of_date": "2026-04-23"},
        "report_data": {"report_id": "portfolio-review:PB_SG_GLOBAL_BAL_001:2026-04-23"},
        "lineage_refs": ["rlineage_1"],
        "disclosure_refs": ["portfolio-review.standard-disclosures.v1"],
        "requested_by": "advisor.sg@example.com",
        "correlation_id": "corr-portfolio-review-1",
        "trace_id": "trace-portfolio-review-1",
    }
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


def _build_manifest(
    *, status: TemplateLifecycleStatus = TemplateLifecycleStatus.ACTIVE
) -> TemplateManifest:
    return TemplateManifest(
        template_id="portfolio-review",
        template_version="v1",
        supported_report_types=["portfolio_review"],
        supported_report_data_contract_versions=["portfolio_review.v1"],
        supported_locales=["en-SG"],
        supported_brand_variants=["private_banking"],
        supported_output_formats=["pdf"],
        required_disclosure_fragments=["portfolio-review.standard-disclosures.v1"],
        owner_team="lotus-reporting",
        approver="lotus-platform-governance",
        approved_at="2026-04-23",
        status=status,
        golden_sample_ids=["golden-portfolio-review-en-SG-private-banking-v1"],
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )


def test_service_name_is_lotus_prefixed() -> None:
    assert SERVICE_NAME.startswith("lotus-")


def test_render_attempt_lifecycle_transitions() -> None:
    attempt = RenderAttempt(
        render_job_id="rdr_123",
        report_job_id="rpt_456",
        attempt_number=1,
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
    )

    assert attempt.status.value == "accepted"
    attempt.mark_validating_package()
    assert attempt.status.value == "validating_package"

    attempt.mark_rendering()
    assert attempt.status.value == "rendering"

    attempt.mark_failed(
        RenderFailureCategory.TEMPLATE_RENDER_FAILED,
        "template render failed",
    )
    assert attempt.status.value == "failed"
    assert attempt.failure_category == RenderFailureCategory.TEMPLATE_RENDER_FAILED

    attempt.mark_rendered("abc123")
    assert attempt.status.value == "rendered"
    assert attempt.artifact_sha256 == "abc123"
    assert attempt.failure_category is None


def test_render_attempt_timestamps_are_per_instance_and_lifecycle_stable() -> None:
    first = RenderAttempt(
        render_job_id="rdr_first",
        report_job_id="rpt_456",
        attempt_number=1,
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
    )
    sleep(0.001)
    second = RenderAttempt(
        render_job_id="rdr_second",
        report_job_id="rpt_456",
        attempt_number=1,
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
    )

    assert second.created_at > first.created_at
    created_at = second.created_at
    second.mark_rendering()
    assert second.created_at == created_at
    assert second.updated_at > created_at


def test_render_foundation_metadata_exposes_supported_statuses() -> None:
    service = RenderFoundationService(Settings())
    metadata = service.metadata()

    assert metadata["runtimeEngine"] == "typst"
    assert metadata["supportedOutputFormats"] == ["pdf"]
    assert metadata["renderAttemptStatuses"] == [
        "accepted",
        "validating_package",
        "rendering",
        "rendered",
        "failed",
    ]


def test_render_foundation_supportability_reports_ready_posture() -> None:
    service = RenderFoundationService(Settings())

    supportability = service.supportability_status(
        is_draining=False,
        render_store_ready=True,
        template_registry_ready=True,
    )

    assert supportability["featureKey"] == "render.observability.render_supportability"
    assert supportability["state"] == "ready"
    assert supportability["reason"] == "render_supportability_ready"
    assert supportability["freshnessBucket"] == "current"
    assert supportability["deterministicOutputSupported"] is True
    assert supportability["renderStoreReady"] is True
    assert supportability["templateRegistryReady"] is True


def test_render_foundation_supportability_reports_source_backed_degradation() -> None:
    service = RenderFoundationService(Settings())

    draining = service.supportability_status(
        is_draining=True,
        render_store_ready=True,
        template_registry_ready=True,
    )
    store_unavailable = service.supportability_status(
        is_draining=False,
        render_store_ready=False,
        template_registry_ready=True,
    )
    registry_unavailable = service.supportability_status(
        is_draining=False,
        render_store_ready=True,
        template_registry_ready=False,
    )

    assert draining["state"] == "degraded"
    assert draining["reason"] == "render_supportability_draining"
    assert store_unavailable["state"] == "unavailable"
    assert store_unavailable["reason"] == "render_store_unavailable"
    assert store_unavailable["freshnessBucket"] == "unknown"
    assert registry_unavailable["state"] == "unavailable"
    assert registry_unavailable["reason"] == "template_registry_unavailable"


def test_render_foundation_reports_not_ready_without_supported_formats() -> None:
    service = RenderFoundationService(Settings(supported_output_formats=()))

    status_code, payload = service.readiness_status(
        is_draining=False,
        render_store_ready=True,
    )

    assert status_code == 503
    assert payload["status"] == "not_ready"


def test_render_package_rejects_blank_identity_fields() -> None:
    try:
        _build_render_package(trace_id="   ")
    except ValueError as exc:
        assert "value must not be blank" in str(exc)
    else:
        raise AssertionError("expected blank trace_id to be rejected")


def test_render_package_requires_non_empty_render_context() -> None:
    try:
        _build_render_package(render_context={})
    except ValueError as exc:
        assert "value must not be empty" in str(exc)
    else:
        raise AssertionError("expected empty render_context to be rejected")


def test_template_registry_loads_repo_manifest() -> None:
    registry = TemplateRegistry.load_from_directory(Path(Settings().template_registry_path))
    manifest = registry.resolve_for_new_render(_build_render_package())

    assert manifest.template_id == "portfolio-review"
    assert manifest.status == TemplateLifecycleStatus.ACTIVE


def test_template_registry_exports_manifest_dicts() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    exported = registry.export_manifests()

    assert exported == [
        {
            "template_id": "portfolio-review",
            "template_version": "v1",
            "supported_report_types": ["portfolio_review"],
            "supported_report_data_contract_versions": ["portfolio_review.v1"],
            "supported_locales": ["en-SG"],
            "supported_brand_variants": ["private_banking"],
            "supported_output_formats": ["pdf"],
            "required_disclosure_fragments": ["portfolio-review.standard-disclosures.v1"],
            "owner_team": "lotus-reporting",
            "approver": "lotus-platform-governance",
            "approved_at": "2026-04-23",
            "status": "active",
            "golden_sample_ids": ["golden-portfolio-review-en-SG-private-banking-v1"],
            "runtime_engine": "typst",
            "runtime_engine_version": "0.14.2",
        }
    ]


def test_template_registry_rejects_empty_registry(tmp_path: Path) -> None:
    try:
        TemplateRegistry.load_from_directory(tmp_path)
    except TemplateRegistryError as exc:
        assert "no template manifests found" in str(exc)
    else:
        raise AssertionError("expected empty registry to be rejected")


def test_template_registry_rejects_duplicate_manifest_keys(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry"
    primary_dir = registry_path / "one"
    secondary_dir = registry_path / "two"
    primary_dir.mkdir(parents=True)
    secondary_dir.mkdir(parents=True)
    manifest_json = _build_manifest().model_dump_json(indent=2)
    (primary_dir / "v1.manifest.json").write_text(manifest_json, encoding="utf-8")
    (secondary_dir / "v1.manifest.json").write_text(manifest_json, encoding="utf-8")

    try:
        TemplateRegistry.load_from_directory(registry_path)
    except TemplateRegistryError as exc:
        assert "duplicate template manifest detected" in str(exc)
    else:
        raise AssertionError("expected duplicate manifests to be rejected")


def test_render_intake_accepts_supported_package() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})
    service = RenderIntakeService(registry)

    manifest = service.validate_package(_build_render_package())

    assert manifest.template_version == "v1"


def test_template_registry_rejects_unknown_template_id() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(template_id="not-registered"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "template_not_supported"
    else:
        raise AssertionError("expected unknown template id to be rejected")


def test_template_registry_rejects_unsupported_template_version() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(template_version="v2"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "template_version_not_supported"
    else:
        raise AssertionError("expected unsupported template version to be rejected")


def test_template_registry_rejects_unsupported_report_type() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(report_type="tax_report"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "report_type_not_supported"
    else:
        raise AssertionError("expected unsupported report type to be rejected")


def test_template_registry_rejects_unsupported_contract_version() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(
            _build_render_package(report_data_contract_version="portfolio_review.v2")
        )
    except TemplateCompatibilityError as exc:
        assert exc.reason == "report_data_contract_version_not_supported"
    else:
        raise AssertionError("expected unsupported contract version to be rejected")


def test_template_registry_rejects_unsupported_locale() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(locale="en-US"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "locale_not_supported"
    else:
        raise AssertionError("expected unsupported locale to be rejected")


def test_template_registry_rejects_unsupported_brand_variant() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(brand_variant="retail"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "brand_variant_not_supported"
    else:
        raise AssertionError("expected unsupported brand variant to be rejected")


def test_template_registry_rejects_unsupported_output_format() -> None:
    registry = TemplateRegistry({("portfolio-review", "v1"): _build_manifest()})

    try:
        registry.resolve_for_new_render(_build_render_package(output_format="docx"))
    except TemplateCompatibilityError as exc:
        assert exc.reason == "output_format_not_supported"
    else:
        raise AssertionError("expected unsupported output format to be rejected")


def test_template_registry_rejects_deprecated_for_new_renders() -> None:
    registry = TemplateRegistry(
        {
            ("portfolio-review", "v1"): _build_manifest(
                status=TemplateLifecycleStatus.DEPRECATED_RERENDERABLE
            )
        }
    )

    try:
        registry.resolve_for_new_render(_build_render_package())
    except TemplateCompatibilityError as exc:
        assert exc.reason == "template_deprecated_for_new_renders"
    else:
        raise AssertionError("expected deprecated template to be rejected for new renders")


def test_template_registry_rejects_blocked_for_new_renders() -> None:
    registry = TemplateRegistry(
        {
            ("portfolio-review", "v1"): _build_manifest(
                status=TemplateLifecycleStatus.BLOCKED_FOR_NEW_RENDERS
            )
        }
    )

    try:
        registry.resolve_for_new_render(_build_render_package())
    except TemplateCompatibilityError as exc:
        assert exc.reason == "template_blocked_for_new_renders"
    else:
        raise AssertionError("expected blocked_for_new_renders template to be rejected")


def test_template_registry_rejects_blocked_templates() -> None:
    registry = TemplateRegistry(
        {("portfolio-review", "v1"): _build_manifest(status=TemplateLifecycleStatus.BLOCKED)}
    )

    try:
        registry.resolve_for_new_render(_build_render_package())
    except TemplateCompatibilityError as exc:
        assert exc.reason == "template_blocked"
    else:
        raise AssertionError("expected blocked template to be rejected")
