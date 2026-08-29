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

from app.services.typst_rendering import template_digest

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
