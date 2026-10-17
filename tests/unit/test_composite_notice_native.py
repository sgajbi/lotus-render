"""Receiver correspondence to native producer assets; no live source/Archive acceptance."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from notice_fixtures import ROOT, native_bytes, native_json, notice_package

from app.contracts.composite_notice import CompositeNoticeContent, RelationshipRecord
from app.contracts.composite_notice_custody import NoticeCustodyIdentity
from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.notice_custody import validate_notice_custody
from app.services.composite_workbook.notice_hashes import (
    PREFIX,
    canonical,
    manifest_preimage,
    pair_preimage,
    validate_hashes,
)
from app.services.composite_workbook.notice_path import _validate_relationship_record
from app.services.composite_workbook.notice_source import notice_schema_validator, validate_notice


def test_native_complete_positive_and_semantic_serialization_correspondence() -> None:
    package = notice_package()
    original = canonical(package)
    content = validate_notice(package["report_data"])
    validate_notice_custody(RenderPackage.model_validate(package))
    identity = package["render_context"]["archive"]["composite_report_identity"]
    typed_identity = NoticeCustodyIdentity.model_validate_json(json.dumps(identity))
    assert json.loads(typed_identity.model_dump_json()) == identity
    assert json.loads(content.model_dump_json()) == package["report_data"]
    assert len(content.tables) == 32
    assert len(content.pair_index) == 1289
    assert canonical(package) == original


def test_native_schemas_and_fixture_bytes_are_pinned() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    assert hashlib.sha256((ROOT / "manifest.json").read_bytes()).hexdigest() == (
        "c90bd5a91e2c629885cbcb9f1927f855f0641dfe668e47f4bdffc790695258b9"
    )
    for name, entry in manifest["files"].items():
        if name.endswith(".schema.json"):
            raw = (Path("src/app/contracts/notice_schemas") / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        else:
            native_bytes(name)


def test_nine_known_answer_canonical_preimages() -> None:
    data = notice_package()["report_data"]
    preimages: dict[str, Any] = {
        "pair": pair_preimage(data),
        "manifest": manifest_preimage(data),
    }
    for i, node in enumerate(data["archive_path"]["nodes"]):
        preimages[f"document-{i}"] = {
            "domain": PREFIX + "archive-document.v1",
            "raw_payload": node["document_response"],
        }
    for i, edge in enumerate(data["archive_path"]["edges"]):
        ack = edge["acknowledgement"]
        preimages[f"acknowledgement-{i}"] = {
            "domain": PREFIX + "acknowledgement.v1",
            "kind": ack["kind"],
            "raw_payload": ack["raw_payload"],
        }
    digests = native_json("known-answer-digests.json")
    for name, value in preimages.items():
        actual = canonical(value).encode("ascii")
        assert actual == native_bytes(name + ".preimage.json")
        assert "sha256:" + hashlib.sha256(actual).hexdigest() == digests[name]


@pytest.mark.parametrize(
    "case",
    [
        "old_post_kind",
        "dynamic_head_field",
        "naive_timestamp",
        "missing_record_reason",
        "wrong_relationship",
        "technical_economic_promotion",
        "purged_source",
        "source_hash",
        "duplicate_coordinate",
        "omitted_coordinate",
        "wrong_cell_ref",
        "changed_source_policy",
        "omitted_side_cell",
        "null_zero_substitute",
        "materiality_inference",
    ],
)
def test_native_resealed_single_faults_refuse(case: str) -> None:
    data = native_json(f"refusal-single-fault-{case}.json")
    validate_hashes(data)
    with pytest.raises(ValueError):
        validate_notice(data)


def test_local_models_do_not_coerce_source_wire() -> None:
    data = notice_package()["report_data"]
    data["archive_path"]["nodes"][0]["position"] = "0"
    with pytest.raises(ValueError):
        CompositeNoticeContent.model_validate(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("contract_version", "composite_review.v8"),
        ("comparison_profile", "RETAINED_CROSS_SCOPE_NOTICE"),
        ("publication_state", "APPROVED"),
        ("notice_completeness", "COMPLETE"),
    ],
)
def test_native_version_profile_and_authority_refuse(key: str, value: str) -> None:
    data = notice_package()["report_data"]
    data[key] = value
    with pytest.raises(ValueError, match="composite_notice_schema"):
        validate_notice(data)


def test_native_relationship_field_schema_correspondence() -> None:
    raw = notice_schema_validator().schema["$defs"]["Acknowledgement"]["properties"]["raw_payload"]
    producer = raw["anyOf"][0]
    record = relationship_record()
    native = notice_schema_validator().evolve(schema=producer)
    assert not list(native.iter_errors(record))
    assert set(producer["properties"]) == set(RelationshipRecord.model_fields)
    assert set(producer["required"]) == set(RelationshipRecord.model_fields)
    assert producer["additionalProperties"] is False and producer["type"] == "object"
    _validate_relationship_record(record)


def relationship_record() -> dict[str, Any]:
    payload = notice_package()["report_data"]
    record: dict[str, Any] = payload["archive_path"]["edges"][1]["acknowledgement"]["raw_payload"]
    return record


@pytest.mark.parametrize(
    "key", ["lifecycle_relationship_id", "source_document_id", "target_document_id"]
)
def test_native_dto_does_not_expand_receiver_identifier_policy(key: str) -> None:
    raw = notice_schema_validator().schema["$defs"]["Acknowledgement"]["properties"]["raw_payload"]
    native = notice_schema_validator().evolve(schema=raw["anyOf"][0])
    record = {**relationship_record(), key: "x" * 256}
    assert not list(native.iter_errors(record))
    _validate_relationship_record(record)
    record[key] += "x"
    # Native DTO admits this value; the receiver's existing profile still refuses it.
    assert not list(native.iter_errors(record))
    with pytest.raises(ValueError, match="composite_notice_ack_record"):
        _validate_relationship_record(record)


@pytest.mark.parametrize(
    "key,value",
    [
        ("requested_by", 1),
        ("source_document_id", 1),
        ("transition_type", "economic"),
    ],
)
def test_native_record_types_and_transitions_refuse(key: str, value: Any) -> None:
    raw = notice_schema_validator().schema["$defs"]["Acknowledgement"]["properties"]["raw_payload"]
    native = notice_schema_validator().evolve(schema=raw["anyOf"][0])
    record = {**relationship_record(), key: value}
    assert list(native.iter_errors(record))
    with pytest.raises(ValueError, match="composite_notice_ack_record"):
        _validate_relationship_record(record)


def test_relationship_timestamp_guard_preserves_raw_capture_without_format_checker() -> None:
    raw = notice_schema_validator().schema["$defs"]["Acknowledgement"]["properties"]["raw_payload"]
    native = notice_schema_validator().evolve(schema=raw["anyOf"][0], format_checker=None)
    record = relationship_record()
    for value in ("2026-10-11T19:30:22.153880Z", "2026-10-11T21:30:22.153880+02:00"):
        record["requested_at"] = value
        before = canonical(record)
        assert not list(native.iter_errors(record))
        _validate_relationship_record(record)
        assert canonical(record) == before
    record["requested_at"] = "2026-10-11T19:30:22"
    assert not list(native.iter_errors(record))
    with pytest.raises(ValueError, match="composite_notice_ack_record"):
        _validate_relationship_record(record)


def test_concrete_inherited_v8_schema_optional_omission_and_digest_spelling() -> None:
    validator = notice_schema_validator("composite_notice_custody.v9.schema.json").evolve(
        schema={"$ref": "#/$defs/CompositeReportIdentityV8"}
    )
    identity = notice_package()["report_data"]["archive_path"]["nodes"][0]["document_response"][
        "composite_report_identity"
    ]
    assert not list(validator.iter_errors(identity))
    identity.pop("source_products", None)
    # Schema correspondence only: omission is legal and no default is written into retained bytes.
    # Runtime source equality separately refuses omission when actual sources contain products.
    original = canonical(identity)
    assert not list(validator.iter_errors(identity))
    assert canonical(identity) == original and "source_products" not in identity
    identity["series_digest"] = "sha256:" + identity["series_digest"]
    assert list(validator.iter_errors(identity))


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize(
    "key",
    [
        "report_job_id",
        "snapshot_id",
        "report_revision_id",
        "snapshot_hash",
        "source_document_id",
        "source_identity",
    ],
)
def test_each_of_six_custody_anchors_refuses_independent_mutation(side: str, key: str) -> None:
    wire = notice_package()
    anchor = wire["render_context"]["archive"]["composite_report_identity"]["generations"][side]
    if key == "source_identity":
        anchor[key]["selection"]["return_view"] = "GROSS"
    elif key == "snapshot_hash":
        anchor[key] = "sha256:" + "0" * 64
    else:
        anchor[key] = "foreign"
    with pytest.raises(ValueError):
        validate_notice_custody(RenderPackage.model_validate(wire))


@pytest.mark.parametrize(
    "fault", ["revision", "lineage", "snapshot_reuse", "revision_reuse", "scope"]
)
def test_separate_own_capture_refuses(fault: str) -> None:
    wire = notice_package()
    source = wire["report_data"]["generations"]["before"]["selection"]
    if fault == "revision":
        wire["render_context"]["report_revision_id"] = "foreign"
    elif fault == "lineage":
        wire["lineage_refs"] = []
    elif fault == "snapshot_reuse":
        wire["snapshot_id"] = source["snapshot_id"]
        wire["lineage_refs"][0] = source["snapshot_id"]
    elif fault == "revision_reuse":
        wire["render_context"]["report_revision_id"] = source["report_revision_id"]
        wire["render_context"]["archive"]["report_revision_id"] = source["report_revision_id"]
        wire["lineage_refs"][1] = source["report_revision_id"]
    else:
        wire["render_context"]["archive"]["reporting_period_start"] = "2026-01-02"
    with pytest.raises(ValueError):
        validate_notice_custody(RenderPackage.model_validate(wire))
