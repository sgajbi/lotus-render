# lotus-render

Deterministic document rendering service for Lotus reporting.

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make check
make ci
```

```powershell
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy --config-file mypy.ini
.venv\Scripts\python.exe scripts/openapi_quality_gate.py
.venv\Scripts\python.exe scripts/validate_template_registry.py
.venv\Scripts\python.exe -m pytest tests/unit tests/integration tests/e2e
.venv\Scripts\python.exe scripts/coverage_gate.py
```

## Run

```powershell
uvicorn app.main:app --reload --port 8310
```

## Docker

```powershell
docker compose up --build
```

## Standards

- CI and governance: .github/workflows/
- Engineering commands: Makefile
- Platform standards docs: docs/standards/

## Current Slice

Slice 5 now adds the first governed internal render API on top of the earlier service, registry,
and Typst proof slices:

- versioned `RenderPackage` contract with strict validation
- source-controlled template manifests under `templates/registry/`
- explicit lifecycle posture for `active`, `deprecated_rerenderable`,
  `blocked_for_new_renders`, and `blocked`
- machine validation through `scripts/validate_template_registry.py` and `make check`
- first governed Typst template under `templates/typst/portfolio-review/v1/`
- golden render package and expected PDF proof under `tests/golden/portfolio-review/v1/`
- docker-governed Typst rendering is preferred on developer and CI hosts so golden proof is minted
  from the same controlled runtime envelope
- bounded-determinism fingerprinting that normalizes volatile PDF metadata while preserving raw
  artifact hashing truth
- sqlite-backed governed render job store at `data/render-store.sqlite3` by default
- internal render API surface:
  - `POST /renders`
  - `GET /renders/{render_job_id}`
  - `GET /renders/{render_job_id}/artifact-metadata`
- idempotent render-job semantics: same `render_job_id` plus same package returns prior truth;
  same `render_job_id` plus different package returns `409 render_job_conflict`
- `/health/ready` now reflects both runtime posture and render-store availability

## Internal Render API

Use `POST /renders` only after upstream report data is already immutable and supportable. The
endpoint accepts a complete `RenderPackage`, validates it against the governed template registry,
executes the synchronous first-wave Typst render path, and returns render truth plus inline
`artifact_base64` on first successful submission.

Use `GET /renders/{render_job_id}` to read support-safe render-job posture without rerunning
anything. Use `GET /renders/{render_job_id}/artifact-metadata` when callers need artifact hash,
size, MIME type, and determinism posture without archive semantics.
