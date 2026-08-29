from __future__ import annotations

import json
from pathlib import Path

from app.contracts.render_package import RenderPackage
from app.domain.templates.models import TemplateLifecycleStatus, TemplateManifest


class TemplateRegistryError(RuntimeError):
    pass


class TemplateCompatibilityError(TemplateRegistryError):
    def __init__(self, *, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class TemplateRegistry:
    def __init__(self, manifests: dict[tuple[str, str], TemplateManifest]) -> None:
        self._manifests = manifests

    @classmethod
    def load_from_directory(cls, root: Path) -> "TemplateRegistry":
        manifests: dict[tuple[str, str], TemplateManifest] = {}

        for manifest_path in sorted(root.rglob("*.json")):
            manifest = TemplateManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            key = (manifest.template_id, manifest.template_version)
            if key in manifests:
                raise TemplateRegistryError(
                    "duplicate template manifest detected for "
                    f"{manifest.template_id} {manifest.template_version}"
                )
            manifests[key] = manifest

        if not manifests:
            raise TemplateRegistryError(f"no template manifests found under {root}")

        return cls(manifests)

    def export_manifests(self) -> list[dict[str, object]]:
        return [json.loads(manifest.model_dump_json()) for manifest in self._manifests.values()]

    def resolve_for_new_render(self, render_package: RenderPackage) -> TemplateManifest:
        exact_key = (render_package.template_id, render_package.template_version)
        manifest = self._manifests.get(exact_key)
        if manifest is None:
            if any(template_id == render_package.template_id for template_id, _ in self._manifests):
                raise TemplateCompatibilityError(
                    reason="template_version_not_supported",
                    message=(
                        f"template {render_package.template_id} does not support version "
                        f"{render_package.template_version}"
                    ),
                )
            raise TemplateCompatibilityError(
                reason="template_not_supported",
                message=f"template {render_package.template_id} is not registered",
            )

        _require_supported_dimensions(render_package, manifest)
        _require_renderable_status(manifest)
        return manifest


# One row per render-package dimension a manifest must support:
# (package attribute, manifest attribute, rejection reason, noun used in the message).
_COMPATIBILITY_DIMENSIONS = (
    ("report_type", "supported_report_types", "report_type_not_supported", "report type"),
    (
        "report_data_contract_version",
        "supported_report_data_contract_versions",
        "report_data_contract_version_not_supported",
        "report-data contract",
    ),
    ("locale", "supported_locales", "locale_not_supported", "locale"),
    ("brand_variant", "supported_brand_variants", "brand_variant_not_supported", "brand variant"),
    ("output_format", "supported_output_formats", "output_format_not_supported", "output format"),
)


def _require_supported_dimensions(
    render_package: RenderPackage, manifest: TemplateManifest
) -> None:
    for package_attr, manifest_attr, reason, noun in _COMPATIBILITY_DIMENSIONS:
        requested = getattr(render_package, package_attr)
        if requested not in getattr(manifest, manifest_attr):
            raise TemplateCompatibilityError(
                reason=reason,
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not "
                    f"support {noun} {requested}"
                ),
            )


def _require_renderable_status(manifest: TemplateManifest) -> None:
    if manifest.status == TemplateLifecycleStatus.ACTIVE:
        return
    if manifest.status == TemplateLifecycleStatus.DEPRECATED_RERENDERABLE:
        raise TemplateCompatibilityError(
            reason="template_deprecated_for_new_renders",
            message=(
                f"template {manifest.template_id} {manifest.template_version} is deprecated "
                "and not allowed for new renders"
            ),
        )
    if manifest.status == TemplateLifecycleStatus.BLOCKED_FOR_NEW_RENDERS:
        raise TemplateCompatibilityError(
            reason="template_blocked_for_new_renders",
            message=(
                f"template {manifest.template_id} {manifest.template_version} is blocked "
                "for new renders"
            ),
        )
    raise TemplateCompatibilityError(
        reason="template_blocked",
        message=f"template {manifest.template_id} {manifest.template_version} is blocked",
    )
