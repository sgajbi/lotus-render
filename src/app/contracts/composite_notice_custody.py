"""Notice-owned capture binding and exact immutable original source anchors."""

from typing import Any, Literal

from app.contracts.composite_notice import BareDigest, Identifier, SelectionTuple
from app.contracts.composite_review import CompositeModel
from app.contracts.composite_selection import Digest


class SourceGenerationCustody(SelectionTuple):
    source_document_id: Identifier
    source_identity: dict[str, Any]


class SourceGenerationPair(CompositeModel):
    before: SourceGenerationCustody
    after: SourceGenerationCustody


class NoticeCustodyIdentity(CompositeModel):
    contract_version: Literal["composite_review.v9"]
    comparison_profile: Literal["RETAINED_SAME_SCOPE_CORRECTION_NOTICE_V1"]
    qualification: Literal["EXPLICIT_RETAINED_CALCULATED_REPLAY"]
    publication_state: Literal["NOT_ATTESTED"]
    notice_completeness: Literal["PARTIAL"]
    pair_fingerprint: Digest
    manifest_digest: Digest
    generations: SourceGenerationPair
    series_digest: BareDigest
    source_revision_digest: BareDigest
    factual_content_digest: BareDigest
