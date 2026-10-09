"""Consumer admission of pinned monthly corrections, without producer execution claims."""

import json

import pytest
from amendment_fixtures import amendment_data

from app.services.composite_workbook.amendment_tables import amendment_rows
from app.services.composite_workbook.source_cells import validate_dataset


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("kind", ["evaluated", "published"])
def test_pinned_monthly_amendment_dataset_is_admitted(version: str, kind: str) -> None:
    data = amendment_data(version, kind)
    content = validate_dataset(data)
    assert content.model_dump(mode="json") == data


@pytest.mark.parametrize("kind", ["evaluated", "published"])
def test_sorted_pinned_json_replay_preserves_table_occurrence_order(kind: str) -> None:
    original = amendment_data(kind=kind)
    replay = json.loads(json.dumps(original, sort_keys=True))
    assert validate_dataset(replay).model_dump(mode="json") == original


def test_amendment_row_recipe_continues_global_ordinal_across_months() -> None:
    # Projection-only control: duplicating a source here does not claim a valid
    # multi-month dataset. This isolates Report's global row-identity convention.
    data = amendment_data()
    one_month = amendment_rows(data)
    data["source_months"] *= 2
    rows = amendment_rows(data)
    assert rows[: len(one_month)] == one_month
    assert rows[len(one_month)][0] == f"m1:a{len(one_month)}"
    assert [row_id.split(":a")[1] for row_id, _ in rows] == [
        str(ordinal) for ordinal in range(len(rows))
    ]
