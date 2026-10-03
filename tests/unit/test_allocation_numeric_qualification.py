"""An unavailable contributor is not a measured zero, even beside a known one."""

import io
import json
import re
from pathlib import Path

import pypdf
import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.portfolio_charts import allocation_items_from_rows
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService
from app.services.typst_tables import (
    composition_note,
    render_allocation_breakdown_rows,
    render_allocation_chart_section,
    render_allocation_dimension_blocks,
)

UNKNOWN = [
    None,
    "",
    "-",
    "--",
    "N/A",
    "not_available",
    "Not available",
    "null",
    "unknown",
    "bad number",
    "NaN",
    "Infinity",
    "-Infinity",
    False,
    True,
]


def report(rows: object, posture: str = "ready") -> dict[str, object]:
    return {
        "allocation_presentation": {
            "dimensions": [
                {"dimension": "asset_class", "package_key": "by_asset_class", "posture": posture}
            ]
        },
        "allocation_breakdowns": {"by_asset_class": rows},
    }


@pytest.mark.parametrize("unknown", UNKNOWN)
@pytest.mark.parametrize("mixed", [False, True])
def test_unknown_survives_bucket_aggregation(unknown: object, mixed: bool) -> None:
    rows = [{"name": "Bond", "weight_pct": unknown, "market_value": unknown}]
    if mixed:
        rows.insert(0, {"name": "Bond", "weight_pct": "25%", "market_value": "25"})
    emitted = render_allocation_breakdown_rows(rows)
    assert '"Bond", "Not available", "Not available"' in emitted
    assert "0.00" not in emitted
    assert "coverage is not available" in composition_note(rows)
    assert allocation_items_from_rows(rows) == []


def test_absent_fields_and_explicit_unknown_do_not_fall_back_to_legacy_weight() -> None:
    for row in [{"name": "Bond"}, {"name": "Bond", "weight_pct": None, "weight": "25"}]:
        emitted = render_allocation_breakdown_rows([row])
        assert '"Bond", "Not available", "Not available"' in emitted
        assert "0.00" not in emitted


@pytest.mark.parametrize("zero", [0, "0", "0.00", "0.00%"])
def test_supplied_zero_remains_measured(zero: object) -> None:
    rows = [{"name": "Zero", "weight_pct": zero, "weight": "99", "market_value": 0}]
    assert '"Zero", "0.00%", "0.00"' in render_allocation_breakdown_rows(rows)
    assert "covers 0.00%" in composition_note(rows)
    assert "Not available" not in render_allocation_breakdown_rows(rows)


def test_fields_are_qualified_independently_and_unknown_value_is_not_charted_zero() -> None:
    rows = [{"name": "Bond", "weight_pct": "20%", "market_value": "Not available"}]
    assert '"Bond", "20.00%", "Not available"' in render_allocation_breakdown_rows(rows)
    assert "covers 20.00%" in composition_note(rows)
    assert allocation_items_from_rows(rows) == []
    section = render_allocation_chart_section(report(rows))
    assert "centre-value" not in section
    assert "not available" in section
    assert "Bond" in render_allocation_dimension_blocks(report(rows))


def test_unknown_weight_preserves_known_value_without_numeric_coverage() -> None:
    rows = [{"name": "Bond", "market_value": "25"}]
    assert '"Bond", "Not available", "25.00"' in render_allocation_breakdown_rows(rows)
    assert "covers 0.00%" not in composition_note(rows)
    assert allocation_items_from_rows(rows) == []


def test_positive_weight_with_supplied_zero_is_a_valid_slice() -> None:
    items = allocation_items_from_rows(
        [{"name": "Zero value", "weight_pct": "20", "market_value": 0}]
    )
    assert len(items) == 1
    assert items[0].market_value == 0


def test_same_bucket_unknown_cannot_disappear_from_known_chart_entry() -> None:
    rows = [
        {"name": "Bond", "weight_pct": "25", "market_value": "25"},
        {"name": "Bond", "weight_pct": None, "market_value": None},
        {"name": "Equity", "weight_pct": "50", "market_value": "50"},
    ]
    assert [item.label for item in allocation_items_from_rows(rows)] == ["Equity"]
    section = render_allocation_chart_section(report(rows))
    assert 'centre-value: "50"' in section
    assert "not available" in section
    assert "Bond" in render_allocation_dimension_blocks(report(rows))


def test_unknown_bucket_is_visible_when_row_capacity_is_exceeded() -> None:
    rows: list[dict[str, object]] = [
        {"name": f"Known {i}", "weight_pct": "10", "market_value": "10"} for i in range(10)
    ]
    rows.append({"name": "Unknown bond", "weight_pct": None, "market_value": None})
    assert "Unknown bond" in render_allocation_breakdown_rows(rows)


def test_folding_note_names_only_the_fully_supplied_groups_it_folds() -> None:
    rows: list[dict[str, object]] = [
        {"name": f"Known {i}", "weight_pct": str(i), "market_value": str(i)}
        for i in range(10, 0, -1)
    ]
    rows.append({"name": "Small unknown", "weight_pct": "0.01", "market_value": None})
    assert "Small unknown" in render_allocation_breakdown_rows(rows)
    assert "3 smallest fully supplied groups" in composition_note(rows)
    assert "2 smallest groups" in composition_note(rows[:-1])


@pytest.mark.parametrize("posture", ["empty", "unavailable"])
def test_report_posture_remains_authoritative(posture: str) -> None:
    data = report([{"name": "Hidden", "weight_pct": "100", "market_value": "100"}], posture)
    assert "Hidden" not in render_allocation_dimension_blocks(data)
    assert "centre-value" not in render_allocation_chart_section(data)


def test_signed_and_finite_values_remain_supplied() -> None:
    rows = [
        {"name": "Long", "weight_pct": "120", "market_value": "120"},
        {"name": "Short", "weight_pct": "-20", "market_value": "-20"},
    ]
    table = render_allocation_breakdown_rows(rows)
    assert '"Long", "120.00%", "120.00"' in table
    assert '"Short", "-20.00%", "-20.00"' in table
    assert 'centre-value: "120"' in render_allocation_chart_section(report(rows))


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([{"name": "Qualified bond"}], "Qualified bond Not available Not available"),
        (
            [{"name": "Qualified bond", "weight_pct": "0", "market_value": "0"}],
            "Qualified bond 0.00% 0.00",
        ),
        (
            [
                {"name": "Qualified bond", "weight_pct": "25", "market_value": "25"},
                {"name": "Qualified bond", "weight_pct": "Not available", "market_value": None},
            ],
            "Qualified bond Not available Not available",
        ),
        (
            [{"name": "Qualified bond", "weight_pct": "20", "market_value": "not_available"}],
            "Qualified bond 20.00% Not available",
        ),
    ],
)
def test_qualification_reaches_actual_compiled_pdf(rows: object, expected: str) -> None:
    raw = json.loads(Path("tests/golden/portfolio-review/v2/render-package.json").read_text())
    raw["report_data"].update(report(rows))
    settings = Settings()
    intake = RenderIntakeService(
        TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    )
    package = RenderPackage.model_validate(raw)
    intake.validate_package(package)
    result = TypstRenderService(settings, intake).render(package)
    assert result.attempt.status.value == "rendered"
    pages = pypdf.PdfReader(io.BytesIO(result.artifact_bytes)).pages
    text = re.sub(r"\s+", " ", " ".join(page.extract_text() for page in pages))
    assert expected in text
    if "Not available" in expected:
        assert "Charted total 0" not in text
        assert "Chart values are not available" in text


def test_known_contributors_aggregate_without_losing_decimal_precision() -> None:
    rows = [
        {"name": "Cash", "weight_pct": "0.1", "market_value": "10000000000000.01"},
        {"name": "Cash", "weight_pct": "0.2", "market_value": "0.02"},
    ]
    assert '"Cash", "0.30%", "10,000,000,000,000.03"' in render_allocation_breakdown_rows(rows)
    assert str(allocation_items_from_rows(rows)[0].market_value) == "10000000000000.03"


@pytest.mark.parametrize("reverse", [False, True])
def test_unknown_value_does_not_remove_supplied_aggregate_weight(reverse: bool) -> None:
    rows = [
        {"name": "Bond", "weight_pct": "25", "market_value": "25"},
        {"name": "Bond", "weight_pct": "20", "market_value": None},
    ]
    if reverse:
        rows.reverse()
    assert '"Bond", "45.00%", "Not available"' in render_allocation_breakdown_rows(rows)
    assert "covers 45.00%" in composition_note(rows)
    assert allocation_items_from_rows(rows) == []
