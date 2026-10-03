"""The actual CLI must report qualified model agreement through its process exit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Replace only the expensive render boundary. Argument parsing, package construction,
# dispatch, verification and SystemExit remain the real script in a fresh process.
CLI_DRIVER = """
import os
import runpy
from types import SimpleNamespace
from app.domain.render_attempts.models import RenderFailureCategory
from app.services.render_ports import RenderCompileFailedError, RenderEngineTimeoutError
from app.services import typst_rendering

class ControlledRenderer:
    def __init__(self, *args):
        pass

    def render(self, package):
        print("COMPILE", package.render_job_id)
        if not package.render_job_id.startswith("rdr_mix_"):
            raise RuntimeError("CEILING_SEARCH_MUST_NOT_RUN")
        positions = len(package.report_data["top_holdings"])
        transactions = len(package.report_data["transactions"])
        oversized = (positions, transactions) == (3000, 500)
        scenario = os.environ["CAPACITY_PROBE_TEST_SCENARIO"]
        if oversized and scenario == "oversized_renders":
            return SimpleNamespace(artifact_bytes=b"pdf")
        if not oversized and scenario == "valid_mix_refused":
            raise RenderCompileFailedError(
                RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED, "bounded refusal"
            )
        if oversized:
            if scenario.startswith("category:"):
                raise RenderCompileFailedError(
                    RenderFailureCategory(scenario.split(":", 1)[1]), "compile failed"
                )
            if scenario == "timeout":
                raise RenderEngineTimeoutError("compile timeout")
            if scenario == "raw_resource_message":
                raise RuntimeError("resource_limit_exceeded")
            if scenario == "unexpected":
                raise ValueError("invalid configuration")
            if scenario == "import_failure":
                raise ImportError("missing compiler adapter")
            raise RenderCompileFailedError(
                RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED, "bounded refusal"
            )
        return SimpleNamespace(artifact_bytes=b"pdf")

typst_rendering.TypstRenderService = ControlledRenderer
runpy.run_path("scripts/capacity_probe.py", run_name="__main__")
"""


def run_cli(
    scenario: str, *arguments: str, registry: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONPATH=str(ROOT / "src"),
        CAPACITY_PROBE_TEST_SCENARIO=scenario,
    )
    if registry is not None:
        environment["LOTUS_RENDER_TEMPLATE_REGISTRY_PATH"] = registry
    return subprocess.run(
        [sys.executable, "-c", CLI_DRIVER, *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_agreement_returns_zero_and_verification_runs_only_the_five_mixes() -> None:
    result = run_cli("agreement", "--verify-model", "--template-version", "v2")

    assert result.returncode == 0, result.stderr
    assert "the rule held" in result.stdout
    assert "CEILING_SEARCH_MUST_NOT_RUN" not in result.stdout
    assert "--- positions ---" not in result.stdout
    assert [line for line in result.stdout.splitlines() if line.startswith("COMPILE")] == [
        "COMPILE rdr_mix_v2_3000_500",
        "COMPILE rdr_mix_v2_2500_500",
        "COMPILE rdr_mix_v2_500_4000",
        "COMPILE rdr_mix_v2_1500_1500",
        "COMPILE rdr_mix_v2_2800_300",
    ]


@pytest.mark.parametrize("scenario", ["oversized_renders", "valid_mix_refused"])
def test_either_direction_of_model_disagreement_returns_nonzero(scenario: str) -> None:
    result = run_cli(scenario, "--verify-model")

    assert result.returncode != 0
    assert "the rule did not hold" in result.stdout
    assert "the rule is wrong here" in result.stdout


@pytest.mark.parametrize(
    ("scenario", "detail"),
    [
        ("category:template_render_failed", "template_render_failed"),
        ("category:engine_unavailable", "engine_unavailable"),
        ("category:timeout", "timeout"),
        ("timeout", "RenderEngineTimeoutError"),
        ("raw_resource_message", "RuntimeError"),
        ("unexpected", "ValueError"),
        ("import_failure", "ImportError"),
    ],
)
def test_unqualified_failure_cannot_count_as_predicted_memory_refusal(
    scenario: str, detail: str
) -> None:
    result = run_cli(scenario, "--verify-model")

    assert result.returncode != 0
    assert "the rule held" not in result.stdout
    assert "ERROR" in result.stdout
    assert detail in result.stdout


def test_registry_failure_returns_nonzero_before_any_compile(tmp_path: Path) -> None:
    result = run_cli("agreement", "--verify-model", registry=str(tmp_path / "missing"))

    assert result.returncode != 0
    assert "COMPILE" not in result.stdout
    assert "the rule held" not in result.stdout


def test_plain_probe_keeps_its_existing_ceiling_search_dispatch() -> None:
    result = run_cli("agreement", "--low", "1", "--precision", "1")

    assert result.returncode == 0, result.stderr
    assert all(
        f"--- {shape} ---" in result.stdout for shape in ("positions", "transactions", "both")
    )
    assert "verifying" not in result.stdout
