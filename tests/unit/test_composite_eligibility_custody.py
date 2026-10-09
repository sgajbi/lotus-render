"""The v4 custody shape preserves Report's selector and digest authority."""

import json
from typing import Any

import pytest
from eligibility_fixtures import producer_package, selector
from pydantic import ValidationError

from app.contracts.render_package import RenderPackage
from app.services.composite_workbook.eligibility_custody import (
    EligibilityCustodyIdentity,
    validate_eligibility_custody,
)


@pytest.mark.parametrize("kind", ["evaluated_only", "published"])
def test_actual_supplier_unit_envelope_binds_exact_selection_and_revision(kind: str) -> None:
    validate_eligibility_custody(RenderPackage.model_validate(producer_package(kind)))


@pytest.mark.parametrize(
    "field",
    [
        "tenant_id",
        "composite_id",
        "portfolio_id",
        "portfolio_scope",
        "as_of_date",
        "reporting_period_start",
        "reporting_period_end",
        "retention_start_date",
        "report_revision_id",
    ],
)
def test_conflicting_custody_scope_refuses_before_writing(field: str) -> None:
    package = producer_package()
    package["render_context"]["archive"][field] = "wrong"
    with pytest.raises(ValueError, match="composite_eligibility_.*conflict"):
        validate_eligibility_custody(RenderPackage.model_validate(package))


def test_changed_snapshot_lineage_cannot_borrow_another_report_revision() -> None:
    package = producer_package()
    package["lineage_refs"][0] = "foreign-snapshot"
    with pytest.raises(ValueError, match="snapshot_revision_conflict"):
        validate_eligibility_custody(RenderPackage.model_validate(package))


@pytest.mark.parametrize("change", ["missing_archive", "selection", "missing_revision"])
def test_custody_requires_complete_original_transport_identity(change: str) -> None:
    package = producer_package()
    if change == "missing_archive":
        del package["render_context"]["archive"]
    elif change == "selection":
        package["render_context"]["archive"]["composite_report_identity"]["selection"]["months"][0][
            "source_cut_id"
        ] = "other-cut"
    else:
        del package["render_context"]["report_revision_id"]
    with pytest.raises(ValueError, match="composite_eligibility_"):
        validate_eligibility_custody(RenderPackage.model_validate(package))


def identity() -> dict[str, Any]:
    return {
        "contract_version": "composite_review.v4",
        "qualification": "CONTROLLED_ELIGIBILITY_SOURCE_REPLAY",
        "publication_state": "NOT_ATTESTED",
        "selection": selector(),
        "series_digest": "a" * 64,
        "source_revision_digest": "b" * 64,
        "factual_content_digest": "c" * 64,
    }


def test_custody_identity_preserves_the_exact_nonfinancial_selection() -> None:
    wire = identity()
    parsed = EligibilityCustodyIdentity.model_validate_json(json.dumps(wire))
    assert parsed.model_dump(mode="json") == wire
    assert "calculation_id" not in wire["selection"]


@pytest.mark.parametrize(
    "field", ["series_digest", "source_revision_digest", "factual_content_digest"]
)
@pytest.mark.parametrize("value", ["sha256:" + "a" * 64, "A" * 64, "a" * 63, None])
def test_custody_digest_is_exact_lowercase_unprefixed_sha256(field: str, value: Any) -> None:
    wire = identity()
    wire[field] = value
    with pytest.raises(ValidationError):
        EligibilityCustodyIdentity.model_validate_json(json.dumps(wire))


@pytest.mark.parametrize(
    "field,value",
    [
        ("publication_state", "ATTESTED"),
        ("qualification", "EXPLICIT_RETAINED_CALCULATED_REPLAY"),
        ("contract_version", "composite_review.v3"),
    ],
)
def test_custody_cannot_promote_or_relabel_controlled_eligibility(field: str, value: str) -> None:
    wire = identity()
    wire[field] = value
    with pytest.raises(ValidationError):
        EligibilityCustodyIdentity.model_validate_json(json.dumps(wire))
