# Service Operations Runbook

## Standard Commands

- make install
- make lint
- make typecheck
- make template-registry-gate
- make check
- make ci
- docker compose up --build
- typst --version

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata

## Incident First Checks

1. Check container logs for request failures, correlation IDs, and structured request timing lines.
2. Verify `/health/ready`, `/metadata`, and `/metrics`.
3. Run `make template-registry-gate` if template manifests or lifecycle posture changed.
4. Render the governed golden package from the container-first Typst envelope if a template or
   runtime change is suspected.
5. Run local fast parity (`make check`) before deeper investigation.
6. Run `make ci` before a hotfix PR.
