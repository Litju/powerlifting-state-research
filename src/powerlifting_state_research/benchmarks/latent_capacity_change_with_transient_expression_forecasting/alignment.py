"""Row-key alignment and canonical target-wise metric calculation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from ...contracts.prediction import MissingPredictionPolicy
from ...evaluation.identity import TARGETS
from ...evaluation.metrics import (
    NonFiniteMetricInputPolicy,
    TargetMetrics,
    canonical_target_metrics,
)
from ...evaluation.prediction import PredictionRow
from .dataset import PublicForecastRow


def align_and_score(
    truth_rows: Sequence[PublicForecastRow], predictions: Sequence[PredictionRow]
) -> tuple[TargetMetrics, ...]:
    truth_ids = [row.row_id for row in truth_rows]
    prediction_ids = [row.row_id for row in predictions]
    if len(truth_ids) != len(set(truth_ids)):
        raise ValueError("validation row IDs must be unique")
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("prediction row IDs must be unique")
    missing = sorted(set(truth_ids) - set(prediction_ids))
    extra = sorted(set(prediction_ids) - set(truth_ids))
    if missing or extra:
        raise ValueError(
            f"prediction row IDs must exactly match validation; missing={missing}, extra={extra}"
        )

    by_id = {row.row_id: row for row in predictions}
    output: list[TargetMetrics] = []
    for target in TARGETS:
        truth_values = [cast(dict[str, float], row.targets)[target] for row in truth_rows]
        prediction_values = [float(getattr(by_id[row.row_id], target)) for row in truth_rows]
        output.append(
            canonical_target_metrics(
                target,
                truth_values,
                prediction_values,
                unit="kg",
                missing_prediction_policy=MissingPredictionPolicy.REJECT,
                non_finite_policy=NonFiniteMetricInputPolicy.REJECT,
            )
        )
    return tuple(output)
