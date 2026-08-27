# Operations

How to tell whether `lotus-render` is healthy, what a stuck render looks like, and where the
detailed procedures live. The alert-by-alert runbook is not repeated here — it is authored in the
repository and linked below.

## The four surfaces

| surface | answers |
|---|---|
| `GET /health/live` | is the process up? — nothing else |
| `GET /health/ready` | should this instance receive render traffic? |
| `GET /metadata` | what posture is it in, and can it produce deterministic evidence? |
| `GET /metrics` | how much work, how fast, failing how? |

`/health/ready` is the one that matters for routing. It requires **three** things at once: the
instance is not draining, the render store is readable and schema-current, and an executable Typst
or Docker runtime is present. A process that is live but has lost its compile runtime is live and
not ready — that distinction is the point of having both.

## Supportability posture

`/metadata` publishes `render.observability.render_supportability`, derived from drain state, render
store readiness, template registry availability and runtime availability. Treat
`state=unavailable` as operator-impacting: the service cannot produce complete deterministic
rendering evidence, whatever it may still be returning.

The reason code names which of the four failed. `runtime_configuration_unavailable` means neither a
governed Docker runtime nor a local Typst binary is executable from the service process — do not
route new render traffic until `/health/ready` is ready and `/metadata` reports
`runtimeAvailable=true`.

`/metadata` also publishes aggregate stale posture for persisted `accepted` and `rendering` jobs, so
a backlog of jobs going nowhere is visible without querying them one at a time.

## Diagnosing one job

`GET /renders/{render_job_id}/diagnostics` takes a job id from an incident ticket and returns a
bounded decision rather than raw material: stale posture, whether the job is retryable, a recovery
action and a handoff owner.

The vocabulary is closed — these are the only values any of them can take:

| field | values |
|---|---|
| `status` | `accepted`, `rendering`, `rendered`, `failed` |
| `stale_state` | `fresh`, `stale`, `not_applicable` |
| `failure_category` | `package_validation_failed`, `template_not_supported`, `template_render_failed`, `engine_unavailable`, `artifact_validation_failed`, `timeout`, `operator_intervention_required` |
| `recovery_action` | `wait_for_completion`, `resubmit_identical_package_or_escalate_runtime`, `read_artifact_metadata`, `fix_upstream_render_package`, `fix_template_registry_or_package`, `escalate_render_runtime`, `escalate_template_support`, `escalate_reporting_platform` |
| `handoff_owner` | `lotus-render`, `lotus-report`, `template-owner`, `reporting-platform-on-call` |

Because they are closed sets, the routing decision is mechanical: the category identifies whose
problem it is, and the owner field says so directly. A package that failed validation is
`lotus-report`'s; an unsupported template is the template owner's; an unavailable engine or a
timeout is the platform on-call's. The full state-to-action matrix is in the
[service operations runbook](https://github.com/sgajbi/lotus-render/blob/main/docs/runbooks/service-operations.md#render-job-diagnostics-and-recovery-matrix).

Two points that mislead if missed:

- **`409 render_artifact_not_ready` is not a render state.** It means artifact metadata was
  requested before a successful render. Call diagnostics for the same id to find out why.
- **Recovering a stale job means resubmitting the *identical* package.** Submission is idempotent on
  id plus package, so an identical resubmit is safe; a modified one is a `409 render_job_conflict`.

## Metrics

Render submission, status lookup, diagnostics lookup, artifact-metadata lookup, latency,
failure category, artifact size, stale in-flight jobs and supportability state are all exported.
Labels are bounded by construction — no render job id, report job id, portfolio, tenant, trace,
correlation or storage label ever appears, and unknown label values fall back to a known value at
the recorder rather than creating a new series.

The metric, dashboard and alert contract is authored at
[`docs/operations/rendering-observability-metrics.md`](https://github.com/sgajbi/lotus-render/blob/main/docs/operations/rendering-observability-metrics.md),
and the six alert runbooks — submission failure rate, capacity exhaustion, p95 latency, artifact
size, supportability unavailable, stale in-flight jobs — are in the
[service operations runbook](https://github.com/sgajbi/lotus-render/blob/main/docs/runbooks/service-operations.md#alert-runbooks).

## Capacity and failure behaviour

Compilation is blocking work on a bounded threadpool, so capacity is a hard number, not a soft
degradation:

- at the concurrency limit, `POST /renders` returns `429 render_execution_capacity_exhausted`
  immediately rather than queueing — callers retry the identical package
- a compile exceeding the timeout persists as `failed` with category `timeout`, so an overrun leaves
  durable evidence instead of a held thread
- an unavailable engine fails readiness, so the instance stops receiving traffic rather than
  accepting jobs it cannot compile

What the service will not do on its own is recover a job that went stale. There is no reaper: the
stale windows make a lost job *visible*, and resubmission is the operator's action.

## Incident first checks

The ordered checklist — logs, readiness, supportability, the affected job's posture, then the
registry, OpenAPI and dependency gates — is in the
[service operations runbook](https://github.com/sgajbi/lotus-render/blob/main/docs/runbooks/service-operations.md#incident-first-checks).

## Read next

1. [Configuration](Configuration) — the controls behind these behaviours
2. [API Surface](API-Surface) — the status and error contracts
3. [Architecture](Architecture) — why a job belongs to one instance
