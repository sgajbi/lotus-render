"""The tenant a request is admitted under, read from transport, never from the body.

Render is a receiver on the Report -> Render leg of the admitted-tenant contract
(lotus-report#375, Cycle 6 C6-REN-02). The tenant that owns a render job is whatever
the trusted caller asserts in ``X-Tenant-Id``; the package's ``render_context.archive``
custody block is a claim about the document and may only agree with it. Step (c)
requires the header at every HTTP boundary: absence and an empty value are refused as
missing authority, while malformed values are refused as invalid authority. Legacy
``NULL`` rows remain quarantined; a request header cannot adopt them.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import Depends, Header, HTTPException, Request, status

TENANT_HEADER = "X-Tenant-Id"


def _refuse_tenant_authority(status_code: int, code: str, message: str) -> NoReturn:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _has_duplicate_tenant_headers(request: Request) -> bool:
    # Count raw fields before scalar Header binding can discard duplicates. Header
    # names are case-insensitive; repeated equal values are still ambiguous authority.
    raw_headers: list[tuple[bytes, bytes]] = request.scope["headers"]
    return sum(name.lower() == b"x-tenant-id" for name, _ in raw_headers) > 1


def get_admitted_tenant(
    request: Request,
    x_tenant_id: Annotated[
        str | None,
        Header(
            alias=TENANT_HEADER,
            description=(
                "Tenant the caller is admitted for. Binds the job at submission and scopes "
                "every read; a job owned by another tenant is indistinguishable from one that "
                "does not exist. Required for every render operation."
            ),
        ),
    ] = None,
) -> str:
    """Require one bounded, non-blank transport tenant before route-side I/O."""
    if _has_duplicate_tenant_headers(request):
        _refuse_tenant_authority(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_TENANT_AUTHORITY",
            "X-Tenant-Id must be supplied exactly once.",
        )
    if x_tenant_id is None:
        _refuse_tenant_authority(
            status.HTTP_401_UNAUTHORIZED,
            "MISSING_TENANT_AUTHORITY",
            "X-Tenant-Id is required for tenant-owned render operations.",
        )
    if x_tenant_id == "":
        _refuse_tenant_authority(
            status.HTTP_401_UNAUTHORIZED,
            "MISSING_TENANT_AUTHORITY",
            "X-Tenant-Id is required for tenant-owned render operations.",
        )
    if (
        x_tenant_id != x_tenant_id.strip()
        or len(x_tenant_id) > 128
        or not x_tenant_id.isprintable()
    ):
        _refuse_tenant_authority(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_TENANT_AUTHORITY",
            "X-Tenant-Id must name a non-blank tenant of at most 128 printable characters.",
        )
    return x_tenant_id


AdmittedTenantDependency = Annotated[str, Depends(get_admitted_tenant)]
