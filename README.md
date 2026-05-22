# lotus-render

Deterministic document rendering service for Lotus reporting.

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make check
make ci
```

```powershell
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy --config-file mypy.ini
.venv\Scripts\python.exe scripts/openapi_quality_gate.py
.venv\Scripts\python.exe scripts/validate_template_registry.py
.venv\Scripts\python.exe -m pytest tests/unit tests/integration tests/e2e
.venv\Scripts\python.exe scripts/coverage_gate.py
```

## Run

```powershell
uvicorn app.main:app --reload --port 8310
```

## Docker

```powershell
docker compose up --build
```

## Standards

- CI and governance: .github/workflows/
- Engineering commands: Makefile
- Platform standards docs: docs/standards/

## Current Implementation

RFC-0102 now covers the first governed internal render API on top of the earlier service, registry,
and Typst foundation slices:

- versioned `RenderPackage` contract with strict validation
- source-controlled template manifests under `templates/registry/`
- explicit lifecycle posture for `active`, `deprecated_rerenderable`,
  `blocked_for_new_renders`, and `blocked`
- machine validation through `scripts/validate_template_registry.py` and `make check`
- governed Typst templates under `templates/typst/portfolio-review/v1/`,
  `templates/typst/outcome-review/v1/`, `templates/typst/proof-pack/v1/`, and
  `templates/typst/rebalance-wave/v1/`
- optional `portfolio-review v1` reviewed advisory narrative rendering when `lotus-report` supplies
  an included advisor-use package from `lotus-advise`
- golden render package and expected PDF proof under `tests/golden/portfolio-review/v1/`
- docker-governed Typst rendering is preferred on developer and CI hosts so golden proof is minted
  from the same controlled runtime envelope
- bounded-determinism fingerprinting that normalizes volatile PDF metadata while preserving raw
  artifact hashing truth
- raw PDF bytes are not claimed to be stable across renders because Typst remints PDF document ids
  and creation timestamps; the supported determinism claim is the bounded-runtime-envelope
  fingerprint
- request middleware propagates `X-Correlation-Id`, `X-Trace-Id`, and `traceparent` and includes
  correlation and trace identifiers in support-safe request logs
- sqlite-backed governed render job store at `data/render-store.sqlite3` by default
- internal render API surface:
  - `POST /renders`
  - `GET /renders/{render_job_id}`
  - `GET /renders/{render_job_id}/artifact-metadata`
- idempotent render-job semantics: same `render_job_id` plus same package returns prior truth;
  same `render_job_id` plus different package returns `409 render_job_conflict`
- `/health/ready` now reflects both runtime posture and render-store availability
- RFC-0105 render metrics expose bounded render submission, status lookup, artifact metadata lookup,
  latency, failure-category, and artifact-size signals through `/metrics`
- RFC-0108 render supportability posture is published through `/metadata` as
  `render.observability.render_supportability` and counted through bounded
  `lotus_render_supportability_total` observations

## Internal Render API

Use `POST /renders` only after upstream report data is already immutable and supportable. The
endpoint accepts a complete `RenderPackage`, validates it against the governed template registry,
executes the synchronous first-wave Typst render path, and returns render truth plus inline
`artifact_base64` on first successful submission.

Use `GET /renders/{render_job_id}` to read support-safe render-job posture without rerunning
anything. Use `GET /renders/{render_job_id}/artifact-metadata` when callers need artifact hash,
size, MIME type, and determinism posture without archive semantics.

The supported determinism posture is explicit:

- raw artifact hash is truthful per concrete PDF file
- bounded determinism is expressed through `bounded_determinism_fingerprint`
- archive retrieval, legal hold, replay, rerender, regenerate, and document distribution remain
  out of scope for `lotus-render`

For advisory narrative content, `lotus-render` renders only the reviewed package supplied in
`report_data.reviewed_advisory_narrative`. It does not approve, rewrite, infer, or fetch advisory
facts; advisor-use boundaries and disclosures must arrive in the render package.

## Observability Metrics

`docs/operations/rendering-observability-metrics.md` is the code-backed metrics, dashboard, and
alert contract for first-wave render observability. Metrics must not add render job, report job,
portfolio, tenant, trace, correlation, raw package, or storage labels.
