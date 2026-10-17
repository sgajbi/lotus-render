"""Component path/anchor guards use controlled v8 data, never claim a producer notice fixture."""

from copy import deepcopy
from typing import Any

import pytest
from source_context_fixtures import source_context_package

from app.services.composite_workbook.notice_custody import _validate_source_anchors
from app.services.composite_workbook.notice_hashes import digest
from app.services.composite_workbook.notice_path import validate_path
from app.services.composite_workbook.notice_source import source_custody_identity


def component_path() -> dict[str, Any]:
    data: dict[str, Any] = {"generations": {}, "archive_path": {"nodes": [], "edges": []}}
    for side, case in (("before", "original"), ("after", "corrected")):
        wire = source_context_package(case)
        payload = wire["report_data"]
        capture = {
            "report_revision_id": side + "-revision",
            "series_digest": "1" * 64,
            "source_revision_digest": "2" * 64,
            "factual_content_digest": "sha256:" + "3" * 64,
        }
        data["tenant_id"] = payload["tenant_id"]
        data["generations"][side] = {
            "payload": payload,
            "capture_identity": capture,
            "selection": {
                "report_job_id": side + "-job",
                "snapshot_id": side + "-snapshot",
                "report_revision_id": capture["report_revision_id"],
                "snapshot_hash": digest(payload),
            },
        }
    for i, role in enumerate(("O", "O_rr", "C", "C_rr")):
        side = "before" if i < 2 else "after"
        generation = data["generations"][side]
        node = {
            **generation["selection"],
            "position": i,
            "role": role,
            "economic_generation": side,
            "document_id": role + "-doc",
            "tenant_id": data["tenant_id"],
            "artifact_sha256": "sha256:" + str(i) * 64,
        }
        node["document_response"] = {
            **{
                k: node[k]
                for k in (
                    "document_id",
                    "tenant_id",
                    "report_job_id",
                    "snapshot_id",
                    "report_revision_id",
                )
            },
            "composite_report_identity": deepcopy(source_custody_identity(generation)),
            "declared_artifact_sha256": node["artifact_sha256"].removeprefix("sha256:"),
            "checksum": node["artifact_sha256"].removeprefix("sha256:"),
            "output_format": "xlsx",
            "report_type": "composite_review",
            "template_id": "composite-review",
            "template_version": "v8",
            "report_data_contract_version": "composite_review.v8",
            "purge_status": "not_eligible",
        }
        data["archive_path"]["nodes"].append(node)
    nodes = data["archive_path"]["nodes"]
    for source, target in zip(nodes, nodes[1:], strict=False):
        source["document_response"]["superseded_by_document_id"] = target["document_id"]
        target["document_response"]["correction_of_document_id"] = source["document_id"]
    for i in range(3):
        source, target = data["archive_path"]["nodes"][i : i + 2]
        payload = {
            "lifecycle_relationship_id": f"relation-{i}",
            "source_document_id": source["document_id"],
            "target_document_id": target["document_id"],
            "transition_type": "correct",
        }
        if i == 1:
            raw = {
                **payload,
                "transition_reason": "Controlled test correction",
                "transition_reason_code": "archive_document_correction_requested",
                "requested_by": "component-test",
                "requested_at": "2026-10-12T00:00:00Z",
            }
            kind = "ARCHIVE_RELATIONSHIP_RECORD"
        else:
            payload["event_type"] = "job_archive_lineage_recorded"
            raw = {
                "report_job_id": target["report_job_id"],
                "event_payload": payload,
                "event_family": "job_lifecycle",
                "event_schema_version": "report-status-event.v1",
                "event_type": "job_archive_lineage_recorded",
            }
            kind = "REPORT_LINEAGE_EVENT"
        data["archive_path"]["edges"].append(
            {
                "position": i,
                "relationship_id": payload["lifecycle_relationship_id"],
                "source_document_id": source["document_id"],
                "target_document_id": target["document_id"],
                "transition_type": "correct",
                "semantic_role": "ECONOMIC_CORRECTION" if i == 1 else "TECHNICAL_RERENDER",
                "source_generation": source["economic_generation"],
                "target_generation": target["economic_generation"],
                "acknowledgement": {"kind": kind, "raw_payload": raw},
            }
        )
    return data


def test_component_path_preserves_technical_and_economic_roles() -> None:
    data = component_path()
    original = deepcopy(data)
    validate_path(data)
    assert data == original
    assert [e["transition_type"] for e in data["archive_path"]["edges"]] == ["correct"] * 3


@pytest.mark.parametrize(
    "mutation",
    [
        "role",
        "duplicate",
        "skip",
        "ack",
        "current",
        "identity",
        "digest",
        "tuple",
        "forward",
        "back",
        "technical_tuple",
        "node_version",
    ],
)
def test_rehashed_path_semantic_mutations_refuse(mutation: str) -> None:
    data = component_path()
    nodes, edges = (data["archive_path"][k] for k in ("nodes", "edges"))
    if mutation == "role":
        edges[0]["semantic_role"] = "ECONOMIC_CORRECTION"
    elif mutation == "duplicate":
        nodes[1]["document_id"] = nodes[0]["document_id"]
    elif mutation == "skip":
        edges[1]["source_document_id"] = nodes[0]["document_id"]
    elif mutation == "ack":
        edges[0]["acknowledgement"]["raw_payload"]["event_family"] = "archive_lifecycle"
    elif mutation == "current":
        edges[1]["acknowledgement"]["raw_payload"]["current_document_id"] = nodes[3]["document_id"]
    elif mutation == "identity":
        nodes[2]["document_response"]["composite_report_identity"]["selection"]["return_view"] = (
            "GROSS"
        )
    elif mutation == "digest":
        nodes[0]["artifact_sha256"] = "sha256:" + "9" * 64
    elif mutation == "forward":
        nodes[0]["document_response"]["superseded_by_document_id"] = nodes[3]["document_id"]
    elif mutation == "back":
        nodes[2]["document_response"]["correction_of_document_id"] = nodes[0]["document_id"]
    elif mutation == "technical_tuple":
        nodes[1]["report_job_id"] = "foreign"
        nodes[1]["document_response"]["report_job_id"] = "foreign"
    elif mutation == "node_version":
        nodes[0]["document_response"]["template_version"] = "v9"
    else:
        nodes[2]["snapshot_id"] = "foreign"
        nodes[2]["document_response"]["snapshot_id"] = "foreign"
    # Recomputed wrappers do not clear the semantic guard.
    data["manifest_digest"] = digest(data)
    with pytest.raises(ValueError, match="composite_notice_"):
        validate_path(data)


def test_six_field_anchor_equality_and_optional_product_omission() -> None:
    data = component_path()
    identity: dict[str, Any] = {"generations": {}}
    for side, i in (("before", 0), ("after", 2)):
        node = data["archive_path"]["nodes"][i]
        identity["generations"][side] = {
            **data["generations"][side]["selection"],
            "source_document_id": node["document_id"],
            "source_identity": node["document_response"]["composite_report_identity"],
        }
    _validate_source_anchors(data, identity)
    identity["generations"]["before"]["source_document_id"] = "O_rr-doc"
    with pytest.raises(ValueError, match="custody_source_anchor"):
        _validate_source_anchors(data, identity)
    generation = data["generations"]["before"]
    generation["payload"]["source_products"] = []
    assert "source_products" not in source_custody_identity(generation)
