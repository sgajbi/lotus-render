from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.main import app
from scripts.openapi_quality_gate import OpenApiQualityError, validate_openapi_spec


def test_openapi_quality_gate_accepts_generated_spec() -> None:
    validate_openapi_spec(app.openapi())


def test_openapi_quality_gate_rejects_missing_operation_id() -> None:
    spec = deepcopy(app.openapi())
    del spec["paths"]["/renders"]["post"]["operationId"]

    with pytest.raises(OpenApiQualityError, match="missing operationId"):
        validate_openapi_spec(spec)


def test_openapi_quality_gate_rejects_noncanonical_render_example() -> None:
    spec = deepcopy(app.openapi())
    spec["paths"]["/renders"]["post"]["requestBody"]["content"]["application/json"]["example"][
        "render_job_id"
    ] = "rdr_drifted"

    with pytest.raises(OpenApiQualityError, match="example is not canonical"):
        validate_openapi_spec(spec)


def _spec() -> dict[str, Any]:
    """A mutable copy of the published spec, so a mutation cannot leak between tests."""

    spec: dict[str, Any] = deepcopy(app.openapi())
    return spec


def test_the_gate_rejects_a_deleted_response() -> None:
    """A subset check cannot see a response that vanished from the contract.

    The 400 and 413 the boundary middleware actually returns could be deleted and the
    gate stayed green, which is how documented-but-removed drift accumulates (issue #126).
    """

    spec = _spec()
    for code in ("400", "413"):
        spec["paths"]["/renders"]["post"]["responses"].pop(code)

    with pytest.raises(OpenApiQualityError, match="missing response"):
        validate_openapi_spec(spec)


def test_the_gate_rejects_a_deleted_replay_branch() -> None:
    """POST /renders returns 200 on idempotent replay; consumers generate clients from this."""

    spec = _spec()
    spec["paths"]["/renders"]["post"]["responses"].pop("200")

    with pytest.raises(OpenApiQualityError, match="missing response"):
        validate_openapi_spec(spec)


def test_the_gate_rejects_an_undocumented_operation() -> None:
    """The wiki claims nine operations and no undocumented tenth; now that is enforced."""

    spec = _spec()
    spec["paths"]["/renders/{render_job_id}/raw-package"] = {
        "get": {
            "operationId": "readRawPackage",
            "summary": "Read the raw package",
            "description": "An operation nobody declared.",
            "tags": ["renders"],
            "responses": {"200": {"description": "ok"}},
        }
    }

    with pytest.raises(OpenApiQualityError, match="not declared"):
        validate_openapi_spec(spec)


def test_the_gate_rejects_an_undeclared_response() -> None:
    spec = _spec()
    spec["paths"]["/renders"]["post"]["responses"]["418"] = {"description": "teapot"}

    with pytest.raises(OpenApiQualityError, match="does not declare"):
        validate_openapi_spec(spec)


def test_every_error_response_uses_the_governed_error_schema() -> None:
    """An error the service can return must be documented in the shape it actually returns.

    The three GET operations documented their 422 as FastAPI's `HTTPValidationError`
    (`detail: [{loc, msg, type}]`), while this service's handler always answers with the
    governed error object. A consumer generating a client from the spec would have parsed
    the wrong shape (issue #126).
    """

    spec = _spec()
    wrong: list[str] = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            for code, response in operation.get("responses", {}).items():
                if not code.startswith(("4", "5")):
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                if not schema:
                    continue
                if schema.get("$ref") != "#/components/schemas/ApiErrorResponse":
                    wrong.append(f"{method.upper()} {path} {code} -> {schema}")

    assert not wrong, (
        f"these error responses are documented in a shape the service does not return: {wrong}"
    )
