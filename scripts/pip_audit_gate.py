from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS_PATH = ROOT / "security" / "pip-audit-exceptions.json"
REQUIRED_FIELDS = {
    "id",
    "package",
    "owner",
    "tracking_issue",
    "created_on",
    "expires_on",
    "reason",
    "compensating_controls",
}


class PipAuditExceptionError(RuntimeError):
    pass


def load_active_exceptions(path: Path = EXCEPTIONS_PATH, *, today: date | None = None) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    exceptions = payload.get("exceptions")
    if not isinstance(exceptions, list):
        raise PipAuditExceptionError("pip-audit exception manifest must contain exceptions list")

    active_ids: list[str] = []
    seen: set[str] = set()
    current_date = today or date.today()
    for index, entry in enumerate(exceptions):
        if not isinstance(entry, dict):
            raise PipAuditExceptionError(f"pip-audit exception {index} must be an object")
        missing = sorted(REQUIRED_FIELDS - set(entry))
        if missing:
            joined = ", ".join(missing)
            raise PipAuditExceptionError(
                f"pip-audit exception {entry.get('id', index)} missing field(s): {joined}"
            )
        for field in REQUIRED_FIELDS:
            if not str(entry[field]).strip():
                raise PipAuditExceptionError(f"pip-audit exception {entry['id']} has blank {field}")
        vulnerability_id = str(entry["id"]).strip()
        if vulnerability_id in seen:
            raise PipAuditExceptionError(f"pip-audit exception {vulnerability_id} is duplicated")
        seen.add(vulnerability_id)
        expires_on = date.fromisoformat(str(entry["expires_on"]))
        created_on = date.fromisoformat(str(entry["created_on"]))
        if expires_on < created_on:
            raise PipAuditExceptionError(
                f"pip-audit exception {vulnerability_id} expires before creation"
            )
        if expires_on < current_date:
            raise PipAuditExceptionError(f"pip-audit exception {vulnerability_id} is expired")
        active_ids.append(vulnerability_id)
    return active_ids


def build_pip_audit_command(exception_ids: list[str]) -> list[str]:
    command = [sys.executable, "-m", "pip_audit"]
    for vulnerability_id in exception_ids:
        command.extend(["--ignore-vuln", vulnerability_id])
    return command


def main() -> None:
    exception_ids = load_active_exceptions()
    print(
        "pip-audit governed exceptions active: "
        + (", ".join(exception_ids) if exception_ids else "none"),
        flush=True,
    )
    subprocess.run(build_pip_audit_command(exception_ids), check=True)


if __name__ == "__main__":
    try:
        main()
    except PipAuditExceptionError as exc:
        raise SystemExit(str(exc)) from exc
