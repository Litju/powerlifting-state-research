"""Deterministic analytical observation study; run with --check for full replay."""

# ruff: noqa: E501
# Generated scientific prose keeps complete sentences together.

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (
    LiftParameters,
    TrainingSession,
    simulate_lift,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.interventions import (
    declared_plan,
    training_sessions,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.observations import (
    ASSESSMENT_CV,
    VELOCITY_CONSTANTS,
    VELOCITY_SD_MPS,
    PerformanceObservation,
    sample_performance_observation,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (
    LIFTS,
    parameters_from_coordinates,
)
from ..contracts.serialization import canonical_json_bytes, sha256_record
from .observation_inversion_protocol import PROTOCOL, PROTOCOL_DIGEST, STUDY_ID

HOME = Path("results/studies/observation_inversion")
DESIGN = Path("studies/observation_inversion")
Array = NDArray[np.float64]


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def verify_design(root: Path) -> None:
    record = json.loads((root / DESIGN / "protocol.json").read_bytes())
    if record["protocol_digest"] != PROTOCOL_DIGEST or record["study_id"] != STUDY_ID:
        raise ValueError("frozen study protocol drift")
    if sha256_record(record["protocol"]) != PROTOCOL_DIGEST:
        raise ValueError("frozen protocol payload drift")
    frozen = json.loads((root / DESIGN / "frozen-m0-m5.json").read_bytes())
    for path, expected in frozen.items():
        if digest((root / path).read_bytes()) != expected:
            raise ValueError(f"frozen M0-M5 bytes changed: {path}")


def observation_days(length: int, cadence: int) -> tuple[int, ...]:
    if length not in PROTOCOL.lengths or cadence not in PROTOCOL.cadences_days:
        raise ValueError("undeclared observation support")
    return tuple(223 - cadence * offset for offset in reversed(range(length)))


def scaled_observation(
    base: PerformanceObservation, expressed_kg: float, scale: float, lift: str
) -> PerformanceObservation:
    if scale not in PROTOCOL.noise_scales or expressed_kg <= 0:
        raise ValueError("undeclared noise scale or invalid truth")
    fraction = base.prescribed_load_kg / base.assessment_kg
    endpoint, span, _ = VELOCITY_CONSTANTS[lift]
    base_expected = endpoint + span * (1 - base.prescribed_load_kg / expressed_kg) / 0.6
    assessment = expressed_kg + scale * (base.assessment_kg - expressed_kg)
    load = fraction * assessment
    if assessment <= 0 or not 0.4 <= load / expressed_kg <= 1:
        raise ValueError("scaled observation outside declared native domain")
    velocity = endpoint + span * (1 - load / expressed_kg) / 0.6
    velocity += scale * (base.velocity_mps - base_expected)
    return PerformanceObservation(base.day, assessment, load, velocity)


def reconstruct(
    observations: tuple[PerformanceObservation, ...],
    lift: str,
    channel: str,
    method: str,
    noise_scale: float,
) -> float | None:
    """Only participant observations enter; truth and parameters are not arguments."""
    if not observations or lift not in LIFTS or channel not in PROTOCOL.channels:
        raise ValueError("invalid reconstruction inputs")
    if method not in PROTOCOL.methods or noise_scale not in PROTOCOL.noise_scales:
        raise ValueError("undeclared reconstruction method or noise")
    if any(
        o.day > 223
        or o.day < 0
        or o.assessment_kg <= 0
        or o.prescribed_load_kg <= 0
        or not all(
            math.isfinite(v) for v in (o.assessment_kg, o.prescribed_load_kg, o.velocity_mps)
        )
        for o in observations
    ) or any(a.day >= b.day for a, b in zip(observations, observations[1:], strict=False)):
        raise ValueError("invalid observation boundary or ordering")
    values: list[float] = []
    endpoint, span, _ = VELOCITY_CONSTANTS[lift]
    for observation in observations[-1:] if method == "last" else observations:
        assessment = observation.assessment_kg
        if channel == "assessment":
            value = assessment
        elif channel == "load":
            value = observation.prescribed_load_kg / 0.695
        else:
            relative = 1 - 0.6 * (observation.velocity_mps - endpoint) / span
            if not 0.4 <= relative <= 1:
                return None
            velocity = observation.prescribed_load_kg / relative
            value = velocity
            if channel == "combined":
                va = (ASSESSMENT_CV[lift] * assessment) ** 2
                vv = (
                    0.6
                    * observation.prescribed_load_kg
                    * VELOCITY_SD_MPS[lift]
                    / (span * relative**2)
                ) ** 2
                value = (
                    (assessment + velocity) / 2
                    if noise_scale == 0
                    else (assessment * vv + velocity * va) / (va + vv)
                )
        values.append(value)
    return math.fsum(values) / len(values)


def rest_jacobian(
    parameters: LiftParameters, state: tuple[float, float], days: tuple[int, ...]
) -> Array:
    a, r = state
    b, ga, gr = parameters.baseline_kg, parameters.adaptation_gain, parameters.suppression_gain
    return np.array(
        [
            [
                b
                * ga
                * math.exp(-k / parameters.adaptation_time_days)
                * (1 - gr * math.exp(-k / parameters.suppression_time_days) * r),
                -b
                * (1 + ga * math.exp(-k / parameters.adaptation_time_days) * a)
                * gr
                * math.exp(-k / parameters.suppression_time_days),
            ]
            for k in days
        ],
        dtype=np.float64,
    )


def rest_output(
    parameters: LiftParameters, state: tuple[float, float], days: tuple[int, ...]
) -> Array:
    return np.array(
        [
            parameters.baseline_kg
            * (
                1
                + parameters.adaptation_gain
                * state[0]
                * math.exp(-k / parameters.adaptation_time_days)
            )
            * (
                1
                - parameters.suppression_gain
                * state[1]
                * math.exp(-k / parameters.suppression_time_days)
            )
            for k in days
        ],
        dtype=np.float64,
    )


def numerical_rest_jacobian(
    parameters: LiftParameters, state: tuple[float, float], days: tuple[int, ...]
) -> Array:
    columns = []
    for index in range(2):
        plus, minus = list(state), list(state)
        plus[index] += 1e-6
        minus[index] -= 1e-6
        columns.append(
            (
                rest_output(parameters, (plus[0], plus[1]), days)
                - rest_output(parameters, (minus[0], minus[1]), days)
            )
            / 2e-6
        )
    return np.column_stack(columns)


def sensitivity(template: int, step: float) -> Array:
    columns = []
    for index in (0, 3, 4, 5, 6, 15):
        plus, minus = [0.5] * 16, [0.5] * 16
        plus[index] += step
        minus[index] -= step
        outputs = []
        for coordinates in (plus, minus):
            world = parameters_from_coordinates(coordinates)
            trajectory = simulate_lift(
                world.lifts["squat"],
                training_sessions(template, declared_plan("continue")),
                world.stimulus_reference,
            )
            outputs.append(
                np.array(trajectory.expressed_performance_kg)[list(observation_days(32, 7))]
            )
        columns.append((outputs[0] - outputs[1]) / (2 * step))
    return np.column_stack(columns)


def rank_record(jacobian: Array) -> dict[str, Any]:
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.sum(singular > singular[0] * 1e-8))
    # Round only serialized SVD diagnostics to suppress backend last-bit differences.
    return {
        "singular_values": [round(float(value), 8) for value in singular],
        "rank": rank,
        "threshold_relative": 1e-8,
        "condition": round(float(singular[0] / singular[-1]), 8) if singular[-1] > 0 else None,
        "authority": "GENERATOR_AUTHORITY",
        "global_identification": "INCONCLUSIVE",
    }


def diagnostics() -> dict[str, Any]:
    world = parameters_from_coordinates([0.5] * 16)
    p = world.lifts["squat"]
    a1, r1, r2 = 0.3, 0.3, 0.5
    c1 = p.baseline_kg * (1 + p.adaptation_gain * a1)
    expressed = c1 * (1 - p.suppression_gain * r1)
    a2 = (expressed / (p.baseline_kg * (1 - p.suppression_gain * r2)) - 1) / p.adaptation_gain
    c2 = p.baseline_kg * (1 + p.adaptation_gain * a2)
    assert 0 <= a2 <= 1 and abs(c2 * (1 - p.suppression_gain * r2) - expressed) < 1e-10
    rest = []
    for gap in (1, 7, 28):
        jac = rest_jacobian(p, (a1, r1), (0, gap))
        error = float(np.max(np.abs(jac - numerical_rest_jacobian(p, (a1, r1), (0, gap)))))
        assert error < 1e-6
        rest.append({"gap_days": gap, "analytical_fd_max_error": error, **rank_record(jac)})
    params = []
    for template in range(4):
        jac, refined = sensitivity(template, 1e-5), sensitivity(template, 5e-6)
        params.append(
            {
                "template": template,
                "fd_step": 1e-5,
                "refined_step_max_difference": float(np.max(np.abs(jac - refined))),
                **rank_record(jac),
            }
        )
    constant = {day: TrainingSession(day, 0.8, 0.75) for day in range(280)}
    trajectories = []
    for reference in (0.2, 0.8):
        coordinates = [0.5] * 16
        coordinates[15] = reference
        alternative = parameters_from_coordinates(coordinates)
        trajectories.append(
            simulate_lift(alternative.lifts["squat"], constant, alternative.stimulus_reference)
        )
    t1, t2 = trajectories
    difference = max(
        abs(x - y)
        for x, y in zip(t1.expressed_performance_kg, t2.expressed_performance_kg, strict=True)
    )
    assert difference < 1e-10
    q = [0.5] * 16
    q[15] += 0.01
    perturbed = parameters_from_coordinates(q)
    sessions = training_sessions(0, declared_plan("continue"))
    base = simulate_lift(p, sessions, world.stimulus_reference)
    near = simulate_lift(perturbed.lifts["squat"], sessions, perturbed.stimulus_reference)
    differences = (
        np.array(base.expressed_performance_kg)[list(observation_days(32, 7))]
        - np.array(near.expressed_performance_kg)[list(observation_days(32, 7))]
    )
    return {
        "instantaneous": {
            "state1": [a1, r1],
            "state2": [a2, r2],
            "P_kg": expressed,
            "C1_kg": c1,
            "C2_kg": c2,
            "rank": 1,
            "claim": "single-time state/capacity nonuniqueness",
        },
        "free_initial_state_rest": rest,
        "native_parameter_local_sensitivity": params,
        "constant_input_equivalence": {
            "reference_coordinates": [0.2, 0.8],
            "max_P_difference_kg": difference,
            "A223_difference": t2.chronic_adaptation[223] - t1.chronic_adaptation[223],
            "R223_difference": t2.transient_suppression[223] - t1.transient_suppression[223],
            "support": "constant continue; outside canonical four history templates",
            "claim": "exact all-time state/parameter ambiguity for this controlled input",
        },
        "native_near_equivalence": {
            "template": 0,
            "reference_coordinate_difference": 0.01,
            "P_history_rmse_kg": float(np.sqrt(np.mean(differences**2))),
            "C223_difference_kg": near.latent_capacity_kg[223] - base.latent_capacity_kg[223],
            "claim": "practical sensitivity example; not exact equivalence",
        },
    }


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def generate_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(PROTOCOL.population_seed)
    days = sorted(
        {
            d
            for length in PROTOCOL.lengths
            for cadence in PROTOCOL.cadences_days
            for d in observation_days(length, cadence)
        }
    )
    inputs, truth = [], []
    for entity in range(PROTOCOL.entities):
        world = parameters_from_coordinates([rng.random() for _ in range(16)])
        for lift_index, lift in enumerate(LIFTS):
            template = (entity + lift_index) % 4
            trajectory = simulate_lift(
                world.lifts[lift],
                training_sessions(template, declared_plan("continue")),
                world.stimulus_reference,
            )
            observation_rng = random.Random(PROTOCOL.observation_seed + 100 * entity + lift_index)
            observations = [
                asdict(
                    sample_performance_observation(
                        day, trajectory.expressed_performance_kg[day], lift, observation_rng
                    )
                )
                for day in days
            ]
            inputs.append(
                {"entity": entity, "lift": lift, "template": template, "observations": observations}
            )
            truth.append(
                {
                    "entity": entity,
                    "lift": lift,
                    "P_by_observation_day": {
                        str(day): trajectory.expressed_performance_kg[day] for day in days
                    },
                    "P223_kg": trajectory.expressed_performance_kg[223],
                    "C223_kg": trajectory.latent_capacity_kg[223],
                    "P230_kg": trajectory.expressed_performance_kg[230],
                }
            )
    return inputs, truth


def evaluate(
    inputs: list[dict[str, Any]], truth: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metrics, errors, comparisons = [], [], []
    bootstrap_rng = random.Random(PROTOCOL.bootstrap_seed)
    bootstrap = np.array(
        [
            [bootstrap_rng.randrange(PROTOCOL.entities) for _ in range(PROTOCOL.entities)]
            for _ in range(PROTOCOL.bootstrap_replicates)
        ]
    )
    for lift in LIFTS:
        pairs = [(x, y) for x, y in zip(inputs, truth, strict=True) if x["lift"] == lift]
        for scale in PROTOCOL.noise_scales:
            for length in PROTOCOL.lengths:
                for cadence in PROTOCOL.cadences_days:
                    estimates: dict[tuple[str, str], list[float | None]] = {}
                    for channel in PROTOCOL.channels:
                        for method in PROTOCOL.methods:
                            values = []
                            for row, target in pairs:
                                selected = tuple(
                                    scaled_observation(
                                        PerformanceObservation(**o),
                                        target["P_by_observation_day"][str(o["day"])],
                                        scale,
                                        lift,
                                    )
                                    for o in row["observations"]
                                    if o["day"] in observation_days(length, cadence)
                                )
                                values.append(reconstruct(selected, lift, channel, method, scale))
                            estimates[channel, method] = values
                            for target_name in PROTOCOL.targets:
                                invalid = sum(v is None for v in values)
                                condition = {
                                    "lift": lift,
                                    "noise_scale": scale,
                                    "length": length,
                                    "cadence_days": cadence,
                                    "channel": channel,
                                    "method": method,
                                    "target": target_name,
                                }
                                cell: dict[str, Any] = {
                                    **condition,
                                    "status": "INCONCLUSIVE" if invalid else "COMPLETE",
                                    "invalid_count": invalid,
                                    "n_entities": PROTOCOL.entities,
                                    "rmse_kg": None,
                                    "mae_kg": None,
                                    "bias_kg": None,
                                    "rmse_ci_low_kg": None,
                                    "rmse_ci_high_kg": None,
                                }
                                for (row, target), value in zip(pairs, values, strict=True):
                                    errors.append(
                                        {
                                            **condition,
                                            "entity": row["entity"],
                                            "estimate_kg": value,
                                            "truth_kg": target[target_name],
                                            "error_kg": None
                                            if value is None
                                            else value - target[target_name],
                                        }
                                    )
                                if not invalid:
                                    error = np.array(
                                        [
                                            float(v) - y[target_name]
                                            for v, (_, y) in zip(values, pairs, strict=True)
                                            if v is not None
                                        ]
                                    )
                                    rmses = np.sqrt(np.mean(error[bootstrap] ** 2, axis=1))
                                    ci = np.quantile(rmses, [0.025, 0.975])
                                    cell.update(
                                        rmse_kg=float(np.sqrt(np.mean(error**2))),
                                        mae_kg=float(np.mean(np.abs(error))),
                                        bias_kg=float(np.mean(error)),
                                        rmse_ci_low_kg=float(ci[0]),
                                        rmse_ci_high_kg=float(ci[1]),
                                    )
                                    if (
                                        scale == 0
                                        and channel in ("assessment", "velocity", "combined")
                                        and method == "last"
                                        and target_name == "P223_kg"
                                    ):
                                        assert max(abs(error)) < 1e-10
                                metrics.append(cell)
                    for method in PROTOCOL.methods:
                        for target_name in PROTOCOL.targets:
                            a, c = estimates["assessment", method], estimates["combined", method]
                            row = {
                                "lift": lift,
                                "noise_scale": scale,
                                "length": length,
                                "cadence_days": cadence,
                                "method": method,
                                "target": target_name,
                            }
                            if any(v is None for v in c):
                                comparisons.append(
                                    {
                                        **row,
                                        "delta_rmse_kg": None,
                                        "ci_low_kg": None,
                                        "ci_high_kg": None,
                                        "status": "INCONCLUSIVE",
                                    }
                                )
                                continue
                            ae = np.array(
                                [
                                    float(v) - y[target_name]
                                    for v, (_, y) in zip(a, pairs, strict=True)
                                    if v is not None
                                ]
                            )
                            ce = np.array(
                                [
                                    float(v) - y[target_name]
                                    for v, (_, y) in zip(c, pairs, strict=True)
                                    if v is not None
                                ]
                            )
                            differences = np.sqrt(np.mean(ce[bootstrap] ** 2, axis=1)) - np.sqrt(
                                np.mean(ae[bootstrap] ** 2, axis=1)
                            )
                            low, high = np.quantile(differences, [0.025, 0.975])
                            status = "PASS" if high < 0 else "FAIL" if low > 0 else "INCONCLUSIVE"
                            comparisons.append(
                                {
                                    **row,
                                    "delta_rmse_kg": float(
                                        np.sqrt(np.mean(ce**2)) - np.sqrt(np.mean(ae**2))
                                    ),
                                    "ci_low_kg": float(low),
                                    "ci_high_kg": float(high),
                                    "status": status,
                                }
                            )
    return metrics, errors, comparisons


def figure(metrics: list[dict[str, Any]]) -> bytes:
    """Small deterministic SVG plot sourced directly from quantitative table rows."""
    selected = [
        r
        for r in metrics
        if r["lift"] == "squat"
        and r["length"] == 1
        and r["cadence_days"] == 7
        and r["method"] == "last"
        and r["target"] == "P223_kg"
    ]
    ymax = max(r["rmse_kg"] or 0 for r in selected) * 1.1
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480">',
        '<rect width="800" height="480" fill="white"/>',
        '<g font-family="sans-serif" font-size="14" fill="black">',
        '<text x="70" y="25">Squat expressed-performance recovery, day223 (32 synthetic entities)</text>',
        '<text x="70" y="55">RMSE (kg); last observation; lines are point estimates</text>',
        '<path d="M70 80 V370 H650" fill="none" stroke="black"/>',
    ]
    for tick in range(5):
        value = ymax * tick / 4
        y = 370 - 280 * tick / 4
        lines.append(f'<text x="10" y="{y:.3f}">{value:.2f}</text>')
    for scale in PROTOCOL.noise_scales:
        x = 70 + scale * 280
        lines.append(f'<text x="{x:.3f}" y="395">{scale}</text>')
    for index, channel in enumerate(PROTOCOL.channels):
        color = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")[index]
        rows = [r for r in selected if r["channel"] == channel]
        points = " ".join(
            f"{70 + r['noise_scale'] * 280:.3f},{370 - (r['rmse_kg'] or 0) * 280 / ymax:.3f}"
            for r in rows
            if r["rmse_kg"] is not None
        )
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="660" y="{100 + index * 25}" fill="{color}">{channel}</text>')
    lines.extend(
        [
            '<text x="220" y="430">Observation-noise multiplier (dimensionless)</text>',
            '<text x="70" y="460">Synthetic laws only; not latent recovery. Uncertainty: metrics.csv; invalid cells omitted.</text>',
            "</g></svg>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def history_figure(metrics: list[dict[str, Any]]) -> bytes:
    rows = [
        r
        for r in metrics
        if r["lift"] == "squat"
        and r["channel"] == "assessment"
        and r["method"] == "mean"
        and r["target"] == "P223_kg"
        and r["noise_scale"] in (0.0, 1.0)
    ]
    ymax = max(r["rmse_kg"] for r in rows) * 1.1
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480">',
        '<rect width="800" height="480" fill="white"/>',
        '<g font-family="sans-serif" font-size="14">',
        '<text x="70" y="25">Squat current P reconstruction: assessment history mean</text>',
        '<text x="70" y="55">RMSE (kg), 32 synthetic entities; point estimates</text>',
        '<path d="M70 80 V370 H650" fill="none" stroke="black"/>',
    ]
    for tick in range(5):
        lines.append(f'<text x="10" y="{370 - 280 * tick / 4:.3f}">{ymax * tick / 4:.2f}</text>')
    for index, length in enumerate(PROTOCOL.lengths):
        lines.append(f'<text x="{70 + index * 180}" y="395">{length}</text>')
    for index, (scale, cadence) in enumerate(((0.0, 1), (0.0, 7), (1.0, 1), (1.0, 7))):
        color = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")[index]
        selected = [r for r in rows if r["noise_scale"] == scale and r["cadence_days"] == cadence]
        points = " ".join(
            f"{70 + i * 180},{370 - r['rmse_kg'] * 280 / ymax:.3f}" for i, r in enumerate(selected)
        )
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        lines.append(
            f'<text x="660" y="{100 + index * 35}" fill="{color}">noise{scale}, {cadence}d</text>'
        )
    lines.extend(
        [
            '<text x="200" y="430">History observations (count, categorical spacing)</text>',
            '<text x="70" y="460">Same count spans different time periods; smoothing bias remains at zero noise.</text>',
            "</g></svg>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def report(
    metrics: list[dict[str, Any]], diag: dict[str, Any], comparisons: list[dict[str, Any]]
) -> bytes:
    rows = [
        r
        for r in metrics
        if r["noise_scale"] == 1
        and r["length"] == 1
        and r["cadence_days"] == 7
        and r["method"] == "last"
    ]
    table = [
        "| Lift | Channel | Target | RMSE kg | 95% entity bootstrap kg | Status |",
        "|---|---|---|---:|---|---|",
    ]
    for r in rows:
        rmse = "undefined" if r["rmse_kg"] is None else f"{r['rmse_kg']:.6f}"
        ci = (
            "undefined"
            if r["rmse_kg"] is None
            else f"[{r['rmse_ci_low_kg']:.6f}, {r['rmse_ci_high_kg']:.6f}]"
        )
        table.append(
            f"| {r['lift']} | {r['channel']} | {r['target']} | {rmse} | {ci} | {r['status']} |"
        )
    indexed = {
        (
            r["lift"],
            r["noise_scale"],
            r["length"],
            r["cadence_days"],
            r["channel"],
            r["method"],
            r["target"],
        ): r
        for r in metrics
    }
    zero_mean = indexed["squat", 0.0, 32, 7, "assessment", "mean", "P223_kg"]["rmse_kg"]
    zero_capacity = indexed["squat", 0.0, 1, 7, "assessment", "last", "C223_kg"]["rmse_kg"]
    native_assessment = indexed["squat", 1.0, 1, 7, "assessment", "last", "P223_kg"]["rmse_kg"]
    native_combined = indexed["squat", 1.0, 1, 7, "combined", "last", "P223_kg"]["rmse_kg"]
    paired = next(
        r
        for r in comparisons
        if r["lift"] == "squat"
        and r["noise_scale"] == 1
        and r["length"] == 1
        and r["cadence_days"] == 7
        and r["method"] == "last"
        and r["target"] == "P223_kg"
    )
    states = {
        status: sum(r["status"] == status for r in comparisons)
        for status in ("PASS", "FAIL", "INCONCLUSIVE")
    }
    text = f"""# Observation inversion and latent-state observability

Study `{STUDY_ID}`; protocol `{PROTOCOL_DIGEST}`. Independent synthetic experiment, not recovered G1 measurements. [Manifest](manifest.json) binds every input, source and output SHA-256. The [frozen protocol](../../../studies/observation_inversion/protocol.json), [formal derivation](../../../studies/observation_inversion/formal-specification.md) and [historical lineage](../../../studies/observation_inversion/historical-lineage.md) specify assumptions and evidence classes.

## Historical evidence

G1 research-home/name and attachment survive as metadata. Exact original question, G1 measurements, estimators, experiments, fitted models and numerical results are unavailable. Parent benchmark equations and channel semantics survive as public projections; they cannot be relabelled G1 experiments. Historical numerical claims remain UNSUPPORTED_BY_EVIDENCE. No private artifacts are read. All executed numbers below are NEW_PUBLIC_NATIVE_EXPERIMENT.

## Methods and independent realization

32 independently sampled entities; three lifts; four balanced native history templates per lift; future continue plan. No fitting or selection: all entities form a separately hashed evaluation-only split. Truth and base observations are stored separately as truth.jsonl and observations.jsonl. Native observation draws are reused across noise scales, with the load recomputed from the same fraction of scaled assessment. Noise changes no latent truth. Cadences 1/7 days and lengths 1/4/16/32 all end at223; equal lengths span different time intervals. Estimators use analytical inverse, last observation or mean. Load-only uses its known fraction midpoint. Combined uses a plug-in delta-method variance rule, which is approximate and not a physiological estimator or Bayes optimum.

Targets are current expressed P223, current latent C223 and future expressed P230, all kg. Persistence/mean prediction of P230 is distinct from the frozen canonical DeltaC benchmark; no canonical model comparisons or scores are changed. RMSE, MAE and signed bias are per lift/target. Point estimates and 95% percentile bootstrap intervals describe this finite synthetic population; paired intervals in comparisons.csv assess combined-minus-assessment differences. No multiple-testing or universal superiority claim is made. Invalid inverses invalidate the entire cell; no row is silently removed. Raw entity errors permit independent metric checks.

## Quantitative channel comparison

Native noise, one most recent observation; exact full-precision values and all ablations appear in [metrics.csv](metrics.csv). Each row has its condition and status; [comparisons.csv](comparisons.csv) retains paired uncertainty and negative/inconclusive findings.

{chr(10).join(table)}

![Channel/noise sensitivity](channel-noise.svg)

![History and cadence sensitivity](history-cadence.svg)

The plots read these table cells directly. It depicts P recovery, not latent observability. [metrics.csv](metrics.csv) also contains history/cadence and C/P230 sensitivity, including smoothing bias and invalid counts. Per-condition evidence must be used rather than a single aggregate score.

A concrete negative result: with noiseless squat assessments, the last observation has zero P223 error but the 32-week history mean has RMSE {zero_mean:.6f} kg (metrics.csv: squat, noise0, cadence7, length32, mean, P223). The same noiseless last-observation reconstruction has C223 RMSE {zero_capacity:.6f} kg, directly separating P recovery from capacity recovery. Native-noise squat P223 RMSE is {native_assessment:.6f} kg for assessment and {native_combined:.6f} kg for combined, but the paired difference interval [{paired["ci_low_kg"]:.6f}, {paired["ci_high_kg"]:.6f}] kg includes zero (comparisons.csv: squat, noise1, length1, cadence7, last, P223). Deadlift's same-condition interval excludes zero, while bench press's does not. These support condition-specific conclusions only. Across all predeclared comparisons, {states["PASS"]} PASS, {states["FAIL"]} FAIL and {states["INCONCLUSIVE"]} INCONCLUSIVE cells are retained; duplicated last/mean and cadence conditions are not independent experiments.

## Mathematical findings and authority boundaries

Noiseless last-observation assessment, velocity with measured load, and combined inversion recover P within 1e-10 kg on every entity/lift. This is hypothesis H1, checked during execution. C is not generally equal to P, so even exact P recovery is not capacity recovery (H3; zero-noise C cells in metrics.csv). A single-time channel Jacobian factors through P and has latent rank at most one (H2; formal derivation and diagnostics.json instantaneous).

The constructive same-P example has C1={diag["instantaneous"]["C1_kg"]:.9f} kg and C2={diag["instantaneous"]["C2_kg"]:.9f} kg, with different admissible (A,R). It is a single-time free-state counterexample; it is not proof that native whole histories admit those states. Under a separate free-initial-state rest extension with known parameters, two-time Jacobians have the ranks/conditioning and derivative checks in [diagnostics.json](diagnostics.json). Native initial states are fixed zero; knowing parameters and inputs permits forward simulation, which is privileged knowledge rather than observation-based inference.

Midpoint six-coordinate Jacobians for four native templates have ranks and singular spectra in diagnostics.json. Singular values and condition numbers serialize to eight decimal places for portable byte replay; rank is calculated before rounding. These are generator-authority local numerical sensitivity diagnostics with central-difference refinement, not global inverse proofs or participant recovery. Constant-continue histories admit an exact reference-stimulus parameter and hidden-state ambiguity, with maximum P discrepancy {diag["constant_input_equivalence"]["max_P_difference_kg"]:.3g} kg. This controlled input is within dose support but outside the four native templates. The native near-equivalence perturbation changes reference coordinate by 0.01 and yields P-history RMSE {diag["native_near_equivalence"]["P_history_rmse_kg"]:.9f} kg; this measures weak practical sensitivity, not exact equivalence.

## Negative results and unresolved claims

[claims.csv](claims.csv) preserves negative results and missing-evidence semantics. Exact expressed-performance inversion is insufficient for C/A/R recovery. Full local numerical rank is insufficient for global identification. Long-history means can mix changing states; their errors cannot be interpreted as pure observation-noise effects. Correlated load prescription makes velocity-only a load-plus-velocity information set, and load alone already contains assessment information. H4 remains condition-specific PASS/FAIL/INCONCLUSIVE in paired comparisons; uncertainty spanning zero is not positive evidence. Zero-noise differences within the declared 1e-10 kg inverse tolerance are numerical equivalence: raw interval-sign PASS/FAIL labels in those cells are not scientific superiority evidence. Physiology, causal effects, real-athlete validation, unknown-model discovery and native-template global identification remain unsupported or unresolved.

## Rights, reproduction and limits

New code and generated numeric artifacts are MIT; authored prose CC BY 4.0. All source hashes and origin decisions are in manifest.json and the public origin ledger. Historical provenance confers no artifact rights. RES-284 missing matched historical panels and uncertainty restrictions remain unchanged. This study has its own truth, so its entity bootstrap is supported independently. Small synthetic sample, one population realization and one noise realization do not establish robustness across seeds or distributions.

Run `uv run --locked python -m powerlifting_state_research.studies.observation_inversion --check` for full deterministic replay, hashes, source/protocol freeze and M0–M5 preservation. [RES-289 handoff](RES-289-handoff.md) lists evidence requirements only; RES-289 is not executed.
"""
    return text.encode()


def build_bundle(root: Path) -> dict[str, bytes]:
    verify_design(root)
    inputs, truth = generate_data()
    metrics, errors, comparisons = evaluate(inputs, truth)
    diag = diagnostics()
    sources = [
        DESIGN / "protocol.json",
        DESIGN / "formal-specification.md",
        DESIGN / "historical-lineage.md",
        DESIGN / "frozen-m0-m5.json",
        Path("src/powerlifting_state_research/studies/observation_inversion.py"),
        Path("src/powerlifting_state_research/studies/observation_inversion_protocol.py"),
        Path("src/powerlifting_state_research/studies/registry.py"),
        Path("src/powerlifting_state_research/provenance/historical_sources.py"),
        Path("results/audits/res284-publication/methods-limitations.md"),
    ]
    outputs = {
        "observations.jsonl": b"".join(json_bytes(row) for row in inputs),
        "truth.jsonl": b"".join(json_bytes(row) for row in truth),
        "errors.csv": csv_bytes(errors),
        "metrics.csv": csv_bytes(metrics),
        "comparisons.csv": csv_bytes(comparisons),
        "diagnostics.json": json_bytes(diag),
        "observability-diagnostics.csv": csv_bytes(
            [
                {
                    "diagnostic": name,
                    "support": r.get("template", r.get("gap_days")),
                    "rank": r["rank"],
                    "condition": r["condition"],
                    "threshold_relative": r["threshold_relative"],
                    "authority": r["authority"],
                    "global_identification": r["global_identification"],
                }
                for name, records in (
                    ("native_six_parameter_weekly", diag["native_parameter_local_sensitivity"]),
                    ("known_parameter_free_initial_rest", diag["free_initial_state_rest"]),
                )
                for r in records
            ]
        ),
        "channel-noise.svg": figure(metrics),
        "history-cadence.svg": history_figure(metrics),
        "report.md": report(metrics, diag, comparisons),
    }
    claims = [
        {
            "claim": "Noiseless P inverse",
            "status": "PASS",
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "evidence": "metrics.csv: noise0,last,P223; formal specification inverse",
            "limit": "expressed performance only",
        },
        {
            "claim": "Single-time C/A/R uniqueness",
            "status": "FAIL",
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "evidence": "diagnostics.json: instantaneous; formal specification level set",
            "limit": "free state at one time",
        },
        {
            "claim": "Universal hidden state/parameter identification",
            "status": "FAIL",
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "evidence": "diagnostics.json: constant_input_equivalence; formal specification",
            "limit": "constant continue outside canonical history templates",
        },
        {
            "claim": "Global native-template parameter identification",
            "status": "INCONCLUSIVE",
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "evidence": "diagnostics.json: native_parameter_local_sensitivity",
            "limit": "local rank does not prove global injectivity",
        },
        {
            "claim": "Combined finite-noise improvement",
            "status": "INCONCLUSIVE",
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "evidence": "comparisons.csv: condition-specific statuses",
            "limit": "no universal superiority claim",
        },
        {
            "claim": "Historical G1 quantitative conclusions",
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "classification": "UNSUPPORTED_BY_EVIDENCE",
            "evidence": "historical-lineage.md; registry and historical provenance",
            "limit": "missing historical measurements/results",
        },
        {
            "claim": "Real-athlete physiology or causal effects",
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "classification": "UNSUPPORTED_BY_EVIDENCE",
            "evidence": "formal specification; synthetic protocol",
            "limit": "no empirical or causal identification design",
        },
    ]
    outputs["claims.csv"] = csv_bytes(claims)
    outputs["RES-289-handoff.md"] = b"""# RES-289 scientific handoff

RES-287 supplies source-bound observation laws, analytical P inversion, matched channel/noise/history tables, entity errors and bootstrap comparisons. See manifest.json for exact identities/hashes and report.md for all claim limits. G1 metadata survives; no historical quantitative result is recovered.

For target-sufficient reconstruction, name the target functional and participant-visible inputs first. Evaluate P, C, DeltaC, A/R and parameters separately. Native zero initial states differ from a free-state observability problem. Local rank is not a global inverse. Constant-input ambiguity is outside canonical templates; canonical global identification remains unresolved. Generator coordinates are truth only, never participant information. Better prediction does not identify states, physiology or causal effects.

Use a separate frozen protocol, realization, split and seeds. Before stronger claims, supply global equivalence analysis on native support and practical noisy parameter recovery with uncertainty. Preserve invalid inverses and negative findings. No G1 replay without rights-cleared original protocol and measurements. Canonical M0-M5 evidence remains frozen. This handoff executes no RES-289 work.
"""
    outputs["README.md"] = b"""# RES-287 results

Read [report.md](report.md), [manifest.json](manifest.json), [claims.csv](claims.csv) and [RES-289-handoff.md](RES-289-handoff.md). All measurements here are independent public-native experiments, not G1 historical results. The frozen study protocol precedes execution. Full replay: `uv run --locked python -m powerlifting_state_research.studies.observation_inversion --check`.
"""
    realization_payload = {
        "protocol_id": STUDY_ID,
        "observations_sha256": digest(outputs["observations.jsonl"]),
        "truth_sha256": digest(outputs["truth.jsonl"]),
        "entities": PROTOCOL.entities,
        "population_seed": PROTOCOL.population_seed,
        "observation_seed": PROTOCOL.observation_seed,
    }
    realization_digest = sha256_record(realization_payload)
    split = {
        "role": "evaluation-only",
        "entities": list(range(PROTOCOL.entities)),
        "training_entities": [],
        "selection_entities": [],
    }
    manifest = {
        "format": "PSR_OBSERVATION_INVERSION_STUDY_V1",
        "status": "PASS",
        "scientific_claim_status": "see claims.csv; execution PASS is not identification PASS",
        "study_id": STUDY_ID,
        "protocol_digest": PROTOCOL_DIGEST,
        "realization_id": f"psr:dataset-realization:observation-inversion-independent@{realization_digest}",
        "realization": realization_payload,
        "realization_digest": realization_digest,
        "split": split,
        "split_digest": sha256_record(split),
        "rights": {
            "origin_class": "GENERATED_PUBLIC_ARTIFACT",
            "license_expression": "MIT; prose CC-BY-4.0",
            "owner": "Powerlifting State Research contributors",
            "access_conditions": None,
            "historical_private_artifacts_used": False,
        },
        "sources": {str(p): digest((root / p).read_bytes()) for p in sources},
        "outputs": {str(HOME / name): digest(content) for name, content in outputs.items()},
        "metric_cells": len(metrics),
        "entity_error_rows": len(errors),
        "paired_comparisons": len(comparisons),
    }
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    outputs = build_bundle(root)
    for name, content in outputs.items():
        path = root / HOME / name
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                raise ValueError(f"study replay mismatch: {name}")
        elif path.exists() and name != "README.md" and path.read_bytes() != content:
            raise ValueError(f"refusing divergent artifact overwrite: {name}")
    if not args.check:
        (root / HOME).mkdir(parents=True, exist_ok=True)
        for name, content in outputs.items():
            (root / HOME / name).write_bytes(content)
    print(f"PASS: {STUDY_ID}; deterministic replay and frozen M0-M5 integrity")


if __name__ == "__main__":
    main()
