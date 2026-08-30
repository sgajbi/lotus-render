"""Template-context builders: one governed context per report family.

Each builder assembles the full substitution context for its template from a
validated render package. Section selection for the portfolio review lives
here too, since the requested sections decide which fragments are emitted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.contracts.render_package import RenderPackage
from app.services.absence import supplied_text
from app.services.appendix_glossary import applicable_glossary
from app.services.date_format import format_date, format_dates_in_text
from app.services.number_format import group_digits
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
    render_appendix_glossary_groups,
    render_holding_bar_rows,
    render_holding_rows,
    render_observation_notes,
    render_performance_chart_rows,
    render_performance_chart_section,
    render_performance_detail_rows,
    render_performance_period_rows,
    render_performance_summary_table,
    render_position_table,
    render_transaction_table,
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


def _reporting_period_label(report_data: Mapping[str, object]) -> str:
    """How the document describes the span it covers, from what it was given.

    A package carries an as-of date and usually a period label ("YTD", "Q1 2026"); it
    does not carry a period start. Naming the label and the as-of date says exactly what
    is known. Where no label arrives, the as-of date alone is still true.
    """
    as_of = format_date(report_data.get("as_of_date", ""))
    label = str(report_data.get("review_period_label", "")).strip()
    if not as_of:
        return label
    return f"{label} to {as_of}" if label else f"As of {as_of}"


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

    reporting_period_label = _reporting_period_label(report_data)

    position_widths, position_header, position_rows = render_position_table(
        report_data.get("positions") or report_data.get("top_holdings")
    )
    transaction_widths, transaction_header, transaction_rows = render_transaction_table(
        report_data.get("transactions")
    )

    return {
        "REPORT_SECTIONS": render_report_sections(
            render_context.get("sections"),
            include_advisory_narrative=include_reviewed_advisory_narrative,
            include_advisor_memo=include_advisor_proposal_memo,
            # The appendix explains the terms this document uses. A report that uses
            # none of them would otherwise ship a page saying so.
            include_appendix=bool(applicable_glossary(report_data)),
        ),
        "OPTIONAL_ADVISORY_IMPORT": (
            '#import "_advisory.typ": reviewed-advisory-narrative-page, advisor-proposal-memo-page'
            if include_reviewed_advisory_narrative or include_advisor_proposal_memo
            else ""
        ),
        "CLIENT_NAME": escape_typst_string(str(report_data["client_name"])),
        "PORTFOLIO_NAME": escape_typst_string(str(report_data["portfolio_name"])),
        "AS_OF_DATE": escape_typst_string(format_date(report_data["as_of_date"])),
        # No render package carries a period start, so the document names the period it
        # was given rather than a date nobody supplied. "1 Jan 2026" used to be a literal
        # in the header of every page (#150).
        "REPORTING_PERIOD_LABEL": escape_typst_string(reporting_period_label),
        "REVIEW_PERIOD_RANGE": escape_typst_string(reporting_period_label),
        "CURRENCY": escape_typst_string(str(report_data["currency"])),
        "TOTAL_VALUE": escape_typst_string(group_digits(report_data["total_value"])),
        "SUMMARY_PARAGRAPH": escape_typst_string(str(report_data["summary_paragraph"])),
        "REVIEW_PERIOD_LABEL": escape_typst_string(
            str(report_data.get("review_period_label", "YTD"))
        ),
        "OBJECTIVE": escape_typst_string(
            str(mandate.get("objective", "Objective not available in the governed snapshot."))
        ),
        "RISK_EXPOSURE": escape_typst_string(supplied_text(mandate.get("risk_exposure"))),
        "BOOKING_CENTER": escape_typst_string(supplied_text(mandate.get("booking_center_code"))),
        "ADVISOR_ID": escape_typst_string(supplied_text(mandate.get("advisor_id"))),
        "INVESTED_VALUE": escape_typst_string(
            group_digits(portfolio_metrics.get("invested_value", "Not available"))
        ),
        "CASH_BALANCE": escape_typst_string(
            group_digits(portfolio_metrics.get("cash_balance", "Not available"))
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
            group_digits(
                allocation_summary.get("largest_asset_class_market_value", "Not available")
            )
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
            supplied_text(performance_highlight.get("benchmark_comparison_status"))
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
        # Whether a sub-page has anything to show. Each of these guards an
        # unconditional #pagebreak() that fired even for an all-empty report, so a
        # portfolio with no history still shipped three near-blank pages (issue #138).
        "HAS_PERFORMANCE_PERIODS": _presence_flag(report_data.get("performance_periods")),
        "HAS_ANNUAL_PERFORMANCE": _presence_flag(report_data.get("performance_annual_history")),
        "HAS_MONTHLY_PERFORMANCE": _presence_flag(report_data.get("performance_monthly_history")),
        "HAS_RISK_PROFILE": _presence_flag(risk_summary),
        "APPENDIX_GLOSSARY_GROUPS": render_appendix_glossary_groups(report_data),
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
        "PERFORMANCE_12M_CHART_SECTION": render_performance_chart_section(report_data),
        "HOLDING_ROWS": render_holding_rows(report_data.get("top_holdings")),
        "HOLDING_BAR_ROWS": render_holding_bar_rows(report_data.get("top_holdings")),
        "ASSET_CLASS_ROWS": render_allocation_breakdown_rows(
            allocation_breakdowns.get("by_asset_class") or report_data.get("top_holdings")
        ),
        "ALLOCATION_DONUT_CHART_SECTION": render_allocation_chart_section(report_data),
        "SUPPLEMENTAL_ALLOCATION_TITLE": escape_typst_string(supplemental_allocation_title),
        "SUPPLEMENTAL_ALLOCATION_ROWS": supplemental_allocation_rows,
        "POSITION_TABLE_WIDTHS": position_widths,
        "POSITION_TABLE_HEADER": position_header,
        "DENSE_POSITION_ROWS": position_rows,
        "TRANSACTION_PERIOD_LABEL": escape_typst_string(
            format_dates_in_text(
                report_data.get("transaction_period_label", "Transaction activity")
            )
        ),
        "TRANSACTION_TABLE_WIDTHS": transaction_widths,
        "TRANSACTION_TABLE_HEADER": transaction_header,
        "DENSE_TRANSACTION_ROWS": transaction_rows,
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
    source_contract_version = supplied_text(report_data.get("source_contract_version"))
    return {
        "TITLE": escape_typst_string(str(report_data["title"])),
        "PORTFOLIO_ID": escape_typst_string(str(report_data["portfolio_id"])),
        "PROOF_PACK_ID": escape_typst_string(str(report_data["proof_pack_id"])),
        "MANDATE_ID": escape_typst_string(supplied_text(report_data.get("mandate_id"))),
        "AS_OF_DATE": escape_typst_string(supplied_text(report_data.get("as_of_date"))),
        "STATE": escape_typst_string(str(report_data["state"])),
        "DECISION_ACTION": escape_typst_string(
            supplied_text(decision_summary.get("recommended_action"))
        ),
        "DECISION_RATIONALE": escape_typst_string(
            str(decision_summary.get("rationale", "No decision rationale supplied."))
        ),
        "SUPPORTABILITY_STATUS": escape_typst_string(
            supplied_text(supportability.get("status") or supportability.get("state"))
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
        "REBALANCE_RUN_ID": escape_typst_string(supplied_text(report_data.get("rebalance_run_id"))),
        "WAVE_ID": escape_typst_string(supplied_text(report_data.get("wave_id"))),
        "STATE": escape_typst_string(str(report_data["state"])),
        "OVERALL_OUTCOME": escape_typst_string(str(report_data["overall_outcome"])),
        "REVIEW_WINDOW_START": escape_typst_string(
            supplied_text(report_data.get("review_window_start"))
        ),
        "REVIEW_WINDOW_END": escape_typst_string(
            supplied_text(report_data.get("review_window_end"))
        ),
        "DIMENSION_ROWS": render_outcome_dimension_rows(dimensions),
        "SOURCE_SERVICES": escape_typst_string(
            ", ".join(string_list(report_data.get("source_services"))) or "lotus-manage"
        ),
        "SOURCE_HASH_ROWS": render_key_value_rows(source_hashes),
        "SECTION_HASH_ROWS": render_key_value_rows(section_hashes),
        "CONTENT_HASH": escape_typst_string(str(report_data["content_hash"])),
        "OUTCOME_REVIEW_CONTENT_HASH": escape_typst_string(
            supplied_text(report_data.get("outcome_review_content_hash"))
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
        "AS_OF_DATE": escape_typst_string(supplied_text(report_data.get("as_of_date"))),
        "ITEM_COUNT": escape_typst_string(supplied_text(aggregate_metrics.get("item_count"))),
        "READY_ITEM_COUNT": escape_typst_string(
            supplied_text(aggregate_metrics.get("ready_item_count"))
        ),
        "BLOCKED_ITEM_COUNT": escape_typst_string(
            supplied_text(aggregate_metrics.get("blocked_item_count"))
        ),
        "SUPPORTABILITY_STATUS": escape_typst_string(
            str(
                supportability.get(
                    "supportability_state",
                    supplied_text(supportability.get("status")),
                )
            )
        ),
        "SUPPORTABILITY_REASON": escape_typst_string(supplied_text(supportability.get("reason"))),
        "PROOF_PACK_READY_COUNT": escape_typst_string(
            supplied_text(proof_pack_posture.get("ready_proof_pack_count"))
        ),
        "PROOF_PACK_DEGRADED_COUNT": escape_typst_string(
            supplied_text(proof_pack_posture.get("degraded_proof_pack_count"))
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


def _presence_flag(value: object) -> str:
    """ "yes" when a sub-page has content to render, else "no".

    Compared as a string in the template because the substitution is textual; the
    value is produced here, never from report data, so it cannot carry untrusted text.
    """
    if isinstance(value, Mapping):
        return "yes" if value else "no"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "yes" if len(value) else "no"
    return "yes" if value else "no"


def render_report_sections(
    requested_sections: object,
    *,
    include_advisory_narrative: bool = False,
    include_advisor_memo: bool = False,
    include_appendix: bool = True,
) -> str:
    section_keys = requested_section_keys(
        requested_sections,
        include_advisory_narrative=include_advisory_narrative,
        include_advisor_memo=include_advisor_memo,
        include_appendix=include_appendix,
    )
    rendered = [f"#{PORTFOLIO_REVIEW_SECTION_CALLS[key]}" for key in section_keys]
    return "\n#pagebreak()\n".join(rendered)


def requested_section_keys(
    requested_sections: object,
    *,
    include_advisory_narrative: bool = False,
    include_advisor_memo: bool = False,
    include_appendix: bool = True,
) -> list[str]:
    if not isinstance(requested_sections, Sequence) or isinstance(
        requested_sections, (str, bytes, bytearray)
    ):
        return _default_section_keys(
            include_advisory_narrative=include_advisory_narrative,
            include_advisor_memo=include_advisor_memo,
            include_appendix=include_appendix,
        )

    allowed = set(PORTFOLIO_REVIEW_SECTION_CALLS) - _excluded_section_keys(
        include_advisory_narrative=include_advisory_narrative,
        include_advisor_memo=include_advisor_memo,
        include_appendix=include_appendix,
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
        include_appendix=include_appendix,
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
    *, include_advisory_narrative: bool, include_advisor_memo: bool, include_appendix: bool
) -> set[str]:
    excluded: set[str] = set()
    if not include_advisory_narrative:
        excluded.add("advisory_narrative")
    if not include_advisor_memo:
        excluded.add("advisor_memo")
    if not include_appendix:
        excluded.add("appendix")
    return excluded


def _default_section_keys(
    *, include_advisory_narrative: bool, include_advisor_memo: bool, include_appendix: bool
) -> list[str]:
    if include_advisor_memo:
        keys = list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_MEMO)
    elif include_advisory_narrative:
        keys = list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS_WITH_ADVISORY_NARRATIVE)
    else:
        keys = list(DEFAULT_PORTFOLIO_REVIEW_SECTIONS)
    if not include_appendix:
        keys = [key for key in keys if key != "appendix"]
    return keys


# Every "not available" on a page goes through one theme component, so counting its
# call sites in the built context counts exactly what a reader would see missing.
EMPTY_STATE_MARKER = "empty-state("


def count_empty_content_blocks(template_context: Mapping[str, str]) -> int:
    """How many content blocks this render replaced with a placeholder.

    A measurement of the output, not a judgement about the data: whether a document with
    eleven empty blocks is publishable belongs to the caller, and deciding it here would
    be Render forming an opinion about report completeness it has no standing to hold.
    """
    return sum(value.count(EMPTY_STATE_MARKER) for value in template_context.values())
