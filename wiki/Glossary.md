# Glossary

The vocabulary `lotus-render` uses, with the page that defines each term authoritatively. Terms are
defined once elsewhere and summarised here for navigation — where the two differ, follow the link.

## The render contract

| term | meaning | defined in |
|---|---|---|
| **render package** | the complete, self-contained input to a render: contract versions, job and snapshot identity, template selection, content and evidence references. The service reads nothing else. | [API Surface](API-Surface#submitting-a-render) |
| **render job** | one submission, identified by `render_job_id`, with a persisted lifecycle and durable evidence | [Architecture](Architecture#job-lifecycle) |
| **report job** | the upstream `lotus-report` unit of work a render belongs to, carried as `report_job_id` | [API Surface](API-Surface#submitting-a-render) |
| **snapshot id** | the identifier of the immutable upstream data the package was built from | [Architecture](Architecture) |
| **lineage refs** | references to the upstream evidence a document was produced from, preserved through the render | [Security and Controls](Security-and-Controls#what-is-persisted) |
| **disclosure refs** | references to the disclosure fragments a template requires and the package supplies | [Template Registry](Template-Registry) |
| **idempotent submission** | resubmitting the same `render_job_id` with the same package returns prior truth without re-rendering; with a different package it is a `409 render_job_conflict` | [API Surface](API-Surface#idempotency-and-conflict) |

## Templates

| term | meaning | defined in |
|---|---|---|
| **template manifest** | the governed file declaring a template's owner, approver, supported contracts, locales, brand variants, output formats and lifecycle status | [Template Registry](Template-Registry) |
| **lifecycle status** | `active`, `deprecated_rerenderable`, `blocked_for_new_renders` or `blocked` — the posture that decides whether a template may take new work | [Template Registry](Template-Registry#current-rules) |
| **report-data contract version** | the versioned shape of `report_data` a template accepts, owned by the upstream service that produces it | [Template Registry](Template-Registry) |
| **golden proof** | the banked render package and expected artifact for an active template, used to detect unintended rendering change | [Development and Testing](Development-and-Testing#golden-proof) |

## Artifacts and determinism

| term | meaning | defined in |
|---|---|---|
| **artifact** | the produced document — a PDF, returned inline on the call that renders it | [API Surface](API-Surface) |
| **`artifact_sha256`** | the truthful hash of the concrete file produced. Not stable across renders. | [Security and Controls](Security-and-Controls#integrity-of-what-is-produced) |
| **bounded determinism fingerprint** | the repeatability claim: stable across renders within the governed Typst runtime envelope, computed after normalising volatile PDF metadata. This is the value to compare, not the file hash. | [Security and Controls](Security-and-Controls#integrity-of-what-is-produced) |
| **runtime envelope** | the pinned engine and version (`typst 0.14.2`) that bounds the determinism claim; changing it invalidates prior comparisons | [Configuration](Configuration#rendering-engine-and-output) |

## Operating

| term | meaning | defined in |
|---|---|---|
| **support-safe** | a response or log constructed so that operating the service does not require access to client data — no raw `report_data`, engine stderr, storage locations or retention truth | [Security and Controls](Security-and-Controls#support-safe-responses) |
| **supportability posture** | whether the service can currently produce complete deterministic rendering evidence, published on `/metadata` with a reason code | [Operations](Operations#supportability-posture) |
| **stale** | a job that has sat in `accepted` or `rendering` past its configured window. Stale makes a lost job *visible*; nothing recovers it automatically. | [Operations](Operations#capacity-and-failure-behaviour) |
| **failure category** | the closed set of reasons a render failed, which determines who owns the fix | [Operations](Operations#diagnosing-one-job) |
| **recovery action** and **handoff owner** | the bounded decision and owner returned by diagnostics, so routing an incident is mechanical rather than judged | [Operations](Operations#diagnosing-one-job) |
| **drain** | the posture in which an instance reports not-ready so traffic stops arriving before it stops working | [Operations](Operations#the-four-surfaces) |

## Scope words that carry weight

| term | meaning |
|---|---|
| **first-wave** | the current synchronous submission model — `POST /renders` renders on the call. There is no queue and no background worker. |
| **presentation-only** | the service renders what it is given; it does not approve, rewrite, infer or fetch the content it presents |
| **client-publication authority** | the upstream right to treat a document as client-ready. `lotus-render` never grants it; proof-pack packages carry `client_publication_authority_granted=false`. |
| **advisor-use** | content approved for an advisor to read, not for a client. Rendering it does not change that. |

## Read next

1. [Home](Home) — what the service is for
2. [Architecture](Architecture) — how these pieces fit together
3. [API Surface](API-Surface) — the contracts the terms describe
