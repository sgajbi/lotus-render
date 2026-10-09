"""Versioned exact package-member identity, independent of ZIP container attributes."""

import hashlib
import io
from zipfile import ZipFile

DOMAIN = b"lotus-render/composite-xlsx-members/v1\x00"


def workbook_content_fingerprint(artifact: bytes) -> str:
    """Names and payload bytes are length framed; no XML/content normalization occurs.

    Ignore only ZIP compression, ordering and filesystem/header metadata. The raw
    artifact SHA remains the independent identity for transport and Archive custody.
    """
    digest = hashlib.sha256(DOMAIN)
    with ZipFile(io.BytesIO(artifact)) as package:
        names = sorted(package.namelist())
        if len(names) != len(set(names)):
            raise ValueError("composite_workbook_member_duplicated")
        digest.update(len(names).to_bytes(8, "big"))
        for name in names:
            encoded = name.encode("utf-8")
            content = package.read(name)
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return digest.hexdigest()
