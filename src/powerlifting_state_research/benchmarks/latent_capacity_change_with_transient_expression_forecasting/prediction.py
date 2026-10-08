"""The concrete public-native prediction-time and output contract."""

from ...contracts.benchmark import DecisionCutoff
from ...contracts.prediction import (
    InformationKind,
    InputField,
    MissingPredictionPolicy,
    NonFiniteOutputPolicy,
    OrderingAlignmentPolicy,
    OutputField,
    PredictionContract,
)
from ...evaluation.identity import QOI_ID, TARGETS, TASK_ID
from .interventions import ORIGIN_DAY

PREDICTION_CONTRACT = PredictionContract(
    task_id=TASK_ID,
    qoi_ids=(QOI_ID,),
    entity_identity_fields=("entity_id",),
    row_identity_fields=("row_id",),
    event_index="day",
    decision_cutoff=DecisionCutoff("day", ORIGIN_DAY),
    cutoff_inclusive=True,
    inputs=(
        InputField("history_through_day_223", InformationKind.HISTORICAL_OBSERVATION),
        InputField("declared_future_plan", InformationKind.DECLARED_FUTURE_PLAN),
    ),
    outputs=tuple(OutputField(name, QOI_ID, "kg") for name in TARGETS),
    task_allows_declared_future_plan=True,
    missing_prediction_policy=MissingPredictionPolicy.REJECT,
    non_finite_output_policy=NonFiniteOutputPolicy.REJECT,
    ordering_alignment_policy=OrderingAlignmentPolicy.ALIGN_BY_DECLARED_KEYS,
    history_observation_last_day=223,
)
PREDICTION_CONTRACT.validate()
