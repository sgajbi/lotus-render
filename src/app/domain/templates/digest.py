"""Content hash of a template directory.

Lives in the domain because the template registry verifies a manifest against the
bytes it describes, and the domain must not depend on a service to do it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def template_digest(template_directory: Path) -> str:
    """A content hash of the template that produced a document.

    ``template_version`` names a directory, and that directory is mutable: nothing binds
    v1 to the bytes it held when a job rendered. Recording the digest makes a divergence
    detectable and explainable afterwards, which is what the evidence chain needs -- and
    it matters more because a rendered artifact is not re-fetchable, so re-obtaining a
    document means re-rendering against whatever the directory contains today (#139).

    Paths are relative and sorted so the digest is stable across machines and checkouts.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in template_directory.rglob("*") if p.is_file()):
        # Length-prefixed so no separator byte can appear in a path or a file and
        # make two different template trees hash alike.
        name = path.relative_to(template_directory).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(str(len(name)).encode("ascii"))
        digest.update(name)
        digest.update(str(len(content)).encode("ascii"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"
