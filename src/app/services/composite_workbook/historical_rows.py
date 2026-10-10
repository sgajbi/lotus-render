"""Lexical scalar pointers and global table ordinals survive sorted JSON replay."""

from typing import Any

from app.services.composite_workbook.eligibility_rows import PointerRow
from app.services.composite_workbook.source_values import resolve_pointer


def scalar_pointers(value: Any, pointer: str) -> list[str]:
    if isinstance(value, dict):
        return [
            leaf
            for key in sorted(value)
            for leaf in scalar_pointers(
                value[key], pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            )
        ]
    if isinstance(value, list):
        return [
            leaf
            for index, child in enumerate(value)
            for leaf in scalar_pointers(child, f"{pointer}/{index}")
        ]
    return [pointer]


def _amendment_paths(
    proposal: dict[str, Any], month: dict[str, Any], base: str, root: str
) -> list[str]:
    if proposal["product_version"] == "v3":
        return ["/report_facts/no_amendment"]
    paths = scalar_pointers(proposal["amendment"], base + "/amendment")
    for position, receipt in enumerate(month["lineage_receipts"]):
        pointer = f"{root}/lineage_receipts/{position}"
        paths.extend(
            pointer + "/" + key
            for key in ("product_name", "product_version", "content_hash", "publication_sequence")
        )
        if receipt["product_version"] == "v4":
            paths.extend(scalar_pointers(receipt["lineage"], pointer + "/lineage"))
    return paths


def _proof_paths(raw: dict[str, Any], base: str, receipt: Any) -> list[tuple[str, str]]:
    roles = [
        ("POLICY_ADMISSION", base + "/policy_approval"),
        ("EVALUATION_PROPOSAL", base + "/operation_verification"),
    ]
    if receipt is not None:
        roles.append(
            ("EVALUATION_APPROVAL", base.rsplit("/proposal", 1)[0] + "/operation_verification")
        )
    return [
        (role, leaf)
        for role, pointer in roles
        for leaf in scalar_pointers(resolve_pointer(raw, pointer), pointer)
    ]


def _provenance_paths(
    raw: dict[str, Any], month: dict[str, Any], base: str, root: str
) -> list[tuple[str, str]]:
    proposals = [(base, month.get("receipt"))]
    proposals.extend(
        (f"{root}/lineage_receipts/{position}/approval/proposal", receipt)
        for position, receipt in enumerate(month["lineage_receipts"])
    )
    return [path for pointer, receipt in proposals for path in _proof_paths(raw, pointer, receipt)]


def historical_rows(raw: dict[str, Any]) -> dict[str, list[PointerRow]]:
    rows: dict[str, list[PointerRow]] = {"Amendments": [], "PolicyAdmission": []}
    for index, month in enumerate(raw["source_months"]):
        root = f"/source_months/{index}"
        suffix = (
            "/proposal"
            if month["evidence_kind"] == "EVALUATED_ONLY"
            else "/receipt/approval/proposal"
        )
        base = root + suffix
        proposal = resolve_pointer(raw, base)
        for pointer in _amendment_paths(proposal, month, base, root):
            rows["Amendments"].append(
                (
                    f"m{index}:a{len(rows['Amendments'])}",
                    {
                        "month": f"/selection/months/{index}/month",
                        "value": pointer,
                    },
                )
            )
        for role, pointer in _provenance_paths(raw, month, base, root):
            rows["PolicyAdmission"].append(
                (
                    f"m{index}:p{len(rows['PolicyAdmission'])}",
                    {
                        "month": f"/selection/months/{index}/month",
                        "evidence_role": "/report_facts/evidence_roles/" + role,
                        "value": pointer,
                    },
                )
            )
    return rows
