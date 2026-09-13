from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from starlette.concurrency import run_in_threadpool

from app.contracts.render_evidence import (
    RenderArtifactMetadataResponse,
    RenderJobDiagnosticsResponse,
)
from app.contracts.renders import (
    API_ERROR_RESPONSE_EXAMPLES,
    RENDER_SUBMIT_REQUEST_EXAMPLE,
    ApiErrorResponse,
    RenderJobStatusResponse,
    RenderSubmitRequest,
    RenderSubmitResponse,
)
from app.dependencies.admitted_tenant import AdmittedTenantDependency
from app.dependencies.container import ContainerDependency, RenderSubmissionDependency
from app.infrastructure.render_store import RenderJobConflictError, RenderJobNotFoundError
from app.observability.render_metrics import record_render_operation
from app.services.render_submission import (
    RenderCapacityExhaustedError,
    RenderExecutionFailedError,
    RenderPackageInvalidError,
)

router = APIRouter(prefix="/renders", tags=["Renders"])


def _custody_tenant(request_payload: RenderSubmitRequest) -> str | None:
    """The tenant the package's custody block names, or None when it names none.

    A claim about the document, checked against the admitted tenant and never used in
    its place: the body cannot grant authority the transport did not.
    """
    custody = request_payload.render_context.get("archive")
    if not isinstance(custody, dict):
        return None
    tenant = custody.get("tenant_id")
    if not isinstance(tenant, str) or not tenant.strip():
        return None
    return tenant.strip()


def _refuse_tenant_contradiction(
    request_payload: RenderSubmitRequest, admitted_tenant: str
) -> None:
    """Refuse a package whose custody block names a tenant other than the admitted one.

    The admitted tenant is transport truth; the custody block is a claim about the
    document. When both are present they must agree, and a contradiction is refused
    here -- before the job is created, claimed, compiled or handed to Archive -- because
    nothing downstream can decide which of the two to believe. The transport tenant
    is required; the custody claim may be absent.
    """
    custody_tenant = _custody_tenant(request_payload)
    if custody_tenant is None or custody_tenant == admitted_tenant:
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=API_ERROR_RESPONSE_EXAMPLES["tenant_scope_contradiction"]["detail"],
    )


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


TENANT_AUTH_RESPONSES = _error_response(
    status.HTTP_401_UNAUTHORIZED,
    example_key="missing_tenant_authority",
    description="Returned when X-Tenant-Id is absent; refused before any render or custody effect.",
)

INVALID_TENANT_RESPONSE = _error_response(
    status.HTTP_400_BAD_REQUEST,
    example_key="invalid_tenant_authority",
    description=(
        "Returned when X-Tenant-Id is malformed; refused before any render or custody effect."
    ),
)


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
        **TENANT_AUTH_RESPONSES,
        # The idempotent-replay branch: the job already reached a terminal state, so the
        # render is not repeated and no artifact bytes are returned. The wiki calls this
        # the caller's first trap - "a client that assumes artifact_base64 is always
        # present will break on its first retry" - and it was missing from the machine
        # readable contract consumers generate clients from (issue #126).
        status.HTTP_200_OK: {
            "model": RenderSubmitResponse,
            "description": (
                "The render job already existed in a terminal state; the stored outcome is "
                "returned and artifact_base64 is null."
            ),
        },
        **_error_response(
            status.HTTP_400_BAD_REQUEST,
            example_key="invalid_content_length",
            description="Returned when Content-Length or X-Tenant-Id is malformed.",
        ),
        **_error_response(
            status.HTTP_413_CONTENT_TOO_LARGE,
            example_key="request_body_too_large",
            description=(
                "Returned when the declared or measured request body exceeds the configured limit."
            ),
        ),
        **_error_response(
            status.HTTP_409_CONFLICT,
            example_key="render_job_conflict",
            description=(
                "Returned when the render job identifier is reused with a different package, "
                "or already belongs to a different admitted tenant."
            ),
        ),
        **_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            example_key="render_package_invalid",
            description=(
                "Returned when governed package or template validation fails, or (code "
                "tenant_scope_contradiction) when the admitted X-Tenant-Id contradicts the "
                "package's custody tenant; refused before any render or archive effect."
            ),
        ),
        **_error_response(
            status.HTTP_502_BAD_GATEWAY,
            example_key="render_failed",
            description="Returned when governed render execution fails after package acceptance.",
        ),
        **_error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            example_key="render_execution_capacity_exhausted",
            description="Returned when bounded render execution capacity is exhausted.",
        ),
    },
)
async def submit_render(
    request_payload: RenderSubmitRequest,
    response: Response,
    container: ContainerDependency,
    service: RenderSubmissionDependency,
    admitted_tenant: AdmittedTenantDependency,
) -> RenderSubmitResponse:
    _refuse_tenant_contradiction(request_payload, admitted_tenant)
    try:
        result = await run_in_threadpool(
            service.submit, request_payload, admitted_tenant=admitted_tenant
        )
    except RenderCapacityExhaustedError as exc:
        # The slot is taken inside the service, around work that actually renders, so a
        # replay or an already-terminal job can no longer exhaust capacity (issue #115).
        record_render_operation(
            operation="render_submission",
            status="rejected",
            failure_category="render_execution_capacity_exhausted",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=API_ERROR_RESPONSE_EXAMPLES["render_execution_capacity_exhausted"]["detail"],
        ) from exc
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
        **TENANT_AUTH_RESPONSES,
        **INVALID_TENANT_RESPONSE,
        **_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            example_key="render_package_invalid",
            description=(
                "Returned if the path identifier fails validation. FastAPI documents this "
                "for any operation with a path parameter; this service always answers with "
                "the governed error object rather than the framework's default array shape."
            ),
        ),
        **_error_response(
            status.HTTP_404_NOT_FOUND,
            example_key="render_job_not_found",
            description="Returned when the requested render job identifier does not exist.",
        ),
    },
)
async def get_render_status(
    render_job_id: str,
    service: RenderSubmissionDependency,
    admitted_tenant: AdmittedTenantDependency,
) -> RenderJobStatusResponse:
    try:
        return service.get_status(render_job_id, admitted_tenant=admitted_tenant)
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
        **TENANT_AUTH_RESPONSES,
        **INVALID_TENANT_RESPONSE,
        **_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            example_key="render_package_invalid",
            description=(
                "Returned if the path identifier fails validation. FastAPI documents this "
                "for any operation with a path parameter; this service always answers with "
                "the governed error object rather than the framework's default array shape."
            ),
        ),
        **_error_response(
            status.HTTP_404_NOT_FOUND,
            example_key="render_job_not_found",
            description="Returned when the requested render job identifier does not exist.",
        ),
    },
)
async def get_render_diagnostics(
    render_job_id: str,
    container: ContainerDependency,
    admitted_tenant: AdmittedTenantDependency,
) -> RenderJobDiagnosticsResponse:
    try:
        return container.render_submission_service.get_diagnostics(
            render_job_id,
            accepted_stale_seconds=container.settings.stale_accepted_seconds,
            rendering_stale_seconds=container.settings.stale_rendering_seconds,
            admitted_tenant=admitted_tenant,
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
        **TENANT_AUTH_RESPONSES,
        **INVALID_TENANT_RESPONSE,
        **_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            example_key="render_package_invalid",
            description=(
                "Returned if the path identifier fails validation. FastAPI documents this "
                "for any operation with a path parameter; this service always answers with "
                "the governed error object rather than the framework's default array shape."
            ),
        ),
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
    admitted_tenant: AdmittedTenantDependency,
) -> RenderArtifactMetadataResponse:
    try:
        return service.get_artifact_metadata(render_job_id, admitted_tenant=admitted_tenant)
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
