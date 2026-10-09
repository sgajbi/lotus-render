"""Consumer admission of pinned monthly corrections, without producer execution claims."""

import json

import pytest
from amendment_fixtures import amendment_data

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
