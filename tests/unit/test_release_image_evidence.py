"""The runtime SBOM gate must be able to tell the image apart from the runner.

The defect it exists to catch produced a plausible, well-formed, complete-looking
inventory of the wrong software: `cyclonedx_py environment` run on the CI runner
describes the environment `make install` built, not the image that ships. Nothing
about that document announces the mistake -- it has components, versions and licences,
and every runtime dependency really is in it, because the runner installs them too.

So the assertions below are about the one property that separates the two
environments, rather than about the document being well formed.
"""

from __future__ import annotations

from scripts.release_image_evidence import _declared_dependencies, evaluate_inventory

RUNTIME, DEV_ONLY = _declared_dependencies()


def test_an_inventory_of_the_shipped_runtime_is_accepted() -> None:
    """The accepted case, so the refusals below mean something.

    Without it a set of refusals is indistinguishable from a check that refuses every
    input, which is the shape my first attempt at a gate in a sibling repository took.
    """

    image_like = RUNTIME | {"click", "h11", "annotated-types", "typing-extensions"}

    failures, leaked = evaluate_inventory(image_like, RUNTIME, DEV_ONLY)

    assert failures == []
    assert leaked == []


def test_an_inventory_taken_on_the_runner_is_refused() -> None:
    """The exact document the previous step produced, and why counts cannot catch it.

    This input satisfies every check that asks whether the SBOM looks complete: it
    contains all seven declared runtime dependencies and more besides. What gives it
    away is what the image cannot contain -- the dev extras, which the Dockerfile never
    installs because it installs `.` without them.
    """

    runner_like = RUNTIME | {"pytest", "ruff", "mypy", "coverage"}

    failures, leaked = evaluate_inventory(runner_like, RUNTIME, DEV_ONLY)

    assert leaked == ["coverage", "mypy", "pytest", "ruff"]
    assert any("did not come from the shipped runtime" in failure for failure in failures), failures


def test_a_missing_runtime_dependency_is_refused() -> None:
    """An image that does not contain what it declares is a different failure.

    Reported separately from the runner case because the operator action differs: one
    is a broken build, the other is an inventory of the wrong machine.
    """

    incomplete = RUNTIME - {"fastapi"}

    failures, _ = evaluate_inventory(incomplete, RUNTIME, DEV_ONLY)

    assert any("fastapi" in failure for failure in failures), failures


def test_an_empty_inventory_cannot_pass() -> None:
    """A scan that found nothing must not read as a clean scan.

    An empty component list satisfies "no dev-only distributions present" perfectly,
    which is how a zero-input check reports success.
    """

    failures, _ = evaluate_inventory(set(), RUNTIME, DEV_ONLY)

    assert any("no components at all" in failure for failure in failures), failures


def test_the_declared_sets_are_disjoint_and_non_empty() -> None:
    """The discriminator is only as good as the two sets it compares.

    If the dev-only set were empty -- an extras rename, a moved dependency -- the
    runner case above would pass and nothing would fail, so the gate would be
    reporting on an empty comparison.
    """

    assert RUNTIME, "no declared runtime dependencies; the completeness half is vacuous"
    assert DEV_ONLY, "no dev-only distributions; the discriminating half is vacuous"
    assert not (RUNTIME & DEV_ONLY), "a distribution is both runtime and dev-only"


def test_the_evidence_script_imports_only_the_standard_library() -> None:
    """It runs where the application is not installed, so it must not need it.

    `make image-provenance-check` and `make runtime-sbom` run in the image-building job,
    which has no virtualenv because building an image needs none. A third-party import
    added here would fail that lane with `ModuleNotFoundError` rather than a provenance
    verdict — and it would fail only in CI, since a developer's checkout has the venv
    that hides it.
    """

    import ast
    import sys
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "scripts" / "release_image_evidence.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    third_party = sorted(name for name in imported if name and name not in sys.stdlib_module_names)

    assert third_party == [], (
        f"{source.name} imports {third_party}, which the image-building job cannot provide"
    )
