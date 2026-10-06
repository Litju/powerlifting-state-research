"""Hash public files with a streaming standard-library implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of one file without loading it all into memory."""
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()
