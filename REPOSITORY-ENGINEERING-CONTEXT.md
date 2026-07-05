# Repository Engineering Context

## Repository Role

`lotus-render` is the Lotus document rendering service. It owns deterministic report rendering from
governed render packages into supported output artifacts and exposes only support-safe render
diagnostics and metadata.

## Business And Domain Responsibility

`lotus-render` owns rendering execution, template registry governance, render-attempt diagnostics,
artifact hashing, and render-engine runtime posture for enterprise reporting. It does not own
report-data assembly, upstream domain data retrieval, archive lifecycle, or replay/rerender
operator workflows beyond the render-stage contract defined by RFC-0102.

## Current-State Summary

`lotus-render` implements the RFC-0102 render-service side for the first-wave portfolio review PDF
flow. The repository contains the dedicated render-service runtime baseline, explicit render-attempt
domain models, structured request logging, support-safe system metadata, versioned render package
validation, source-controlled template registry enforcement, deterministic SVG chart asset
generation, the modular Typst portfolio review template, golden PDF proof, and the first
store-backed internal render API. RFC-0105 first-wave render metrics now expose bounded render
submission, status lookup, diagnostics lookup, artifact metadata lookup, latency,
failure-category, artifact-size, and source-backed stale in-flight render signals without
high-cardinality or sensitive labels. RFC-0108 render supportability now publishes
`render.observability.render_supportability` through `/metadata` and
`lotus_render_supportability_total`, backed by drain state, render-store readiness,
template-registry availability, executable Typst/Docker runtime configuration, and aggregate
`accepted`/`rendering` stale posture. HTTP boundary configuration is explicit through the
`LOTUS_RENDER_` settings contract, including trusted hosts, CORS allow-listing, request body
limits, persistent-store enforcement, compile timeouts, and stale in-flight thresholds.
The render store now uses versioned SQLite migrations, readiness-time schema validation, and
support-safe source evidence persistence for snapshot identity, lineage refs, disclosure refs,
caller identity, and package correlation/trace identifiers. Local Docker Compose mounts the store
on a named volume so render-job state survives container recreation in the supported local runtime.
Consumer-facing governance is declared in `contracts/render-supported-features.v1.json`,
`contracts/render-source-contracts.v1.json`, and `contracts/render-data-product-trust.v1.json`;
unit tests validate those contracts against the live template registry, OpenAPI paths, and metric
contracts.
RFC40-WTBD-004 Slice 1 adds the
first-wave `proof-pack v1` template and registry manifest for
`dpm_proof_pack_report_input.v1`, establishing deterministic render-service support for
pre-trade proof-pack artifacts while keeping proof-pack truth and report-data assembly outside
`lotus-render`. RFC-0042 outcome-review support is active through the `outcome-review v1` template
and `dpm_outcome_report_input.v1` render package contract, establishing post-trade outcome-review
artifact rendering while keeping outcome truth and report-data assembly upstream. RFC41-WTBD-008
adds the first-wave `rebalance-wave v1` template and registry
manifest for `dpm_wave_report_input.v1`, establishing deterministic render-service support for
wave evidence artifacts while keeping wave state, proof-pack linkage, internal handoff evidence,
and report-data assembly outside `lotus-render`. The companion `lotus-report` implementation
submits complete render packages and records render outcomes while keeping business-data assembly
outside `lotus-render`. RFC-0023 Slice 11C adds optional `portfolio-review v1` rendering for
reviewed advisor-use narrative packages emitted by `lotus-report` from `lotus-advise`; the renderer
presents package lineage, review state, source hash, approved narrative text, and disclosure text
without approving, rewriting, inferring, or fetching advisory facts. RFC-0024 Slice 9 adds optional
`portfolio-review v1` rendering for advisor proposal memo packages emitted by `lotus-report` from
`lotus-advise`; the renderer presents memo lineage, advisor-use review posture, memo/source hashes,
section summaries, and disclosure text while keeping client-ready memo publication blocked upstream.

## Architecture And Module Map

Current repository baseline:

1. `src/app/main.py`: FastAPI application factory and lifespan wiring.
2. `src/app/api/routes/`: system routes and internal render APIs.
3. `src/app/contracts/`: OpenAPI-facing response models and render package contracts.
4. `src/app/core/`: settings and logging configuration.
5. `src/app/domain/render_attempts/`: render-attempt lifecycle models.
6. `src/app/domain/templates/`: template manifest models and registry compatibility rules.
7. `src/app/services/`: foundation services, package intake, render submission use case, Typst
   orchestration, and render-engine ports.
8. `src/app/dependencies/`: typed FastAPI dependency providers and the route-facing application
   container.
9. `src/app/infrastructure/`: concrete persistence adapters, including the sqlite-backed governed
   render job state for the first-wave synchronous render lifecycle.
10. `src/app/observability/`: RFC-0105 and RFC-0108 render metrics contracts and bounded
    Prometheus metric emitters.
11. `src/app/middleware/`: correlation, HTTP-boundary, and structured request logging middleware.
12. `templates/registry/`: PR-governed template source truth.
13. `templates/typst/`: governed Typst template source.
14. `tests/golden/`: golden render package and artifact proof inputs.
15. `tests/unit`, `tests/integration`, `tests/e2e`: test pyramid baseline.
16. `contracts/`: supported-feature, source-contract, and data-product trust declarations.

## Active Template Inventory

Template lifecycle, report-data contract versions, and disclosure fragments are governed by
`templates/registry/` and documented in `wiki/Template-Registry.md`. Keep this inventory aligned
whenever a template is added, deprecated, blocked, or moved across ownership boundaries.

| Template | Version | Report data contract | Upstream package owner | Render boundary |
| --- | --- | --- | --- | --- |
| `portfolio-review` | `v1` | `portfolio_review.v1` | `lotus-report` | Client/advisor portfolio review presentation only. |
| `outcome-review` | `v1` | `dpm_outcome_report_input.v1` | `lotus-report` with outcome evidence from `lotus-manage` | Post-trade outcome-review artifact rendering only. |
| `proof-pack` | `v1` | `dpm_proof_pack_report_input.v1` | `lotus-report` with proof-pack evidence from `lotus-manage` | Pre-trade proof-pack artifact rendering only. |
| `rebalance-wave` | `v1` | `dpm_wave_report_input.v1` | `lotus-report` with wave evidence from `lotus-manage` | Rebalance wave evidence artifact rendering only. |

## Runtime And Integration Boundaries

1. Runtime model: standalone backend service with its own Docker image and independently scalable
   runtime.
2. Upstream dependencies: `lotus-report` submits complete render packages through the internal
   render API; future platform ingress and service-to-service auth flow through Lotus platform
   conventions.
3. Downstream consumers: `lotus-report` first; `lotus-gateway` only if support-safe operator
   surfaces are later added through governed APIs.
4. Boundary rules:
   - `lotus-render` must not fetch business data directly from domain services.
   - `lotus-render` consumes complete render packages only.
   - advisor-use narrative rendering is presentation-only and must be backed by the
     `reviewed_advisory_narrative` package in `report_data`.
   - `lotus-render` returns render artifacts and support-safe diagnostics, not archive truth.
   - `lotus-render` owns render-engine/runtime posture, template compatibility, and artifact hash
     generation.
   - developer and CI proof should prefer the governed Typst container runtime when Docker is
     available; local Typst is fallback only when Docker is unavailable.
   - direct service HTTP access is bounded by trusted-host and request-body-size controls; browser
     access and authentication remain platform-ingress responsibilities until governed otherwise.

## Repo-Native Commands

1. Install/bootstrap: `make install`
2. Lint: `make lint`
3. Typecheck: `make typecheck`
4. Template registry validation: `make template-registry-gate`
5. Unit tests: `make test-unit`
6. Integration tests: `make test-integration`
7. CI parity: `make check` and `make ci`
8. Local runtime: `uvicorn app.main:app --reload --port 8310`

## Validation And CI Expectations

`lotus-render` follows the standard Lotus backend lane model scaffolded by
`automation/New-Lotus-Service.ps1`.

Key expectations:

1. local fast gate: `make check`
2. repo-native full gate: `make ci`
3. Docker build must stay green because the service is independently deployable
4. OpenAPI quality, strict typing, coverage gate, and security audit are all part of baseline CI

## Standards And RFCs That Govern This Repository

Primary governing artifacts:

1. `lotus-platform/rfcs/RFC-0102-render-package-template-registry-and-render-service.md`
2. `lotus-platform/rfcs/RFC-0099-enterprise-reporting-and-document-archive-target-architecture.md`
3. `lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
4. `lotus-platform/rfcs/RFC-0084-mesh-governance.md`
5. `lotus-platform/rfcs/RFC-0091-enterprise-data-mesh-maturity-and-production-readiness.md`

## Known Constraints And Implementation Notes

1. The repository owns only render-stage behavior. `POST /renders`, render status,
   artifact-metadata reads, template compatibility, bounded-determinism diagnostics, and governed
   portfolio-review template rendering are in scope; report package assembly remains in
   `lotus-report`.
2. Keep render/data/archive boundaries strict from the start. Do not let `lotus-render` become a
   business-data authority.
3. Update repo-local wiki source and platform RFC/context truth when service ownership or runtime
   contracts change.
4. Determinism is currently bounded to the governed Typst `0.14.2` runtime envelope; raw artifact
   hashes remain truthful, while bounded-determinism proof normalizes volatile PDF metadata fields.
5. The committed first-wave golden PDF is minted from the governed container-first Typst envelope so
   CI, local proof, and the future service image stay aligned.
6. `/health/ready` should remain truthful for both runtime posture and render-store availability,
   because the first-wave render APIs depend on persisted render-job state.
7. Render metrics must remain bounded to operation, status, failure category, artifact-size, and
   supportability/stale in-flight posture. Do not add render job, report job, portfolio, tenant,
   trace, correlation, raw package, or storage labels.
8. HTTP routes should consume typed dependencies from `src/app/dependencies/` rather than reading
   concrete adapters from raw `app.state`; route tests should use app-factory instances and
   dependency overrides instead of the module-level singleton app.
9. Persisted render job lifecycle updates are compare-and-set transitions. Same-package
   `accepted`, `rendering`, `rendered`, and `failed` replays return prior truth without rerunning
   the renderer; terminal states are immutable unless a future governed recovery workflow changes
   that contract.
10. Settings live behind the `LOTUS_RENDER_` contract documented in `docs/configuration.md`.
    Required invalid configuration fails at service startup; runtime unavailability reports as
    `runtime_configuration_unavailable`; Typst/Docker compile timeouts persist as failed render
    jobs with category `timeout`.
11. Render-store migrations are applied on startup and validated by readiness. The render store owns
    render-stage lifecycle, idempotency, support-safe evidence, diagnostics, and artifact hashes;
    archive retention, legal hold, retrieval, and distribution remain out of scope for
    `lotus-render`.
12. Persisted non-terminal render states require source-backed aggregate visibility and a typed
    diagnostics handoff. Keep stale classification in store/service policy, expose only bounded
    aggregate metrics, and use `/renders/{render_job_id}/diagnostics` for recovery decisions rather
    than raw logs or raw engine output.

## Context Maintenance Rule

Update this document when:

1. repository ownership changes,
2. repo-native commands or CI gates change,
3. runtime or integration boundaries change,
4. dominant local implementation patterns change,
5. current-state rollout or product posture materially changes.

## Cross-Links

1. `lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `lotus-platform/context/CONTEXT-REFERENCE-MAP.md`
