"""Independent exact notice metadata recipes; unavailable authority stays explicit."""

from typing import Any

from app.contracts.composite_notice import NOTICE_COLUMNS, OBLIGATIONS
from app.services.composite_workbook.notice_hashes import canonical, require
from app.services.composite_workbook.source_values import resolve_pointer

SCOPE = (
    ("profile", "/comparison_profile"),
    ("contract_version", "/contract_version"),
    ("tenant_id", "/tenant_id"),
    *(
        (k, "/generations/before/payload/selection/" + k)
        for k in (
            "composite_id",
            "period_start",
            "period_end",
            "reporting_currency",
            "return_view",
            "methodology",
            "engine_version",
        )
    ),
    *(
        (side + "_" + k, "/generations/" + side + "/selection/" + k)
        for side in ("before", "after")
        for k in ("report_job_id", "snapshot_id", "report_revision_id", "snapshot_hash")
    ),
    ("pair_fingerprint", "/pair_fingerprint"),
    ("manifest_digest", "/manifest_digest"),
    ("qualification", "/qualification"),
    ("publication_state", "/publication_state"),
    ("completeness", "/notice_completeness"),
)
TITLES = {
    "NoticeScope": "Notice scope",
    "PairIndex": "Complete source coordinate union",
    "ArchivePath": "Acknowledged source path",
    "Obligations": "Partial obligation evidence",
}


def metadata_facts(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    pairs = [
        {
            "source_table_id": p["coordinate"]["table_id"],
            "source_row_id": p["coordinate"]["row_id"],
            "source_column_id": p["coordinate"]["column_id"],
            "presence": p["presence"],
            **{
                side + "_cell_ref": None
                if p[side + "_ref"] is None
                else canonical(p[side + "_ref"])
                for side in ("before", "after")
            },
        }
        for p in data["pair_index"]
    ]
    edges = [
        {
            "edge_index": str(e["position"]),
            **{
                k: e[k]
                for k in (
                    "source_document_id",
                    "target_document_id",
                    "relationship_id",
                    "semantic_role",
                    "source_generation",
                    "target_generation",
                )
            },
            "wire_transition_type": e["transition_type"],
            "acknowledgement_evidence_digest": e["acknowledgement"]["digest"],
        }
        for e in data["archive_path"]["edges"]
    ]
    obligations = [
        {
            "obligation_id": k,
            "status": data["obligations"][k]["status"],
            "reason_code": data["obligations"][k]["reason_code"],
            "evidence_refs": canonical(data["obligations"][k]["evidence_refs"]),
        }
        for k in OBLIGATIONS
    ]
    return {
        "scope": [
            {"field": k, "value": resolve_pointer(data, p), "source_pointer": p} for k, p in SCOPE
        ],
        "pair_index": pairs,
        "archive_path": edges,
        "obligations": obligations,
    }


def text_column(key: str) -> dict[str, Any]:
    return {
        "column_id": key,
        "label": key,
        "value_type": "TEXT",
        "unit": "TEXT",
        "display_unit": "TEXT",
        "display_conversion": "IDENTITY",
        "display_decimal_places": None,
        "display_rounding_mode": "HALF_UP",
        "currency": None,
        "scale": "1",
    }


def metadata_table(
    name: str, facts: list[dict[str, Any]], group: str, row_ids: list[str]
) -> dict[str, Any]:
    rows = []
    for i, (fact, row_id) in enumerate(zip(facts, row_ids, strict=True)):
        cells = {
            k: {
                "canonical_value": fact[k],
                "availability": "NOT_APPLICABLE" if fact[k] is None else "AVAILABLE",
                "reason_codes": ["SOURCE_COORDINATE_NOT_PRESENT"] if fact[k] is None else [],
                "source_pointer": f"/notice_facts/{group}/{i}/{k}",
            }
            for k in NOTICE_COLUMNS[name]
        }
        rows.append({"row_id": row_id, "cells": cells})
    return {
        "table_id": name,
        "title": TITLES[name],
        "columns": [text_column(k) for k in NOTICE_COLUMNS[name]],
        "rows": rows,
    }


def validate_metadata(data: dict[str, Any]) -> None:
    facts = metadata_facts(data)
    require(data["notice_facts"] == facts, "derived_facts")
    groups = ("scope", "pair_index", "archive_path", "obligations")
    row_ids = (
        [k for k, _ in SCOPE],
        [p["row_id"] for p in data["pair_index"]],
        [f"edge:{i}" for i in range(3)],
        list(OBLIGATIONS),
    )
    expected = [
        metadata_table(name, facts[group], group, ids)
        for name, group, ids in zip(NOTICE_COLUMNS, groups, row_ids, strict=True)
    ]
    require(data["tables"][28:] == expected, "metadata_tables")


def validate_notice_table_set(layout: dict[str, Any], table_names: set[str]) -> None:
    from app.contracts.composite_notice import TABLES
    from app.domain.templates.registry import TemplateRegistryError

    if (
        layout.get("required_tables") != list(TABLES)
        or layout.get("period_tables") != []
        or layout.get("optional_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    require(table_names == set(TABLES), "table_set")
