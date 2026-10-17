"""Check every source coordinate and copied side cell without financial arithmetic."""

from copy import deepcopy
from typing import Any

from app.contracts.composite_notice import SOURCE_TABLES
from app.services.composite_workbook.notice_hashes import canonical, require


def source_coordinates(
    payload: dict[str, Any], side: str
) -> dict[tuple[str, str, str], dict[str, Any]]:
    coordinates = {}
    for ti, table in enumerate(payload["tables"]):
        for ri, row in enumerate(table["rows"]):
            for ci, column in enumerate(table["columns"]):
                key = (table["table_id"], row["row_id"], column["column_id"])
                require(key not in coordinates, "duplicate_coordinate")
                coordinates[key] = {
                    "generation": side,
                    "table_index": ti,
                    "row_index": ri,
                    "column_index": ci,
                    "table_id": key[0],
                    "row_id": key[1],
                    "column_id": key[2],
                    "source_pointer": row["cells"][key[2]]["source_pointer"],
                }
    return coordinates


def expected_pair_index(data: dict[str, Any]) -> list[dict[str, Any]]:
    before, after = (
        source_coordinates(data["generations"][side]["payload"], side)
        for side in ("before", "after")
    )
    ranks = {
        (table["table_id"], c["column_id"]): i
        for table in data["generations"]["before"]["payload"]["tables"]
        for i, c in enumerate(table["columns"])
    }
    keys = sorted(
        before.keys() | after.keys(),
        key=lambda k: (
            SOURCE_TABLES.index(k[0]),
            k[1],
            ranks[(k[0], k[2])],
        ),
    )
    result = []
    for key in keys:
        row_id = canonical(list(key))
        require(len(row_id) <= 256, "coordinate_row_id_limit")
        presence = (
            "BOTH_PRESENT"
            if key in before and key in after
            else ("BEFORE_ONLY" if key in before else "AFTER_ONLY")
        )
        result.append(
            {
                "row_id": row_id,
                "coordinate": dict(zip(("table_id", "row_id", "column_id"), key, strict=True)),
                "presence": presence,
                "before_ref": before.get(key),
                "after_ref": after.get(key),
            }
        )
    return result


def validate_side_tables(data: dict[str, Any]) -> None:
    expected = []
    for side, prefix in (("before", "Before_"), ("after", "After_")):
        for source in data["generations"][side]["payload"]["tables"]:
            table = deepcopy(source)
            table["table_id"] = prefix + source["table_id"]
            for row in table["rows"]:
                for cell in row["cells"].values():
                    cell["source_pointer"] = (
                        "/generations/" + side + "/payload" + cell["source_pointer"]
                    )
            expected.append(table)
    require(data["tables"][:28] == expected, "side_projection")
    require(data["pair_index"] == expected_pair_index(data), "coordinate_union")
