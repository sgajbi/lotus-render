# lotus-render Wiki

Deterministic document rendering service for Lotus reporting.

## Current posture

- separate deployable render service with its own Docker image and independently scalable runtime
- Slice 1 foundation implements health, readiness, metadata, structured request logging, and explicit render-attempt domain models
- render package validation, template registry enforcement, and actual Typst rendering are not implemented yet
- `lotus-render` consumes complete render packages only and must not fetch business data directly

## Operator checks

- `make check`
- `make ci`
- `docker compose up --build`
- `/health`
- `/health/live`
- `/health/ready`
- `/metadata`
