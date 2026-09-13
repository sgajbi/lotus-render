"""The tenant a request is admitted under, read from transport, never from the body.

Render is a receiver on the Report -> Render leg of the admitted-tenant contract
(lotus-report#375, Cycle 6 C6-REN-02). The tenant that owns a render job is whatever
the trusted caller asserts in ``X-Tenant-Id``; the package's ``render_context.archive``
custody block is a claim about the document and may only agree with it. Step (a) of
the rollout admits the header when present and admits its absence -- the producer has
not started sending it -- so a missing header yields ``None``, not a refusal. Refusing
absence is step (c), after the producer threads the header as a required argument.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

TENANT_HEADER = "X-Tenant-Id"


def get_admitted_tenant(
    x_tenant_id: Annotated[
        str | None,
        Header(
            alias=TENANT_HEADER,
            description=(
                "Tenant the caller is admitted for. Binds the job at submission and scopes "
                "every read; a job owned by another tenant is indistinguishable from one that "
                "does not exist. Optional until the producer sends it on every call."
            ),
        ),
    ] = None,
) -> str | None:
    """The admitted tenant, or None when the caller sent none.

    Whitespace-only is the same as absent: a blank tenant is not a tenant, and
    admitting it would create jobs owned by an empty string.
    """
    if x_tenant_id is None:
        return None
    admitted = x_tenant_id.strip()
    return admitted or None


AdmittedTenantDependency = Annotated[str | None, Depends(get_admitted_tenant)]
