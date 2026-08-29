"""Structural ceilings on the open payload mappings.

``report_data`` is untrusted and attacker-influenced up to the request body cap. Without a
structural bound it is the only thing between the wire and the Typst compiler, and a single
in-cap request expands into a far larger source while holding one of two render slots for the
whole compile timeout (issue #107).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import (
    MAX_PAYLOAD_DEPTH,
    MAX_PAYLOAD_LIST_ITEMS,
    MAX_PAYLOAD_STRING_LENGTH,
    SUPPORTED_RENDER_PACKAGE_VERSION,
    RenderPackage,
)


def _package_payload(**report_data_overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8")
    )
    if report_data_overrides:
        payload["report_data"] = dict(report_data_overrides)
    return payload


def test_render_package_accepts_a_real_report_payload() -> None:
    """The ceilings must be far above any legitimate report; the canonical example proves it."""

    assert RenderPackage.model_validate(_package_payload()).report_data


def test_render_package_rejects_a_list_beyond_the_row_ceiling() -> None:
    payload = _package_payload(rows=list(range(MAX_PAYLOAD_LIST_ITEMS + 1)))

    with pytest.raises(ValidationError, match=f"list longer than {MAX_PAYLOAD_LIST_ITEMS} items"):
        RenderPackage.model_validate(payload)


def test_render_package_rejects_a_string_beyond_the_length_ceiling() -> None:
    payload = _package_payload(narrative="x" * (MAX_PAYLOAD_STRING_LENGTH + 1))

    with pytest.raises(
        ValidationError, match=f"string longer than {MAX_PAYLOAD_STRING_LENGTH} characters"
    ):
        RenderPackage.model_validate(payload)


def test_render_package_rejects_nesting_beyond_the_depth_ceiling_without_recursing() -> None:
    """A recursive guard would raise RecursionError on exactly this input instead of rejecting."""

    deep: dict[str, Any] = {}
    node = deep
    for _ in range(MAX_PAYLOAD_DEPTH + 50):
        child: dict[str, Any] = {}
        node["nested"] = child
        node = child
    payload = _package_payload(deep=deep)

    with pytest.raises(ValidationError, match=f"nests deeper than {MAX_PAYLOAD_DEPTH} levels"):
        RenderPackage.model_validate(payload)


def test_render_context_is_bounded_like_report_data() -> None:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload["render_context"] = {"timezone": "x" * (MAX_PAYLOAD_STRING_LENGTH + 1)}

    with pytest.raises(ValidationError, match="string longer than"):
        RenderPackage.model_validate(payload)


def test_render_package_rejects_an_unsupported_envelope_version() -> None:
    """The envelope version must fail closed, like the report-data contract version.

    It was declared as SUPPORTED_RENDER_PACKAGE_VERSION and then used only as an OpenAPI
    example, never compared, so an unknown or newer package was accepted and rendered
    under v1 semantics.
    """

    payload = _package_payload()
    payload["render_package_version"] = "render_package.v99"

    with pytest.raises(ValidationError, match="unsupported render_package_version"):
        RenderPackage.model_validate(payload)


def test_render_package_accepts_the_supported_envelope_version() -> None:
    payload = _package_payload()
    payload["render_package_version"] = SUPPORTED_RENDER_PACKAGE_VERSION

    assert RenderPackage.model_validate(payload).render_package_version == (
        SUPPORTED_RENDER_PACKAGE_VERSION
    )
