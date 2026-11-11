"""Cohort generation for the observable-assessment task.

Mirrors ``dataset.iter_public_rows`` (same random streams, same history law) and additionally
produces the future noisy assessment Y with a separate RNG stream. Models only ever receive the
``inputs`` fields of a cohort; ``truth`` stays sealed until scoring.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import numpy.typing as npt
import torch

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset,
    interventions,
    observations,
    population,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (
    LiftTrajectory,
    simulate_lift,
)
from ..models import temporal_expert as te
from ..probabilistic import reference as ref
from . import contract as C

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
Transform = Callable[[Sequence[float]], tuple[float, ...]]
BATCH = 256


def identity_transform(coordinates: Sequence[float]) -> tuple[float, ...]:
    return tuple(coordinates)


def adaptation_shift_transform(coordinates: Sequence[float]) -> tuple[float, ...]:
    """u -> sqrt(u) on the three adaptation-retention coordinates; all others unchanged."""
    values = list(coordinates)
    for index in C.SHIFTED_COORDINATES:
        values[index] = math.sqrt(values[index])
    return tuple(values)


def stratum_of(plan_id: str, horizon: int) -> int:
    return C.PLANS.index(plan_id) * len(C.HORIZONS) + C.HORIZONS.index(horizon)


@dataclass(frozen=True)
class ObsTruth:
    """Sealed hidden quantities: Y is the target; E and C are audit-only and never model inputs."""

    y: FloatArray  # (n,3) observed assessment on the assessment day
    e: FloatArray  # (n,3) expressed performance on the assessment day
    c: FloatArray  # (n,3) latent capacity on the assessment day
    last_e: FloatArray  # (n,3) expressed performance on day 223
    last_c: FloatArray  # (n,3) latent capacity on day 223


class Sealed:
    def __init__(self, truth: ObsTruth) -> None:
        self._truth = truth
        self.opened = False

    def open(self) -> ObsTruth:
        self.opened = True
        return self._truth


@dataclass(frozen=True)
class ObsCohort:
    role: str
    scenario: str
    row_ids: tuple[str, ...]
    stratum: IntArray
    raw_history: FloatArray  # (n,3,32,10)
    plan_numeric: FloatArray  # (n,6)
    base_features: FloatArray  # (n,127)
    truth: Sealed

    @property
    def n(self) -> int:
        return len(self.row_ids)

    @property
    def plan(self) -> IntArray:
        return self.stratum // len(C.HORIZONS)

    @property
    def last_assessment(self) -> FloatArray:
        """Latest admissible assessment (day 223) per lift: the persistence forecast."""
        out: FloatArray = self.raw_history[:, :, -1, 0]
        return out


@dataclass(frozen=True)
class RawRow:
    split: str
    row_id: str
    inputs: dataset.ForecastInputs
    stratum: int
    y: tuple[float, float, float]
    e: tuple[float, float, float]
    c: tuple[float, float, float]
    last_e: tuple[float, float, float]
    last_c: tuple[float, float, float]


def generation_config(spec_rows: int, base: int) -> dataset.GenerationConfig:
    return dataset.GenerationConfig(
        train_rows=spec_rows,
        validation_rows=len(C.PLANS) * len(C.HORIZONS),
        population_seed=base,
        intervention_seed=base + 1,
        observation_seed=base + 2,
        split_seed=base + 3,
        serialization_seed=base + 4,
    )


def iter_raw_rows(
    config: dataset.GenerationConfig, future_seed: int, transform: Transform = identity_transform
) -> Iterator[RawRow]:
    """Same streams as ``iter_public_rows``; ``transform`` changes only population coordinates."""
    records = dataset._row_records(config)
    population_rng = random.Random(config.population_seed)
    observation_rng = random.Random(config.observation_seed)
    future_rng = random.Random(future_seed)
    for split, index, plan_id, horizon, templates in records:
        coordinates = tuple(population_rng.random() for _ in range(population.COORDINATE_COUNT))
        parameters = population.parameters_from_coordinates(transform(coordinates))
        plan = interventions.declared_plan(plan_id)
        sessions = {
            lift: interventions.training_sessions(templates[i], plan)
            for i, lift in enumerate(C.LIFTS)
        }
        trajectories: dict[str, LiftTrajectory] = {
            lift: simulate_lift(
                parameters.lifts[lift],
                sessions[lift],
                parameters.stimulus_reference,
                interventions.PLAN_END_DAY,
            )
            for lift in C.LIFTS
        }
        lifts: dict[str, dataset.LiftInputs] = {}
        for i, lift in enumerate(C.LIFTS):
            history = observations.sample_performance_history(
                trajectories[lift].expressed_performance_kg, lift, observation_rng
            )
            lifts[lift] = dataset.LiftInputs(history, interventions.history_segments(templates[i]))
        entity = f"entity-{index:06d}"
        inputs = dataset.ForecastInputs(
            entity,
            interventions.ORIGIN_DAY,
            horizon,
            plan,
            lifts,  # type: ignore[arg-type]
        )
        day = C.ASSESSMENT_DAYS[horizon]
        if day != interventions.ORIGIN_DAY + horizon - 1:
            raise ValueError("assessment day does not equal origin + horizon - 1")
        y = tuple(
            observations.sample_performance_observation(
                day, trajectories[lift].expressed_performance_kg[day], lift, future_rng
            ).assessment_kg
            for lift in C.LIFTS
        )
        yield RawRow(
            split,
            entity,
            inputs,
            stratum_of(plan_id, horizon),
            y,  # type: ignore[arg-type]
            tuple(trajectories[lift].expressed_performance_kg[day] for lift in C.LIFTS),  # type: ignore[arg-type]
            tuple(trajectories[lift].latent_capacity_kg[day] for lift in C.LIFTS),  # type: ignore[arg-type]
            tuple(
                trajectories[lift].expressed_performance_kg[C.HISTORY_LAST_DAY] for lift in C.LIFTS
            ),  # type: ignore[arg-type]
            tuple(trajectories[lift].latent_capacity_kg[C.HISTORY_LAST_DAY] for lift in C.LIFTS),  # type: ignore[arg-type]
        )


def add_velocity_noise(
    inputs: dataset.ForecastInputs, rng: random.Random
) -> dataset.ForecastInputs:
    """Shift A: independent extra Normal(0, lift velocity SD) on history velocity only."""
    lifts: dict[str, dataset.LiftInputs] = {}
    for lift in C.LIFTS:
        source = inputs.lifts[lift]  # type: ignore[literal-required]
        sd = observations.VELOCITY_SD_MPS[lift]
        history = tuple(
            replace(item, velocity_mps=item.velocity_mps + rng.gauss(0.0, sd))
            for item in source.history
        )
        lifts[lift] = dataset.LiftInputs(history, source.history_schedule)
    return replace(inputs, lifts=lifts)  # type: ignore[arg-type]


def _assemble(
    role: str, scenario: str, rows: list[RawRow], inputs: list[dataset.ForecastInputs]
) -> ObsCohort:
    ids = [f"{role}-{r.row_id}" for r in rows]
    histories: list[FloatArray] = []
    numerics: list[FloatArray] = []
    features: list[FloatArray] = []
    for start in range(0, len(rows), BATCH):
        chunk = [
            te.TemporalModelInput.from_forecast_inputs(ids[i], inputs[i])
            for i in range(start, min(start + BATCH, len(rows)))
        ]
        history = torch.stack([te._raw_history(item) for item in chunk]).numpy()
        numeric = np.asarray([te._plan_numeric(item) for item in chunk], dtype=np.float64)
        plan = np.asarray(
            [C.PLANS.index(item.declared_future_plan.plan_id) for item in chunk], dtype=np.int64
        )
        features.append(ref.visible_features(history, numeric, plan))
        histories.append(history)
        numerics.append(numeric)
    stratum = np.asarray([r.stratum for r in rows], dtype=np.int64)
    truth = ObsTruth(
        np.asarray([r.y for r in rows]),
        np.asarray([r.e for r in rows]),
        np.asarray([r.c for r in rows]),
        np.asarray([r.last_e for r in rows]),
        np.asarray([r.last_c for r in rows]),
    )
    return ObsCohort(
        role,
        scenario,
        tuple(ids),
        stratum,
        np.concatenate(histories),
        np.vstack(numerics),
        np.vstack(features),
        Sealed(truth),
    )


def build_cohorts(
    role: str,
    rows_n: int,
    base: int,
    scenarios: Sequence[str] = ("CONTROL",),
) -> dict[str, ObsCohort]:
    """Build the requested scenarios of one role; scenarios of a role are entity-paired."""
    seeds = C.role_seeds(base)
    config = generation_config(rows_n, base)
    out: dict[str, ObsCohort] = {}
    if "CONTROL" in scenarios or "VELOCITY_NOISE_SHIFT" in scenarios:
        everything = list(iter_raw_rows(config, seeds["future_assessment"]))
        kept = [r for r in everything if r.split == "train"]
        _check_cohort(role, kept, rows_n)
        if "CONTROL" in scenarios:
            out["CONTROL"] = _assemble(role, "CONTROL", kept, [r.inputs for r in kept])
        if "VELOCITY_NOISE_SHIFT" in scenarios:
            # noise is drawn for every generated record (including discarded validation records)
            # so the stream is consumed identically regardless of the split assignment
            rng = random.Random(seeds["velocity_shift_noise"])
            shifted = [add_velocity_noise(r.inputs, rng) for r in everything]
            pairs = [(r, s) for r, s in zip(everything, shifted, strict=True) if r.split == "train"]
            out["VELOCITY_NOISE_SHIFT"] = _assemble(
                role, "VELOCITY_NOISE_SHIFT", [p[0] for p in pairs], [p[1] for p in pairs]
            )
    if "ADAPTATION_TIMESCALE_SHIFT" in scenarios:
        moved = [
            r
            for r in iter_raw_rows(config, seeds["future_assessment"], adaptation_shift_transform)
            if r.split == "train"
        ]
        _check_cohort(role, moved, rows_n)
        out["ADAPTATION_TIMESCALE_SHIFT"] = _assemble(
            role, "ADAPTATION_TIMESCALE_SHIFT", moved, [r.inputs for r in moved]
        )
    return out


def _check_cohort(role: str, rows: list[RawRow], rows_n: int) -> None:
    if len(rows) != rows_n or len({r.row_id for r in rows}) != rows_n:
        raise ValueError(f"{role} cohort has the wrong size or duplicate ids")
    counts = np.bincount([r.stratum for r in rows], minlength=12)
    if (counts != rows_n // 12).any():
        raise ValueError(f"{role} cohort is not balanced across plan/horizon strata")


def describe(cohort: ObsCohort) -> dict[str, Any]:
    return {"role": cohort.role, "scenario": cohort.scenario, "rows": cohort.n}
