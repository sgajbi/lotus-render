# lotus-render Wiki

Deterministic document rendering service for Lotus reporting.

## Reader Map

| Reader | Start Here | Current Evidence |
| --- | --- | --- |
| Business and product | [Current posture](#current-posture), [Template Registry](Template-Registry) | Supported render templates, upstream package boundaries, and presentation-only advisory scope. |
| Operations and support | [Runtime and operations](#runtime-and-operations), [Configuration](Configuration) | Health/readiness, persisted render state, bounded diagnostics, supportability metadata, and Docker runtime posture. |
| Engineering and agents | [Registry truth](#registry-truth), [Validation commands](#validation-commands), [Remote governance](#remote-governance) | Repo-native gates, golden proof artifacts, OpenAPI/template registry controls, and CI-only merge governance. |
| Integration consumers | [Scope guardrails](#scope-guardrails), [Template Registry](Template-Registry) | Complete render-package input ownership, supported template/version tuples, and downstream artifact boundaries. |

## Current posture

- separate deployable render service with its own Docker image and independently scalable runtime
- RFC-0102 first-wave implementation now covers health, readiness, metadata, structured request logging with correlation and trace identifiers, explicit render-attempt domain models, governed render package validation, template registry enforcement, the first real Typst PDF render path, and the first internal render API
- `lotus-render` consumes complete render packages only and must not fetch business data directly
- the `POST /renders` OpenAPI request example is sourced from the same canonical
  portfolio-review render package used by regression tests
- template lifecycle posture is explicit for `active`, `deprecated_rerenderable`, `blocked_for_new_renders`, and `blocked`
- the current determinism claim is bounded to the governed Typst `0.14.2` runtime envelope
- raw PDF bytes are not claimed to be stable across renders because PDF document ids and timestamps are reminted per artifact; support-safe repeatability uses the bounded determinism fingerprint
- active-template golden proof is minted from the container-first Typst runtime on developer and CI
  hosts so proof is stable across environments
- render jobs are persisted in the governed local store before readiness is reported as healthy for
  first-wave traffic
- render-store schema is versioned through SQLite migrations and validated during readiness
- local Docker Compose mounts render job state on the `lotus-render-data` volume at
  `/var/lib/lotus-render/render-store.sqlite3`
- persisted render jobs retain support-safe snapshot, lineage, disclosure, caller, correlation, and
  trace evidence without storing raw report data or archive retention truth
- direct HTTP traffic is bounded by trusted hosts, configured request body size, and disabled CORS
  by default; browser-facing access remains a platform-ingress concern
- `POST /renders` executes blocking Typst/Docker work through a bounded threadpool-backed runtime
  path and returns `429 render_execution_capacity_exhausted` when configured capacity is exhausted
- same-package render replays return the prior persisted `accepted`, `rendering`, `rendered`, or
  `failed` truth without rerunning the renderer; different-package reuse of a render job id remains
  a governed conflict
- HTTP routes consume typed application dependencies while persistence and metrics live behind
  explicit infrastructure and observability modules
- `/metadata` now publishes source-backed RFC-0108 `render.observability.render_supportability`
  posture derived from drain, render-store, template-registry, and runtime configuration state
- Typst/Docker compile execution is timeout-bounded; timed-out renders persist as failed jobs with
  category `timeout` and support-safe diagnostics
- the active `portfolio-review v1` flow now renders structured mandate, performance, risk,
  holdings, and governance sections from the governed render package rather than a thin text-only
  summary payload
- `portfolio-review v1` can render an optional reviewed advisory narrative page when `lotus-report`
  supplies an included advisor-use package from `lotus-advise`; render remains presentation-only
  and does not approve, rewrite, infer, or fetch advisory facts
- `portfolio-review v1` can render an optional advisor proposal memo page when `lotus-report`
  supplies an included advisor-use memo package from `lotus-advise`; client-ready memo publication
  remains blocked upstream
- RFC-0105 first-wave render metrics are implementation-backed for render submission, status
  lookup, diagnostics lookup, artifact metadata lookup, latency, failure-category, artifact-size,
  and source-backed stale in-flight render signals with bounded labels only
- RFC-0108 render supportability metrics are implementation-backed through
  `lotus_render_supportability_total` with bounded `state`, `reason`, and `freshness_bucket` labels
  and recorder-level fallback for unknown label values
- `/metadata` publishes aggregate `accepted` and `rendering` stale posture from the render store,
  and `/renders/{render_job_id}/diagnostics` maps lifecycle/failure state to bounded recovery
  actions and handoff owners without raw package or engine output

## Registry truth

- manifests live under `templates/registry/`
- `make template-registry-gate` validates registry structure and lifecycle metadata
- remote feature, PR merge, and main releasability lanes run the template registry gate
- `make openapi-gate` validates operation metadata, expected response codes, and canonical request
  example truth
- `make security-audit` validates governed pip-audit exceptions before running dependency audit
- `contracts/render-supported-features.v1.json` publishes supported templates, API paths, and
  non-goals for consumers
- `contracts/render-source-contracts.v1.json` binds manifest report-data contract versions to
  source ownership/provenance
- `contracts/render-data-product-trust.v1.json` declares support-safe render status, artifact
  metadata, supportability, and metrics trust posture
- active report-data contract versions are parsed through typed render content adapters before
  Typst context generation
- template context routing is explicit for active report/template/version tuples and unknown
  combinations fail without falling back to portfolio review
- current active templates are `portfolio-review` version `v1`, `outcome-review` version `v1`,
  `proof-pack` version `v1`, and `rebalance-wave` version `v1`
- current active-template golden proof lives under `tests/golden/<template>/v1/`; each active
  registry golden sample must have `render-package.json`, `expected.pdf`, and provenance in
  `tests/golden/producer-fixtures.v1.json`

See [Template Registry](Template-Registry).

## Operator checks

- `make check`
- `make ci`
- `make template-registry-gate`
- `docker compose up --build`
- `/health`
- `/health/live`
- `/health/ready`
- `/metadata`
- `/metrics`
- `POST /renders`
- `GET /renders/{render_job_id}`
- `GET /renders/{render_job_id}/diagnostics`
- `GET /renders/{render_job_id}/artifact-metadata`
- `docs/configuration.md`

## Remote governance

- `main` branch protection requires strict PR Merge Gate contexts, conversation resolution, linear
  history, and admin enforcement
- human approval is optional in the solo-developer baseline; required GitHub checks and truthful PR
  evidence are the merge control

## Scope guardrails

- `lotus-render` owns render execution, render status, artifact hash, and support-safe diagnostics
- `lotus-render` does not own archive retrieval, retention, legal hold, replay, rerender, regenerate, or document distribution commands
