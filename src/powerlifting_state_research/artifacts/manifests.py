"""Minimal typed rights metadata for public artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OriginClass = Literal[
    "NEWLY_AUTHORED",
    "PUBLIC_PROJECTION_OF_FROZEN_SPEC",
    "GENERATED_PUBLIC_ARTIFACT",
    "EXTERNAL_LICENSED_ARTIFACT",
]


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
