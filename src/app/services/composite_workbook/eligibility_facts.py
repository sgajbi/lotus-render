"""Report-owned controlled v4 statements from the frozen r2 producer examples."""

ELIGIBILITY_REPORT_FACTS = {
    "disclosures": [
        {
            "code": "CONTROLLED_SYNTHETIC_ONLY",
            "text": "Controlled synthetic source replay / NOT_ATTESTED. Population and "
            "published completeness are UNVERIFIED; official activation is "
            "UNAVAILABLE.",
        },
        {
            "code": "SOURCE_OWNED_DECISIONS",
            "text": "Manage owns eligibility and publication. Report preserves all "
            "three assessments and does not evaluate thresholds or manufacture "
            "approvals.",
        },
        {
            "code": "FIRST_REASON_LOSS_BOUNDARY",
            "text": "Membership reason_code is only the first reason. "
            "EligibilityReasons preserves every failure and unknown occurrence; "
            "occurrences are not unique excluded members.",
        },
        {
            "code": "EVALUATED_IS_NOT_PUBLISHED",
            "text": "EVALUATED_ONLY retains a proposal and missing-observation UNKNOWN "
            "cases. Approval, publication and membership history are "
            "unavailable for that variant; no receipt is inferred.",
        },
        {
            "code": "EXACT_HISTORY",
            "text": "History retains original inclusive revision intervals. Selected "
            "month gaps are not filled; same-month policy diffs are not "
            "cross-month history. Cleared cash alone does not imply re-entry.",
        },
        {
            "code": "SOURCE_UNITS",
            "text": "Ratios are source decimal ratios, not return percentages. Money, "
            "portfolio counts, event counts and booleans remain distinct. Raw "
            "decimal spelling and nulls remain retained.",
        },
    ],
    "no_reasons": {
        "statement": "All captured assessment reason arrays for this month are empty; "
        "no applicable reason occurrences.",
        "value": None,
    },
    "reason_kinds": {"failure_reasons": "FAILURE", "unknown_reasons": "UNKNOWN"},
    "unavailable": None,
}
