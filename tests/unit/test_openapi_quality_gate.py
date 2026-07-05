from __future__ import annotations

from copy import deepcopy

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
