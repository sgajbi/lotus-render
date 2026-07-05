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
.venv\Scripts\python.exe scripts/pip_audit_gate.py
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
- Runtime configuration: docs/configuration.md

## Current Implementation

RFC-0102 now covers the first governed internal render API on top of the earlier service, registry,
and Typst foundation slices:

- versioned `RenderPackage` contract with strict validation
- canonical `POST /renders` OpenAPI request example sourced from
  `src/app/contracts/examples/portfolio-review-render-package.v1.json`
- source-controlled template manifests under `templates/registry/`
- explicit lifecycle posture for `active`, `deprecated_rerenderable`,
  `blocked_for_new_renders`, and `blocked`
- machine validation through `scripts/validate_template_registry.py` and `make check`
- OpenAPI governance through `scripts/openapi_quality_gate.py`, including operation metadata,
  expected response codes, internal security posture text, and canonical render-package examples
- governed dependency-audit exception metadata under `security/pip-audit-exceptions.json`
- consumer contract declarations under `contracts/` for supported features, source-contract
  provenance, and data-product trust
- typed render content adapters for each active report-data contract version before Typst context
  generation
- explicit template-context renderer registration for active report/template/version tuples, with
  unknown combinations failing instead of falling back to portfolio review
- governed Typst templates under `templates/typst/portfolio-review/v1/`,
  `templates/typst/outcome-review/v1/`, `templates/typst/proof-pack/v1/`, and
  `templates/typst/rebalance-wave/v1/`
- optional `portfolio-review v1` reviewed advisory narrative and advisor proposal memo rendering
  when `lotus-report` supplies included advisor-use packages from `lotus-advise`
- producer-backed golden render packages and expected PDF proofs under `tests/golden/<template>/v1/`
  for every active template, with provenance in `tests/golden/producer-fixtures.v1.json`
- docker-governed Typst rendering is preferred on developer and CI hosts so golden proof is minted
  from the same controlled runtime envelope
- bounded-determinism fingerprinting that normalizes volatile PDF metadata while preserving raw
  artifact hashing truth
- renderer-owned allocation chart market-value calculations use `Decimal`; float conversion is
  limited to SVG geometry coordinates
- raw PDF bytes are not claimed to be stable across renders because Typst remints PDF document ids
  and creation timestamps; the supported determinism claim is the bounded-runtime-envelope
  fingerprint
- request middleware propagates `X-Correlation-Id`, `X-Trace-Id`, and `traceparent` and includes
  correlation and trace identifiers in support-safe request logs
- direct HTTP requests are bounded by trusted-host, request-body-size, and CORS configuration;
  browser-facing access remains platform-ingress governed by default
- `POST /renders` offloads blocking Typst/Docker execution to a threadpool and applies the
  configured `LOTUS_RENDER_RENDER_EXECUTION_CONCURRENCY_LIMIT`, returning
  `429 render_execution_capacity_exhausted` when capacity is exhausted
- sqlite-backed governed render job store at `data/render-store.sqlite3` by default
- versioned SQLite render-store migrations with schema readiness validation
- support-safe render evidence persistence for snapshot identity, lineage refs, disclosure refs,
  caller identity, and original package correlation/trace identifiers
- `docker compose up --build` uses a named `lotus-render-data` volume and
  `/var/lib/lotus-render/render-store.sqlite3` for local durable render-job state
- internal render API surface:
  - `POST /renders`
  - `GET /renders/{render_job_id}`
  - `GET /renders/{render_job_id}/diagnostics`
  - `GET /renders/{render_job_id}/artifact-metadata`
- idempotent render-job semantics: same `render_job_id` plus same package returns prior stored
  truth for `accepted`, `rendering`, `rendered`, and `failed` without rerunning the renderer; same
  `render_job_id` plus different package returns `409 render_job_conflict`
- `/health/ready` now reflects both runtime posture and render-store availability
- Typst/Docker compile execution is bounded by `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS`;
  timeouts persist as failed render jobs with category `timeout`
- RFC-0105 render metrics expose bounded render submission, status lookup, diagnostics lookup,
  artifact metadata lookup, latency, failure-category, artifact-size, and source-backed stale
  in-flight render signals through `/metrics`
- RFC-0108 render supportability posture is published through `/metadata` as
  `render.observability.render_supportability` and counted through bounded
  `lotus_render_supportability_total` observations; `/metadata` also publishes aggregate
  `accepted` and `rendering` stale posture from the render store

## Internal Render API

Use `POST /renders` only after upstream report data is already immutable and supportable. The
endpoint accepts a complete `RenderPackage`, validates it against the governed template registry,
executes the synchronous first-wave Typst render path, and returns render truth plus inline
`artifact_base64` on first successful submission.

The endpoint remains synchronous for first-wave consumers, but expensive Typst/Docker work runs off
the ASGI event loop behind a bounded in-process limiter. Capacity exhaustion returns
`429 render_execution_capacity_exhausted`; callers should retry after current render work completes
using the same idempotent package.

Use `GET /renders/{render_job_id}` to read support-safe render-job posture without rerunning
anything. Use `GET /renders/{render_job_id}/diagnostics` to classify stale posture, retryability,
recovery action, and support handoff without raw package or engine diagnostics. Use
`GET /renders/{render_job_id}/artifact-metadata` when callers need artifact hash, size, MIME type,
and determinism posture without archive semantics.

Supported report-data contract versions are parsed through render-safe content adapters before
Typst context generation. The adapters validate the active `portfolio_review.v1`,
`dpm_outcome_report_input.v1`, `dpm_proof_pack_report_input.v1`, and
`dpm_wave_report_input.v1` shapes without making `lotus-render` the owner of upstream domain
calculations or source-data retrieval.

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
