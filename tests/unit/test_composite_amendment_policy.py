"""Exact layout and opaque custody pins cannot broaden source-correction authority."""

import json
from pathlib import Path

import pytest
from amendment_fixtures import unit_amendment_package

from app.contracts.render_package import RenderPackage
from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.amendment_custody import validate_amendment_custody
from app.services.composite_workbook.amendment_tables import AMENDMENT_TABLE_COLUMNS
from app.services.composite_workbook.rendering import _validate_layout


def test_v6_layout_and_opaque_unit_custody_are_admissible() -> None:
    layout = json.loads(Path("templates/xlsx/composite-review/v6/layout.json").read_bytes())
    _validate_layout(layout, set(AMENDMENT_TABLE_COLUMNS), version="v6")
    validate_amendment_custody(RenderPackage.model_validate(unit_amendment_package()))


@pytest.mark.parametrize("field", ["required_tables", "optional_tables", "period_tables"])
def test_v6_layout_cannot_admit_financial_tables(field: str) -> None:
    layout = json.loads(Path("templates/xlsx/composite-review/v6/layout.json").read_bytes())
    layout[field] = ["PooledReturns"]
    with pytest.raises(TemplateRegistryError, match="layout_policy_mismatch"):
        _validate_layout(layout, set(AMENDMENT_TABLE_COLUMNS), version="v6")


@pytest.mark.parametrize("table", list(AMENDMENT_TABLE_COLUMNS))
def test_each_required_logical_table_is_required(table: str) -> None:
    layout = json.loads(Path("templates/xlsx/composite-review/v6/layout.json").read_bytes())
    with pytest.raises(ValueError, match="table_set_invalid"):
        _validate_layout(layout, set(AMENDMENT_TABLE_COLUMNS) - {table}, version="v6")


@pytest.mark.parametrize(
    "change", ["archive", "identity", "selection", "revision", "lineage", "scope", "promotion"]
)
def test_custody_cannot_be_borrowed_or_promoted(change: str) -> None:
    wire = unit_amendment_package()
    context = wire["render_context"]
    if change == "archive":
        context.pop("archive")
    elif change == "identity":
        context["archive"].pop("composite_report_identity")
    elif change == "selection":
        # Break aliasing in the artificial fixture before changing only custody.
        context["archive"]["composite_report_identity"]["selection"] = json.loads(
            json.dumps(wire["report_data"]["selection"])
        )
        context["archive"]["composite_report_identity"]["selection"]["composite_id"] = "foreign"
    elif change == "revision":
        context["report_revision_id"] = ""
    elif change == "lineage":
        wire["lineage_refs"] = ["foreign"]
    elif change == "scope":
        context["archive"]["composite_id"] = "foreign"
    else:
        context["archive"]["composite_report_identity"]["publication_state"] = "ATTESTED"
    with pytest.raises(ValueError):
        validate_amendment_custody(RenderPackage.model_validate(wire))
