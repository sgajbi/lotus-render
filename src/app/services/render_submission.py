from __future__ import annotations

import base64
import hashlib
import json

from app.contracts.render_package import RenderPackage
from app.contracts.renders import (
    RenderArtifactMetadataResponse,
    RenderFailureCategory,
    RenderJobStatusResponse,
    RenderSubmitResponse,
)
from app.domain.templates.registry import TemplateCompatibilityError
from app.render_store import RenderStore, StoredRenderJob
from app.services.typst_rendering import TypstRenderService


class RenderPackageInvalidError(ValueError):
    pass


class RenderExecutionFailedError(RuntimeError):
    pass


class RenderSubmissionService:
    def __init__(
        self,
        *,
        render_store: RenderStore,
        typst_render_service: TypstRenderService,
    ) -> None:
        self._render_store = render_store
        self._typst_render_service = typst_render_service

    def submit(self, render_package: RenderPackage) -> RenderSubmitResponse:
        package_hash = hashlib.sha256(
            json.dumps(
                render_package.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        existing = self._render_store.create_or_get(
            render_job_id=render_package.render_job_id,
            report_job_id=render_package.report_job_id,
            render_package_version=render_package.render_package_version,
            package_hash=package_hash,
            report_type=render_package.report_type,
            template_id=render_package.template_id,
            template_version=render_package.template_version,
            output_format=render_package.output_format,
            runtime_engine=self._typst_render_service._settings.runtime_engine,
            runtime_engine_version=self._typst_render_service._settings.runtime_engine_version,
        )
        if existing.status == "rendered":
            return self._to_submit_response(existing, artifact_base64=None)
        if existing.status == "failed":
            return self._to_submit_response(existing, artifact_base64=None)

        self._render_store.mark_rendering(render_package.render_job_id)
        try:
            result = self._typst_render_service.render(render_package)
        except TemplateCompatibilityError as exc:
            failure = self._render_store.mark_failed(
                render_job_id=render_package.render_job_id,
                failure_category="template_not_supported",
                failure_message=str(exc),
            )
            raise RenderPackageInvalidError(
                failure.failure_message or "template_not_supported"
            ) from exc
        except ValueError as exc:
            failure = self._render_store.mark_failed(
                render_job_id=render_package.render_job_id,
                failure_category="package_validation_failed",
                failure_message=str(exc),
            )
            raise RenderPackageInvalidError(
                failure.failure_message or "package_validation_failed"
            ) from exc
        except RuntimeError as exc:
            failure_message = str(exc)
            failure_category: RenderFailureCategory = "template_render_failed"
            if "neither docker nor typst is installed" in failure_message.lower():
                failure_category = "engine_unavailable"
            failure = self._render_store.mark_failed(
                render_job_id=render_package.render_job_id,
                failure_category=failure_category,
                failure_message=failure_message,
            )
            raise RenderExecutionFailedError(failure.failure_message or "render_failed") from exc

        stored = self._render_store.mark_rendered(render_package.render_job_id, result)
        return self._to_submit_response(
            stored,
            artifact_base64=base64.b64encode(result.artifact_bytes).decode("ascii"),
        )

    def get_status(self, render_job_id: str) -> RenderJobStatusResponse:
        return self._to_status_response(self._render_store.get(render_job_id))

    def get_artifact_metadata(
        self,
        render_job_id: str,
    ) -> RenderArtifactMetadataResponse:
        stored = self._render_store.get(render_job_id)
        if stored.status != "rendered":
            raise ValueError("render_artifact_not_ready")
        assert stored.artifact_sha256 is not None
        assert stored.bounded_determinism_fingerprint is not None
        assert stored.mime_type is not None
        assert stored.output_size_bytes is not None
        assert stored.render_duration_ms is not None
        assert stored.determinism_mode is not None
        return RenderArtifactMetadataResponse(
            render_job_id=stored.render_job_id,
            status=stored.status,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            determinism_mode=stored.determinism_mode,
        )

    @staticmethod
    def _to_submit_response(
        stored: StoredRenderJob,
        *,
        artifact_base64: str | None,
    ) -> RenderSubmitResponse:
        return RenderSubmitResponse(
            render_job_id=stored.render_job_id,
            report_job_id=stored.report_job_id,
            status=stored.status,
            failure_category=stored.failure_category,
            failure_message=stored.failure_message,
            template_id=stored.template_id,
            template_version=stored.template_version,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            runtime_engine=stored.runtime_engine,
            runtime_engine_version=stored.runtime_engine_version,
            determinism_mode=stored.determinism_mode,
            determinism_statement=stored.determinism_statement,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            completed_at=stored.completed_at,
            artifact_base64=artifact_base64,
        )

    @staticmethod
    def _to_status_response(stored: StoredRenderJob) -> RenderJobStatusResponse:
        return RenderJobStatusResponse(
            render_job_id=stored.render_job_id,
            report_job_id=stored.report_job_id,
            status=stored.status,
            failure_category=stored.failure_category,
            failure_message=stored.failure_message,
            template_id=stored.template_id,
            template_version=stored.template_version,
            output_format=stored.output_format,
            artifact_sha256=stored.artifact_sha256,
            bounded_determinism_fingerprint=stored.bounded_determinism_fingerprint,
            runtime_engine=stored.runtime_engine,
            runtime_engine_version=stored.runtime_engine_version,
            determinism_mode=stored.determinism_mode,
            determinism_statement=stored.determinism_statement,
            mime_type=stored.mime_type,
            output_size_bytes=stored.output_size_bytes,
            render_duration_ms=stored.render_duration_ms,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            completed_at=stored.completed_at,
        )
