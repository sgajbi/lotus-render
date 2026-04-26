# Service Operations Runbook

## Standard Commands

- make install
- make lint
- make typecheck
- make template-registry-gate
- make check
- make ci
- docker compose up --build
- typst --version

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata

## Internal Render APIs

- Submit first-wave synchronous render: `POST /renders`
- Read persisted render status: `GET /renders/{render_job_id}`
- Read support-safe artifact metadata: `GET /renders/{render_job_id}/artifact-metadata`
- Metrics: `/metrics`

The first-wave render path is intentionally idempotent on `render_job_id` plus package hash.
Replaying the exact same request returns the prior stored truth. Reusing the same `render_job_id`
with a different render package returns `409 render_job_conflict`.

## Metrics Contract

RFC-0105 first-wave render metrics are documented in
`docs/operations/rendering-observability-metrics.md`. Operators may use:

- `lotus_render_operations_total`
- `lotus_render_operation_duration_seconds`
- `lotus_render_artifact_size_bytes`

These metrics use bounded labels only and must not expose render job ids, report job ids,
portfolio ids, tenant ids, correlation ids, trace ids, raw render packages, or storage locations.
Stuck-render and SLA-breach metrics remain planned until source-backed stuck-state scanning is
implemented.

## Incident First Checks

1. Check container logs for request failures, correlation IDs, and structured request timing lines.
2. Verify `/health/ready`, `/metadata`, `/metrics`, and the persisted render job posture for the
   affected `render_job_id`.
3. Run `make template-registry-gate` if template manifests or lifecycle posture changed.
4. Render the governed golden package from the container-first Typst envelope if a template or
   runtime change is suspected.
5. Run local fast parity (`make check`) before deeper investigation.
6. Run `make ci` before a hotfix PR.
