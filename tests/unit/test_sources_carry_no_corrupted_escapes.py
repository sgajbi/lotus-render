"""No source file carries a control byte where an escape was written.

A backslash escape written through a shell heredoc is interpreted by the
shell before the file is created, so `\\b` in a regex becomes a literal
backspace (0x08), `\\t` a tab, `\\n` a newline. The result is invisible:
terminals do not render 0x08, `git diff` shows nothing unusual, and every
re-reading of the source looks correct.

The consequence is worse than cosmetic. `tests/unit/test_no_machine_values
_reach_a_page.py` carried `re.compile(r"<BS>[a-z]...")` where `\\b` was
meant, so its call-syntax pattern could match only text containing a
literal backspace -- which no rendered document contains. The guard that
exists to catch Typst call syntax reaching a client page could never fire,
and had been passing for exactly that reason.

Whether a file is corrupt is a question about its BYTES, so this test asks
the bytes. It is the cheapest check in the suite and the only one that can
see this class at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED_DIRECTORIES = ("src", "tests", "scripts", "quality", "templates", ".github")
SCANNED_SUFFIXES = {".py", ".json", ".yml", ".yaml", ".typ", ".ini", ".toml"}


#: Bytes no source file in this repository has a legitimate reason to hold.
#: Tab (0x09), newline (0x0a) and carriage return (0x0d) are excluded because
#: they are ordinary whitespace; everything else below 0x20 is a control byte
#: that arrived by accident.
def _forbidden(byte: int) -> bool:
    return byte < 0x09 or byte in (0x0B, 0x0C) or 0x0D < byte < 0x20


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for directory in SCANNED_DIRECTORIES:
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        files.extend(
            path
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix in SCANNED_SUFFIXES
        )
    return files


def test_the_scan_covers_a_meaningful_number_of_files() -> None:
    """A zero-input scan passes by finding nothing, which is the same
    result as a clean tree and tells a reader nothing."""

    assert len(_scanned_files()) > 100


def test_no_source_file_holds_a_stray_control_byte() -> None:
    offenders: list[str] = []
    for path in _scanned_files():
        raw = path.read_bytes()
        positions = [index for index, byte in enumerate(raw) if _forbidden(byte)]
        if positions:
            index = positions[0]
            line = raw[:index].count(b"\n") + 1
            offenders.append(
                f"{path.relative_to(REPO_ROOT)}:{line} holds {hex(raw[index])} "
                f"({len(positions)} total) - an escape was probably written "
                "through a shell heredoc and interpreted before the file was created"
            )

    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize("byte", [0x08, 0x00, 0x1B])
def test_the_scan_would_catch_a_corrupted_file(tmp_path: Path, byte: int) -> None:
    """Prove the check can fail. A guard whose failure path has never run is
    indistinguishable from one that cannot fail -- which is precisely the
    defect this file exists to catch, one level up."""

    corrupted = tmp_path / "corrupted.py"
    corrupted.write_bytes(b'PATTERN = re.compile(r"' + bytes([byte]) + b'[a-z]+")')
    raw = corrupted.read_bytes()

    assert [index for index, value in enumerate(raw) if _forbidden(value)]
