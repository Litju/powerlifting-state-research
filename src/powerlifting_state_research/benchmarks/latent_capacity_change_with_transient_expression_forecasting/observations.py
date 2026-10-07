"""Noisy test, prescribed-load, and velocity observations of expressed performance."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

ORIGIN_DAY = 224
HISTORY_OBSERVATION_DAYS = tuple(range(6, ORIGIN_DAY, 7))
ASSESSMENT_CV = {"squat": 0.05, "bench_press": 0.04, "deadlift": 0.05}
VELOCITY_SD_MPS = {"squat": 0.04, "bench_press": 0.03, "deadlift": 0.05}
VELOCITY_CONSTANTS = {
    "squat": (0.25, 0.60, 1.0),
    "bench_press": (0.18, 0.74, 1.0),
    "deadlift": (0.20, 0.60, 1.0),
}
LOAD_FRACTION_RANGE = (0.68, 0.71)
RELATIVE_LOAD_DOMAIN = (0.40, 1.00)


@dataclass(frozen=True, slots=True)
class PerformanceObservation:
    day: int
    assessment_kg: float
    prescribed_load_kg: float
    velocity_mps: float


def sample_performance_observation(
    day: int, expressed_performance_kg: float, lift: str, rng: random.Random
) -> PerformanceObservation:
    if lift not in ASSESSMENT_CV:
        raise ValueError(f"unknown lift: {lift}")
    if day < 0 or expressed_performance_kg <= 0 or not math.isfinite(expressed_performance_kg):
        raise ValueError("observation day and expressed performance are invalid")

    assessment = expressed_performance_kg * (1.0 + rng.gauss(0.0, ASSESSMENT_CV[lift]))
    if assessment <= 0 or not math.isfinite(assessment):
        raise ValueError("assessment noise produced a non-positive result")
    fraction = LOAD_FRACTION_RANGE[0] + rng.random() * (
        LOAD_FRACTION_RANGE[1] - LOAD_FRACTION_RANGE[0]
    )
    prescribed_load = fraction * assessment
    relative_load = prescribed_load / expressed_performance_kg
    if not RELATIVE_LOAD_DOMAIN[0] <= relative_load <= RELATIVE_LOAD_DOMAIN[1]:
        raise ValueError("sampled relative load is outside the observation model domain")
    endpoint, span, exponent = VELOCITY_CONSTANTS[lift]
    expected_velocity = (
        endpoint
        + span
        * (
            (RELATIVE_LOAD_DOMAIN[1] - relative_load)
            / (RELATIVE_LOAD_DOMAIN[1] - RELATIVE_LOAD_DOMAIN[0])
        )
        ** exponent
    )
    velocity = expected_velocity + rng.gauss(0.0, VELOCITY_SD_MPS[lift])
    if not math.isfinite(velocity):
        raise ValueError("velocity observation must be finite")
    return PerformanceObservation(day, assessment, prescribed_load, velocity)


def sample_performance_history(
    expressed_performance_by_day: tuple[float, ...], lift: str, rng: random.Random
) -> tuple[PerformanceObservation, ...]:
    if len(expressed_performance_by_day) <= HISTORY_OBSERVATION_DAYS[-1]:
        raise ValueError("trajectory does not cover the complete observation history")
    return tuple(
        sample_performance_observation(day, expressed_performance_by_day[day], lift, rng)
        for day in HISTORY_OBSERVATION_DAYS
    )
