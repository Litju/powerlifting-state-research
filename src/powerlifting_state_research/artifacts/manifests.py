"""Minimal typed rights metadata for public artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

OriginClass = Literal[
    "NEWLY_AUTHORED",
    "PUBLIC_PROJECTION_OF_FROZEN_SPEC",
    "GENERATED_PUBLIC_ARTIFACT",
    "EXTERNAL_LICENSED_ARTIFACT",
]


@dataclass(frozen=True, slots=True)
class RightsMetadata:
    license_expression: str
    copyright_holder: str
    redistribution_status: str
    access_conditions: str | None = None

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.license_expression,
                self.copyright_holder,
                self.redistribution_status,
            )
        ):
            raise ValueError(
                "rights metadata must identify license, holder, and redistribution status"
            )


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    artifact_id: str
    artifact_kind: str
    license_expression: str
    copyright_holder: str
    origin_class: OriginClass
    source_reference: str | None
    sha256: str | None
    redistribution_status: str
    access_conditions: str | None
    generated_at: str | None
    tool_identity: str | None

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.artifact_kind.strip():
            raise ValueError("artifact identity and kind must be non-empty")
        if not self.license_expression.strip() or not self.copyright_holder.strip():
            raise ValueError("artifact license and copyright holder must be explicit")
        if self.sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("artifact SHA-256 must be 64 lowercase hexadecimal characters")
