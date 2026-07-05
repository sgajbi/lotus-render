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
