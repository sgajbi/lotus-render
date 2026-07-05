from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app.contracts.examples import load_portfolio_review_render_package_example  # noqa: E402
from app.main import app  # noqa: E402

OperationKey = tuple[str, str]

EXPECTED_RESPONSE_CODES: dict[OperationKey, set[str]] = {
    ("GET", "/health"): {"200"},
    ("GET", "/health/live"): {"200"},
    ("GET", "/health/ready"): {"200", "503"},
    ("GET", "/metadata"): {"200"},
    ("GET", "/metrics"): {"200"},
    ("POST", "/renders"): {"201", "409", "422", "429", "502"},
    ("GET", "/renders/{render_job_id}"): {"200", "404", "422"},
    ("GET", "/renders/{render_job_id}/diagnostics"): {"200", "404", "422"},
    ("GET", "/renders/{render_job_id}/artifact-metadata"): {"200", "404", "409", "422"},
}

POST_RENDERS_REQUIRED_DESCRIPTION_TERMS = (
    "X-Correlation-Id",
    "idempotent",
    "platform ingress",
)


class OpenApiQualityError(RuntimeError):
    pass


def validate_openapi_spec(spec: dict[str, Any]) -> None:
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise OpenApiQualityError("OpenAPI gate failed: no paths defined")

    discovered_operations: set[OperationKey] = set()
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            raise OpenApiQualityError(f"OpenAPI gate failed: {path} has invalid methods")
        for method, operation in methods.items():
            if method.startswith("x-"):
                continue
            method_upper = method.upper()
            key = (method_upper, path)
            discovered_operations.add(key)
            _validate_operation_metadata(key, operation)
            _validate_expected_responses(key, operation)

    missing = sorted(set(EXPECTED_RESPONSE_CODES) - discovered_operations)
    if missing:
        formatted = ", ".join(f"{method} {path}" for method, path in missing)
        raise OpenApiQualityError(
            f"OpenAPI gate failed: missing expected operation(s): {formatted}"
        )

    _validate_post_renders_request_example(paths)


def _validate_operation_metadata(key: OperationKey, operation: Any) -> None:
    if not isinstance(operation, dict):
        raise OpenApiQualityError(f"OpenAPI gate failed: {key[0]} {key[1]} is invalid")
    for field in ("operationId", "summary", "description"):
        if not operation.get(field):
            raise OpenApiQualityError(f"OpenAPI gate failed: {key[0]} {key[1]} missing {field}")
    if key[1] != "/metrics" and not operation.get("tags"):
        raise OpenApiQualityError(f"OpenAPI gate failed: {key[0]} {key[1]} missing tags")

    if key == ("POST", "/renders"):
        description = str(operation.get("description", ""))
        missing_terms = [
            term for term in POST_RENDERS_REQUIRED_DESCRIPTION_TERMS if term not in description
        ]
        if missing_terms:
            joined = ", ".join(missing_terms)
            raise OpenApiQualityError(
                f"OpenAPI gate failed: POST /renders description missing {joined}"
            )


def _validate_expected_responses(key: OperationKey, operation: dict[str, Any]) -> None:
    responses = operation.get("responses")
    if not isinstance(responses, dict) or not responses:
        raise OpenApiQualityError(f"OpenAPI gate failed: {key[0]} {key[1]} missing responses")
    expected = EXPECTED_RESPONSE_CODES.get(key)
    if expected is None:
        return
    missing = sorted(expected - set(responses))
    if missing:
        joined = ", ".join(missing)
        raise OpenApiQualityError(
            f"OpenAPI gate failed: {key[0]} {key[1]} missing response(s): {joined}"
        )
    for status_code in expected:
        response = responses.get(status_code)
        if not isinstance(response, dict):
            raise OpenApiQualityError(
                f"OpenAPI gate failed: {key[0]} {key[1]} response {status_code} invalid"
            )
        if not response.get("description"):
            raise OpenApiQualityError(
                f"OpenAPI gate failed: {key[0]} {key[1]} response {status_code} missing description"
            )


def _validate_post_renders_request_example(paths: dict[str, Any]) -> None:
    operation = paths["/renders"]["post"]
    media = operation["requestBody"]["content"]["application/json"]
    canonical = load_portfolio_review_render_package_example()
    if media.get("example") != canonical:
        raise OpenApiQualityError("OpenAPI gate failed: POST /renders example is not canonical")
    examples = media.get("examples", {})
    portfolio_example = examples.get("portfolio_review_render_package", {})
    if portfolio_example.get("value") != canonical:
        raise OpenApiQualityError(
            "OpenAPI gate failed: POST /renders named example is not canonical"
        )


def main() -> None:
    validate_openapi_spec(app.openapi())
    print("OpenAPI gate passed")


if __name__ == "__main__":
    try:
        main()
    except OpenApiQualityError as exc:
        raise SystemExit(str(exc)) from exc
