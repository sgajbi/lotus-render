"""Exact frozen v4 table identities; operational ratios are never investment returns."""

from typing import Any

from app.domain.templates.registry import TemplateRegistryError

ELIGIBILITY_TABLE_COLUMNS = {
    "Summary": (
        "month",
        "evidence_kind",
        "expected_count",
        "observed_count",
        "included_count",
        "excluded_count",
        "pending_review_count",
        "population_verification",
        "official_activation",
    ),
    "Members": ("month", "portfolio_id", "status", "observations_present"),
    "EligibilityAssessments": (
        "month",
        "portfolio_id",
        "rule",
        "outcome",
        "numerator",
        "denominator",
        "ratio",
        "gross_inflow",
        "gross_outflow",
        "admitted_flow_count",
    ),
    "EligibilityReasons": ("month", "portfolio_id", "rule", "kind", "reason_code"),
    "MembershipHistory": (
        "month",
        "membership_revision",
        "portfolio_id",
        "effective_from",
        "effective_to",
        "status",
        "reason_code",
        "discretionary",
        "approval_ref",
        "source_snapshot_id",
        "supersedes_membership_revision",
        "affected_from",
        "affected_to",
    ),
    "Methods": (
        "month",
        "profile_kind",
        "flow_threshold",
        "cash_threshold",
        "flow_measure",
        "flow_breach_operator",
        "cash_breach_operator",
        "reentry",
        "content_hash",
    ),
    "Lineage": ("month", "evidence_kind", "product", "revision", "content_hash", "response_digest"),
    "Disclosures": ("code", "text"),
}


def eligibility_column_policy(key: str, currency: str) -> dict[str, Any]:
    value_type, unit, places = _column_type(key)
    return {
        "column_id": key,
        "label": key.replace("_", " "),
        "value_type": value_type,
        "unit": unit,
        "display_unit": unit,
        "display_conversion": "IDENTITY",
        "display_decimal_places": places,
        "display_rounding_mode": "HALF_UP",
        "currency": currency if value_type == "MONEY" else None,
        "scale": "1",
    }


def _column_type(key: str) -> tuple[str, str, int | None]:
    if key in {"numerator", "denominator", "gross_inflow", "gross_outflow"}:
        return "MONEY", "CURRENCY_UNITS", 2
    if key in {"ratio", "flow_threshold", "cash_threshold"}:
        return "DECIMAL_FACTOR", "DECIMAL_RATIO", 12
    if key in {
        "expected_count",
        "observed_count",
        "included_count",
        "excluded_count",
        "pending_review_count",
    }:
        return "COUNT", "PORTFOLIO_COUNT", 0
    if key == "admitted_flow_count":
        return "COUNT", "EVENT_COUNT", 0
    if key in {"observations_present", "discretionary"}:
        return "BOOLEAN", "BOOLEAN", None
    return "TEXT", "TEXT", None


def validate_eligibility_table_set(layout: dict[str, Any], table_names: set[str]) -> None:
    if (
        layout.get("required_tables") != list(ELIGIBILITY_TABLE_COLUMNS)
        or layout.get("optional_tables") != []
        or layout.get("period_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if table_names != set(ELIGIBILITY_TABLE_COLUMNS):
        raise ValueError("composite_workbook_table_set_invalid")
