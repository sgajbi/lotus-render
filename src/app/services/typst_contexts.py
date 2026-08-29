"""Template-context builders: one governed context per report family.

Each builder assembles the full substitution context for its template from a
validated render package. Section selection for the portfolio review lives
here too, since the requested sections decide which fragments are emitted.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contracts.render_package import RenderPackage
from app.services.render_content import (
    parse_outcome_review_content,
    parse_portfolio_review_content,
    parse_proof_pack_content,
    parse_rebalance_wave_content,
)
from app.services.typst_fragments import (
    render_advisor_memo_fact_rows,
    render_advisor_memo_section_blocks,
    render_advisory_disclosure_blocks,
    render_advisory_narrative_blocks,
    render_key_value_rows,
    render_outcome_dimension_rows,
    render_proof_pack_section_rows,
    render_reviewed_advisory_fact_rows,
    render_source_lineage_rows,
    render_wave_event_rows,
    render_wave_item_rows,
)
from app.services.typst_tables import (
    render_allocation_breakdown_rows,
    render_allocation_chart_section,
    render_dense_position_rows,
    render_dense_transaction_rows,
    render_holding_bar_rows,
    render_holding_rows,
    render_observation_notes,
    render_performance_bar_rows,
    render_performance_chart_rows,
    render_performance_chart_section,
    render_performance_detail_rows,
    render_performance_period_rows,
    render_performance_summary_table,
    supplemental_allocation_view,
)
from app.services.typst_values import (
    escape_typst_string,
    mapping,
    string_list,
)

PORTFOLIO_REVIEW_SECTION_CALLS = {
    "cover": "cover-page()",
    "contents": "contents-page()",
    "overview": "scope-page()",
    "scope": "scope-page()",
    "performance": "performance-page()",
    "allocation": "allocation-page()",
    "positions": "observations-page()",
    "holdings": "observations-page()",
    "transactions": "transactions-page()",
    "advisory_narrative": "reviewed-advisory-narrative-page()",
    "advisor_memo": "advisor-proposal-memo-page()",
    "appendix": "appendix-page()",
}
DEFAULT_PORTFOLIO_REVIEW_SECTIONS = (
    "cover",
    "contents",
    "overview",
    "performance",
    "allocation",
    "positions",
    "transactions",
    "appendix",
)
DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_NARRATIVE = (
    "cover",
    "contents",
    "overview",
    "performance",
    "allocation",
    "positions",
    "transactions",
    "advisory_narrative",
    "appendix",
)
DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_MEMO = (
    "cover",
    "contents",
    "overview",
    "performance",
    "allocation",
    "positions",
    "transactions",
    "advisor_memo",
    "appendix",
)


def build_portfolio_review_context(render_package: RenderPackage) -> dict[str, str]:
    report_data = parse_portfolio_review_content(render_package).as_report_data()
    render_context = render_package.render_context

    observations = report_data["review_observations"]

    mandate = mapping(report_data.get("mandate"))
    portfolio_metrics = mapping(report_data.get("portfolio_metrics"))
    allocation_summary = mapping(report_data.get("allocation_summary"))
    allocation_breakdowns = mapping(report_data.get("allocation_breakdowns"))
    performance_highlight = mapping(report_data.get("performance_highlight"))
    risk_summary = mapping(report_data.get("risk_summary"))
    governance_summary = mapping(report_data.get("governance_summary"))
    reviewed_advisory_narrative = mapping(report_data.get("reviewed_advisory_narrative"))
    advisor_proposal_memo = mapping(report_data.get("advisor_proposal_memo"))
    include_reviewed_advisory_narrative = reviewed_advisory_narrative.get("status") == "included"
    include_advisor_proposal_memo = advisor_proposal_memo.get("status") == "included"
    supplemental_allocation_title, supplemental_allocation_rows = supplemental_allocation_view(
        allocation_breakdowns
    )

    return {
        "REPORT_SECTIONS": render_report_sections(
            render_context.get("sections"),
            include_advisory_narrative=include_reviewed_advisory_narrative,
            include_advisor_memo=include_advisor_proposal_memo,
        ),
        "OPTIONAL_ADVISORY_IMPORT": (
            '#import "_advisory.typ": reviewed-advisory-narrative-page, advisor-proposal-memo-page'
            if include_reviewed_advisory_narrative or include_advisor_proposal_memo
            else ""
        ),
        "CLIENT_NAME": escape_typst_string(str(report_data["client_name"])),
        "PORTFOLIO_NAME": escape_typst_string(str(report_data["portfolio_name"])),
        "AS_OF_DATE": escape_typst_string(str(report_data["as_of_date"])),
        "CURRENCY": escape_typst_string(str(report_data["currency"])),
        "TOTAL_VALUE": escape_typst_string(str(report_data["total_value"])),
        "SUMMARY_PARAGRAPH": escape_typst_string(str(report_data["summary_paragraph"])),
        "REVIEW_PERIOD_LABEL": escape_typst_string(
            str(report_data.get("review_period_label", "YTD"))
        ),
        "OBJECTIVE": escape_typst_string(
            str(mandate.get("objective", "Objective not available in the governed snapshot."))
        ),
        "RISK_EXPOSURE": escape_typst_string(str(mandate.get("risk_exposure", "not_available"))),
        "BOOKING_CENTER": escape_typst_string(
            str(mandate.get("booking_center_code", "not_available"))
        ),
        "ADVISOR_ID": escape_typst_string(str(mandate.get("advisor_id", "not_available"))),
        "INVESTED_VALUE": escape_typst_string(
            str(portfolio_metrics.get("invested_value", "Not available"))
        ),
        "CASH_BALANCE": escape_typst_string(
            str(portfolio_metrics.get("cash_balance", "Not available"))
        ),
        "CASH_WEIGHT_PCT": escape_typst_string(
            str(portfolio_metrics.get("cash_weight_pct", "Not available"))
        ),
        "ALLOCATION_LARGEST_NAME": escape_typst_string(
            str(allocation_summary.get("largest_asset_class_name", "Not available"))
        ),
        "ALLOCATION_LARGEST_WEIGHT": escape_typst_string(
            str(allocation_summary.get("largest_asset_class_weight_pct", "Not available"))
        ),
        "ALLOCATION_LARGEST_VALUE": escape_typst_string(
            str(allocation_summary.get("largest_asset_class_market_value", "Not available"))
        ),
        "ALLOCATION_POSITION_COUNT": escape_typst_string(
            str(allocation_summary.get("largest_asset_class_position_count", "Not available"))
        ),
        "TOP_CONTRIBUTOR_NAME": escape_typst_string(
            str(
                performance_highlight.get(
                    "largest_positive_contributor_name",
                    "Not available",
                )
            )
        ),
        "TOP_CONTRIBUTOR_VALUE": escape_typst_string(
            str(
                performance_highlight.get(
                    "largest_positive_contribution_pct",
                    "Not available",
                )
            )
        ),
        "BENCHMARK_STATUS": escape_typst_string(
            str(performance_highlight.get("benchmark_comparison_status", "not_available"))
        ),
        "RISK_VOLATILITY": escape_typst_string(
            str(risk_summary.get("volatility_pct", "Not available"))
        ),
        "RISK_BETA": escape_typst_string(str(risk_summary.get("beta", "Not available"))),
        "RISK_TRACKING_ERROR": escape_typst_string(
            str(risk_summary.get("tracking_error_pct", "Not available"))
        ),
        "RISK_INFORMATION_RATIO": escape_typst_string(
            str(risk_summary.get("information_ratio", "Not available"))
        ),
        "RISK_VAR": escape_typst_string(
            str(risk_summary.get("value_at_risk_pct", "Not available"))
        ),
        "OBSERVATION_NOTES": render_observation_notes(observations),
        "PERFORMANCE_PERIOD_ROWS": render_performance_period_rows(
            report_data.get("performance_periods")
        ),
        "PERFORMANCE_SUMMARY_TABLE": render_performance_summary_table(
            report_data.get("performance_summary_table")
        ),
        "PERFORMANCE_MONTHLY_CHART_ROWS": render_performance_chart_rows(
            report_data.get("performance_monthly_history"),
            two_column=True,
        ),
        "PERFORMANCE_ANNUAL_CHART_ROWS": render_performance_chart_rows(
            report_data.get("performance_annual_history")
        ),
        "PERFORMANCE_MONTHLY_TABLE_ROWS": render_performance_detail_rows(
            report_data.get("performance_monthly_history")
        ),
        "PERFORMANCE_BAR_ROWS": render_performance_bar_rows(report_data.get("performance_periods")),
        "PERFORMANCE_12M_CHART_SECTION": render_performance_chart_section(report_data),
        "HOLDING_ROWS": render_holding_rows(report_data.get("top_holdings")),
        "HOLDING_BAR_ROWS": render_holding_bar_rows(report_data.get("top_holdings")),
        "ASSET_CLASS_ROWS": render_allocation_breakdown_rows(
            allocation_breakdowns.get("by_asset_class") or report_data.get("top_holdings")
        ),
        "ALLOCATION_DONUT_CHART_SECTION": render_allocation_chart_section(report_data),
        "SUPPLEMENTAL_ALLOCATION_TITLE": escape_typst_string(supplemental_allocation_title),
        "SUPPLEMENTAL_ALLOCATION_ROWS": supplemental_allocation_rows,
        "DENSE_POSITION_ROWS": render_dense_position_rows(
            report_data.get("positions") or report_data.get("top_holdings")
        ),
        "TRANSACTION_PERIOD_LABEL": escape_typst_string(
            str(report_data.get("transaction_period_label", "Transaction activity"))
        ),
        "DENSE_TRANSACTION_ROWS": render_dense_transaction_rows(report_data.get("transactions")),
        "SOURCE_SERVICES": escape_typst_string(
            ", ".join(string_list(governance_summary.get("source_services"))) or "Not available"
        ),
        "COMPLETENESS_STATUS": escape_typst_string(
            str(governance_summary.get("completeness_status", "unknown"))
        ),
        "DATA_QUALITY_STATUS": escape_typst_string(
            str(governance_summary.get("data_quality_status", "unknown"))
        ),
        "READINESS_STATUS": escape_typst_string(
            str(governance_summary.get("readiness_status", "unknown"))
        ),
        "REVIEWED_ADVISORY_FACT_ROWS": render_reviewed_advisory_fact_rows(
            reviewed_advisory_narrative
        ),
        "REVIEWED_ADVISORY_NARRATIVE_BLOCKS": render_advisory_narrative_blocks(
            reviewed_advisory_narrative.get("sections")
        ),
        "REVIEWED_ADVISORY_DISCLOSURE_BLOCKS": render_advisory_disclosure_blocks(
            reviewed_advisory_narrative.get("disclosures")
        ),
        "ADVISOR_MEMO_FACT_ROWS": render_advisor_memo_fact_rows(advisor_proposal_memo),
        "ADVISOR_MEMO_SECTION_BLOCKS": render_advisor_memo_section_blocks(
            advisor_proposal_memo.get("sections")
        ),
        "ADVISOR_MEMO_DISCLOSURE_BLOCKS": render_advisory_disclosure_blocks(
            advisor_proposal_memo.get("disclosures")
        ),
        "RENDER_JOB_ID": escape_typst_string(render_package.render_job_id),
        "TEMPLATE_ID": escape_typst_string(render_package.template_id),
        "TEMPLATE_VERSION": escape_typst_string(render_package.template_version),
        "REQUESTED_BY": escape_typst_string(str(render_package.requested_by)),
        "TIMEZONE": escape_typst_string(str(render_context.get("timezone", "unknown"))),
    }


def build_proof_pack_context(render_package: RenderPackage) -> dict[str, str]:
    report_data = parse_proof_pack_content(render_package).as_report_data()
    render_context = render_package.render_context
    sections = report_data["sections"]

    decision_summary = mapping(report_data.get("decision_summary"))
    supportability = mapping(report_data.get("supportability"))
    source_hashes = mapping(report_data.get("source_hashes"))
    source_contract_version = str(report_data.get("source_contract_version", "not_available"))
    return {
        "TITLE": escape_typst_string(str(report_data["title"])),
        "PORTFOLIO_ID": escape_typst_string(str(report_data["portfolio_id"])),
        "PROOF_PACK_ID": escape_typst_string(str(report_data["proof_pack_id"])),
        "MANDATE_ID": escape_typst_string(str(report_data.get("mandate_id", "not_available"))),
        "AS_OF_DATE": escape_typst_string(str(report_data.get("as_of_date", "not_available"))),
        "STATE": escape_typst_string(str(report_data["state"])),
        "DECISION_ACTION": escape_typst_string(
            str(decision_summary.get("recommended_action", "not_available"))
        ),
        "DECISION_RATIONALE": escape_typst_string(
            str(decision_summary.get("rationale", "No decision rationale supplied."))
        ),
        "SUPPORTABILITY_STATUS": escape_typst_string(
            str(supportability.get("status", supportability.get("state", "not_available")))
        ),
        "SUPPORTABILITY_REASONS": escape_typst_string(
            ", ".join(string_list(supportability.get("reason_codes"))) or "none"
        ),
        "SECTION_ROWS": render_proof_pack_section_rows(sections),
        "SOURCE_CONTRACT_VERSION": escape_typst_string(source_contract_version),
        "CLIENT_PUBLICATION_AUTHORITY": escape_typst_string(
            str(bool(report_data.get("client_publication_authority_granted"))).lower()
        ),
        "SOURCE_LINEAGE_ROWS": render_source_lineage_rows(report_data.get("source_lineage")),
        "SOURCE_HASH_ROWS": render_key_value_rows(source_hashes),
        "CONTENT_HASH": escape_typst_string(str(report_data["content_hash"])),
        "PROOF_PACK_CONTENT_HASH": escape_typst_string(str(report_data["proof_pack_content_hash"])),
        "REDACTION_POLICY": escape_typst_string(
            str(report_data.get("redaction_policy", "NO_RAW_PAYLOADS"))
        ),
        "RENDER_JOB_ID": escape_typst_string(render_package.render_job_id),
        "TEMPLATE_ID": escape_typst_string(render_package.template_id),
        "TEMPLATE_VERSION": escape_typst_string(render_package.template_version),
        "REQUESTED_BY": escape_typst_string(str(render_package.requested_by)),
        "TIMEZONE": escape_typst_string(str(render_context.get("timezone", "unknown"))),
    }


def build_outcome_review_context(render_package: RenderPackage) -> dict[str, str]:
    report_data = parse_outcome_review_content(render_package).as_report_data()
    render_context = render_package.render_context
    dimensions = report_data["dimensions"]
    source_hashes = mapping(report_data.get("source_hashes"))
    section_hashes = mapping(report_data.get("section_hashes"))
    return {
        "TITLE": escape_typst_string(str(report_data["title"])),
        "PORTFOLIO_ID": escape_typst_string(str(report_data["portfolio_id"])),
        "OUTCOME_REVIEW_ID": escape_typst_string(str(report_data["outcome_review_id"])),
        "PROOF_PACK_ID": escape_typst_string(str(report_data.get("proof_pack_id", ""))),
        "REBALANCE_RUN_ID": escape_typst_string(
            str(report_data.get("rebalance_run_id", "not_available"))
        ),
        "WAVE_ID": escape_typst_string(str(report_data.get("wave_id", "not_available"))),
        "STATE": escape_typst_string(str(report_data["state"])),
        "OVERALL_OUTCOME": escape_typst_string(str(report_data["overall_outcome"])),
        "REVIEW_WINDOW_START": escape_typst_string(
            str(report_data.get("review_window_start", "not_available"))
        ),
        "REVIEW_WINDOW_END": escape_typst_string(
            str(report_data.get("review_window_end", "not_available"))
        ),
        "DIMENSION_ROWS": render_outcome_dimension_rows(dimensions),
        "SOURCE_SERVICES": escape_typst_string(
            ", ".join(string_list(report_data.get("source_services"))) or "lotus-manage"
        ),
        "SOURCE_HASH_ROWS": render_key_value_rows(source_hashes),
        "SECTION_HASH_ROWS": render_key_value_rows(section_hashes),
        "CONTENT_HASH": escape_typst_string(str(report_data["content_hash"])),
        "OUTCOME_REVIEW_CONTENT_HASH": escape_typst_string(
            str(report_data.get("outcome_review_content_hash", "not_available"))
        ),
        "REDACTION_POLICY": escape_typst_string(
            str(report_data.get("redaction_policy", "NO_RAW_PAYLOADS"))
        ),
        "RENDER_JOB_ID": escape_typst_string(render_package.render_job_id),
        "TEMPLATE_ID": escape_typst_string(render_package.template_id),
        "TEMPLATE_VERSION": escape_typst_string(render_package.template_version),
        "REQUESTED_BY": escape_typst_string(str(render_package.requested_by)),
        "TIMEZONE": escape_typst_string(str(render_context.get("timezone", "unknown"))),
    }


def build_wave_context(render_package: RenderPackage) -> dict[str, str]:
    report_data = parse_rebalance_wave_content(render_package).as_report_data()
    render_context = render_package.render_context
    items = report_data["items"]
    aggregate_metrics = mapping(report_data.get("aggregate_metrics"))
    supportability = mapping(report_data.get("supportability"))
    proof_pack_posture = mapping(report_data.get("proof_pack_posture"))
    return {
        "TITLE": escape_typst_string(str(report_data["title"])),
        "WAVE_ID": escape_typst_string(str(report_data["wave_id"])),
        "WAVE_STATE": escape_typst_string(str(report_data["wave_state"])),
        "TRIGGER_TYPE": escape_typst_string(str(report_data["trigger_type"])),
        "TRIGGER_ID": escape_typst_string(str(report_data.get("trigger_id", ""))),
        "TRIGGER_RATIONALE": escape_typst_string(
            str(report_data.get("trigger_rationale", "No trigger rationale supplied."))
        ),
        "AS_OF_DATE": escape_typst_string(str(report_data.get("as_of_date", "not_available"))),
        "ITEM_COUNT": escape_typst_string(
            str(aggregate_metrics.get("item_count", "not_available"))
        ),
        "READY_ITEM_COUNT": escape_typst_string(
            str(aggregate_metrics.get("ready_item_count", "not_available"))
        ),
        "BLOCKED_ITEM_COUNT": escape_typst_string(
            str(aggregate_metrics.get("blocked_item_count", "not_available"))
        ),
        "SUPPORTABILITY_STATUS": escape_typst_string(
            str(
                supportability.get(
                    "supportability_state",
                    supportability.get("status", "not_available"),
                )
            )
        ),
        "SUPPORTABILITY_REASON": escape_typst_string(
            str(supportability.get("reason", "not_available"))
        ),
        "PROOF_PACK_READY_COUNT": escape_typst_string(
            str(proof_pack_posture.get("ready_proof_pack_count", "not_available"))
        ),
        "PROOF_PACK_DEGRADED_COUNT": escape_typst_string(
            str(proof_pack_posture.get("degraded_proof_pack_count", "not_available"))
        ),
        "HANDOFF_COUNT": escape_typst_string(str(report_data.get("handoff_count", 0))),
        "EXTERNAL_EXECUTION": escape_typst_string(
            str(bool(report_data.get("external_execution_claimed"))).lower()
        ),
        "ITEM_ROWS": render_wave_item_rows(items),
        "EVENT_ROWS": render_wave_event_rows(report_data.get("events")),
        "CONTENT_HASH": escape_typst_string(str(report_data["content_hash"])),
        "WAVE_CONTENT_HASH": escape_typst_string(str(report_data["wave_content_hash"])),
        "REDACTION_POLICY": escape_typst_string(
            str(report_data.get("redaction_policy", "NO_RAW_PAYLOADS"))
        ),
        "RENDER_JOB_ID": escape_typst_string(render_package.render_job_id),
        "TEMPLATE_ID": escape_typst_string(render_package.template_id),
        "TEMPLATE_VERSION": escape_typst_string(render_package.template_version),
        "REQUESTED_BY": escape_typst_string(str(render_package.requested_by)),
        "TIMEZONE": escape_typst_string(str(render_context.get("timezone", "unknown"))),
    }


def render_report_sections(
    requested_sections: object,
    *,
    include_advisory_narrative: bool = False,
    include_advisor_memo: bool = False,
) -> str:
    section_keys = requested_section_keys(
        requested_sections,
        include_advisory_narrative=include_advisory_narrative,
        include_advisor_memo=include_advisor_memo,
    )
    rendered = [f"#{PORTFOLIO_REVIEW_SECTION_CALLS[key]}" for key in section_keys]
    return "\n#pagebreak()\n".join(rendered)


def requested_section_keys(
    requested_sections: object,
    *,
    include_advisory_narrative: bool = False,
    include_advisor_memo: bool = False,
) -> list[str]:
    if not isinstance(requested_sections, Sequence) or isinstance(
        requested_sections, (str, bytes, bytearray)
    ):
        return _default_section_keys(
            include_advisory_narrative=include_advisory_narrative,
            include_advisor_memo=include_advisor_memo,
        )

    allowed = set(PORTFOLIO_REVIEW_SECTION_CALLS) - _excluded_section_keys(
        include_advisory_narrative=include_advisory_narrative,
        include_advisor_memo=include_advisor_memo,
    )
    normalized: list[str] = []
    seen: set[str] = set()
    for item in requested_sections:
        key = _normalized_section_key(item)
        if key not in allowed or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    if normalized:
        return normalized
    return _default_section_keys(
        include_advisory_narrative=include_advisory_narrative,
        include_advisor_memo=include_advisor_memo,
    )


_SECTION_KEY_ALIASES = {
    "detailed-positions": "positions",
    "holdings-appendix": "positions",
    "asset-allocation": "allocation",
    "scope-of-analysis": "overview",
    "performance-review": "performance",
    "transaction-list": "transactions",
    "additional-information": "appendix",
    "advisor-narrative": "advisory-narrative",
    "advisory": "advisory-narrative",
    "reviewed-advisory": "advisory-narrative",
    "reviewed-advisory-narrative": "advisory-narrative",
    "advisor-proposal-memo": "advisor-memo",
    "proposal-memo": "advisor-memo",
    "memo": "advisor-memo",
}


def _normalized_section_key(item: object) -> str:
    key = str(item).strip().lower().replace("_", "-")
    return _SECTION_KEY_ALIASES.get(key, key).replace("-", "_")


def _excluded_section_keys(
    *, include_advisory_narrative: bool, include_advisor_memo: bool
) -> set[str]:
    excluded: set[str] = set()
    if not include_advisory_narrative:
        excluded.add("advisory_narrative")
    if not include_advisor_memo:
        excluded.add("advisor_memo")
    return excluded


def _default_section_keys(
    *, include_advisory_narrative: bool, include_advisor_memo: bool
) -> list[str]:
    if include_advisor_memo:
        return list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_MEMO)
    if include_advisory_narrative:
        return list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_NARRATIVE)
    return list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS)
