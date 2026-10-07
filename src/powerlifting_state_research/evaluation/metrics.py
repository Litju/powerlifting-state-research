"""Canonical target-wise regression metrics with explicit undefined cases."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from ..contracts.prediction import MissingPredictionPolicy


class MetricName(StrEnum):
    RMSE = "RMSE"
    MAE = "MAE"
    R2 = "R²"
    SRE = "SRE(ddof=0)"


class MetricStatus(StrEnum):
    COMPUTED = "COMPUTED"
    UNDEFINED = "UNDEFINED"


class NonFiniteMetricInputPolicy(StrEnum):
    REJECT = "REJECT"
    MARK_TARGET_UNDEFINED = "MARK_TARGET_UNDEFINED"


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric: MetricName
    value: float | None
    unit: str
    status: MetricStatus
    reason: str | None
    sample_count: int

    def __post_init__(self) -> None:
        if not self.unit.strip() or self.sample_count < 0:
            raise ValueError("metric results need a unit and non-negative sample count")
        if self.status is MetricStatus.COMPUTED:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("computed metric values must be finite")
        elif self.value is not None or not self.reason or not self.reason.strip():
            raise ValueError("undefined metrics need no value and an explicit reason")


@dataclass(frozen=True, slots=True)
class TargetMetrics:
    target: str
    target_unit: str
    metrics: tuple[MetricResult, ...]

    def __post_init__(self) -> None:
        if not self.target.strip() or not self.target_unit.strip():
            raise ValueError("target metrics need a target and unit")
        names = [item.metric for item in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("target metric names must be unique")


def _undefined(target_unit: str, sample_count: int, reason: str) -> tuple[MetricResult, ...]:
    return tuple(
        MetricResult(
            metric,
            None,
            target_unit if metric in {MetricName.RMSE, MetricName.MAE} else "1",
            MetricStatus.UNDEFINED,
            reason,
            sample_count,
        )
        for metric in MetricName
    )


def canonical_target_metrics(
    target: str,
    truth: Sequence[float],
    prediction: Sequence[float | None],
    *,
    unit: str,
    missing_prediction_policy: MissingPredictionPolicy = MissingPredictionPolicy.REJECT,
    non_finite_policy: NonFiniteMetricInputPolicy = NonFiniteMetricInputPolicy.REJECT,
) -> TargetMetrics:
    """Calculate RMSE, MAE, R², and population-SD SRE for one aligned target."""
    if not target.strip() or not unit.strip():
        raise ValueError("target and target unit must be explicit")
    if len(truth) != len(prediction):
        raise ValueError("truth and prediction lengths must match exactly")
    count = len(truth)
    if count == 0:
        return TargetMetrics(target, unit, _undefined(unit, 0, "EMPTY_TRUTH"))
    if any(value is None for value in prediction):
        if missing_prediction_policy is MissingPredictionPolicy.REJECT:
            raise ValueError("missing predictions are rejected by the declared evaluation policy")
        return TargetMetrics(target, unit, _undefined(unit, count, "MISSING_PREDICTION"))
    values = tuple(value for value in prediction if value is not None)
    if any(not math.isfinite(value) for value in truth) or any(
        not math.isfinite(value) for value in values
    ):
        if non_finite_policy is NonFiniteMetricInputPolicy.REJECT:
            raise ValueError("non-finite truth or prediction is rejected by the declared policy")
        return TargetMetrics(target, unit, _undefined(unit, count, "NON_FINITE_VALUE"))

    try:
        errors = tuple(predicted - actual for actual, predicted in zip(truth, values, strict=True))
        rmse = math.sqrt(math.fsum(error * error for error in errors) / count)
        mae = math.fsum(abs(error) for error in errors) / count
        mean = math.fsum(truth) / count
        sst = math.fsum((actual - mean) ** 2 for actual in truth)
        truth_sd = math.sqrt(sst / count)
        sse = math.fsum(error * error for error in errors)
        r2 = None if sst == 0.0 else 1.0 - sse / sst
        sre = None if truth_sd == 0.0 else rmse / truth_sd
        calculated = (rmse, mae, truth_sd, sse, r2, sre)
        if any(value is not None and not math.isfinite(value) for value in calculated):
            raise OverflowError
    except (OverflowError, ValueError) as error:
        if non_finite_policy is NonFiniteMetricInputPolicy.REJECT:
            raise ValueError("metric calculation produced a non-finite value") from error
        return TargetMetrics(target, unit, _undefined(unit, count, "NON_FINITE_METRIC"))
    results = (
        MetricResult(MetricName.RMSE, rmse, unit, MetricStatus.COMPUTED, None, count),
        MetricResult(MetricName.MAE, mae, unit, MetricStatus.COMPUTED, None, count),
        MetricResult(
            MetricName.R2,
            r2,
            "1",
            MetricStatus.UNDEFINED if r2 is None else MetricStatus.COMPUTED,
            "CONSTANT_TRUTH" if r2 is None else None,
            count,
        ),
        MetricResult(
            MetricName.SRE,
            sre,
            "1",
            MetricStatus.UNDEFINED if sre is None else MetricStatus.COMPUTED,
            "ZERO_TRUTH_POPULATION_SD" if sre is None else None,
            count,
        ),
    )
    return TargetMetrics(target, unit, results)
