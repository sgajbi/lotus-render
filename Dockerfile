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

EXPOSE 8310
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8310"]
