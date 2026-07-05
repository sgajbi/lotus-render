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

Runtime configuration is documented in `docs/configuration.md`. Settings use the
`LOTUS_RENDER_` prefix and invalid required configuration fails at service startup.

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata and RFC-0108 render supportability posture: /metadata

## Internal Render APIs

- Submit first-wave synchronous render: `POST /renders`
- Read persisted render status: `GET /renders/{render_job_id}`
- Read support-safe artifact metadata: `GET /renders/{render_job_id}/artifact-metadata`
- Metrics: `/metrics`

The first-wave render path is intentionally idempotent on `render_job_id` plus package hash.
Replaying the exact same request returns the prior stored truth for `accepted`, `rendering`,
`rendered`, and `failed` jobs without rerunning the renderer. Reusing the same `render_job_id` with
a different render package returns `409 render_job_conflict`.

## Metrics Contract

RFC-0105 first-wave render metrics are documented in
`docs/operations/rendering-observability-metrics.md`. Operators may use:

- `lotus_render_operations_total`
- `lotus_render_operation_duration_seconds`
- `lotus_render_artifact_size_bytes`
- `lotus_render_supportability_total`

These metrics use bounded labels only and must not expose render job ids, report job ids,
portfolio ids, tenant ids, correlation ids, trace ids, raw render packages, or storage locations.
Stuck-render and SLA-breach metrics remain planned until source-backed stuck-state scanning is
implemented.

## Render Supportability

`GET /metadata` publishes the `render.observability.render_supportability` posture consumed by
evidence and reporting surfaces. The posture is source-backed by drain state, render-store
readiness, governed template-registry availability, and executable Typst or Docker runtime
availability. Treat
`state=unavailable` as an operator-impacting condition because the service cannot provide complete
deterministic rendering supportability evidence.

`runtime_configuration_unavailable` means neither a governed Docker runtime nor local Typst binary
is executable from the service process. Do not route new render traffic until `/health/ready`
returns ready and `/metadata` reports `runtimeAvailable=true`.

## HTTP Boundary And Timeout Checks

- Unknown direct-service hosts are rejected by the trusted-host boundary.
- CORS is disabled by default; browser-facing access must use governed platform ingress.
- Requests larger than `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES` return
  `413 request_body_too_large` without echoing package payload content.
- Typst/Docker compile execution is bounded by
  `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS`. Timed-out jobs persist as `failed` with failure
  category `timeout` and support-safe diagnostics.

## Incident First Checks

1. Check container logs for request failures, correlation IDs, and structured request timing lines.
2. Verify `/health/ready`, `/metadata` supportability state and reason, `/metrics`, and the
   persisted render job posture for the affected `render_job_id`.
3. Check `docs/configuration.md` and the active `LOTUS_RENDER_` settings when readiness, request
   boundary, timeout, or render-store posture changed.
4. Run `make template-registry-gate` if template manifests or lifecycle posture changed.
5. Render the governed golden package from the container-first Typst envelope if a template or
   runtime change is suspected.
6. Run local fast parity (`make check`) before deeper investigation.
7. Run `make ci` before a hotfix PR.
