from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.contracts.system import (
    HealthResponse,
    MetadataResponse,
    RenderInFlightJobSummary,
    RenderSupportabilitySummary,
    TemplateProjectionEntry,
    TemplatesProjectionResponse,
)
from app.dependencies.container import ContainerDependency
from app.observability.render_posture import refresh_render_posture_metrics

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check service health",
    description="Returns the current liveness posture for lotus-render.",
)
async def health(container: ContainerDependency) -> HealthResponse:
    service = container.render_foundation
    metadata = service.metadata()
    return HealthResponse(status="ok", service=str(metadata["service"]))


@router.get(
    "/health/live",
    response_model=HealthResponse,
    summary="Check service liveness",
    description="Returns the basic process liveness posture.",
)
async def health_live() -> HealthResponse:
    return HealthResponse(status="live")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Check service readiness",
    description="Returns readiness based on foundation runtime availability and drain posture.",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service is draining or not ready to accept work.",
        }
    },
)
async def health_ready(container: ContainerDependency, response: Response) -> HealthResponse:
    service = container.render_foundation
    render_store_ready = container.render_store_ready()
    status_code, payload = service.readiness_status(
        is_draining=container.is_draining,
        render_store_ready=render_store_ready,
        render_runtime_available=container.render_runtime_available(),
    )
    response.status_code = status_code
    return HealthResponse(**payload)


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    summary="Describe service foundation metadata",
    description=(
        "Returns support-safe foundation metadata, including runtime posture "
        "and render-attempt lifecycle values."
    ),
)
async def metadata(container: ContainerDependency) -> MetadataResponse:
    service = container.render_foundation
    foundation_metadata = service.metadata()
    render_store_ready = container.render_store_ready()
    template_registry_ready = container.template_registry_ready()
    supportability = service.supportability_status(
        is_draining=container.is_draining,
        render_store_ready=render_store_ready,
        template_registry_ready=template_registry_ready,
        render_runtime_available=container.render_runtime_available(),
    )
    # The posture gauges are published by the scrape path (issue #125); refresh them here
    # too so /metadata and /metrics never disagree about the same instant.
    refresh_render_posture_metrics(container)
    in_flight_summaries = container.render_store.in_flight_summaries(
        accepted_stale_seconds=container.settings.stale_accepted_seconds,
        rendering_stale_seconds=container.settings.stale_rendering_seconds,
    )
    render_store_in_flight = []
    for summary in in_flight_summaries:
        render_store_in_flight.append(
            RenderInFlightJobSummary(
                status=summary.status,
                count=summary.count,
                staleCount=summary.stale_count,
                freshCount=summary.count - summary.stale_count,
                oldestAgeSeconds=summary.oldest_age_seconds,
                staleThresholdSeconds=summary.stale_threshold_seconds,
            )
        )
    return MetadataResponse(
        service=foundation_metadata["service"],
        version=foundation_metadata["version"],
        roundingPolicyVersion=foundation_metadata["roundingPolicyVersion"],
        environment=foundation_metadata["environment"],
        runtimeEngine=foundation_metadata["runtimeEngine"],
        runtimeEngineVersion=foundation_metadata["runtimeEngineVersion"],
        defaultOutputFormat=foundation_metadata["defaultOutputFormat"],
        supportedOutputFormats=foundation_metadata["supportedOutputFormats"],
        renderAttemptStatuses=foundation_metadata["renderAttemptStatuses"],
        supportability=RenderSupportabilitySummary(**supportability),
        renderStoreInFlight=render_store_in_flight,
    )


@router.get(
    "/system/templates",
    response_model=TemplatesProjectionResponse,
    summary="List registered template versions",
    description=(
        "The registry projection a producer needs for version-aware family "
        "supportability: which (template_id, template_version) pairs exist, whether "
        "each is renderable (status), and whether its bytes are frozen under recorded "
        "approval (template_publication -- a separate stated fact from rendering "
        "support; custody and distribution authority live elsewhere). Deliberately "
        "narrow: no digests (consumers must never bind to template bytes), no "
        "locales or brand variants (a mismatch is a render-time refusal), no output "
        "formats and no runtime posture (the /metadata surface states those)."
    ),
)
async def system_templates(container: ContainerDependency) -> TemplatesProjectionResponse:
    entries = [
        TemplateProjectionEntry(
            template_id=manifest.template_id,
            template_version=manifest.template_version,
            status=manifest.status.value,
            template_publication=manifest.publication.value,
            published_at=manifest.published_at,
            published_by=manifest.published_by,
            supported_report_types=list(manifest.supported_report_types),
            supported_report_data_contract_versions=list(
                manifest.supported_report_data_contract_versions
            ),
        )
        for manifest in container.template_registry.registered_manifests()
    ]
    return TemplatesProjectionResponse(templates=entries)
