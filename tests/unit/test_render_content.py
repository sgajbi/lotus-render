from __future__ import annotations

import json
from typing import Any

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.services.render_content import (
    RenderContentValidationError,
    parse_outcome_review_content,
    parse_portfolio_review_content,
    parse_proof_pack_content,
    parse_rebalance_wave_content,
)


def _portfolio_package(**overrides: object) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload.update(overrides)
    return RenderPackage.model_validate(payload)


def _package(
    *, report_type: str, contract_version: str, template_id: str, report_data: dict[str, Any]
) -> RenderPackage:
    return RenderPackage.model_validate(
        {
            "render_package_version": "render_package.v1",
            "render_job_id": f"rdr_{report_type}",
            "report_job_id": f"rjob_{report_type}",
            "snapshot_id": f"rsnap_{report_type}",
            "report_type": report_type,
            "report_data_contract_version": contract_version,
            "template_id": template_id,
            "template_version": "v1",
            "locale": "en-SG",
            "brand_variant": "private_banking",
            "output_format": "pdf",
            "render_context": {"timezone": "Asia/Singapore"},
            "report_data": report_data,
            "lineage_refs": [f"rlineage_{report_type}"],
            "disclosure_refs": ["portfolio-review.standard-disclosures.v1"],
            "requested_by": "advisor.sg@example.com",
            "correlation_id": f"corr-{report_type}",
            "trace_id": f"trace-{report_type}",
        }
    )


def test_portfolio_review_content_adapter_validates_required_fields() -> None:
    content = parse_portfolio_review_content(_portfolio_package())

    assert content.client_name == "Alex Tan"
    assert content.as_report_data()["summary_paragraph"]

    invalid = _portfolio_package(report_data={"client_name": "Alex Tan"})
    with pytest.raises(RenderContentValidationError, match="portfolio_name"):
        parse_portfolio_review_content(invalid)


def test_portfolio_review_content_adapter_rejects_empty_observations() -> None:
    package = _portfolio_package()
    invalid = package.model_copy(
        update={"report_data": {**package.report_data, "review_observations": []}}
    )

    with pytest.raises(RenderContentValidationError, match="review_observations"):
        parse_portfolio_review_content(invalid)


def test_portfolio_review_content_adapter_reports_invalid_field_without_payload_echo() -> None:
    package = _portfolio_package()
    invalid = package.model_copy(
        update={"report_data": {**package.report_data, "client_name": ["not", "a", "name"]}}
    )

    with pytest.raises(
        RenderContentValidationError,
        match="invalid report_data field: client_name",
    ):
        parse_portfolio_review_content(invalid)


def test_proof_pack_content_adapter_validates_nested_sections() -> None:
    package = _package(
        report_type="proof_pack",
        contract_version="dpm_proof_pack_report_input.v1",
        template_id="proof-pack",
        report_data={
            "title": "Proof pack",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "proof_pack_id": "dpp_001",
            "state": "READY",
            "decision_summary": {"recommended_action": "APPROVE"},
            "supportability": {"status": "READY"},
            "sections": [{"title": "Mandate", "state": "READY"}],
            "content_hash": "sha256:content",
            "proof_pack_content_hash": "sha256:proof-pack",
        },
    )

    assert parse_proof_pack_content(package).proof_pack_id == "dpp_001"

    invalid = package.model_copy(update={"report_data": {**package.report_data, "sections": "bad"}})
    with pytest.raises(RenderContentValidationError, match="sections must be a list"):
        parse_proof_pack_content(invalid)


def test_proof_pack_content_adapter_enforces_idea_evidence_boundary() -> None:
    report_data = {
        "title": "Idea Evidence Pack - irep_001",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "proof_pack_id": "irep_001",
        "state": "READY_FOR_REPORT_MATERIALIZATION",
        "decision_summary": {"recommended_action": "review_opportunity_evidence"},
        "supportability": {"status": "READY"},
        "sections": [{"title": "Source summary", "state": "READY"}],
        "source_contract_version": "lotus_idea_evidence_pack_report_input.v1",
        "source_hashes": {"idea_evidence_packet": "sha256:idea-evidence-content"},
        "source_lineage": [
            {
                "source_system": "lotus-idea",
                "source_type": "IdeaEvidencePacket",
                "source_id": "ievp_001",
                "content_hash": "sha256:idea-evidence-content",
            }
        ],
        "content_hash": "sha256:idea-evidence-content",
        "proof_pack_content_hash": "sha256:idea-evidence-content",
        "client_publication_authority_granted": False,
    }
    package = _package(
        report_type="proof_pack",
        contract_version="dpm_proof_pack_report_input.v1",
        template_id="proof-pack",
        report_data=report_data,
    )

    content = parse_proof_pack_content(package)

    assert content.source_contract_version == "lotus_idea_evidence_pack_report_input.v1"

    missing_lineage = package.model_copy(
        update={"report_data": {**report_data, "source_lineage": []}}
    )
    with pytest.raises(RenderContentValidationError, match="source_lineage"):
        parse_proof_pack_content(missing_lineage)

    publication_claim = package.model_copy(
        update={"report_data": {**report_data, "client_publication_authority_granted": True}}
    )
    with pytest.raises(RenderContentValidationError, match="client publication"):
        parse_proof_pack_content(publication_claim)


def test_outcome_review_content_adapter_validates_dimensions() -> None:
    package = _package(
        report_type="outcome_review",
        contract_version="dpm_outcome_report_input.v1",
        template_id="outcome-review",
        report_data={
            "title": "Outcome review",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "outcome_review_id": "dor_001",
            "state": "COMPLETE",
            "overall_outcome": "PASS",
            "dimensions": [{"dimension": "risk", "state": "PASS"}],
            "content_hash": "sha256:content",
        },
    )

    assert parse_outcome_review_content(package).outcome_review_id == "dor_001"

    invalid = package.model_copy(
        update={"report_data": {**package.report_data, "dimensions": "bad"}}
    )
    with pytest.raises(RenderContentValidationError, match="dimensions must be a list"):
        parse_outcome_review_content(invalid)


def test_rebalance_wave_content_adapter_validates_items_and_contract_version() -> None:
    package = _package(
        report_type="rebalance_wave",
        contract_version="dpm_wave_report_input.v1",
        template_id="rebalance-wave",
        report_data={
            "title": "Wave",
            "wave_id": "dwv_001",
            "wave_state": "HANDOFF_READY",
            "trigger_type": "DRIFT",
            "aggregate_metrics": {"item_count": 1},
            "supportability": {"supportability_state": "ready"},
            "proof_pack_posture": {"ready_proof_pack_count": 1},
            "items": [{"portfolio_id": "PB_SG_GLOBAL_BAL_001"}],
            "content_hash": "sha256:content",
            "wave_content_hash": "sha256:wave",
        },
    )

    assert parse_rebalance_wave_content(package).wave_id == "dwv_001"

    wrong_contract = package.model_copy(
        update={"report_data_contract_version": "dpm_wave_report_input.v2"}
    )
    with pytest.raises(RenderContentValidationError, match="unsupported"):
        parse_rebalance_wave_content(wrong_contract)


def _idea_evidence_report_data(**overrides: Any) -> dict[str, Any]:
    """A payload that satisfies render's floor -- not a sample of producer output.

    The golden fixture this was modelled on carries `sha256:idea-evidence-content`,
    which turns out to be a lotus-idea OpenAPI placeholder rather than emitted data.
    lotus-idea enforces only non-empty-after-strip on this field today, so real
    output may be weaker than what is built here.

    That does not make these cases wrong -- render is deliberately stricter than its
    producer, agreed with that repository's owner -- but the fixture is evidence
    about *render's* contract, and calling it producer output would be the same
    provenance error the module comment now records.
    """

    report_data: dict[str, Any] = {
        "title": "Idea Evidence Pack - irep_001",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "proof_pack_id": "irep_001",
        "state": "READY_FOR_REPORT_MATERIALIZATION",
        "decision_summary": {"recommended_action": "review_opportunity_evidence"},
        "supportability": {"status": "READY"},
        "sections": [{"title": "Source summary", "state": "READY"}],
        "source_contract_version": "lotus_idea_evidence_pack_report_input.v1",
        "source_hashes": {"idea_evidence_packet": "sha256:idea-evidence-content"},
        "source_lineage": [
            {
                "source_system": "lotus-idea",
                "source_type": "IdeaEvidencePacket",
                "source_id": "ievp_001",
                "content_hash": "sha256:idea-evidence-content",
            }
        ],
        "content_hash": "sha256:idea-evidence-content",
        "proof_pack_content_hash": "sha256:idea-evidence-content",
        "client_publication_authority_granted": False,
    }
    report_data.update(overrides)
    return report_data


def _idea_evidence_package(**overrides: Any) -> Any:
    return _package(
        report_type="proof_pack",
        contract_version="dpm_proof_pack_report_input.v1",
        template_id="proof-pack",
        report_data=_idea_evidence_report_data(**overrides),
    )


@pytest.mark.parametrize(
    ("label", "source_hashes"),
    [
        ("null digest", {"idea_evidence_packet": None}),
        ("blank digest", {"idea_evidence_packet": ""}),
        ("whitespace digest", {"idea_evidence_packet": "   "}),
        ("algorithm with no value", {"idea_evidence_packet": "sha256:"}),
        ("value with no algorithm", {"idea_evidence_packet": ":abc"}),
        ("not a digest reference", {"idea_evidence_packet": "idea-evidence-content"}),
        ("digest is not a string", {"idea_evidence_packet": 12345}),
    ],
)
def test_a_declared_evidence_digest_that_states_nothing_is_refused(
    label: str, source_hashes: dict[str, Any]
) -> None:
    """The guard named the content and tested the container.

    Every case here was **accepted** before: the check was `"idea_evidence_packet"
    not in source_hashes`, so a pack claiming idea-evidence provenance with a null
    or blank digest rendered, and the reader learned the hash was missing by seeing
    `None` in a provenance table rather than by being refused.
    """

    with pytest.raises(RenderContentValidationError, match="idea_evidence_packet"):
        parse_proof_pack_content(_idea_evidence_package(source_hashes=source_hashes))


@pytest.mark.parametrize(
    ("label", "source_lineage"),
    [
        ("null entry", [None]),
        ("blank string entry", [""]),
        ("empty mapping", [{}]),
        (
            "missing source_id",
            [{"source_system": "lotus-idea", "source_type": "T", "content_hash": "sha256:x"}],
        ),
        (
            "blank source_system",
            [
                {
                    "source_system": "  ",
                    "source_type": "T",
                    "source_id": "i",
                    "content_hash": "sha256:x",
                }
            ],
        ),
        (
            "content hash is not a digest",
            [
                {
                    "source_system": "lotus-idea",
                    "source_type": "T",
                    "source_id": "i",
                    "content_hash": "",
                }
            ],
        ),
    ],
)
def test_a_lineage_entry_that_names_no_source_is_refused(
    label: str, source_lineage: list[Any]
) -> None:
    """A proof pack asserts what it was derived from.

    `[None]`, `[""]` and `[{}]` all satisfied the previous non-empty check while
    stating nothing about origin -- an entry that names no source cannot support
    the assertion the document makes.
    """

    with pytest.raises(RenderContentValidationError, match="source_lineage"):
        parse_proof_pack_content(_idea_evidence_package(source_lineage=source_lineage))


def test_the_producers_declared_shape_still_renders() -> None:
    """The discriminating half: this must accept, or the refusals prove nothing.

    A guard that refuses everything passes every refusal test above.
    """

    content = parse_proof_pack_content(_idea_evidence_package())

    assert content.source_hashes["idea_evidence_packet"] == "sha256:idea-evidence-content"
    assert content.source_lineage[0]["source_id"] == "ievp_001"


def test_the_earlier_container_refusals_are_not_weakened() -> None:
    """The previous behaviour must survive the stronger checks.

    Tightening a guard is where its existing cases quietly get lost.
    """

    with pytest.raises(RenderContentValidationError, match="source_lineage"):
        parse_proof_pack_content(_idea_evidence_package(source_lineage=[]))
    with pytest.raises(RenderContentValidationError, match="idea_evidence_packet"):
        parse_proof_pack_content(_idea_evidence_package(source_hashes={}))
    with pytest.raises(RenderContentValidationError, match="client publication"):
        parse_proof_pack_content(_idea_evidence_package(client_publication_authority_granted=True))


@pytest.mark.parametrize(
    "source_contract_version", [None, "dpm_proof_pack_report_input.v1", "some_other_contract.v2"]
)
def test_non_idea_contracts_are_untouched_by_the_evidence_boundary(
    source_contract_version: str | None,
) -> None:
    """The assignment requires legitimate non-Idea render contracts to be preserved.

    A pack on any other contract must not acquire idea-evidence requirements: it
    carries no `idea_evidence_packet` and may carry no lineage at all, and that is
    correct rather than a gap.
    """

    package = _idea_evidence_package(
        source_contract_version=source_contract_version,
        source_hashes={"mandate": "sha256:mandate"},
        source_lineage=[],
    )

    content = parse_proof_pack_content(package)

    assert content.source_contract_version == source_contract_version


@pytest.mark.parametrize(
    ("value", "producer_permits", "render_accepts"),
    [
        ("sha256:" + "a" * 64, True, True),
        ("sha256:idea-evidence-content", True, True),
        ("x", True, False),
        ("abc123", True, False),
        ("", False, False),
        ("   ", False, False),
    ],
)
def test_the_gap_between_what_the_producer_permits_and_render_accepts_is_stated(
    value: str, producer_permits: bool, render_accepts: bool
) -> None:
    """Render is deliberately stricter than lotus-idea, and by exactly this much.

    lotus-idea validates this field with `_require_text` -- non-empty after strip --
    while four sibling evidence families in that same repository enforce
    `^sha256:[0-9a-f]{64}$`. Render sits between the two: `<algorithm>:<value>`.

    So there are values lotus-idea permits itself to emit that render refuses, and
    that is an accepted position rather than an oversight, agreed with that
    repository's owner. It is pinned here because an accepted gap that lives only in
    a comment becomes an accident the first time someone widens the guard to make a
    refusal go away -- and because when lotus-idea tightens to match its siblings,
    this table is what says which rows should change.
    """

    from app.services.render_content import _digest_reason

    assert bool(value.strip()) is producer_permits, (
        "this row's claim about what lotus-idea permits no longer matches "
        "`_require_text` semantics; re-read the producer before editing the table"
    )
    assert (_digest_reason(value, field="idea_evidence_packet") is None) is render_accepts
