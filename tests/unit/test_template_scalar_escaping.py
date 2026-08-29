"""Scalar report values must never change the structure of the Typst source.

Scalars used to be substituted into two incompatible contexts by blind textual
replacement -- markup (``[${KEY}]``) and string literal (``"${KEY}"``) -- with a single
markup escaper applied to both. That escaper leaves ``"`` live, so a quote in a client
name broke out of the literal into Typst code, and its output ``\\#`` / ``\\[`` are not
valid Typst string escapes, so ordinary punctuation hard-failed the compile (issue #110).

Every scalar placeholder now sits in string-literal context, which makes one escaper
correct everywhere and the invariant statically checkable.
"""

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "templates" / "typst"
CONTEXTS = ROOT / "src" / "app" / "services" / "typst_contexts.py"
GOLDEN_PRODUCER_FIXTURES = Path("tests/golden/producer-fixtures.v1.json")
PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

# A value carrying every character that is special to either Typst context.
HOSTILE_SCALAR = r'Ac"me #1 [Gold] {Fund} $x @y \ end'


def _scalar_keys() -> set[str]:
    """Context keys whose value is an escaped scalar rather than composed markup."""

    tree = ast.parse(CONTEXTS.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key_node, value_node in zip(node.keys, node.values, strict=False):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key_node.value):
                continue
            if ast.unparse(value_node).startswith("escape_typst_string("):
                keys.add(key_node.value)
    keys.update({"DETERMINISM_STATEMENT", "TRACE_ID", "CORRELATION_ID"})
    return keys


def test_every_scalar_placeholder_sits_in_string_literal_context() -> None:
    """The whole fix rests on this: one context means one correct escaper.

    A scalar placeholder outside a string literal would be interpolated as raw markup and
    escaped for the wrong context, which is exactly the defect this closes.
    """

    keys = _scalar_keys()
    assert keys, "no scalar context keys were identified; this test would prove nothing."

    offenders: list[str] = []
    for path in sorted(TEMPLATE_ROOT.rglob("*.typ")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in PLACEHOLDER.finditer(line):
                if match.group(1) not in keys:
                    continue
                # An odd number of quotes before it means the placeholder is inside one.
                if (line[: match.start()].count('"') % 2) != 1:
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno} {match.group(1)}")

    assert not offenders, (
        "these scalar placeholders are substituted outside a string literal, so the value "
        f"lands in markup context and the string escaper is wrong for them: {offenders}"
    )


def _golden_fixtures() -> list[dict[str, str]]:
    manifest = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    fixtures: list[dict[str, str]] = manifest["fixtures"]
    return fixtures


@pytest.mark.parametrize(
    "fixture", _golden_fixtures(), ids=lambda fixture: str(fixture["golden_sample_id"])
)
def test_hostile_scalar_values_render_instead_of_breaking_the_compile(
    fixture: dict[str, str],
) -> None:
    """Every governed template must survive report text full of Typst metacharacters."""

    settings = Settings()
    service = TypstRenderService(
        settings,
        RenderIntakeService(
            TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
        ),
    )
    package = RenderPackage.model_validate_json(
        Path(fixture["package_path"]).read_text(encoding="utf-8")
    )
    report_data = deepcopy(package.report_data)
    poisoned = 0
    for key, value in list(report_data.items()):
        if isinstance(value, str) and len(value) < 200:
            report_data[key] = HOSTILE_SCALAR
            poisoned += 1
    assert poisoned, "the fixture carried no scalar strings to poison."

    result = service.render(package.model_copy(update={"report_data": report_data}))

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")
