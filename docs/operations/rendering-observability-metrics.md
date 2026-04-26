# Rendering Observability Metrics

This document records the RFC-0105 first-wave metrics contract implemented by `lotus-render`.
The contract is intentionally bounded: metrics expose render lifecycle posture, latency, and
artifact size without render job ids, report job ids, portfolio ids, tenant ids, correlation ids,
trace ids, raw render packages, or storage locations.

## Implemented Metrics

| Metric | Type | Labels | Source |
| --- | --- | --- | --- |
| `lotus_render_operations_total` | counter | `operation`, `status`, `failure_category` | `POST /renders`, `GET /renders/{render_job_id}`, and `GET /renders/{render_job_id}/artifact-metadata` service paths |
| `lotus_render_operation_duration_seconds` | histogram | `operation`, `status`, `failure_category` | Same render operation paths, measured inside `RenderSubmissionService` |
| `lotus_render_artifact_size_bytes` | histogram | `status` | Successful render submission and artifact metadata reads when artifact size is persisted |

Supported `operation` labels are:

- `render_submission`
- `render_status_lookup`
- `artifact_metadata_lookup`

Supported `status` labels are bounded to render lifecycle and lookup states:

- `accepted`
- `validating_package`
- `rendering`
- `rendered`
- `failed`
- `not_ready`
- `not_found`

`failure_category` is normalized to lower-case snake case and falls back to `other` when an input
is too long or contains unsupported characters.

## Dashboard Contract

First-wave dashboard panels may reference only the implemented metrics above:

| Panel | Query family | Purpose |
| --- | --- | --- |
| Render submissions by status | `sum by (status) (rate(lotus_render_operations_total{operation="render_submission"}[5m]))` | Show render success and failure posture |
| Render failure category mix | `sum by (failure_category) (increase(lotus_render_operations_total{status="failed"}[15m]))` | Classify product-safe render failures |
| Render latency | `histogram_quantile(0.95, sum by (le) (rate(lotus_render_operation_duration_seconds_bucket{operation="render_submission"}[5m])))` | Track render-stage latency |
| Artifact size distribution | `histogram_quantile(0.95, sum by (le) (rate(lotus_render_artifact_size_bytes_bucket{status="rendered"}[15m])))` | Detect unexpectedly large generated artifacts |

## Alert Contract

| Alert | Threshold | Severity | Owner | Runbook |
| --- | --- | --- | --- | --- |
| `LotusRenderSubmissionFailureRateHigh` | failure rate for `render_submission` above 5% for 15 minutes | page | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderP95LatencyHigh` | p95 `render_submission` latency above 30 seconds for 15 minutes | ticket | Reporting platform on-call | `docs/runbooks/service-operations.md` |
| `LotusRenderArtifactSizeHigh` | p95 rendered artifact size above 5 MiB for 30 minutes | ticket | Reporting platform on-call | `docs/runbooks/service-operations.md` |

Stuck-render and SLA-breach metrics remain out of this slice until RFC-0105 Slice 8 implements
source-backed stuck-state scanning and SLA monitoring.
