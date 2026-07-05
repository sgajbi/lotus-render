# Service Operations Runbook

## Standard Commands

- make install
- make lint
- make typecheck
- make template-registry-gate
- make openapi-gate
- make security-audit
- make check
- make ci
- docker compose up --build
- typst --version

Runtime configuration is documented in `docs/configuration.md`. Settings use the
`LOTUS_RENDER_` prefix and invalid required configuration fails at service startup.

`make ci` and the remote feature, PR merge, and main releasability lanes all run the template
registry validator. `make openapi-gate` proves operation metadata, expected response codes,
internal security posture text, and canonical request-example truth. `make security-audit`
validates time-bounded pip-audit exceptions from `security/pip-audit-exceptions.json` before
running `pip-audit`.

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

The persisted render job row retains support-safe render evidence from the governed package:
`snapshot_id`, `lineage_refs`, `disclosure_refs`, `requested_by`, `package_correlation_id`, and
`package_trace_id`. It does not store raw `report_data`, raw engine stderr, artifact bytes, client
narrative content, archive retention truth, legal hold posture, or distribution commands.

## Render Store Durability And Migrations

`RenderStore` applies source-controlled SQLite migrations on startup and validates the expected
schema version and required columns during readiness checks. Operators should treat
`render_store_schema_version_outdated` or `render_store_schema_missing:*` as deployment-blocking
conditions.

Local Docker Compose stores render job state in the named `lotus-render-data` volume at
`/var/lib/lotus-render/render-store.sqlite3` and sets
`LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE=true`. Removing the volume intentionally deletes local
render-stage diagnostics and idempotency rows; it does not affect archive-owned document retention.

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
5. Run `make openapi-gate` if API descriptions, examples, response envelopes, or route metadata
   changed.
6. Run `make security-audit` if dependency pins or vulnerability exceptions changed.
7. Render the governed golden package from the container-first Typst envelope if a template or
   runtime change is suspected.
8. Run local fast parity (`make check`) before deeper investigation.
9. Run `make ci` before a hotfix PR.
