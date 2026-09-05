# lotus-render

Deterministic document rendering for the Lotus platform. Given a governed template and a complete
package of already-approved data, `lotus-render` produces a PDF and returns evidence of what it
produced — a truthful artifact hash, a bounded determinism fingerprint, and the engine version that
made it.

It holds no client, portfolio or advisory data of its own, and fetches none. The package is the
whole input.

**Documentation lives in the [wiki](https://github.com/sgajbi/lotus-render/wiki)**, authored in
[`wiki/`](wiki/):

| page | for |
|---|---|
| [Home](https://github.com/sgajbi/lotus-render/wiki/Home) | what the service is for, what it produces today, what it does not own |
| [Architecture](https://github.com/sgajbi/lotus-render/wiki/Architecture) | how a submission becomes a PDF, and why job state is instance-local |
| [API Surface](https://github.com/sgajbi/lotus-render/wiki/API-Surface) | the nine operations, the package contract, idempotency and errors |
| [Template Registry](https://github.com/sgajbi/lotus-render/wiki/Template-Registry) | the four active templates and their contract shapes |
| [Configuration](https://github.com/sgajbi/lotus-render/wiki/Configuration) | every `LOTUS_RENDER_` setting, deployment and secrets |
| [Security and Controls](https://github.com/sgajbi/lotus-render/wiki/Security-and-Controls) | what protects the service, and what a deployment must provide |
| [Operations](https://github.com/sgajbi/lotus-render/wiki/Operations) | readiness, diagnostics, metrics, incidents |
| [Development and Testing](https://github.com/sgajbi/lotus-render/wiki/Development-and-Testing) | building, testing, gating and merging |

## Quick start

```powershell
make install
docker compose up --build
```

Or run it directly — rendering needs `docker` or `typst` on `PATH`, and Docker is the preferred
path because golden proof is minted from the same controlled Typst envelope:

```powershell
uvicorn app.main:app --reload --port 8310
```

## Validate a change

```powershell
make check   # lint, typecheck, code-health gates, openapi + registry gates, unit tests
make ci      # the above plus integration, e2e, coverage and security audit
```

Note that `make check` runs unit tests only. Run `make ci` before opening a PR that touches the
render path. The individual gates and what each enforces are listed in
[Home](https://github.com/sgajbi/lotus-render/wiki/Home#validation-commands).
The feature, pull-request, and exact-main workflows each invoke `make code-health-gates` explicitly;
the unit suite fails if a gate advertised by the local aggregate lanes becomes unreachable in CI.

## Repository documentation

Deep reference material that belongs next to the code rather than in the wiki:

- [`docs/runbooks/service-operations.md`](docs/runbooks/service-operations.md) — alert runbooks,
  recovery matrix, incident first checks
- [`docs/operations/rendering-observability-metrics.md`](docs/operations/rendering-observability-metrics.md)
  — the metric, dashboard and alert contract
- [`docs/portfolio-review-typst-design-system.md`](docs/portfolio-review-typst-design-system.md) —
  layout rhythm, typography scale and component model for the portfolio review template
- [`docs/portfolio-review-attribute-inventory.md`](docs/portfolio-review-attribute-inventory.md) —
  every client-facing report attribute, its source application, and known source gaps
- [`docs/standards/`](docs/standards/) — platform standards this service is held to
- [`AGENTS.md`](AGENTS.md) and [`REPOSITORY-ENGINEERING-CONTEXT.md`](REPOSITORY-ENGINEERING-CONTEXT.md)
  — delivery posture and repository engineering context

## Scope

`lotus-render` owns render execution, render status, artifact identity, support-safe diagnostics,
and delivery of the exact bytes it produced to the configured Archive authority. It persists
Archive's returned custody identifiers and state but does not own archive retrieval, retention,
legal hold, replay, rerender, regenerate, or document distribution — those belong to
`lotus-archive`. The decision to produce a document remains with the calling workflow.
