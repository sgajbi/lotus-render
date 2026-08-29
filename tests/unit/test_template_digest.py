"""A rendered document must be able to name the template bytes that produced it.

`template_version` names a directory, and that directory is mutable: nothing bound `v1`
to the bytes it held when a job rendered, and the registry gate never read
`templates/typst/` at all. Recording a digest makes a divergence detectable and
explainable after the fact, which is what the evidence chain needs -- and it matters
because a rendered artifact is not re-fetchable, so re-obtaining a document means
re-rendering against whatever the directory contains today (issue #139).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.domain.templates.digest import template_digest
from app.domain.templates.registry import TemplateRegistry, TemplateRegistryError

PORTFOLIO = Path("templates/typst/portfolio-review/v1")


def test_the_digest_is_stable_for_unchanged_template_bytes() -> None:
    assert template_digest(PORTFOLIO) == template_digest(PORTFOLIO)


def test_the_digest_distinguishes_two_templates() -> None:
    assert template_digest(PORTFOLIO) != template_digest(Path("templates/typst/outcome-review/v1"))


def test_a_one_character_template_edit_changes_the_digest(tmp_path: Path) -> None:
    """The whole point: an edit to a published version must be detectable afterwards."""

    original = tmp_path / "original"
    edited = tmp_path / "edited"
    shutil.copytree(PORTFOLIO, original)
    shutil.copytree(PORTFOLIO, edited)
    target = edited / "_theme.typ"
    target.write_text(target.read_text(encoding="utf-8") + "\n// one character\n", encoding="utf-8")

    assert template_digest(original) != template_digest(edited), (
        "an edited template produced the same digest, so a change to a published version "
        "would still be unexplainable after the fact"
    )


def test_the_digest_covers_file_names_not_only_contents(tmp_path: Path) -> None:
    """Renaming a file changes the template even when every byte is still present."""

    original = tmp_path / "a"
    renamed = tmp_path / "b"
    shutil.copytree(PORTFOLIO, original)
    shutil.copytree(PORTFOLIO, renamed)
    (renamed / "_theme.typ").rename(renamed / "_palette.typ")

    assert template_digest(original) != template_digest(renamed)


def test_the_registry_refuses_a_template_that_no_longer_matches_its_manifest(
    tmp_path: Path,
) -> None:
    """An unreviewed template edit must never be served.

    The manifest now names the bytes it describes, so a published template changed
    without its manifest being updated fails at load rather than being discovered later
    from a diverged render digest. Before this the registry gate never read
    `templates/typst` at all (issue #139).
    """

    source = tmp_path / "typst"
    shutil.copytree("templates/typst", source)
    theme = source / "portfolio-review" / "v1" / "_theme.typ"
    theme.write_text(theme.read_text(encoding="utf-8") + "\n// unreviewed edit\n", encoding="utf-8")

    with pytest.raises(TemplateRegistryError, match="template digest mismatch"):
        TemplateRegistry.load_from_directory(
            Path("templates/registry"), template_source_root=source
        )


def test_the_registry_loads_when_every_manifest_matches_its_template() -> None:
    registry = TemplateRegistry.load_from_directory(Path("templates/registry"))

    assert registry.export_manifests(), "the registry loaded no manifests"


def test_a_missing_template_directory_fails_closed(tmp_path: Path) -> None:
    """A manifest describing a directory that is not there cannot be honoured."""

    with pytest.raises(TemplateRegistryError, match="template source missing"):
        TemplateRegistry.load_from_directory(
            Path("templates/registry"), template_source_root=tmp_path / "absent"
        )


def test_template_sources_are_line_ending_stable() -> None:
    """The digest hashes file bytes, so a CRLF checkout would change it.

    `.gitattributes` sets `* text=auto eol=lf`, which is what keeps the digest identical
    on Windows and on CI. If that ever changed, the manifest would match on one platform
    and fail closed on the other -- a confusing failure that would look like tampering.
    """

    offenders = [
        str(path)
        for path in sorted(Path("templates/typst").rglob("*.typ"))
        if b"\r\n" in path.read_bytes()
    ]

    assert not offenders, (
        "these template sources use CRLF, so their digest differs from a LF checkout and "
        f"the registry would refuse to load on the other platform: {offenders}"
    )
