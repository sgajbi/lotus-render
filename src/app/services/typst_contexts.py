"""Template-context builders: one governed context per report family.

Each builder assembles the full substitution context for its template from a
validated render package. Section selection for the portfolio review lives
here too, since the requested sections decide which fragments are emitted.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from app.contracts.render_package import RenderPackage
from app.services.absence import supplied_text
from app.services.appendix_glossary import applicable_glossary
from app.services.attribution_bridge import render_attribution_bridge
from app.services.benchmark_presentation import benchmark_note, benchmark_presentation
from app.services.contribution_ranking import render_contribution_ranking_section
from app.services.date_format import format_date, format_dates_in_text
from app.services.earnings_statement import render_earnings_statement
from app.services.fee_drag import render_fee_drag_note
from app.services.holdings_presentation import render_holdings_scope_notes
from app.services.number_format import group_digits
from app.services.render_content import (
    parse_outcome_review_content,
    parse_portfolio_review_content,
    parse_proof_pack_content,
    parse_rebalance_wave_content,
)
from app.services.risk_attribution import render_risk_attribution_panel
from app.services.risk_supportability import render_risk_supportability_notes
from app.services.risk_trend import render_risk_trend_panel
from app.services.section_selection import (
    included_optional_sections,
    resolve_section_keys,
)
from app.services.typst_fragments import (
    render_advisor_commentary_fact_rows,
    render_advisor_commentary_prose,
    render_advisor_memo_fact_rows,
    render_advisor_memo_section_blocks,
    render_advisory_disclosure_blocks,
    render_advisory_narrative_blocks,
    render_commentary_points,
    render_key_value_rows,
    render_outcome_dimension_rows,
    render_proof_pack_section_rows,
    render_reviewed_advisory_fact_rows,
    render_source_lineage_rows,
    render_wave_event_rows,
    render_wave_item_rows,
)
from app.services.typst_tables import (
    render_allocation_chart_section,
    render_allocation_dimension_blocks,
    render_appendix_glossary_groups,
    render_holding_bar_rows,
    render_observation_notes,
    render_performance_chart_rows,
    render_performance_chart_section,
    render_performance_detail_rows,
    render_performance_period_rows,
    render_performance_summary_table,
    render_position_table,
    render_transaction_table,
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
    "advisor_commentary": "advisor-commentary-page()",
    "appendix": "appendix-page()",
}


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
    performance_highlight = mapping(report_data.get("performance_highlight"))
    risk_summary = mapping(report_data.get("risk_summary"))
    governance_summary = mapping(report_data.get("governance_summary"))
    reviewed_advisory_narrative = mapping(report_data.get("reviewed_advisory_narrative"))
    advisor_proposal_memo = mapping(report_data.get("advisor_proposal_memo"))
    advisor_commentary = mapping(report_data.get("advisor_commentary"))
    # Which optional sections this package carries -- the same computation admission
    # validates the explicit selection against, from the same module.
    included_sections = included_optional_sections(report_data)
    # A fact about the mandate, stated by Report. Inferring it from whether any period
    # row supplied a benchmark value removed the columns during an upstream outage, so a
    # benchmarked client received a report that read as unbenchmarked.
    benchmark = benchmark_presentation(report_data)
    benchmarked = benchmark.columns_are_drawn
    benchmark_caveat = benchmark_note(benchmark) or ""
    reporting_period_label = _reporting_period_label(report_data)
    # Emitted once and flagged from the emission: a block that draws nothing must not
    # leave the template a "yes" flag over an empty fragment.
    attribution_bridge = render_attribution_bridge(report_data)
    fee_drag_note = render_fee_drag_note(report_data)

    position_widths, position_header, position_rows = render_position_table(
        report_data.get("positions") or report_data.get("top_holdings")
    )
    transaction_widths, transaction_header, transaction_rows = render_transaction_table(
        report_data.get("transactions")
    )

    return {
        "REPORT_SECTIONS": render_report_sections(
            render_context.get("sections"),
            included=included_sections,
            # The appendix explains the terms this document uses. A report that uses
            # none of them would otherwise ship a page saying so.
            include_appendix=bool(applicable_glossary(report_data)),
        ),
        "OPTIONAL_ADVISORY_IMPORT": (
            '#import "_advisory.typ": advisor-commentary-page, '
            "advisor-proposal-memo-page, reviewed-advisory-narrative-page"
            if included_sections
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
            group_digits(supplied_text(portfolio_metrics.get("invested_value")))
        ),
        "CASH_BALANCE": escape_typst_string(
            group_digits(supplied_text(portfolio_metrics.get("cash_balance")))
        ),
        "CASH_WEIGHT_PCT": escape_typst_string(
            supplied_text(portfolio_metrics.get("cash_weight_pct"))
        ),
        "ALLOCATION_LARGEST_NAME": escape_typst_string(
            supplied_text(allocation_summary.get("largest_asset_class_name"))
        ),
        "ALLOCATION_LARGEST_WEIGHT": escape_typst_string(
            supplied_text(allocation_summary.get("largest_asset_class_weight_pct"))
        ),
        "ALLOCATION_LARGEST_VALUE": escape_typst_string(
            group_digits(supplied_text(allocation_summary.get("largest_asset_class_market_value")))
        ),
        "ALLOCATION_POSITION_COUNT": escape_typst_string(
            supplied_text(allocation_summary.get("largest_asset_class_position_count"))
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
        "RISK_VOLATILITY": escape_typst_string(supplied_text(risk_summary.get("volatility_pct"))),
        "RISK_BETA": escape_typst_string(supplied_text(risk_summary.get("beta"))),
        "RISK_TRACKING_ERROR": escape_typst_string(
            supplied_text(risk_summary.get("tracking_error_pct"))
        ),
        "RISK_INFORMATION_RATIO": escape_typst_string(
            supplied_text(risk_summary.get("information_ratio"))
        ),
        "RISK_VAR": escape_typst_string(supplied_text(risk_summary.get("value_at_risk_pct"))),
        # Whether a sub-page has anything to show. Each of these guards an
        # unconditional #pagebreak() that fired even for an all-empty report, so a
        # portfolio with no history still shipped three near-blank pages (issue #138).
        "HAS_PERFORMANCE_PERIODS": _presence_flag(report_data.get("performance_periods")),
        # The same fact the appendix reads to decide whether "Benchmark" needs defining,
        # so the columns and their definitions cannot disagree.
        "HAS_BENCHMARK": "yes" if benchmarked else "no",
        # Empty when the comparison arrived. A note that is always there is furniture.
        "BENCHMARK_NOTE": escape_typst_string(benchmark_caveat),
        "HAS_BENCHMARK_NOTE": _presence_flag(benchmark_caveat),
        "HAS_ANNUAL_PERFORMANCE": _presence_flag(report_data.get("performance_annual_history")),
        "HAS_MONTHLY_PERFORMANCE": _presence_flag(report_data.get("performance_monthly_history")),
        "HAS_RISK_PROFILE": _presence_flag(risk_summary),
        "RISK_SUPPORTABILITY_NOTES": render_risk_supportability_notes(report_data),
        "APPENDIX_GLOSSARY_GROUPS": render_appendix_glossary_groups(report_data),
        "OBSERVATION_NOTES": render_observation_notes(observations),
        "PERFORMANCE_PERIOD_ROWS": render_performance_period_rows(
            report_data.get("performance_periods"), benchmarked=benchmarked
        ),
        "PERFORMANCE_SUMMARY_TABLE": render_performance_summary_table(
            report_data.get("performance_summary_table")
        ),
        "PERFORMANCE_ANNUAL_CHART_ROWS": render_performance_chart_rows(
            report_data.get("performance_annual_history")
        ),
        "PERFORMANCE_MONTHLY_TABLE_ROWS": render_performance_detail_rows(
            report_data.get("performance_monthly_history")
        ),
        "PERFORMANCE_12M_CHART_SECTION": render_performance_chart_section(report_data),
        "CONTRIBUTION_RANKING_ROWS": render_contribution_ranking_section(report_data),
        "ATTRIBUTION_BRIDGE": attribution_bridge,
        "HAS_ATTRIBUTION_BRIDGE": _presence_flag(attribution_bridge),
        "FEE_DRAG_NOTE": fee_drag_note,
        "HAS_FEE_DRAG_NOTE": _presence_flag(fee_drag_note),
        # Drawn only where the package carries a ranking at all. A posture of `empty` or
        # `unavailable` still draws the section, because the reader asked which holdings
        # explained the period and is owed the answer that none can be shown.
        "HAS_CONTRIBUTION_RANKING": _presence_flag(report_data.get("contribution_ranking")),
        "HOLDING_BAR_ROWS": render_holding_bar_rows(report_data.get("top_holdings")),
        "HOLDINGS_SCOPE_NOTES": render_holdings_scope_notes(report_data),
        "ALLOCATION_DONUT_CHART_SECTION": render_allocation_chart_section(report_data),
        # One block per dimension the package named, in its order. Replaces a hard-coded
        # asset-class table beside one supplemental slot Render chose for itself.
        "ALLOCATION_DIMENSION_BLOCKS": render_allocation_dimension_blocks(report_data),
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
        "EARNINGS_STATEMENT": render_earnings_statement(report_data),
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
        "ADVISOR_COMMENTARY_FACT_ROWS": render_advisor_commentary_fact_rows(advisor_commentary),
        # Composed by lotus-report, placed by Render. Required output: this is AI-drafted
        # narrative, and who accepted it and when is part of the content.
        "ADVISOR_COMMENTARY_PROVENANCE": render_advisor_commentary_prose(
            advisor_commentary, "disclosure_text"
        ),
        "ADVISOR_COMMENTARY_SUMMARY": render_advisor_commentary_prose(
            advisor_commentary, "grounded_summary"
        ),
        "ADVISOR_COMMENTARY_TALKING_POINTS": render_commentary_points(
            advisor_commentary,
            "talking_points",
            empty_message="No talking points were supplied with the accepted commentary.",
        ),
        "ADVISOR_COMMENTARY_RISKS": render_commentary_points(
            advisor_commentary,
            "risks_and_exceptions",
            empty_message="No risks or exceptions were supplied with the accepted commentary.",
        ),
        "RENDER_JOB_ID": escape_typst_string(render_package.render_job_id),
        "TEMPLATE_ID": escape_typst_string(render_package.template_id),
        "TEMPLATE_VERSION": escape_typst_string(render_package.template_version),
        "REQUESTED_BY": escape_typst_string(str(render_package.requested_by)),
        "TIMEZONE": escape_typst_string(str(render_context.get("timezone", "unknown"))),
    }


def build_portfolio_review_v2_context(render_package: RenderPackage) -> dict[str, str]:
    """v1's context plus exactly what v2's page adds.

    Layered rather than copied so the frozen v1 never gains keys it does not
    draw, and v2's additions are visible in one place: the risk-trend band and
    the source insertion point for report#254's attribution half (empty until its
    producer contract ships -- filling it will change pagination, acceptable only
    while v2 is development; after v2 publishes, attribution is a v3 change).
    """
    context = build_portfolio_review_context(render_package)
    report_data = render_package.report_data
    context["RISK_TREND_PANEL"] = render_risk_trend_panel(report_data)
    context["RISK_ATTRIBUTION_PANEL"] = ""
    return context


def build_portfolio_review_v3_context(render_package: RenderPackage) -> dict[str, str]:
    """v2's context plus exactly what v3's page adds: the risk-attribution
    panel filling the insertion point v2 reserved (and keeps empty forever)."""
    context = build_portfolio_review_v2_context(render_package)
    context["RISK_ATTRIBUTION_PANEL"] = render_risk_attribution_panel(render_package.report_data)
    return context


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
    included: Collection[str] = (),
    include_appendix: bool = True,
) -> str:
    section_keys = requested_section_keys(
        requested_sections, included=included, include_appendix=include_appendix
    )
    rendered = [f"#{PORTFOLIO_REVIEW_SECTION_CALLS[key]}" for key in section_keys]
    return "\n#pagebreak()\n".join(rendered)


def requested_section_keys(
    requested_sections: object,
    *,
    included: Collection[str] = (),
    include_appendix: bool = True,
) -> list[str]:
    """The sections to draw: the caller's explicit selection honoured exactly, or the
    default composition when no selection was made.

    Raises `SectionSelectionError` on a selection that cannot be honoured. Admission
    refuses such packages before compilation (`section_selection_refusal`), so reaching
    that error here means a package skipped admission -- failing the render is correct,
    because the fallback this function used to perform silently widened an explicit
    request to the full default report.
    """
    return resolve_section_keys(
        requested_sections, included=included, include_appendix=include_appendix
    )


# Every "not available" on a page goes through one theme component, so counting its call
# sites counts what a reader sees missing -- but only because every key that can carry
# one is substituted into a template. That was not true: `HOLDING_ROWS` and
# `PERFORMANCE_MONTHLY_CHART_ROWS` were built and dropped, and the degraded review
# reported eleven placeholders where a reader could see nine. Both are gone, and
# `test_no_unreferenced_key_can_inflate_the_empty_block_count` is what keeps it so.
EMPTY_STATE_MARKER = "empty-state("


def count_empty_content_blocks(template_context: Mapping[str, str]) -> int:
    """How many content blocks this render replaced with a placeholder.

    A measurement of the output, not a judgement about the data: whether a document with
    nine empty blocks is publishable belongs to the caller, and deciding it here would be
    Render forming an opinion about report completeness it has no standing to hold.
    """
    return sum(value.count(EMPTY_STATE_MARKER) for value in template_context.values())
