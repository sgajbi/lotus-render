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
#
# Taken from the figure `docker-compose.yml` already documents beside `mem_limit`, rather
# than chosen independently. A gate that enforces a different number from the one written
# next to the value it guards leaves a reader two answers and no way to tell which is
# authoritative -- and this one enforced the looser of the two.
SERVICE_MEMORY_HEADROOM_MB = 400


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


def test_the_headroom_the_gate_enforces_is_the_headroom_the_compose_file_documents() -> None:
    """One number, not two.

    `docker-compose.yml` explains its `mem_limit` as the concurrency limit times the
    per-compile budget "plus ~400m for uvicorn, the app and one artifact held in memory
    through its base64 response". That figure is the intent; a gate that quietly enforces
    a smaller one passes configurations the documented reasoning would reject, and leaves
    a reader two answers with no way to tell which is authoritative.
    """

    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    documented = re.search(r"plus ~(\d+)m", compose)
    assert documented is not None, (
        "docker-compose.yml no longer documents the service headroom its mem_limit "
        "arithmetic rests on; the gate below is now the only statement of it."
    )
    assert int(documented.group(1)) == SERVICE_MEMORY_HEADROOM_MB, (
        f"docker-compose.yml documents {documented.group(1)}m of service headroom and the "
        f"gate enforces {SERVICE_MEMORY_HEADROOM_MB}m."
    )
