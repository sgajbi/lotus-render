from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.render_package import RenderPackage
from app.contracts.renders import RenderFailureCategory
from app.domain.render_attempts.models import (
    RenderFailureCategory as RuntimeFailureCategory,
)
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

    def claim_for_rendering(
        self,
        render_job_id: str,
        *,
        rendering_stale_seconds: int,
    ) -> StoredRenderJob | None: ...

    def mark_rendered(self, render_job_id: str, result: RenderResult) -> StoredRenderJob: ...

    def record_archive_outcome(
        self,
        render_job_id: str,
        *,
        archive_state: str,
        archive_document_id: str | None,
        archive_request_id: str | None,
        archive_detail: str | None,
    ) -> StoredRenderJob: ...

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


class RenderCompileFailedError(RuntimeError):
    """A compile that failed, carrying why rather than only what it said.

    The runtime classifies its own failures -- a killed process and a rejected
    template arrive differently and mean different things -- and that verdict used to
    end at a local attempt object while the submission surface re-derived a category by
    matching on the message text. Anything the matcher did not recognise became
    `template_render_failed`, which is the answer for a broken template and the wrong
    answer for a document too large to draw.
    """

    def __init__(self, failure_category: RuntimeFailureCategory, summary: str) -> None:
        super().__init__(summary)
        self.failure_category = failure_category


class RenderEngineTimeoutError(RuntimeError):
    pass
