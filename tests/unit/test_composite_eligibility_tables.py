"""All frozen cells are reconstructed from source, independently of supplied tables."""

import json

import pytest
from eligibility_fixtures import producer_package

from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.services.composite_workbook.eligibility_tables import validate_eligibility_tables


@pytest.mark.parametrize("kind", ["evaluated_only", "published"])
def test_complete_supplier_table_population_and_exact_cells(kind: str) -> None:
    data = producer_package(kind)["report_data"]
    content = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    validate_eligibility_tables(content, data)


def test_exact_eight_table_order_cannot_be_relabelled() -> None:
    data = producer_package()["report_data"]
    data["tables"].reverse()
    content = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="table_population_conflict"):
        validate_eligibility_tables(content, data)


@pytest.mark.parametrize("kind", ["evaluated_only", "published"])
@pytest.mark.parametrize(
    "change",
    [
        "missing_row",
        "duplicate_row",
        "extra_row",
        "missing_cell",
        "pointer",
        "value",
        "availability",
        "reasons",
        "precision",
        "title",
        "disclosure",
    ],
)
def test_refuses_incomplete_or_forged_source_projection(kind: str, change: str) -> None:
    data = producer_package(kind)["report_data"]
    table = next(item for item in data["tables"] if item["table_id"] == "EligibilityAssessments")
    cell = table["rows"][0]["cells"]["ratio"]
    if change == "missing_row":
        table["rows"].pop()
    elif change == "duplicate_row":
        table["rows"].append(table["rows"][0])
    elif change == "extra_row":
        table["rows"].append(dict(table["rows"][0], row_id="extra"))
    elif change == "missing_cell":
        del table["rows"][0]["cells"]["ratio"]
    elif change == "pointer":
        cell["source_pointer"] = table["rows"][0]["cells"]["numerator"]["source_pointer"]
        cell["canonical_value"] = table["rows"][0]["cells"]["numerator"]["canonical_value"]
    elif change == "value":
        cell["canonical_value"] = "0.10"
    elif change == "availability":
        cell["availability"] = "UNAVAILABLE"
    elif change == "reasons":
        cell["reason_codes"] = ["invented"]
    elif change == "precision":
        next(column for column in table["columns"] if column["column_id"] == "ratio")[
            "display_decimal_places"
        ] = 2
    elif change == "title":
        table["title"] = "Official eligibility"
    else:
        data["report_facts"]["disclosures"][0]["text"] = "Officially attested"
    content = CompositeEligibilityContent.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="composite_eligibility_.*conflict"):
        validate_eligibility_tables(content, data)
