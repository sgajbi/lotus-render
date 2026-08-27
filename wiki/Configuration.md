# Configuration

The authoritative catalogue of every setting `lotus-render` reads, the default that applies when
the variable is unset, and the deployment rules that go with it. Taken from
[`src/app/core/settings.py`](https://github.com/sgajbi/lotus-render/blob/main/src/app/core/settings.py)
on `main`; if this page and that file disagree, the file is right and this page is a bug.

All variables take the **`LOTUS_RENDER_`** prefix. Invalid required configuration fails at settings
load — the service does not start in a degraded mode.

## What the defaults mean

Four facts are worth knowing before changing anything, because each is a property of the service
rather than of one setting:

1. **Output is PDF only.** `supported_output_formats` defaults to `("pdf",)`, and a settings
   validator rejects any configuration that omits `pdf` outright — `"pdf output support is required
   for lotus-render"`. Another format is not a configuration change.
2. **Rendering is Typst.** `runtime_engine` defaults to `typst` at version `0.14.2`. The runtime
   probe looks for `docker` or `typst` on `PATH`; without one of them the service cannot compile.
3. **State is a local SQLite file** at `data/render-store.sqlite3`, not a shared database. That
   makes a render job's lifecycle local to the instance that accepted it.
4. **Persistence is not required by default.** `require_persistent_render_store` is `false`, so a
   bare deployment can run with `render_store_path=":memory:"` and lose accepted jobs on restart.
   The supplied Docker Compose file sets it to `true`; anything not using that file must set it
   deliberately. See [#83](https://github.com/sgajbi/lotus-render/issues/83).

## Service identity

| variable | default |
|---|---|
| `LOTUS_RENDER_SERVICE_NAME` | `lotus-render` |
| `LOTUS_RENDER_SERVICE_VERSION` | `0.1.0` |
| `LOTUS_RENDER_ENVIRONMENT` | `development` |
| `LOTUS_RENDER_ROUNDING_POLICY_VERSION` | `v1` |

Service name, version and rounding-policy version are published through `/metadata`.

## Rendering engine and output

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RUNTIME_ENGINE` | `typst` | |
| `LOTUS_RENDER_RUNTIME_ENGINE_VERSION` | `0.14.2` | reported in metadata; pin deliberately — it bounds the determinism claim |
| `LOTUS_RENDER_DEFAULT_OUTPUT_FORMAT` | `pdf` | must appear in the supported list |
| `LOTUS_RENDER_SUPPORTED_OUTPUT_FORMATS` | `("pdf",)` | must contain `pdf` |
| `LOTUS_RENDER_TEMPLATE_REGISTRY_PATH` | `templates/registry` | see [Template Registry](Template-Registry) |

Both output settings are cross-checked at startup: `default_output_format` must be one of
`supported_output_formats`, and `pdf` must be present. A configuration that violates either fails to
start rather than starting degraded.

## Render store

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RENDER_STORE_PATH` | `data/render-store.sqlite3` | `:memory:` is accepted unless the flag below forbids it |
| `LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE` | `false` | when `true`, `:memory:` becomes a startup error |

The store schema is versioned through SQLite migrations and validated during readiness, so a store
whose schema is behind the code reports not-ready rather than serving against it.

## Execution limits

These bound how much work one instance will take on, and how long a stuck job stays stuck.

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RENDER_EXECUTION_CONCURRENCY_LIMIT` | `2` | concurrent compiles; over the limit, `POST /renders` returns `429 render_execution_capacity_exhausted` |
| `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS` | `60` | per-compile ceiling; a timeout persists as `failed` with category `timeout` |
| `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` | `300` | an accepted job not started within this window is reported stale |
| `LOTUS_RENDER_STALE_RENDERING_SECONDS` | `900` | a rendering job exceeding this is reported stale |

The two stale windows are what turn a lost job into a reportable state rather than one that waits
forever; they feed `/metadata`, `/renders/{id}/diagnostics` and the stale in-flight metric. Raise
the compile timeout before raising the stale windows — a compile timeout shorter than the work will
fail jobs that would have succeeded, and stale windows shorter than the compile timeout will flag
healthy work as stuck.

## HTTP boundary

| variable | default |
|---|---|
| `LOTUS_RENDER_ALLOWED_HOSTS` | `localhost`, `127.0.0.1`, `testserver`, `lotus-render`, `render.dev.lotus`, `host.docker.internal` |
| `LOTUS_RENDER_CORS_ALLOWED_ORIGINS` | `()` — empty, no cross-origin callers |
| `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES` | `5242880` (5 MiB) |

`allowed_hosts` is a blast-radius boundary, not authentication — see
[Security and Controls](Security-and-Controls) for what actually authenticates a caller. The
local default deliberately admits `render.dev.lotus` for governed platform-ingress validation and
`host.docker.internal` for the supported Report-to-Render Docker path. Production deployments should
carry an explicit environment-scoped allowlist rather than inheriting this one.

CORS is empty by default because browser-facing access is a platform-ingress concern, not a
service concern. Oversized bodies return `413 request_body_too_large` and never echo package
content.

## Deployment

`docker compose up --build` is the supported local deployment and the reference for a real one. It
differs from the bare defaults in exactly two ways, both about durability:

| setting | compose value | why |
|---|---|---|
| `LOTUS_RENDER_RENDER_STORE_PATH` | `/var/lib/lotus-render/render-store.sqlite3` | on the named `lotus-render-data` volume, so job state survives container replacement |
| `LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE` | `true` | makes an in-memory store a startup error rather than a silent risk |

The container healthcheck polls `/health/ready`, so a container whose render store or Typst runtime
is unavailable is reported unhealthy rather than being sent traffic.

Because the store is local, **an instance can only answer for the jobs it accepted**. Run one
instance per store, or route follow-up reads for a `render_job_id` back to the instance that
accepted it.

## Secret handling

`lotus-render` settings contain no secrets today, and that is worth keeping. Do not introduce
build, registry, database or service credentials through Docker `ARG` or persisted `ENV` defaults.
Runtime secrets must come from the deployment platform and stay out of rendered metadata, logs,
metrics and OpenAPI examples.

## Operator-relevant controls

The settings most likely to be changed in response to an incident:

- **rendering is saturated** — `RENDER_EXECUTION_CONCURRENCY_LIMIT`, bearing in mind each compile is
  blocking work, so raising it trades latency for host CPU
- **large documents time out** — `RENDER_COMPILE_TIMEOUT_SECONDS`, then re-check the stale windows
  remain larger than it
- **jobs appear stuck** — `STALE_ACCEPTED_SECONDS` and `STALE_RENDERING_SECONDS` decide when that
  becomes visible; see `GET /renders/{render_job_id}/diagnostics`
- **accepted jobs lost on restart** — `REQUIRE_PERSISTENT_RENDER_STORE=true` plus a real
  `RENDER_STORE_PATH` on durable storage

## Read next

1. [Operations](Operations) — health, metrics and diagnostics
2. [Security and Controls](Security-and-Controls) — what the boundary settings do and do not do
3. [Architecture](Architecture) — why the store is local and what follows from it
