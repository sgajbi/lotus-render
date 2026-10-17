"""Verify the acknowledged four-node path without treating wire 'correct' as authority."""

import json
from typing import Any

from pydantic import ValidationError

from app.contracts.composite_notice import RelationshipRecord
from app.services.composite_workbook.notice_hashes import require


def _validate_node(node: dict[str, Any], data: dict[str, Any], index: int) -> None:
    from app.services.composite_workbook.notice_source import source_custody_identity

    side = "before" if index < 2 else "after"
    require(
        (node["position"], node["role"], node["economic_generation"])
        == (
            index,
            ("O", "O_rr", "C", "C_rr")[index],
            side,
        ),
        "node_role",
    )
    response = node["document_response"]
    require(response["purge_status"] != "purged", "source_purged")
    for key in ("document_id", "tenant_id", "report_job_id", "snapshot_id", "report_revision_id"):
        require(node[key] == response[key], "node_response")
    require(node["tenant_id"] == data["tenant_id"], "node_tenant")
    require(
        node["artifact_sha256"] == "sha256:" + response["declared_artifact_sha256"]
        and response["checksum"] == response["declared_artifact_sha256"],
        "node_artifact",
    )
    require(
        (
            response["output_format"],
            response["report_type"],
            response["template_id"],
            response["template_version"],
            response["report_data_contract_version"],
        )
        == ("xlsx", "composite_review", "composite-review", "v8", "composite_review.v8"),
        "node_contract",
    )
    generation = data["generations"][side]
    require(node["snapshot_hash"] == generation["selection"]["snapshot_hash"], "node_snapshot")
    require(
        response["composite_report_identity"] == source_custody_identity(generation),
        "node_source_identity",
    )
    # Economic anchors and their technical rerenders retain the exact original capture tuple.
    for key in ("report_job_id", "snapshot_id", "report_revision_id"):
        require(node[key] == generation["selection"][key], "source_anchor")
    require(
        node["report_revision_id"] == generation["capture_identity"]["report_revision_id"],
        "node_revision",
    )


def _validate_edge(edge: dict[str, Any], nodes: list[dict[str, Any]], index: int) -> None:
    source, target = nodes[index : index + 2]
    expected = (
        index,
        source["document_id"],
        target["document_id"],
        "correct",
        ("TECHNICAL_RERENDER", "ECONOMIC_CORRECTION", "TECHNICAL_RERENDER")[index],
        source["economic_generation"],
        target["economic_generation"],
    )
    require(
        tuple(
            edge[k]
            for k in (
                "position",
                "source_document_id",
                "target_document_id",
                "transition_type",
                "semantic_role",
                "source_generation",
                "target_generation",
            )
        )
        == expected,
        "edge_path",
    )
    ack = edge["acknowledgement"]
    raw = ack["raw_payload"]
    if index == 1:
        require(ack["kind"] == "ARCHIVE_RELATIONSHIP_RECORD", "ack_kind")
        # Generic JSON Schema format support varies by environment. Enforce native
        # AwareDatetime and strict field semantics without rewriting captured strings.
        _validate_relationship_record(raw)
        payload = raw
    else:
        require(ack["kind"] == "REPORT_LINEAGE_EVENT", "ack_kind")
        require(
            (raw["event_family"], raw["event_schema_version"], raw["event_type"])
            == (
                "job_lifecycle",
                "report-status-event.v1",
                "job_archive_lineage_recorded",
            ),
            "ack_event",
        )
        require(raw["report_job_id"] == target["report_job_id"], "ack_job")
        payload = raw["event_payload"]
        require(payload["event_type"] == "job_archive_lineage_recorded", "ack_event")
    require(payload["lifecycle_relationship_id"] == edge["relationship_id"], "ack_relationship")
    for key in ("source_document_id", "target_document_id", "transition_type"):
        require(payload[key] == edge[key], "ack_endpoint")


def _validate_relationship_record(raw: dict[str, Any]) -> None:
    try:
        RelationshipRecord.model_validate_json(json.dumps(raw))
    except ValidationError as exc:
        raise ValueError("composite_notice_ack_record") from exc


def _validate_links(nodes: list[dict[str, Any]]) -> None:
    for source, target in zip(nodes, nodes[1:], strict=False):
        require(
            source["document_response"]["superseded_by_document_id"] == target["document_id"]
            and target["document_response"]["correction_of_document_id"] == source["document_id"],
            "node_path_links",
        )


def validate_path(data: dict[str, Any]) -> None:
    nodes, edges = (data["archive_path"][k] for k in ("nodes", "edges"))
    require(len({n["document_id"] for n in nodes}) == 4, "duplicate_node")
    require(len({e["relationship_id"] for e in edges}) == 3, "duplicate_edge")
    _validate_links(nodes)
    for i, node in enumerate(nodes):
        _validate_node(node, data, i)
    for i, edge in enumerate(edges):
        _validate_edge(edge, nodes, i)
