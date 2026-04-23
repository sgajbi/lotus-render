# lotus-render Wiki

Deterministic document rendering service for Lotus reporting.

## Current posture

- separate deployable render service with its own Docker image and independently scalable runtime
- RFC-0102 first-wave implementation now covers health, readiness, metadata, structured request logging, explicit render-attempt domain models, governed render package validation, template registry enforcement, the first real Typst PDF render path, and the first internal render API
- `lotus-render` consumes complete render packages only and must not fetch business data directly
- template lifecycle posture is explicit for `active`, `deprecated_rerenderable`, `blocked_for_new_renders`, and `blocked`
- the current determinism claim is bounded to the governed Typst `0.14.2` runtime envelope
- raw PDF bytes are not claimed to be stable across renders because PDF document ids and timestamps are reminted per artifact; support-safe repeatability uses the bounded determinism fingerprint
- golden proof is minted from the container-first Typst runtime on developer and CI hosts so proof
  is stable across environments
- render jobs are persisted in the governed local store before readiness is reported as healthy for
  first-wave traffic
- the active `portfolio-review v1` flow now renders structured mandate, performance, risk,
  holdings, and governance sections from the governed render package rather than a thin text-only
  summary payload

## Registry truth

- manifests live under `templates/registry/`
- `make template-registry-gate` validates registry structure and lifecycle metadata
- current first-wave active template is `portfolio-review` version `v1`
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
- `POST /renders`
- `GET /renders/{render_job_id}`
- `GET /renders/{render_job_id}/artifact-metadata`

## Scope guardrails

- `lotus-render` owns render execution, render status, artifact hash, and support-safe diagnostics
- `lotus-render` does not own archive retrieval, retention, legal hold, replay, rerender, regenerate, or document distribution commands
