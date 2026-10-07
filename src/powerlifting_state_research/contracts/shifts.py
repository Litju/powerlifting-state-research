"""Small, explicit declarations of source-to-target distribution shifts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .serialization import require_scientific_id


class ShiftCategory(StrEnum):
    ATHLETE_SHIFT = "ATHLETE_SHIFT"
    INITIAL_STATE_SHIFT = "INITIAL_STATE_SHIFT"
    INTERVENTION_SHIFT = "INTERVENTION_SHIFT"
    HORIZON_SHIFT = "HORIZON_SHIFT"
    TEMPORAL_SHIFT = "TEMPORAL_SHIFT"
    OBSERVATION_SHIFT = "OBSERVATION_SHIFT"
    SENSOR_MODALITY_SHIFT = "SENSOR_MODALITY_SHIFT"
    MISSINGNESS_SHIFT = "MISSINGNESS_SHIFT"
    NOISE_SHIFT = "NOISE_SHIFT"
    WORLD_PARAMETER_SHIFT = "WORLD_PARAMETER_SHIFT"
    WORLD_MECHANISM_SHIFT = "WORLD_MECHANISM_SHIFT"
    COMPOSITIONAL_SHIFT = "COMPOSITIONAL_SHIFT"


class SupportRelation(StrEnum):
    MATCHED = "MATCHED"
    OVERLAPPING = "OVERLAPPING"
    COVARIATE_SHIFT = "COVARIATE_SHIFT"
    EXTRAPOLATIVE = "EXTRAPOLATIVE"
    DISJOINT = "DISJOINT"
    MECHANISM_CHANGE = "MECHANISM_CHANGE"


@dataclass(frozen=True, slots=True)
class ShiftDeclaration:
    shift_id: str
    category: ShiftCategory
    source_distribution_ref: str
    target_distribution_ref: str
    changed_axes: tuple[str, ...]
    invariant_axes: tuple[str, ...]
    support_relation: SupportRelation
    support_overlap: str
    hypothesis: str
    task_id: str
    qoi_ids: tuple[str, ...]
    evaluation_id: str
    evidence_status: str

    def __post_init__(self) -> None:
        required = (
            self.shift_id,
            self.source_distribution_ref,
            self.target_distribution_ref,
            self.support_overlap,
            self.hypothesis,
            self.task_id,
            self.evaluation_id,
            self.evidence_status,
        )
        if any(not value.strip() for value in required):
            raise ValueError("shift identity and evidence fields must be non-empty")
        for label, value, expected_class in (
            ("shift ID", self.shift_id, "shift"),
            ("task ID", self.task_id, "task"),
            ("evaluation ID", self.evaluation_id, "evaluation"),
        ):
            require_scientific_id(value, label, expected_class=expected_class)
        if not self.changed_axes or not self.invariant_axes or not self.qoi_ids:
            raise ValueError("a shift needs changed axes, invariant axes, and at least one QOI")
        for qoi_id in self.qoi_ids:
            require_scientific_id(qoi_id, "QOI ID", expected_class="qoi")
        if set(self.changed_axes) & set(self.invariant_axes):
            raise ValueError("a shift axis cannot be both changed and invariant")
        if "OOD" in self.changed_axes or self.support_overlap.strip().upper() == "OOD":
            raise ValueError("OOD alone is not a complete shift declaration")

    def identity_payload(self) -> dict[str, object]:
        return {
            "shift_id": self.shift_id,
            "category": self.category.value,
            "source_distribution_ref": self.source_distribution_ref,
            "target_distribution_ref": self.target_distribution_ref,
            "changed_axes_and_components": sorted(self.changed_axes),
            "invariant_components": sorted(self.invariant_axes),
            "support_change_kind": self.support_relation.value,
            "support_overlap": self.support_overlap,
            "hypothesis": self.hypothesis,
            "task_id": self.task_id,
            "qoi_ids": sorted(self.qoi_ids),
            "evaluation_id": self.evaluation_id,
            "evidence_status": self.evidence_status,
        }
