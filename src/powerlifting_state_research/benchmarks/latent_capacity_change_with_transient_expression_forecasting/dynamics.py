"""Lift-isolated capacity, adaptation, and transient-expression mechanics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingSession:
    day: int
    dose: float
    intensity: float

    def __post_init__(self) -> None:
        if self.day < 0 or not math.isfinite(self.dose) or self.dose < 0:
            raise ValueError("training day and dose must be non-negative and finite")
        if not math.isfinite(self.intensity) or self.intensity < 0:
            raise ValueError("training intensity must be non-negative and finite")


@dataclass(frozen=True, slots=True)
class LiftParameters:
    baseline_kg: float
    adaptation_gain: float
    adaptation_time_days: float
    suppression_gain: float
    suppression_time_days: float

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                self.baseline_kg,
                self.adaptation_gain,
                self.adaptation_time_days,
                self.suppression_gain,
                self.suppression_time_days,
            )
        ):
            raise ValueError("lift parameters must be finite and positive")


@dataclass(frozen=True, slots=True)
class WorldParameters:
    reference_stimulus: float
    reference_dose_product: float
    lifts: dict[str, LiftParameters]

    def __post_init__(self) -> None:
        if not 0 < self.reference_stimulus < 1:
            raise ValueError("reference stimulus must be between zero and one")
        if self.reference_dose_product <= 0 or not math.isfinite(self.reference_dose_product):
            raise ValueError("reference dose product must be finite and positive")
        if set(self.lifts) != {"squat", "bench_press", "deadlift"}:
            raise ValueError("world parameters must contain squat, bench press, and deadlift")

    @property
    def stimulus_reference(self) -> float:
        return (
            self.reference_dose_product * (1.0 - self.reference_stimulus) / self.reference_stimulus
        )


@dataclass(frozen=True, slots=True)
class LiftTrajectory:
    stimulus: tuple[float, ...]
    chronic_adaptation: tuple[float, ...]
    latent_capacity_kg: tuple[float, ...]
    transient_suppression: tuple[float, ...]
    expressed_performance_kg: tuple[float, ...]


def bounded_training_stimulus(dose: float, intensity: float, stimulus_reference: float) -> float:
    """Convert a non-negative dose/intensity product into a value in [0, 1)."""
    if not all(math.isfinite(value) for value in (dose, intensity, stimulus_reference)):
        raise ValueError("dose, intensity, and stimulus reference must be finite")
    if dose < 0 or intensity < 0 or stimulus_reference <= 0:
        raise ValueError("dose and intensity must be non-negative; reference must be positive")
    product = dose * intensity
    if not math.isfinite(product):
        raise ValueError("dose/intensity product must be finite")
    return product / (product + stimulus_reference)


def simulate_lift(
    parameters: LiftParameters,
    sessions_by_day: Mapping[int, TrainingSession],
    stimulus_reference: float,
    last_day: int = 279,
) -> LiftTrajectory:
    """Evolve one lift; no state or input from another lift is accepted."""
    if last_day < 0:
        raise ValueError("last day must be non-negative")
    if any(day != session.day or day > last_day for day, session in sessions_by_day.items()):
        raise ValueError("training sessions must match their day keys and fit the horizon")

    alpha_adaptation = math.exp(-1.0 / parameters.adaptation_time_days)
    alpha_suppression = math.exp(-1.0 / parameters.suppression_time_days)
    adaptation = 0.0
    suppression = 0.0
    stimuli: list[float] = []
    adaptation_values: list[float] = []
    capacity_values: list[float] = []
    suppression_values: list[float] = []
    expression_values: list[float] = []

    for day in range(last_day + 1):
        session = sessions_by_day.get(day)
        stimulus = bounded_training_stimulus(
            0.0 if session is None else session.dose,
            0.0 if session is None else session.intensity,
            stimulus_reference,
        )
        adaptation = alpha_adaptation * adaptation + (1.0 - alpha_adaptation) * stimulus
        capacity = parameters.baseline_kg * (1.0 + parameters.adaptation_gain * adaptation)
        suppression = alpha_suppression * suppression + (1.0 - alpha_suppression) * stimulus
        expressed = capacity * (1.0 - parameters.suppression_gain * suppression)
        if not all(
            math.isfinite(value) for value in (adaptation, capacity, suppression, expressed)
        ):
            raise ValueError(f"non-finite state for day {day}")
        if not 0 <= adaptation <= 1 or not 0 <= suppression <= 1:
            raise ValueError(f"adaptation or suppression outside [0, 1] on day {day}")
        if capacity <= 0 or expressed <= 0:
            raise ValueError(f"capacity and expressed performance must be positive on day {day}")
        stimuli.append(stimulus)
        adaptation_values.append(adaptation)
        capacity_values.append(capacity)
        suppression_values.append(suppression)
        expression_values.append(expressed)

    return LiftTrajectory(
        tuple(stimuli),
        tuple(adaptation_values),
        tuple(capacity_values),
        tuple(suppression_values),
        tuple(expression_values),
    )


def latent_capacity_change(trajectory: LiftTrajectory, origin_day: int, horizon_days: int) -> float:
    """Return C(origin + horizon - 1) - C(origin - 1), independent of expression."""
    if origin_day < 1 or horizon_days < 1:
        raise ValueError("origin and horizon must be positive")
    end_day = origin_day + horizon_days - 1
    if end_day >= len(trajectory.latent_capacity_kg):
        raise ValueError("target endpoint is outside the simulated trajectory")
    return trajectory.latent_capacity_kg[end_day] - trajectory.latent_capacity_kg[origin_day - 1]
