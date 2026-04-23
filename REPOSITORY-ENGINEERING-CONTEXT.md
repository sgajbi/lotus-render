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

`lotus-render` is newly scaffolded from Lotus platform automation as the dedicated render service
for RFC-0102. The repository currently holds the governed backend baseline and will next receive
the first rendering slice: service foundation, render attempt model, template registry, and Typst
integration.

## Architecture And Module Map

Current scaffold baseline:

1. `src/app/main.py`: FastAPI application, health/readiness, metadata, and middleware wiring.
2. `src/app/contracts/`: API contracts and OpenAPI-facing models.
3. `src/app/middleware/`: correlation and request middleware.
4. `tests/unit`, `tests/integration`, `tests/e2e`: test pyramid baseline.
5. `docs/standards/`: required engineering standards placeholders to be replaced with service truth.
6. `docs/rfcs/`: repo-local RFC index and future service-local RFC material.

## Runtime And Integration Boundaries

1. Runtime model: standalone backend service with its own Docker image and independently scalable
   runtime.
2. Upstream dependencies: `lotus-report` submits complete render packages; future platform ingress
   and service-to-service auth flow through Lotus platform conventions.
3. Downstream consumers: `lotus-report` first; `lotus-gateway` only if support-safe operator
   surfaces are later added through governed APIs.
4. Boundary rules:
   - `lotus-render` must not fetch business data directly from domain services.
   - `lotus-render` consumes complete render packages only.
   - `lotus-render` returns render artifacts and support-safe diagnostics, not archive truth.
   - `lotus-render` owns render-engine/runtime posture, template compatibility, and artifact hash
     generation.

## Repo-Native Commands

1. Install/bootstrap: `make install`
2. Lint: `make lint`
3. Typecheck: `make typecheck`
4. Unit tests: `make test-unit`
5. Integration tests: `make test-integration`
6. CI parity: `make check` and `make ci`

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

1. The current repository is scaffold baseline only; most standards docs are placeholders until the
   first implementation slice lands.
2. Keep render/data/archive boundaries strict from the start. Do not let `lotus-render` become a
   business-data authority.
3. Update repo-local wiki source and platform RFC/context truth when service ownership or runtime
   contracts change.

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
