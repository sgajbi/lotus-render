"""Independent notice hash verification; never mint Report revision identities."""

import hashlib
import json
from typing import Any

SELECTOR = {
    "report_family_id": "composite_review",
    "report_type": "composite_review",
    "ordering_mode_id": "single_composite",
    "comparison_profile": "RETAINED_SAME_SCOPE_CORRECTION_NOTICE_V1",
    "report_data_contract_version": "composite_review.v9",
    "input_snapshot_contract_version": "composite_review.v9",
    "template_id": "composite-review",
    "template_version": "v9",
    "output_format": "xlsx",
    "locale": "en-SG",
    "brand": "private_banking",
}
OPERATION = "ORDER_RETAINED_COMPOSITE_NOTICE"
PREFIX = "lotus-report/composite-notice/"


def canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def require(condition: bool, category: str) -> None:
    if not condition:
        raise ValueError("composite_notice_" + category)


def pair_preimage(data: dict[str, Any]) -> dict[str, Any]:
    path = data["archive_path"]
    nodes = [{k: v for k, v in node.items() if k != "document_response"} for node in path["nodes"]]
    edges = [
        {
            **{k: v for k, v in edge.items() if k != "acknowledgement"},
            "acknowledgement_digest": edge["acknowledgement"]["digest"],
        }
        for edge in path["edges"]
    ]
    return {
        "domain": PREFIX + "pair.v1",
        "operation": OPERATION,
        "selector": SELECTOR,
        "tenant_id": data["tenant_id"],
        "before": data["generations"]["before"]["selection"],
        "after": data["generations"]["after"]["selection"],
        "ordered_nodes": nodes,
        "ordered_edges": edges,
    }


def manifest_preimage(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": PREFIX + "manifest.v1",
        "operation": OPERATION,
        "selector": SELECTOR,
        **{
            k: data[k]
            for k in (
                "tenant_id",
                "qualification",
                "publication_state",
                "notice_completeness",
                "pair_fingerprint",
                "generations",
                "archive_path",
                "obligations",
            )
        },
        "projection_recipe_id": "report446-v9-32-table-projection.r4",
    }


def validate_hashes(data: dict[str, Any]) -> None:
    for node in data["archive_path"]["nodes"]:
        require(
            node["document_response_digest"]
            == digest(
                {
                    "domain": PREFIX + "archive-document.v1",
                    "raw_payload": node["document_response"],
                }
            ),
            "document_digest",
        )
    for edge in data["archive_path"]["edges"]:
        ack = edge["acknowledgement"]
        require(
            ack["digest"]
            == digest(
                {
                    "domain": PREFIX + "acknowledgement.v1",
                    "kind": ack["kind"],
                    "raw_payload": ack["raw_payload"],
                }
            ),
            "acknowledgement_digest",
        )
    require(data["pair_fingerprint"] == digest(pair_preimage(data)), "pair_digest")
    require(data["manifest_digest"] == digest(manifest_preimage(data)), "manifest_digest")
