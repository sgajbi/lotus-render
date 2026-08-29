FROM ghcr.io/typst/typst:0.14.2 AS typst

FROM python:3.12-slim

WORKDIR /app
COPY --from=typst /bin/typst /usr/local/bin/typst
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY security ./security
COPY templates ./templates
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"

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
