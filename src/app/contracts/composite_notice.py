"""Additive retained correction notice; source datasets keep their original contracts."""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, Field

from app.contracts.composite_review import CompositeCell, CompositeColumn, CompositeModel
from app.contracts.composite_selection import Digest

Side = Literal["before", "after"]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]
PROFILE = "RETAINED_SAME_SCOPE_CORRECTION_NOTICE_V1"
SOURCE_TABLES = (
    "Summary",
    "PeriodReturns",
    "Contribution",
    "Methods",
    "Lineage",
    "Disclosures",
    "AnnualReturns",
    "Risk",
    "Members",
    "EligibilityReasons",
    "Attribution",
    "Restatement",
    "SinceInception",
    "MembershipHistory",
)
NOTICE_COLUMNS = {
    "NoticeScope": ("field", "value", "source_pointer"),
    "PairIndex": (
        "source_table_id",
        "source_row_id",
        "source_column_id",
        "presence",
        "before_cell_ref",
        "after_cell_ref",
    ),
    "ArchivePath": (
        "edge_index",
        "source_document_id",
        "target_document_id",
        "relationship_id",
        "wire_transition_type",
        "semantic_role",
        "source_generation",
        "target_generation",
        "acknowledgement_evidence_digest",
    ),
    "Obligations": ("obligation_id", "status", "reason_code", "evidence_refs"),
}
TABLES = tuple(p + t for p in ("Before_", "After_") for t in SOURCE_TABLES) + tuple(NOTICE_COLUMNS)
OBLIGATIONS = (
    "before_after_results",
    "affected_periods",
    "reason",
    "materiality",
    "report_approval",
    "report_replacements",
    "explanation_delta_interaction",
    "recipient_distribution",
)
BareDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SelectionTuple(CompositeModel):
    report_job_id: Identifier
    snapshot_id: Identifier
    report_revision_id: Identifier
    snapshot_hash: Digest


class CaptureIdentity(CompositeModel):
    report_revision_id: str = Field(pattern=r"^rrv3_[0-9a-f]{64}$")
    series_digest: BareDigest
    source_revision_digest: BareDigest
    factual_content_digest: Digest


class NoticeGeneration(CompositeModel):
    selection: SelectionTuple
    contract_version: Literal["composite_review.v8"]
    snapshot_response_bytes_sha256: Digest
    # Exact retained mappings: frozen native schema plus unchanged v8 semantic validation
    # run before any projection. Never dump a typed adapter back over these source bytes.
    payload: dict[str, Any]
    source_revision_vector: dict[str, Any]
    source_identity: dict[str, Any]
    capture_identity: CaptureIdentity


class Generations(CompositeModel):
    before: NoticeGeneration
    after: NoticeGeneration


class Coordinate(CompositeModel):
    generation: Side
    table_index: int = Field(ge=0, le=13)
    row_index: int = Field(ge=0, le=9999)
    column_index: int = Field(ge=0, le=31)
    table_id: Identifier
    row_id: Identifier
    column_id: Identifier
    source_pointer: str = Field(min_length=1, max_length=4096)


class SourceCoordinate(CompositeModel):
    table_id: Identifier
    row_id: Identifier
    column_id: Identifier


class PairIndexItem(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    coordinate: SourceCoordinate
    presence: Literal["BOTH_PRESENT", "BEFORE_ONLY", "AFTER_ONLY"]
    before_ref: Coordinate | None
    after_ref: Coordinate | None


class NoticeCell(CompositeCell):
    source_pointer: str = Field(pattern=r"^(/generations/(before|after)/payload/|/notice_facts/)")


class NoticeRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, NoticeCell]


class NoticeTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[CompositeColumn] = Field(min_length=1, max_length=32)
    rows: list[NoticeRow] = Field(min_length=1, max_length=10000)


class Acknowledgement(CompositeModel):
    kind: Literal["ARCHIVE_RELATIONSHIP_RECORD", "REPORT_LINEAGE_EVENT"]
    source_capture: str = Field(min_length=1, max_length=512)
    raw_payload: dict[str, Any]
    digest: Digest


class RelationshipRecord(CompositeModel):
    """Verified offline Archive197 fields with Render's bounded-ID/aware-time profile."""

    lifecycle_relationship_id: Identifier
    source_document_id: Identifier
    target_document_id: Identifier
    transition_type: Literal["supersede", "correct", "reissue"]
    transition_reason: str = Field(min_length=1)
    transition_reason_code: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    requested_at: AwareDatetime


class NoticeNode(CompositeModel):
    position: int = Field(ge=0, le=3)
    role: Literal["O", "O_rr", "C", "C_rr"]
    document_id: Identifier
    artifact_sha256: Digest
    tenant_id: Identifier
    report_job_id: Identifier
    snapshot_id: Identifier
    report_revision_id: Identifier
    snapshot_hash: Digest
    economic_generation: Side
    document_response: dict[str, Any]
    document_response_digest: Digest


class NoticeEdge(CompositeModel):
    position: int = Field(ge=0, le=2)
    relationship_id: Identifier
    source_document_id: Identifier
    target_document_id: Identifier
    transition_type: Literal["correct"]
    semantic_role: Literal["TECHNICAL_RERENDER", "ECONOMIC_CORRECTION"]
    source_generation: Side
    target_generation: Side
    acknowledgement: Acknowledgement


class ArchivePath(CompositeModel):
    nodes: list[NoticeNode] = Field(min_length=4, max_length=4)
    edges: list[NoticeEdge] = Field(min_length=3, max_length=3)


class Obligation(CompositeModel):
    status: Literal["CAPTURED_INTERNAL", "UNAVAILABLE", "UNKNOWN", "NOT_APPLICABLE"]
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")
    evidence_refs: list[Annotated[str, Field(min_length=1, max_length=4096)]] = Field(max_length=32)


class CompositeNoticeContent(CompositeModel):
    contract_version: Literal["composite_review.v9"]
    comparison_profile: Literal["RETAINED_SAME_SCOPE_CORRECTION_NOTICE_V1"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    notice_completeness: Literal["PARTIAL"]
    tenant_id: Identifier
    generations: Generations
    archive_path: ArchivePath
    obligations: dict[str, Obligation]
    pair_index: list[PairIndexItem] = Field(min_length=1, max_length=10000)
    pair_fingerprint: Digest
    manifest_digest: Digest
    notice_facts: dict[str, list[dict[str, Any]]]
    tables: list[NoticeTable] = Field(min_length=32, max_length=32)
