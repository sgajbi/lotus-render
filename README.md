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
python -m pip install -e '.[dev]'
python -m ruff check . && python -m ruff format --check .
python -m mypy --config-file mypy.ini
python scripts/openapi_quality_gate.py
python -m pytest tests/unit tests/integration tests/e2e
python scripts/coverage_gate.py
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
