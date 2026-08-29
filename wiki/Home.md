# lotus-render

The Lotus platform's document production service. Given a governed template and a complete package
of already-approved data, it produces a **PDF** — deterministically, with evidence of what it
produced and from what.

## Why it exists

A private bank's client-facing documents are a regulated output. The same portfolio review must look
the same, say the same thing, and be reproducible months later when someone asks what the client was
actually sent. Left inside each reporting workflow, document production drifts: layouts diverge,
template changes ship without review, and nobody can prove which version of a document a client
received.

`lotus-render` isolates that concern in one service, with three deliberate consequences:

- **Templates are governed artefacts, not code details.** Every template carries a manifest naming
  its owner, approver, approval date, supported contracts, locales, brand variants and lifecycle
  status. A render is accepted only against a combination that manifest supports.
- **Production is separated from authority.** The service renders what it is given and holds no
  client, portfolio or advisory data of its own. It cannot approve advice, grant publication
  authority, or fill a gap in upstream data — so a rendering change can never quietly become a
  business change.
- **Every artefact is accountable.** Each render returns a truthful artifact hash, a bounded
  determinism fingerprint, the engine version that produced it, and the lineage and disclosure
  references it was rendered from.

The trade is that `lotus-render` is deliberately incapable on its own. It is useful only alongside
the services that own the data — and that is the property that makes it safe.

## Who uses it

| Reader | What matters | Start here |
|---|---|---|
| Business and product | which documents can be produced today, and what the service is not allowed to decide | [Capabilities](#what-it-produces-today), [Template Registry](Template-Registry) |
| Integration engineers | the package contract, idempotency, and error semantics | [API Surface](API-Surface) |
| Operations and support | readiness, stuck renders, diagnostics, alerts | [Operations](Operations) |
| Security and risk | what authenticates a caller, what is persisted, what an artefact proves | [Security and Controls](Security-and-Controls) |
| Engineers on the repo | how it is built, tested and gated | [Development and Testing](Development-and-Testing), [Architecture](Architecture) |

`lotus-report` is the only production caller today: it assembles immutable report data and submits
the complete package. `lotus-archive` owns the artefact's durable home afterwards.

## What it produces today

Four governed templates, all `active`, all PDF, all `en-SG` / `private_banking`:

| template | document | data contract | upstream authority |
|---|---|---|---|
| `portfolio-review v1` | client portfolio review | `portfolio_review.v1` | `lotus-report` |
| `outcome-review v1` | post-trade outcome review | `dpm_outcome_report_input.v1` | `lotus-manage` |
| `proof-pack v1` | pre-trade proof pack | `dpm_proof_pack_report_input.v1` | `lotus-manage`, `lotus-idea` |
| `rebalance-wave v1` | rebalance wave evidence | `dpm_wave_report_input.v1` | `lotus-manage` |

`portfolio-review v1` renders the full client report by default and supports a caller-selected
subset of sections. It can also render an optional reviewed advisory narrative or advisor proposal
memo when `lotus-report` includes an approved advisor-use package from `lotus-advise` — presentation
only, with client-ready publication still blocked upstream.

Each template's contract shape, section list and source-ownership rules are in
[Template Registry](Template-Registry).

## What it does not own

Stated as prohibitions because each has been asked for at least once:

- **domain data** — it fetches nothing; the package is the whole input
- **advisory judgement** — it does not approve, rewrite, infer or fetch advisory facts
- **publication authority** — proof-pack packages carry `client_publication_authority_granted=false`
  and it stays false
- **archive semantics** — retrieval, retention, legal hold, replay, rerender, regenerate and
  distribution belong to `lotus-archive`
- **template authorship** — templates are governed through manifests and PR review, not configured
  at runtime

## Current posture

Implemented and in use:

- the internal render API — submit, status, diagnostics, artifact metadata
- governed package validation against the template registry, with no fallback template
- real Typst PDF rendering for all four active templates, with banked golden proof
- persisted render jobs in a local SQLite store, schema-versioned and validated at readiness
- idempotent submission, bounded execution capacity, bounded compile timeout
- correlation and trace propagation, support-safe request logging, metrics and supportability
  posture

Submission is synchronous for first-wave consumers: `POST /renders` returns the artifact inline on
the call that renders it. There is no queue and no background worker.

Not implemented today — recorded so that absence is not mistaken for capability:

| gap | consequence | tracked |
|---|---|---|
| output formats other than PDF | a settings validator requires `pdf`; another format is a code change | — |
| shared job state | the store is a local file, so one instance cannot report on another's jobs | — |
| enforced durability by default | `REQUIRE_PERSISTENT_RENDER_STORE` is `false`; Docker Compose sets it `true`, bare deployments must too | [#83](https://github.com/sgajbi/lotus-render/issues/83) |
| unconditional request-body cap | the cap is skipped when no `Content-Length` is declared | [#84](https://github.com/sgajbi/lotus-render/issues/84) |

## Validation commands

The repo-native gates. This list is kept honest in both directions by
`tests/unit/test_wiki_gate_coverage.py`, which fails when a gate the blocking workflows run is missing
from this page, and equally when this page names a gate the lanes no longer run.

| command | enforces |
|---|---|
| `make openapi-gate` | operation metadata, response codes, security-posture text, canonical example |
| `make template-registry-gate` | manifest structure and lifecycle metadata |
| `make code-health-gates` | the four gates below, as one target |
| `make complexity-gate` | no rank D–F function, and maximum complexity at or below the banked value |
| `make source-size-gate` | no module past its banked line count |
| `make dead-code-gate` | no vulture finding at 80% confidence |
| `make dependency-hygiene-gate` | no deptry finding |

Baselines are banked at the measured tree with no headroom, and `tests/unit/test_code_health_gates.py`
asserts each threshold equals the measurement and that empty scans fail closed. All three blocking
workflows run the aggregate; a separate liveness fitness test rejects workflow/Make reachability
drift. See [Development and Testing](Development-and-Testing#code-health-gate-liveness).

Operator-facing checks — `/health`, `/health/live`, `/health/ready`, `/metadata`, `/metrics` — are
described in [Operations](Operations).

## The pages

1. [Architecture](Architecture) — how a submission becomes a PDF, and why state is local
2. [API Surface](API-Surface) — the nine operations and their contracts
3. [Template Registry](Template-Registry) — templates, lifecycle, per-template contract shapes
4. [Configuration](Configuration) — every setting, deployment, secrets
5. [Security and Controls](Security-and-Controls) — what protects the service and what does not
6. [Operations](Operations) — health, diagnostics, metrics, incidents
7. [Development and Testing](Development-and-Testing) — building it, testing it, merging it
8. [Glossary](Glossary) — the vocabulary, and where each term is defined
