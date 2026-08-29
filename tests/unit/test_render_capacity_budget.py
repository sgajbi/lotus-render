"""The concurrency limit, the per-compile bound and the container limit are one budget.

`docker-compose.yml` says "Raise these together with the concurrency limit", and nothing
enforces it. The three numbers live in three files and are related by arithmetic:

    concurrency_limit x per_compile_bound + service_headroom <= container_memory_limit

Today that holds with room to spare. Raising `render_execution_concurrency_limit` from 2
to 3 alone breaks it: three compiles may hold 1536 MB inside a 1500 MB container, so the
container is killed rather than the offending compile -- the exact failure #128 exists to
prevent, reintroduced from the configuration side instead of the code side.

A comment asking a person to remember is not a bound. This is.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.settings import Settings
from app.services.typst_rendering import COMPILE_ADDRESS_SPACE_LIMIT_KB, DOCKER_ISOLATION_FLAGS

COMPOSE_FILE = Path("docker-compose.yml")

# What the service itself needs while every compile slot is full: the CPython runtime,
# uvicorn and FastAPI, plus a rendered artifact held in memory and its base64 encoding on
# the way out. The largest document measured in #168 was 5.4 MB, so the artifact side is
# tens of megabytes; this is a floor for the runtime, not a measurement of a peak.
SERVICE_MEMORY_HEADROOM_MB = 256


def _compose_memory_limit_mb() -> int:
    match = re.search(
        r"^\s*mem_limit:\s*(\d+)m\s*$", COMPOSE_FILE.read_text(encoding="utf-8"), re.M
    )
    assert match is not None, f"no mem_limit found in {COMPOSE_FILE}"
    return int(match.group(1))


def _docker_compile_limit_mb() -> int:
    flags = list(DOCKER_ISOLATION_FLAGS)
    value = flags[flags.index("--memory") + 1]
    assert value.endswith("m"), value
    return int(value[:-1])


def test_the_two_compile_branches_bound_a_compile_identically() -> None:
    """The container branch and the in-process branch must grant the same ceiling.

    They are set in different units in different places, so they can drift apart while
    each looks correct on its own -- and then a compile that fits in development fails in
    production, or the reverse.
    """

    assert _docker_compile_limit_mb() * 1024 == COMPILE_ADDRESS_SPACE_LIMIT_KB


def test_every_compile_slot_can_be_full_without_killing_the_container() -> None:
    """The bound is per compile; the risk is that they are all held at once.

    #128 moved the failure from "the whole service dies" to "this render fails". That
    holds only while the container can actually accommodate every slot at its ceiling.
    """

    container_mb = _compose_memory_limit_mb()
    concurrency = Settings().render_execution_concurrency_limit
    compile_mb = _docker_compile_limit_mb()
    required = concurrency * compile_mb + SERVICE_MEMORY_HEADROOM_MB

    assert required <= container_mb, (
        f"{concurrency} concurrent compiles may hold {concurrency * compile_mb} MB, and with "
        f"{SERVICE_MEMORY_HEADROOM_MB} MB for the service that needs {required} MB inside a "
        f"{container_mb} MB container. Every in-flight render dies with it, which is the "
        "failure #128 removed. Raise mem_limit, or lower the concurrency limit or the "
        "per-compile bound."
    )
