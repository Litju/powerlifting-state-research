"""Home for small public research comparators.

No reference model is implemented at bootstrap. Future comparators must state
their inputs, tuning procedure, task scope, and reproducibility requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ..contracts.serialization import require_scientific_id

ReferenceModels: TypeAlias = tuple[()]
REFERENCE_MODELS: ReferenceModels = ()


def _require_id(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must be non-empty")


def _require_hash(value: str, label: str) -> None:
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
        raise ValueError(f"{label} must be a full prefixed SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ModelReference:
    model_id: str

    def __post_init__(self) -> None:
        require_scientific_id(self.model_id, "model_id")


@dataclass(frozen=True, slots=True)
class TrainingProtocolReference:
    training_protocol_id: str | None
    not_applicable_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.training_protocol_id is None) == (self.not_applicable_reason is None):
            raise ValueError("training protocol ID or a not-applicable reason is required")
        if self.training_protocol_id is not None:
            require_scientific_id(self.training_protocol_id, "training_protocol_id")
        if self.not_applicable_reason is not None:
            _require_id(self.not_applicable_reason, "not_applicable_reason")


@dataclass(frozen=True, slots=True)
class FittedInstanceReference:
    fitted_instance_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        _require_id(self.fitted_instance_id, "fitted_instance_id")
        _require_hash(self.content_sha256, "content_sha256")


@dataclass(frozen=True, slots=True)
class CheckpointReference:
    checkpoint_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        _require_id(self.checkpoint_id, "checkpoint_id")
        _require_hash(self.content_sha256, "content_sha256")


@dataclass(frozen=True, slots=True)
class EnvironmentProvenance:
    environment_id: str
    python_version: str
    platform: str
    dependency_identity: str
    hardware: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("environment_id", self.environment_id),
            ("python_version", self.python_version),
            ("platform", self.platform),
            ("dependency_identity", self.dependency_identity),
        ):
            _require_id(value, label)


class DeterminismStatus(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    SEEDED = "SEEDED"
    NON_DETERMINISTIC = "NON_DETERMINISTIC"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class RNGProvenance:
    status: DeterminismStatus
    seeds: tuple[tuple[str, int], ...] = ()
    explanation: str | None = None

    def __post_init__(self) -> None:
        if len({name for name, _ in self.seeds}) != len(self.seeds):
            raise ValueError("RNG seed names must be unique")
        if self.status is DeterminismStatus.SEEDED and not self.seeds:
            raise ValueError("SEEDED provenance requires at least one seed")
        if self.status in {
            DeterminismStatus.NON_DETERMINISTIC,
            DeterminismStatus.NOT_APPLICABLE,
        } and not (self.explanation and self.explanation.strip()):
            raise ValueError("non-deterministic and not-applicable RNG states need an explanation")
