from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts.render_package import RenderPackage


class RenderContentValidationError(ValueError):
    pass


class _RenderContentModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    def as_report_data(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class PortfolioReviewRenderContent(_RenderContentModel):
    client_name: str
    portfolio_name: str
    as_of_date: str
    currency: str
    total_value: str
    summary_paragraph: str
    review_observations: list[Any] = Field(min_length=1)


class ProofPackRenderContent(_RenderContentModel):
    title: str
    portfolio_id: str
    proof_pack_id: str
    state: str
    decision_summary: dict[str, Any]
    supportability: dict[str, Any]
    sections: list[Any]
    source_contract_version: str | None = None
    source_hashes: dict[str, Any] = Field(default_factory=dict)
    source_lineage: list[Any] = Field(default_factory=list)
    content_hash: str
    proof_pack_content_hash: str
    client_publication_authority_granted: bool = False

    @model_validator(mode="after")
    def _validate_idea_evidence_boundary(self) -> "ProofPackRenderContent":
        if self.source_contract_version != "lotus_idea_evidence_pack_report_input.v1":
            return self
        if self.client_publication_authority_granted:
            raise ValueError("idea evidence proof-pack rendering cannot grant client publication")
        _require_evidence_lineage(self.source_lineage)
        _require_evidence_digest(self.source_hashes)
        return self


class OutcomeReviewRenderContent(_RenderContentModel):
    title: str
    portfolio_id: str
    outcome_review_id: str
    state: str
    overall_outcome: str
    dimensions: list[Any]
    content_hash: str


class RebalanceWaveRenderContent(_RenderContentModel):
    title: str
    wave_id: str
    wave_state: str
    trigger_type: str
    aggregate_metrics: dict[str, Any]
    supportability: dict[str, Any]
    proof_pack_posture: dict[str, Any]
    items: list[Any]
    content_hash: str
    wave_content_hash: str


ContentModel = TypeVar("ContentModel", bound=_RenderContentModel)


def parse_portfolio_review_content(render_package: RenderPackage) -> PortfolioReviewRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="portfolio_review.v1",
        model=PortfolioReviewRenderContent,
    )


def parse_proof_pack_content(render_package: RenderPackage) -> ProofPackRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_proof_pack_report_input.v1",
        model=ProofPackRenderContent,
    )


def parse_outcome_review_content(render_package: RenderPackage) -> OutcomeReviewRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_outcome_report_input.v1",
        model=OutcomeReviewRenderContent,
    )


def parse_rebalance_wave_content(render_package: RenderPackage) -> RebalanceWaveRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_wave_report_input.v1",
        model=RebalanceWaveRenderContent,
    )


def _parse_content(
    render_package: RenderPackage,
    *,
    expected_contract_version: str,
    model: type[ContentModel],
) -> ContentModel:
    if render_package.report_data_contract_version != expected_contract_version:
        raise RenderContentValidationError(
            "unsupported report_data_contract_version for render content adapter"
        )
    try:
        return model.model_validate(render_package.report_data)
    except ValidationError as exc:
        raise RenderContentValidationError(_validation_message(exc)) from exc


def _validation_message(exc: ValidationError) -> str:
    first_error = exc.errors(include_input=False)[0]
    loc = ".".join(str(part) for part in first_error.get("loc", ()))
    error_type = str(first_error.get("type", ""))
    if error_type == "missing":
        return f"missing required report_data field: {loc}"
    if error_type == "list_type":
        return f"{loc} must be a list"
    message = str(first_error.get("msg", "invalid value"))
    if loc == "review_observations" and "at least 1 item" in message:
        return "review_observations must be a non-empty list"
    if error_type == "value_error" and message:
        return message.removeprefix("Value error, ")
    return f"invalid report_data field: {loc}"


#: A source digest: `<algorithm>:<value>`, both halves non-blank.
#:
#: This is **render's floor, not the producer's guarantee**, and the distinction was
#: got wrong once already. An earlier version of this comment said the shape was read
#: from the producer's golden sample. It was not: `sha256:idea-evidence-content` lives
#: in a lotus-idea OpenAPI example and two fixture generators -- a documentation
#: placeholder that lotus-idea's own strict evidence families would themselves reject.
#:
#: What lotus-idea actually enforces on this field is `_require_text`: non-empty after
#: strip. `"x"` passes. Four sibling runtime-evidence families in that same repository
#: enforce `^sha256:[0-9a-f]{64}$`, and this field does not -- an unjustified difference
#: that happens to sit on a cross-repo boundary.
#:
#: So render is deliberately **stricter than its producer**, and knowingly: a colonless
#: digest that lotus-idea permits itself to emit is refused here. That is the accepted
#: position, agreed with the lotus-idea owner, because it rejects the null, blank and
#: empty-mapping cases that reached this boundary without asserting a guarantee nobody
#: makes. Tightening to 64-hex would be right about the intent and wrong about today's
#: producer, and the failure would land on this repository rather than the one that
#: caused it.
#:
#: Tighten only when lotus-idea's AI-governance evidence lineage enforces what its four
#: siblings already do, and its owner supplies the revision.
_EVIDENCE_PACKET_KEY = "idea_evidence_packet"
_REQUIRED_LINEAGE_TEXT_FIELDS = ("source_id", "source_system", "source_type")


def _digest_reason(value: object, *, field: str) -> str | None:
    """Why this value is not a usable digest, or None when it is."""

    if not isinstance(value, str):
        return f"{field} must be a string digest reference, got {type(value).__name__}"
    algorithm, separator, digest = value.partition(":")
    if not separator:
        return f"{field} must be an <algorithm>:<value> digest reference, got {value!r}"
    if not algorithm.strip() or not digest.strip():
        return f"{field} digest reference has a blank algorithm or value: {value!r}"
    return None


def _require_evidence_digest(source_hashes: Mapping[str, object]) -> None:
    """The evidence digest must be present *and* be a digest.

    Presence was the whole check before. A pack carrying
    `{"idea_evidence_packet": None}` was admitted, and the caller learned the hash
    was missing by reading `None` in a rendered provenance table rather than by
    being refused -- after a render slot had been spent.
    """

    if _EVIDENCE_PACKET_KEY not in source_hashes:
        raise ValueError("idea evidence proof-pack rendering requires an idea_evidence_packet hash")
    reason = _digest_reason(source_hashes[_EVIDENCE_PACKET_KEY], field=_EVIDENCE_PACKET_KEY)
    if reason is not None:
        raise ValueError(f"idea evidence proof-pack rendering rejected: {reason}")


def _require_evidence_lineage(source_lineage: Sequence[object]) -> None:
    """Every lineage entry must identify a source, not merely occupy a slot.

    `[None]`, `[""]` and `[{}]` all satisfied a non-empty check while stating
    nothing about where the evidence came from. A proof pack asserts what it was
    derived from; an entry that names no source cannot support that assertion.
    """

    if not source_lineage:
        raise ValueError("idea evidence proof-pack rendering requires source_lineage")
    for index, entry in enumerate(source_lineage):
        reason = _lineage_entry_reason(entry, index=index)
        if reason is not None:
            raise ValueError(f"idea evidence proof-pack rendering rejected: {reason}")


def _lineage_entry_reason(entry: object, *, index: int) -> str | None:
    """Why one lineage entry does not identify a source, or None when it does."""

    if not isinstance(entry, Mapping):
        return (
            f"source_lineage[{index}] must be a mapping describing one source, "
            f"got {type(entry).__name__}"
        )
    digest_reason = _digest_reason(
        entry.get("content_hash"), field=f"source_lineage[{index}].content_hash"
    )
    if digest_reason is not None:
        return digest_reason
    for field in _REQUIRED_LINEAGE_TEXT_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"source_lineage[{index}].{field} must be a non-blank string"
    return None
