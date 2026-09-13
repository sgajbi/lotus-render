"""`scripts/read_github_api_answer.py`: the dispatcher's one reader of what GitHub said.

The bodies here are the shapes `gh api` really leaves on stdout, measured against the
live API: a refusal is `{"message": ..., "documentation_url": ..., "status": "404"}`
with the status as a JSON STRING, and a ref lookup that succeeds is the ref object with
`object.sha`. A transport failure leaves nothing on stdout at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.read_github_api_answer import read_field

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "read_github_api_answer.py"

NOT_FOUND = (
    '{"message":"Not Found","documentation_url":"https://docs.github.com/rest","status":"404"}'
)
SCOPE_REFUSAL = (
    '{"message":"Resource not accessible by integration",'
    '"documentation_url":"https://docs.github.com/rest","status":"403"}'
)
REF = (
    '{"ref":"refs/tags/main-releasability-abc","node_id":"x",'
    '"url":"https://api.github.com/x","object":{"sha":"abc","type":"commit","url":"u"}}'
)


@pytest.mark.parametrize(
    ("body", "field_path", "expected"),
    [
        (NOT_FOUND, "status", "404"),
        (SCOPE_REFUSAL, "status", "403"),
        (SCOPE_REFUSAL, "message", "Resource not accessible by integration"),
        (REF, "object.sha", "abc"),
        # Defensive: a numeric status reads the same as the string GitHub sends today.
        ('{"status": 404}', "status", "404"),
    ],
)
def test_reads_the_field_github_wrote(body: str, field_path: str, expected: str) -> None:
    assert read_field(body, field_path) == expected


@pytest.mark.parametrize(
    ("body", "field_path"),
    [
        ("", "status"),  # transport failure: no answer at all
        ("<html>502 Bad Gateway</html>", "status"),  # a proxy answered, GitHub did not
        ("[]", "status"),  # JSON, but not an object
        (NOT_FOUND, "object.sha"),  # a refusal carries no ref
        (REF, "status"),  # a success carries no status field
        (REF, "object"),  # a container is not an answer
        ('{"status": true}', "status"),  # nor is a boolean
        ('{"status": null}', "status"),
    ],
)
def test_anything_that_is_not_the_field_reads_as_absent(body: str, field_path: str) -> None:
    assert read_field(body, field_path) == ""


def _run(field_path: str, body_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), field_path, str(body_file)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_command_prints_the_value_and_exits_zero(tmp_path: Path) -> None:
    body = tmp_path / "create-ref.stdout"
    body.write_text(SCOPE_REFUSAL, encoding="utf-8")

    completed = _run("message", body)

    assert completed.returncode == 0
    assert completed.stdout.strip() == "Resource not accessible by integration"


def test_an_empty_or_missing_body_prints_nothing_and_still_exits_zero(tmp_path: Path) -> None:
    """`$(...)` under `set -e` aborts the caller on a non-zero exit, before it can emit
    the diagnostic that names the unclassifiable answer; absence is an empty value."""

    empty = tmp_path / "lookup-ref.stdout"
    empty.write_text("", encoding="utf-8")
    missing = tmp_path / "never-written.stdout"

    for body in (empty, missing):
        completed = _run("status", body)
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""


def test_wrong_arity_is_a_usage_error() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "status"], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 2
    assert "usage" in completed.stderr
