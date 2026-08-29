"""Content hash of a template directory.

Lives in the domain because the template registry verifies a manifest against the
bytes it describes, and the domain must not depend on a service to do it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Where the shared design module lives, relative to the template source root, and the
# namespace its files occupy inside a digest.
SHARED_TEMPLATE_ID = "_shared"
SHARED_TEMPLATE_VERSION = "v1"
SHARED_DIGEST_PREFIX = "_shared/"


def template_digest(template_directory: Path, *, shared_directory: Path | None = None) -> str:
    """A content hash of everything that produced a document.

    ``template_version`` names a directory, and that directory is mutable: nothing binds
    v1 to the bytes it held when a job rendered. Recording the digest makes a divergence
    detectable and explainable afterwards, which is what the evidence chain needs -- and
    it matters more because a rendered artifact is not re-fetchable, so re-obtaining a
    document means re-rendering against whatever the directory contains today (#139).

    The shared design module is hashed alongside the family's own files. It is compiled
    into every document, so leaving it out would let a palette change alter every
    document while every digest stayed the same -- the digest would attest to bytes that
    were no longer the whole story. Its entries are namespaced, so a shared file and a
    family file of the same name cannot be mistaken for each other.

    Paths are relative and sorted so the digest is stable across machines and checkouts.
    """
    digest = hashlib.sha256()
    _absorb(digest, template_directory, prefix="")
    if shared_directory is not None:
        _absorb(digest, shared_directory, prefix=SHARED_DIGEST_PREFIX)
    return f"sha256:{digest.hexdigest()}"


def _absorb(digest: "hashlib._Hash", directory: Path, *, prefix: str) -> None:
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        # Length-prefixed so no separator byte can appear in a path or a file and
        # make two different template trees hash alike.
        name = (prefix + path.relative_to(directory).as_posix()).encode("utf-8")
        content = path.read_bytes()
        digest.update(str(len(name)).encode("ascii"))
        digest.update(name)
        digest.update(str(len(content)).encode("ascii"))
        digest.update(content)
