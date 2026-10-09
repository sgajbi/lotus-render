"""Independent JSON/Excel round trips for large metadata without financial-cell splitting."""

import hashlib
import io
import json

import openpyxl
import pytest

from app.services.composite_workbook.identity import identity_rows
from app.services.composite_workbook.literal_writer import LiteralTable, write_literal_workbook


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


@pytest.mark.parametrize("characters", [32_765, 32_766])
def test_identity_boundary_keeps_small_json_and_fragments_one_character_over(
    characters: int,
) -> None:
    value = "a" * characters
    canonical = json.dumps(value, ensure_ascii=True, sort_keys=True)
    rows = list(identity_rows({"render_context": value}))
    if characters == 32_765:
        assert rows == [("render_context", canonical)]
    else:
        assert rows[0][0] == "render_context__chunks"
        assert json.loads(rows[0][1])["utf8_bytes"] == len(canonical)


@pytest.mark.parametrize(
    "value",
    ["a" * 60_148, '\\"' * 30_000, "汉字🚀\x00" * 8_000],
    ids=["ascii", "escaped", "unicode"],
)
def test_excel_parser_recovers_every_metadata_character_and_exact_json(value: str) -> None:
    fields = {"snapshot_id": "unchanged", "render_context": {"__chunks": value}}
    rows = list(identity_rows(fields))
    artifact = write_literal_workbook(
        [LiteralTable("ArtifactIdentity", ("Field", "Exact JSON value"), rows)]
    )
    workbook = openpyxl.load_workbook(io.BytesIO(artifact))
    stored = [
        tuple(_text(cell) for cell in row)
        for row in list(workbook["ArtifactIdentity_1"].values)[1:]
    ]
    assert stored[0] == ("snapshot_id", '"unchanged"')
    descriptor = json.loads(stored[1][1])
    assert set(descriptor) == {"encoding", "count", "utf8_bytes", "sha256"}
    assert descriptor["encoding"] == "ordered_json_text_v1"
    fragments = stored[2:]
    assert len(fragments) == descriptor["count"]
    assert [row[0] for row in fragments] == [
        f"render_context__chunk_{index:06d}" for index in range(len(fragments))
    ]
    reconstructed = "".join(json.loads(row[1]) for row in fragments)
    canonical = json.dumps(fields["render_context"], ensure_ascii=True, sort_keys=True)
    assert reconstructed == canonical
    assert len(reconstructed.encode("utf-8")) == descriptor["utf8_bytes"]
    assert hashlib.sha256(reconstructed.encode("utf-8")).hexdigest() == descriptor["sha256"]
    assert json.loads(reconstructed) == fields["render_context"]
    assert all(len(row[1].encode("utf-16-le")) // 2 <= 32_767 for row in stored)
    assert all(
        cell.data_type == "s" and cell.hyperlink is None
        for row in workbook["ArtifactIdentity_1"]
        for cell in row
    )
    workbook.close()


@pytest.mark.parametrize("key", ["render_context__chunks", "render_context__chunk_000000"])
def test_reserved_render_owned_field_names_refuse_collision(key: str) -> None:
    with pytest.raises(ValueError, match="artifact_identity_reserved_field"):
        list(identity_rows({key: "ambiguous"}))
