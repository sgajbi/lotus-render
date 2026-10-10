"""Validate retained Manage/Performance joins without source I/O or calculations."""

import json
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Any
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from app.contracts.composite_products import CompositeProductsContent, ProductTable
from app.contracts.composite_selection import CompositePinnedSelection
from app.contracts.composite_source_context import CapturedMembership, CompositeSourceContextContent
from app.services.composite_workbook.eligibility_hashes import (
    source_content_digest,
    whole_response_digest,
)
from app.services.composite_workbook.pinned_identity import validate_pinned_identity
from app.services.composite_workbook.source_products import (
    validate_response_digest,
    validate_source_products,
)


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("composite_source_context_conflict")


@lru_cache
def source_context_schema_validator() -> Any:
    path = files("app.contracts").joinpath("source_context_schemas/composite_review.v8.schema.json")
    return Draft202012Validator(json.loads(path.read_bytes()), format_checker=FormatChecker())


def product_view(content: CompositeSourceContextContent) -> CompositeProductsContent:
    """Typed adapter for unchanged v2 validators; never a serialized v2 claim."""
    return CompositeProductsContent.model_construct(
        contract_version="composite_review.v2",
        qualification=content.qualification,
        publication_state=content.publication_state,
        tenant_id=content.tenant_id,
        selection=content.selection,
        source_response_digest=content.source_response_digest,
        source_response=content.source_response,
        report_facts=content.report_facts,
        source_products=content.source_products,
        tables=[
            ProductTable.model_validate(t.model_dump())
            for t in content.tables
            if t.table_id in {"AnnualReturns", "TrailingReturns"}
        ],
    )


def validate_source_context(content: CompositeSourceContextContent, raw: dict[str, Any]) -> None:
    require(next(source_context_schema_validator().iter_errors(raw), None) is None)
    CompositePinnedSelection.model_validate_json(json.dumps(content.selection))
    require(content.tenant_id == content.selection["tenant_id"])
    validate_response_digest(
        content.selection, content.source_response, content.source_response_digest
    )
    validate_pinned_identity(content)
    require(bool(content.source_context.since_inception or content.source_context.memberships))
    require(content.source_context.definition == content.definition.pin)
    require(
        content.source_context.memberships == [item.pin for item in content.supplied_memberships]
    )
    _validate_definition(content)
    _validate_vectors(content)
    _validate_capture_capacity(content)


def _validate_vectors(content: CompositeSourceContextContent) -> None:
    if content.source_products:
        validate_source_products(product_view(content))
        require(
            all(
                p.pin.selection["engine_version"] == content.selection["engine_version"]
                for p in content.source_products
            )
        )
    vectors = [content.selection, *(p.pin.selection for p in content.source_products)]
    require(
        all(
            w["definition_content_hash"] == content.definition.pin.content_hash
            for vector in vectors
            for w in vector["windows"]
        )
    )
    _validate_memberships(content, vectors)


def _validate_capture_capacity(content: CompositeSourceContextContent) -> None:
    captures = [
        content.source_response,
        content.definition.source_response,
        *(p.source_response for p in content.source_products),
        *(m.source_response for m in content.supplied_memberships),
    ]
    require(
        sum(len(json.dumps(c, ensure_ascii=False).encode("utf-8")) for c in captures) <= 8_388_608
    )


def _validate_definition(content: CompositeSourceContextContent) -> None:
    capture = content.definition
    raw, pin, selection = capture.source_response, capture.pin, content.selection
    require(raw["content_hash"] == source_content_digest(raw, recursive=True) == pin.content_hash)
    require(whole_response_digest(raw) == capture.source_response_digest == pin.response_digest)
    require(raw["definition_version"] == pin.definition_version)
    require(
        all(raw[k] == selection[k] for k in ("tenant_id", "composite_id", "reporting_currency"))
    )
    endpoint = (
        "/api/v1/rebalance/composites/"
        + quote(selection["composite_id"], safe="")
        + "/definitions/"
        + quote(pin.definition_version, safe="")
    )
    require(capture.endpoint == endpoint)
    require(
        date.fromisoformat(selection["period_start"]) >= date.fromisoformat(raw["inception_date"])
    )
    require(
        raw["termination_date"] is None
        or date.fromisoformat(selection["period_end"])
        <= date.fromisoformat(raw["termination_date"])
    )


def _validate_memberships(
    content: CompositeSourceContextContent, vectors: list[dict[str, Any]]
) -> None:
    captures = content.supplied_memberships
    if not captures:
        return
    by_revision = {m.pin.membership_revision: m for m in captures}
    require(len(by_revision) == len(captures))
    referenced = {w["membership_content_hash"] for v in vectors for w in v["windows"]}
    actual = {m.pin.content_hash for m in captures}
    require(referenced.issubset(actual))
    linked = set(referenced)
    for capture in captures:
        _validate_membership_capture(content, capture)
        linked.update(_membership_parent_hashes(capture, by_revision, referenced))
        _validate_intervals(capture.source_response)
    require(actual == linked)


def _membership_parent_hashes(
    capture: CapturedMembership, by_revision: dict[str, CapturedMembership], referenced: set[str]
) -> set[str]:
    raw = capture.source_response
    parent = raw["supersedes_membership_revision"]
    if parent is None:
        require(raw["affected_from"] is None and raw["affected_to"] is None)
        return set()
    _validate_parent(raw, by_revision)
    if capture.pin.content_hash in referenced:
        return {by_revision[parent].pin.content_hash}
    return set()


def _validate_membership_capture(
    content: CompositeSourceContextContent, capture: CapturedMembership
) -> None:
    raw, pin = capture.source_response, capture.pin
    require(raw["content_hash"] == source_content_digest(raw) == pin.content_hash)
    require(whole_response_digest(raw) == capture.source_response_digest == pin.response_digest)
    require(raw["membership_revision"] == pin.membership_revision)
    require(all(raw[k] == content.selection[k] for k in ("tenant_id", "composite_id")))
    require(raw["definition_version"] == content.definition.pin.definition_version)
    require(
        capture.endpoint
        == content.definition.endpoint + "/membership/" + quote(pin.membership_revision, safe="")
    )


def _validate_intervals(raw: dict[str, Any]) -> None:
    for decision in raw["decisions"]:
        require(
            decision["effective_to"] is None
            or date.fromisoformat(decision["effective_to"])
            >= date.fromisoformat(decision["effective_from"])
        )


def _validate_parent(raw: dict[str, Any], captures: dict[str, CapturedMembership]) -> None:
    parent = raw["supersedes_membership_revision"]
    require(parent in captures and parent != raw["membership_revision"])
    require(captures[parent].source_response["supersedes_membership_revision"] is None)
    require(raw["affected_from"] is not None and raw["affected_to"] is not None)
    require(date.fromisoformat(raw["affected_to"]) >= date.fromisoformat(raw["affected_from"]))
