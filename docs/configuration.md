# lotus-render Configuration

`lotus-render` uses `LOTUS_RENDER_` environment variables backed by `src/app/core/settings.py`.
Invalid required runtime configuration fails at settings load rather than being treated as a
degraded service mode.

## Supported Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `LOTUS_RENDER_SERVICE_NAME` | `lotus-render` | Service identity exposed through OpenAPI and metadata. |
| `LOTUS_RENDER_SERVICE_VERSION` | `0.1.0` | Service version exposed through `/metadata`. |
| `LOTUS_RENDER_ROUNDING_POLICY_VERSION` | `v1` | Rounding policy version exposed through `/metadata`. |
| `LOTUS_RENDER_ENVIRONMENT` | `development` | Runtime environment label. |
| `LOTUS_RENDER_DEFAULT_OUTPUT_FORMAT` | `pdf` | Default render output format. Must be listed in supported output formats. |
| `LOTUS_RENDER_RUNTIME_ENGINE` | `typst` | Configured render engine family. |
| `LOTUS_RENDER_RUNTIME_ENGINE_VERSION` | `0.14.2` | Governed runtime engine version posture. |
| `LOTUS_RENDER_SUPPORTED_OUTPUT_FORMATS` | `["pdf"]` | Supported render output formats. `pdf` is required. |
| `LOTUS_RENDER_TEMPLATE_REGISTRY_PATH` | `templates/registry` | Source-controlled template manifest registry path. |
| `LOTUS_RENDER_RENDER_STORE_PATH` | `data/render-store.sqlite3` | SQLite render job store path. |
| `LOTUS_RENDER_ALLOWED_HOSTS` | `["localhost","127.0.0.1","testserver","lotus-render"]` | Trusted Host boundary for direct HTTP requests. |
| `LOTUS_RENDER_CORS_ALLOWED_ORIGINS` | `[]` | CORS allow-list. Empty by default because browser ingress is platform-governed. |
| `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES` | `5242880` | Maximum accepted request body size for render API requests. |
| `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS` | `60` | Typst/Docker compile timeout. Timed-out renders persist as `failed` with category `timeout`. |
| `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` | `300` | Stale threshold for persisted `accepted` render jobs used by `/metadata`, diagnostics, and metrics. |
| `LOTUS_RENDER_STALE_RENDERING_SECONDS` | `900` | Stale threshold for persisted `rendering` render jobs used by `/metadata`, diagnostics, and metrics. |
| `LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE` | `false` | Rejects `:memory:` render stores when an environment requires persistent render truth. |

Docker Compose overrides `LOTUS_RENDER_RENDER_STORE_PATH` to
`/var/lib/lotus-render/render-store.sqlite3`, mounts the named `lotus-render-data` volume there,
and sets `LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE=true`.

## Boundary Rules

- `allowed_hosts` is a direct-service safety boundary, not an authentication mechanism.
- CORS is disabled by default. Client-facing browser access must flow through governed platform
  ingress and service-to-service policy.
- Oversized request bodies return `413 request_body_too_large` with correlation and trace
  identifiers when supplied, and never echo render-package payload content.
- `/health/ready` requires drain posture, render-store readiness, and executable Typst or Docker
  runtime availability.
- `/metadata` publishes `runtimeAvailable` through
  `render.observability.render_supportability`; `runtime_configuration_unavailable` means
  deterministic render supportability is unavailable.
- `/metadata` publishes source-backed aggregate stale posture for persisted `accepted` and
  `rendering` jobs using `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` and
  `LOTUS_RENDER_STALE_RENDERING_SECONDS`.
- Render compile timeouts are bounded by `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS` and are
  persisted as support-safe failed render jobs.

## Secret Handling

Current `lotus-render` settings do not include secrets. Do not introduce build, registry, database,
or service credentials through Docker `ARG` or persisted `ENV` defaults. Runtime secrets must be
provided by the deployment platform and kept out of rendered metadata, logs, metrics, and
OpenAPI examples.
