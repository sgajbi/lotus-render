# Service Operations Runbook

## Standard Commands

- make install
- make lint
- make typecheck
- make check
- make ci
- docker compose up --build

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata

## Incident First Checks

1. Check container logs for request failures, correlation IDs, and structured request timing lines.
2. Verify `/health/ready`, `/metadata`, and `/metrics`.
3. Run local fast parity (`make check`) before deeper investigation.
4. Run `make ci` before a hotfix PR.
