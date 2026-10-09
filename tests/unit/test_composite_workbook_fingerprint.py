"""Only ZIP packaging may vary; every exact member identity remains sealed."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from app.services.composite_workbook.fingerprint import DOMAIN, workbook_content_fingerprint

MEMBERS = {
    "xl/worksheets/sheet1.xml": b'<cell id="000000000000000001"><value>0.0302</value></cell>',
    "xl/sharedStrings.xml": b"<text>pin-original</text>",
}


def _package(members: dict[str, bytes], *, packaging: bool = False) -> bytes:
    target = io.BytesIO()
    with ZipFile(target, "w") as archive:
        names = sorted(members, reverse=packaging)
        for name in names:
            info = ZipInfo(
                name, date_time=(2026, 1, 1, 0, 0, 0) if packaging else (1980, 1, 1, 0, 0, 0)
            )
            info.create_system = 3 if packaging else 0
            info.external_attr = 0o600 << 16 if packaging else 0o644 << 16
            info.compress_type = ZIP_DEFLATED if packaging else ZIP_STORED
            archive.writestr(info, members[name])
    return target.getvalue()


def test_only_container_drift_preserves_exact_member_fingerprint() -> None:
    first, second = _package(MEMBERS), _package(MEMBERS, packaging=True)
    assert first != second and hashlib.sha256(first).digest() != hashlib.sha256(second).digest()
    assert workbook_content_fingerprint(first) == workbook_content_fingerprint(second)
    assert DOMAIN == b"lotus-render/composite-xlsx-members/v1\x00"


def test_committed_workbook_matches_its_banked_member_fingerprint() -> None:
    fixtures = json.loads(Path("tests/golden/producer-fixtures.v1.json").read_text())["fixtures"]
    for fixture in fixtures:
        if fixture.get("output_format") == "xlsx":
            artifact = Path(fixture["expected_artifact_path"]).read_bytes()
            expected = fixture["bounded_determinism_fingerprint"]
            assert workbook_content_fingerprint(artifact) == expected


@pytest.mark.parametrize("change", ["membership", "name", "number", "pin", "formula", "xml"])
def test_actual_member_or_content_change_never_normalizes_away(change: str) -> None:
    changed = dict(MEMBERS)
    if change == "membership":
        changed["xl/new.xml"] = b"<new/>"
    elif change == "name":
        changed["xl/renamed.xml"] = changed.pop("xl/sharedStrings.xml")
    elif change == "pin":
        changed["xl/sharedStrings.xml"] = b"<text>pin-corrected</text>"
    elif change == "number":
        changed["xl/worksheets/sheet1.xml"] = MEMBERS["xl/worksheets/sheet1.xml"].replace(
            b"0.0302", b"0.032"
        )
    elif change == "formula":
        changed["xl/worksheets/sheet1.xml"] += b"<f>SUM(A1:A2)</f>"
    else:
        changed["xl/worksheets/sheet1.xml"] += b"\n"
    assert workbook_content_fingerprint(_package(changed)) != workbook_content_fingerprint(
        _package(MEMBERS)
    )


def test_length_framing_distinguishes_ambiguous_plain_concatenation() -> None:
    assert workbook_content_fingerprint(_package({"a": b"bc"})) != workbook_content_fingerprint(
        _package({"ab": b"c"})
    )


def test_duplicate_member_names_refuse() -> None:
    target = io.BytesIO()
    with ZipFile(target, "w") as archive:
        archive.writestr("duplicate", b"one")
        with pytest.warns(UserWarning):
            archive.writestr("duplicate", b"two")
    with pytest.raises(ValueError, match="member_duplicated"):
        workbook_content_fingerprint(target.getvalue())
