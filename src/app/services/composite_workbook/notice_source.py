"""Retained notice admission: frozen wire schema and unchanged original v8 semantics."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from app.contracts.composite_notice import (
    OBLIGATIONS,
    SOURCE_TABLES,
    TABLES,
    CompositeNoticeContent,
)
from app.services.composite_workbook.notice_coordinates import validate_side_tables
from app.services.composite_workbook.notice_hashes import (
    canonical,
    digest,
    require,
    validate_hashes,
)
from app.services.composite_workbook.notice_metadata import validate_metadata
from app.services.composite_workbook.notice_path import validate_path

SCOPE_AXES = (
    "tenant_id",
    "composite_id",
    "period_start",
    "period_end",
    "reporting_currency",
    "return_view",
    "methodology",
    "engine_version",
)


@lru_cache
def notice_schema_validator(name: str = "composite_review.v9.schema.json") -> Any:
    # Final Report66dc assets match the Report447 main subtree; Archive197 DTO verified offline.
    # This correspondence is not joined live authority/custody acceptance.
    path = files("app.contracts").joinpath("notice_schemas/" + name)
    return Draft202012Validator(json.loads(path.read_bytes()), format_checker=FormatChecker())


def source_custody_identity(generation: dict[str, Any]) -> dict[str, Any]:
    data, capture = generation["payload"], generation["capture_identity"]
    identity = {
        **{
            k: data[k]
            for k in (
                "contract_version",
                "qualification",
                "publication_state",
                "selection",
                "source_context",
            )
        },
        "definition": {k: data["definition"][k] for k in ("pin", "source_response_digest")},
        **{
            k: capture[k].removeprefix("sha256:")
            for k in (
                "series_digest",
                "source_revision_digest",
                "factual_content_digest",
            )
        },
    }
    products = [
        {k: p[k] for k in ("pin", "source_response_digest")}
        for p in data.get("source_products", [])
    ]
    if products:
        identity["source_products"] = products
    return identity


def _validate_generation(generation: dict[str, Any], tenant: str) -> None:
    from app.services.composite_workbook.source_cells import validate_dataset

    payload = generation["payload"]
    validate_dataset(payload)
    require(payload["contract_version"] == "composite_review.v8", "source_version")
    require([t["table_id"] for t in payload["tables"]] == list(SOURCE_TABLES), "source_layout")
    require(payload["tenant_id"] == tenant, "source_tenant")
    require(
        generation["source_identity"] == {k: payload["selection"][k] for k in SCOPE_AXES},
        "source_scope",
    )
    require(
        generation["capture_identity"]["report_revision_id"]
        == generation["selection"]["report_revision_id"],
        "source_revision",
    )
    require(digest(payload) == generation["selection"]["snapshot_hash"], "snapshot_hash")


def _validate_pair(data: dict[str, Any]) -> None:
    before, after = (data["generations"][k] for k in ("before", "after"))
    require(before["selection"] != after["selection"], "distinct_pair")
    require(before["source_identity"] == after["source_identity"], "pair_scope")
    require(before["payload"]["selection"] != after["payload"]["selection"], "economic_generation")
    for a, b in zip(before["payload"]["tables"], after["payload"]["tables"], strict=True):
        require(a["columns"] == b["columns"], "source_column_policy")


def _validate_obligations(data: dict[str, Any]) -> None:
    require(set(data["obligations"]) == set(OBLIGATIONS), "obligations")
    # Initial profile accepts only captured facts; it cannot promote absent institutional authority.
    reasons = (
        ("CAPTURED_INTERNAL", "RETAINED_SOURCE_FACTS_ONLY"),
        ("CAPTURED_INTERNAL", "RETAINED_REPORT_HORIZON_ONLY"),
        ("UNAVAILABLE", "AUTHORITATIVE_REPORT_REASON_NOT_CAPTURED"),
        ("UNAVAILABLE", "AUTHORITATIVE_MATERIALITY_NOT_CAPTURED"),
        ("UNAVAILABLE", "REPORT_PUBLICATION_APPROVAL_NOT_CAPTURED"),
        ("CAPTURED_INTERNAL", "ACKNOWLEDGED_SOURCE_PATH_ONLY"),
        ("UNAVAILABLE", "CMP_LIN_006_SUPPLIER_PRODUCT_NOT_CAPTURED"),
        ("UNAVAILABLE", "CMP_RPT_009_DELIVERY_REGISTER_NOT_CAPTURED"),
    )
    refs: tuple[list[str], ...] = (
        ["/generations/before", "/generations/after"],
        [
            f"/generations/{side}/payload/selection/{k}"
            for side in ("before", "after")
            for k in ("period_start", "period_end")
        ],
        [],
        [],
        [],
        [f"/archive_path/edges/{i}" for i in range(3)],
        [],
        [],
    )
    expected = {
        k: {"status": status, "reason_code": reason, "evidence_refs": ref}
        for k, (status, reason), ref in zip(OBLIGATIONS, reasons, refs, strict=True)
    }
    require(data["obligations"] == expected, "authority_promotion")


def validate_notice(data: dict[str, Any]) -> CompositeNoticeContent:
    require(next(notice_schema_validator().iter_errors(data), None) is None, "schema")
    content = CompositeNoticeContent.model_validate_json(json.dumps(data, allow_nan=False))
    require([t["table_id"] for t in data["tables"]] == list(TABLES), "table_order")
    for side in ("before", "after"):
        _validate_generation(data["generations"][side], data["tenant_id"])
    _validate_pair(data)
    _validate_obligations(data)
    validate_hashes(data)
    validate_path(data)
    validate_side_tables(data)
    validate_metadata(data)
    # Measure complete retained data once; side budgets never replace the aggregate.
    require(len(canonical(data).encode("ascii")) <= 8_388_608, "capture_capacity")
    return content
