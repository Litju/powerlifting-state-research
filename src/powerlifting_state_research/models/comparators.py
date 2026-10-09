"""Frozen public-native comparators for the RES-275 IID model frontier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor, nn

from .. import __version__
from ..artifacts.manifests import RightsMetadata
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset,
    evaluate,
    interventions,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (
    bounded_training_stimulus,
)
from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..evaluation.identity import EVALUATION_ID, METRIC_IDENTITIES, QOI_ID, TARGETS, TASK_ID
from ..evaluation.metrics import MetricName
from ..evaluation.prediction import PredictionRow, canonical_prediction_jsonl
from ..evaluation.protocols import EvaluationResult
from ..models.references import (
    DeterminismStatus,
    EnvironmentProvenance,
    FittedInstanceReference,
    RNGProvenance,
    TrainingProtocolReference,
)
from ..models.temporal_expert import NormalizationStats, TemporalModelInput, prepare_batch
from ..models.training import (
    COMPARATOR_TRAINING_PROTOCOL_ID,
)
from ..models.training import (
    PUBLIC_NATIVE_COMPARATOR_PROTOCOL as PROTOCOL,
)
from .train_temporal_expert import (
    _read_train_rows,
    configure_determinism,
    make_internal_split,
)

FloatArray = NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = (
    ROOT
    / "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production"
)
MANIFEST_PATH = (
    ROOT / "data/manifests/realizations/"
    "latent_capacity_change_with_transient_expression_forecasting/iid-production.json"
)
OUTPUT_ROOT = (
    ROOT / "results/benchmarks/"
    "iid_latent_capacity_change_with_transient_expression_forecasting/public-native-comparator-suite"
)
FITTED_ROOT = ROOT / "models/fitted-instances/public-native-comparator-suite"
REGISTRY_PATH = ROOT / "artifacts/registries/public-native-comparator-registry.json"
RUN_MANIFEST_PATH = ROOT / "results/manifests/public-native-comparator-suite.json"
CHECKSUM_INDEX_PATH = ROOT / "results/manifests/public-native-comparator-suite-checksums.json"
TARGET_METRICS_PATH = ROOT / "results/tables/public-native-comparator-frontier.csv"
TRAIN_SHA256 = PROTOCOL.train_sha256
VALIDATION_SHA256 = PROTOCOL.validation_sha256
SEEDS = PROTOCOL.seeds
FEATURE_COUNT = 127
OUTPUT_RIGHTS = RightsMetadata(
    "MIT",
    "Powerlifting State Research contributors",
    "Repository-generated comparator artifacts; redistribution permitted under the repository "
    "license.",
)


@dataclass(frozen=True, slots=True)
class ComparatorModelSpec:
    method: str
    slug: str
    model_id: str
    semantics: dict[str, object]


@dataclass(frozen=True, slots=True)
class FittedComparator:
    model_state: dict[str, Any]
    parameter_count: int
    fixed_constant_count: int
    selection_loss: float | None
    selected_steps: int | None


@dataclass(frozen=True, slots=True)
class FitRecord:
    model: ComparatorModelSpec
    seed: int
    fitted_instance_id: str
    fitted_instance_sha256: str
    fitted_instance_path: str
    training_receipt: dict[str, object]


_METHOD_CONFIGS = {name: dict(settings) for name, settings in PROTOCOL.comparator_methods}


def model_semantics(method: str) -> dict[str, object]:
    if method not in _METHOD_CONFIGS:
        raise ValueError(f"unknown standardized comparator: {method}")
    configuration = {
        key: repr(value) if isinstance(value, float) else value
        for key, value in _METHOD_CONFIGS[method].items()
    }
    return {
        "classification": "NEW_STANDARDIZED_COMPARATOR",
        "task_id": TASK_ID,
        "qoi_id": QOI_ID,
        "input_semantics": PROTOCOL.participant_visible_input,
        "feature_representation": PROTOCOL.feature_representation,
        "output_targets": TARGETS,
        "output_unit": "kg",
        "method": method,
        "configuration": configuration,
    }


def _model_spec(method: str) -> ComparatorModelSpec:
    semantics = model_semantics(method)
    slug = f"public-native-{method.replace('_', '-')}"
    digest = sha256_record(
        {
            "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
            "component_class": "model",
            "slug": slug,
            "version": "1.0.0",
            "semantics": semantics,
        },
        reject_floats=True,
    )
    model_id = f"psr:model:{slug}@1.0.0~{digest[7:19]}"
    return ComparatorModelSpec(method, slug, model_id, semantics)


MODEL_SPECS = tuple(_model_spec(name) for name, _ in PROTOCOL.comparator_methods)
MODEL_BY_METHOD = {item.method: item for item in MODEL_SPECS}


def _target_matrix(rows: tuple[dataset.PublicForecastRow, ...]) -> FloatArray:
    return np.asarray(
        [
            (
                row.targets["squat_delta_capacity_kg"],
                row.targets["bench_press_delta_capacity_kg"],
                row.targets["deadlift_delta_capacity_kg"],
            )
            for row in rows
        ],
        dtype=np.float64,
    )


def feature_matrix(
    rows: tuple[dataset.PublicForecastRow, ...], stats: NormalizationStats
) -> FloatArray:
    """Build the fixed 127-value visible-history summary, with no IDs or targets."""
    if not rows:
        raise ValueError("feature matrix requires at least one row")
    model_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in rows
    )
    prepared = prepare_batch(model_inputs, stats).tensors
    history = prepared.history.detach().cpu().numpy().astype(np.float64, copy=False)
    plan = prepared.plan_numeric.detach().cpu().numpy().astype(np.float64, copy=False)
    plan_index = prepared.plan_index.detach().cpu().numpy()
    output = np.empty((len(rows), FEATURE_COUNT), dtype=np.float64)
    times = np.arange(32, dtype=np.float64)
    centered_time = times - times.mean()
    denominator = float(centered_time @ centered_time)
    for row_index in range(len(rows)):
        values: list[float] = []
        for lift_index in range(3):
            observed = history[row_index, lift_index, :, :6]
            for channel_index in range(6):
                series = observed[:, channel_index]
                slope = float(centered_time @ (series - series.mean()) / denominator)
                values.extend(
                    (
                        float(series[0]),
                        float(series[-1]),
                        float(series.mean()),
                        float(series.std(ddof=0)),
                        slope,
                    )
                )
            schedule = history[row_index, lift_index, :, 6:9]
            for channel_index in range(3):
                values.extend(
                    (
                        float(schedule[:, channel_index].mean()),
                        float(schedule[-4:, channel_index].mean()),
                        float(schedule[-1, channel_index]),
                    )
                )
        values.extend(float(value) for value in plan[row_index])
        values.extend(float(value) for value in np.eye(4, dtype=np.float64)[plan_index[row_index]])
        if len(values) != FEATURE_COUNT:
            raise AssertionError(f"feature transform emitted {len(values)} values, expected 127")
        output[row_index] = values
    if not np.isfinite(output).all():
        raise ValueError("participant-visible feature matrix must be finite")
    return output


def _standardize_features(
    fit: FloatArray, other: FloatArray
) -> tuple[FloatArray, FloatArray, tuple[FloatArray, FloatArray]]:
    mean = fit.mean(axis=0)
    scale = np.maximum(fit.std(axis=0, ddof=0), 1e-6)
    return (fit - mean) / scale, (other - mean) / scale, (mean, scale)


def _mse(prediction: FloatArray, truth: FloatArray) -> float:
    return float(np.mean(np.square(prediction - truth)))


def _fit_ridge(features: FloatArray, targets: FloatArray, alpha: float) -> dict[str, object]:
    feature_mean = features.mean(axis=0)
    centered_features = features - feature_mean
    target_mean = targets.mean(axis=0)
    centered_targets = targets - target_mean
    coefficients = np.linalg.solve(
        centered_features.T @ centered_features + alpha * np.eye(features.shape[1]),
        centered_features.T @ centered_targets,
    )
    intercept = target_mean - feature_mean @ coefficients
    return {
        "coefficients": coefficients.tolist(),
        "intercept": intercept.tolist(),
        "alpha": alpha,
    }


def _ridge_predict(features: FloatArray, state: dict[str, Any]) -> FloatArray:
    coefficients = np.asarray(state["coefficients"], dtype=np.float64)
    intercept = np.asarray(state["intercept"], dtype=np.float64)
    return features @ coefficients + intercept


def _fit_stump(
    features: FloatArray,
    residual: FloatArray,
    thresholds: tuple[FloatArray, ...],
    orders: tuple[NDArray[np.int64], ...],
    sorted_values: tuple[FloatArray, ...],
) -> tuple[int, float, float, float]:
    best_score = -1.0
    best: tuple[int, float, float, float] | None = None
    total = float(residual.sum())
    cumulative = tuple(np.cumsum(residual[order]) for order in orders)
    for feature_index, cuts in enumerate(thresholds):
        if cuts.size == 0:
            continue
        counts = np.searchsorted(sorted_values[feature_index], cuts, side="right")
        valid = (counts > 0) & (counts < residual.size)
        if not valid.any():
            continue
        valid_cuts = cuts[valid]
        valid_counts = counts[valid]
        left_sums = cumulative[feature_index][valid_counts - 1]
        right_sums = total - left_sums
        scores = np.square(left_sums) / valid_counts + np.square(right_sums) / (
            residual.size - valid_counts
        )
        local_index = int(np.argmax(scores))
        score = float(scores[local_index])
        if score > best_score + 1e-12:
            count = int(valid_counts[local_index])
            best_score = score
            best = (
                feature_index,
                float(valid_cuts[local_index]),
                float(left_sums[local_index] / count),
                float(right_sums[local_index] / (residual.size - count)),
            )
    if best is None:
        return -1, 0.0, 0.0, 0.0
    return best


def _stump_values(features: FloatArray, stump: tuple[int, float, float, float]) -> FloatArray:
    feature_index, threshold, left, right = stump
    if feature_index < 0:
        return np.zeros(features.shape[0], dtype=np.float64)
    return np.where(features[:, feature_index] <= threshold, left, right)


def _fit_boosted_stumps(
    fit_features: FloatArray,
    fit_targets: FloatArray,
    selection_features: FloatArray,
    selection_targets: FloatArray,
    *,
    learning_rate: float = 0.05,
    maximum_rounds: int = 40,
) -> tuple[dict[str, object], float, int]:
    cuts_by_feature = tuple(
        np.unique(np.quantile(fit_features[:, index], np.arange(1, 16, dtype=np.float64) / 16.0))
        for index in range(fit_features.shape[1])
    )
    thresholds = tuple(
        cuts[(cuts > fit_features[:, index].min()) & (cuts < fit_features[:, index].max())]
        for index, cuts in enumerate(cuts_by_feature)
    )
    orders = tuple(
        np.argsort(fit_features[:, index], kind="stable").astype(np.int64, copy=False)
        for index in range(fit_features.shape[1])
    )
    sorted_values = tuple(fit_features[order, index] for index, order in enumerate(orders))
    base = fit_targets.mean(axis=0)
    fit_prediction = np.broadcast_to(base, fit_targets.shape).copy()
    selection_prediction = np.broadcast_to(base, selection_targets.shape).copy()
    best_loss = _mse(selection_prediction, selection_targets)
    best_round = 0
    last_improvement = 0
    best_trees: list[list[tuple[int, float, float, float]]] = [[], [], []]
    trees: list[list[tuple[int, float, float, float]]] = [[], [], []]
    for round_index in range(1, maximum_rounds + 1):
        for target_index in range(3):
            residual = fit_targets[:, target_index] - fit_prediction[:, target_index]
            stump = _fit_stump(fit_features, residual, thresholds, orders, sorted_values)
            trees[target_index].append(stump)
            fit_prediction[:, target_index] += learning_rate * _stump_values(fit_features, stump)
            selection_prediction[:, target_index] += learning_rate * _stump_values(
                selection_features, stump
            )
        selection_loss = _mse(selection_prediction, selection_targets)
        if selection_loss < best_loss - 1e-4:
            best_loss = selection_loss
            best_round = round_index
            last_improvement = round_index
            best_trees = [list(target_stumps) for target_stumps in trees]
        if round_index - last_improvement >= 8:
            break
    state = {
        "base": base.tolist(),
        "learning_rate": learning_rate,
        "trees_by_target": [
            [[feature, threshold, left, right] for feature, threshold, left, right in stumps]
            for stumps in best_trees
        ],
        "selected_rounds": best_round,
        "selection_loss": best_loss,
    }
    return state, best_loss, best_round


def _boosted_stumps_predict(features: FloatArray, state: dict[str, Any]) -> FloatArray:
    output = np.broadcast_to(np.asarray(state["base"], dtype=np.float64), (len(features), 3)).copy()
    learning_rate = float(state["learning_rate"])
    for target_index, stumps in enumerate(cast(list[list[list[Any]]], state["trees_by_target"])):
        for values in stumps:
            stump = (int(values[0]), float(values[1]), float(values[2]), float(values[3]))
            output[:, target_index] += learning_rate * _stump_values(features, stump)
    return output


def _mechanistic_predictions(
    rows: tuple[dataset.PublicForecastRow, ...], parameters: dict[str, Any] | None = None
) -> FloatArray:
    fixed = parameters or cast(dict[str, Any], _METHOD_CONFIGS["mechanistic_midpoint"])
    reference_stimulus = float(fixed["reference_stimulus"])
    reference_dose_product = float(fixed["reference_dose_product"])
    adaptation_gain = float(fixed["adaptation_utilization"]) / reference_stimulus
    adaptation_time = -28.0 / math.log(1.0 - float(fixed["adaptation_retention_28d"]))
    suppression_gain = float(fixed["suppression_utilization"]) / reference_stimulus
    suppression_time = -1.0 / math.log(float(fixed["suppression_retention"]))
    stimulus_reference = reference_dose_product * (1.0 - reference_stimulus) / reference_stimulus
    alpha_adaptation = math.exp(-1.0 / adaptation_time)
    alpha_suppression = math.exp(-1.0 / suppression_time)
    predictions = np.empty((len(rows), 3), dtype=np.float64)
    for row_index, row in enumerate(rows):
        lifts = (
            row.inputs.lifts["squat"],
            row.inputs.lifts["bench_press"],
            row.inputs.lifts["deadlift"],
        )
        for lift_index, lift in enumerate(lifts):
            adaptation = 0.0
            suppression = 0.0
            segment_index = 0
            for day in range(interventions.ORIGIN_DAY):
                while lift.history_schedule[segment_index].end_day < day:
                    segment_index += 1
                segment = lift.history_schedule[segment_index]
                stimulus = bounded_training_stimulus(
                    segment.dose, segment.intensity, stimulus_reference
                )
                adaptation = alpha_adaptation * adaptation + (1.0 - alpha_adaptation) * stimulus
                suppression = alpha_suppression * suppression + (1.0 - alpha_suppression) * stimulus
            assessment = lift.history[-1].assessment_kg
            expression_fraction = (1.0 + adaptation_gain * adaptation) * (
                1.0 - suppression_gain * suppression
            )
            baseline = assessment / expression_fraction
            adaptation_at_origin = adaptation
            plan = row.inputs.declared_future_plan
            for _ in range(row.inputs.horizon_days):
                stimulus = bounded_training_stimulus(plan.dose, plan.intensity, stimulus_reference)
                adaptation = alpha_adaptation * adaptation + (1.0 - alpha_adaptation) * stimulus
                suppression = alpha_suppression * suppression + (1.0 - alpha_suppression) * stimulus
            predictions[row_index, lift_index] = (
                baseline * adaptation_gain * (adaptation - adaptation_at_origin)
            )
    if not np.isfinite(predictions).all():
        raise ValueError("mechanistic comparator produced a non-finite prediction")
    return predictions


def _fit_neural(
    fit_features: FloatArray,
    fit_targets: FloatArray,
    selection_features: FloatArray,
    selection_targets: FloatArray,
    seed: int,
) -> tuple[dict[str, object], float, int]:
    configure_determinism(seed)
    torch.set_num_threads(1)
    model = nn.Sequential(nn.Linear(FEATURE_COUNT, 32), nn.ReLU(), nn.Linear(32, 3))
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    x_fit = torch.tensor(fit_features, dtype=torch.float32)
    y_fit = torch.tensor(fit_targets, dtype=torch.float32)
    x_selection = torch.tensor(selection_features, dtype=torch.float32)
    y_selection = torch.tensor(selection_targets, dtype=torch.float32)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    best_loss = math.inf
    best_epoch = 0
    last_improvement = 0
    best_state: dict[str, Tensor] = {}
    for epoch in range(1, 61):
        model.train()
        order = torch.randperm(len(x_fit), generator=generator)
        for start in range(0, len(order), 256):
            batch = order[start : start + 256]
            optimizer.zero_grad(set_to_none=True)
            loss = torch.mean(torch.square(model(x_fit[batch]) - y_fit[batch]))
            loss.backward()  # type: ignore[no-untyped-call]
            optimizer.step()
        model.eval()
        with torch.inference_mode():
            selection_loss = float(torch.mean(torch.square(model(x_selection) - y_selection)))
        if selection_loss < best_loss - 1e-4:
            best_loss = selection_loss
            best_epoch = epoch
            last_improvement = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
        if epoch - last_improvement >= 10:
            break
    if not best_state:
        raise ValueError("neural comparator did not produce a selected state")
    model.load_state_dict(best_state)
    weights = model.state_dict()
    state = {
        "weights_1": weights["0.weight"].numpy().astype(np.float64).tolist(),
        "bias_1": weights["0.bias"].numpy().astype(np.float64).tolist(),
        "weights_2": weights["2.weight"].numpy().astype(np.float64).tolist(),
        "bias_2": weights["2.bias"].numpy().astype(np.float64).tolist(),
        "selected_epoch": best_epoch,
        "selection_loss": best_loss,
    }
    return state, best_loss, best_epoch


def _neural_predict(features: FloatArray, state: dict[str, Any]) -> FloatArray:
    first_weight = torch.tensor(state["weights_1"], dtype=torch.float32)
    first_bias = torch.tensor(state["bias_1"], dtype=torch.float32)
    second_weight = torch.tensor(state["weights_2"], dtype=torch.float32)
    second_bias = torch.tensor(state["bias_2"], dtype=torch.float32)
    x = torch.tensor(features, dtype=torch.float32)
    with torch.inference_mode():
        hidden = torch.relu(x @ first_weight.T + first_bias)
        return cast(FloatArray, (hidden @ second_weight.T + second_bias).numpy().astype(np.float64))


def fit_comparator(
    method: str,
    fit_rows: tuple[dataset.PublicForecastRow, ...],
    selection_rows: tuple[dataset.PublicForecastRow, ...],
    fit_features: FloatArray,
    selection_features: FloatArray,
    fit_targets: FloatArray,
    selection_targets: FloatArray,
    feature_mean: FloatArray,
    feature_scale: FloatArray,
    target_mean: FloatArray,
    target_scale: FloatArray,
    seed: int,
) -> FittedComparator:
    """Fit one frozen configuration; only tree/neural stopping reads selection rows."""
    x_fit = (fit_features - feature_mean) / feature_scale
    x_selection = (selection_features - feature_mean) / feature_scale
    y_fit = (fit_targets - target_mean) / target_scale
    y_selection = (selection_targets - target_mean) / target_scale
    config = _METHOD_CONFIGS[method]
    selection_loss: float | None = None
    selected_steps: int | None = None
    parameter_count = 0
    fixed_constant_count = 0
    if method == "context_mean":
        groups: dict[str, list[FloatArray]] = {}
        for row, target in zip(fit_rows, fit_targets, strict=True):
            key = f"{row.inputs.declared_future_plan.plan_id}|{row.inputs.horizon_days}"
            groups.setdefault(key, []).append(target)
        if len(groups) != 12:
            raise ValueError("context baseline requires all 12 frozen plan/horizon groups in FIT")
        state: dict[str, Any] = {
            "group_means": {
                key: np.stack(values).mean(axis=0).tolist() for key, values in groups.items()
            }
        }
        parameter_count = len(groups) * len(TARGETS)
    elif method == "ridge":
        state = _fit_ridge(x_fit, y_fit, float(cast(float, config["alpha"])))
        parameter_count = FEATURE_COUNT * len(TARGETS) + len(TARGETS)
    elif method == "histogram_boosted_stumps":
        state, selection_loss, selected_steps = _fit_boosted_stumps(
            x_fit,
            y_fit,
            x_selection,
            y_selection,
            learning_rate=float(cast(float, config["learning_rate"])),
            maximum_rounds=int(cast(int, config["maximum_rounds"])),
        )
        stumps = sum(
            len(target_stumps) for target_stumps in cast(list[list[Any]], state["trees_by_target"])
        )
        parameter_count = len(TARGETS) + 3 * stumps
    elif method == "mechanistic_midpoint":
        fixed_parameters = {
            key: config[key]
            for key in (
                "reference_stimulus",
                "reference_dose_product",
                "adaptation_utilization",
                "adaptation_retention_28d",
                "suppression_utilization",
                "suppression_retention",
            )
        }
        state = {"fixed_parameters": fixed_parameters}
        fixed_constant_count = 6
    elif method == "compact_neural":
        state, selection_loss, selected_steps = _fit_neural(
            x_fit, y_fit, x_selection, y_selection, seed
        )
        parameter_count = FEATURE_COUNT * 32 + 32 + 32 * 3 + 3
    elif method == "mechanistic_ridge_residual":
        base = _mechanistic_predictions(fit_rows)
        residual = (fit_targets - base) / target_scale
        state = {
            "residual_ridge": _fit_ridge(x_fit, residual, float(cast(float, config["alpha"]))),
            "mechanistic_parameters": {
                key: _METHOD_CONFIGS["mechanistic_midpoint"][key]
                for key in (
                    "reference_stimulus",
                    "reference_dose_product",
                    "adaptation_utilization",
                    "adaptation_retention_28d",
                    "suppression_utilization",
                    "suppression_retention",
                )
            },
        }
        parameter_count = FEATURE_COUNT * len(TARGETS) + len(TARGETS)
        fixed_constant_count = 6
    else:
        raise ValueError(f"unknown standardized comparator: {method}")
    if not np.isfinite(target_mean).all() or not np.isfinite(target_scale).all():
        raise ValueError("fitting target normalization must be finite")
    state["feature_mean"] = feature_mean.tolist()
    state["feature_scale"] = feature_scale.tolist()
    state["target_mean"] = target_mean.tolist()
    state["target_scale"] = target_scale.tolist()
    return FittedComparator(
        state, parameter_count, fixed_constant_count, selection_loss, selected_steps
    )


def predict_comparator(
    method: str,
    state: dict[str, Any],
    rows: tuple[dataset.PublicForecastRow, ...],
    raw_features: FloatArray,
) -> FloatArray:
    model_state = cast(dict[str, Any], state["model_state"])
    feature_mean = np.asarray(model_state["feature_mean"], dtype=np.float64)
    feature_scale = np.asarray(model_state["feature_scale"], dtype=np.float64)
    target_mean = np.asarray(model_state["target_mean"], dtype=np.float64)
    target_scale = np.asarray(model_state["target_scale"], dtype=np.float64)
    features = (raw_features - feature_mean) / feature_scale
    if method == "context_mean":
        groups = cast(dict[str, list[float]], model_state["group_means"])
        output = np.asarray(
            [
                groups[f"{row.inputs.declared_future_plan.plan_id}|{row.inputs.horizon_days}"]
                for row in rows
            ],
            dtype=np.float64,
        )
    elif method == "ridge":
        output = _ridge_predict(features, model_state) * target_scale + target_mean
    elif method == "histogram_boosted_stumps":
        output = _boosted_stumps_predict(features, model_state) * target_scale + target_mean
    elif method == "mechanistic_midpoint":
        output = _mechanistic_predictions(
            rows, cast(dict[str, Any], model_state["fixed_parameters"])
        )
    elif method == "compact_neural":
        output = _neural_predict(features, model_state) * target_scale + target_mean
    elif method == "mechanistic_ridge_residual":
        residual_z = _ridge_predict(features, cast(dict[str, Any], model_state["residual_ridge"]))
        output = (
            _mechanistic_predictions(
                rows, cast(dict[str, Any], model_state["mechanistic_parameters"])
            )
            + residual_z * target_scale
        )
    else:
        raise ValueError(f"unknown standardized comparator: {method}")
    if output.shape != (len(rows), len(TARGETS)) or not np.isfinite(output).all():
        raise ValueError("comparator output must be finite with three target columns")
    return output


def _source_identity() -> dict[str, str]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise ValueError("comparator training requires a clean source checkout")
    return {"code_sha": head, "worktree_status": "clean"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> str:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(payload)
    return _sha256(payload)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return cast(dict[str, Any], value)


def _runtime_provenance() -> tuple[EnvironmentProvenance, dict[str, object]]:
    try:
        cpu = platform.processor() or "unknown CPU"
    except OSError:
        cpu = "unknown CPU"
    dependency_facts = {
        "package": f"powerlifting-state-research=={__version__}",
        "numpy": np.__version__,
        "torch": torch.__version__,
        "device": "cpu",
    }
    environment = EnvironmentProvenance(
        environment_id=f"psr:comparator-environment@{sha256_record(dependency_facts)}",
        python_version=platform.python_version(),
        platform=f"{platform.system()}-{platform.machine()}",
        dependency_identity=";".join(f"{key}={value}" for key, value in dependency_facts.items()),
        hardware=cpu,
    )
    return environment, {
        **dependency_facts,
        "platform": platform.platform(),
        "cpu": cpu,
        "logical_cpu_count": os.cpu_count(),
    }


def _load_expert_results() -> tuple[list[dict[str, object]], dict[str, str]]:
    manifest_path = ROOT / "results/manifests/public-native-temporal-expert.json"
    checksums_path = ROOT / "results/manifests/public-native-temporal-expert-checksums.json"
    manifest = _read_json(manifest_path)
    checksums = _read_json(checksums_path)
    records: list[dict[str, object]] = []
    hashes: dict[str, str] = {}
    for entry in cast(list[dict[str, Any]], checksums["copied_artifacts"]):
        path = str(entry["path"])
        digest = str(entry["sha256"])
        file_path = ROOT / path
        if _sha256(file_path.read_bytes()) != digest:
            raise ValueError(f"immutable RES-274 artifact hash mismatch: {path}")
        hashes[path] = digest
    scientific_identity = cast(dict[str, Any], manifest.get("scientific_identity", {}))
    if scientific_identity.get("model_id") != (
        "psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f"
    ):
        raise ValueError("RES-274 immutable model identity changed")
    if scientific_identity.get("evaluation_id") != EVALUATION_ID:
        raise ValueError("RES-274 immutable evaluator identity changed")
    result_root = (
        ROOT / "results/benchmarks/"
        "iid_latent_capacity_change_with_transient_expression_forecasting/public-native-temporal-expert"
    )
    for seed in SEEDS:
        result_path = result_root / f"seed-{seed}.evaluation-result.json"
        envelope = _read_json(result_path)
        result = cast(dict[str, Any], envelope.get("result", envelope))
        record = _result_rows(result, "public-native-temporal-expert", str(seed), None, None)
        if (
            envelope.get("result_id", record["evaluation_result_id"])
            != record["evaluation_result_id"]
        ):
            raise ValueError("RES-274 result identity does not match its canonical content")
        records.append(record)
    ensemble_path = result_root / "ensemble.evaluation-result.json"
    envelope = _read_json(ensemble_path)
    result = cast(dict[str, Any], envelope.get("result", envelope))
    record = _result_rows(result, "public-native-temporal-expert", "ensemble", None, None)
    if envelope.get("result_id", record["evaluation_result_id"]) != record["evaluation_result_id"]:
        raise ValueError("RES-274 ensemble result identity does not match its canonical content")
    records.append(record)
    return records, hashes


def _result_rows(
    result: dict[str, Any],
    method: str,
    seed: str,
    fitted_instance_id: str | None,
    parameter_count: int | None,
) -> dict[str, object]:
    if (
        result.get("evaluation_id") != EVALUATION_ID
        or result.get("benchmark_id") != evaluate.CANONICAL_BENCHMARK_ID
        or result.get("dataset_realization_id") != evaluate.CANONICAL_VALIDATION.realization_id
        or result.get("status") != "COMPLETE"
    ):
        raise ValueError("result does not bind the canonical RES-271 evaluation population")
    targets = cast(list[dict[str, Any]], result["targets"])
    values: dict[str, dict[str, float | None]] = {}
    for item in targets:
        raw_metrics = {str(value["metric"]): value.get("value") for value in item["metrics"]}
        metric_values = {
            "RMSE": raw_metrics.get(MetricName.RMSE.value),
            "MAE": raw_metrics.get(MetricName.MAE.value),
            "R2": raw_metrics.get(MetricName.R2.value),
            "SRE": raw_metrics.get(MetricName.SRE.value),
        }
        values[str(item["target"])] = metric_values
    return {
        "method": method,
        "model_id": result["model"]["model_id"],
        "classification": "RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT",
        "seed": seed,
        "fitted_instance_id": (
            fitted_instance_id
            or cast(dict[str, Any], result.get("fitted_instance") or {}).get(
                "fitted_instance_id", ""
            )
        ),
        "checkpoint_id": cast(dict[str, Any], result.get("checkpoint") or {}).get(
            "checkpoint_id", ""
        ),
        "parameter_count": parameter_count,
        "fit_runtime_seconds": "",
        "prediction_artifact_identity": (
            f"psr:prediction-artifact:{result['prediction_artifact']['artifact_id']}@"
            f"{sha256_record(result['prediction_artifact'])}"
        ),
        "evaluation_result_id": f"psr:evaluation-result@{sha256_record(result)}",
        "target_metrics": values,
    }


def _metric_rows(
    results: list[dict[str, Any]],
    model_id: str,
    classification: str,
    method: str,
    seed: int,
    fitted_instance_id: str,
    prediction_identity: str,
    result_id: str,
    parameter_count: int,
    fixed_constant_count: int,
    fit_seconds: float,
    shared_preprocessing_seconds: float,
    shared_validation_preprocessing_seconds: float,
    prediction_seconds: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target in results:
        metrics = {str(item["metric"]): item.get("value") for item in target["metrics"]}
        rows.append(
            {
                "method": method,
                "classification": classification,
                "model_id": model_id,
                "seed": seed,
                "target": target["target"],
                "rmse_kg": metrics.get(MetricName.RMSE.value),
                "mae_kg": metrics.get(MetricName.MAE.value),
                "r2": metrics.get(MetricName.R2.value),
                "sre_ddof0": metrics.get(MetricName.SRE.value),
                "parameter_count": parameter_count,
                "fixed_constant_count": fixed_constant_count,
                "fit_runtime_seconds": fit_seconds,
                "shared_preprocessing_runtime_seconds": shared_preprocessing_seconds,
                "shared_validation_preprocessing_runtime_seconds": (
                    shared_validation_preprocessing_seconds
                ),
                "prediction_runtime_seconds": prediction_seconds,
                "fitted_instance_id": fitted_instance_id,
                "prediction_artifact_identity": prediction_identity,
                "evaluation_result_id": result_id,
            }
        )
    return rows


def _metric_payload(result: EvaluationResult) -> list[dict[str, Any]]:
    return [
        {
            "target": item.target,
            "metrics": [
                {"metric": value.metric.value, "value": value.value, "unit": value.unit}
                for value in item.metrics
            ],
        }
        for item in result.targets
    ]


def _write_metrics_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = (
        "method",
        "classification",
        "model_id",
        "seed",
        "target",
        "rmse_kg",
        "mae_kg",
        "r2",
        "sre_ddof0",
        "parameter_count",
        "fixed_constant_count",
        "fit_runtime_seconds",
        "shared_preprocessing_runtime_seconds",
        "shared_validation_preprocessing_runtime_seconds",
        "prediction_runtime_seconds",
        "fitted_instance_id",
        "prediction_artifact_identity",
        "evaluation_result_id",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _model_registry_entry(
    spec: ComparatorModelSpec, runs: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "model_id": spec.model_id,
        "slug": spec.slug,
        "classification": "NEW_STANDARDIZED_COMPARATOR",
        "training_protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
        "method": spec.method,
        "semantics": spec.semantics,
        "configuration": _METHOD_CONFIGS[spec.method],
        "model_card": "artifacts/model-cards/public-native-comparator-suite.md",
        "runs": runs,
    }


def run_comparator_suite(
    *,
    train_path: Path = DATA_ROOT / "train.jsonl",
    validation_path: Path = DATA_ROOT / "validation.jsonl",
    manifest_path: Path = MANIFEST_PATH,
    output_root: Path = OUTPUT_ROOT,
    fitted_root: Path = FITTED_ROOT,
) -> None:
    """Fit all six fixed comparators on TRAIN; access canonical validation only after sealing."""
    if output_root.exists() or fitted_root.exists():
        raise FileExistsError("RES-275 result or fitted-state output already exists")
    source = _source_identity()
    if not train_path.is_file():
        raise ValueError(
            f"canonical TRAIN JSONL not found at {train_path}; regenerate with RES-270"
        )
    train_bytes = train_path.read_bytes()
    if _sha256(train_bytes) != TRAIN_SHA256:
        raise ValueError("canonical TRAIN SHA-256 does not match the frozen RES-271 identity")
    evaluate._parse_manifest(manifest_path, evaluate.CANONICAL_VALIDATION)
    train_rows = _read_train_rows(train_path, PROTOCOL.train_row_count)
    split = make_internal_split(
        train_rows,
        realization_id=PROTOCOL.dataset_realization_id,
        realization_digest=PROTOCOL.dataset_realization_digest,
        protocol_id=COMPARATOR_TRAINING_PROTOCOL_ID,
    )
    training_partition = dict(PROTOCOL.training_partition)
    if (
        split.manifest["split_digest"] != training_partition["split_digest"]
        or split.manifest["internal_selection_split_id"] != training_partition["split_id"]
        or len(split.fit_rows) != training_partition["fit_row_count"]
        or len(split.selection_rows) != training_partition["selection_row_count"]
    ):
        raise ValueError("derived TRAIN fit/selection split differs from the frozen protocol")

    output_root.mkdir(parents=True)
    fitted_root.mkdir(parents=True)
    split_payload = {
        key: value
        for key, value in split.manifest.items()
        if key not in {"fit_row_ids", "selection_row_ids"}
    }
    split_path = output_root / "internal-selection-split.json"
    split_sha = _write_json(split_path, split_payload)

    preprocessing_started = time.perf_counter()
    fit_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in split.fit_rows
    )
    fit_targets = _target_matrix(split.fit_rows)
    selection_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs)
        for row in split.selection_rows
    )
    selection_targets = _target_matrix(split.selection_rows)
    input_stats = NormalizationStats.fit_train(
        fit_inputs,
        cast(tuple[tuple[float, float, float], ...], tuple(map(tuple, fit_targets.tolist()))),
    )
    fit_features_raw = feature_matrix(split.fit_rows, input_stats)
    selection_features_raw = feature_matrix(split.selection_rows, input_stats)
    _, _, (feature_mean, feature_scale) = _standardize_features(
        fit_features_raw, selection_features_raw
    )
    target_mean = np.asarray(input_stats.target_mean, dtype=np.float64)
    target_scale = np.asarray(input_stats.target_scale, dtype=np.float64)
    preprocessing_seconds = time.perf_counter() - preprocessing_started
    del fit_inputs, selection_inputs

    environment, runtime = _runtime_provenance()
    fit_records: list[FitRecord] = []
    training_receipts: list[dict[str, object]] = []
    runs_by_model: dict[str, list[dict[str, object]]] = {item.method: [] for item in MODEL_SPECS}
    fitted_states: dict[tuple[str, int], dict[str, Any]] = {}
    for seed in SEEDS:
        for spec in MODEL_SPECS:
            configure_determinism(seed)
            started = time.perf_counter()
            fitted = fit_comparator(
                spec.method,
                split.fit_rows,
                split.selection_rows,
                fit_features_raw,
                selection_features_raw,
                fit_targets,
                selection_targets,
                feature_mean,
                feature_scale,
                target_mean,
                target_scale,
                seed,
            )
            fit_seconds = time.perf_counter() - started
            state = {
                "format": "PSR_FITTED_COMPARATOR_STATE_V1",
                "model_id": spec.model_id,
                "classification": "NEW_STANDARDIZED_COMPARATOR",
                "training_protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
                "dataset_realization_id": PROTOCOL.dataset_realization_id,
                "dataset_realization_digest": PROTOCOL.dataset_realization_digest,
                "training_sha256": TRAIN_SHA256,
                "fit_split_id": split.manifest["internal_selection_split_id"],
                "fit_split_digest": split.manifest["split_digest"],
                "fit_row_count": len(split.fit_rows),
                "selection_row_count": len(split.selection_rows),
                "seed": seed,
                "input_normalization": input_stats.to_dict(),
                "model_state": fitted.model_state,
            }
            state_path = fitted_root / spec.slug / f"seed-{seed}.fitted-instance.json"
            state_sha = _write_json(state_path, state)
            fitted_id = f"psr:fitted-instance:{spec.slug}-seed-{seed}@sha256:{state_sha}"
            record = FitRecord(
                spec,
                seed,
                fitted_id,
                f"sha256:{state_sha}",
                state_path.relative_to(ROOT).as_posix(),
                {
                    "seed": seed,
                    "fit_runtime_seconds": fit_seconds,
                    "parameter_count": fitted.parameter_count,
                    "fixed_constant_count": fitted.fixed_constant_count,
                    "selection_loss_standardized_mse": fitted.selection_loss,
                    "selected_steps": fitted.selected_steps,
                    "shared_preprocessing_runtime_seconds": preprocessing_seconds,
                    "training_validation_accessed": False,
                    "training_code_sha": source["code_sha"],
                },
            )
            fit_records.append(record)
            fitted_states[(spec.method, seed)] = state
            run = {
                **record.training_receipt,
                "fitted_instance_id": fitted_id,
                "fitted_instance_path": record.fitted_instance_path,
                "fitted_instance_sha256": record.fitted_instance_sha256,
            }
            runs_by_model[spec.method].append(run)
            training_receipts.append({"method": spec.method, "model_id": spec.model_id, **run})

    seal_path = output_root / "training-seal.json"
    seal = {
        "format": "PSR_RES275_FIT_SEAL_V1",
        "protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
        "dataset_realization_id": PROTOCOL.dataset_realization_id,
        "dataset_realization_digest": PROTOCOL.dataset_realization_digest,
        "training_sha256": TRAIN_SHA256,
        "fit_split_id": split.manifest["internal_selection_split_id"],
        "fit_split_digest": split.manifest["split_digest"],
        "fit_row_count": len(split.fit_rows),
        "selection_row_count": len(split.selection_rows),
        "shared_preprocessing_runtime_seconds": preprocessing_seconds,
        "canonical_validation_accessed": False,
        "fitted_instances": training_receipts,
    }
    seal_sha = _write_json(seal_path, seal)
    if _read_json(seal_path).get("canonical_validation_accessed") is not False:
        raise ValueError("fit seal did not persist before canonical validation access")

    validation_rows = evaluate._load_truth(
        validation_path, manifest_path, evaluate.CANONICAL_VALIDATION
    )
    if len(validation_rows) != PROTOCOL.validation_row_count:
        raise ValueError("canonical validation row count differs from the frozen protocol")
    first_fitted_state = next(iter(fitted_states.values()))
    input_normalization = cast(dict[str, Any], first_fitted_state["input_normalization"])
    if any(
        fitted_state["input_normalization"] != input_normalization
        for fitted_state in fitted_states.values()
    ):
        raise ValueError("all comparators must share fitting-row input normalization")
    validation_preprocessing_started = time.perf_counter()
    validation_features = feature_matrix(
        validation_rows, NormalizationStats.from_dict(input_normalization)
    )
    shared_validation_preprocessing_seconds = time.perf_counter() - validation_preprocessing_started
    expert_rows, expert_hashes = _load_expert_results()
    metric_rows: list[dict[str, object]] = []
    comparator_registry: list[dict[str, object]] = []
    for spec in MODEL_SPECS:
        model_runs: list[dict[str, object]] = []
        for run in runs_by_model[spec.method]:
            seed = cast(int, run["seed"])
            fitted_state = fitted_states[(spec.method, seed)]
            prediction_started = time.perf_counter()
            prediction_values = predict_comparator(
                spec.method,
                fitted_state,
                validation_rows,
                validation_features,
            )
            prediction_seconds = time.perf_counter() - prediction_started
            prediction_rows = tuple(
                PredictionRow(row.row_id, *map(float, values))
                for row, values in zip(validation_rows, prediction_values, strict=True)
            )
            prediction_bytes = canonical_prediction_jsonl(prediction_rows)
            prediction_path = output_root / spec.slug / f"seed-{seed}.predictions.jsonl"
            prediction_path.parent.mkdir(parents=True, exist_ok=True)
            with prediction_path.open("xb") as file:
                file.write(prediction_bytes)
            prediction_sha = _sha256(prediction_bytes)
            base_result = evaluate.evaluate_files(
                validation_path,
                prediction_path,
                spec.model_id,
                manifest_path=manifest_path,
                environment=environment,
            )
            fitted_id = str(run["fitted_instance_id"])
            fitted_sha = str(run["fitted_instance_sha256"])
            rng = (
                RNGProvenance(DeterminismStatus.SEEDED, (("training", seed),))
                if spec.method == "compact_neural"
                else RNGProvenance(
                    DeterminismStatus.DETERMINISTIC,
                    (("declared_run_seed", seed),),
                    "The fit is deterministic; the frozen run seed labels this protocol replicate.",
                )
            )
            result = replace(
                base_result,
                training_protocol=TrainingProtocolReference(COMPARATOR_TRAINING_PROTOCOL_ID),
                fitted_instance=FittedInstanceReference(fitted_id, fitted_sha),
                rng=rng,
                prediction_artifact=replace(
                    base_result.prediction_artifact,
                    rights=RightsMetadata(
                        "MIT",
                        "Powerlifting State Research contributors",
                        "Repository-generated public-native predictions; redistribution permitted "
                        "under the repository license.",
                    ),
                ),
                rights=OUTPUT_RIGHTS,
            )
            result_path = output_root / spec.slug / f"seed-{seed}.evaluation-result.json"
            result_bytes = evaluate.result_json_bytes(result)
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with result_path.open("xb") as file:
                file.write(result_bytes)
            prediction_identity = result.prediction_artifact.identity_id
            result_id = result.result_id
            model_run = {
                **run,
                "prediction_path": prediction_path.relative_to(ROOT).as_posix(),
                "prediction_sha256": f"sha256:{prediction_sha}",
                "prediction_artifact_identity": prediction_identity,
                "evaluation_result_path": result_path.relative_to(ROOT).as_posix(),
                "evaluation_result_sha256": f"sha256:{_sha256(result_bytes)}",
                "evaluation_result_id": result_id,
                "prediction_runtime_seconds": prediction_seconds,
                "shared_validation_preprocessing_runtime_seconds": (
                    shared_validation_preprocessing_seconds
                ),
                "target_metrics": _metric_payload(result),
            }
            model_runs.append(model_run)
            metric_rows.extend(
                _metric_rows(
                    _metric_payload(result),
                    spec.model_id,
                    "NEW_STANDARDIZED_COMPARATOR",
                    spec.method,
                    seed,
                    fitted_id,
                    prediction_identity,
                    result_id,
                    int(cast(int, run["parameter_count"])),
                    int(cast(int, run["fixed_constant_count"])),
                    float(cast(float, run["fit_runtime_seconds"])),
                    preprocessing_seconds,
                    shared_validation_preprocessing_seconds,
                    prediction_seconds,
                )
            )
        comparator_registry.append(_model_registry_entry(spec, model_runs))

    expert_target_rows = expert_rows
    for item in expert_target_rows:
        target_metrics = cast(dict[str, dict[str, float | None]], item["target_metrics"])
        for target, values in target_metrics.items():
            metric_rows.append(
                {
                    "method": item["method"],
                    "classification": item["classification"],
                    "model_id": item["model_id"],
                    "seed": item["seed"],
                    "target": target,
                    "rmse_kg": values.get("RMSE"),
                    "mae_kg": values.get("MAE"),
                    "r2": values.get("R2"),
                    "sre_ddof0": values.get("SRE"),
                    "parameter_count": 118_571 * (3 if item["seed"] == "ensemble" else 1),
                    "fixed_constant_count": 0,
                    "fit_runtime_seconds": "",
                    "shared_preprocessing_runtime_seconds": "",
                    "shared_validation_preprocessing_runtime_seconds": "",
                    "prediction_runtime_seconds": "",
                    "fitted_instance_id": item["fitted_instance_id"],
                    "prediction_artifact_identity": item["prediction_artifact_identity"],
                    "evaluation_result_id": item["evaluation_result_id"],
                }
            )

    target_metrics_path = TARGET_METRICS_PATH
    _write_metrics_csv(target_metrics_path, metric_rows)
    registry = {
        "format": "PSR_STANDARDIZED_COMPARATOR_REGISTRY_V1",
        "training_protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
        "training_protocol_path": (
            "artifacts/training-protocols/public-native-comparator-suite.json"
        ),
        "benchmark_id": PROTOCOL.benchmark_id,
        "benchmark_digest": PROTOCOL.benchmark_digest,
        "dataset_spec_id": PROTOCOL.dataset_spec_id,
        "dataset_realization_id": PROTOCOL.dataset_realization_id,
        "dataset_realization_digest": PROTOCOL.dataset_realization_digest,
        "evaluation_id": EVALUATION_ID,
        "shared_preprocessing_runtime_seconds": preprocessing_seconds,
        "shared_validation_preprocessing_runtime_seconds": (
            shared_validation_preprocessing_seconds
        ),
        "comparators": comparator_registry,
        "immutable_res274_reference": {
            "model_id": (
                "psr:model:public-native-lift-shared-temporal-gru-capacity-change"
                "@1.0.0~34d23123138f"
            ),
            "training_protocol_id": (
                "psr:training-protocol:public-native-temporal-expert@1.0.0~dc47230f3465"
            ),
            "classification": "RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT",
            "result_paths": [
                f"results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-temporal-expert/seed-{seed}.evaluation-result.json"
                for seed in SEEDS
            ]
            + [
                "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-temporal-expert/ensemble.evaluation-result.json"
            ],
            "prediction_and_result_hashes_verified": True,
        },
        "target_metrics_path": target_metrics_path.relative_to(ROOT).as_posix(),
    }
    registry_sha = _write_json(REGISTRY_PATH, registry)

    run_manifest = {
        "format": "PSR_RES275_STANDARDIZED_COMPARATOR_RUN_V1",
        "status": "PASS",
        "source": source,
        "runtime": runtime,
        "shared_preprocessing_runtime_seconds": preprocessing_seconds,
        "shared_validation_preprocessing_runtime_seconds": (
            shared_validation_preprocessing_seconds
        ),
        "protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
        "protocol_path": "artifacts/training-protocols/public-native-comparator-suite.json",
        "benchmark_id": PROTOCOL.benchmark_id,
        "benchmark_digest": PROTOCOL.benchmark_digest,
        "dataset_spec_id": PROTOCOL.dataset_spec_id,
        "dataset_realization_id": PROTOCOL.dataset_realization_id,
        "dataset_realization_digest": PROTOCOL.dataset_realization_digest,
        "train_sha256": TRAIN_SHA256,
        "train_row_count": len(train_rows),
        "validation_sha256": VALIDATION_SHA256,
        "validation_row_count": len(validation_rows),
        "evaluation_id": EVALUATION_ID,
        "metric_ids": tuple(item.metric_id for item in METRIC_IDENTITIES),
        "seeds": SEEDS,
        "fit_selection_split": {
            "path": split_path.relative_to(ROOT).as_posix(),
            "sha256": f"sha256:{split_sha}",
            "split_id": split.manifest["internal_selection_split_id"],
            "split_digest": split.manifest["split_digest"],
            "fit_row_count": len(split.fit_rows),
            "selection_row_count": len(split.selection_rows),
            "entity_disjoint": True,
            "support_preserved": True,
        },
        "validation_isolation": {
            "training_loader_opened_validation": False,
            "fit_artifacts_sealed_before_validation_access": True,
            "seal_path": seal_path.relative_to(ROOT).as_posix(),
            "seal_sha256": f"sha256:{seal_sha}",
            "canonical_validation_used_for_selection_or_revision": False,
            "evaluation_after_seal": True,
        },
        "fitted_state_root": FITTED_ROOT.relative_to(ROOT).as_posix(),
        "registry": {
            "path": REGISTRY_PATH.relative_to(ROOT).as_posix(),
            "sha256": f"sha256:{registry_sha}",
        },
        "target_metrics_path": target_metrics_path.relative_to(ROOT).as_posix(),
        "immutable_res274_artifacts": expert_hashes,
        "rights": OUTPUT_RIGHTS,
    }
    run_manifest_sha = _write_json(RUN_MANIFEST_PATH, run_manifest)

    checksum_paths = {
        protocol_path: ROOT / protocol_path
        for protocol_path in (
            "artifacts/training-protocols/public-native-comparator-suite.json",
            REGISTRY_PATH.relative_to(ROOT).as_posix(),
            target_metrics_path.relative_to(ROOT).as_posix(),
            RUN_MANIFEST_PATH.relative_to(ROOT).as_posix(),
        )
    }
    checksum_paths[split_path.relative_to(ROOT).as_posix()] = split_path
    checksum_paths[seal_path.relative_to(ROOT).as_posix()] = seal_path
    for record in fit_records:
        checksum_paths[record.fitted_instance_path] = ROOT / record.fitted_instance_path
    for method_runs in comparator_registry:
        for run in cast(list[dict[str, Any]], method_runs["runs"]):
            checksum_paths[str(run["prediction_path"])] = ROOT / str(run["prediction_path"])
            checksum_paths[str(run["evaluation_result_path"])] = ROOT / str(
                run["evaluation_result_path"]
            )
    checksum_paths.update({path: ROOT / path for path in expert_hashes})
    checksum_index = {
        "format": "PSR_SHA256_INDEX_V1",
        "algorithm": "SHA-256",
        "run_manifest_sha256": f"sha256:{run_manifest_sha}",
        "entries": [
            {
                "path": path,
                "sha256": _sha256(file_path.read_bytes()),
                "size_bytes": file_path.stat().st_size,
            }
            for path, file_path in sorted(checksum_paths.items())
        ],
    }
    _write_json(CHECKSUM_INDEX_PATH, checksum_index)
    print("RES275_COMPARATOR_RUN=PASS")
    print(f"protocol_id={COMPARATOR_TRAINING_PROTOCOL_ID}")
    print(f"run_manifest={RUN_MANIFEST_PATH.relative_to(ROOT)}")
    print(f"checksum_index={CHECKSUM_INDEX_PATH.relative_to(ROOT)}")
    print(f"run_manifest_sha256=sha256:{run_manifest_sha}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DATA_ROOT / "train.jsonl")
    parser.add_argument("--validation", type=Path, default=DATA_ROOT / "validation.jsonl")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fitted-root", type=Path, default=FITTED_ROOT)
    args = parser.parse_args(argv)
    try:
        run_comparator_suite(
            train_path=args.train,
            validation_path=args.validation,
            manifest_path=args.manifest,
            output_root=args.output,
            fitted_root=args.fitted_root,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"RES275_COMPARATOR_RUN=FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
