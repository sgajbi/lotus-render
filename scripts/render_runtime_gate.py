"""Assert the Typst render runtime is present before the suites that depend on it.

The golden tests compile real PDFs, but nothing in CI ever declared that dependency: the
compiles happened only because GitHub's runner image ships Docker on PATH, so
``_build_compile_command`` found it and pulled the pinned Typst image. A runner image
without Docker would turn those compiles into confusing collection errors rather than a
named failure, and a change that silently stopped reaching the runtime would look like a
faster green lane (issue #109).

This gate makes the dependency explicit and fails with the reason when it is absent.
"""

from __future__ import annotations

import shutil
import sys


def main() -> int:
    docker = shutil.which("docker")
    typst = shutil.which("typst")
    if docker is None and typst is None:
        print(
            "Render runtime gate failed: neither docker nor typst is on PATH, so the golden "
            "suites cannot compile a real PDF. Install the Typst CLI or provide a Docker "
            "runtime for this job.",
            file=sys.stderr,
        )
        return 1
    selected = "docker" if docker is not None else "typst"
    print(f"Render runtime gate passed: compiling through {selected} ({docker or typst}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
