# Rendering Observability Metrics

This document records the RFC-0105 and RFC-0108 first-wave metrics contract implemented by
`lotus-render`.
The contract is intentionally bounded: metrics expose render lifecycle posture, latency, and
artifact size without render job ids, report job ids, portfolio ids, tenant ids, correlation ids,
trace ids, raw render packages, or storage locations.

## Implemented Metrics

| Metric | Type | Labels | Source |
| --- | --- | --- | --- |
| `lotus_render_operations_total` | counter | `operation`, `status`, `failure_category` | `POST /renders`, `GET /renders/{render_job_id}`, and `GET /renders/{render_job_id}/artifact-metadata` service paths |
| `lotus_render_operation_duration_seconds` | histogram | `operation`, `status`, `failure_category` | Same render operation paths, measured inside `RenderSubmissionService` |
| `lotus_render_artifact_size_bytes` | histogram | `status` | Successful render submission and artifact metadata reads when artifact size is persisted |
| `lotus_render_supportability_total` | counter | `state`, `reason`, `freshness_bucket` | `GET /metadata` supportability posture derived from drain, render-store, template-registry, and runtime configuration state |
| `lotus_render_in_flight_jobs` | gauge | `status`, `stale_state` | `GET /metadata` source-backed scan of persisted `accepted` and `rendering` render jobs |
| `lotus_render_oldest_in_flight_age_seconds` | gauge | `status` | `GET /metadata` source-backed oldest age of persisted `accepted` and `rendering` render jobs |

The render supportability recorder sanitizes label values before they reach Prometheus. Unknown
states fall back to `unavailable`, unknown reasons fall back to
`runtime_configuration_unavailable`, and unknown freshness values fall back to `unknown`. Do not
emit render job ids, report job ids, portfolio ids, client names, tenant ids, trace ids,
correlation ids, raw packages, or storage locations as labels.

Supported `operation` labels are:

- `render_submission`
- `render_status_lookup`
- `render_diagnostics_lookup`
- `artifact_metadata_lookup`

Supported `status` labels are bounded to render lifecycle and lookup states:

- `accepted`
- `rendering`
- `rendered`
- `failed`
- `not_ready`
- `not_found`

`validating_package` is a transient render-attempt phase exposed in `/metadata` as attempt
vocabulary. It is not emitted as a persisted render job operation status.

`failure_category` is normalized to lower-case snake case and falls back to `other` when an input
is too long or contains unsupported characters.

Supported `state` labels for render supportability are:

- `ready`
- `degraded`
- `unavailable`

Supported `reason` labels are:

- `render_supportability_ready`
- `render_supportability_draining`
- `render_store_unavailable`
- `template_registry_unavailable`
- `runtime_configuration_unavailable`

Supported `freshness_bucket` labels are `current` and `unknown`.

Supported `stale_state` labels for in-flight render jobs are `fresh` and `stale`. Stale
classification uses:

- `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` for persisted `accepted` jobs
- `LOTUS_RENDER_STALE_RENDERING_SECONDS` for persisted `rendering` jobs

## Dashboard Contract

First-wave dashboard panels may reference only the implemented metrics above:

| Panel | Query family | Purpose |
| --- | --- | --- |
| Render submissions by status | `sum by (status) (rate(lotus_render_operations_total{operation="render_submission"}[5m]))` | Show render success and failure posture |
| Render failure category mix | `sum by (failure_category) (increase(lotus_render_operations_total{status="failed"}[15m]))` | Classify product-safe render failures |
| Render latency | `histogram_quantile(0.95, sum by (le) (rate(lotus_render_operation_duration_seconds_bucket{operation="render_submission"}[5m])))` | Track render-stage latency |
| Artifact size distribution | `histogram_quantile(0.95, sum by (le) (rate(lotus_render_artifact_size_bytes_bucket{status="rendered"}[15m])))` | Detect unexpectedly large generated artifacts |
| Render supportability posture | `sum by (state, reason, freshness_bucket) (increase(lotus_render_supportability_total[15m]))` | Show source-backed RFC-0108 supportability observations for evidence and reporting surfaces |
| In-flight render posture | `sum by (status, stale_state) (lotus_render_in_flight_jobs)` | Detect stale `accepted` or `rendering` rows after deploy interruption, process crash, or runtime hang |
| Oldest in-flight render age | `max by (status) (lotus_render_oldest_in_flight_age_seconds)` | Track SLA age for non-terminal render rows without exposing job identifiers |

## Alert Contract

| Alert | Threshold | Severity | Owner | Runbook |
| --- | --- | --- | --- | --- |
| `LotusRenderSubmissionFailureRateHigh` | failure rate for `render_submission` above 5% for 15 minutes | page | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderP95LatencyHigh` | p95 `render_submission` latency above 30 seconds for 15 minutes | ticket | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderArtifactSizeHigh` | p95 rendered artifact size above 5 MiB for 30 minutes | ticket | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderSupportabilityUnavailable` | latest supportability posture is `unavailable` for 10 minutes | page | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderStaleInFlightJobs` | any `lotus_render_in_flight_jobs{stale_state="stale"}` above 0 for 10 minutes | page | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderOldestInFlightAgeHigh` | oldest in-flight age exceeds the configured threshold for 10 minutes | ticket | Reporting platform on-call | `docs/runbooks/service-operations.md` |
