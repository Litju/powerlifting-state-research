"""Isolated, observation-only learner for RES-290.

This module has no benchmark or evaluation imports. The evaluator stages this file alone,
starts it with isolated Python mode, and supplies only the frozen JSON allow-list on stdin.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any, cast

import numpy as np
from numpy import linalg as _linalg
from numpy import random as _random
from numpy.typing import NDArray

Array = NDArray[np.float64]
LIFTS = ("squat", "bench_press", "deadlift")
CHANNELS = ("assessment_kg", "prescribed_load_kg", "velocity_mps")
PLAN_IDS = ("cessation", "step_down", "continue", "step_up")
HORIZONS = (14, 28, 56)
TARGETS = tuple(f"{lift}_delta_capacity_kg" for lift in LIFTS)
QUERY_SETS = ("test_a", "test_b", "test_a_noise_replicate", "matched")
SUMMARY_ALPHAS = (0.1, 1.0, 10.0, 100.0)
RFF_GAMMAS = (0.01, 0.05, 0.2)
RFF_ALPHAS = (0.1, 1.0, 10.0)
RFF_COUNT = 128
RFF_SEED = 290190


def _keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} has unknown or missing fields")
    return cast(dict[str, Any], value)


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _validate_row(value: Any, targets_required: bool) -> dict[str, Any]:
    row = _keys(value, {"row_id", "inputs", *({"targets"} if targets_required else set())}, "row")
    if not isinstance(row["row_id"], str) or not row["row_id"]:
        raise ValueError("row_id must be a non-empty string")
    inputs = _keys(
        row["inputs"],
        {"entity_id", "origin_day", "horizon_days", "declared_future_plan", "lifts"},
        "inputs",
    )
    if inputs["entity_id"] != row["row_id"]:
        raise ValueError("row_id must equal entity_id")
    if inputs["origin_day"] != 224 or inputs["horizon_days"] not in HORIZONS:
        raise ValueError("input origin or horizon is outside the frozen schema")
    plan = _keys(
        inputs["declared_future_plan"],
        {"plan_id", "start_day", "end_day", "dose", "intensity"},
        "declared_future_plan",
    )
    expected_plans = {
        "cessation": 0.0,
        "step_down": 0.4,
        "continue": 0.8,
        "step_up": 1.2,
    }
    if plan["plan_id"] not in expected_plans:
        raise ValueError("future plan is outside the frozen declared plan categories")
    if (
        plan["start_day"] != 224
        or plan["end_day"] != 279
        or _finite(plan["dose"], "plan dose") != expected_plans[plan["plan_id"]]
        or _finite(plan["intensity"], "plan intensity") != 0.75
    ):
        raise ValueError("future plan fields are inconsistent with their declared category")
    lifts = _keys(inputs["lifts"], set(LIFTS), "lifts")
    for lift in LIFTS:
        lift_inputs = _keys(lifts[lift], {"history", "history_schedule"}, f"{lift} inputs")
        history = lift_inputs["history"]
        if not isinstance(history, list) or len(history) != 32:
            raise ValueError(f"{lift} history must contain 32 rows")
        for index, observation in enumerate(history):
            item = _keys(
                observation,
                {"day", "assessment_kg", "prescribed_load_kg", "velocity_mps"},
                f"{lift} observation",
            )
            if item["day"] != 6 + index * 7:
                raise ValueError(f"{lift} observation days are not the frozen weekly sequence")
            for channel in CHANNELS:
                _finite(item[channel], f"{lift}.{channel}")
        schedule = lift_inputs["history_schedule"]
        if not isinstance(schedule, list) or not schedule:
            raise ValueError(f"{lift} history schedule is empty")
        next_day = 0
        for segment in schedule:
            part = _keys(segment, {"start_day", "end_day", "dose", "intensity"}, "schedule segment")
            if part["start_day"] != next_day or part["end_day"] < next_day:
                raise ValueError(f"{lift} schedule contains a gap or overlap")
            if part["end_day"] > 223:
                raise ValueError(f"{lift} schedule exceeds the day-223 cutoff")
            pair = (
                _finite(part["dose"], "schedule dose"),
                _finite(part["intensity"], "schedule intensity"),
            )
            if pair not in {(0.0, 0.75), (0.4, 0.75), (0.8, 0.75), (1.2, 0.75)}:
                raise ValueError(f"{lift} schedule has an undeclared dose/intensity value")
            next_day = part["end_day"] + 1
        if next_day != 224:
            raise ValueError(f"{lift} schedule does not cover days 0 through 223")
    if targets_required:
        targets = _keys(row["targets"], set(TARGETS), "targets")
        for name in TARGETS:
            _finite(targets[name], name)
    return row


def _weekly_schedule(value: dict[str, Any]) -> Array:
    result = np.zeros((32, 2), dtype=np.float64)
    totals = np.zeros(32, dtype=np.float64)
    for segment in value["history_schedule"]:
        start = int(segment["start_day"])
        end = int(segment["end_day"])
        first = start // 7
        last = end // 7
        for week in range(first, last + 1):
            overlap = max(0, min(end + 1, (week + 1) * 7) - max(start, week * 7))
            result[week, 0] += overlap * float(segment["dose"]) / 7.0
            result[week, 1] += overlap * float(segment["intensity"]) / 7.0
            totals[week] += overlap
    if not np.all(totals == 7.0):
        raise ValueError("historical schedule cannot be aligned to the declared weekly bins")
    return result


def _plan_features(inputs: dict[str, Any]) -> list[float]:
    plan_id = inputs["declared_future_plan"]["plan_id"]
    horizon = inputs["horizon_days"]
    return [float(plan_id == value) for value in PLAN_IDS] + [
        float(horizon == value) for value in HORIZONS
    ]


def _summary_features(row: dict[str, Any]) -> Array:
    values: list[float] = []
    inputs = row["inputs"]
    time = np.arange(32, dtype=np.float64)
    centered_time = time - float(time.mean())
    denom = float(centered_time @ centered_time)
    for lift in LIFTS:
        observations = inputs["lifts"][lift]["history"]
        for channel in CHANNELS:
            series = np.asarray([item[channel] for item in observations], dtype=np.float64)
            values.extend(
                (float(series[-1]), float(series.mean()), float(centered_time @ series / denom))
            )
        schedule = _weekly_schedule(inputs["lifts"][lift])
        for channel_index in range(2):
            series = schedule[:, channel_index]
            values.extend(
                (
                    float(series.mean()),
                    float(series.std()),
                    float(series[-1]),
                    float(centered_time @ series / denom),
                )
            )
    values.extend(_plan_features(inputs))
    return np.asarray(values, dtype=np.float64)


def _sequence_features(row: dict[str, Any]) -> Array:
    inputs = row["inputs"]
    values: list[float] = []
    for lift in LIFTS:
        observations = inputs["lifts"][lift]["history"]
        for item in observations:
            values.extend(float(item[channel]) for channel in CHANNELS)
        values.extend(_weekly_schedule(inputs["lifts"][lift]).reshape(-1).tolist())
    values.extend(_plan_features(inputs))
    return np.asarray(values, dtype=np.float64)


def _design_stats(x: Array) -> tuple[Array, Array, Array]:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0.0] = 1.0
    return (x - mean) / scale, mean, scale


def _linear_fit(x: Array, y: Array, alpha: float) -> tuple[dict[str, Any], Array]:
    design, x_mean, x_scale = _design_stats(x)
    y_mean = y.mean(axis=0)
    y_scale = y.std(axis=0)
    y_scale[y_scale == 0.0] = 1.0
    response = (y - y_mean) / y_scale
    coefficients = _linalg.solve(
        design.T @ design + alpha * np.eye(design.shape[1], dtype=np.float64),
        design.T @ response,
    )
    state = {
        "x_mean": x_mean.tolist(),
        "x_scale": x_scale.tolist(),
        "y_mean": y_mean.tolist(),
        "y_scale": y_scale.tolist(),
        "coefficients": coefficients.tolist(),
        "alpha": alpha,
        "parameter_count": int(coefficients.size),
    }
    return state, _linear_predict(state, x)


def _linear_predict(state: dict[str, Any], x: Array) -> Array:
    z = (x - np.asarray(state["x_mean"])) / np.asarray(state["x_scale"])
    return np.asarray(
        z @ np.asarray(state["coefficients"]) * np.asarray(state["y_scale"])
        + np.asarray(state["y_mean"]),
        dtype=np.float64,
    )


def _selection_loss(prediction: Array, truth: Array, target_scale: Array) -> float:
    return float(np.mean(((prediction - truth) / target_scale) ** 2))


def _rff_map(x: Array, omega: Array, phase: Array) -> Array:
    return math.sqrt(2.0 / RFF_COUNT) * np.cos(x @ omega + phase)


def _target_matrix(rows: list[dict[str, Any]]) -> Array:
    return np.asarray([[float(row["targets"][target]) for target in TARGETS] for row in rows])


def _query_inputs(queries: list[dict[str, Any]], evaluation_set: str) -> list[dict[str, Any]]:
    return [query["row"] for query in queries if query["evaluation_set"] == evaluation_set]


def _predict_rff(state: dict[str, Any], rows: list[dict[str, Any]]) -> Array:
    x = np.asarray([_sequence_features(row) for row in rows], dtype=np.float64)
    z = (x - np.asarray(state["raw_mean"])) / np.asarray(state["raw_scale"])
    omega = np.asarray(state["omega"])
    phase = np.asarray(state["phase"])
    features = _rff_map(z, omega, phase)
    return _linear_predict(cast(dict[str, Any], state["response"]), features)


def _fit_request(request: dict[str, Any]) -> dict[str, Any]:
    fit_rows = [_validate_row(row, True) for row in request["fitting_rows"]]
    dev_rows = [_validate_row(row, True) for row in request["development_rows"]]
    queries: list[dict[str, Any]] = []
    for value in request["queries"]:
        item = _keys(value, {"evaluation_set", "row"}, "query")
        if item["evaluation_set"] not in QUERY_SETS:
            raise ValueError("unknown evaluation set")
        queries.append(
            {
                "evaluation_set": item["evaluation_set"],
                "row": _validate_row(item["row"], False),
            }
        )
    fit_ids = {row["row_id"] for row in fit_rows}
    dev_ids = {row["row_id"] for row in dev_rows}
    query_ids = {value["row"]["row_id"] for value in queries}
    if fit_ids & dev_ids or fit_ids & query_ids or dev_ids & query_ids:
        raise ValueError("fitting, development, and evaluation entity IDs must be disjoint")
    if len(query_ids) != len(queries):
        raise ValueError("evaluation row IDs must be unique across query sets")

    y_fit = _target_matrix(fit_rows)
    y_dev = _target_matrix(dev_rows)
    target_scale = y_fit.std(axis=0)
    target_scale[target_scale == 0.0] = 1.0
    evaluation_rows = {name: _query_inputs(queries, name) for name in QUERY_SETS}

    # Empirical finite-support baseline: conditional cell means plus a separate row sampler.
    cell_means: dict[str, list[float]] = {}
    for row, targets in zip(fit_rows, y_fit, strict=True):
        plan = row["inputs"]["declared_future_plan"]["plan_id"]
        horizon = row["inputs"]["horizon_days"]
        key = f"{plan}:{horizon}"
        if key not in cell_means:
            cell_means[key] = []
        cell_means[key].append(targets.tolist())
    empirical_state: dict[str, Any] = {
        key: np.asarray(values, dtype=np.float64).mean(axis=0).tolist()
        for key, values in sorted(cell_means.items())
    }

    # Summary Ridge: one predeclared development-selected alpha.
    x_fit_summary = np.asarray([_summary_features(row) for row in fit_rows])
    x_dev_summary = np.asarray([_summary_features(row) for row in dev_rows])
    summary_candidates: list[tuple[float, float, dict[str, Any]]] = []
    summary_attempts: list[dict[str, Any]] = []
    for alpha in SUMMARY_ALPHAS:
        try:
            candidate, _ = _linear_fit(x_fit_summary, y_fit, alpha)
            dev_prediction = _linear_predict(candidate, x_dev_summary)
            loss = _selection_loss(dev_prediction, y_dev, target_scale)
        except (_linalg.LinAlgError, FloatingPointError) as error:
            summary_attempts.append(
                {
                    "alpha": alpha,
                    "status": "MODEL_CONFIGURATION_FAILED",
                    "failure": type(error).__name__,
                }
            )
            continue
        summary_candidates.append((loss, alpha, candidate))
        summary_attempts.append({"alpha": alpha, "status": "COMPLETE", "standardized_mse": loss})
    summary_state: dict[str, Any] | None = None
    summary_alpha: float | None = None
    if summary_candidates:
        summary_loss, summary_alpha, summary_state = min(
            summary_candidates, key=lambda value: (value[0], SUMMARY_ALPHAS.index(value[1]))
        )
        summary_state["family"] = "summary_ridge_v1"
        summary_state["development_mse_standardized"] = summary_loss

    # Sequence RFF Ridge: fixed-size generic random features; selection uses development only.
    x_fit_sequence = np.asarray([_sequence_features(row) for row in fit_rows])
    x_dev_sequence = np.asarray([_sequence_features(row) for row in dev_rows])
    x_fit_standard, raw_mean, raw_scale = _design_stats(x_fit_sequence)
    x_dev_standard = (x_dev_sequence - raw_mean) / raw_scale
    rff_candidates: list[tuple[float, float, float, dict[str, Any]]] = []
    rff_attempts: list[dict[str, Any]] = []
    for gamma_index, gamma in enumerate(RFF_GAMMAS):
        try:
            rng = _random.default_rng(RFF_SEED + gamma_index)
            omega = rng.normal(0.0, math.sqrt(2.0 * gamma), (x_fit_standard.shape[1], RFF_COUNT))
            phase = rng.uniform(0.0, 2.0 * math.pi, RFF_COUNT)
            fit_features = _rff_map(x_fit_standard, omega, phase)
            dev_features = _rff_map(x_dev_standard, omega, phase)
        except (ValueError, FloatingPointError) as error:
            rff_attempts.extend(
                {
                    "gamma": gamma,
                    "alpha": alpha,
                    "status": "MODEL_CONFIGURATION_FAILED",
                    "failure": type(error).__name__,
                }
                for alpha in RFF_ALPHAS
            )
            continue
        for alpha in RFF_ALPHAS:
            try:
                response_state, _ = _linear_fit(fit_features, y_fit, alpha)
                dev_prediction = _linear_predict(response_state, dev_features)
                loss = _selection_loss(dev_prediction, y_dev, target_scale)
            except (_linalg.LinAlgError, FloatingPointError) as error:
                rff_attempts.append(
                    {
                        "gamma": gamma,
                        "alpha": alpha,
                        "status": "MODEL_CONFIGURATION_FAILED",
                        "failure": type(error).__name__,
                    }
                )
                continue
            candidate_state: dict[str, Any] = {
                "family": "sequence_rff_ridge_v1",
                "raw_mean": raw_mean.tolist(),
                "raw_scale": raw_scale.tolist(),
                "omega": omega.tolist(),
                "phase": phase.tolist(),
                "gamma": gamma,
                "alpha": alpha,
                "response": response_state,
                "parameter_count": int(
                    omega.size + phase.size + np.asarray(response_state["coefficients"]).size
                ),
            }
            rff_candidates.append((loss, gamma, alpha, candidate_state))
            rff_attempts.append(
                {
                    "gamma": gamma,
                    "alpha": alpha,
                    "status": "COMPLETE",
                    "standardized_mse": loss,
                }
            )
    rff_state: dict[str, Any] | None = None
    rff_gamma: float | None = None
    rff_alpha: float | None = None
    if rff_candidates:
        rff_loss, rff_gamma, rff_alpha, rff_state = min(
            rff_candidates,
            key=lambda value: (
                value[0],
                RFF_GAMMAS.index(value[1]),
                RFF_ALPHAS.index(value[2]),
            ),
        )
        rff_state["development_mse_standardized"] = rff_loss

    def predict(method: str, rows: list[dict[str, Any]]) -> Array:
        if not rows:
            return np.empty((0, len(TARGETS)), dtype=np.float64)
        if method == "empirical_finite_support_resampler_v1":
            return np.asarray(
                [
                    empirical_state[
                        f"{row['inputs']['declared_future_plan']['plan_id']}:{row['inputs']['horizon_days']}"
                    ]
                    for row in rows
                ],
                dtype=np.float64,
            )
        if method == "summary_ridge_v1":
            if summary_state is None:
                raise ValueError("summary Ridge has no successful configuration")
            x = np.asarray([_summary_features(row) for row in rows])
            return _linear_predict(summary_state, x)
        if method == "sequence_rff_ridge_v1":
            if rff_state is None:
                raise ValueError("sequence RFF Ridge has no successful configuration")
            return _predict_rff(rff_state, rows)
        raise ValueError(f"unknown model family: {method}")

    requested_methods = (
        "empirical_finite_support_resampler_v1",
        "summary_ridge_v1",
        "sequence_rff_ridge_v1",
    )
    method_names = tuple(
        method
        for method in requested_methods
        if method == "empirical_finite_support_resampler_v1"
        or (method == "summary_ridge_v1" and summary_state is not None)
        or (method == "sequence_rff_ridge_v1" and rff_state is not None)
    )
    predictions: list[dict[str, Any]] = []
    for evaluation_set in QUERY_SETS:
        rows = evaluation_rows[evaluation_set]
        for method in method_names:
            predicted = predict(method, rows)
            for row, output in zip(rows, predicted, strict=True):
                predictions.append(
                    {
                        "evaluation_set": evaluation_set,
                        "row_id": row["row_id"],
                        "method": method,
                        "targets": {
                            target: float(output[index]) for index, target in enumerate(TARGETS)
                        },
                    }
                )

    # Sample full observable records only from the empirical row-resampling baseline.
    fit_groups: dict[str, list[dict[str, Any]]] = {}
    for row in fit_rows:
        plan = row["inputs"]["declared_future_plan"]["plan_id"]
        horizon = row["inputs"]["horizon_days"]
        fit_groups.setdefault(f"{plan}:{horizon}", []).append(row)
    sample_rng = _random.default_rng(int(request["seeds"]["empirical_resampling"]))
    empirical_sample: list[dict[str, Any]] = []
    for key in sorted(fit_groups):
        donors = fit_groups[key]
        draw_indices = sample_rng.integers(0, len(donors), size=len(donors))
        for donor_index in draw_indices:
            donor = donors[int(donor_index)]
            sample_number = len(empirical_sample)
            sample_id = f"empirical-sample-{sample_number:06d}"
            inputs = dict(donor["inputs"])
            inputs["entity_id"] = sample_id
            empirical_sample.append(
                {
                    "sample_id": sample_id,
                    "donor_row_id": donor["row_id"],
                    "inputs": inputs,
                }
            )

    fitted_models: dict[str, Any] = {
        "empirical_finite_support_resampler_v1": {
            "family": "empirical_finite_support_resampler_v1",
            "cell_mean_targets_kg": empirical_state,
            "fitting_row_count": len(fit_rows),
            "parameter_count": 0,
        }
    }
    method_failures: list[dict[str, Any]] = []
    if summary_state is None:
        method_failures.append(
            {
                "family": "summary_ridge_v1",
                "status": "MODEL_FIT_FAILED",
                "attempts": summary_attempts,
            }
        )
    else:
        fitted_models["summary_ridge_v1"] = {
            **summary_state,
            "selected_alpha": summary_alpha,
            "fitting_row_count": len(fit_rows),
            "development_row_count": len(dev_rows),
        }
    if rff_state is None:
        method_failures.append(
            {
                "family": "sequence_rff_ridge_v1",
                "status": "MODEL_FIT_FAILED",
                "attempts": rff_attempts,
            }
        )
    else:
        fitted_models["sequence_rff_ridge_v1"] = {
            **rff_state,
            "selected_gamma": rff_gamma,
            "selected_alpha": rff_alpha,
            "fitting_row_count": len(fit_rows),
            "development_row_count": len(dev_rows),
        }

    return {
        "protocol_id": request["protocol_id"],
        "learner_runtime": {"numpy": np.__version__, "python": sys.version.split()[0]},
        "fitted_models": fitted_models,
        "method_failures": method_failures,
        "development_selection": {
            "summary_ridge_v1": summary_attempts,
            "sequence_rff_ridge_v1": rff_attempts,
        },
        "predictions": predictions,
        "empirical_sample": empirical_sample,
    }


def _restrict_runtime() -> None:
    blocked = {
        "open",
        "os.open",
        "os.listdir",
        "os.scandir",
        "os.chdir",
        "os.remove",
        "os.rename",
        "os.mkdir",
        "os.rmdir",
        "os.link",
        "os.symlink",
        "subprocess.Popen",
        "os.system",
        "socket.connect",
        "socket.getaddrinfo",
    }

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event in blocked:
            raise PermissionError(f"learner runtime blocked {event}")
        if event == "import" and args and str(args[0]).startswith("powerlifting_state_research"):
            raise PermissionError("learner runtime blocked repository imports")

    sys.addaudithook(audit)


def main() -> None:
    _restrict_runtime()
    request = json.load(sys.stdin)
    request = _keys(
        request,
        {"protocol_id", "fitting_rows", "development_rows", "queries", "seeds"},
        "request",
    )
    if not isinstance(request["protocol_id"], str) or not request["protocol_id"]:
        raise ValueError("protocol_id is required")
    seeds = _keys(request["seeds"], {"empirical_resampling"}, "seeds")
    _finite(seeds["empirical_resampling"], "empirical resampling seed")
    result = _fit_request(request)
    json.dump(
        result,
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
