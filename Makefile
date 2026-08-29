.PHONY: install lint monetary-float-guard typecheck openapi-gate template-registry-gate test test-unit test-integration test-e2e test-coverage security-audit check ci docker-build clean complexity-gate source-size-gate dead-code-gate dependency-hygiene-gate code-health-gates

# Code-health baselines, banked at the measured tree with no headroom. An allowance above the
# measurement is slack the next change spends, so each of these equals what the tree measures today
# and is asserted as such by tests/unit/test_code_health_gates.py. Reducing them is a separate,
# reviewable change; raising one to go green is not an option. See issue #72.
SOURCE_FILE_MAX_LINES ?= 623
MAX_CYCLOMATIC_COMPLEXITY ?= 10
MAX_HIGH_COMPLEXITY_FUNCTIONS ?= 0

VENV_DIR ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
else
VENV_PYTHON := $(VENV_DIR)/bin/python
endif

install:
	python -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

lint:
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m ruff format --check .
	$(MAKE) monetary-float-guard

monetary-float-guard:
	$(VENV_PYTHON) scripts/check_monetary_float_usage.py

typecheck:
	$(VENV_PYTHON) -m mypy --config-file mypy.ini

openapi-gate:
	$(VENV_PYTHON) scripts/openapi_quality_gate.py

template-registry-gate:
	$(VENV_PYTHON) scripts/validate_template_registry.py

test:
	$(MAKE) test-unit

test-unit:
	$(VENV_PYTHON) -m pytest tests/unit

test-integration:
	$(VENV_PYTHON) -m pytest tests/integration

test-e2e:
	$(VENV_PYTHON) -m pytest tests/e2e

test-coverage:
	COVERAGE_FILE=.coverage.unit $(VENV_PYTHON) -m pytest tests/unit --cov=src --cov-report=
	COVERAGE_FILE=.coverage.integration $(VENV_PYTHON) -m pytest tests/integration --cov=src --cov-report=
	COVERAGE_FILE=.coverage.e2e $(VENV_PYTHON) -m pytest tests/e2e --cov=src --cov-report=
	$(VENV_PYTHON) scripts/coverage_gate.py

security-audit:
	$(VENV_PYTHON) scripts/pip_audit_gate.py

complexity-gate:
	$(VENV_PYTHON) scripts/python_complexity_inventory.py --limit 20 --max-cc $(MAX_CYCLOMATIC_COMPLEXITY) --max-high-complexity $(MAX_HIGH_COMPLEXITY_FUNCTIONS)

source-size-gate:
	$(VENV_PYTHON) scripts/source_size_gate.py --max-lines=$(SOURCE_FILE_MAX_LINES)

dead-code-gate:
	$(VENV_PYTHON) scripts/dead_code_gate.py

dependency-hygiene-gate:
	$(VENV_PYTHON) -m deptry .

code-health-gates: complexity-gate source-size-gate dead-code-gate dependency-hygiene-gate

check: lint typecheck code-health-gates openapi-gate template-registry-gate test

ci: lint typecheck code-health-gates openapi-gate template-registry-gate test-integration test-e2e test-coverage security-audit

docker-build:
	docker build -t backend-service:ci-test .

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache']]; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', '.coverage.unit', '.coverage.integration', '.coverage.e2e']]"
