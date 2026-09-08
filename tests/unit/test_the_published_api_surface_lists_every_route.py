"""Every route the service serves appears in the published API surface.

`GET /version` shipped in #300 and `wiki/API-Surface.md` never learned about it. Nothing
failed: the endpoint worked, the tests passed, and a consumer reading the documentation
had no reason to look for it. That is worse for this endpoint than for most, because
its whole purpose is to let someone attribute a rendered artifact to a build — stating
it in the application and omitting it from the surface states it to nobody.

Asserted as a relationship rather than as a list, so the next route cannot repeat it.
Found by the lotus-report owner auditing documentation currency after Cycle 5, having
hit the same shape in lotus-risk#283.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]

# Served but deliberately outside the documented contract: FastAPI's own docs plumbing
# describes the surface rather than being part of it.
_UNDOCUMENTED_BY_DESIGN = {
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
}


def _served_paths() -> set[str]:
    # `app.routes` is typed as BaseRoute, which carries neither `path` nor `methods`;
    # both exist on the APIRoute subclass that actually populates it. Read through
    # getattr so the reader sees that this is a runtime property of the concrete route
    # rather than a type the checker can confirm.
    return {
        path
        for route in app.routes
        if (path := getattr(route, "path", None))
        and getattr(route, "methods", None)
        and getattr(route, "include_in_schema", True)
    } - _UNDOCUMENTED_BY_DESIGN


def _documented_paths() -> set[str]:
    surface = (REPO_ROOT / "wiki" / "API-Surface.md").read_text(encoding="utf-8")
    # Paths appear as `GET /health/ready` or `POST /renders` inside backticks.
    return set(re.findall(r"`(?:GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)`", surface))


def test_every_served_route_is_published() -> None:
    """A route nobody documented is a route nobody can build against."""

    undocumented = sorted(_served_paths() - _documented_paths())

    assert not undocumented, (
        f"these routes are served but absent from wiki/API-Surface.md: {undocumented}. "
        "A consumer reading the surface would not know they exist."
    )


def test_the_surface_documents_nothing_the_service_does_not_serve() -> None:
    """The other direction, because a stale entry is a promise nobody keeps.

    A removed route left in the documentation is worse than an undocumented one: a
    consumer builds against it and discovers the absence at runtime.
    """

    phantom = sorted(_documented_paths() - _served_paths())

    assert not phantom, (
        f"wiki/API-Surface.md documents routes the service does not serve: {phantom}"
    )
