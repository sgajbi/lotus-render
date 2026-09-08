FROM ghcr.io/typst/typst:0.14.2 AS typst

FROM python:3.12-slim

# Build provenance. Same names and same defaults as the sibling services, so one
# vocabulary covers the estate. Each default is the honest answer for a build that
# supplied nothing, not a plausible-looking placeholder: `unknown` is a fact an
# operator can act on, an invented sha is not.
ARG LOTUS_BUILD_COMMIT_SHA=unknown
ARG LOTUS_BUILD_GIT_BRANCH=unknown
ARG LOTUS_BUILD_REPO_URL=https://github.com/sgajbi/lotus-render
ARG LOTUS_BUILD_VERSION=0.1.0
ARG LOTUS_BUILD_TIMESTAMP=unknown
ARG LOTUS_CI_PIPELINE_ID=local
# Not `unknown`: an image cannot contain its own digest, because the digest exists
# only once the image does. `unknown` would report a structural impossibility using
# the same word as a genuine gap, inviting someone to supply a value that no build
# argument can carry. Matches lotus-performance, which already names the reason.
ARG LOTUS_IMAGE_DIGEST=unavailable-before-push

LABEL org.opencontainers.image.title="lotus-render" \
    org.opencontainers.image.source="${LOTUS_BUILD_REPO_URL}" \
    org.opencontainers.image.revision="${LOTUS_BUILD_COMMIT_SHA}" \
    com.lotus.image.digest="${LOTUS_IMAGE_DIGEST}"

# An ARG is build-time only; the running process reads environment. Declaring the
# arguments without this conversion is the failure mode where provenance exists in
# the image metadata and the service still cannot report it.
ENV LOTUS_BUILD_COMMIT_SHA="${LOTUS_BUILD_COMMIT_SHA}" \
    LOTUS_BUILD_GIT_BRANCH="${LOTUS_BUILD_GIT_BRANCH}" \
    LOTUS_BUILD_REPO_URL="${LOTUS_BUILD_REPO_URL}" \
    LOTUS_BUILD_VERSION="${LOTUS_BUILD_VERSION}" \
    LOTUS_BUILD_TIMESTAMP="${LOTUS_BUILD_TIMESTAMP}" \
    LOTUS_CI_PIPELINE_ID="${LOTUS_CI_PIPELINE_ID}" \
    LOTUS_IMAGE_DIGEST="${LOTUS_IMAGE_DIGEST}"

WORKDIR /app
COPY --from=typst /bin/typst /usr/local/bin/typst
COPY pyproject.toml README.md ./
COPY src ./src
COPY templates ./templates

# Runtime dependencies only. The [dev] extra carries the CI toolchain - pip-audit and
# its HTTP/resolver stack, a second HTTP client, a YAML parser, mypy, ruff, pytest -
# none of which any module under src/ imports, and each of which is CVE surface and
# patch burden in a container whose job is to compile untrusted Typst source.
# Non-editable so the running code is an installed distribution rather than a mutable
# source tree the service's own user can rewrite.
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# The compile child is fed untrusted report_data, and in this image it is a direct child
# of the API process rather than a container, so it inherits this identity: run both as a
# non-root user (issue #106). The render-store directory is created and owned here because
# the named volume mounted over it inherits the mount point's ownership.
RUN useradd --create-home --uid 10001 lotus \
    && mkdir -p /var/lib/lotus-render \
    && chown -R lotus:lotus /app /var/lib/lotus-render
USER lotus

EXPOSE 8310
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8310"]
