# API Surface

Every operation `lotus-render` publishes, taken from the generated OpenAPI document on `main`.
There are **nine**, and there is no undocumented tenth: four form the render contract and five are
operational.

## The render contract

| operation | purpose |
|---|---|
| `POST /renders` | submit a governed render package and execute the render |
| `GET /renders/{render_job_id}` | support-safe job posture |
| `GET /renders/{render_job_id}/diagnostics` | why a job is where it is, and who should act |
| `GET /renders/{render_job_id}/artifact-metadata` | artifact hash, size, MIME type, determinism posture |

## Operational

| operation | purpose |
|---|---|
| `GET /health` | service health with identity |
| `GET /health/live` | process liveness only — no dependency checks |
| `GET /health/ready` | drain posture **and** render-store readiness **and** Typst/Docker availability |
| `GET /metadata` | service identity, runtime posture, supportability state, aggregate stale posture |
| `GET /metrics` | Prometheus exposition |

`/health/live` and `/health/ready` answer genuinely different questions: a process that is alive but
whose render store or compile runtime is unavailable is **live and not ready**, and must not be sent
render traffic. See [Operations](Operations).

## Submitting a render

`POST /renders` accepts a complete `RenderPackage`. The caller supplies everything the document
needs; the service fetches no domain data of its own. The package carries:

| group | fields |
|---|---|
| contract identity | `render_package_version`, `report_data_contract_version` |
| job identity | `render_job_id`, `report_job_id`, `snapshot_id` |
| template selection | `report_type`, `template_id`, `template_version`, `locale`, `brand_variant`, `output_format` |
| content | `render_context`, `report_data` |
| evidence | `lineage_refs`, `disclosure_refs`, `requested_by`, `correlation_id`, `trace_id` |

The template selection fields are matched against the governed manifest for that template — see
[Template Registry](Template-Registry). A combination the manifest does not support is
rejected; it never falls back to another template.

### Two success codes, and the difference matters

| code | meaning |
|---|---|
| `201 Created` | the render ran on this call; the response carries the artifact inline as `artifact_base64` |
| `200 OK` | the job already existed; prior stored truth is returned and **no artifact bytes are included** |

A client that assumes `artifact_base64` is always present will break on its first retry. Fetch the
artifact identity from `/artifact-metadata` when the submit response returns `200`.

### Idempotency and conflict

Idempotency is keyed on `render_job_id` **plus the package**:

- same id, same package → prior truth returned, renderer not re-run
- same id, different package → `409 render_job_conflict`

The conflict is deliberate. Silently rendering a different document under an id another system has
already recorded would make the render job id useless as evidence.

### Error codes

| status | code | when |
|---|---|---|
| `404` | `render_job_not_found` | unknown `render_job_id` on any read |
| `409` | `render_job_conflict` | `render_job_id` reused with a different package |
| `409` | `render_artifact_not_ready` | artifact metadata requested before a successful render |
| `413` | `request_body_too_large` | body over `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES` |
| `422` | `render_package_invalid` | package failed governed validation |
| `429` | `render_execution_capacity_exhausted` | concurrency limit reached; retry the identical package |
| `502` | `render_failed` | execution failed inside the governed runtime envelope |
| `503` | — | `/health/ready` while draining or a dependency is unavailable |

Errors return a `detail` object with `code` and `message`, plus `field_paths`, `correlation_id` and
`trace_id` where they apply. `429` is the one to retry unchanged; `409 render_job_conflict` and
`422` are caller defects and retrying them changes nothing.

## Events

There are none. `lotus-render` publishes no events, consumes no queue, and holds no outbound
integration other than the responses above — the compile runtime is the only process it invokes.
Every interaction with this service is a synchronous HTTP call made by the caller.

The runtime dependency list is the evidence: `fastapi`, `uvicorn`, `pydantic`,
`pydantic-settings`, `starlette` and the two Prometheus packages. There is no HTTP client, message
broker or cloud SDK among them, so there is no path by which the service could reach out even if a
future change wanted one — adding an integration would mean adding a dependency, which the
dependency-hygiene gate makes visible.

## Correlation

`X-Correlation-Id`, `X-Trace-Id` and `traceparent` are propagated when supplied and appear in
support-safe request logs. The package also carries its own `correlation_id` and `trace_id`, echoed
back on submit as `package_correlation_id` and `package_trace_id` — these are the *upstream report
job's* identifiers, not the HTTP request's, and the two are kept distinct on purpose.

## What responses never contain

Read responses are support-safe by construction. None of them returns raw `report_data`, raw engine
stderr, artifact storage locations, archive retention truth, or upstream replay commands. That is a
contract, not an omission — see [Security and Controls](Security-and-Controls).

## Published consumer contracts

Three machine-readable declarations under
[`contracts/`](https://github.com/sgajbi/lotus-render/tree/main/contracts) tell downstream services
what they may rely on, without their having to read this service's source:

| file | declares |
|---|---|
| `render-supported-features.v1.json` | supported templates, API paths and explicit non-goals |
| `render-source-contracts.v1.json` | which report-data contract version each manifest accepts, and who owns it upstream |
| `render-data-product-trust.v1.json` | the trust posture of render status, artifact metadata, supportability and metrics |

Each names the source files it is generated from, so a contract that has drifted from the code is
detectable rather than merely suspected.

## Governance

`make openapi-gate` validates operation metadata, expected response codes, the internal security
posture text, and that the canonical `POST /renders` request example is the same portfolio-review
package used by regression tests. The gate runs on every CI lane, so this surface cannot drift
without a failing build.

## Read next

1. [Architecture](Architecture) — how a submission becomes a PDF
2. [Operations](Operations) — reading status, diagnostics and metrics
3. [Template Registry](Template-Registry) — what each template accepts
