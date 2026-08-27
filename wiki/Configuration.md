# Configuration

Every setting `lotus-render` reads, with the default that applies when the variable is unset. Taken
from `src/app/core/settings.py` on `main` and verified against it; if this page and that file
disagree, the file is right and this page is a bug.

All variables take the **`LOTUS_RENDER_`** prefix (`env_prefix="LOTUS_RENDER_"`).

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
   deployment can run with `render_store_path=":memory:"` and lose accepted jobs on restart. Setting
   it to `true` makes that combination a startup error rather than a silent risk — do that in any
   environment where an accepted job must survive a restart.

## Service identity

| variable | default |
|---|---|
| `LOTUS_RENDER_SERVICE_NAME` | `lotus-render` |
| `LOTUS_RENDER_SERVICE_VERSION` | `0.1.0` |
| `LOTUS_RENDER_ENVIRONMENT` | `development` |
| `LOTUS_RENDER_ROUNDING_POLICY_VERSION` | `v1` |

## Rendering engine and output

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RUNTIME_ENGINE` | `typst` | |
| `LOTUS_RENDER_RUNTIME_ENGINE_VERSION` | `0.14.2` | reported in metadata; pin deliberately |
| `LOTUS_RENDER_DEFAULT_OUTPUT_FORMAT` | `pdf` | must appear in the supported list |
| `LOTUS_RENDER_SUPPORTED_OUTPUT_FORMATS` | `("pdf",)` | must contain `pdf` |
| `LOTUS_RENDER_TEMPLATE_REGISTRY_PATH` | `templates/registry` | see [Template Registry](./Template-Registry.md) |

Both output settings are cross-checked at startup: `default_output_format` must be one of
`supported_output_formats`, and `pdf` must be present. A configuration that violates either fails to
start rather than starting degraded.

## Render store

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RENDER_STORE_PATH` | `data/render-store.sqlite3` | `:memory:` is accepted unless the flag below forbids it |
| `LOTUS_RENDER_REQUIRE_PERSISTENT_RENDER_STORE` | `false` | when `true`, `:memory:` becomes a startup error |

## Execution limits

These bound how much work one instance will take on, and how long a stuck job stays stuck.

| variable | default | notes |
|---|---|---|
| `LOTUS_RENDER_RENDER_EXECUTION_CONCURRENCY_LIMIT` | `2` | concurrent compiles; Typst work is blocking and runs on a bounded threadpool |
| `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS` | `60` | per-compile ceiling |
| `LOTUS_RENDER_STALE_ACCEPTED_SECONDS` | `300` | an accepted job not started within this window is treated as stale |
| `LOTUS_RENDER_STALE_RENDERING_SECONDS` | `900` | a rendering job exceeding this is treated as stale |

The two stale windows are what turn a lost job into a reportable state rather than one that waits
forever. Raise the compile timeout before raising the stale windows — a compile timeout shorter than
the work will fail jobs that would have succeeded, and stale windows shorter than the compile
timeout will flag healthy work.

## HTTP boundary

| variable | default |
|---|---|
| `LOTUS_RENDER_ALLOWED_HOSTS` | *(bounded list in `settings.py`)* |
| `LOTUS_RENDER_CORS_ALLOWED_ORIGINS` | `()` — empty, no cross-origin callers |
| `LOTUS_RENDER_MAX_REQUEST_BODY_BYTES` | `5242880` (5 MiB) |

## Operator-relevant controls

The settings most likely to be changed in response to an incident:

- **rendering is saturated** — `RENDER_EXECUTION_CONCURRENCY_LIMIT`, bearing in mind each compile is
  blocking work, so raising it trades latency for host CPU
- **large documents time out** — `RENDER_COMPILE_TIMEOUT_SECONDS`, then re-check the stale windows
  remain larger than it
- **jobs appear stuck** — `STALE_ACCEPTED_SECONDS` and `STALE_RENDERING_SECONDS` decide when that
  becomes visible; see `GET /renders/{render_job_id}/diagnostics`
- **accepted jobs lost on restart** — `REQUIRE_PERSISTENT_RENDER_STORE=true` plus a real
  `RENDER_STORE_PATH`

## Read next

1. [Home](./Home.md) — posture, operator checks, scope guardrails
2. [Template Registry](./Template-Registry.md) — template rules and the active set
