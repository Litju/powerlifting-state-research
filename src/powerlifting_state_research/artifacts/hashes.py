"""Hash public files with a streaming standard-library implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..contracts.serialization import canonical_json_bytes


def sha256_bytes(content: bytes) -> str:
    """Return a full SHA-256 digest with an explicit algorithm prefix."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def sha256_record(value: Any) -> str:
    """Hash a typed record using the package's canonical JSON encoding."""
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of one file without loading it all into memory."""
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def sha256_file_content(path: str | Path) -> str:
    """Return the prefixed content hash of a file without loading it in memory."""
    return "sha256:" + sha256_file(path)
