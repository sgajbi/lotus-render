"""An approved layout cannot claim a storage or rounding policy the engine does not execute."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.templates.registry import TemplateRegistryError
from app.services.composite_workbook.rendering import _validate_layout


def _layout() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        Path("templates/xlsx/composite-review/v1/layout.json").read_text()
    )
    return value


def test_declared_layout_policy_and_bounds_match_the_actual_adapter() -> None:
    layout = _layout()
    _validate_layout(layout, set(layout["required_tables"]) | {"MonthlyReturns"})


@pytest.mark.parametrize(
    "field",
    [
        "layout_version",
        "financial_storage",
        "display_rounding_mode",
        "metadata_created",
        "max_total_rows",
        "max_total_cells",
        "max_total_text_bytes",
        "max_output_bytes",
    ],
)
def test_unimplemented_or_mismatched_layout_policy_refuses(field: str) -> None:
    layout = _layout()
    names = set(layout["required_tables"]) | {"MonthlyReturns"}
    layout[field] = "different"
    with pytest.raises(TemplateRegistryError):
        _validate_layout(layout, names)
