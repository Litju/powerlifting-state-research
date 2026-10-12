"""Independent public-native structural reconstruction study for RES-289."""

# ruff: noqa: E501
# Generated scientific prose keeps complete sentences together.

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import quad
from scipy.optimize import least_squares, minimize
from scipy.signal import lfilter
from scipy.special import betaln

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (
    LiftTrajectory,
    TrainingSession,
    simulate_lift,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.interventions import (
    HISTORY_TEMPLATES,
    PLAN_IDS,
    declared_plan,
    history_segments,
    training_sessions,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.observations import (
    ASSESSMENT_CV,
    LOAD_FRACTION_RANGE,
    RELATIVE_LOAD_DOMAIN,
    VELOCITY_CONSTANTS,
    VELOCITY_SD_MPS,
    PerformanceObservation,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (
    LIFTS,
    parameters_from_coordinates,
)
from ..contracts.serialization import canonical_json_bytes, sha256_record
from .target_sufficient_structural_reconstruction_protocol import (
    BOOTSTRAP_REPLICATES,
    DEVELOPMENT_COUNT,
    ENTITY_COUNT,
    EQUIVALENCE_COORDINATE_DISTANCE,
    EQUIVALENCE_HISTORY_RMSE_KG,
    EQUIVALENCE_OBJECTIVE_TOLERANCE,
    EVALUATION_ID,
    JACOBIAN_RANK_TOLERANCE,
    JACOBIAN_STEPS,
    LAPLACE_BOUND_MARGIN,
    LAPLACE_MAX_CONDITION,
    LIKELIHOOD_SUPPORT_PENALTY,
    NOISE_FREE_MAX_EVALUATIONS,
    NOISE_SCALES,
    OPTIMIZER_MAX_FUNCTION_CALLS,
    OPTIMIZER_MAX_ITERATIONS,
    POSTERIOR_DRAWS,
    PROTOCOL_DIGEST,
    REJECTION_ATTEMPTS,
    RESIDUAL_ALPHA,
    RESIDUAL_BOUND_KG,
    SEEDS,
    STARTING_MAIN,
    STUDY_ID,
)

HOME = Path("results/studies/target_sufficient_structural_reconstruction")
DESIGN = Path("studies/target_sufficient_structural_reconstruction")
OBSERVATION_DAYS = tuple(range(6, 224, 7))
HISTORY_DAY_COUNT = 224
LAST_DAY = 279
COORDINATE_NAMES = (
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
ESTIMATOR_IDS = {
    "reduced": "reduced_latest_assessment_p223_v1",
    "full": "full_bounded_native_mle_v1",
    "bayesian": "bayesian_native_laplace_v1",
    "hybrid": "full_plus_development_ridge_residual_v1",
}
TARGET_NAMES = ("P_223_kg", "C_223_kg", "DeltaC_56_kg", "A_223", "R_223")
SOURCE_PATHS = (
    Path("pyproject.toml"),
    Path("uv.lock"),
    DESIGN / "README.md",
    DESIGN / "protocol.json",
    DESIGN / "formal-specification.md",
    DESIGN / "historical-lineage.md",
    DESIGN / "frozen-evidence.json",
    Path("results/studies/target_sufficient_structural_reconstruction/README.md"),
    Path("studies/observation_inversion/formal-specification.md"),
    Path("studies/observation_inversion/historical-lineage.md"),
    Path("studies/observation_inversion/protocol.json"),
    Path("src/powerlifting_state_research/studies/registry.py"),
    Path("src/powerlifting_state_research/provenance/historical_sources.py"),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/spec.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py"
    ),
    Path(
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/evaluate.py"
    ),
    Path("docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md"),
    Path("docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md"),
    Path("docs/benchmarks/iid-latent-capacity-change-public-native-evaluation.md"),
    Path(
        "artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md"
    ),
    Path("artifacts/model-cards/historical-model-evidence-lineage.md"),
    Path("artifacts/model-cards/public-native-comparator-suite.md"),
    Path("artifacts/training-protocols/public-native-comparator-suite.json"),
    Path("src/powerlifting_state_research/models/comparators.py"),
    Path("src/powerlifting_state_research/models/training.py"),
    Path("results/tables/public-native-comparator-frontier.csv"),
    Path("results/manifests/public-native-comparator-suite.json"),
    Path("results/audits/res281-analysis/res281-validity-analysis.md"),
    Path("results/audits/res284-publication/methods-limitations.md"),
    Path("results/audits/res284-publication/tables/scientific-limitations.csv"),
    Path("artifacts/registries/benchmark-registry.json"),
    Path(
        "src/powerlifting_state_research/studies/target_sufficient_structural_reconstruction_protocol.py"
    ),
    Path("src/powerlifting_state_research/studies/target_sufficient_structural_reconstruction.py"),
)
Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class StudyInputs:
    """Participant-visible inputs passed to every estimator; no truth fields."""

    entity_id: str
    entity_index: int
    template_indices: tuple[int, int, int]
    plan_id: str
    schedule_products: Array
    assessments: Array
    noise_scale: float


@dataclass(frozen=True, slots=True)
class ModelOutput:
    history_performance: Array
    history_jacobian: Array
    p223: Array
    c223: Array
    a223: Array
    r223: Array
    delta_c56: Array


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(json_bytes(row) for row in rows)


def csv_bytes(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def verify_design(root: Path) -> None:
    record = json.loads((root / DESIGN / "protocol.json").read_bytes())
    if record["study_id"] != STUDY_ID or record["protocol_digest"] != PROTOCOL_DIGEST:
        raise ValueError("frozen RES-289 study identity drift")
    if record["starting_main"] != STARTING_MAIN:
        raise ValueError("RES-289 starting main drift")
    if sha256_record(record["protocol"]) != PROTOCOL_DIGEST:
        raise ValueError("frozen RES-289 protocol payload drift")
    protocol = record["protocol"]
    if (
        protocol["realization"]["population"]
        != "64 public-native entities drawn from the M2 IID coordinate transform."
    ):
        raise ValueError("frozen entity-count contract drift")
    if ENTITY_COUNT != 64 or DEVELOPMENT_COUNT != 32 or len(OBSERVATION_DAYS) != 32:
        raise ValueError("implementation does not match the frozen realization dimensions")
    if tuple(protocol["realization"]["noise_scales"]) != NOISE_SCALES:
        raise ValueError("frozen observation-noise conditions drift")
    if "upper bound nextafter(1,0)" not in protocol["optimization"]["noisy_solver"]:
        raise ValueError("frozen optimizer does not match the public half-open coordinate domain")
    if protocol["identities"]["study_evaluation_id"] != EVALUATION_ID:
        raise ValueError("frozen study evaluation identity drift")
    for name, expected in SEEDS.items():
        if protocol["seeds"][name] != expected:
            raise ValueError(f"frozen {name} seed drift")
    if protocol["uncertainty"]["paired_bootstrap"].split(" ", 1)[0] != str(BOOTSTRAP_REPLICATES):
        raise ValueError("frozen bootstrap budget drift")

    freeze = json.loads((root / DESIGN / "frozen-evidence.json").read_bytes())
    m0_m5_path = root / freeze["m0_m5_manifest"]
    if digest(m0_m5_path.read_bytes()) != freeze["m0_m5_manifest_sha256"]:
        raise ValueError("frozen M0-M5 evidence manifest changed")
    m0_m5 = json.loads(m0_m5_path.read_bytes())
    for path, expected in m0_m5.items():
        if digest((root / path).read_bytes()) != expected:
            raise ValueError(f"frozen M0-M5 evidence changed: {path}")
    for path, expected in freeze["res287_frozen_files"].items():
        if digest((root / path).read_bytes()) != expected:
            raise ValueError(f"frozen RES-287 evidence changed: {path}")


def schedule_products(template_indices: tuple[int, int, int], plan_id: str) -> Array:
    """Expand public M3 schedule declarations to daily dose-intensity products."""
    plan = declared_plan(plan_id)
    products = np.zeros((len(LIFTS), LAST_DAY + 1), dtype=np.float64)
    for index, template in enumerate(template_indices):
        sessions = training_sessions(template, plan)
        products[index] = [
            sessions[day].dose * sessions[day].intensity for day in range(LAST_DAY + 1)
        ]
    return products


def _history_template_indices(entity_index: int) -> tuple[int, int, int]:
    local = entity_index % DEVELOPMENT_COUNT
    return tuple((local // 4 + lift_index) % len(HISTORY_TEMPLATES) for lift_index in range(3))  # type: ignore[return-value]


def _plan_id(entity_index: int) -> str:
    return PLAN_IDS[(entity_index % DEVELOPMENT_COUNT) % len(PLAN_IDS)]


def _split_label(entity_index: int) -> str:
    return "development" if entity_index < DEVELOPMENT_COUNT else "test"


def _expected_velocity(performance_kg: float, load_kg: float, lift: str) -> float:
    endpoint, span, _ = VELOCITY_CONSTANTS[lift]
    relative_load = load_kg / performance_kg
    return endpoint + span * (1.0 - relative_load) / 0.6


def _sample_observation(
    day: int,
    performance_kg: float,
    lift: str,
    noise_scale: float,
    rng: random.Random,
) -> PerformanceObservation:
    if noise_scale == 0:
        assessment = performance_kg
        fraction = LOAD_FRACTION_RANGE[0] + rng.random() * (
            LOAD_FRACTION_RANGE[1] - LOAD_FRACTION_RANGE[0]
        )
        load = fraction * assessment
        return PerformanceObservation(
            day, assessment, load, _expected_velocity(performance_kg, load, lift)
        )
    for _ in range(REJECTION_ATTEMPTS):
        assessment = performance_kg * (1.0 + rng.gauss(0.0, ASSESSMENT_CV[lift] * noise_scale))
        if assessment <= 0 or not math.isfinite(assessment):
            continue
        fraction = LOAD_FRACTION_RANGE[0] + rng.random() * (
            LOAD_FRACTION_RANGE[1] - LOAD_FRACTION_RANGE[0]
        )
        load = fraction * assessment
        relative_load = load / performance_kg
        if not RELATIVE_LOAD_DOMAIN[0] <= relative_load <= RELATIVE_LOAD_DOMAIN[1]:
            continue
        velocity = _expected_velocity(performance_kg, load, lift) + rng.gauss(
            0.0, VELOCITY_SD_MPS[lift] * noise_scale
        )
        if math.isfinite(velocity):
            return PerformanceObservation(day, assessment, load, velocity)
    raise ValueError(f"observation rejection limit exceeded for {lift} at day {day}")


def generate_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate separate public participant inputs and hidden evaluation truth."""
    population_rng = random.Random(SEEDS["population"])
    observation_rng = random.Random(SEEDS["observation"])
    observation_rows: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    for entity_index in range(ENTITY_COUNT):
        true_coordinates = [population_rng.random() for _ in range(16)]
        world = parameters_from_coordinates(true_coordinates)
        entity_id = f"entity-{entity_index:06d}"

        templates = _history_template_indices(entity_index)
        plan_id = _plan_id(entity_index)
        trajectories: dict[str, LiftTrajectory] = {}
        for lift_index, lift in enumerate(LIFTS):
            sessions = training_sessions(templates[lift_index], declared_plan(plan_id))
            trajectories[lift] = simulate_lift(
                world.lifts[lift], sessions, world.stimulus_reference, last_day=LAST_DAY
            )
        condition_records: dict[str, dict[str, list[dict[str, float | int]]]] = {}
        for noise_scale in NOISE_SCALES:
            per_lift: dict[str, list[dict[str, float | int]]] = {}
            for lift in LIFTS:
                trajectory = trajectories[lift]
                per_lift[lift] = [
                    {
                        "day": observation.day,
                        "assessment_kg": observation.assessment_kg,
                        "prescribed_load_kg": observation.prescribed_load_kg,
                        "velocity_mps": observation.velocity_mps,
                    }
                    for observation in (
                        _sample_observation(
                            day,
                            trajectory.expressed_performance_kg[day],
                            lift,
                            noise_scale,
                            observation_rng,
                        )
                        for day in OBSERVATION_DAYS
                    )
                ]
            condition_records[str(noise_scale)] = per_lift

        observation_rows.append(
            {
                "entity_id": entity_id,
                "entity_index": entity_index,
                "split": _split_label(entity_index),
                "history_template_by_lift": dict(zip(LIFTS, templates, strict=True)),
                "declared_plan": plan_id,
                "history_segments_by_lift": {
                    lift: [
                        {
                            "start_day": segment.start_day,
                            "end_day": segment.end_day,
                            "dose": segment.dose,
                            "intensity": segment.intensity,
                        }
                        for segment in history_segments(templates[lift_index])
                    ]
                    for lift_index, lift in enumerate(LIFTS)
                },
                "future_plan": {
                    "start_day": 224,
                    "end_day": 279,
                    "plan_id": plan_id,
                },
                "observations_by_noise_scale": condition_records,
            }
        )
        truth_lifts: dict[str, dict[str, float]] = {}
        for lift in LIFTS:
            trajectory = trajectories[lift]
            params = world.lifts[lift]
            truth_lifts[lift] = {
                "P_223_kg": trajectory.expressed_performance_kg[223],
                "C_223_kg": trajectory.latent_capacity_kg[223],
                "DeltaC_56_kg": trajectory.latent_capacity_kg[279]
                - trajectory.latent_capacity_kg[223],
                "A_223": trajectory.chronic_adaptation[223],
                "R_223": trajectory.transient_suppression[223],
                "baseline_kg": params.baseline_kg,
                "adaptation_gain": params.adaptation_gain,
                "adaptation_time_days": params.adaptation_time_days,
                "suppression_gain": params.suppression_gain,
                "suppression_time_days": params.suppression_time_days,
            }
        truth_rows.append(
            {
                "entity_id": entity_id,
                "entity_index": entity_index,
                "split": _split_label(entity_index),
                "population_coordinates": true_coordinates,
                "reference_stimulus": world.reference_stimulus,
                "reference_dose_product": world.reference_dose_product,
                "X_REF": world.stimulus_reference,
                "lifts": truth_lifts,
            }
        )
    return observation_rows, truth_rows


def model_with_jacobian(coordinates: Array, products: Array) -> ModelOutput:
    """Run the native zero-state model and its exact forward sensitivities."""
    q = np.asarray(coordinates, dtype=np.float64)
    if q.shape != (16,) or not np.all(np.isfinite(q)) or np.any(q < 0) or np.any(q >= 1):
        raise ValueError("full reconstruction requires 16 finite coordinates in [0,1)")
    if products.shape != (len(LIFTS), LAST_DAY + 1) or not np.all(np.isfinite(products)):
        raise ValueError("daily schedule products have the wrong shape or non-finite values")
    if np.any(products < 0):
        raise ValueError("daily schedule products must be non-negative")

    world = parameters_from_coordinates(q.tolist())
    reference_stimulus = world.reference_stimulus
    x_ref = world.stimulus_reference
    dx_ref = -0.6 * 0.73 / reference_stimulus**2
    baseline_scale = world.lifts["squat"].baseline_kg
    history_by_lift: list[Array] = []
    jacobian_by_lift: list[Array] = []
    p223_values = np.empty(3, dtype=np.float64)
    c223_values = np.empty(3, dtype=np.float64)
    a223_values = np.empty(3, dtype=np.float64)
    r223_values = np.empty(3, dtype=np.float64)
    delta_c_values = np.empty(3, dtype=np.float64)
    observation_indices = np.asarray(OBSERVATION_DAYS, dtype=np.int64)

    for lift_index, lift in enumerate(LIFTS):
        parameters = world.lifts[lift]
        baseline = parameters.baseline_kg
        d_baseline = np.zeros(16, dtype=np.float64)
        d_baseline[0] = baseline * math.log(3.0)
        if lift_index == 1:
            d_baseline[1] = baseline_scale * 0.4
        elif lift_index == 2:
            d_baseline[2] = baseline_scale * 0.4

        coordinate_index = 3 + lift_index * 4
        adaptation_utilization = 0.04 + 0.14 * q[coordinate_index]
        adaptation_retention = 0.15 + 0.75 * q[coordinate_index + 1]
        suppression_utilization = 0.01 + 0.06 * q[coordinate_index + 2]
        suppression_retention = 0.30 + 0.65 * q[coordinate_index + 3]
        d_adaptation_gain = np.zeros(16, dtype=np.float64)
        d_adaptation_gain[coordinate_index] = 0.14 / reference_stimulus
        d_adaptation_gain[15] = -adaptation_utilization * 0.73 / reference_stimulus**2
        d_suppression_gain = np.zeros(16, dtype=np.float64)
        d_suppression_gain[coordinate_index + 2] = 0.06 / reference_stimulus
        d_suppression_gain[15] = -suppression_utilization * 0.73 / reference_stimulus**2

        log_a = math.log1p(-adaptation_retention)
        d_tau_adaptation = -28.0 * 0.75 / ((1.0 - adaptation_retention) * log_a**2)
        log_r = math.log(suppression_retention)
        d_tau_suppression = 0.65 / (suppression_retention * log_r**2)
        alpha_adaptation = math.exp(-1.0 / parameters.adaptation_time_days)
        alpha_suppression = math.exp(-1.0 / parameters.suppression_time_days)
        d_alpha_adaptation = (
            alpha_adaptation / parameters.adaptation_time_days**2 * d_tau_adaptation
        )
        d_alpha_suppression = (
            alpha_suppression / parameters.suppression_time_days**2 * d_tau_suppression
        )

        daily_products = products[lift_index]
        stimulus = daily_products / (daily_products + x_ref)
        d_stimulus_reference = -daily_products / (daily_products + x_ref) ** 2 * dx_ref
        adaptation = lfilter([1.0 - alpha_adaptation], [1.0, -alpha_adaptation], stimulus)
        suppression = lfilter([1.0 - alpha_suppression], [1.0, -alpha_suppression], stimulus)
        previous_adaptation = np.concatenate(([0.0], adaptation[:-1]))
        previous_suppression = np.concatenate(([0.0], suppression[:-1]))
        d_adaptation = np.zeros((LAST_DAY + 1, 16), dtype=np.float64)
        d_suppression = np.zeros((LAST_DAY + 1, 16), dtype=np.float64)
        d_adaptation[:, 15] = lfilter(
            [1.0],
            [1.0, -alpha_adaptation],
            (1.0 - alpha_adaptation) * d_stimulus_reference,
        )
        d_adaptation[:, coordinate_index + 1] = lfilter(
            [1.0],
            [1.0, -alpha_adaptation],
            d_alpha_adaptation * (previous_adaptation - stimulus),
        )
        d_suppression[:, 15] = lfilter(
            [1.0],
            [1.0, -alpha_suppression],
            (1.0 - alpha_suppression) * d_stimulus_reference,
        )
        d_suppression[:, coordinate_index + 3] = lfilter(
            [1.0],
            [1.0, -alpha_suppression],
            d_alpha_suppression * (previous_suppression - stimulus),
        )

        capacity = baseline * (1.0 + parameters.adaptation_gain * adaptation)
        d_capacity = d_baseline[None, :] * (
            1.0 + parameters.adaptation_gain * adaptation[:, None]
        ) + baseline * (
            d_adaptation_gain[None, :] * adaptation[:, None]
            + parameters.adaptation_gain * d_adaptation
        )
        expression = 1.0 - parameters.suppression_gain * suppression
        d_expression = -(
            d_suppression_gain[None, :] * suppression[:, None]
            + parameters.suppression_gain * d_suppression
        )
        performance = capacity * expression
        d_performance = d_capacity * expression[:, None] + capacity[:, None] * d_expression
        history_by_lift.append(performance[observation_indices])
        jacobian_by_lift.append(d_performance[observation_indices])
        p223_values[lift_index] = performance[223]
        c223_values[lift_index] = capacity[223]
        a223_values[lift_index] = adaptation[223]
        r223_values[lift_index] = suppression[223]
        delta_c_values[lift_index] = capacity[LAST_DAY] - capacity[223]

    history = np.concatenate(history_by_lift)
    jacobian = np.concatenate(jacobian_by_lift, axis=0)
    if not np.all(np.isfinite(history)) or not np.all(np.isfinite(jacobian)):
        raise ValueError("model produced non-finite output or sensitivity")
    if np.any(p223_values <= 0) or np.any(c223_values <= 0):
        raise ValueError("model produced non-positive performance or capacity")
    return ModelOutput(
        history,
        jacobian,
        p223_values,
        c223_values,
        a223_values,
        r223_values,
        delta_c_values,
    )


def batch_targets(coordinates: Array, products: Array) -> dict[str, Array]:
    """Vectorized target calculation for reproducible Laplace posterior draws."""
    q = np.asarray(coordinates, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != 16 or not np.all(np.isfinite(q)):
        raise ValueError("posterior coordinates must have shape (draws, 16)")
    if np.any(q < 0) or np.any(q >= 1):
        raise ValueError("posterior coordinates must remain in [0,1)")
    if products.shape != (len(LIFTS), LAST_DAY + 1):
        raise ValueError("posterior schedule products have the wrong shape")

    baseline_scale = np.exp(math.log(120.0) + q[:, 0] * math.log(3.0))
    baselines = np.column_stack(
        (
            baseline_scale,
            baseline_scale * (0.5 + 0.4 * q[:, 1]),
            baseline_scale * (1.0 + 0.4 * q[:, 2]),
        )
    )
    reference_stimulus = 0.12 + 0.73 * q[:, 15]
    x_ref = 0.6 * (1.0 - reference_stimulus) / reference_stimulus
    adaptation_utilization = np.column_stack(
        (0.04 + 0.14 * q[:, 3], 0.04 + 0.14 * q[:, 7], 0.04 + 0.14 * q[:, 11])
    )
    adaptation_retention = np.column_stack(
        (0.15 + 0.75 * q[:, 4], 0.15 + 0.75 * q[:, 8], 0.15 + 0.75 * q[:, 12])
    )
    suppression_utilization = np.column_stack(
        (0.01 + 0.06 * q[:, 5], 0.01 + 0.06 * q[:, 9], 0.01 + 0.06 * q[:, 13])
    )
    suppression_retention = np.column_stack(
        (0.30 + 0.65 * q[:, 6], 0.30 + 0.65 * q[:, 10], 0.30 + 0.65 * q[:, 14])
    )
    adaptation_gain = adaptation_utilization / reference_stimulus[:, None]
    suppression_gain = suppression_utilization / reference_stimulus[:, None]
    adaptation_tau = -28.0 / np.log1p(-adaptation_retention)
    suppression_tau = -1.0 / np.log(suppression_retention)
    alpha_adaptation = np.exp(-1.0 / adaptation_tau)
    alpha_suppression = np.exp(-1.0 / suppression_tau)

    adaptation = np.zeros((len(q), len(LIFTS)), dtype=np.float64)
    suppression = np.zeros_like(adaptation)
    c223 = np.zeros_like(adaptation)
    p223 = np.zeros_like(adaptation)
    a223 = np.zeros_like(adaptation)
    r223 = np.zeros_like(adaptation)
    for day in range(LAST_DAY + 1):
        stimulus = products[:, day][None, :] / (products[:, day][None, :] + x_ref[:, None])
        adaptation = alpha_adaptation * adaptation + (1.0 - alpha_adaptation) * stimulus
        suppression = alpha_suppression * suppression + (1.0 - alpha_suppression) * stimulus
        capacity = baselines * (1.0 + adaptation_gain * adaptation)
        performance = capacity * (1.0 - suppression_gain * suppression)
        if day == 223:
            c223 = capacity.copy()
            p223 = performance.copy()
            a223 = adaptation.copy()
            r223 = suppression.copy()
    return {
        "p223": p223,
        "c223": c223,
        "a223": a223,
        "r223": r223,
        "delta_c56": capacity - c223,
    }


def _accepted_fraction_weight(z: float) -> float:
    if z <= 0 or not math.isfinite(z):
        return 0.0
    lower = max(LOAD_FRACTION_RANGE[0], RELATIVE_LOAD_DOMAIN[0] / z)
    upper = min(LOAD_FRACTION_RANGE[1], RELATIVE_LOAD_DOMAIN[1] / z)
    return max(0.0, upper - lower) / (LOAD_FRACTION_RANGE[1] - LOAD_FRACTION_RANGE[0])


def _accepted_fraction_weight_derivative(z: float) -> float:
    if z <= 0 or not math.isfinite(z):
        return 0.0
    fraction_low, fraction_high = LOAD_FRACTION_RANGE
    relative_low, relative_high = RELATIVE_LOAD_DOMAIN
    upper_inverse = relative_high / z
    lower_inverse = relative_low / z
    upper_derivative = 0.0 if fraction_high <= upper_inverse else -relative_high / z**2
    lower_derivative = 0.0 if fraction_low >= lower_inverse else -relative_low / z**2
    if _accepted_fraction_weight(z) == 0:
        return 0.0
    return (upper_derivative - lower_derivative) / (fraction_high - fraction_low)


@lru_cache(maxsize=16)
def _acceptance_probability(relative_noise_sd: float) -> float:
    """Native observation acceptance mass after integrating the sampled load fraction."""
    if relative_noise_sd <= 0:
        raise ValueError("noise-free observations have a degenerate likelihood")

    def integrand(z: float) -> float:
        standardized = (z - 1.0) / relative_noise_sd
        density = math.exp(-0.5 * standardized**2) / (relative_noise_sd * math.sqrt(2.0 * math.pi))
        return density * _accepted_fraction_weight(z)

    value, _ = quad(integrand, 0.0, 3.0, epsabs=1e-12, epsrel=1e-12)
    if not 0 < value <= 1:
        raise ValueError("assessment/load acceptance probability is invalid")
    return value


def assessment_nll_and_gradient(
    coordinates: Array,
    inputs: StudyInputs,
    *,
    include_constants: bool = False,
    support_penalty_counter: list[int] | None = None,
) -> tuple[float, Array]:
    """Exact assessment marginal likelihood under native load-domain rejection."""
    if inputs.noise_scale <= 0:
        raise ValueError("noise-free observations have a degenerate likelihood")
    output = model_with_jacobian(coordinates, inputs.schedule_products)
    assessments = inputs.assessments.reshape(-1)
    predictions = output.history_performance
    if assessments.shape != predictions.shape or np.any(assessments <= 0):
        raise ValueError("assessment inputs are malformed")

    total_nll = 0.0
    gradient = np.zeros(16, dtype=np.float64)
    row_index = 0
    support_violations = 0
    support_penalty = LIKELIHOOD_SUPPORT_PENALTY
    minimum_z = RELATIVE_LOAD_DOMAIN[0] / LOAD_FRACTION_RANGE[1]
    maximum_z = RELATIVE_LOAD_DOMAIN[1] / LOAD_FRACTION_RANGE[0]
    for lift in LIFTS:
        sigma = ASSESSMENT_CV[lift] * inputs.noise_scale
        for _day in OBSERVATION_DAYS:
            prediction = predictions[row_index]
            observed = assessments[row_index]
            z = observed / prediction
            weight = _accepted_fraction_weight(z)
            if weight <= 0:
                support_violations += 1
                if z <= minimum_z:
                    distance = minimum_z - z
                    derivative_wrt_prediction = 2.0 * support_penalty * distance * z / prediction
                else:
                    distance = z - maximum_z
                    derivative_wrt_prediction = -2.0 * support_penalty * distance * z / prediction
                total_nll += support_penalty * (1.0 + distance**2)
                gradient += derivative_wrt_prediction * output.history_jacobian[row_index]
                row_index += 1
                continue
            residual = z - 1.0
            contribution = math.log(prediction) + 0.5 * (residual / sigma) ** 2 - math.log(weight)
            derivative_wrt_prediction = (
                1.0 / prediction
                - z * residual / (prediction * sigma**2)
                + z / prediction * _accepted_fraction_weight_derivative(z) / weight
            )
            total_nll += contribution
            gradient += derivative_wrt_prediction * output.history_jacobian[row_index]
            if include_constants:
                total_nll += (
                    math.log(sigma)
                    + 0.5 * math.log(2.0 * math.pi)
                    + math.log(_acceptance_probability(sigma))
                )
            row_index += 1
    if support_penalty_counter is not None:
        support_penalty_counter.append(support_violations)
    if not math.isfinite(total_nll) or not np.all(np.isfinite(gradient)):
        raise ValueError("assessment likelihood produced a non-finite value")
    return total_nll, gradient


@dataclass(frozen=True, slots=True)
class FitResult:
    coordinates: Array | None
    output: ModelOutput | None
    objective: float | None
    status: str
    starts: tuple[dict[str, Any], ...]
    function_evaluations: int
    gradient_evaluations: int
    model_evaluations: int
    support_penalty_evaluations: int


def _fit_starts(entity_index: int, noise_scale: float) -> tuple[Array, ...]:
    rng = random.Random(SEEDS["optimizer_starts"] + entity_index * 10 + int(noise_scale))
    return (
        np.full(16, 0.25, dtype=np.float64),
        np.full(16, 0.50, dtype=np.float64),
        np.full(16, 0.75, dtype=np.float64),
        np.asarray([rng.uniform(0.1, 0.9) for _ in range(16)], dtype=np.float64),
    )


def _prior_nll_gradient(coordinates: Array, prior: str | None) -> tuple[float, Array]:
    gradient = np.zeros(16, dtype=np.float64)
    if prior in (None, "uniform"):
        return 0.0, gradient
    if prior != "beta8":
        raise ValueError(f"unknown coordinate prior: {prior}")
    safe = np.clip(coordinates, 1e-12, 1.0 - 1e-12)
    log_density = 7.0 * np.log(safe) + 7.0 * np.log1p(-safe) - betaln(8.0, 8.0)
    gradient = -7.0 / safe + 7.0 / (1.0 - safe)
    return float(-np.sum(log_density)), gradient


def fit_coordinates(inputs: StudyInputs, prior: str | None = None) -> FitResult:
    """Fit all 16 population coordinates; retain every bounded solver start."""
    starts = _fit_starts(inputs.entity_index, inputs.noise_scale)
    candidate_records: list[dict[str, Any]] = []
    eligible: list[tuple[float, Array, ModelOutput, bool]] = []
    support_penalty_evaluations = 0
    total_function_evaluations = 0
    total_gradient_evaluations = 0
    total_model_evaluations = 0

    for start_index, start in enumerate(starts):
        coordinate_upper_bound = float(np.nextafter(1.0, 0.0))
        if inputs.noise_scale == 0:
            cached_key: bytes | None = None
            cached_output: ModelOutput | None = None
            model_evaluation_count = 0

            def output_at(coordinates: Array) -> ModelOutput:
                nonlocal cached_key, cached_output, model_evaluation_count
                key = np.ascontiguousarray(coordinates, dtype=np.float64).tobytes()
                if key != cached_key:
                    cached_output = model_with_jacobian(coordinates, inputs.schedule_products)
                    cached_key = key
                    model_evaluation_count += 1
                if cached_output is None:
                    raise AssertionError("least-squares cache failed to populate")
                return cached_output

            def residual(coordinates: Array) -> Array:
                return output_at(coordinates).history_performance - inputs.assessments.reshape(-1)

            def residual_jacobian(coordinates: Array) -> Array:
                return output_at(coordinates).history_jacobian

            least_squares_result = least_squares(
                residual,
                start,
                jac=residual_jacobian,
                bounds=(np.zeros(16), np.full(16, coordinate_upper_bound)),
                max_nfev=NOISE_FREE_MAX_EVALUATIONS,
                ftol=1e-11,
                xtol=1e-11,
                gtol=1e-11,
            )
            coordinates = np.asarray(least_squares_result.x, dtype=np.float64)
            output = output_at(coordinates)
            objective = float(0.5 * np.dot(residual(coordinates), residual(coordinates)))
            final_support_violations = 0
            gradient_norm = float(least_squares_result.optimality)
            nfev = int(least_squares_result.nfev)
            njev = int(least_squares_result.njev or 0)
            model_evaluations = model_evaluation_count
            message = str(least_squares_result.message)
            solver_status = int(least_squares_result.status)
            success = bool(least_squares_result.success)
        else:
            penalty_counts: list[int] = []

            def objective_and_gradient(
                coordinates: Array, counts: list[int] = penalty_counts
            ) -> tuple[float, Array]:
                nonlocal support_penalty_evaluations
                support_count: list[int] = []
                value, gradient = assessment_nll_and_gradient(
                    coordinates, inputs, support_penalty_counter=support_count
                )
                counts.append(support_count[-1])
                support_penalty_evaluations += support_count[-1]
                prior_value, prior_gradient = _prior_nll_gradient(coordinates, prior)
                return value + prior_value, gradient + prior_gradient

            minimize_result = minimize(
                objective_and_gradient,
                start,
                method="L-BFGS-B",
                jac=True,
                bounds=[(0.0, coordinate_upper_bound)] * 16,
                options={
                    "maxiter": OPTIMIZER_MAX_ITERATIONS,
                    "maxfun": OPTIMIZER_MAX_FUNCTION_CALLS,
                    "ftol": 1e-10,
                    "gtol": 1e-6,
                },
            )
            coordinates = np.asarray(minimize_result.x, dtype=np.float64)
            output = model_with_jacobian(coordinates, inputs.schedule_products)
            exact_value, exact_gradient = assessment_nll_and_gradient(coordinates, inputs)
            prior_value, prior_gradient = _prior_nll_gradient(coordinates, prior)
            objective = float(exact_value + prior_value)
            final_counter: list[int] = []
            assessment_nll_and_gradient(coordinates, inputs, support_penalty_counter=final_counter)
            final_support_violations = final_counter[-1]
            gradient_norm = float(np.linalg.norm(exact_gradient + prior_gradient, ord=np.inf))
            nfev = int(minimize_result.nfev)
            njev = int(minimize_result.njev or 0)
            model_evaluations = nfev + 3
            message = str(minimize_result.message)
            solver_status = int(minimize_result.status)
            success = bool(minimize_result.success)

        total_function_evaluations += nfev
        total_gradient_evaluations += njev
        total_model_evaluations += model_evaluations
        finite = math.isfinite(objective) and np.all(np.isfinite(coordinates))
        feasible = final_support_violations == 0
        eligible_start = bool(finite and feasible)
        candidate_status = (
            "CONVERGED"
            if success and eligible_start
            else "NONCONVERGED_FEASIBLE"
            if eligible_start
            else "INFEASIBLE_FINAL"
        )
        candidate_records.append(
            {
                "start_index": start_index,
                "start_coordinates": start.tolist(),
                "coordinates": coordinates.tolist(),
                "objective": objective if finite else None,
                "converged": success,
                "eligible_final": eligible_start,
                "status": candidate_status,
                "solver_status": solver_status,
                "message": message,
                "function_evaluations": nfev,
                "gradient_evaluations": njev,
                "model_evaluations": model_evaluations,
                "gradient_infinity_norm": gradient_norm if math.isfinite(gradient_norm) else None,
                "support_penalty_rows_seen": sum(penalty_counts) if inputs.noise_scale > 0 else 0,
                "final_support_violations": final_support_violations,
            }
        )
        if eligible_start:
            eligible.append((objective, coordinates, output, success))

    converged = [item for item in eligible if item[3]]
    selected = min(converged or eligible, key=lambda item: item[0]) if eligible else None
    if selected is None:
        return FitResult(
            None,
            None,
            None,
            "OPTIMIZATION_FAILED",
            tuple(candidate_records),
            total_function_evaluations,
            total_gradient_evaluations,
            total_model_evaluations,
            support_penalty_evaluations,
        )
    objective, coordinates, output, success = selected
    return FitResult(
        coordinates.copy(),
        output,
        objective,
        "CONVERGED" if success else "NONCONVERGED_BEST_RETAINED",
        tuple(candidate_records),
        total_function_evaluations,
        total_gradient_evaluations,
        total_model_evaluations,
        support_penalty_evaluations,
    )


def _laplace_posterior(inputs: StudyInputs, map_fit: FitResult, prior: str) -> dict[str, Any]:
    if inputs.noise_scale == 0:
        return {
            "status": "NOT_DEFINED_NOISE_FREE_POSTERIOR",
            "hessian_gradient_evaluations": 0,
        }
    if map_fit.coordinates is None or map_fit.output is None:
        return {"status": "MAP_OPTIMIZATION_FAILED", "hessian_gradient_evaluations": 0}
    mode = map_fit.coordinates
    distance_to_bound = np.minimum(mode, 1.0 - mode)
    if np.any(distance_to_bound < LAPLACE_BOUND_MARGIN):
        return {
            "status": "POSTERIOR_BOUNDARY_MODE",
            "boundary_distance_min": float(np.min(distance_to_bound)),
            "hessian_gradient_evaluations": 0,
        }

    hessian = np.empty((16, 16), dtype=np.float64)
    step = 1e-4
    for coordinate_index in range(16):
        plus = mode.copy()
        minus = mode.copy()
        plus[coordinate_index] += step
        minus[coordinate_index] -= step
        _, likelihood_gradient_plus = assessment_nll_and_gradient(plus, inputs)
        _, likelihood_gradient_minus = assessment_nll_and_gradient(minus, inputs)
        _, prior_gradient_plus = _prior_nll_gradient(plus, prior)
        _, prior_gradient_minus = _prior_nll_gradient(minus, prior)
        hessian[:, coordinate_index] = (
            likelihood_gradient_plus
            + prior_gradient_plus
            - likelihood_gradient_minus
            - prior_gradient_minus
        ) / (2.0 * step)
    hessian = 0.5 * (hessian + hessian.T)
    hessian_gradient_evaluations = 32
    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    if not np.all(np.isfinite(eigenvalues)) or eigenvalues[0] <= 0:
        return {
            "status": "POSTERIOR_NON_POSITIVE_HESSIAN",
            "minimum_hessian_eigenvalue": float(eigenvalues[0]),
            "maximum_hessian_eigenvalue": float(eigenvalues[-1]),
            "hessian_gradient_evaluations": hessian_gradient_evaluations,
        }
    condition = float(eigenvalues[-1] / eigenvalues[0])
    if not math.isfinite(condition) or condition > LAPLACE_MAX_CONDITION:
        return {
            "status": "POSTERIOR_ILL_CONDITIONED",
            "minimum_hessian_eigenvalue": float(eigenvalues[0]),
            "maximum_hessian_eigenvalue": float(eigenvalues[-1]),
            "hessian_condition_number": condition,
            "hessian_gradient_evaluations": hessian_gradient_evaluations,
        }
    covariance = (eigenvectors / eigenvalues) @ eigenvectors.T
    rng_seed = (
        SEEDS["posterior_draws"]
        + inputs.entity_index * 100
        + int(inputs.noise_scale) * 10
        + (0 if prior == "uniform" else 1)
    )
    rng = np.random.default_rng(rng_seed)
    accepted: list[Array] = []
    attempted = 0
    while sum(len(batch) for batch in accepted) < POSTERIOR_DRAWS and attempted < 20:
        attempted += 1
        candidates = rng.multivariate_normal(mode, covariance, size=POSTERIOR_DRAWS)
        valid = candidates[np.all((candidates >= 0.0) & (candidates < 1.0), axis=1)]
        if valid.size:
            accepted.append(valid)
    samples = np.concatenate(accepted, axis=0)[:POSTERIOR_DRAWS] if accepted else np.empty((0, 16))
    if len(samples) != POSTERIOR_DRAWS:
        return {
            "status": "POSTERIOR_SUPPORT_FAILURE",
            "accepted_draws": int(len(samples)),
            "candidate_batches": attempted,
            "hessian_gradient_evaluations": hessian_gradient_evaluations,
        }
    targets = batch_targets(samples, inputs.schedule_products)
    physical = _batch_physical_parameters(samples)
    physical_units = {
        "reference_stimulus": "dimensionless",
        "X_REF": "dose-intensity product",
    }
    for lift in LIFTS:
        physical_units.update(
            {
                f"{lift}.baseline_kg": "kg",
                f"{lift}.adaptation_gain": "dimensionless",
                f"{lift}.adaptation_time_days": "days",
                f"{lift}.suppression_gain": "dimensionless",
                f"{lift}.suppression_time_days": "days",
            }
        )
    return {
        "status": "LAPLACE_APPROXIMATION_VALID",
        "mode_coordinates": mode.tolist(),
        "hessian_min_eigenvalue": float(eigenvalues[0]),
        "hessian_max_eigenvalue": float(eigenvalues[-1]),
        "hessian_condition_number": condition,
        "candidate_batches": attempted,
        "accepted_draws": len(samples),
        "hessian_gradient_evaluations": hessian_gradient_evaluations,
        "coordinates": _interval_records(samples, COORDINATE_NAMES, "dimensionless"),
        "physical_parameters": [
            {
                "name": name,
                "unit": physical_units[name],
                **_interval_values(values, physical_units[name]),
            }
            for name, values in physical.items()
        ],
        "targets": {
            "P_223_kg": _interval_values(targets["p223"], "kg"),
            "C_223_kg": _interval_values(targets["c223"], "kg"),
            "DeltaC_56_kg": _interval_values(targets["delta_c56"], "kg"),
            "A_223": _interval_values(targets["a223"], "dimensionless"),
            "R_223": _interval_values(targets["r223"], "dimensionless"),
        },
    }


def _interval_values(samples: Array, unit: str) -> dict[str, Any]:
    return {
        "mean": np.mean(samples, axis=0).tolist(),
        "lower_95": np.quantile(samples, 0.025, axis=0).tolist(),
        "upper_95": np.quantile(samples, 0.975, axis=0).tolist(),
        "unit": unit,
    }


def _interval_records(samples: Array, names: Sequence[str], unit: str) -> list[dict[str, Any]]:
    interval = _interval_values(samples, unit)
    return [
        {
            "name": name,
            "mean": interval["mean"][index],
            "lower_95": interval["lower_95"][index],
            "upper_95": interval["upper_95"][index],
            "unit": unit,
        }
        for index, name in enumerate(names)
    ]


def study_inputs_from_row(row: Mapping[str, Any], noise_scale: float) -> StudyInputs:
    """Validate and expose only M3 schedules plus the declared assessment channel."""
    if noise_scale not in NOISE_SCALES:
        raise ValueError("undeclared observation-noise condition")
    if any(key in row for key in ("truth", "targets", "population_coordinates", "latent_states")):
        raise ValueError("participant input row contains hidden truth")
    entity_index = int(row["entity_index"])
    templates_by_lift = row["history_template_by_lift"]
    templates: tuple[int, int, int] = (
        int(templates_by_lift[LIFTS[0]]),
        int(templates_by_lift[LIFTS[1]]),
        int(templates_by_lift[LIFTS[2]]),
    )
    if any(template < 0 or template >= len(HISTORY_TEMPLATES) for template in templates):
        raise ValueError("unknown native history template")
    plan_id = str(row["declared_plan"])
    if plan_id not in PLAN_IDS:
        raise ValueError("unknown native future plan")
    raw_condition = row["observations_by_noise_scale"][str(noise_scale)]
    assessments = np.empty((len(LIFTS), len(OBSERVATION_DAYS)), dtype=np.float64)
    for lift_index, lift in enumerate(LIFTS):
        records = raw_condition[lift]
        if len(records) != len(OBSERVATION_DAYS):
            raise ValueError("participant history has the wrong observation count")
        for observation_index, (record, expected_day) in enumerate(
            zip(records, OBSERVATION_DAYS, strict=True)
        ):
            if int(record["day"]) != expected_day:
                raise ValueError("participant observations are out of order or outside cutoff")
            assessment = float(record["assessment_kg"])
            load = float(record["prescribed_load_kg"])
            velocity = float(record["velocity_mps"])
            fraction = load / assessment
            if (
                assessment <= 0
                or not math.isfinite(assessment)
                or not math.isfinite(load)
                or not math.isfinite(velocity)
                or not LOAD_FRACTION_RANGE[0] <= fraction < LOAD_FRACTION_RANGE[1]
            ):
                raise ValueError("participant observation violates the M2 channel contract")
            assessments[lift_index, observation_index] = assessment
    return StudyInputs(
        str(row["entity_id"]),
        entity_index,
        templates,
        plan_id,
        schedule_products(templates, plan_id),
        assessments,
        noise_scale,
    )


def _physical_parameters(
    coordinates: Array,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    world = parameters_from_coordinates(coordinates.tolist())
    global_parameters = {
        "reference_stimulus": world.reference_stimulus,
        "X_REF": world.stimulus_reference,
    }
    per_lift = {
        lift: {
            "baseline_kg": params.baseline_kg,
            "adaptation_gain": params.adaptation_gain,
            "adaptation_time_days": params.adaptation_time_days,
            "suppression_gain": params.suppression_gain,
            "suppression_time_days": params.suppression_time_days,
        }
        for lift, params in world.lifts.items()
    }
    return global_parameters, per_lift


def _batch_physical_parameters(coordinates: Array) -> dict[str, Array]:
    q = np.asarray(coordinates, dtype=np.float64)
    baseline_scale = np.exp(math.log(120.0) + q[:, 0] * math.log(3.0))
    baselines = np.column_stack(
        (
            baseline_scale,
            baseline_scale * (0.5 + 0.4 * q[:, 1]),
            baseline_scale * (1.0 + 0.4 * q[:, 2]),
        )
    )
    reference_stimulus = 0.12 + 0.73 * q[:, 15]
    output: dict[str, Array] = {
        "reference_stimulus": reference_stimulus,
        "X_REF": 0.6 * (1.0 - reference_stimulus) / reference_stimulus,
    }
    for lift_index, lift in enumerate(LIFTS):
        base = 3 + 4 * lift_index
        adaptation_utilization = 0.04 + 0.14 * q[:, base]
        adaptation_retention = 0.15 + 0.75 * q[:, base + 1]
        suppression_utilization = 0.01 + 0.06 * q[:, base + 2]
        suppression_retention = 0.30 + 0.65 * q[:, base + 3]
        output[f"{lift}.baseline_kg"] = baselines[:, lift_index]
        output[f"{lift}.adaptation_gain"] = adaptation_utilization / reference_stimulus
        output[f"{lift}.adaptation_time_days"] = -28.0 / np.log1p(-adaptation_retention)
        output[f"{lift}.suppression_gain"] = suppression_utilization / reference_stimulus
        output[f"{lift}.suppression_time_days"] = -1.0 / np.log(suppression_retention)
    return output


def _estimate_targets(output: ModelOutput, lift_index: int) -> dict[str, float]:
    return {
        "P_223_kg": float(output.p223[lift_index]),
        "C_223_kg": float(output.c223[lift_index]),
        "DeltaC_56_kg": float(output.delta_c56[lift_index]),
        "A_223": float(output.a223[lift_index]),
        "R_223": float(output.r223[lift_index]),
    }


def _target_units() -> dict[str, str]:
    return {
        "P_223_kg": "kg",
        "C_223_kg": "kg",
        "DeltaC_56_kg": "kg",
        "A_223": "dimensionless",
        "R_223": "dimensionless",
    }


def _truth_parameters(truth_row: Mapping[str, Any], lift: str) -> dict[str, float]:
    per_lift = dict(truth_row["lifts"][lift])
    per_lift["reference_stimulus"] = float(truth_row["reference_stimulus"])
    per_lift["X_REF"] = float(truth_row["X_REF"])
    return per_lift


def _finite_difference_jacobian(coordinates: Array, products: Array, step: float) -> Array:
    columns: list[Array] = []
    for index in range(16):
        plus = coordinates.copy()
        minus = coordinates.copy()
        plus[index] += step
        minus[index] -= step
        upper = model_with_jacobian(plus, products).history_performance
        lower = model_with_jacobian(minus, products).history_performance
        columns.append((upper - lower) / (2.0 * step))
    return np.column_stack(columns)


def _rank_record(jacobian: Array) -> dict[str, Any]:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.sum(singular_values / singular_values[0] > JACOBIAN_RANK_TOLERANCE))
    condition = (
        float(singular_values[0] / singular_values[rank - 1]) if rank == jacobian.shape[1] else None
    )
    return {
        "rank": rank,
        "parameter_count": int(jacobian.shape[1]),
        "relative_rank_tolerance": JACOBIAN_RANK_TOLERANCE,
        "singular_values": singular_values.tolist(),
        "condition_number_full_rank_only": condition,
    }


def _constant_input_equivalence() -> dict[str, Any]:
    first = np.full(16, 0.5, dtype=np.float64)
    second = first.copy()
    first[15] = 0.2
    second[15] = 0.8
    sessions = {day: TrainingSession(day, dose=0.8, intensity=0.75) for day in range(LAST_DAY + 1)}
    first_world = parameters_from_coordinates(first.tolist())
    second_world = parameters_from_coordinates(second.tolist())
    first_trajectories = {
        lift: simulate_lift(
            first_world.lifts[lift], sessions, first_world.stimulus_reference, LAST_DAY
        )
        for lift in LIFTS
    }
    second_trajectories = {
        lift: simulate_lift(
            second_world.lifts[lift], sessions, second_world.stimulus_reference, LAST_DAY
        )
        for lift in LIFTS
    }
    differences = {
        key: max(
            abs(a - b)
            for lift in LIFTS
            for a, b in zip(
                getattr(first_trajectories[lift], key),
                getattr(second_trajectories[lift], key),
                strict=True,
            )
        )
        for key in (
            "chronic_adaptation",
            "latent_capacity_kg",
            "transient_suppression",
            "expressed_performance_kg",
        )
    }
    return {
        "design": "constant continue input, dose-intensity product 0.6; outside canonical history templates",
        "reference_coordinate_pair": [0.2, 0.8],
        "reference_stimulus_pair": [
            first_world.reference_stimulus,
            second_world.reference_stimulus,
        ],
        "X_REF_pair": [first_world.stimulus_reference, second_world.stimulus_reference],
        "hidden_state_max_absolute_differences": differences,
        "maximum_performance_difference_kg": differences["expressed_performance_kg"],
        "equivalence_status": "EXACT_COUNTEREXAMPLE_OUTSIDE_CANONICAL_TEMPLATES",
    }


def identifiability_diagnostics() -> dict[str, Any]:
    """Evaluate the frozen local-sensitivity designs without claiming global uniqueness."""
    midpoint = np.full(16, 0.5, dtype=np.float64)
    by_design: list[dict[str, Any]] = []
    central_jacobians: dict[str, Array] = {}
    for template in range(len(HISTORY_TEMPLATES)):
        template_products = schedule_products((template, template, template), "continue")
        by_step: list[dict[str, Any]] = []
        for step in JACOBIAN_STEPS:
            jacobian = _finite_difference_jacobian(midpoint, template_products, step)
            by_step.append({"central_step": step, **_rank_record(jacobian)})
            if step == JACOBIAN_STEPS[-1]:
                central_jacobians[f"template-{template}"] = jacobian
        spectrum_difference = np.asarray(
            by_step[0]["singular_values"], dtype=np.float64
        ) - np.asarray(by_step[1]["singular_values"], dtype=np.float64)
        spectrum_norm = float(
            np.linalg.norm(np.asarray(by_step[1]["singular_values"], dtype=np.float64))
        )
        relative_refinement = float(np.linalg.norm(spectrum_difference)) / max(spectrum_norm, 1e-15)
        products_seen = sorted(
            {round(segment.dose * segment.intensity, 12) for segment in history_segments(template)}
        )
        by_design.append(
            {
                "design": f"canonical-template-{template}",
                "schedule_excitation_products": products_seen,
                "distinct_history_products": len(products_seen),
                "steps": by_step,
                "relative_singular_spectrum_refinement": relative_refinement,
            }
        )

    no_input = np.zeros((len(LIFTS), LAST_DAY + 1), dtype=np.float64)
    no_input_jacobian = _finite_difference_jacobian(midpoint, no_input, JACOBIAN_STEPS[-1])
    by_design.append(
        {
            "design": "zero-input-low-excitation-sensitivity",
            "schedule_excitation_products": [0.0],
            "distinct_history_products": 1,
            "steps": [
                {
                    "central_step": JACOBIAN_STEPS[-1],
                    **_rank_record(no_input_jacobian),
                }
            ],
            "support_classification": "outside canonical history templates",
        }
    )
    if len(central_jacobians) == 4:
        # The native templates are compared at one fixed midpoint; no outcome threshold is selected.
        native_rank_records = [_rank_record(central_jacobians[f"template-{i}"]) for i in range(4)]
    else:
        native_rank_records = []
    constant_input = _constant_input_equivalence()
    return {
        "study_id": STUDY_ID,
        "protocol_digest": PROTOCOL_DIGEST,
        "estimand": "local sensitivity of the 96 weekly expressed-performance outputs to 16 normalized coordinates",
        "initial_state": "native A[-1]=R[-1]=0",
        "normalized_coordinate_count": 16,
        "observation_rows": 96,
        "jacobian_methods": by_design,
        "canonical_template_rank_summary": native_rank_records,
        "single_time_latent_rank": {
            "maximum_rank": 1,
            "latent_coordinate_count": 2,
            "reason": "all assessment, load, and velocity channels factor through P at one time",
        },
        "constant_input_equivalence": constant_input,
        "native_template_global_identification": "INCONCLUSIVE",
        "free_initial_state_transfer": "PROHIBITED; RES-287 free-state result is a separate extension",
    }


def _residual_features(inputs: StudyInputs, output: ModelOutput) -> Array:
    plan = declared_plan(inputs.plan_id)
    exposure = plan.dose * plan.intensity
    recent_x = np.arange(4, dtype=np.float64)
    centered_x = recent_x - np.mean(recent_x)
    slope_denominator = float(np.dot(centered_x, centered_x))
    rows: list[list[float]] = []
    for lift_index in range(len(LIFTS)):
        recent = inputs.assessments[lift_index, -4:]
        slope = float(np.dot(centered_x, recent - np.mean(recent)) / slope_denominator)
        reduced_gap = float(inputs.assessments[lift_index, -1] - output.p223[lift_index])
        rows.append(
            [
                float(output.delta_c56[lift_index]),
                reduced_gap,
                slope,
                exposure,
            ]
        )
    return np.asarray(rows, dtype=np.float64)


def fit_residual_model(
    development_features: Array,
    development_residuals: Array,
    development_entity_ids: Sequence[str],
) -> dict[str, Any]:
    """Fit only the fixed alpha Ridge residual map on development rows."""
    features = np.asarray(development_features, dtype=np.float64)
    residuals = np.asarray(development_residuals, dtype=np.float64)
    if (
        features.ndim != 2
        or features.shape[1] != 4
        or residuals.shape != (len(features),)
        or len(development_entity_ids) * len(LIFTS) != len(features)
        or not np.all(np.isfinite(features))
        or not np.all(np.isfinite(residuals))
    ):
        raise ValueError("residual development data are malformed or incomplete")
    if len(set(development_entity_ids)) != len(development_entity_ids):
        raise ValueError("residual training entity identities must be unique")
    means = np.mean(features, axis=0)
    scales = np.std(features, axis=0)
    scales[scales < 1e-12] = 1.0
    design = np.column_stack((np.ones(len(features)), (features - means) / scales))
    penalty = np.eye(design.shape[1], dtype=np.float64) * RESIDUAL_ALPHA
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ residuals)
    return {
        "status": "FIT_ON_DEVELOPMENT_ONLY",
        "feature_names": [
            "full_deltaC56_kg",
            "assessment_minus_full_P223_kg",
            "recent_assessment_slope_kg_per_week",
            "declared_plan_dose_intensity",
        ],
        "alpha": RESIDUAL_ALPHA,
        "correction_bound_kg": RESIDUAL_BOUND_KG,
        "development_entity_ids": sorted(set(development_entity_ids)),
        "development_entity_ids_sha256": sha256_record(sorted(set(development_entity_ids))),
        "development_feature_rows": int(len(features)),
        "feature_means": means.tolist(),
        "feature_scales": scales.tolist(),
        "coefficients": coefficients.tolist(),
    }


def predict_residual(model: Mapping[str, Any], features: Array) -> Array:
    if model.get("status") != "FIT_ON_DEVELOPMENT_ONLY":
        raise ValueError("residual model is not fitted")
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 4:
        raise ValueError("residual prediction features have the wrong shape")
    means = np.asarray(model["feature_means"], dtype=np.float64)
    scales = np.asarray(model["feature_scales"], dtype=np.float64)
    coefficients = np.asarray(model["coefficients"], dtype=np.float64)
    design = np.column_stack((np.ones(len(x)), (x - means) / scales))
    return np.clip(design @ coefficients, -RESIDUAL_BOUND_KG, RESIDUAL_BOUND_KG)


def _source_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in SOURCE_PATHS:
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"RES-289 source evidence is missing: {relative_path}")
        hashes[str(relative_path)] = digest(path.read_bytes())
    return hashes


def _seed_for_key(key: object) -> int:
    raw = canonical_json_bytes(key)
    return SEEDS["bootstrap"] + int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _rmse_interval(errors: Sequence[float], seed: int) -> tuple[float | None, float | None]:
    if not errors:
        return None, None
    rng = random.Random(seed)
    samples = np.asarray(errors, dtype=np.float64)
    replicates = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for replicate in range(BOOTSTRAP_REPLICATES):
        selected = [samples[rng.randrange(len(samples))] for _ in range(len(samples))]
        replicates[replicate] = math.sqrt(float(np.mean(np.square(selected))))
    lower, upper = np.quantile(replicates, [0.025, 0.975])
    return float(lower), float(upper)


def _mean_interval(values: Sequence[float], seed: int) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(seed)
    samples = np.asarray(values, dtype=np.float64)
    replicates = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for replicate in range(BOOTSTRAP_REPLICATES):
        selected = [samples[rng.randrange(len(samples))] for _ in range(len(samples))]
        replicates[replicate] = float(np.mean(selected))
    lower, upper = np.quantile(replicates, [0.025, 0.975])
    return float(lower), float(upper)


def _target_metric_rows(
    estimate_rows: Sequence[Mapping[str, Any]], binding: Mapping[str, str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, float, str, str], list[Mapping[str, Any]]] = {}
    for row in estimate_rows:
        key = (
            str(row["estimator_id"]),
            str(row["prior"]),
            float(row["noise_scale"]),
            str(row["target"]),
            str(row["lift"]),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        estimator_id, prior, noise_scale, target, lift = key
        scored = [row for row in rows if row["estimate"] is not None and row["truth"] is not None]
        errors = [float(row["estimate"]) - float(row["truth"]) for row in scored]
        rmse = math.sqrt(float(np.mean(np.square(errors)))) if errors else None
        mae = float(np.mean(np.abs(errors))) if errors else None
        bias = float(np.mean(errors)) if errors else None
        lower, upper = _rmse_interval(errors, _seed_for_key(key))
        status_counts: dict[str, int] = {}
        for row in rows:
            status = str(row["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        if not rows:
            status = "NO_ROWS"
        elif len(scored) == len(rows):
            fit_statuses = {str(row["status"]) for row in scored}
            if any("NONCONVERGED" in fit_status for fit_status in fit_statuses):
                status = "COMPLETE_WITH_NONCONVERGED_FITS_RETAINED"
            elif any(fit_status.startswith("MAP_ONLY") for fit_status in fit_statuses):
                status = "COMPLETE_MAP_ONLY_POSTERIOR_FAILURE_RETAINED"
            else:
                status = "COMPLETE"
        elif scored:
            status = "PARTIAL_FAILURES_RETAINED"
        elif len({str(row["status"]) for row in rows}) == 1:
            status = str(rows[0]["status"])
        else:
            status = "NO_VALID_ESTIMATES"
        unit = str(rows[0]["unit"]) if rows else _target_units().get(target, "dimensionless")
        output.append(
            {
                **binding,
                "estimator_id": estimator_id,
                "prior": prior,
                "noise_scale": noise_scale,
                "target": target,
                "lift": lift,
                "unit": unit,
                "n_total": len(rows),
                "n_scored": len(scored),
                "n_failed": len(rows) - len(scored),
                "status": status,
                "status_counts_json": json_bytes(status_counts).decode("utf-8").strip(),
                "rmse": rmse,
                "rmse_ci95_low": lower,
                "rmse_ci95_high": upper,
                "mae": mae,
                "signed_bias": bias,
            }
        )
    return output


def _paired_metric_row(
    estimate_rows: Sequence[Mapping[str, Any]],
    binding: Mapping[str, str],
    *,
    contrast_id: str,
    left_estimator: str,
    left_prior: str,
    left_noise: float,
    right_estimator: str,
    right_prior: str,
    right_noise: float,
    target: str,
    lift: str,
) -> dict[str, Any]:
    lookup: dict[tuple[str, str, float, str, str, str], Mapping[str, Any]] = {
        (
            str(row["entity_id"]),
            str(row["estimator_id"]),
            float(row["noise_scale"]),
            str(row["prior"]),
            str(row["target"]),
            str(row["lift"]),
        ): row
        for row in estimate_rows
    }
    all_entities = sorted(
        {
            str(row["entity_id"])
            for row in estimate_rows
            if str(row["target"]) == target and str(row["lift"]) == lift
        }
    )
    paired: list[tuple[str, float, float]] = []
    paired_fit_statuses: list[str] = []
    for entity_id in all_entities:
        left = lookup.get((entity_id, left_estimator, left_noise, left_prior, target, lift))
        right = lookup.get((entity_id, right_estimator, right_noise, right_prior, target, lift))
        if (
            left is not None
            and right is not None
            and left["estimate"] is not None
            and right["estimate"] is not None
            and left["truth"] is not None
            and right["truth"] is not None
        ):
            paired.append(
                (
                    entity_id,
                    float(left["estimate"]) - float(left["truth"]),
                    float(right["estimate"]) - float(right["truth"]),
                )
            )
            paired_fit_statuses.extend([str(left["status"]), str(right["status"])])
    left_errors = [left_error for _, left_error, _ in paired]
    right_errors = [right_error for _, _, right_error in paired]
    difference = (
        math.sqrt(float(np.mean(np.square(left_errors))))
        - math.sqrt(float(np.mean(np.square(right_errors))))
        if paired
        else None
    )
    if paired:
        rng = random.Random(
            _seed_for_key(
                [
                    contrast_id,
                    left_estimator,
                    left_prior,
                    left_noise,
                    right_estimator,
                    right_prior,
                    right_noise,
                    target,
                    lift,
                ]
            )
        )
        indices = np.arange(len(paired))
        replicates = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
        for replicate in range(BOOTSTRAP_REPLICATES):
            chosen = [int(indices[rng.randrange(len(indices))]) for _ in range(len(indices))]
            left_rmse = math.sqrt(float(np.mean([left_errors[index] ** 2 for index in chosen])))
            right_rmse = math.sqrt(float(np.mean([right_errors[index] ** 2 for index in chosen])))
            replicates[replicate] = left_rmse - right_rmse
        ci_low: float | None
        ci_high: float | None
        ci_low, ci_high = [float(x) for x in np.quantile(replicates, [0.025, 0.975])]
    else:
        ci_low = ci_high = None
    status = "NO_PAIRED_ESTIMATES"
    if paired:
        if len(paired) != len(all_entities):
            status = "PARTIAL_FAILURES_RETAINED"
        elif any("NONCONVERGED" in value for value in paired_fit_statuses):
            status = "COMPLETE_WITH_NONCONVERGED_FITS_RETAINED"
        elif any(value.startswith("MAP_ONLY") for value in paired_fit_statuses):
            status = "COMPLETE_MAP_ONLY_POSTERIOR_FAILURE_RETAINED"
        else:
            status = "COMPLETE"
    return {
        **binding,
        "contrast_id": contrast_id,
        "estimator_a": left_estimator,
        "prior_a": left_prior,
        "noise_scale_a": left_noise,
        "estimator_b": right_estimator,
        "prior_b": right_prior,
        "noise_scale_b": right_noise,
        "target": target,
        "lift": lift,
        "unit": next(
            (str(row["unit"]) for row in estimate_rows if str(row["target"]) == target),
            "dimensionless",
        ),
        "n_total": len(all_entities),
        "n_paired": len(paired),
        "status": status,
        "paired_rmse_difference_a_minus_b": difference,
        "rmse_difference_ci95_low": ci_low,
        "rmse_difference_ci95_high": ci_high,
    }


def _parameter_true_values(truth_row: Mapping[str, Any]) -> tuple[dict[str, float], dict[str, str]]:
    values = {
        f"coordinate.{name}": float(truth_row["population_coordinates"][index])
        for index, name in enumerate(COORDINATE_NAMES)
    }
    units = {name: "dimensionless" for name in values}
    values["reference_stimulus"] = float(truth_row["reference_stimulus"])
    values["X_REF"] = float(truth_row["X_REF"])
    units["reference_stimulus"] = "dimensionless"
    units["X_REF"] = "dose-intensity product"
    for lift in LIFTS:
        for name in (
            "baseline_kg",
            "adaptation_gain",
            "adaptation_time_days",
            "suppression_gain",
            "suppression_time_days",
        ):
            key = f"{lift}.{name}"
            values[key] = float(truth_row["lifts"][lift][name])
            units[key] = (
                "kg"
                if name == "baseline_kg"
                else "days"
                if name.endswith("_days")
                else "dimensionless"
            )
    return values, units


def _parameter_estimate_values(
    coordinates: Array | None, posterior: Mapping[str, Any] | None = None
) -> dict[str, float]:
    if coordinates is None:
        return {}
    if posterior is not None and posterior.get("status") == "LAPLACE_APPROXIMATION_VALID":
        values = {
            f"coordinate.{item['name']}": float(item["mean"]) for item in posterior["coordinates"]
        }
        values.update(
            {str(item["name"]): float(item["mean"]) for item in posterior["physical_parameters"]}
        )
        return values
    global_values, per_lift = _physical_parameters(coordinates)
    values = {
        f"coordinate.{name}": float(coordinates[index])
        for index, name in enumerate(COORDINATE_NAMES)
    }
    values.update(global_values)
    for lift in LIFTS:
        values.update({f"{lift}.{name}": value for name, value in per_lift[lift].items()})
    return values


def _parameter_lift(name: str) -> str:
    if name.startswith("coordinate."):
        coordinate = name.removeprefix("coordinate.")
        if coordinate.startswith("bench_"):
            return "bench_press"
        if coordinate.startswith(("squat_", "deadlift_")):
            return coordinate.split("_", 1)[0]
        return "shared"
    if "." in name:
        return name.split(".", 1)[0]
    return "shared"


def _parameter_metric_rows(
    parameter_rows: Sequence[Mapping[str, Any]], binding: Mapping[str, str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, float, str, str, str], list[Mapping[str, Any]]] = {}
    for row in parameter_rows:
        key = (
            str(row["estimator_id"]),
            str(row["prior"]),
            float(row["noise_scale"]),
            str(row["parameter"]),
            str(row["lift"]),
            str(row["unit"]),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        estimator_id, prior, noise_scale, parameter, lift, unit = key
        scored = [row for row in rows if row["estimate"] is not None and row["truth"] is not None]
        errors = [float(row["estimate"]) - float(row["truth"]) for row in scored]
        rmse = math.sqrt(float(np.mean(np.square(errors)))) if errors else None
        lower, upper = _rmse_interval(errors, _seed_for_key(key))
        status = (
            str(rows[0]["status"])
            if not scored and len({str(row["status"]) for row in rows}) == 1
            else "COMPLETE_WITH_NONCONVERGED_FITS_RETAINED"
            if len(scored) == len(rows)
            and any("NONCONVERGED" in str(row["status"]) for row in scored)
            else "COMPLETE_MAP_ONLY_POSTERIOR_FAILURE_RETAINED"
            if len(scored) == len(rows)
            and any(str(row["status"]).startswith("MAP_ONLY") for row in scored)
            else "COMPLETE"
            if len(scored) == len(rows)
            else "PARTIAL_FAILURES_RETAINED"
            if scored
            else "NO_VALID_ESTIMATES"
        )
        output.append(
            {
                **binding,
                "estimator_id": estimator_id,
                "prior": prior,
                "noise_scale": noise_scale,
                "parameter": parameter,
                "lift": lift,
                "unit": unit,
                "n_total": len(rows),
                "n_scored": len(scored),
                "n_failed": len(rows) - len(scored),
                "status": status,
                "rmse": rmse,
                "rmse_ci95_low": lower,
                "rmse_ci95_high": upper,
                "mae": float(np.mean(np.abs(errors))) if errors else None,
                "signed_bias": float(np.mean(errors)) if errors else None,
            }
        )
    return output


def run_experiments(
    observation_rows: Sequence[dict[str, Any]],
    truth_rows: Sequence[dict[str, Any]],
    binding: Mapping[str, str],
) -> dict[str, bytes]:
    """Fit every declared method and build target-wise, paired, and diagnostic evidence."""
    observation_by_id = {str(row["entity_id"]): row for row in observation_rows}
    truth_by_id = {str(row["entity_id"]): row for row in truth_rows}
    if set(observation_by_id) != set(truth_by_id) or len(observation_by_id) != ENTITY_COUNT:
        raise ValueError("participant observations and evaluation truth do not align")
    development_ids = sorted(
        str(row["entity_id"]) for row in observation_rows if row["split"] == "development"
    )
    test_ids = sorted(str(row["entity_id"]) for row in observation_rows if row["split"] == "test")
    if (
        len(development_ids) != DEVELOPMENT_COUNT
        or len(test_ids) != ENTITY_COUNT - DEVELOPMENT_COUNT
    ):
        raise ValueError("development/test entity counts differ from the frozen split")
    if set(development_ids) & set(test_ids):
        raise ValueError("development and test entities overlap")

    inputs_by_key: dict[tuple[str, float], StudyInputs] = {}
    full_fits: dict[tuple[str, float], FitResult] = {}
    optimizer_rows: list[dict[str, Any]] = []
    for observation_row in observation_rows:
        entity_id = str(observation_row["entity_id"])
        for noise_scale in NOISE_SCALES:
            inputs = study_inputs_from_row(observation_row, noise_scale)
            inputs_by_key[(entity_id, noise_scale)] = inputs
            fit = fit_coordinates(inputs)
            full_fits[(entity_id, noise_scale)] = fit
            optimizer_rows.extend(
                {
                    **binding,
                    "estimator_id": ESTIMATOR_IDS["full"],
                    "prior": "none",
                    "entity_id": entity_id,
                    "split": str(observation_row["split"]),
                    "noise_scale": noise_scale,
                    **start,
                }
                for start in fit.starts
            )

    posterior_by_key: dict[tuple[str, float, str], dict[str, Any]] = {}
    posterior_fit_by_key: dict[tuple[str, float, str], FitResult] = {}
    posterior_diagnostic_rows: list[dict[str, Any]] = []
    for entity_id in test_ids:
        for noise_scale in NOISE_SCALES:
            for prior in ("uniform", "beta8"):
                inputs = inputs_by_key[(entity_id, noise_scale)]
                if noise_scale == 0:
                    fit = full_fits[(entity_id, noise_scale)]
                    posterior = {"status": "NOT_DEFINED_NOISE_FREE_POSTERIOR"}
                else:
                    if prior == "uniform":
                        fit = full_fits[(entity_id, noise_scale)]
                    else:
                        fit = fit_coordinates(inputs, prior="beta8")
                        optimizer_rows.extend(
                            {
                                **binding,
                                "estimator_id": ESTIMATOR_IDS["bayesian"],
                                "prior": prior,
                                "entity_id": entity_id,
                                "split": "test",
                                "noise_scale": noise_scale,
                                **start,
                            }
                            for start in fit.starts
                        )
                    posterior = _laplace_posterior(inputs, fit, prior)
                posterior_by_key[(entity_id, noise_scale, prior)] = posterior
                posterior_fit_by_key[(entity_id, noise_scale, prior)] = fit
                posterior_diagnostic_rows.append(
                    {
                        **binding,
                        "estimator_id": ESTIMATOR_IDS["bayesian"],
                        "entity_id": entity_id,
                        "noise_scale": noise_scale,
                        "prior": prior,
                        "status": posterior.get("status"),
                        "map_fit_status": fit.status,
                        "boundary_distance_min": posterior.get("boundary_distance_min"),
                        "hessian_min_eigenvalue": posterior.get(
                            "minimum_hessian_eigenvalue", posterior.get("hessian_min_eigenvalue")
                        ),
                        "hessian_max_eigenvalue": posterior.get(
                            "maximum_hessian_eigenvalue", posterior.get("hessian_max_eigenvalue")
                        ),
                        "hessian_condition_number": posterior.get("hessian_condition_number"),
                        "candidate_batches": posterior.get("candidate_batches"),
                        "accepted_draws": posterior.get("accepted_draws"),
                        "hessian_gradient_evaluations": posterior.get(
                            "hessian_gradient_evaluations"
                        ),
                        "diagnostic_method": "local Laplace approximation; no MCMC chain or ESS claimed",
                    }
                )

    residual_models: dict[float, dict[str, Any]] = {}
    for noise_scale in NOISE_SCALES:
        residual_features: list[Array] = []
        residual_targets: list[float] = []
        training_complete = True
        for entity_id in development_ids:
            inputs = inputs_by_key[(entity_id, noise_scale)]
            fit = full_fits[(entity_id, noise_scale)]
            if fit.output is None:
                training_complete = False
                continue
            truth_lifts = truth_by_id[entity_id]["lifts"]
            features = _residual_features(inputs, fit.output)
            for lift_index, lift in enumerate(LIFTS):
                residual_features.append(features[lift_index])
                residual_targets.append(
                    float(truth_lifts[lift]["DeltaC_56_kg"])
                    - float(fit.output.delta_c56[lift_index])
                )
        if training_complete and len(residual_features) == DEVELOPMENT_COUNT * len(LIFTS):
            model = fit_residual_model(
                np.vstack(residual_features),
                np.asarray(residual_targets, dtype=np.float64),
                development_ids,
            )
            model["noise_scale"] = noise_scale
            model["model_sha256"] = sha256_record(model)
            residual_models[noise_scale] = model
        else:
            residual_models[noise_scale] = {
                "status": "RESIDUAL_TRAINING_INCOMPLETE",
                "noise_scale": noise_scale,
                "development_entity_ids": development_ids,
                "failed_development_entities": [
                    entity_id
                    for entity_id in development_ids
                    if full_fits[(entity_id, noise_scale)].output is None
                ],
            }
        training_set = set(residual_models[noise_scale]["development_entity_ids"])
        if training_set & set(test_ids):
            raise ValueError("residual training contains a held-out test entity")

    estimate_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []

    def add_target(
        *,
        estimator_id: str,
        prior: str,
        noise_scale: float,
        entity_id: str,
        lift_index: int,
        target: str,
        estimate: float | None,
        status: str,
        source_estimator_id: str | None = None,
    ) -> None:
        lift = LIFTS[lift_index]
        truth_value = float(truth_by_id[entity_id]["lifts"][lift][target])
        estimate_rows.append(
            {
                **binding,
                "estimator_id": estimator_id,
                "prior": prior,
                "noise_scale": noise_scale,
                "entity_id": entity_id,
                "split": "test",
                "history_template": int(
                    observation_by_id[entity_id]["history_template_by_lift"][lift]
                ),
                "declared_plan": str(observation_by_id[entity_id]["declared_plan"]),
                "lift": lift,
                "target": target,
                "unit": _target_units()[target],
                "estimate": estimate,
                "truth": truth_value,
                "error": estimate - truth_value if estimate is not None else None,
                "status": status,
                "source_estimator_id": source_estimator_id or estimator_id,
            }
        )

    def add_parameters(
        *,
        estimator_id: str,
        prior: str,
        noise_scale: float,
        entity_id: str,
        coordinates: Array | None,
        posterior: Mapping[str, Any] | None,
        status: str,
        source_estimator_id: str | None = None,
    ) -> None:
        truth_values, units = _parameter_true_values(truth_by_id[entity_id])
        estimates = _parameter_estimate_values(coordinates, posterior)
        for name, truth_value in truth_values.items():
            estimate = estimates.get(name)
            parameter_lift = _parameter_lift(name)
            history_template: int | str = (
                int(observation_by_id[entity_id]["history_template_by_lift"][parameter_lift])
                if parameter_lift in LIFTS
                else "shared"
            )
            parameter_rows.append(
                {
                    **binding,
                    "estimator_id": estimator_id,
                    "prior": prior,
                    "noise_scale": noise_scale,
                    "entity_id": entity_id,
                    "history_template": history_template,
                    "parameter": name,
                    "lift": parameter_lift,
                    "unit": units[name],
                    "estimate": estimate,
                    "truth": truth_value,
                    "error": estimate - truth_value if estimate is not None else None,
                    "status": status if estimate is not None else status,
                    "source_estimator_id": source_estimator_id or estimator_id,
                }
            )

    for entity_id in test_ids:
        for noise_scale in NOISE_SCALES:
            inputs = inputs_by_key[(entity_id, noise_scale)]
            full_fit = full_fits[(entity_id, noise_scale)]
            output = full_fit.output
            for lift_index, _lift in enumerate(LIFTS):
                reduced_estimate = float(inputs.assessments[lift_index, -1])
                add_target(
                    estimator_id=ESTIMATOR_IDS["reduced"],
                    prior="none",
                    noise_scale=noise_scale,
                    entity_id=entity_id,
                    lift_index=lift_index,
                    target="P_223_kg",
                    estimate=reduced_estimate,
                    status="DIRECT_LATEST_ASSESSMENT",
                )
                for target in TARGET_NAMES[1:]:
                    add_target(
                        estimator_id=ESTIMATOR_IDS["reduced"],
                        prior="none",
                        noise_scale=noise_scale,
                        entity_id=entity_id,
                        lift_index=lift_index,
                        target=target,
                        estimate=None,
                        status="NOT_ESTIMATED_BY_METHOD",
                    )
                for target in TARGET_NAMES:
                    estimate = _estimate_targets(output, lift_index).get(target) if output else None
                    add_target(
                        estimator_id=ESTIMATOR_IDS["full"],
                        prior="none",
                        noise_scale=noise_scale,
                        entity_id=entity_id,
                        lift_index=lift_index,
                        target=target,
                        estimate=estimate,
                        status=full_fit.status,
                    )
            add_parameters(
                estimator_id=ESTIMATOR_IDS["full"],
                prior="none",
                noise_scale=noise_scale,
                entity_id=entity_id,
                coordinates=full_fit.coordinates,
                posterior=None,
                status=full_fit.status,
            )

            for prior in ("uniform", "beta8"):
                map_fit = posterior_fit_by_key[(entity_id, noise_scale, prior)]
                posterior = posterior_by_key[(entity_id, noise_scale, prior)]
                posterior_status = str(posterior.get("status"))
                valid_posterior = posterior_status == "LAPLACE_APPROXIMATION_VALID"
                if valid_posterior:
                    point_status = posterior_status
                elif noise_scale == 0:
                    point_status = "NOT_DEFINED_NOISE_FREE_POSTERIOR"
                else:
                    point_status = f"MAP_ONLY_{posterior_status}"
                if map_fit.status == "NONCONVERGED_BEST_RETAINED":
                    point_status = f"{point_status}_NONCONVERGED_MAP"
                for lift_index, _lift in enumerate(LIFTS):
                    for target in TARGET_NAMES:
                        if valid_posterior:
                            target_summaries = cast(Mapping[str, Any], posterior.get("targets", {}))
                            estimate = float(target_summaries[target]["mean"][lift_index])
                        elif noise_scale == 0 or map_fit.output is None:
                            estimate = None
                        else:
                            estimate = _estimate_targets(map_fit.output, lift_index)[target]
                        add_target(
                            estimator_id=ESTIMATOR_IDS["bayesian"],
                            prior=prior,
                            noise_scale=noise_scale,
                            entity_id=entity_id,
                            lift_index=lift_index,
                            target=target,
                            estimate=estimate,
                            status=point_status,
                        )
                add_parameters(
                    estimator_id=ESTIMATOR_IDS["bayesian"],
                    prior=prior,
                    noise_scale=noise_scale,
                    entity_id=entity_id,
                    coordinates=map_fit.coordinates,
                    posterior=posterior,
                    status=point_status,
                )

            residual_model = residual_models[noise_scale]
            if output is None:
                correction = np.full(len(LIFTS), np.nan, dtype=np.float64)
                hybrid_status = "FULL_STRUCTURAL_FIT_FAILED"
            elif residual_model.get("status") != "FIT_ON_DEVELOPMENT_ONLY":
                correction = np.full(len(LIFTS), np.nan, dtype=np.float64)
                hybrid_status = "RESIDUAL_TRAINING_INCOMPLETE"
            else:
                correction = predict_residual(residual_model, _residual_features(inputs, output))
                hybrid_status = "RESIDUAL_CORRECTION_FIT_ON_DEVELOPMENT_ONLY"
            if full_fit.status == "NONCONVERGED_BEST_RETAINED":
                hybrid_status = f"{hybrid_status}_NONCONVERGED_FULL_FIT"
            for lift_index, _lift in enumerate(LIFTS):
                inherited = _estimate_targets(output, lift_index) if output else {}
                for target in TARGET_NAMES:
                    if target == "DeltaC_56_kg":
                        estimate = (
                            inherited[target] + float(correction[lift_index])
                            if math.isfinite(float(correction[lift_index]))
                            else None
                        )
                        status = hybrid_status
                    else:
                        estimate = inherited.get(target)
                        status = (
                            "INHERITED_FROM_NONCONVERGED_FULL_FIT"
                            if full_fit.status == "NONCONVERGED_BEST_RETAINED"
                            else "INHERITED_FROM_FULL_STRUCTURAL_FIT"
                            if output
                            else full_fit.status
                        )
                    add_target(
                        estimator_id=ESTIMATOR_IDS["hybrid"],
                        prior="none",
                        noise_scale=noise_scale,
                        entity_id=entity_id,
                        lift_index=lift_index,
                        target=target,
                        estimate=estimate,
                        status=status,
                        source_estimator_id=ESTIMATOR_IDS["full"],
                    )
            add_parameters(
                estimator_id=ESTIMATOR_IDS["hybrid"],
                prior="none",
                noise_scale=noise_scale,
                entity_id=entity_id,
                coordinates=full_fit.coordinates,
                posterior=None,
                status=(
                    "INHERITED_FROM_NONCONVERGED_FULL_FIT"
                    if full_fit.status == "NONCONVERGED_BEST_RETAINED"
                    else "INHERITED_FROM_FULL_STRUCTURAL_FIT"
                    if full_fit.output
                    else full_fit.status
                ),
                source_estimator_id=ESTIMATOR_IDS["full"],
            )
            add_parameters(
                estimator_id=ESTIMATOR_IDS["reduced"],
                prior="none",
                noise_scale=noise_scale,
                entity_id=entity_id,
                coordinates=None,
                posterior=None,
                status="NOT_ESTIMATED_BY_METHOD",
            )

    target_metrics = _target_metric_rows(estimate_rows, binding)
    parameter_metrics = _parameter_metric_rows(parameter_rows, binding)
    paired_rows = _build_paired_comparisons(estimate_rows, binding)
    posterior_metrics, prior_sensitivity = _posterior_metrics(
        posterior_by_key, truth_by_id, test_ids, binding
    )
    parameter_posterior_metrics, parameter_prior_sensitivity = _posterior_parameter_metrics(
        posterior_by_key, truth_by_id, test_ids, binding
    )
    history_rows = _history_sensitivity_rows(estimate_rows, binding)
    equivalences = _equivalent_solutions(inputs_by_key, full_fits, binding)
    identifiability = identifiability_diagnostics()
    identifiability.update(binding)
    identifiability["native_template_global_identification"] = (
        "COUNTEREXAMPLE_FOUND_IN_CANONICAL_SAMPLE" if equivalences else "INCONCLUSIVE"
    )
    identifiability["native_template_equivalent_solution_count"] = len(equivalences)
    posterior_summary_rows = [
        {
            **binding,
            "entity_id": entity_id,
            "noise_scale": noise_scale,
            "prior": prior,
            "status": posterior.get("status"),
            "mode_coordinates": posterior.get("mode_coordinates"),
            "targets": posterior.get("targets"),
            "coordinates": posterior.get("coordinates"),
            "physical_parameters": posterior.get("physical_parameters"),
            "hessian_min_eigenvalue": posterior.get(
                "minimum_hessian_eigenvalue", posterior.get("hessian_min_eigenvalue")
            ),
            "hessian_max_eigenvalue": posterior.get(
                "maximum_hessian_eigenvalue", posterior.get("hessian_max_eigenvalue")
            ),
            "hessian_condition_number": posterior.get("hessian_condition_number"),
            "candidate_batches": posterior.get("candidate_batches"),
            "accepted_draws": posterior.get("accepted_draws"),
            "hessian_gradient_evaluations": posterior.get("hessian_gradient_evaluations"),
        }
        for (entity_id, noise_scale, prior), posterior in sorted(posterior_by_key.items())
    ]

    output_files = {
        "target-estimates.csv": csv_bytes(
            estimate_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "noise_scale",
                "entity_id",
                "split",
                "history_template",
                "declared_plan",
                "lift",
                "target",
                "unit",
                "estimate",
                "truth",
                "error",
                "status",
                "source_estimator_id",
            ),
        ),
        "parameter-errors.csv": csv_bytes(
            parameter_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "noise_scale",
                "entity_id",
                "history_template",
                "parameter",
                "lift",
                "unit",
                "estimate",
                "truth",
                "error",
                "status",
                "source_estimator_id",
            ),
        ),
        "target-results.csv": csv_bytes(
            target_metrics,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "noise_scale",
                "target",
                "lift",
                "unit",
                "n_total",
                "n_scored",
                "n_failed",
                "status",
                "status_counts_json",
                "rmse",
                "rmse_ci95_low",
                "rmse_ci95_high",
                "mae",
                "signed_bias",
            ),
        ),
        "parameter-results.csv": csv_bytes(
            parameter_metrics,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "noise_scale",
                "parameter",
                "lift",
                "unit",
                "n_total",
                "n_scored",
                "n_failed",
                "status",
                "rmse",
                "rmse_ci95_low",
                "rmse_ci95_high",
                "mae",
                "signed_bias",
            ),
        ),
        "paired-comparisons.csv": csv_bytes(
            paired_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "contrast_id",
                "estimator_a",
                "prior_a",
                "noise_scale_a",
                "estimator_b",
                "prior_b",
                "noise_scale_b",
                "target",
                "lift",
                "unit",
                "n_total",
                "n_paired",
                "status",
                "paired_rmse_difference_a_minus_b",
                "rmse_difference_ci95_low",
                "rmse_difference_ci95_high",
            ),
        ),
        "posterior-results.csv": csv_bytes(
            posterior_metrics,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "prior",
                "noise_scale",
                "target",
                "lift",
                "unit",
                "n_total",
                "n_valid_posterior",
                "coverage_95",
                "mean_interval_width",
                "mean_posterior_bias",
                "status",
            ),
        ),
        "posterior-summaries.jsonl": jsonl_bytes(posterior_summary_rows),
        "parameter-posterior-results.csv": csv_bytes(
            parameter_posterior_metrics,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "prior",
                "noise_scale",
                "parameter",
                "lift",
                "unit",
                "n_total",
                "n_valid_posterior",
                "coverage_95",
                "mean_interval_width",
                "mean_posterior_bias",
                "status",
            ),
        ),
        "parameter-prior-sensitivity.csv": csv_bytes(
            parameter_prior_sensitivity,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "noise_scale",
                "parameter",
                "lift",
                "unit",
                "n_total",
                "n_paired_posteriors",
                "posterior_mean_difference_beta8_minus_uniform",
                "mean_difference_ci95_low",
                "mean_difference_ci95_high",
                "uniform_mean_interval_width",
                "beta8_mean_interval_width",
                "uniform_coverage_95",
                "beta8_coverage_95",
                "status",
            ),
        ),
        "prior-sensitivity.csv": csv_bytes(
            prior_sensitivity,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "noise_scale",
                "target",
                "lift",
                "unit",
                "n_total",
                "n_paired_posteriors",
                "posterior_mean_difference_beta8_minus_uniform",
                "mean_difference_ci95_low",
                "mean_difference_ci95_high",
                "uniform_mean_interval_width",
                "beta8_mean_interval_width",
                "uniform_coverage_95",
                "beta8_coverage_95",
                "status",
            ),
        ),
        "history-sensitivity.csv": csv_bytes(
            history_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "noise_scale",
                "history_template",
                "target",
                "lift",
                "unit",
                "n_total",
                "n_scored",
                "rmse",
                "mae",
                "signed_bias",
                "status",
            ),
        ),
        "optimizer-diagnostics.csv": csv_bytes(
            optimizer_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "entity_id",
                "split",
                "noise_scale",
                "start_index",
                "start_coordinates",
                "coordinates",
                "objective",
                "converged",
                "eligible_final",
                "status",
                "solver_status",
                "message",
                "function_evaluations",
                "gradient_evaluations",
                "model_evaluations",
                "gradient_infinity_norm",
                "support_penalty_rows_seen",
                "final_support_violations",
            ),
        ),
        "posterior-diagnostics.csv": csv_bytes(
            posterior_diagnostic_rows,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "entity_id",
                "noise_scale",
                "prior",
                "status",
                "map_fit_status",
                "boundary_distance_min",
                "hessian_min_eigenvalue",
                "hessian_max_eigenvalue",
                "hessian_condition_number",
                "candidate_batches",
                "accepted_draws",
                "hessian_gradient_evaluations",
                "diagnostic_method",
            ),
        ),
        "equivalent-solutions.csv": csv_bytes(
            equivalences,
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "entity_id",
                "noise_scale",
                "start_a",
                "start_b",
                "objective_difference",
                "history_rmse_kg",
                "max_coordinate_difference",
                "status",
            ),
        ),
        "identifiability.json": json_bytes(identifiability),
        "residual-models.json": json_bytes(
            {
                "study_id": STUDY_ID,
                "protocol_digest": PROTOCOL_DIGEST,
                "realization_id": binding["realization_id"],
                "evaluation_id": EVALUATION_ID,
                "training_entity_ids": development_ids,
                "held_out_entity_ids": test_ids,
                "models_by_noise_scale": {
                    str(noise_scale): model for noise_scale, model in residual_models.items()
                },
            }
        ),
        "compute-cost.csv": csv_bytes(
            _compute_cost_rows(optimizer_rows, posterior_diagnostic_rows, binding),
            (
                "study_id",
                "protocol_digest",
                "realization_id",
                "evaluation_id",
                "source_set_digest",
                "truth_sha256",
                "observations_sha256",
                "estimator_id",
                "prior",
                "noise_scale",
                "solver_starts",
                "solver_function_evaluations",
                "solver_gradient_evaluations",
                "solver_model_evaluations",
                "shared_full_fit_model_evaluations",
                "posterior_candidate_batches",
                "posterior_hessian_gradient_evaluations",
                "posterior_draws",
                "residual_fit_rows",
                "direct_observation_reads",
                "daily_state_transition_equivalents",
                "compute_measure",
            ),
        ),
    }
    return output_files


def _posterior_metrics(
    posterior_by_key: Mapping[tuple[str, float, str], Mapping[str, Any]],
    truth_by_id: Mapping[str, Mapping[str, Any]],
    test_ids: Sequence[str],
    binding: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    posterior_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    for noise_scale in NOISE_SCALES:
        for prior in ("uniform", "beta8"):
            for target in TARGET_NAMES:
                for lift_index, lift in enumerate(LIFTS):
                    valid: list[tuple[str, float, float, float, float]] = []
                    for entity_id in test_ids:
                        posterior = posterior_by_key[(entity_id, noise_scale, prior)]
                        if posterior.get("status") != "LAPLACE_APPROXIMATION_VALID":
                            continue
                        summary = posterior["targets"][target]
                        mean = float(summary["mean"][lift_index])
                        lower = float(summary["lower_95"][lift_index])
                        upper = float(summary["upper_95"][lift_index])
                        truth = float(truth_by_id[entity_id]["lifts"][lift][target])
                        valid.append((entity_id, mean, lower, upper, truth))
                    coverage = (
                        float(
                            np.mean(
                                [lower <= truth <= upper for _, _, lower, upper, truth in valid]
                            )
                        )
                        if valid
                        else None
                    )
                    widths = [upper - lower for _, _, lower, upper, _ in valid]
                    biases = [mean - truth for _, mean, _, _, truth in valid]
                    status = (
                        "NOT_DEFINED_NOISE_FREE_POSTERIOR"
                        if noise_scale == 0
                        else "COMPLETE"
                        if len(valid) == len(test_ids)
                        else "PARTIAL_POSTERIOR_FAILURES_RETAINED"
                        if valid
                        else "NO_VALID_POSTERIOR_INTERVALS"
                    )
                    posterior_rows.append(
                        {
                            **binding,
                            "prior": prior,
                            "noise_scale": noise_scale,
                            "target": target,
                            "lift": lift,
                            "unit": _target_units()[target],
                            "n_total": len(test_ids),
                            "n_valid_posterior": len(valid),
                            "coverage_95": coverage,
                            "mean_interval_width": float(np.mean(widths)) if widths else None,
                            "mean_posterior_bias": float(np.mean(biases)) if biases else None,
                            "status": status,
                        }
                    )

        if noise_scale == 0:
            for target in TARGET_NAMES:
                for lift in LIFTS:
                    sensitivity_rows.append(
                        {
                            **binding,
                            "noise_scale": noise_scale,
                            "target": target,
                            "lift": lift,
                            "unit": _target_units()[target],
                            "n_total": len(test_ids),
                            "n_paired_posteriors": 0,
                            "posterior_mean_difference_beta8_minus_uniform": None,
                            "mean_difference_ci95_low": None,
                            "mean_difference_ci95_high": None,
                            "uniform_mean_interval_width": None,
                            "beta8_mean_interval_width": None,
                            "uniform_coverage_95": None,
                            "beta8_coverage_95": None,
                            "status": "NOT_DEFINED_NOISE_FREE_POSTERIOR",
                        }
                    )
            continue

        for target in TARGET_NAMES:
            for lift_index, lift in enumerate(LIFTS):
                paired: list[tuple[float, float, float, float, bool, bool]] = []
                for entity_id in test_ids:
                    uniform = posterior_by_key[(entity_id, noise_scale, "uniform")]
                    beta8 = posterior_by_key[(entity_id, noise_scale, "beta8")]
                    if (
                        uniform.get("status") != "LAPLACE_APPROXIMATION_VALID"
                        or beta8.get("status") != "LAPLACE_APPROXIMATION_VALID"
                    ):
                        continue
                    uniform_summary = uniform["targets"][target]
                    beta_summary = beta8["targets"][target]
                    truth = float(truth_by_id[entity_id]["lifts"][lift][target])
                    uniform_mean = float(uniform_summary["mean"][lift_index])
                    beta_mean = float(beta_summary["mean"][lift_index])
                    uniform_covered = (
                        float(uniform_summary["lower_95"][lift_index])
                        <= truth
                        <= float(uniform_summary["upper_95"][lift_index])
                    )
                    beta_covered = (
                        float(beta_summary["lower_95"][lift_index])
                        <= truth
                        <= float(beta_summary["upper_95"][lift_index])
                    )
                    paired.append(
                        (
                            beta_mean - uniform_mean,
                            float(uniform_summary["upper_95"][lift_index])
                            - float(uniform_summary["lower_95"][lift_index]),
                            float(beta_summary["upper_95"][lift_index])
                            - float(beta_summary["lower_95"][lift_index]),
                            truth,
                            uniform_covered,
                            beta_covered,
                        )
                    )
                differences = [row[0] for row in paired]
                mean_ci_low, mean_ci_high = _mean_interval(
                    differences,
                    _seed_for_key(["prior-sensitivity", noise_scale, target, lift]),
                )
                uniform_coverage = float(np.mean([row[4] for row in paired])) if paired else None
                beta8_coverage = float(np.mean([row[5] for row in paired])) if paired else None
                sensitivity_rows.append(
                    {
                        **binding,
                        "noise_scale": noise_scale,
                        "target": target,
                        "lift": lift,
                        "unit": _target_units()[target],
                        "n_total": len(test_ids),
                        "n_paired_posteriors": len(paired),
                        "posterior_mean_difference_beta8_minus_uniform": float(np.mean(differences))
                        if differences
                        else None,
                        "mean_difference_ci95_low": mean_ci_low,
                        "mean_difference_ci95_high": mean_ci_high,
                        "uniform_mean_interval_width": float(np.mean([row[1] for row in paired]))
                        if paired
                        else None,
                        "beta8_mean_interval_width": float(np.mean([row[2] for row in paired]))
                        if paired
                        else None,
                        "uniform_coverage_95": uniform_coverage,
                        "beta8_coverage_95": beta8_coverage,
                        "status": "COMPLETE"
                        if len(paired) == len(test_ids)
                        else "PARTIAL_POSTERIOR_FAILURES_RETAINED"
                        if paired
                        else "NO_PAIRED_POSTERIOR_INTERVALS",
                    }
                )
    return posterior_rows, sensitivity_rows


def _posterior_parameter_metrics(
    posterior_by_key: Mapping[tuple[str, float, str], Mapping[str, Any]],
    truth_by_id: Mapping[str, Mapping[str, Any]],
    test_ids: Sequence[str],
    binding: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    parameter_keys, units = _parameter_true_values(truth_by_id[test_ids[0]])
    names = tuple(parameter_keys)

    def summaries(posterior: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        by_name: dict[str, Mapping[str, Any]] = {}
        for record in posterior.get("coordinates", []):
            by_name[f"coordinate.{record['name']}"] = record
        for record in posterior.get("physical_parameters", []):
            by_name[str(record["name"])] = record
        return by_name

    for noise_scale in NOISE_SCALES:
        for prior in ("uniform", "beta8"):
            for name in names:
                valid: list[tuple[str, float, float, float, float]] = []
                for entity_id in test_ids:
                    posterior = posterior_by_key[(entity_id, noise_scale, prior)]
                    if posterior.get("status") != "LAPLACE_APPROXIMATION_VALID":
                        continue
                    record = summaries(posterior)[name]
                    truth_values, _ = _parameter_true_values(truth_by_id[entity_id])
                    valid.append(
                        (
                            entity_id,
                            float(record["mean"]),
                            float(record["lower_95"]),
                            float(record["upper_95"]),
                            truth_values[name],
                        )
                    )
                coverage = (
                    float(np.mean([lower <= truth <= upper for _, _, lower, upper, truth in valid]))
                    if valid
                    else None
                )
                widths = [upper - lower for _, _, lower, upper, _ in valid]
                biases = [mean - truth for _, mean, _, _, truth in valid]
                status = (
                    "NOT_DEFINED_NOISE_FREE_POSTERIOR"
                    if noise_scale == 0
                    else "COMPLETE"
                    if len(valid) == len(test_ids)
                    else "PARTIAL_POSTERIOR_FAILURES_RETAINED"
                    if valid
                    else "NO_VALID_POSTERIOR_INTERVALS"
                )
                summary_rows.append(
                    {
                        **binding,
                        "prior": prior,
                        "noise_scale": noise_scale,
                        "parameter": name,
                        "lift": _parameter_lift(name),
                        "unit": units[name],
                        "n_total": len(test_ids),
                        "n_valid_posterior": len(valid),
                        "coverage_95": coverage,
                        "mean_interval_width": float(np.mean(widths)) if widths else None,
                        "mean_posterior_bias": float(np.mean(biases)) if biases else None,
                        "status": status,
                    }
                )

        for name in names:
            if noise_scale == 0:
                sensitivity_rows.append(
                    {
                        **binding,
                        "noise_scale": noise_scale,
                        "parameter": name,
                        "lift": _parameter_lift(name),
                        "unit": units[name],
                        "n_total": len(test_ids),
                        "n_paired_posteriors": 0,
                        "posterior_mean_difference_beta8_minus_uniform": None,
                        "mean_difference_ci95_low": None,
                        "mean_difference_ci95_high": None,
                        "uniform_mean_interval_width": None,
                        "beta8_mean_interval_width": None,
                        "uniform_coverage_95": None,
                        "beta8_coverage_95": None,
                        "status": "NOT_DEFINED_NOISE_FREE_POSTERIOR",
                    }
                )
                continue
            paired: list[tuple[float, float, float, bool, bool]] = []
            for entity_id in test_ids:
                uniform = posterior_by_key[(entity_id, noise_scale, "uniform")]
                beta8 = posterior_by_key[(entity_id, noise_scale, "beta8")]
                if (
                    uniform.get("status") != "LAPLACE_APPROXIMATION_VALID"
                    or beta8.get("status") != "LAPLACE_APPROXIMATION_VALID"
                ):
                    continue
                uniform_record = summaries(uniform)[name]
                beta_record = summaries(beta8)[name]
                truth_values, _ = _parameter_true_values(truth_by_id[entity_id])
                truth = truth_values[name]
                uniform_covered = (
                    float(uniform_record["lower_95"]) <= truth <= float(uniform_record["upper_95"])
                )
                beta_covered = (
                    float(beta_record["lower_95"]) <= truth <= float(beta_record["upper_95"])
                )
                paired.append(
                    (
                        float(beta_record["mean"]) - float(uniform_record["mean"]),
                        float(uniform_record["upper_95"]) - float(uniform_record["lower_95"]),
                        float(beta_record["upper_95"]) - float(beta_record["lower_95"]),
                        uniform_covered,
                        beta_covered,
                    )
                )
            differences = [row[0] for row in paired]
            lower, upper = _mean_interval(
                differences,
                _seed_for_key(["parameter-prior-sensitivity", noise_scale, name]),
            )
            sensitivity_rows.append(
                {
                    **binding,
                    "noise_scale": noise_scale,
                    "parameter": name,
                    "lift": _parameter_lift(name),
                    "unit": units[name],
                    "n_total": len(test_ids),
                    "n_paired_posteriors": len(paired),
                    "posterior_mean_difference_beta8_minus_uniform": float(np.mean(differences))
                    if differences
                    else None,
                    "mean_difference_ci95_low": lower,
                    "mean_difference_ci95_high": upper,
                    "uniform_mean_interval_width": float(np.mean([row[1] for row in paired]))
                    if paired
                    else None,
                    "beta8_mean_interval_width": float(np.mean([row[2] for row in paired]))
                    if paired
                    else None,
                    "uniform_coverage_95": float(np.mean([row[3] for row in paired]))
                    if paired
                    else None,
                    "beta8_coverage_95": float(np.mean([row[4] for row in paired]))
                    if paired
                    else None,
                    "status": "COMPLETE"
                    if len(paired) == len(test_ids)
                    else "PARTIAL_POSTERIOR_FAILURES_RETAINED"
                    if paired
                    else "NO_PAIRED_POSTERIOR_INTERVALS",
                }
            )
    return summary_rows, sensitivity_rows


def _build_paired_comparisons(
    estimate_rows: Sequence[Mapping[str, Any]], binding: Mapping[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        contrast_id: str,
        left_estimator: str,
        left_prior: str,
        left_noise: float,
        right_estimator: str,
        right_prior: str,
        right_noise: float,
        targets: Sequence[str],
    ) -> None:
        for target in targets:
            for lift in LIFTS:
                rows.append(
                    _paired_metric_row(
                        estimate_rows,
                        binding,
                        contrast_id=contrast_id,
                        left_estimator=left_estimator,
                        left_prior=left_prior,
                        left_noise=left_noise,
                        right_estimator=right_estimator,
                        right_prior=right_prior,
                        right_noise=right_noise,
                        target=target,
                        lift=lift,
                    )
                )

    for noise_scale in NOISE_SCALES:
        add(
            "full_minus_reduced_p223",
            ESTIMATOR_IDS["full"],
            "none",
            noise_scale,
            ESTIMATOR_IDS["reduced"],
            "none",
            noise_scale,
            ("P_223_kg",),
        )
        add(
            "hybrid_minus_full_deltaC56",
            ESTIMATOR_IDS["hybrid"],
            "none",
            noise_scale,
            ESTIMATOR_IDS["full"],
            "none",
            noise_scale,
            ("DeltaC_56_kg",),
        )
        if noise_scale > 0:
            add(
                "uniform_bayes_minus_full",
                ESTIMATOR_IDS["bayesian"],
                "uniform",
                noise_scale,
                ESTIMATOR_IDS["full"],
                "none",
                noise_scale,
                TARGET_NAMES,
            )
            add(
                "beta8_bayes_minus_uniform_bayes",
                ESTIMATOR_IDS["bayesian"],
                "beta8",
                noise_scale,
                ESTIMATOR_IDS["bayesian"],
                "uniform",
                noise_scale,
                TARGET_NAMES,
            )
    for target in TARGET_NAMES:
        add(
            "full_noise2_minus_noise1",
            ESTIMATOR_IDS["full"],
            "none",
            2.0,
            ESTIMATOR_IDS["full"],
            "none",
            1.0,
            (target,),
        )
        add(
            "full_noise1_minus_noise0",
            ESTIMATOR_IDS["full"],
            "none",
            1.0,
            ESTIMATOR_IDS["full"],
            "none",
            0.0,
            (target,),
        )
    return rows


def _history_sensitivity_rows(
    estimate_rows: Sequence[Mapping[str, Any]], binding: Mapping[str, str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, int, str, str], list[Mapping[str, Any]]] = {}
    for row in estimate_rows:
        key = (
            str(row["estimator_id"]),
            float(row["noise_scale"]),
            int(row["history_template"]),
            str(row["target"]),
            str(row["lift"]),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        estimator_id, noise_scale, template, target, lift = key
        scored = [row for row in rows if row["estimate"] is not None]
        errors = [float(row["estimate"]) - float(row["truth"]) for row in scored]
        output.append(
            {
                **binding,
                "estimator_id": estimator_id,
                "noise_scale": noise_scale,
                "history_template": template,
                "target": target,
                "lift": lift,
                "unit": _target_units()[target],
                "n_total": len(rows),
                "n_scored": len(scored),
                "rmse": math.sqrt(float(np.mean(np.square(errors)))) if errors else None,
                "mae": float(np.mean(np.abs(errors))) if errors else None,
                "signed_bias": float(np.mean(errors)) if errors else None,
                "status": "COMPLETE_WITH_NONCONVERGED_FITS_RETAINED"
                if len(scored) == len(rows)
                and any("NONCONVERGED" in str(row["status"]) for row in scored)
                else "COMPLETE_MAP_ONLY_POSTERIOR_FAILURE_RETAINED"
                if len(scored) == len(rows)
                and any(str(row["status"]).startswith("MAP_ONLY") for row in scored)
                else "COMPLETE"
                if len(scored) == len(rows)
                else "PARTIAL_FAILURES_RETAINED"
                if scored
                else "NO_VALID_ESTIMATES",
            }
        )
    return output


def _equivalent_solutions(
    inputs_by_key: Mapping[tuple[str, float], StudyInputs],
    full_fits: Mapping[tuple[str, float], FitResult],
    binding: Mapping[str, str],
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for key, fit in sorted(full_fits.items()):
        entity_id, noise_scale = key
        candidates = [
            row for row in fit.starts if row["eligible_final"] and row["coordinates"] is not None
        ]
        for left_index in range(len(candidates)):
            left = candidates[left_index]
            left_coordinates = np.asarray(left["coordinates"], dtype=np.float64)
            left_output = model_with_jacobian(
                left_coordinates, inputs_by_key[key].schedule_products
            ).history_performance
            for right in candidates[left_index + 1 :]:
                right_coordinates = np.asarray(right["coordinates"], dtype=np.float64)
                objective_difference = abs(float(left["objective"]) - float(right["objective"]))
                coordinate_distance = float(np.max(np.abs(left_coordinates - right_coordinates)))
                if coordinate_distance <= EQUIVALENCE_COORDINATE_DISTANCE:
                    continue
                right_output = model_with_jacobian(
                    right_coordinates, inputs_by_key[key].schedule_products
                ).history_performance
                history_rmse = math.sqrt(float(np.mean(np.square(left_output - right_output))))
                if (
                    objective_difference <= EQUIVALENCE_OBJECTIVE_TOLERANCE
                    and history_rmse <= EQUIVALENCE_HISTORY_RMSE_KG
                ):
                    found.append(
                        {
                            **binding,
                            "entity_id": entity_id,
                            "noise_scale": noise_scale,
                            "start_a": left["start_index"],
                            "start_b": right["start_index"],
                            "objective_difference": objective_difference,
                            "history_rmse_kg": history_rmse,
                            "max_coordinate_difference": coordinate_distance,
                            "status": "OBSERVATIONAL_EQUIVALENCE_CANDIDATE",
                        }
                    )
    return found


def _compute_cost_rows(
    optimizer_rows: Sequence[Mapping[str, Any]],
    posterior_rows: Sequence[Mapping[str, Any]],
    binding: Mapping[str, str],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float], list[Mapping[str, Any]]] = {}
    for row in optimizer_rows:
        key = (str(row["estimator_id"]), str(row["prior"]), float(row["noise_scale"]))
        groups.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    posterior_groups: dict[tuple[str, float], list[Mapping[str, Any]]] = {}
    for row in posterior_rows:
        posterior_key = (str(row["prior"]), float(row["noise_scale"]))
        posterior_groups.setdefault(posterior_key, []).append(row)
    all_groups = set(groups) | {
        (ESTIMATOR_IDS["bayesian"], prior, noise_scale) for prior, noise_scale in posterior_groups
    }
    for noise_scale in NOISE_SCALES:
        all_groups.add((ESTIMATOR_IDS["reduced"], "none", noise_scale))
        all_groups.add((ESTIMATOR_IDS["hybrid"], "none", noise_scale))
    for estimator_id, prior, noise_scale in sorted(all_groups):
        rows = groups.get((estimator_id, prior, noise_scale), [])
        posterior_group = posterior_groups.get((prior, noise_scale), [])
        full_rows = groups.get((ESTIMATOR_IDS["full"], "none", noise_scale), [])
        if estimator_id == ESTIMATOR_IDS["bayesian"] and prior == "uniform":
            shared_rows = [row for row in full_rows if row["split"] == "test"]
        elif estimator_id == ESTIMATOR_IDS["hybrid"]:
            shared_rows = full_rows
        else:
            shared_rows = []
        solver_model_evaluations = sum(int(row["model_evaluations"]) for row in rows)
        shared_model_evaluations = sum(int(row["model_evaluations"]) for row in shared_rows)
        hessian_evaluations = sum(
            int(row["hessian_gradient_evaluations"] or 0) for row in posterior_group
        )
        posterior_draws = sum(int(row["accepted_draws"] or 0) for row in posterior_group)
        total_model_evaluations = (
            solver_model_evaluations
            + shared_model_evaluations
            + hessian_evaluations
            + posterior_draws
        )
        output.append(
            {
                **binding,
                "estimator_id": estimator_id,
                "prior": prior,
                "noise_scale": noise_scale,
                "solver_starts": len(rows),
                "solver_function_evaluations": sum(
                    int(row["function_evaluations"]) for row in rows
                ),
                "solver_gradient_evaluations": sum(
                    int(row["gradient_evaluations"]) for row in rows
                ),
                "solver_model_evaluations": solver_model_evaluations,
                "shared_full_fit_model_evaluations": shared_model_evaluations,
                "posterior_candidate_batches": sum(
                    int(row["candidate_batches"] or 0) for row in posterior_group
                ),
                "posterior_draws": posterior_draws,
                "posterior_hessian_gradient_evaluations": hessian_evaluations,
                "residual_fit_rows": DEVELOPMENT_COUNT * len(LIFTS)
                if estimator_id == ESTIMATOR_IDS["hybrid"]
                else 0,
                "direct_observation_reads": DEVELOPMENT_COUNT * len(LIFTS)
                if estimator_id == ESTIMATOR_IDS["reduced"]
                else 0,
                "daily_state_transition_equivalents": total_model_evaluations
                * len(LIFTS)
                * (LAST_DAY + 1),
                "compute_measure": "Own plus explicitly shared model passes, Hessian-gradient calls, and posterior draws; each pass counts three lifts × 280 days; no wall-clock comparison.",
            }
        )
    return output


def _negative_result_rows(
    identifiability: Mapping[str, Any],
    experiment_outputs: Mapping[str, bytes],
    binding: Mapping[str, str],
) -> list[dict[str, Any]]:
    optimizer_rows = list(
        csv.DictReader(io.StringIO(experiment_outputs["optimizer-diagnostics.csv"].decode()))
    )
    posterior_rows = list(
        csv.DictReader(io.StringIO(experiment_outputs["posterior-diagnostics.csv"].decode()))
    )
    paired_rows = list(
        csv.DictReader(io.StringIO(experiment_outputs["paired-comparisons.csv"].decode()))
    )
    records: list[dict[str, Any]] = []

    def add(result_id: str, claim: str, status: str, evidence: str, limit: str) -> None:
        records.append(
            {
                **binding,
                "result_id": result_id,
                "claim": claim,
                "status": status,
                "evidence": evidence,
                "interpretation_limit": limit,
            }
        )

    add(
        "G2-HISTORICAL-RESULTS",
        "Original G2 measurements, protocol, fitted models, and quantitative results",
        "UNSUPPORTED_BY_EVIDENCE",
        "studies/target_sufficient_structural_reconstruction/historical-lineage.md",
        "No historical G2 result is reconstructed or claimed; the public-native realization is separate.",
    )
    add(
        "SINGLE-TIME-STATE-RANK",
        "One-time assessment/load/velocity channels identify both free A and R states",
        "COUNTEREXAMPLE_TO_LOCAL_IDENTIFICATION",
        "identifiability.json: single_time_latent_rank.maximum_rank",
        "All channels factor through P; complete known-parameter histories are a different question.",
    )
    constant = identifiability["constant_input_equivalence"]
    add(
        "CONSTANT-INPUT-REFERENCE-SYMMETRY",
        "The 0.6 constant-input design uniquely identifies reference stimulus and hidden states",
        str(constant["equivalence_status"]),
        "identifiability.json: constant_input_equivalence",
        "This exact counterexample is outside the four canonical history templates.",
    )
    add(
        "CANONICAL-TEMPLATE-GLOBAL-IDENTIFICATION",
        "Full local rank or finite multistart results establish global uniqueness on canonical histories",
        str(identifiability["native_template_global_identification"]),
        "identifiability.json plus equivalent-solutions.csv",
        "No global proof is made; no found counterexample leaves the claim inconclusive.",
    )
    add(
        "NATIVE-INITIAL-STATE",
        "Free-initial-state observability conclusions transfer to this native system",
        "PROHIBITED_TRANSFER",
        "formal-specification.md: native A[-1]=R[-1]=0",
        "The native state starts at zero; RES-287's free-state extension remains separate.",
    )
    add(
        "NOISE-FREE-BAYESIAN-POSTERIOR",
        "A zero-noise deterministic likelihood supports a regular finite-width posterior",
        "NOT_DEFINED_NOISE_FREE_POSTERIOR",
        "posterior-diagnostics.csv",
        "No artificial observation-noise floor is added.",
    )
    add(
        "REDUCED-ESTIMATOR-SCOPE",
        "The reduced estimate of P_223 also recovers C, A, R, or parameters",
        "NOT_ESTIMATED_BY_METHOD",
        "target-results.csv and parameter-results.csv",
        "The reduced method targets only the latest-observation expressed-performance functional.",
    )
    add(
        "HYBRID-STRUCTURAL-RECOVERY",
        "A learned residual changes latent-state or parameter recovery",
        "UNCHANGED_BY_CONSTRUCTION",
        "parameter-errors.csv and target-estimates.csv",
        "The hybrid copies full structural states and parameters and changes only DeltaC_56.",
    )
    infeasible_starts = sum(row["eligible_final"].lower() != "true" for row in optimizer_rows)
    nonconverged = sum(row["status"] == "NONCONVERGED_FEASIBLE" for row in optimizer_rows)
    add(
        "OPTIMIZER-FAILURE-PRESERVATION",
        "Every declared bounded optimization start converged to a feasible solution",
        "NO_FAILURES" if infeasible_starts == 0 and nonconverged == 0 else "FAILURES_RETAINED",
        "optimizer-diagnostics.csv",
        f"{infeasible_starts} infeasible final starts and {nonconverged} feasible nonconverged starts are retained.",
    )
    noisy_posterior_rows = [row for row in posterior_rows if float(row["noise_scale"]) > 0]
    posterior_failures = sum(
        row["status"] != "LAPLACE_APPROXIMATION_VALID" for row in noisy_posterior_rows
    )
    add(
        "POSTERIOR-DIAGNOSTIC-FAILURES",
        "Every noisy posterior passed the declared interior-mode, Hessian, conditioning, and draw checks",
        "NO_FAILURES" if posterior_failures == 0 else "FAILURES_RETAINED",
        "posterior-diagnostics.csv and posterior-summaries.jsonl",
        f"{posterior_failures} noisy posterior rows are not valid Laplace approximations; the 64 noise-free undefined-posterior rows are excluded. Uncertainty claims use only valid rows and report denominators.",
    )
    for row in paired_rows:
        if row["contrast_id"] != "hybrid_minus_full_deltaC56":
            continue
        low = row["rmse_difference_ci95_low"]
        high = row["rmse_difference_ci95_high"]
        if low == "" or high == "":
            state = "NO_PAIRED_ESTIMATES"
        elif float(low) < 0 < float(high):
            state = "INCONCLUSIVE_INTERVAL_SPANS_ZERO"
        elif float(high) < 0:
            state = "HYBRID_LOWER_TEST_RMSE_IN_THIS_CONDITION"
        else:
            state = "HYBRID_HIGHER_TEST_RMSE_IN_THIS_CONDITION"
        add(
            f"RESIDUAL-{row['noise_scale_a']}-{row['lift']}",
            "The bounded residual improves held-out DeltaC_56 prediction without implying structural recovery",
            state,
            "paired-comparisons.csv: hybrid_minus_full_deltaC56",
            "Entity-bootstrap uncertainty is limited to this realization; latent states and parameters are inherited from full fitting.",
        )
    return records


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:.{digits}f}"


def _markdown_table(rows: Sequence[Sequence[Any]]) -> str:
    if not rows:
        return "(no valid rows)"
    header = "| " + " | ".join(str(value) for value in rows[0]) + " |"
    rule = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ["| " + " | ".join(str(value) for value in row) + " |" for row in rows[1:]]
    return "\n".join([header, rule, *body])


def _read_csv_bytes(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"))))


def _error_figure(metrics: Sequence[Mapping[str, str]]) -> bytes:
    lifts = LIFTS
    targets = ("P_223_kg", "C_223_kg", "DeltaC_56_kg")
    methods = (
        (ESTIMATOR_IDS["reduced"], "Reduced", "#3569a8"),
        (ESTIMATOR_IDS["full"], "Full MLE", "#c6534b"),
        (ESTIMATOR_IDS["bayesian"], "Bayes U", "#5a9c6e"),
        (ESTIMATOR_IDS["bayesian"], "Bayes B8", "#8872b2"),
        (ESTIMATOR_IDS["hybrid"], "Hybrid", "#d18f34"),
    )
    width, height = 1260, 900
    panel_w, panel_h = 400, 290
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="630" y="34" text-anchor="middle" font-size="22" font-family="sans-serif">Test RMSE by target, lift, and method (noise scale 1)</text>',
        '<text x="630" y="58" text-anchor="middle" font-size="13" font-family="sans-serif">Separate panels preserve the distinction between expressed performance, capacity, and capacity change; units are kg.</text>',
    ]
    for target_index, target in enumerate(targets):
        for lift_index, lift in enumerate(lifts):
            x0 = 35 + lift_index * panel_w
            y0 = 85 + target_index * panel_h
            subset = [
                row
                for row in metrics
                if row["target"] == target and row["lift"] == lift and row["noise_scale"] == "1.0"
            ]
            values: list[tuple[str, str, str, float]] = []
            for method_id, label, color in methods:
                prior = (
                    "none"
                    if label in {"Reduced", "Full MLE", "Hybrid"}
                    else ("uniform" if label == "Bayes U" else "beta8")
                )
                row = next(
                    (
                        item
                        for item in subset
                        if item["estimator_id"] == method_id and item["prior"] == prior
                    ),
                    None,
                )
                if row and row["rmse"]:
                    values.append((label, color, row["rmse_ci95_low"], float(row["rmse"])))
            maximum = max((item[3] for item in values), default=1.0) * 1.2
            elements.extend(
                [
                    f'<rect x="{x0}" y="{y0}" width="370" height="240" fill="#fafafa" stroke="#ccc"/>',
                    f'<text x="{x0 + 185}" y="{y0 + 22}" text-anchor="middle" font-size="16" font-family="sans-serif">{html_escape(target)} · {html_escape(lift)}</text>',
                ]
            )
            for grid_index in range(4):
                y = y0 + 52 + grid_index * 48
                value = maximum * (1.0 - grid_index / 3.0)
                elements.append(
                    f'<line x1="{x0 + 48}" y1="{y}" x2="{x0 + 355}" y2="{y}" stroke="#ddd"/><text x="{x0 + 42}" y="{y + 4}" text-anchor="end" font-size="10" font-family="sans-serif">{value:.2f}</text>'
                )
            for method_index, (method_id, label, color) in enumerate(methods):
                row = next(
                    (
                        item
                        for item in subset
                        if item["estimator_id"] == method_id
                        and item["prior"]
                        == (
                            "none"
                            if label in {"Reduced", "Full MLE", "Hybrid"}
                            else "uniform"
                            if label == "Bayes U"
                            else "beta8"
                        )
                    ),
                    None,
                )
                xx = x0 + 66 + method_index * 58
                if row and row["rmse"]:
                    yy = y0 + 52 + (1.0 - float(row["rmse"]) / maximum) * 144
                    elements.append(f'<circle cx="{xx}" cy="{yy}" r="6" fill="{color}"/>')
                else:
                    elements.append(
                        f'<text x="{xx}" y="{y0 + 205}" text-anchor="middle" font-size="9" fill="#777" font-family="sans-serif">n/a</text>'
                    )
                elements.append(
                    f'<text x="{xx}" y="{y0 + 224}" text-anchor="middle" font-size="9" fill="{color}" font-family="sans-serif">{html_escape(label)}</text>'
                )
    elements.append("</svg>")
    return ("\n".join(elements) + "\n").encode("utf-8")


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _identifiability_figure(identifiability: Mapping[str, Any]) -> bytes:
    designs = [
        row
        for row in identifiability["jacobian_methods"]
        if row["design"].startswith("canonical-template") or row["design"].startswith("zero-input")
    ]
    labels = [str(row["design"]) for row in designs]
    series = [row["steps"][-1]["singular_values"] for row in designs]
    width, height = 920, 520
    plot_x, plot_y, plot_w, plot_h = 90, 62, 790, 360
    colors = ("#3569a8", "#c6534b", "#5a9c6e", "#8872b2", "#333333")
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="460" y="30" text-anchor="middle" font-size="20" font-family="sans-serif">Native-history local Jacobian singular spectra</text>',
        '<text x="460" y="49" text-anchor="middle" font-size="12" font-family="sans-serif">Midpoint, 16 normalized coordinates, 96 weekly P outputs; low-excitation design is outside canonical templates.</text>',
    ]
    ymin, ymax = -12.0, 0.0
    for tick in range(0, 13, 2):
        y = plot_y + plot_h * tick / 12
        elements.append(
            f'<line x1="{plot_x}" y1="{y}" x2="{plot_x + plot_w}" y2="{y}" stroke="#ddd"/><text x="{plot_x - 8}" y="{y + 4}" text-anchor="end" font-size="10" font-family="sans-serif">10^-{tick}</text>'
        )
    rank_y = plot_y + plot_h * (-(math.log10(JACOBIAN_RANK_TOLERANCE)) / (ymax - ymin))
    elements.append(
        f'<line x1="{plot_x}" y1="{rank_y}" x2="{plot_x + plot_w}" y2="{rank_y}" stroke="#555" stroke-dasharray="5,4"/>'
    )
    for series_index, values in enumerate(series):
        normalized = np.asarray(values, dtype=np.float64) / float(values[0])
        points = []
        for index, value in enumerate(normalized):
            log_value = max(ymin, math.log10(max(float(value), 1e-15)))
            x = plot_x + plot_w * index / (len(values) - 1)
            y = plot_y + plot_h * (ymax - log_value) / (ymax - ymin)
            points.append(f"{x:.2f},{y:.2f}")
        elements.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[series_index]}" stroke-width="2"/>'
        )
        elements.append(
            f'<text x="{plot_x + 18 + series_index * 170}" y="{height - 24}" font-size="11" fill="{colors[series_index]}" font-family="sans-serif">{html_escape(labels[series_index])}</text>'
        )
    elements.append(
        f'<text x="{plot_x + plot_w / 2}" y="{height - 5}" text-anchor="middle" font-size="11" font-family="sans-serif">Singular mode (normalized by largest)</text>'
    )
    elements.append("</svg>")
    return ("\n".join(elements) + "\n").encode("utf-8")


def _posterior_coverage_figure(posterior_rows: Sequence[Mapping[str, str]]) -> bytes:
    rows = [
        row for row in posterior_rows if row["prior"] == "uniform" and row["noise_scale"] == "1.0"
    ]
    width, height = 1180, 590
    plot_x, plot_y, plot_w, plot_h = 120, 58, 1020, 430
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="590" y="28" text-anchor="middle" font-size="20" font-family="sans-serif">Uniform-prior Laplace interval coverage (noise scale 1)</text>',
        '<text x="590" y="47" text-anchor="middle" font-size="12" font-family="sans-serif">Coverage is descriptive on this 32-entity synthetic test split; valid-posterior denominator is reported in posterior-results.csv.</text>',
    ]
    for tick in range(0, 6):
        y = plot_y + plot_h * (1.0 - tick / 5.0)
        elements.append(
            f'<line x1="{plot_x}" y1="{y}" x2="{plot_x + plot_w}" y2="{y}" stroke="#ddd"/><text x="{plot_x - 10}" y="{y + 4}" text-anchor="end" font-size="10" font-family="sans-serif">{tick / 5:.1f}</text>'
        )
    nominal_y = plot_y + plot_h * (1.0 - 0.95)
    elements.append(
        f'<line x1="{plot_x}" y1="{nominal_y}" x2="{plot_x + plot_w}" y2="{nominal_y}" stroke="#333" stroke-dasharray="5,4"/>'
    )
    total = len(rows)
    bar_w = plot_w / max(total, 1) * 0.56
    for index, row in enumerate(rows):
        x = plot_x + (index + 0.5) * plot_w / total
        if row["coverage_95"]:
            coverage = min(1.0, max(0.0, float(row["coverage_95"])))
            y = plot_y + plot_h * (1.0 - coverage)
            color = "#4c7f6c" if row["status"] == "COMPLETE" else "#c48b3a"
            elements.append(
                f'<rect x="{x - bar_w / 2}" y="{y}" width="{bar_w}" height="{plot_y + plot_h - y}" fill="{color}"/>'
            )
        else:
            elements.append(
                f'<text x="{x}" y="{plot_y + plot_h - 8}" text-anchor="middle" font-size="8" fill="#777" font-family="sans-serif">n/a</text>'
            )
        elements.append(
            f'<text x="{x}" y="{plot_y + plot_h + 18}" transform="rotate(45 {x} {plot_y + plot_h + 18})" font-size="9" font-family="sans-serif">{html_escape(row["lift"] + ":" + row["target"])}</text>'
        )
    elements.append("</svg>")
    return ("\n".join(elements) + "\n").encode("utf-8")


def _target_markdown_table(
    rows: Sequence[Mapping[str, str]], target: str, noise_scale: float
) -> str:
    selected = [
        row for row in rows if row["target"] == target and float(row["noise_scale"]) == noise_scale
    ]
    output: list[list[str]] = [
        ["Method", "Lift", "n", "RMSE", "95% bootstrap interval", "MAE", "Bias", "Status"]
    ]
    for method_id, method_name, prior in (
        (ESTIMATOR_IDS["reduced"], "Reduced", "none"),
        (ESTIMATOR_IDS["full"], "Full MLE", "none"),
        (ESTIMATOR_IDS["bayesian"], "Bayes uniform", "uniform"),
        (ESTIMATOR_IDS["bayesian"], "Bayes Beta(8,8)", "beta8"),
        (ESTIMATOR_IDS["hybrid"], "Structural + residual", "none"),
    ):
        for lift in LIFTS:
            row = next(
                (
                    item
                    for item in selected
                    if item["estimator_id"] == method_id
                    and item["prior"] == prior
                    and item["lift"] == lift
                ),
                None,
            )
            if row is None:
                continue
            interval = (
                f"[{_fmt(row['rmse_ci95_low'])}, {_fmt(row['rmse_ci95_high'])}]"
                if row["rmse_ci95_low"] and row["rmse_ci95_high"]
                else "—"
            )
            output.append(
                [
                    method_name,
                    lift,
                    f"{row['n_scored']}/{row['n_total']}",
                    _fmt(row["rmse"]),
                    interval,
                    _fmt(row["mae"]),
                    _fmt(row["signed_bias"]),
                    row["status"],
                ]
            )
    return _markdown_table(output)


def _report_text(
    experiment_outputs: Mapping[str, bytes],
    identity: Mapping[str, Any],
    identifiability: Mapping[str, Any],
    negative_rows: Sequence[Mapping[str, Any]],
) -> str:
    target_metrics = _read_csv_bytes(experiment_outputs["target-results.csv"])
    parameter_metrics = _read_csv_bytes(experiment_outputs["parameter-results.csv"])
    posterior_metrics = _read_csv_bytes(experiment_outputs["posterior-results.csv"])
    prior_rows = _read_csv_bytes(experiment_outputs["prior-sensitivity.csv"])
    paired_rows = _read_csv_bytes(experiment_outputs["paired-comparisons.csv"])
    cost_rows = _read_csv_bytes(experiment_outputs["compute-cost.csv"])
    estimate_rows = _read_csv_bytes(experiment_outputs["target-estimates.csv"])
    optimizer_rows = _read_csv_bytes(experiment_outputs["optimizer-diagnostics.csv"])
    posterior_diagnostics = _read_csv_bytes(experiment_outputs["posterior-diagnostics.csv"])
    ident_rows = identifiability["jacobian_methods"]

    current_capacity = [["Method", "Lift", "n", "RMSE (kg)", "95% entity bootstrap (kg)", "Status"]]
    for row in target_metrics:
        if row["target"] != "C_223_kg" or row["noise_scale"] != "1.0":
            continue
        label = (
            "Reduced"
            if row["estimator_id"] == ESTIMATOR_IDS["reduced"]
            else "Full MLE"
            if row["estimator_id"] == ESTIMATOR_IDS["full"]
            else "Bayes uniform"
            if row["prior"] == "uniform"
            else "Bayes Beta(8,8)"
            if row["prior"] == "beta8"
            else "Structural + residual"
        )
        interval = (
            f"[{_fmt(row['rmse_ci95_low'])}, {_fmt(row['rmse_ci95_high'])}]"
            if row["rmse_ci95_low"] and row["rmse_ci95_high"]
            else "—"
        )
        current_capacity.append(
            [
                label,
                row["lift"],
                row["n_scored"] + "/" + row["n_total"],
                _fmt(row["rmse"]),
                interval,
                row["status"],
            ]
        )

    state_rows = [["Estimator", "Prior", "Noise", "Target", "Lift", "n", "RMSE", "Unit", "Status"]]
    for row in target_metrics:
        if row["target"] not in ("A_223", "R_223"):
            continue
        if row["estimator_id"] not in (ESTIMATOR_IDS["full"], ESTIMATOR_IDS["bayesian"]):
            continue
        label = "Full MLE" if row["estimator_id"] == ESTIMATOR_IDS["full"] else "Bayesian"
        state_rows.append(
            [
                label,
                row["prior"],
                row["noise_scale"],
                row["target"],
                row["lift"],
                row["n_scored"] + "/" + row["n_total"],
                _fmt(row["rmse"]),
                row["unit"],
                row["status"],
            ]
        )

    parameter_rows = [
        ["Estimator", "Prior", "Noise", "Parameter", "Lift", "n", "RMSE", "Unit", "Status"]
    ]
    for row in parameter_metrics:
        if row["noise_scale"] != "1.0":
            continue
        if row["estimator_id"] not in (ESTIMATOR_IDS["full"], ESTIMATOR_IDS["bayesian"]):
            continue
        label = "Full MLE" if row["estimator_id"] == ESTIMATOR_IDS["full"] else "Bayesian"
        parameter_rows.append(
            [
                label,
                row["prior"],
                row["noise_scale"],
                row["parameter"],
                row["lift"],
                row["n_scored"] + "/" + row["n_total"],
                _fmt(row["rmse"]),
                row["unit"],
                row["status"],
            ]
        )

    noise_free_parameter_rows = [["Estimator", "Parameter", "Lift", "n", "RMSE", "Unit", "Status"]]
    for row in parameter_metrics:
        if row["noise_scale"] != "0.0" or row["estimator_id"] != ESTIMATOR_IDS["full"]:
            continue
        noise_free_parameter_rows.append(
            [
                "Full MLE",
                row["parameter"],
                row["lift"],
                row["n_scored"] + "/" + row["n_total"],
                _fmt(row["rmse"], 8),
                row["unit"],
                row["status"],
            ]
        )

    posterior_table = [
        ["Prior", "Target", "Lift", "Valid / total", "95% coverage", "Mean width", "Status"]
    ]
    for row in posterior_metrics:
        if row["noise_scale"] != "1.0":
            continue
        posterior_table.append(
            [
                row["prior"],
                row["target"],
                row["lift"],
                row["n_valid_posterior"] + "/" + row["n_total"],
                _fmt(row["coverage_95"], 3),
                _fmt(row["mean_interval_width"]),
                row["status"],
            ]
        )

    noisy_posterior_counts = Counter(
        (row["prior"], row["status"])
        for row in posterior_diagnostics
        if row["noise_scale"] in ("1.0", "2.0")
    )
    uniform_valid_count = sum(
        count
        for (prior, status), count in noisy_posterior_counts.items()
        if prior == "uniform" and status == "LAPLACE_APPROXIMATION_VALID"
    )
    uniform_boundary_count = noisy_posterior_counts.get(("uniform", "POSTERIOR_BOUNDARY_MODE"), 0)
    beta_valid_count = sum(
        count
        for (prior, status), count in noisy_posterior_counts.items()
        if prior == "beta8" and status == "LAPLACE_APPROXIMATION_VALID"
    )

    prior_table = [
        [
            "Noise",
            "Target",
            "Lift",
            "n",
            "Mean Δ Beta−Uniform",
            "95% paired CI",
            "Width U/B",
            "Coverage U/B",
            "Status",
        ]
    ]
    for row in prior_rows:
        if row["noise_scale"] not in ("1.0", "2.0"):
            continue
        ci = (
            f"[{_fmt(row['mean_difference_ci95_low'])}, {_fmt(row['mean_difference_ci95_high'])}]"
            if row["mean_difference_ci95_low"] and row["mean_difference_ci95_high"]
            else "—"
        )
        prior_table.append(
            [
                row["noise_scale"],
                row["target"],
                row["lift"],
                row["n_paired_posteriors"] + "/" + row["n_total"],
                _fmt(row["posterior_mean_difference_beta8_minus_uniform"]),
                ci,
                f"{_fmt(row['uniform_mean_interval_width'])}/{_fmt(row['beta8_mean_interval_width'])}",
                f"{_fmt(row['uniform_coverage_95'], 3)}/{_fmt(row['beta8_coverage_95'], 3)}",
                row["status"],
            ]
        )

    residual_table = [
        ["Noise", "Lift", "n paired", "Hybrid − full RMSE", "95% entity bootstrap", "Status"]
    ]
    for row in paired_rows:
        if row["contrast_id"] != "hybrid_minus_full_deltaC56":
            continue
        ci = (
            f"[{_fmt(row['rmse_difference_ci95_low'])}, {_fmt(row['rmse_difference_ci95_high'])}]"
            if row["rmse_difference_ci95_low"] and row["rmse_difference_ci95_high"]
            else "—"
        )
        residual_table.append(
            [
                row["noise_scale_a"],
                row["lift"],
                row["n_paired"] + "/" + row["n_total"],
                _fmt(row["paired_rmse_difference_a_minus_b"]),
                ci,
                row["status"],
            ]
        )

    ident_table = [["Input design", "Local rank / 16", "Condition number", "Refinement"]]
    for row in ident_rows:
        step_record = row["steps"][-1]
        rank_text = f"{step_record['rank']} / {step_record['parameter_count']}"
        ident_table.append(
            [
                row["design"],
                rank_text,
                _fmt(step_record["condition_number_full_rank_only"], 2),
                _fmt(row.get("relative_singular_spectrum_refinement")),
            ]
        )

    convergence_table = [
        [
            "Estimator",
            "Prior",
            "Noise",
            "Converged starts",
            "Nonconverged starts",
            "Infeasible starts",
            "Test selected-fit statuses",
        ]
    ]
    optimizer_groups: dict[tuple[str, str, str], list[Mapping[str, str]]] = {}
    for row in optimizer_rows:
        key = (row["estimator_id"], row["prior"], row["noise_scale"])
        optimizer_groups.setdefault(key, []).append(row)
    selected_fit_counts: dict[tuple[str, str], Counter[str]] = {}
    for row in estimate_rows:
        if (
            row["estimator_id"] == ESTIMATOR_IDS["full"]
            and row["target"] == "P_223_kg"
            and row["lift"] == "squat"
        ):
            selected_key = (row["noise_scale"], row["estimator_id"])
            selected_fit_counts.setdefault(selected_key, Counter())[row["status"]] += 1
    beta_map_counts: dict[str, Counter[str]] = {}
    for row in posterior_diagnostics:
        if row["prior"] == "beta8" and row["noise_scale"] in ("1.0", "2.0"):
            beta_map_counts.setdefault(row["noise_scale"], Counter())[row["map_fit_status"]] += 1
    for key, rows in sorted(optimizer_groups.items()):
        estimator_id, prior, noise_scale = key
        selected = (
            beta_map_counts.get(noise_scale, Counter())
            if prior == "beta8"
            else selected_fit_counts.get((noise_scale, ESTIMATOR_IDS["full"]), Counter())
        )
        convergence_table.append(
            [
                estimator_id,
                prior,
                noise_scale,
                str(sum(row["status"] == "CONVERGED" for row in rows)),
                str(sum(row["status"] == "NONCONVERGED_FEASIBLE" for row in rows)),
                str(sum(row["status"] == "INFEASIBLE_FINAL" for row in rows)),
                json.dumps(dict(selected), sort_keys=True),
            ]
        )

    noise_sensitivity_table = [
        ["Estimator", "Noise", "Target", "Lift", "n", "RMSE", "Unit", "Status"]
    ]
    for row in target_metrics:
        if row["estimator_id"] != ESTIMATOR_IDS["full"] or row["target"] not in (
            "P_223_kg",
            "C_223_kg",
            "DeltaC_56_kg",
        ):
            continue
        noise_sensitivity_table.append(
            [
                "Full MLE",
                row["noise_scale"],
                row["target"],
                row["lift"],
                row["n_scored"] + "/" + row["n_total"],
                _fmt(row["rmse"]),
                row["unit"],
                row["status"],
            ]
        )

    cost_table = [
        [
            "Estimator",
            "Prior",
            "Noise",
            "Starts",
            "Function evals",
            "Gradient evals",
            "Model passes",
            "Shared full passes",
            "Hessian grad evals",
            "Posterior draws",
            "Residual fit rows",
            "Direct observation reads",
            "Daily-state transition equivalents",
        ]
    ]
    for row in cost_rows:
        if (
            int(row["solver_starts"]) == 0
            and int(row["posterior_draws"]) == 0
            and int(row["residual_fit_rows"]) == 0
            and int(row["direct_observation_reads"]) == 0
        ):
            continue
        cost_table.append(
            [
                row["estimator_id"],
                row["prior"],
                row["noise_scale"],
                str(row["solver_starts"]),
                str(row["solver_function_evaluations"]),
                str(row["solver_gradient_evaluations"]),
                str(row["solver_model_evaluations"]),
                str(row["shared_full_fit_model_evaluations"]),
                str(row["posterior_hessian_gradient_evaluations"]),
                str(row["posterior_draws"]),
                str(row["residual_fit_rows"]),
                str(row["direct_observation_reads"]),
                str(row["daily_state_transition_equivalents"]),
            ]
        )

    negative_table = [["Finding", "State", "Evidence", "Limit"]]
    for negative_row in negative_rows:
        negative_table.append(
            [
                negative_row["claim"],
                negative_row["status"],
                negative_row["evidence"],
                negative_row["interpretation_limit"],
            ]
        )

    return f"""# Structural reconstruction and system identification

Study `{identity["study_id"]}`; frozen protocol `{identity["protocol_digest"]}`; public-native realization `{identity["realization_id"]}`; evaluation `{EVALUATION_ID}`. The [manifest](manifest.json) binds source, truth, observation, split, estimator, protocol, evaluation, and output identities. This is a new synthetic study, not a recovery of original G2 results.

## Historical G2 evidence

The surviving record verifies the G2 study name, retrospective purpose, and aliases `G2 / ALI-542` and `pl_study_g2_structural_reconstruction`. No rights-cleared original protocol, measurements, fitted models, uncertainty, or quantitative results survive. The old `PROVEN` marker is bootstrap metadata, not a scientific result. No original G2 result is invented or recomputed. See [historical-lineage.md](../../../studies/target_sufficient_structural_reconstruction/historical-lineage.md).

## Frozen design and evidence boundary

The protocol was frozen before the study realization was generated. It uses the known public M2 daily law and coordinate transforms, the native zero-initial-state assumption, four M3 weekly history templates, and the four declared future plans. It generated 64 independent entities with a 32-entity development set and a 32-entity held-out test set. All entities, schedules, and plans are matched across noise scales 0, 1, and 2. The native channels are preserved; all four estimator families use assessment history only, and the same declared schedules.

The three public observation channels share the same expressed-performance source. The structural fit uses the assessment marginal likelihood conditioned on the native accepted-load domain, including the sampled load-fraction overlap and `1/P` density term. Noise-free Bayesian uncertainty is reported as undefined. The frozen [formal specification](../../../studies/target_sufficient_structural_reconstruction/formal-specification.md) gives the likelihood, units, and identifiability claim boundaries.

M2 world identity: `{identity["world_id"]}`. M3 public-native DatasetSpec: `{identity["dataset_spec_id"]}`; canonical M3 evaluation: `{identity["canonical_m3_evaluation_id"]}`. RES-289's method-by-target evaluation is separate from M3/M4. M4 comparator scores remain forecasting evidence and do not measure latent-state or parameter recovery. M5 validity limitations remain in force.

## Structural identifiability

At one time, assessment, load, and velocity all factor through expressed performance `P`; the two free latent coordinates `A` and `R` therefore have instantaneous output rank at most one. The midpoint local finite-difference diagnostics use 96 weekly `P` outputs and 16 normalized coordinates. Full local rank, if observed, is only local sensitivity at the tested midpoint. The table and singular spectra below do not establish a global inverse.

{_markdown_table(ident_table)}

The constant continue design at dose-intensity product `0.6` is outside the four canonical history templates. Recomputing the reference-stimulus/gain transformation gives maximum `P` history difference `{_fmt(identifiability["constant_input_equivalence"]["maximum_performance_difference_kg"], 12)} kg`; adaptation and suppression states differ while `C` and `P` remain equal. This is an exact counterexample only for that constant-input design. RES-287's free-initial-state rest analysis is not transferred to the native `A[-1]=R[-1]=0` model. The finite native-template multistart search found `{identifiability["native_template_equivalent_solution_count"]}` candidate equivalent solution pairs; global identification on the canonical templates remains **{identifiability["native_template_global_identification"]}**.

## Numerical convergence and observation-noise sensitivity

The solver contract retains each best finite feasible result if none of its four starts converges. Such results are scored but explicitly marked; the entity bootstrap does not include optimization uncertainty. At native and doubled noise, most full-MLE starts did not meet the frozen convergence flag, so their point-error metrics are conditional on the retained finite fits and must be read with the failure counts below.

{_markdown_table(convergence_table)}

{_markdown_table(noise_sensitivity_table)}

![Midpoint local Jacobian spectra](identifiability-spectra.svg)

## Reconstruction results

The reduced estimator reports only the newest assessment as current expressed performance `P_223` in kilograms. It does not estimate `C`, `A`, `R`, dynamics, or future capacity change. The full fit estimates all 16 bounded coordinates under the known zero-state model. The Bayesian method reports a local Laplace approximation with Uniform and Beta(8,8) coordinate priors; the latter is a deliberately informative sensitivity prior, not a human population prior. The hybrid adds a development-only bounded Ridge residual for `DeltaC_56`; its other outputs and parameter estimates are inherited exactly from the full fit.

### Current expressed performance (`P_223`, kg), native noise

{_target_markdown_table(target_metrics, "P_223_kg", 1.0)}

### Current latent capacity (`C_223`, kg), native noise

{_markdown_table(current_capacity)}

### Future capacity change (`DeltaC_56`, kg), native noise

{_target_markdown_table(target_metrics, "DeltaC_56_kg", 1.0)}

![Test RMSE by target and lift](reconstruction-errors.svg)

State and parameter recovery are evaluated separately from prediction. The complete method-by-target state table is in [target-results.csv](target-results.csv). Full per-entity physical-parameter and normalized-coordinate errors are in [parameter-errors.csv](parameter-errors.csv), with target-wise RMSE, MAE, signed bias, and entity-bootstrap intervals in [parameter-results.csv](parameter-results.csv). No parameters with different units are combined into one score.

### Adaptation/suppression state recovery (`A_223`, `R_223`)

{_markdown_table(state_rows)}

### Physical parameter and normalized-coordinate recovery, native noise

{_markdown_table(parameter_rows)}

### Physical parameter and normalized-coordinate recovery, noise-free

{_markdown_table(noise_free_parameter_rows)}

## Bayesian uncertainty and prior sensitivity

The posterior is a local Gaussian approximation at the MAP, truncated to the declared coordinate bounds. A posterior interval is valid only when the mode is interior, the numerical Hessian is positive definite and conditioned at or below `1e10`, and 512 in-support draws are available. The table reports actual valid-posterior denominators; failed approximations are not silently removed. No chain-based R-hat or ESS is claimed.

{_markdown_table(posterior_table)}

{_markdown_table(prior_table)}

For each prior there are 64 noisy test fits (32 entities at noise scales 1 and 2). Uniform produced `{uniform_boundary_count}` boundary modes and `{uniform_valid_count}` valid Laplace approximations; Beta(8,8) produced `{beta_valid_count}` valid approximations. This prevents a paired posterior-interval comparison between those priors in this run: `prior-sensitivity.csv` preserves zero valid paired intervals rather than substituting MAP intervals. Beta(8,8) coverage is reported separately and is below its nominal 95% for several latent targets.

The per-entity target, coordinate, and physical-parameter intervals are preserved in [posterior-summaries.jsonl](posterior-summaries.jsonl). Aggregate parameter coverage and prior sensitivity are in [parameter-posterior-results.csv](parameter-posterior-results.csv) and [parameter-prior-sensitivity.csv](parameter-prior-sensitivity.csv). A narrower Beta(8,8) interval is prior-conditioned evidence, not proof that data identify the parameter.

![Uniform-prior 95% interval coverage](posterior-calibration.svg)

## Learned residual correction

The Ridge correction uses only development-entity residuals, four fixed observable/structural features, `alpha=1`, and a `[-20,20] kg` correction bound. The held-out entity set is disjoint from its training IDs in [residual-models.json](residual-models.json). A reduction in `DeltaC_56` error is a prediction result; it does not change the full-model states or parameters.

{_markdown_table(residual_table)}

## Negative and inconclusive findings

{_markdown_table(negative_table)}

All solver starts, boundary results, infeasible proposals, posterior diagnostics, and candidate equivalent solutions remain in machine-readable artifacts. The [paired comparison table](paired-comparisons.csv) reports the frozen entity-level 95% bootstrap contrasts separately by target, lift, and condition. There is no universal model leaderboard.

## Compute and reproduction

Compute is reported as deterministic solver/model passes, Hessian-gradient calls, posterior draws, direct reads, residual training rows, and equivalent daily state transitions. The hybrid and uniform-prior Bayesian method identify full-fit computation they share, so shared work is visible. These counts support replay and method budgeting; they are not hardware-independent time measurements.

{_markdown_table(cost_table)}

Replay and verify with:

```sh
uv pip install --python .venv/bin/python scipy==1.18.1
uv run --locked --no-sync python -m powerlifting_state_research.studies.target_sufficient_structural_reconstruction --check
```

This study's [protocol](../../../studies/target_sufficient_structural_reconstruction/protocol.json), [frozen M0–M5/RES-287 evidence identities](../../../studies/target_sufficient_structural_reconstruction/frozen-evidence.json), all input bytes, estimator identities, and outputs are checked by the manifest. The result realization is `{identity["realization_id"]}`; truth SHA-256 `{identity["truth_sha256"]}`; observation SHA-256 `{identity["observations_sha256"]}`; source-set digest `{identity["source_set_digest"]}`.

## Scope and limitations

These results concern the named public synthetic system, population transform, schedule templates, observation law, split, and priors. A good `P` estimate does not imply recovery of `C`, `A`, `R`, or physiology. The known equations and zero initial states are strong structural prior knowledge. The local Jacobian is not a global proof; practical recovery is conditional on this finite synthetic population; the Laplace posterior is an approximation; the residual model is trained only on this development split. No result establishes real-athlete validity, causal training effects, or generalization beyond declared support.

## RES-290 scientific handoff

RES-289 supplies the separate public-native realization, frozen methods, source-bound estimates, exact constant-input counterexample, local sensitivity evidence, noisy state/parameter diagnostics, posterior/prior sensitivity, and held-out residual results. The canonical-template global identification question remains **{identifiability["native_template_global_identification"]}** unless an admissible counterexample was found in the finite sample. RES-290 should treat that status as unresolved, keep prediction, state observability, parameter identifiability, and causal identification separate, and leave all M0–M5 and historical G2 evidence untouched. This handoff does not execute RES-290.
"""


def _res290_handoff(identity: Mapping[str, Any], identifiability: Mapping[str, Any]) -> str:
    return f"""# RES-290 scientific handoff

RES-289 study `{identity["study_id"]}`; realization `{identity["realization_id"]}`; protocol `{identity["protocol_digest"]}`; evaluation `{EVALUATION_ID}`. This file is a handoff only; it does not execute RES-290.

## Evidence carried forward

- Historical G2 survives as study metadata and aliases only. Its original protocol, rights-cleared measurements, fitted models, and quantitative results remain unsupported by public evidence.
- RES-289 supplies an independent PUBLIC_NATIVE realization with separate 32-entity development and 32-entity test identities; it does not modify M3 canonical data or RES-287 results.
- Estimator outputs distinguish `P_223`, `C_223`, `DeltaC_56`, `A_223`, `R_223`, physical parameters, and normalized population coordinates.
- A one-time observation has latent rank at most one. The constant `0.6` input family gives an exact reference-stimulus/gain equivalence outside canonical history templates.
- Native-template global identification is `{identifiability["native_template_global_identification"]}`. The zero initial-state assumption is retained; free-initial-state results are not transferred.
- Bayesian summaries use local Laplace approximations with explicit diagnostics and Uniform versus Beta(8,8) prior sensitivity. Residual-model results change prediction only; full states and parameters are inherited.

## Open scientific questions for RES-290

1. Establish or refute global identifiability across every admissible canonical template and parameter point; finite midpoint Jacobians and multi-start searches are insufficient.
2. Repeat practical parameter recovery over independent public-native population/noise realizations while preserving entity-level uncertainty and every failed fit.
3. Examine whether the local Laplace approximation remains adequate under multimodal or weakly identified posteriors; use a predeclared alternative only if its computation and diagnostics are frozen before outcomes.
4. Keep prediction accuracy, latent-state observability, parameter identification, and causal identification as separate outcomes.

M0–M5, G1/RES-287 evidence, and the canonical M3/M4 datasets remain frozen. No real-athlete or causal conclusion follows from this synthetic study.
"""


def build_bundle(root: Path) -> dict[str, bytes]:
    """Generate every deterministic RES-289 input, result, figure, and checksum."""
    verify_design(root)
    source_hashes = _source_hashes(root)
    source_set_digest = sha256_record(source_hashes)
    observation_rows, truth_rows = generate_data()
    observation_bytes = jsonl_bytes(observation_rows)
    truth_bytes = jsonl_bytes(truth_rows)
    observation_sha256 = digest(observation_bytes)
    truth_sha256 = digest(truth_bytes)
    development_ids = sorted(
        str(row["entity_id"]) for row in observation_rows if row["split"] == "development"
    )
    test_ids = sorted(str(row["entity_id"]) for row in observation_rows if row["split"] == "test")
    split_digest = sha256_record(
        {"development_entity_ids": development_ids, "test_entity_ids": test_ids}
    )
    generator_key = str(
        Path(
            "src/powerlifting_state_research/studies/target_sufficient_structural_reconstruction.py"
        )
    )
    realization_digest = sha256_record(
        {
            "study_id": STUDY_ID,
            "protocol_digest": PROTOCOL_DIGEST,
            "generator_source_sha256": source_hashes[generator_key],
            "truth_sha256": truth_sha256,
            "observations_sha256": observation_sha256,
            "split_digest": split_digest,
        }
    )
    realization_id = (
        "psr:study-realization:target-sufficient-structural-reconstruction-public-native"
        "@sha256:" + realization_digest.removeprefix("sha256:")
    )
    binding = {
        "study_id": STUDY_ID,
        "protocol_digest": PROTOCOL_DIGEST,
        "realization_id": realization_id,
        "evaluation_id": EVALUATION_ID,
        "source_set_digest": source_set_digest,
        "truth_sha256": truth_sha256,
        "observations_sha256": observation_sha256,
    }
    experiment_outputs = run_experiments(observation_rows, truth_rows, binding)
    identifiability = json.loads(experiment_outputs["identifiability.json"])
    negative_rows = _negative_result_rows(identifiability, experiment_outputs, binding)
    target_metrics = _read_csv_bytes(experiment_outputs["target-results.csv"])
    posterior_metrics = _read_csv_bytes(experiment_outputs["posterior-results.csv"])
    figures = {
        "reconstruction-errors.svg": _error_figure(target_metrics),
        "identifiability-spectra.svg": _identifiability_figure(identifiability),
        "posterior-calibration.svg": _posterior_coverage_figure(posterior_metrics),
    }
    identity: dict[str, Any] = {
        **binding,
        "realization_digest": realization_digest,
        "starting_main": STARTING_MAIN,
        "world_id": "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e",
        "dataset_spec_id": "psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed",
        "canonical_m3_evaluation_id": "psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8",
        "historical_g2_aliases": ["G2 / ALI-542", "pl_study_g2_structural_reconstruction"],
        "development_entity_count": len(development_ids),
        "test_entity_count": len(test_ids),
        "split_digest": split_digest,
        "source_hashes": source_hashes,
    }
    split_bytes = json_bytes(
        {
            "study_id": STUDY_ID,
            "protocol_digest": PROTOCOL_DIGEST,
            "realization_id": realization_id,
            "split_digest": split_digest,
            "development_entity_ids": development_ids,
            "test_entity_ids": test_ids,
            "entity_disjoint": not bool(set(development_ids) & set(test_ids)),
        }
    )
    negative_bytes = csv_bytes(
        negative_rows,
        (
            "study_id",
            "protocol_digest",
            "realization_id",
            "evaluation_id",
            "source_set_digest",
            "truth_sha256",
            "observations_sha256",
            "result_id",
            "claim",
            "status",
            "evidence",
            "interpretation_limit",
        ),
    )
    report = _report_text(experiment_outputs, identity, identifiability, negative_rows)
    handoff = _res290_handoff(identity, identifiability)
    output_files: dict[str, bytes] = {
        "observations.jsonl": observation_bytes,
        "truth.jsonl": truth_bytes,
        "split.json": split_bytes,
        **experiment_outputs,
        **figures,
        "negative-results.csv": negative_bytes,
        "report.md": report.encode("utf-8"),
        "RES-290-handoff.md": handoff.encode("utf-8"),
    }
    manifest = {
        **identity,
        "manifest_version": "1.0.0",
        "source_hashes": source_hashes,
        "source_set_digest": source_set_digest,
        "input_artifacts": {
            "observations.jsonl": observation_sha256,
            "truth.jsonl": truth_sha256,
            "split.json": digest(split_bytes),
        },
        "protocol_identity": {
            "study_id": STUDY_ID,
            "protocol_digest": PROTOCOL_DIGEST,
            "evaluation_id": EVALUATION_ID,
            "starting_main": STARTING_MAIN,
        },
        "frozen_evidence": {
            "m0_m5_file_count": len(
                json.loads((root / "studies/observation_inversion/frozen-m0-m5.json").read_bytes())
            ),
            "res287_file_count": len(
                json.loads((root / DESIGN / "frozen-evidence.json").read_bytes())[
                    "res287_frozen_files"
                ]
            ),
            "verified": True,
        },
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
        },
        "artifact_sha256": {
            name: digest(content) for name, content in sorted(output_files.items())
        },
        "rights": {
            "new_code_and_numeric_artifacts": "MIT",
            "authored_prose": "CC-BY-4.0",
            "historical_private_inputs_used": False,
            "historical_g2_results_reproduced": False,
        },
    }
    output_files["manifest.json"] = json_bytes(manifest)
    return output_files


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="replay and compare all frozen artifacts"
    )
    args = parser.parse_args(argv)
    root = Path.cwd()
    bundle = build_bundle(root)
    home = root / HOME
    if args.check:
        for name, expected in bundle.items():
            path = home / name
            if not path.is_file() or path.read_bytes() != expected:
                raise SystemExit(f"stale or missing RES-289 artifact: {path}")
        unexpected = {
            path.name
            for path in home.iterdir()
            if path.is_file() and path.name != "README.md" and path.name not in bundle
        }
        if unexpected:
            raise SystemExit(f"unexpected RES-289 result artifacts: {sorted(unexpected)}")
        print(
            f"PASS: {len(bundle)} RES-289 artifacts replayed; "
            f"realization={json.loads(bundle['manifest.json'])['realization_id']}"
        )
        return 0
    existing = [name for name in bundle if (home / name).exists()]
    if existing:
        raise SystemExit(
            f"refusing to overwrite existing RES-289 artifacts: {', '.join(sorted(existing))}; use --check"
        )
    for name, content in bundle.items():
        _write_atomic(home / name, content)
    manifest = json.loads(bundle["manifest.json"])
    print(
        f"Wrote {len(bundle)} RES-289 artifacts; realization={manifest['realization_id']}; "
        f"protocol={manifest['protocol_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
