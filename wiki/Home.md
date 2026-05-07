# lotus-render Wiki

Deterministic document rendering service for Lotus reporting.

## Current posture

- separate deployable render service with its own Docker image and independently scalable runtime
- RFC-0102 first-wave implementation now covers health, readiness, metadata, structured request logging with correlation and trace identifiers, explicit render-attempt domain models, governed render package validation, template registry enforcement, the first real Typst PDF render path, and the first internal render API
- `lotus-render` consumes complete render packages only and must not fetch business data directly
- template lifecycle posture is explicit for `active`, `deprecated_rerenderable`, `blocked_for_new_renders`, and `blocked`
- the current determinism claim is bounded to the governed Typst `0.14.2` runtime envelope
- raw PDF bytes are not claimed to be stable across renders because PDF document ids and timestamps are reminted per artifact; support-safe repeatability uses the bounded determinism fingerprint
- golden proof is minted from the container-first Typst runtime on developer and CI hosts so proof
  is stable across environments
- render jobs are persisted in the governed local store before readiness is reported as healthy for
  first-wave traffic
- `/metadata` now publishes source-backed RFC-0108 `render.observability.render_supportability`
  posture derived from drain, render-store, template-registry, and runtime configuration state
- the active `portfolio-review v1` flow now renders structured mandate, performance, risk,
  holdings, and governance sections from the governed render package rather than a thin text-only
  summary payload
- RFC-0105 first-wave render metrics are implementation-backed for render submission, status
  lookup, artifact metadata lookup, latency, failure-category, and artifact-size signals with
  bounded labels only
- RFC-0108 render supportability metrics are implementation-backed through
  `lotus_render_supportability_total` with bounded `state`, `reason`, and `freshness_bucket` labels
  and recorder-level fallback for unknown label values

## Registry truth

- manifests live under `templates/registry/`
- `make template-registry-gate` validates registry structure and lifecycle metadata
- current active templates are `portfolio-review` version `v1`, `outcome-review` version `v1`,
  and `proof-pack` version `v1`
- current first-wave golden proof lives under `tests/golden/portfolio-review/v1/`

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
- `GET /renders/{render_job_id}/artifact-metadata`

## Scope guardrails

- `lotus-render` owns render execution, render status, artifact hash, and support-safe diagnostics
- `lotus-render` does not own archive retrieval, retention, legal hold, replay, rerender, regenerate, or document distribution commands
