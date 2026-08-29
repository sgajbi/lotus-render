# Development and Testing

Setting the service up locally, the commands that matter, and what CI actually enforces.

## Local setup

```powershell
make install                                   # venv + editable install with dev extras
uvicorn app.main:app --reload --port 8310      # run it
docker compose up --build                      # run it the way it is deployed
```

Rendering needs a compile runtime. The runtime probe looks for `docker` or `typst` on `PATH`;
without one the service starts but reports not-ready, and every submission fails with
`engine_unavailable`. **Docker is the preferred path** — golden proof is minted from the same
controlled Typst envelope on developer and CI hosts, so a local `typst` binary at a different
version will produce artifacts that do not match the banked proofs.

## Commands

| command | what it does |
|---|---|
| `make lint` | ruff check, ruff format check, and the monetary-float guard |
| `make typecheck` | mypy against `mypy.ini` |
| `make openapi-gate` | operation metadata, response codes, security-posture text, canonical example |
| `make template-registry-gate` | manifest structure and lifecycle metadata |
| `make security-audit` | governed pip-audit exceptions, then `pip-audit` |
| `make code-health-gates` | complexity, source size, dead code, dependency hygiene |
| `make check` | lint, typecheck, code-health gates, both gates above, **unit tests only** |
| `make ci` | the above plus integration, e2e, coverage and security audit |

`make test` is an alias for `make test-unit`, so `make check` does **not** exercise the integration
or e2e suites. Run `make ci` before opening a PR if the change touches the render path.

## Test layout

| suite | scope |
|---|---|
| `tests/unit` | 18 modules — contracts, services, settings validation, metrics contracts, and CI/code-health fitness functions |
| `tests/integration` | the render API and health surfaces exercised through the running app |
| `tests/e2e` | smoke coverage of the full submit-and-render path |
| `tests/golden` | banked render packages and expected PDFs per active template |

Coverage is enforced at **99%** across the combined suites, computed from separately uploaded
coverage data rather than a single run.

### Golden proof

Each active template has `render-package.json` and `expected.pdf` under
`tests/golden/<template>/v1/`, with provenance recorded in `tests/golden/producer-fixtures.v1.json`.
Nested producer variants — reviewed Idea evidence rendered through `proof-pack v1`, for instance —
carry their own sample. A new active template without a golden sample is a gate failure, not an
oversight to be noticed later.

Because raw PDF bytes are not stable across renders, golden comparison uses the bounded determinism
fingerprint rather than a file hash. See
[Security and Controls](Security-and-Controls#integrity-of-what-is-produced).

### Code-health baselines

The complexity and source-size thresholds are ratchets banked at the measured tree **with no
headroom**, and `tests/unit/test_code_health_gates.py` asserts each threshold *equals* the
measurement. An improvement therefore cannot go unbanked, and a threshold cannot drift above the
tree. Focused negative tests prove threshold violations, real Vulture findings, and empty
complexity/dead-code input all fail loudly.

## What CI runs

Four workflows: the feature lane, the PR merge gate, main releasability, and PR auto-merge. The
three that validate all run the same shape:

```
pip check → make lint → make typecheck → make code-health-gates
          → make openapi-gate → make template-registry-gate → make security-audit
          → pytest (unit | integration | e2e, in parallel)
          → combined coverage --fail-under=99 → make docker-build
```

### Code-health gate liveness

The feature, pull-request, and exact-main workflows each invoke `make code-health-gates` before the
contract and security checks. `tests/unit/test_ci_gate_liveness.py` expands Make dependencies and
workflow invocations, then fails when any gate advertised by `make check` / `make ci` is unreachable
from GitHub Actions. The parser has its own regression proof so a blank recipe or adjacent Make
target cannot be misclassified as a dependency.

`complexity-gate` and `dead-code-gate` also reject zero governed inputs and name the paths they
scanned. This distinguishes a clean result from a missing or misaddressed source tree.

## Merge governance

`main` requires strict PR Merge Gate contexts, conversation resolution, linear history and admin
enforcement.

A pull request additionally may not merge without an exact-head `VERDICT: mergeable` from the review
lead, written by someone other than the change's author (lotus-platform#718). **GitHub does not
enforce this** — `main` requires zero approving reviews, so the verdict is a process rule with no
mechanical backstop. That gap is a gap, not a permission: two merges on 2026-08-26 went through it,
one on a self-written verdict and one on no verdict at all after a rebase silently voided the one
that existed.

Human approval is optional in the sense that GitHub requests no reviewer. It is not optional in the
sense that a verdict may be skipped.

## Documentation changes

Repo-local `wiki/` is the authored source of truth; the GitHub wiki is only a publication target and
must never receive hand-edited content absent from repo source. Update `wiki/` in the same PR as the
change it describes, verify before merge and publish after, using
`lotus-platform/automation/Sync-RepoWikis.ps1`. The full rule is in
[`AGENTS.md`](https://github.com/sgajbi/lotus-render/blob/main/AGENTS.md#wiki-publication-rule).

## Read next

1. [Architecture](Architecture) — the shape the gates are protecting
2. [Template Registry](Template-Registry) — what changes when a template does
3. [API Surface](API-Surface) — the contract the OpenAPI gate enforces
