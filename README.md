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

Slice 4 now adds real Typst rendering and bounded-determinism proof on top of the earlier service
and registry slices:

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
- `lotus-report` submission stays in a later RFC-0102 slice
