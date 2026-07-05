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

## Alert Runbooks

### LotusRenderSubmissionFailureRateHigh

First query:

```promql
sum by (failure_category) (increase(lotus_render_operations_total{operation="render_submission",status="failed"}[15m]))
```

Checks:

1. Confirm `/health/ready` and `/metadata` supportability state.
2. Inspect failed render status rows with `GET /renders/{render_job_id}` when an incident ticket
   includes an affected job id.
3. Compare failure categories: `package_validation_failed` points to producer package shape,
   `template_not_supported` points to registry/manifest mismatch, `engine_unavailable` and
   `timeout` point to runtime posture, and `template_render_failed` points to template/runtime
   diagnostics.
4. Capture correlation id, trace id, status payload, package contract version, template id/version,
   and commit SHA. Do not capture raw `report_data`.

Escalation: route producer package defects to `lotus-report`; route runtime/template defects to the
reporting platform on-call.

### LotusRenderP95LatencyHigh

First query:

```promql
histogram_quantile(0.95, sum by (le) (rate(lotus_render_operation_duration_seconds_bucket{operation="render_submission"}[15m])))
```

Checks:

1. Confirm whether latency aligns with Typst compile runtime, Docker availability, or large
   artifact generation.
2. Check `/metadata` for runtime availability and draining state.
3. Compare artifact-size histogram with the latency window.
4. If only one template regresses, run the canonical golden render locally and compare duration.

Escalation: page reporting platform on-call for runtime saturation; ticket template owners for
template-specific rendering growth.

### LotusRenderArtifactSizeHigh

First query:

```promql
histogram_quantile(0.95, sum by (le) (rate(lotus_render_artifact_size_bytes_bucket[30m])))
```

Checks:

1. Use artifact metadata to confirm `output_size_bytes`, template id/version, and bounded
   determinism fingerprint.
2. Check whether a package added large tables, dense position rows, advisory pages, or proof-pack
   evidence sections.
3. Verify request body limits and artifact size remain inside expected client/channel constraints.

Escalation: route content growth to the upstream package owner; route template layout bloat to the
reporting template owner.

### LotusRenderSupportabilityUnavailable

First query:

```promql
sum by (reason) (increase(lotus_render_supportability_total{state="unavailable"}[10m]))
```

Checks:

1. Call `/metadata` and capture `state`, `reason`, `renderStoreReady`, `templateRegistryReady`, and
   `runtimeAvailable`.
2. If `render_store_unavailable`, check the configured store path, volume mount, migration/schema
   validation, and filesystem write access.
3. If `template_registry_unavailable`, run `make template-registry-gate`.
4. If `runtime_configuration_unavailable`, check Docker/Typst availability and
   `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS`.

Escalation: page reporting platform on-call when readiness is down; ticket repo owners for manifest
or contract defects.

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
