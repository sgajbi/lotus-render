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

        if render_package.report_type not in manifest.supported_report_types:
            raise TemplateCompatibilityError(
                reason="report_type_not_supported",
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not support "
                    f"report type {render_package.report_type}"
                ),
            )

        if (
            render_package.report_data_contract_version
            not in manifest.supported_report_data_contract_versions
        ):
            raise TemplateCompatibilityError(
                reason="report_data_contract_version_not_supported",
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not support "
                    f"report-data contract {render_package.report_data_contract_version}"
                ),
            )

        if render_package.locale not in manifest.supported_locales:
            raise TemplateCompatibilityError(
                reason="locale_not_supported",
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not support "
                    f"locale {render_package.locale}"
                ),
            )

        if render_package.brand_variant not in manifest.supported_brand_variants:
            raise TemplateCompatibilityError(
                reason="brand_variant_not_supported",
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not support "
                    f"brand variant {render_package.brand_variant}"
                ),
            )

        if render_package.output_format not in manifest.supported_output_formats:
            raise TemplateCompatibilityError(
                reason="output_format_not_supported",
                message=(
                    f"template {manifest.template_id} {manifest.template_version} does not support "
                    f"output format {render_package.output_format}"
                ),
            )

        if manifest.status == TemplateLifecycleStatus.ACTIVE:
            return manifest

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
