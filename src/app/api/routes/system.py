from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.contracts.system import HealthResponse, MetadataResponse, RenderSupportabilitySummary
from app.dependencies.container import ContainerDependency
from app.observability.render_metrics import record_render_supportability

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
    )
    record_render_supportability(
        state=supportability["state"],
        reason=supportability["reason"],
        freshness_bucket=supportability["freshnessBucket"],
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
    )
