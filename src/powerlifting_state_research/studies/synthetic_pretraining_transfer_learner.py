"""Isolated fixed learner for the RES-292 synthetic-pretraining transfer study."""

from __future__ import annotations

import json
import math
import sys
from typing import Any, cast

import numpy as np
from numpy import random as _random
from numpy.typing import NDArray

Array = NDArray[np.float64]
LIFTS = ("squat", "bench_press", "deadlift")
CHANNELS = ("assessment_kg", "prescribed_load_kg", "velocity_mps")
TARGETS = tuple(f"{lift}_delta_capacity_kg" for lift in LIFTS)
PLANS = ("cessation", "step_down", "continue", "step_up")
HORIZONS = (14, 28, 56)
PLAN_DOSE = {"cessation": 0.0, "step_down": 0.4, "continue": 0.8, "step_up": 1.2}
ARMS = (
    "PUBLIC_ONLY",
    "SYNTHETIC_ONLY_BOOTSTRAP",
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP",
    "COMPUTE_MATCHED_PUBLIC_ONLY",
    "SYNTHETIC_ONLY_PSEUDOLABEL",
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL",
)
BATCH_SIZE = 32
PUBLIC_UPDATES = 128
SYNTHETIC_UPDATES = 128
COMPUTE_MATCHED_UPDATES = 256
LEARNING_RATE = 0.01
L2 = 1e-4
TARGET_SCALE_KG = 10.0


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
    expected = {"row_id", "inputs"} | ({"targets"} if targets_required else set())
    row = _keys(value, expected, "row")
    if not isinstance(row["row_id"], str) or not row["row_id"]:
        raise ValueError("row_id must be a non-empty string")
    inputs = _keys(
        row["inputs"],
        {"entity_id", "origin_day", "horizon_days", "declared_future_plan", "lifts"},
        "inputs",
    )
    if (
        inputs["entity_id"] != row["row_id"]
        or inputs["origin_day"] != 224
        or inputs["horizon_days"] not in HORIZONS
    ):
        raise ValueError("row identity, origin, or horizon is outside the frozen schema")
    plan = _keys(
        inputs["declared_future_plan"],
        {"plan_id", "start_day", "end_day", "dose", "intensity"},
        "declared_future_plan",
    )
    if (
        plan["plan_id"] not in PLANS
        or plan["start_day"] != 224
        or plan["end_day"] != 279
        or _finite(plan["dose"], "plan dose") != PLAN_DOSE[plan["plan_id"]]
        or _finite(plan["intensity"], "plan intensity") != 0.75
    ):
        raise ValueError("future plan is outside the frozen schema")
    lifts = _keys(inputs["lifts"], set(LIFTS), "lifts")
    for lift in LIFTS:
        lift_inputs = _keys(lifts[lift], {"history", "history_schedule"}, f"{lift} inputs")
        history = lift_inputs["history"]
        if not isinstance(history, list) or len(history) != 32:
            raise ValueError(f"{lift} history must contain 32 observations")
        for index, observation in enumerate(history):
            item = _keys(
                observation,
                {"day", "assessment_kg", "prescribed_load_kg", "velocity_mps"},
                f"{lift} observation",
            )
            if item["day"] != 6 + index * 7:
                raise ValueError(f"{lift} observation days are invalid")
            for channel in CHANNELS:
                _finite(item[channel], f"{lift}.{channel}")
        schedule = lift_inputs["history_schedule"]
        if not isinstance(schedule, list) or not schedule:
            raise ValueError(f"{lift} history schedule is empty")
        next_day = 0
        for segment in schedule:
            part = _keys(
                segment,
                {"start_day", "end_day", "dose", "intensity"},
                "history schedule segment",
            )
            dose = _finite(part["dose"], "schedule dose")
            intensity = _finite(part["intensity"], "schedule intensity")
            if (
                part["start_day"] != next_day
                or part["end_day"] < next_day
                or part["end_day"] > 223
                or (dose, intensity) not in {(value, 0.75) for value in PLAN_DOSE.values()}
            ):
                raise ValueError("history schedule has a gap or undeclared input")
            next_day = part["end_day"] + 1
        if next_day != 224:
            raise ValueError("history schedule does not cover days 0 through 223")
    if targets_required:
        targets = _keys(row["targets"], set(TARGETS), "targets")
        for name in TARGETS:
            _finite(targets[name], name)
    return row


def _weekly_schedule(segments: list[dict[str, Any]]) -> Array:
    weekly = np.zeros((32, 2), dtype=np.float64)
    covered = np.zeros(32, dtype=np.float64)
    for segment in segments:
        start = int(segment["start_day"])
        end = int(segment["end_day"])
        for week in range(start // 7, end // 7 + 1):
            overlap = max(0, min(end + 1, (week + 1) * 7) - max(start, week * 7))
            weekly[week, 0] += overlap * float(segment["dose"]) / 7.0
            weekly[week, 1] += overlap * float(segment["intensity"]) / 7.0
            covered[week] += overlap
    if not np.all(covered == 7.0):
        raise ValueError("history schedule cannot be aligned to weekly bins")
    return weekly


def _features(row: dict[str, Any]) -> Array:
    values: list[float] = []
    time = np.arange(32, dtype=np.float64)
    centered = time - float(time.mean())
    denom = float(centered @ centered)
    scales = {"assessment_kg": 100.0, "prescribed_load_kg": 100.0, "velocity_mps": 1.0}
    for lift in LIFTS:
        lift_inputs = row["inputs"]["lifts"][lift]
        history = lift_inputs["history"]
        for channel in CHANNELS:
            series = np.asarray([item[channel] for item in history], dtype=np.float64)
            series /= scales[channel]
            values.extend(
                (float(series[-1]), float(series.mean()), float(centered @ series / denom))
            )
        schedule = _weekly_schedule(lift_inputs["history_schedule"])
        for index in range(2):
            series = schedule[:, index]
            values.extend(
                (
                    float(series.mean()),
                    float(series.std()),
                    float(series[-1]),
                    float(centered @ series / denom),
                )
            )
    plan_id = row["inputs"]["declared_future_plan"]["plan_id"]
    horizon = row["inputs"]["horizon_days"]
    values.extend(float(plan_id == value) for value in PLANS)
    values.extend(float(horizon == value) for value in HORIZONS)
    if len(values) != 58:
        raise ValueError("frozen feature representation must contain 58 values")
    result = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(result)):
        raise ValueError("feature representation is nonfinite")
    return result


def _targets(rows: list[dict[str, Any]]) -> Array:
    return np.asarray(
        [[float(row["targets"][target]) / TARGET_SCALE_KG for target in TARGETS] for row in rows],
        dtype=np.float64,
    )


def _predict(weights: Array, features: Array) -> Array:
    design = np.column_stack((features, np.ones(len(features), dtype=np.float64)))
    return (design @ weights) * TARGET_SCALE_KG


def _record_curve(
    curves: list[dict[str, Any]],
    arm: str,
    fit_seed: int,
    stage: str,
    public_updates: int,
    synthetic_updates: int,
    weights: Array,
    development: list[dict[str, Any]],
    development_x: Array,
) -> None:
    predictions = _predict(weights, development_x)
    for row, prediction in zip(development, predictions, strict=True):
        curves.append(
            {
                "arm": arm,
                "fit_seed": fit_seed,
                "stage": stage,
                "public_updates": public_updates,
                "synthetic_updates": synthetic_updates,
                "row_id": row["row_id"],
                "horizon_days": row["inputs"]["horizon_days"],
                "targets": {
                    target: float(value) for target, value in zip(TARGETS, prediction, strict=True)
                },
            }
        )


def _updates(
    weights: Array,
    features: Array,
    targets: Array,
    count: int,
    rng: np.random.Generator,
) -> tuple[Array, int]:
    for _ in range(count):
        indices = rng.integers(0, len(features), size=BATCH_SIZE)
        design = np.column_stack((features[indices], np.ones(BATCH_SIZE, dtype=np.float64)))
        error = design @ weights - targets[indices]
        gradient = (2.0 / BATCH_SIZE) * (design.T @ error)
        gradient[:-1] += L2 * weights[:-1]
        weights = weights - LEARNING_RATE * gradient
        if not np.all(np.isfinite(weights)):
            raise FloatingPointError("learner state became nonfinite")
    return weights, count * BATCH_SIZE


def _fit(request: dict[str, Any]) -> dict[str, Any]:
    arm = request["arm"]
    if arm not in ARMS:
        raise ValueError("unknown frozen learner arm")
    if isinstance(request["fit_seed"], bool) or not isinstance(request["fit_seed"], int):
        raise ValueError("fit seed must be an integer")
    fit_seed = request["fit_seed"]
    public_rows = [_validate_row(row, True) for row in request["public_rows"]]
    synthetic_rows = [_validate_row(row, True) for row in request["synthetic_rows"]]
    if len(public_rows) != len({row["row_id"] for row in public_rows}):
        raise ValueError("public fitting row IDs are not unique")
    if len(synthetic_rows) != len({row["row_id"] for row in synthetic_rows}):
        raise ValueError("synthetic row IDs are not unique")
    if {row["row_id"] for row in public_rows} & {row["row_id"] for row in synthetic_rows}:
        raise ValueError("public and synthetic fitting row IDs overlap")
    expected_provenance = (
        "BOOTSTRAP_DUPLICATE_LABEL"
        if arm.endswith("BOOTSTRAP")
        else "SURROGATE_PSEUDO_LABEL"
        if "PSEUDOLABEL" in arm
        else "NONE"
    )
    if request["synthetic_label_provenance"] != expected_provenance:
        raise ValueError("synthetic target provenance does not match this arm")
    needs_public = arm in {
        "PUBLIC_ONLY",
        "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP",
        "COMPUTE_MATCHED_PUBLIC_ONLY",
        "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL",
    }
    needs_synthetic = arm not in {"PUBLIC_ONLY", "COMPUTE_MATCHED_PUBLIC_ONLY"}
    if bool(public_rows) != needs_public or bool(synthetic_rows) != needs_synthetic:
        raise ValueError("learner payload does not match the declared arm data")
    if needs_public and len(public_rows) != 384:
        raise ValueError("public training rows do not match the frozen count")
    if needs_synthetic and len(synthetic_rows) != 384:
        raise ValueError("synthetic training rows do not match the frozen count")
    if not needs_synthetic and expected_provenance != "NONE":
        raise ValueError("public-only arm has synthetic provenance")
    if needs_synthetic and expected_provenance == "NONE":
        raise ValueError("synthetic arm is missing label provenance")

    queries: list[dict[str, Any]] = []
    for value in request["queries"]:
        item = _keys(value, {"evaluation_set", "row"}, "query")
        if item["evaluation_set"] not in {"development", "test_population_a", "test_population_b"}:
            raise ValueError("unknown evaluation set")
        queries.append(
            {
                "evaluation_set": item["evaluation_set"],
                "row": _validate_row(item["row"], False),
            }
        )
    query_ids = {item["row"]["row_id"] for item in queries}
    train_ids = {row["row_id"] for row in public_rows + synthetic_rows}
    if len(query_ids) != len(queries) or query_ids & train_ids:
        raise ValueError("query rows are duplicated or overlap fitting IDs")
    development = [item["row"] for item in queries if item["evaluation_set"] == "development"]
    if len(development) != 192:
        raise ValueError("development query count does not match the frozen count")

    rng_init = _random.default_rng(fit_seed)
    rng_synthetic = _random.default_rng(fit_seed + 2_000_000)
    rng_public = _random.default_rng(fit_seed + 1_000_000)
    weights = rng_init.normal(0.0, 0.01, size=(59, 3)).astype(np.float64)
    development_x = np.asarray([_features(row) for row in development], dtype=np.float64)
    curves: list[dict[str, Any]] = []
    synthetic_presentations = 0
    public_presentations = 0
    synthetic_updates = 0
    public_updates = 0

    if needs_synthetic:
        synthetic_x = np.asarray([_features(row) for row in synthetic_rows], dtype=np.float64)
        synthetic_y = _targets(synthetic_rows)
        _record_curve(curves, arm, fit_seed, "synthetic", 0, 0, weights, development, development_x)
        for _ in range(32, SYNTHETIC_UPDATES + 1, 32):
            weights, presentations = _updates(weights, synthetic_x, synthetic_y, 32, rng_synthetic)
            synthetic_presentations += presentations
            synthetic_updates += 32
            _record_curve(
                curves,
                arm,
                fit_seed,
                "synthetic",
                0,
                synthetic_updates,
                weights,
                development,
                development_x,
            )

    if needs_public:
        public_x = np.asarray([_features(row) for row in public_rows], dtype=np.float64)
        public_y = _targets(public_rows)
        total_updates = (
            COMPUTE_MATCHED_UPDATES if arm == "COMPUTE_MATCHED_PUBLIC_ONLY" else PUBLIC_UPDATES
        )
        stage = "public_fine_tuning" if needs_synthetic else "public"
        _record_curve(
            curves,
            arm,
            fit_seed,
            stage,
            0,
            synthetic_updates,
            weights,
            development,
            development_x,
        )
        for _ in range(32, total_updates + 1, 32):
            weights, presentations = _updates(weights, public_x, public_y, 32, rng_public)
            public_presentations += presentations
            public_updates += 32
            _record_curve(
                curves,
                arm,
                fit_seed,
                stage,
                public_updates,
                synthetic_updates,
                weights,
                development,
                development_x,
            )

    predictions: list[dict[str, Any]] = []
    for item in queries:
        if item["evaluation_set"] == "development":
            continue
        row = item["row"]
        prediction = _predict(weights, _features(row).reshape(1, -1))[0]
        predictions.append(
            {
                "arm": arm,
                "fit_seed": fit_seed,
                "evaluation_set": item["evaluation_set"],
                "row_id": row["row_id"],
                "targets": {
                    target: float(value) for target, value in zip(TARGETS, prediction, strict=True)
                },
            }
        )
    return {
        "protocol_id": request["protocol_id"],
        "arm": arm,
        "fit_seed": fit_seed,
        "parameter_count": int(weights.size),
        "weights": weights.tolist(),
        "synthetic_updates": synthetic_updates,
        "public_updates": public_updates,
        "synthetic_row_presentations": synthetic_presentations,
        "public_row_presentations": public_presentations,
        "learning_curve_predictions": curves,
        "predictions": predictions,
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
        {
            "protocol_id",
            "arm",
            "fit_seed",
            "public_rows",
            "synthetic_rows",
            "synthetic_label_provenance",
            "queries",
        },
        "request",
    )
    if not isinstance(request["protocol_id"], str) or not request["protocol_id"]:
        raise ValueError("protocol identity is required")
    result = _fit(request)
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
