# lotus-render Wiki

Deterministic document rendering service for Lotus reporting.

## Current posture

- separate deployable render service with its own Docker image and independently scalable runtime
- Slice 4 implements health, readiness, metadata, structured request logging, explicit render-attempt domain models, governed render package validation, template registry enforcement, and the first real Typst PDF render path
- `lotus-render` consumes complete render packages only and must not fetch business data directly
- template lifecycle posture is explicit for `active`, `deprecated_rerenderable`, `blocked_for_new_renders`, and `blocked`
- the current determinism claim is bounded to the governed Typst `0.14.2` runtime envelope
- golden proof is minted from the container-first Typst runtime on developer and CI hosts so proof
  is stable across environments

## Registry truth

- manifests live under `templates/registry/`
- `make template-registry-gate` validates registry structure and lifecycle metadata
- current first-wave active template is `portfolio-review` version `v1`
- current first-wave golden proof lives under `tests/golden/portfolio-review/v1/`

See [Template Registry](Template-Registry).

## Operator checks

- `make check`
- `make ci`
- `make template-registry-gate`
- `docker compose up --build`
- `/health`
- `/health/live`
- `/health/ready`
- `/metadata`
