# Configuration

`lotus-render` runtime settings use the `LOTUS_RENDER_` prefix and are documented in
`docs/configuration.md` in the repository source.

## Operator-Relevant Controls

- trusted hosts are enforced for direct service HTTP requests
- CORS is disabled by default and browser-facing access remains platform-ingress governed
- render API body size is bounded by `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES`
- render execution concurrency is bounded by `LOTUS_RENDER_RENDER_EXECUTION_CONCURRENCY_LIMIT`
- `/health/ready` requires render-store readiness and executable Typst or Docker runtime
- `/metadata` publishes `runtimeAvailable` through RFC-0108 render supportability
- Typst/Docker compile execution is bounded by `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS`
- stale accepted/rendering posture is bounded by `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` and
  `LOTUS_RENDER_STALE_RENDERING_SECONDS`
- timed-out render jobs persist as `failed` with failure category `timeout`

Current settings do not include secrets. Do not add build or runtime secrets through Docker `ARG`
or persisted `ENV` defaults.
