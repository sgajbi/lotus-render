"""Reject source modules that exceed the governed maintainability limit."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / "src"
DEFAULT_MAX_LINES = int(os.getenv("SOURCE_FILE_MAX_LINES", "450"))


@dataclass(frozen=True)
class SourceSizeViolation:
    path: Path
    lines: int


def find_source_size_violations(
    source_root: Path,
    *,
    max_lines: int,
) -> list[SourceSizeViolation]:
    violations: list[SourceSizeViolation] = []
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > max_lines:
            violations.append(SourceSizeViolation(path=path, lines=lines))
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    violations = find_source_size_violations(args.source_root, max_lines=args.max_lines)
    if violations:
        print(f"Source size gate failed: maximum {args.max_lines} lines per Python source file.")
        for violation in violations:
            print(f"- {violation.path}: {violation.lines} lines")
        return 1
    print(f"Source size gate passed: no Python source file exceeds {args.max_lines} lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
