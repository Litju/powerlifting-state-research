"""Model-facing inputs and a mechanical prediction-time information firewall."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .benchmark import DecisionCutoff, PredictionInformationBoundary
from .serialization import require_scientific_id


class InformationKind(StrEnum):
    HISTORICAL_OBSERVATION = "HISTORICAL_OBSERVATION"
    STATIC_CONTEXT = "STATIC_CONTEXT"
    DECLARED_FUTURE_PLAN = "DECLARED_FUTURE_PLAN"
    FUTURE_REALIZED_PERFORMANCE = "FUTURE_REALIZED_PERFORMANCE"
    FUTURE_OBSERVATION = "FUTURE_OBSERVATION"
    FUTURE_PROCESS_DISTURBANCE = "FUTURE_PROCESS_DISTURBANCE"
    UNKNOWN_FUTURE_INTERVENTION_DEVIATION = "UNKNOWN_FUTURE_INTERVENTION_DEVIATION"
    TARGET_DERIVED = "TARGET_DERIVED"
    EVALUATION_TRUTH = "EVALUATION_TRUTH"


class MissingPredictionPolicy(StrEnum):
    REJECT = "REJECT"
    MARK_TARGET_UNDEFINED = "MARK_TARGET_UNDEFINED"


class NonFiniteOutputPolicy(StrEnum):
    REJECT = "REJECT"
    MARK_TARGET_UNDEFINED = "MARK_TARGET_UNDEFINED"


class OrderingAlignmentPolicy(StrEnum):
    EXACT_ROW_ORDER = "EXACT_ROW_ORDER"
    ALIGN_BY_DECLARED_KEYS = "ALIGN_BY_DECLARED_KEYS"


@dataclass(frozen=True, slots=True)
class InputField:
    name: str
    kind: InformationKind

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("prediction input field names must be non-empty")


@dataclass(frozen=True, slots=True)
class OutputField:
    name: str
    qoi_id: str
    unit: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.qoi_id.strip() or not self.unit.strip():
            raise ValueError("prediction outputs need a field, QOI identity, and unit")
        require_scientific_id(self.qoi_id, "output QOI ID", expected_class="qoi")


@dataclass(frozen=True, slots=True)
class PredictionContract:
    task_id: str
    qoi_ids: tuple[str, ...]
    entity_identity_fields: tuple[str, ...]
    row_identity_fields: tuple[str, ...]
    event_index: str
    decision_cutoff: DecisionCutoff
    cutoff_inclusive: bool
    inputs: tuple[InputField, ...]
    outputs: tuple[OutputField, ...]
    task_allows_declared_future_plan: bool
    missing_prediction_policy: MissingPredictionPolicy
    non_finite_output_policy: NonFiniteOutputPolicy
    ordering_alignment_policy: OrderingAlignmentPolicy
    history_observation_last_day: int | None = None

    def validation_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.task_id.strip() or not self.event_index.strip():
            errors.append("task_id and event_index must be explicit")
        try:
            require_scientific_id(self.task_id, "task ID", expected_class="task")
            for qoi_id in self.qoi_ids:
                require_scientific_id(qoi_id, "QOI ID", expected_class="qoi")
        except ValueError as error:
            errors.append(str(error))
        if self.event_index != self.decision_cutoff.event_index:
            errors.append("decision cutoff and input event index must use the same time coordinate")
        if self.history_observation_last_day is not None:
            cutoff_value = self.decision_cutoff.value
            if (
                not isinstance(self.history_observation_last_day, int)
                or isinstance(self.history_observation_last_day, bool)
                or self.history_observation_last_day < 0
                or (
                    isinstance(cutoff_value, int)
                    and not isinstance(cutoff_value, bool)
                    and self.history_observation_last_day > cutoff_value
                )
            ):
                errors.append("history observations must end at or before the decision cutoff")
        if not self.entity_identity_fields or not self.row_identity_fields:
            errors.append("entity and row identity fields are required")
        if len(self.qoi_ids) != len(set(self.qoi_ids)):
            errors.append("prediction QOI IDs must be unique")
        if len(self.entity_identity_fields) != len(set(self.entity_identity_fields)):
            errors.append("entity identity fields must be unique")
        if len(self.row_identity_fields) != len(set(self.row_identity_fields)):
            errors.append("row identity fields must be unique")
        if not self.qoi_ids or not self.outputs:
            errors.append("at least one QOI and output field are required")
        if set(self.qoi_ids) != {output.qoi_id for output in self.outputs}:
            errors.append("output QOI references must exactly match the declared QOI set")
        names = [field.name for field in self.inputs]
        if len(names) != len(set(names)):
            errors.append("prediction input field names must be unique")
        output_names = [field.name for field in self.outputs]
        if len(output_names) != len(set(output_names)):
            errors.append("prediction output field names must be unique")
        for field in self.inputs:
            if field.kind is InformationKind.DECLARED_FUTURE_PLAN:
                if not self.task_allows_declared_future_plan:
                    errors.append(f"future plan input {field.name!r} is not allowed by the task")
            elif field.kind not in {
                InformationKind.HISTORICAL_OBSERVATION,
                InformationKind.STATIC_CONTEXT,
            }:
                errors.append(f"forbidden prediction input {field.name!r}: {field.kind.value}")
        return tuple(errors)

    def validate(self) -> None:
        errors = self.validation_errors()
        if errors:
            raise ValueError("invalid prediction information boundary: " + "; ".join(errors))

    @property
    def information_boundary(self) -> PredictionInformationBoundary:
        has_plan = any(field.kind is InformationKind.DECLARED_FUTURE_PLAN for field in self.inputs)
        return PredictionInformationBoundary(
            decision_cutoff=self.decision_cutoff,
            cutoff_inclusive=self.cutoff_inclusive,
            history_observation_last_day=self.history_observation_last_day,
            static_or_context_inputs="task-declared fields",
            declared_future_plan_visible=has_plan,
        )
