"""Reviewed v5 logical table inventory; exact rows are reconstructed from source."""

from typing import Any

from app.domain.templates.registry import TemplateRegistryError

POOLED_REQUIRED_TABLES = (
    "Summary",
    "Outcome",
    "MonetaryObservation",
    "Policy",
    "Disclosures",
    "SourceEvidence",
)
POOLED_OPTIONAL_TABLES = (
    "InvestorCashFlows",
    "Valuations",
    "PortfolioFlows",
    "MemberControls",
    "SourcePins",
    "Membership",
    "PredecessorEvidence",
)


def validate_pooled_table_set(layout: dict[str, Any], names: set[str]) -> None:
    if (
        layout.get("required_tables") != list(POOLED_REQUIRED_TABLES)
        or layout.get("optional_tables") != list(POOLED_OPTIONAL_TABLES)
        or layout.get("period_tables") != []
    ):
        raise TemplateRegistryError("composite_workbook_layout_policy_mismatch")
    if (
        not set(POOLED_REQUIRED_TABLES)
        <= names
        <= set(POOLED_REQUIRED_TABLES + POOLED_OPTIONAL_TABLES)
    ):
        raise ValueError("composite_workbook_table_set_invalid")
