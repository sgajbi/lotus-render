"""Adversarial transport bindings for the actual Report r4 packages."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.linked_custody import validate_linked_custody


def package_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        Path("tests/golden/composite-review/v3/render-package.json").read_bytes()
    )
    return payload


def test_sealed_supplier_schema_and_packages_keep_exact_bytes() -> None:
    expected = [
        (
            "contracts/report-data/composite_review.v3.schema.json",
            "c81dce9accd3721931663f40d160b282eafcf039191d2d649be9698e7a9c4237",
        ),
        (
            "contracts/report-data/composite_review.v3.custody.schema.json",
            "578001c3ef24964694382bacacbdcc05b71a0c2233106f395665a74336b02870",
        ),
        (
            "tests/golden/composite-review/v3/render-package.json",
            "094b5d39608ceb000141d8a2982bbd02ee12f2daed905d2cea542349a6ed173c",
        ),
        (
            "tests/golden/composite-review/v3/corrected-render-package.json",
            "1dc48914ad30484a71af6568ef9c9bfbbdb40ababd86d51a599dc8f281fe0b22",
        ),
    ]
    for path, digest in expected:
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    assert Path(
        "src/app/contracts/examples/composite-review-render-package.v3.json"
    ).read_bytes() == (Path("tests/golden/composite-review/v3/render-package.json").read_bytes())


@pytest.mark.parametrize("revision", ["render-package", "corrected-render-package"])
def test_actual_report_packages_bind_exact_custody(revision: str) -> None:
    payload = Path(f"tests/golden/composite-review/v3/{revision}.json").read_bytes()
    validate_linked_custody(RenderPackage.model_validate_json(payload))


@pytest.mark.parametrize(
    "change",
    [
        "missing_archive",
        "missing_identity",
        "legacy_identity",
        "extra_identity",
        "selection",
        "null_request_presence",
        "missing_revision",
        "archive_revision",
        "snapshot",
        "lineage_revision",
        "extra_lineage",
        "tenant",
        "composite",
        "scope",
        "portfolio",
        "start",
        "end",
        "as_of",
        "retention",
        "digest",
    ],
)
def test_conflicting_custody_is_refused(change: str) -> None:
    payload = copy.deepcopy(package_payload())
    context = payload["render_context"]
    archive = context["archive"]
    identity = archive["composite_report_identity"]
    if change == "missing_archive":
        del context["archive"]
    elif change == "missing_identity":
        del archive["composite_report_identity"]
    elif change == "legacy_identity":
        identity["contract_version"] = "composite_review.v2"
    elif change == "extra_identity":
        identity["source_products"] = []
    elif change == "selection":
        identity["selection"]["source_request"]["composite_id"] = "competing"
    elif change == "null_request_presence":
        del identity["selection"]["source_request"]["restatement_sequence"]
    elif change == "missing_revision":
        del context["report_revision_id"]
    elif change == "archive_revision":
        archive["report_revision_id"] = "competing"
    elif change == "snapshot":
        payload["snapshot_id"] = "competing"
    elif change == "lineage_revision":
        payload["lineage_refs"][1] = "competing"
    elif change == "extra_lineage":
        payload["lineage_refs"].append("competing")
    elif change == "digest":
        identity["factual_content_digest"] = "sha256:" + "0" * 64
    else:
        field = {
            "tenant": "tenant_id",
            "composite": "composite_id",
            "scope": "portfolio_scope",
            "portfolio": "portfolio_id",
            "start": "reporting_period_start",
            "end": "reporting_period_end",
            "as_of": "as_of_date",
            "retention": "retention_start_date",
        }[change]
        archive[field] = "competing"
    with pytest.raises(ValueError):
        validate_linked_custody(RenderPackage.model_validate(payload))
