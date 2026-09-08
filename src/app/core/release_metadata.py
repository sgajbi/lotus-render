"""Support-safe build and image provenance for the running render service.

Every rendered document asserts bounded determinism "within the governed lotus-render
runtime envelope", and until now the runtime could not say which build it was. The
claim named the Typst version and nothing about the code that produced the output, so
two artifacts from different commits carried identical envelope statements.

Values arrive as environment variables set from Docker build arguments. Absence is
reported as `unknown` rather than guessed: a build that cannot state its commit is a
fact an operator needs, and inventing a plausible value would make the unidentifiable
case indistinguishable from the identified one.

Deliberately the same field names and the same `LOTUS_BUILD_*` variables as
`lotus-advise`, which shipped this first. A third vocabulary for the same facts would
make the estate harder to read for no gain.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

SERVICE_NAME = "lotus-render"
UNKNOWN = "unknown"
REPOSITORY_URL = "https://github.com/sgajbi/lotus-render"


@dataclass(frozen=True)
class ReleaseMetadata:
    service_name: str
    service_version: str
    git_commit_sha: str
    git_branch: str
    repository_url: str
    build_timestamp_utc: str
    ci_pipeline_run_id: str
    image_digest: str

    def as_response(self) -> dict[str, str]:
        return asdict(self)


def build_release_metadata() -> ReleaseMetadata:
    return ReleaseMetadata(
        service_name=SERVICE_NAME,
        service_version=_env("LOTUS_BUILD_VERSION", "0.1.0"),
        git_commit_sha=_env("LOTUS_BUILD_COMMIT_SHA"),
        git_branch=_env("LOTUS_BUILD_GIT_BRANCH"),
        repository_url=_env("LOTUS_BUILD_REPO_URL", REPOSITORY_URL),
        build_timestamp_utc=_env("LOTUS_BUILD_TIMESTAMP"),
        ci_pipeline_run_id=_env("LOTUS_CI_PIPELINE_ID"),
        # Deliberately not the `unknown` default the other fields use. A digest is
        # not merely unknown before push -- it does not exist, and saying so stops a
        # reader trying to supply one through a build argument that cannot carry it.
        image_digest=_env("LOTUS_IMAGE_DIGEST", "unavailable-before-push"),
    )


def _env(name: str, default: str = UNKNOWN) -> str:
    """Read one provenance variable, treating whitespace-only as absent.

    A build argument that is present but blank is the shape an unset shell variable
    takes when it reaches Compose, so it means the same thing as absence and must not
    be published as an empty commit sha.
    """

    value = os.getenv(name, "").strip()
    return value or default
