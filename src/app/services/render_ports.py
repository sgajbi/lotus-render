from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.render_package import RenderPackage
from app.contracts.renders import RenderFailureCategory
from app.domain.rendering.models import RenderResult
from app.infrastructure.render_store import CreateOrGetRenderJobResult, StoredRenderJob


@dataclass(frozen=True, slots=True)
class RenderRuntimeMetadata:
    runtime_engine: str
    runtime_engine_version: str


class RenderJobStorePort(Protocol):
    def create_or_get_with_outcome(
        self,
        *,
        render_job_id: str,
        report_job_id: str,
        render_package_version: str,
        package_hash: str,
        snapshot_id: str,
        lineage_refs: tuple[str, ...],
        disclosure_refs: tuple[str, ...],
        requested_by: str,
        package_correlation_id: str,
        package_trace_id: str,
        report_type: str,
        template_id: str,
        template_version: str,
        output_format: str,
        runtime_engine: str,
        runtime_engine_version: str,
    ) -> CreateOrGetRenderJobResult: ...

    def mark_rendering(self, render_job_id: str) -> StoredRenderJob: ...

    def mark_rendered(self, render_job_id: str, result: RenderResult) -> StoredRenderJob: ...

    def mark_failed(
        self,
        *,
        render_job_id: str,
        failure_category: RenderFailureCategory,
        failure_message: str,
    ) -> StoredRenderJob: ...

    def get(self, render_job_id: str) -> StoredRenderJob: ...


class RenderEnginePort(Protocol):
    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata: ...

    def render(self, render_package: RenderPackage) -> RenderResult: ...


class RenderEngineTimeoutError(RuntimeError):
    pass
