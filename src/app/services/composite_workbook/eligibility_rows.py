"""Reconstruct every frozen row and pointer from complete source products."""

from typing import Any

from app.services.composite_workbook.eligibility_policy import ELIGIBILITY_TABLE_COLUMNS
from app.services.composite_workbook.source_values import resolve_pointer

PointerRow = tuple[str, dict[str, str]]


def eligibility_rows(dataset: dict[str, Any]) -> dict[str, list[PointerRow]]:
    rows: dict[str, list[PointerRow]] = {name: [] for name in ELIGIBILITY_TABLE_COLUMNS}
    for index, source in enumerate(dataset["source_months"]):
        root = f"/source_months/{index}"
        proposal = root + (
            "/proposal"
            if source["evidence_kind"] == "EVALUATED_ONLY"
            else "/receipt/approval/proposal"
        )
        month = f"/selection/months/{index}/month"
        evaluation = proposal + "/evaluation"
        summary = {key: f"{evaluation}/{key}" for key in ELIGIBILITY_TABLE_COLUMNS["Summary"]}
        summary.update(month=month, evidence_kind=root + "/evidence_kind")
        rows["Summary"].append((f"m{index}", summary))
        methods = {
            key: f"{evaluation}/resolved_policy/{key}"
            for key in ELIGIBILITY_TABLE_COLUMNS["Methods"]
        }
        methods["month"] = month
        rows["Methods"].append((f"m{index}", methods))
        _member_rows(dataset, rows, index, evaluation, month)
        _history_rows(dataset, rows, index, root, month)
        _lineage_rows(rows, index, root, proposal, month, source["evidence_kind"])
    rows["Disclosures"] = [
        (f"d{index}", {key: f"/report_facts/disclosures/{index}/{key}" for key in ("code", "text")})
        for index in range(len(dataset["report_facts"]["disclosures"]))
    ]
    return rows


def _member_rows(
    dataset: dict[str, Any],
    rows: dict[str, list[PointerRow]],
    index: int,
    evaluation: str,
    month: str,
) -> None:
    reason_count = len(rows["EligibilityReasons"])
    for member_index, member in enumerate(resolve_pointer(dataset, evaluation + "/portfolios")):
        identity = f"m{index}:p{member_index}"
        base = f"{evaluation}/portfolios/{member_index}"
        cells = {key: f"{base}/{key}" for key in ELIGIBILITY_TABLE_COLUMNS["Members"]}
        cells["month"] = month
        rows["Members"].append((identity, cells))
        for assessment_index, assessment in enumerate(member["assessments"]):
            assessment_id = f"{identity}:a{assessment_index}"
            assessment_base = f"{base}/assessments/{assessment_index}"
            cells = {
                key: f"{assessment_base}/{key}"
                for key in ELIGIBILITY_TABLE_COLUMNS["EligibilityAssessments"]
            }
            cells.update(month=month, portfolio_id=base + "/portfolio_id")
            rows["EligibilityAssessments"].append((assessment_id, cells))
            _reason_rows(rows, assessment, assessment_id, assessment_base, base, month)
    if len(rows["EligibilityReasons"]) == reason_count:
        cells = {
            key: "/report_facts/no_reasons/value"
            for key in ELIGIBILITY_TABLE_COLUMNS["EligibilityReasons"]
        }
        cells["month"] = month
        rows["EligibilityReasons"].append((f"m{index}:not_applicable", cells))


def _reason_rows(
    rows: dict[str, list[PointerRow]],
    assessment: dict[str, Any],
    identity: str,
    base: str,
    member: str,
    month: str,
) -> None:
    for kind in ("failure_reasons", "unknown_reasons"):
        for ordinal in range(len(assessment[kind])):
            rows["EligibilityReasons"].append(
                (
                    f"{identity}:{kind}:{ordinal}",
                    {
                        "month": month,
                        "portfolio_id": member + "/portfolio_id",
                        "rule": base + "/rule",
                        "kind": f"/report_facts/reason_kinds/{kind}",
                        "reason_code": f"{base}/{kind}/{ordinal}",
                    },
                )
            )


def _history_rows(
    dataset: dict[str, Any], rows: dict[str, list[PointerRow]], index: int, root: str, month: str
) -> None:
    if resolve_pointer(dataset, root + "/evidence_kind") == "EVALUATED_ONLY":
        cells = {
            key: "/report_facts/unavailable"
            for key in ELIGIBILITY_TABLE_COLUMNS["MembershipHistory"]
        }
        cells["month"] = month
        rows["MembershipHistory"].append((f"m{index}:unavailable", cells))
        return
    metadata = {
        "membership_revision",
        "supersedes_membership_revision",
        "affected_from",
        "affected_to",
    }
    for name in ("parent_membership", "membership"):
        base = f"{root}/{name}"
        for ordinal in range(len(resolve_pointer(dataset, base + "/decisions"))):
            cells = {
                key: f"{base}/decisions/{ordinal}/{key}"
                for key in ELIGIBILITY_TABLE_COLUMNS["MembershipHistory"]
            }
            cells.update({key: f"{base}/{key}" for key in metadata})
            cells["month"] = month
            rows["MembershipHistory"].append((f"m{index}:{name}:d{ordinal}", cells))


def _lineage_rows(
    rows: dict[str, list[PointerRow]], index: int, root: str, proposal: str, month: str, kind: str
) -> None:
    products = [
        (proposal, "evaluation_revision", "proposal" if kind == "EVALUATED_ONLY" else "receipt")
    ]
    if kind == "PUBLISHED":
        products.extend(
            (f"{root}/{name}", revision, name)
            for name, revision in (
                ("membership", "membership_revision"),
                ("parent_membership", "membership_revision"),
                ("universe", "attestation_version"),
                ("receipt", "publication_sequence"),
            )
        )
    for ordinal, (base, revision, response) in enumerate(products):
        rows["Lineage"].append(
            (
                f"m{index}:s{ordinal}",
                {
                    "month": month,
                    "evidence_kind": root + "/evidence_kind",
                    "product": base + "/product_name",
                    "revision": f"{base}/{revision}",
                    "content_hash": base + "/content_hash",
                    "response_digest": f"{root}/response_digests/{response}",
                },
            )
        )
