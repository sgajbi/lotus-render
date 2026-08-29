"""Run Vulture only after proving that the governed Python tree is non-empty."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = ("src", "tests")


def _resolved_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def python_files(paths: Sequence[str]) -> tuple[Path, ...]:
    """Return the unique Python files Vulture will inspect."""

    files: set[Path] = set()
    for raw_path in paths:
        path = _resolved_path(raw_path)
        if path.is_file() and path.suffix == ".py":
            files.add(path)
            continue
        if path.is_dir():
            files.update(
                candidate
                for candidate in path.rglob("*.py")
                if "__pycache__" not in candidate.parts
            )
    return tuple(sorted(files))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed dead-code gate")
    parser.add_argument("--path", action="append", dest="paths")
    parser.add_argument("--min-confidence", type=int, default=80)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = tuple(args.paths or DEFAULT_PATHS)
    inspected = python_files(paths)
    if not inspected:
        print(
            "Dead-code gate failed: inspected 0 Python files under " + ", ".join(paths) + ".",
            file=sys.stderr,
        )
        return 1

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vulture",
            *paths,
            "--min-confidence",
            str(args.min_confidence),
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
