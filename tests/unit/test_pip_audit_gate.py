from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.pip_audit_gate import (
    PipAuditExceptionError,
    build_pip_audit_command,
    load_active_exceptions,
)


def _write_manifest(path: Path, exceptions: list[dict[str, str]]) -> None:
    path.write_text(json.dumps({"exceptions": exceptions}), encoding="utf-8")


def _exception(**overrides: str) -> dict[str, str]:
    payload = {
        "id": "CVE-2099-0001",
        "package": "starlette",
        "owner": "lotus-platform-governance",
        "tracking_issue": "https://github.com/sgajbi/lotus-render/issues/30",
        "created_on": "2026-07-05",
        "expires_on": "2026-08-31",
        "reason": "temporary dependency constraint",
        "compensating_controls": "internal service boundary",
    }
    payload.update(overrides)
    return payload


def test_pip_audit_gate_loads_active_exceptions(tmp_path: Path) -> None:
    manifest = tmp_path / "exceptions.json"
    _write_manifest(manifest, [_exception()])

    assert load_active_exceptions(manifest, today=date(2026, 7, 5)) == ["CVE-2099-0001"]


def test_pip_audit_gate_rejects_expired_exception(tmp_path: Path) -> None:
    manifest = tmp_path / "exceptions.json"
    _write_manifest(manifest, [_exception(created_on="2026-06-01", expires_on="2026-07-01")])

    with pytest.raises(PipAuditExceptionError, match="expired"):
        load_active_exceptions(manifest, today=date(2026, 7, 5))


def test_pip_audit_gate_rejects_missing_owner(tmp_path: Path) -> None:
    manifest = tmp_path / "exceptions.json"
    entry = _exception()
    del entry["owner"]
    _write_manifest(manifest, [entry])

    with pytest.raises(PipAuditExceptionError, match="owner"):
        load_active_exceptions(manifest, today=date(2026, 7, 5))


def test_pip_audit_gate_builds_ignore_command() -> None:
    command = build_pip_audit_command(["CVE-2099-0001", "PYSEC-2099-0002"])

    assert command[-4:] == [
        "--ignore-vuln",
        "CVE-2099-0001",
        "--ignore-vuln",
        "PYSEC-2099-0002",
    ]


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_MANIFEST = REPO_ROOT / "security" / "pip-audit-exceptions.json"


def test_committed_manifest_claims_no_exception() -> None:
    """The audit must pass on its own merits, with nothing suppressed."""

    assert load_active_exceptions(COMMITTED_MANIFEST, today=date(2026, 8, 26)) == []
    assert build_pip_audit_command([])[-1].endswith("pip_audit")


def test_empty_exception_list_is_valid_and_suppresses_nothing(tmp_path: Path) -> None:
    """An empty list is the intended steady state, not a malformed manifest."""

    manifest = tmp_path / "exceptions.json"
    _write_manifest(manifest, [])

    assert load_active_exceptions(manifest, today=date(2026, 8, 26)) == []
    assert "--ignore-vuln" not in build_pip_audit_command([])


def test_manifest_without_an_exceptions_list_fails_closed(tmp_path: Path) -> None:
    """A malformed manifest must never read as 'nothing to suppress'."""

    manifest = tmp_path / "exceptions.json"
    manifest.write_text(json.dumps({"policy_version": "1.0.0"}), encoding="utf-8")

    with pytest.raises(PipAuditExceptionError):
        load_active_exceptions(manifest, today=date(2026, 8, 26))


def test_every_declared_exception_stays_governed_and_current() -> None:
    """Governance still binds if an exception is ever added back."""

    payload = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))

    for entry in payload["exceptions"]:
        assert entry["owner"]
        assert entry["tracking_issue"].startswith("https://github.com/sgajbi/lotus-render/issues/")
        assert date.fromisoformat(entry["expires_on"]) >= date(2026, 8, 26)
        assert entry["reason"]
        assert entry["compensating_controls"]
