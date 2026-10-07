"""Synthetic population from independent normalized behavior coordinates."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from .dynamics import LiftParameters, WorldParameters

LIFTS = ("squat", "bench_press", "deadlift")
COORDINATE_COUNT = 16
COORDINATE_ORDER = (
    "baseline_scale",
    "bench_baseline_ratio",
    "deadlift_baseline_ratio",
    "squat_adaptation_utilization",
    "squat_adaptation_retention_28d",
    "squat_suppression_utilization",
    "squat_suppression_retention",
    "bench_adaptation_utilization",
    "bench_adaptation_retention_28d",
    "bench_suppression_utilization",
    "bench_suppression_retention",
    "deadlift_adaptation_utilization",
    "deadlift_adaptation_retention_28d",
    "deadlift_suppression_utilization",
    "deadlift_suppression_retention",
    "reference_stimulus",
)
REFERENCE_DOSE_PRODUCT = 0.6
BASELINE_SCALE_KG_RANGE = (120.0, 360.0)
BENCH_RATIO_RANGE = (0.5, 0.9)
DEADLIFT_RATIO_RANGE = (1.0, 1.4)
REFERENCE_STIMULUS_RANGE = (0.12, 0.85)
ADAPTATION_UTILIZATION_RANGE = (0.04, 0.18)
ADAPTATION_RETENTION_28D_RANGE = (0.15, 0.90)
SUPPRESSION_UTILIZATION_RANGE = (0.01, 0.07)
SUPPRESSION_RETENTION_RANGE = (0.30, 0.95)


@dataclass(frozen=True, slots=True)
class AthleteProfile:
    entity_id: str
    parameters: WorldParameters


def parameters_from_coordinates(coordinates: Sequence[float]) -> WorldParameters:
    """Map normalized coordinates in ``COORDINATE_ORDER`` to lift parameters."""
    if len(coordinates) != COORDINATE_COUNT or any(
        not math.isfinite(value) or not 0 <= value <= 1 for value in coordinates
    ):
        raise ValueError("population requires 16 finite coordinates in [0, 1]")
    index = iter(coordinates)
    scale_z = next(index)
    bench_ratio_z = next(index)
    deadlift_ratio_z = next(index)
    baseline_scale = math.exp(
        math.log(BASELINE_SCALE_KG_RANGE[0])
        + scale_z * (math.log(BASELINE_SCALE_KG_RANGE[1]) - math.log(BASELINE_SCALE_KG_RANGE[0]))
    )
    bench_ratio = _linear(*BENCH_RATIO_RANGE, bench_ratio_z)
    deadlift_ratio = _linear(*DEADLIFT_RATIO_RANGE, deadlift_ratio_z)

    per_lift_coordinates: dict[str, tuple[float, float, float, float]] = {
        lift: (next(index), next(index), next(index), next(index)) for lift in LIFTS
    }
    reference_stimulus = _linear(*REFERENCE_STIMULUS_RANGE, next(index))
    baseline_by_lift = {
        "squat": baseline_scale,
        "bench_press": baseline_scale * bench_ratio,
        "deadlift": baseline_scale * deadlift_ratio,
    }
    parameters: dict[str, LiftParameters] = {}
    for lift, (
        adaptation_z,
        retention_z,
        suppression_z,
        recovery_z,
    ) in per_lift_coordinates.items():
        adaptation_utilization = _linear(*ADAPTATION_UTILIZATION_RANGE, adaptation_z)
        adaptation_retention_28d = _linear(*ADAPTATION_RETENTION_28D_RANGE, retention_z)
        suppression_utilization = _linear(*SUPPRESSION_UTILIZATION_RANGE, suppression_z)
        suppression_retention = _linear(*SUPPRESSION_RETENTION_RANGE, recovery_z)
        parameters[lift] = LiftParameters(
            baseline_kg=baseline_by_lift[lift],
            adaptation_gain=adaptation_utilization / reference_stimulus,
            adaptation_time_days=-28.0 / math.log(1.0 - adaptation_retention_28d),
            suppression_gain=suppression_utilization / reference_stimulus,
            suppression_time_days=-1.0 / math.log(suppression_retention),
        )
    return WorldParameters(reference_stimulus, REFERENCE_DOSE_PRODUCT, parameters)


def sample_athlete(index: int, rng: random.Random) -> AthleteProfile:
    if index < 0:
        raise ValueError("population index cannot be negative")
    return AthleteProfile(
        f"entity-{index:06d}",
        parameters_from_coordinates(tuple(rng.random() for _ in range(COORDINATE_COUNT))),
    )


def _linear(lower: float, upper: float, coordinate: float) -> float:
    return lower + coordinate * (upper - lower)
