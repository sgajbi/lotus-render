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
