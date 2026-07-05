from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.contracts.renders import (
    API_ERROR_RESPONSE_EXAMPLES,
    RENDER_SUBMIT_REQUEST_EXAMPLE,
    ApiErrorResponse,
    RenderArtifactMetadataResponse,
    RenderJobDiagnosticsResponse,
    RenderJobStatusResponse,
    RenderSubmitRequest,
    RenderSubmitResponse,
)
from app.dependencies.container import ContainerDependency, RenderSubmissionDependency
from app.infrastructure.render_store import RenderJobConflictError, RenderJobNotFoundError
from app.services.render_submission import (
    RenderExecutionFailedError,
    RenderPackageInvalidError,
)

router = APIRouter(prefix="/renders", tags=["Renders"])


def _error_response(
    status_code: int,
    *,
    example_key: str,
    description: str,
) -> dict[int | str, dict[str, Any]]:
    return {
        status_code: {
            "model": ApiErrorResponse,
            "description": description,
            "content": {
                "application/json": {
                    "example": API_ERROR_RESPONSE_EXAMPLES[example_key],
                }
            },
        }
    }


@router.post(
    "",
    response_model=RenderSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit governed render package",
    description=(
        "Accepts a complete governed render package and executes the first-wave synchronous render "
        "path. Use this internal endpoint when lotus-report has already assembled immutable report "
        "data and needs lotus-render to validate the template, execute the render, and return "
        "support-safe diagnostics plus inline artifact bytes. Submissions are idempotent for the "
        "same render job identifier and package hash. Request correlation uses X-Correlation-Id, "
        "X-Trace-Id, and traceparent headers when supplied. Authentication and authorization are "
        "enforced by governed platform ingress and service-to-service policy before this internal "
        "API is reached."
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": RENDER_SUBMIT_REQUEST_EXAMPLE,
                    "examples": {
                        "portfolio_review_render_package": {
                            "summary": "Portfolio review render package",
                            "value": RENDER_SUBMIT_REQUEST_EXAMPLE,
                        }
                    },
                }
            }
        }
    },
    responses={
        **_error_response(
            status.HTTP_409_CONFLICT,
            example_key="render_job_conflict",
            description=(
                "Returned when the render job identifier is reused with a different package."
            ),
        ),
        **_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            example_key="render_package_invalid",
            description="Returned when governed package or template validation fails.",
        ),
        **_error_response(
            status.HTTP_502_BAD_GATEWAY,
            example_key="render_failed",
            description="Returned when governed render execution fails after package acceptance.",
        ),
    },
)
async def submit_render(
    request_payload: RenderSubmitRequest,
    response: Response,
    service: RenderSubmissionDependency,
) -> RenderSubmitResponse:
    try:
        result = service.submit(request_payload)
    except RenderJobConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_job_conflict"]["detail"],
        ) from exc
    except RenderPackageInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                **API_ERROR_RESPONSE_EXAMPLES["render_package_invalid"]["detail"],
                "message": str(exc),
            },
        ) from exc
    except RenderExecutionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                **API_ERROR_RESPONSE_EXAMPLES["render_failed"]["detail"],
                "message": str(exc),
            },
        ) from exc

    if result.artifact_base64 is None:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/{render_job_id}",
    response_model=RenderJobStatusResponse,
    summary="Get render job status",
    description=(
        "Returns the current support-safe render job posture, including template identity, "
        "render outcome, and artifact hash metadata when available."
    ),
    responses={
        **_error_response(
            status.HTTP_404_NOT_FOUND,
            example_key="render_job_not_found",
            description="Returned when the requested render job identifier does not exist.",
        )
    },
)
async def get_render_status(
    render_job_id: str,
    service: RenderSubmissionDependency,
) -> RenderJobStatusResponse:
    try:
        return service.get_status(render_job_id)
    except RenderJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_job_not_found"]["detail"],
        ) from exc


@router.get(
    "/{render_job_id}/diagnostics",
    response_model=RenderJobDiagnosticsResponse,
    summary="Diagnose render job recovery posture",
    description=(
        "Returns support-safe operator diagnostics for a persisted render job, including bounded "
        "stale posture, retryability, recovery action, and handoff owner. This endpoint never "
        "returns raw render packages, raw engine stderr, artifact storage locations, archive "
        "retention truth, or upstream replay commands."
    ),
    responses={
        **_error_response(
            status.HTTP_404_NOT_FOUND,
            example_key="render_job_not_found",
            description="Returned when the requested render job identifier does not exist.",
        )
    },
)
async def get_render_diagnostics(
    render_job_id: str,
    container: ContainerDependency,
) -> RenderJobDiagnosticsResponse:
    try:
        return container.render_submission_service.get_diagnostics(
            render_job_id,
            accepted_stale_seconds=container.settings.stale_accepted_seconds,
            rendering_stale_seconds=container.settings.stale_rendering_seconds,
        )
    except RenderJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_job_not_found"]["detail"],
        ) from exc


@router.get(
    "/{render_job_id}/artifact-metadata",
    response_model=RenderArtifactMetadataResponse,
    summary="Get render artifact metadata",
    description=(
        "Returns support-safe artifact metadata for a successful render job. Use this endpoint "
        "when the caller needs artifact hash, determinism posture, size, and MIME metadata "
        "without retrieving archive or distribution semantics."
    ),
    responses={
        **_error_response(
            status.HTTP_404_NOT_FOUND,
            example_key="render_job_not_found",
            description="Returned when the requested render job identifier does not exist.",
        ),
        **_error_response(
            status.HTTP_409_CONFLICT,
            example_key="render_artifact_not_ready",
            description="Returned when rendering has not produced successful artifact metadata.",
        ),
    },
)
async def get_render_artifact_metadata(
    render_job_id: str,
    service: RenderSubmissionDependency,
) -> RenderArtifactMetadataResponse:
    try:
        return service.get_artifact_metadata(render_job_id)
    except RenderJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_job_not_found"]["detail"],
        ) from exc
    except ValueError as exc:
        if str(exc) != "render_artifact_not_ready":
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_artifact_not_ready"]["detail"],
        ) from exc
