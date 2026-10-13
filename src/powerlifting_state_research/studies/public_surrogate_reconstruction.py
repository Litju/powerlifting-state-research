"""RES-290 public-native realization, evaluator authority, and publication builder."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import hashlib
import inspect
import io
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast
from xml.sax.saxutils import escape

import numpy as np

from ..artifacts.manifests import ArtifactManifest, RightsMetadata
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dataset import (
    ForecastInputs,
    GenerationConfig,
    LiftInputs,
    PublicCapacityTargets,
    PublicForecastRow,
    PublicLiftInputs,
    iter_public_rows,
    simulate_athlete,
    validate_public_row,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (
    latent_capacity_change,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.interventions import (
    HORIZONS_DAYS,
    declared_plan,
    history_segments,
    sample_history_template_combinations,
    training_sessions,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.observations import (
    HISTORY_OBSERVATION_DAYS,
    sample_performance_history,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (
    LIFTS,
    sample_athlete,
)
from ..contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    ObservationAvailability,
    SplitIdentity,
    SupportSummary,
    TemporalCoverage,
)
from ..contracts.serialization import (
    canonical_json_bytes,
    require_scientific_id,
    sha256_record,
)

PROTOCOL_RELATIVE = "studies/public_surrogate_reconstruction/protocol.json"
FROZEN_RELATIVE = "studies/public_surrogate_reconstruction/frozen-evidence.json"
LEARNER_RELATIVE = (
    "src/powerlifting_state_research/studies/public_surrogate_reconstruction_learner.py"
)
EVALUATOR_RELATIVE = "src/powerlifting_state_research/studies/public_surrogate_reconstruction.py"
OUTPUT_RELATIVE = "results/studies/public_surrogate_reconstruction/public-native"
DATA_GENERATOR_SOURCE_PATHS = (
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py",
    "src/powerlifting_state_research/contracts/serialization.py",
)
TARGETS = tuple(f"{lift}_delta_capacity_kg" for lift in LIFTS)
CHANNELS = ("assessment_kg", "prescribed_load_kg", "velocity_mps")
PLAN_VALUES = ("cessation", "step_down", "continue", "step_up")
QUERY_SETS = ("test_a", "test_b", "test_a_noise_replicate", "matched")
BOOTSTRAP_REPLICATES = 1000


def _file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _protocol_digest(protocol: dict[str, Any]) -> str:
    payload = {key: value for key, value in protocol.items() if key != "identities"}
    payload["identities"] = {
        key: value
        for key, value in protocol["identities"].items()
        if key not in {"protocol_digest", "study_id"}
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + _file_sha256(encoded)


def verify_design(root: Path) -> dict[str, Any]:
    protocol = json.loads((root / PROTOCOL_RELATIVE).read_text(encoding="utf-8"))
    evidence_path = root / FROZEN_RELATIVE
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if _protocol_digest(protocol) != protocol["identities"]["protocol_digest"]:
        raise ValueError("RES-290 protocol identity does not match its frozen contents")
    if protocol["frozen_evidence"]["sha256"] != "sha256:" + _file_sha256(
        evidence_path.read_bytes()
    ):
        raise ValueError("RES-290 frozen-evidence digest does not match")
    if protocol["identities"]["study_id"] != (
        "psr:study:public-surrogate-reconstruction-public-native@1.0.0~"
        + protocol["identities"]["protocol_digest"][7:19]
    ):
        raise ValueError("RES-290 study identity does not match the protocol digest")
    for relative, expected in evidence["files"].items():
        actual = "sha256:" + _file_sha256((root / relative).read_bytes())
        if actual != expected:
            raise ValueError(f"frozen public evidence changed: {relative}")
    base = protocol["starting_main"]
    try:
        base_commit_available = (
            subprocess.run(
                ["git", "cat-file", "-e", f"{base}^{{commit}}"],
                cwd=root,
                check=False,
                capture_output=True,
            ).returncode
            == 0
        )
    except FileNotFoundError:
        base_commit_available = False
    if base_commit_available:
        for relative, expected in evidence["historical_g3_homes_at_starting_main"].items():
            result = subprocess.run(
                ["git", "show", f"{base}:{relative}"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            actual = "sha256:" + _file_sha256(result.stdout)
            if actual != expected:
                raise ValueError(f"starting-main G3 home hash changed: {relative}")
        if (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=root, check=False
            ).returncode
            != 0
        ):
            raise ValueError("starting main is not an ancestor of this study checkout")
    # The frozen evidence digest retains these baseline hashes in depth-one CI clones.
    return cast(dict[str, Any], protocol)


def _opaque_id(role: str, source_key: str) -> str:
    token = _file_sha256(f"{role}\0{source_key}".encode())[:24]
    return f"psr-entity-{token}"


def _public_record(row: PublicForecastRow, role: str, include_targets: bool) -> dict[str, Any]:
    record = asdict(row)
    new_id = _opaque_id(role, row.row_id)
    record["row_id"] = new_id
    record["inputs"]["entity_id"] = new_id
    if not include_targets:
        del record["targets"]
    return record


def _generate_split(
    seeds: dict[str, int],
    role: str,
    selected_split: str,
    selected_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    if selected_split == "train":
        train_count, validation_count = selected_count, 12
    else:
        train_count, validation_count = 12, selected_count
    config = GenerationConfig(
        train_rows=train_count,
        validation_rows=validation_count,
        population_seed=seeds["population"],
        intervention_seed=seeds["intervention"],
        observation_seed=seeds["observation"],
        split_seed=seeds["split"],
    )
    visible: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []
    source_entities: dict[str, str] = {}
    for split, row in iter_public_rows(config):
        if split != selected_split:
            continue
        public = _public_record(row, role, include_targets=False)
        labelled = dict(public)
        labelled["targets"] = asdict_targets(row.targets)
        truth.append({"row_id": public["row_id"], "targets": asdict_targets(row.targets)})
        visible.append(labelled if role in {"fitting", "development"} else public)
        source_entities[public["row_id"]] = row.row_id
    if len(visible) != selected_count:
        raise ValueError(f"{role} realization row count mismatch")
    return visible, truth, source_entities


def asdict_targets(targets: PublicCapacityTargets) -> dict[str, float]:
    return {
        "squat_delta_capacity_kg": float(targets["squat_delta_capacity_kg"]),
        "bench_press_delta_capacity_kg": float(targets["bench_press_delta_capacity_kg"]),
        "deadlift_delta_capacity_kg": float(targets["deadlift_delta_capacity_kg"]),
    }


def _generate_matched(
    seeds: dict[str, int], count: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, str]]]:
    if count != 64:
        raise ValueError("matched evaluation count must cover the 64 public history combinations")
    population_rng = random.Random(seeds["population"])
    intervention_rng = random.Random(seeds["intervention"])
    observation_rng = random.Random(seeds["observation"])
    templates_by_entity = sample_history_template_combinations(intervention_rng, count)
    plans = ("cessation", "step_down", "continue", "step_up")
    rows: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []
    authority_keys: dict[str, dict[str, str]] = {}
    for index, templates in enumerate(templates_by_entity):
        athlete = sample_athlete(index, population_rng)
        baseline_plan = declared_plan("continue")
        baseline_sessions = {
            lift: training_sessions(templates[lift_index], baseline_plan)
            for lift_index, lift in enumerate(LIFTS)
        }
        baseline_trajectories = simulate_athlete(athlete, baseline_sessions)
        lift_values: dict[str, LiftInputs] = {}
        for lift_index, lift in enumerate(LIFTS):
            lift_values[lift] = LiftInputs(
                sample_performance_history(
                    baseline_trajectories[lift].expressed_performance_kg,
                    lift,
                    observation_rng,
                ),
                history_segments(templates[lift_index]),
            )
        authority_entity = f"matched-{index:04d}"
        for plan_id in plans:
            plan = declared_plan(plan_id)
            sessions = {
                lift: training_sessions(templates[lift_index], plan)
                for lift_index, lift in enumerate(LIFTS)
            }
            trajectories = simulate_athlete(athlete, sessions)
            for horizon in HORIZONS_DAYS:
                scenario_source_key = f"{authority_entity}:{plan_id}:{horizon}"
                row_id = _opaque_id("matched", scenario_source_key)
                inputs = ForecastInputs(
                    row_id,
                    224,
                    horizon,
                    plan,
                    cast(PublicLiftInputs, lift_values.copy()),
                )
                targets = cast(
                    PublicCapacityTargets,
                    {
                        f"{lift}_delta_capacity_kg": latent_capacity_change(
                            trajectories[lift], 224, horizon
                        )
                        for lift in LIFTS
                    },
                )
                row = PublicForecastRow(row_id, inputs, targets)
                validate_public_row(row)
                public = _public_record(row, "matched", include_targets=False)
                rows.append(public)
                truth.append({"row_id": public["row_id"], "targets": asdict_targets(targets)})
                authority_keys[public["row_id"]] = {
                    "cluster_key": authority_entity,
                    "plan_id": plan_id,
                    "horizon_days": str(horizon),
                }
    if len(rows) != count * len(plans) * len(HORIZONS_DAYS):
        raise ValueError("matched counterfactual realization row count mismatch")
    return rows, truth, authority_keys


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(record) + b"\n" for record in records)


def _queries(
    datasets: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [{"evaluation_set": name, "row": row} for name in QUERY_SETS for row in datasets[name]]


def _run_learner(
    root: Path,
    fitting_rows: list[dict[str, Any]],
    development_rows: list[dict[str, Any]],
    datasets: dict[str, list[dict[str, Any]]],
    resampling_seed: int,
) -> tuple[dict[str, Any], bytes, bytes]:
    source = (root / LEARNER_RELATIVE).read_bytes()
    request = {
        "protocol_id": verify_design(root)["identities"]["study_id"],
        "fitting_rows": fitting_rows,
        "development_rows": development_rows,
        "queries": _queries(datasets),
        "seeds": {"empirical_resampling": resampling_seed},
    }
    payload = canonical_json_bytes(request)
    _authority_payload_audit(source, payload, datasets)
    with tempfile.TemporaryDirectory(prefix="res290-learner-") as temporary:
        sandbox = Path(temporary)
        learner_script = sandbox / "learner.py"
        learner_script.write_bytes(source)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        process = subprocess.run(
            [sys.executable, "-I", str(learner_script)],
            cwd=sandbox,
            env=environment,
            input=payload,
            capture_output=True,
            check=False,
            timeout=180,
        )
    if process.returncode != 0:
        raise RuntimeError(
            "isolated learner failed: " + process.stderr.decode("utf-8", errors="replace")[-2000:]
        )
    output = process.stdout
    result = json.loads(output)
    if result["protocol_id"] != request["protocol_id"]:
        raise ValueError("learner returned a different protocol identity")
    return cast(dict[str, Any], result), payload, output


def _sha_map(data: dict[str, bytes]) -> dict[str, str]:
    return {path: "sha256:" + _file_sha256(value) for path, value in sorted(data.items())}


def _authority_generator_source_hash(root: Path) -> str:
    file_hashes = {
        path: "sha256:" + _file_sha256((root / path).read_bytes())
        for path in DATA_GENERATOR_SOURCE_PATHS
    }
    function_names = (
        "_opaque_id",
        "_public_record",
        "asdict_targets",
        "_generate_split",
        "_generate_matched",
    )
    function_hashes = {
        name: "sha256:" + _file_sha256(inspect.getsource(globals()[name]).encode())
        for name in function_names
    }
    return sha256_record(
        {
            "format": "PSR_RES290_AUTHORITY_GENERATOR_SOURCE_V1",
            "frozen_public_source_files": file_hashes,
            "study_generation_functions": function_hashes,
        }
    )


def _typed_realization_manifest(
    protocol: dict[str, Any], files: dict[str, bytes]
) -> DatasetRealizationManifest:
    rows = {
        "fitting": protocol["splits"]["fitting_rows"],
        "development": protocol["splits"]["development_rows"],
        "test_a": protocol["splits"]["test_population_a_rows"],
        "test_b": protocol["splits"]["test_population_b_rows"],
        "test_a_noise_replicate": protocol["splits"]["paired_noise_replicate_rows"],
        "matched": protocol["splits"]["matched_rows"],
    }
    splits = tuple(
        SplitIdentity(name, purpose, count if name != "matched" else 64, count)
        for name, purpose, count in (
            ("fitting", "learner fitting rows", rows["fitting"]),
            ("development", "learner development selection rows", rows["development"]),
            ("test_a", "held-out population A; authority truth separate", rows["test_a"]),
            ("test_b", "independent held-out population B", rows["test_b"]),
            (
                "test_a_noise_replicate",
                "paired native observation-noise re-realization of test A",
                rows["test_a_noise_replicate"],
            ),
            ("matched", "authority-matched supported plan contrasts", rows["matched"]),
        )
    )
    jsonl = tuple(
        path
        for path in sorted(files)
        if path.startswith("realizations/") and path.endswith(".jsonl")
    )
    artifacts = tuple(
        ArtifactHash(path, _file_sha256(files[path]), "application/x-ndjson") for path in jsonl
    )
    seeds = tuple(
        (f"{split}_{role}", int(seed))
        for split, values in protocol["seeds"].items()
        if isinstance(values, dict)
        for role, seed in values.items()
    )
    seeds += tuple(
        (name, int(protocol["seeds"][name]))
        for name in ("bootstrap", "empirical_resampling", "random_fourier_features")
    )
    observation_rows = sum(rows.values()) * len(LIFTS) * len(HISTORY_OBSERVATION_DAYS)
    return DatasetRealizationManifest(
        dataset_spec_id=protocol["identities"]["dataset_spec_id"],
        realization_id="public-surrogate-reconstruction-public-native",
        generator_identity=(
            "Evaluation Authority only; frozen public-native dataset iterator and matched generator; "
            f"source-set={_authority_generator_source_hash(Path(__file__).resolve().parents[3])}"
        ),
        source_identity=PROTOCOL_RELATIVE,
        seeds=seeds,
        replicate_ids=("test-a", "test-b", "test-a-noise-replicate", "matched"),
        entity_count=(rows["fitting"] + rows["development"] + rows["test_a"] + rows["test_b"] + 64),
        row_count=sum(rows.values()),
        split_identities=splits,
        artifact_hashes=artifacts,
        schema_identity="latent-capacity-transient-participant-row-v2+res290-role-splits-v1",
        temporal_coverage=TemporalCoverage("day", 0, 279),
        realized_intervention_support=tuple(
            SupportSummary(
                f"future_plan:{plan}",
                "Declared participant-visible future-plan category; no off-support plan evaluated.",
            )
            for plan in PLAN_VALUES
        ),
        observation_availability=tuple(
            ObservationAvailability(field, observation_rows, 0)
            for field in ("assessment_kg", "prescribed_load_kg", "velocity_mps")
        ),
        provenance=(
            "New public-native synthetic study realization from independently authored public source. "
            "Canonical M3/M4 data and historical private artifacts were not read. Evaluation truth is "
            "authority-only during fitting and is serialized separately after predictions are sealed."
        ),
        rights=RightsMetadata(
            "MIT",
            "Powerlifting State Research contributors",
            "Generated public synthetic data with attribution; no private historical source material.",
        ),
    )


def _bootstrap_indices(clusters: list[str], rng: np.random.Generator) -> list[int]:
    positions: dict[str, list[int]] = {}
    for index, key in enumerate(clusters):
        positions.setdefault(key, []).append(index)
    units = sorted(positions)
    sampled = rng.choice(np.asarray(units, dtype=object), size=len(units), replace=True)
    return [index for unit in sampled for index in positions[str(unit)]]


def _rmse(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _metric_values(errors: np.ndarray) -> tuple[float, float, float]:
    return _rmse(errors), float(np.mean(np.abs(errors))), float(np.mean(errors))


def _metric_interval(
    errors: np.ndarray,
    clusters: list[str],
    seed: int,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        indices = _bootstrap_indices(clusters, rng)
        values[replicate] = _rmse(errors[indices])
    lower, upper = np.quantile(values, (0.025, 0.975))
    return float(lower), float(upper)


def _metric_intervals(
    errors: np.ndarray, clusters: list[str], seed: int
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    samples = np.empty((BOOTSTRAP_REPLICATES, 3), dtype=np.float64)
    for replicate in range(BOOTSTRAP_REPLICATES):
        indices = _bootstrap_indices(clusters, rng)
        samples[replicate] = _metric_values(errors[indices])
    return {
        name: (float(low), float(high))
        for name, (low, high) in zip(
            ("rmse", "mae", "bias"),
            np.quantile(samples, (0.025, 0.975), axis=0).T,
            strict=True,
        )
    }


def _paired_rmse_interval(
    first: np.ndarray,
    second: np.ndarray,
    clusters: list[str],
    seed: int,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        indices = _bootstrap_indices(clusters, rng)
        values[replicate] = _rmse(first[indices]) - _rmse(second[indices])
    lower, upper = np.quantile(values, (0.025, 0.975))
    return float(lower), float(upper)


def _index_predictions(
    prediction_rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, float]]:
    return {
        (row["evaluation_set"], row["method"], row["row_id"]): row["targets"]
        for row in prediction_rows
    }


def _index_truth(truth_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {row["row_id"]: row["targets"] for row in truth_rows}


def _predictive_tables(
    prediction_rows: list[dict[str, Any]],
    truths: dict[str, list[dict[str, Any]]],
    authority_keys: dict[str, dict[str, str]],
    bootstrap_seed: int,
) -> tuple[bytes, bytes, dict[str, list[dict[str, Any]]]]:
    predictions = _index_predictions(prediction_rows)
    available_methods = {row["method"] for row in prediction_rows}
    metric_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []
    grouped_errors: dict[str, list[dict[str, Any]]] = {}
    contrast_pairs = (
        ("summary_ridge_v1", "empirical_finite_support_resampler_v1"),
        ("sequence_rff_ridge_v1", "summary_ridge_v1"),
    )
    seed_counter = 0
    for evaluation_set in ("test_a", "test_b", "test_a_noise_replicate"):
        truth = _index_truth(truths[evaluation_set])
        visible_rows = truths[f"{evaluation_set}_visible"]
        for lift_index, lift in enumerate(LIFTS):
            target = TARGETS[lift_index]
            for horizon in HORIZONS_DAYS:
                rows = [row for row in visible_rows if row["inputs"]["horizon_days"] == horizon]
                clusters = [authority_keys[evaluation_set][row["row_id"]] for row in rows]
                if len(rows) != 128:
                    raise ValueError("predictive test strata must contain 128 rows per horizon")
                for method in (
                    "empirical_finite_support_resampler_v1",
                    "summary_ridge_v1",
                    "sequence_rff_ridge_v1",
                ):
                    if method not in available_methods:
                        metric_rows.append(
                            {
                                "population": evaluation_set,
                                "lift": lift,
                                "horizon_days": horizon,
                                "method": method,
                                "n_entities": len(rows),
                                "status": "MODEL_FIT_FAILED",
                            }
                        )
                        continue
                    errors = np.asarray(
                        [
                            predictions[(evaluation_set, method, row["row_id"])][target]
                            - truth[row["row_id"]][target]
                            for row in rows
                        ],
                        dtype=np.float64,
                    )
                    rmse, mae, bias = _metric_values(errors)
                    intervals = _metric_intervals(errors, clusters, bootstrap_seed + seed_counter)
                    seed_counter += 1
                    metric_rows.append(
                        {
                            "population": evaluation_set,
                            "lift": lift,
                            "horizon_days": horizon,
                            "method": method,
                            "n_entities": len(rows),
                            "rmse_kg": rmse,
                            "rmse_ci95_lower_kg": intervals["rmse"][0],
                            "rmse_ci95_upper_kg": intervals["rmse"][1],
                            "mae_kg": mae,
                            "mae_ci95_lower_kg": intervals["mae"][0],
                            "mae_ci95_upper_kg": intervals["mae"][1],
                            "signed_bias_kg": bias,
                            "signed_bias_ci95_lower_kg": intervals["bias"][0],
                            "signed_bias_ci95_upper_kg": intervals["bias"][1],
                            "status": "COMPLETE",
                        }
                    )
                    grouped_errors[f"{evaluation_set}|{lift}|{horizon}|{method}"] = [
                        {
                            "cluster": clusters[index],
                            "error": float(errors[index]),
                            "prediction": predictions[
                                (evaluation_set, method, rows[index]["row_id"])
                            ][target],
                            "truth": truth[rows[index]["row_id"]][target],
                        }
                        for index in range(len(rows))
                    ]
                for first_method, second_method in contrast_pairs:
                    if (
                        first_method not in available_methods
                        or second_method not in available_methods
                    ):
                        contrast_rows.append(
                            {
                                "population": evaluation_set,
                                "lift": lift,
                                "horizon_days": horizon,
                                "contrast": f"{first_method}_minus_{second_method}",
                                "status": "MODEL_FIT_FAILED",
                            }
                        )
                        continue
                    first = np.asarray(
                        [
                            predictions[(evaluation_set, first_method, row["row_id"])][target]
                            - truth[row["row_id"]][target]
                            for row in rows
                        ]
                    )
                    second = np.asarray(
                        [
                            predictions[(evaluation_set, second_method, row["row_id"])][target]
                            - truth[row["row_id"]][target]
                            for row in rows
                        ]
                    )
                    lower, upper = _paired_rmse_interval(
                        first, second, clusters, bootstrap_seed + seed_counter
                    )
                    seed_counter += 1
                    contrast_rows.append(
                        {
                            "population": evaluation_set,
                            "lift": lift,
                            "horizon_days": horizon,
                            "contrast": f"{first_method}_minus_{second_method}",
                            "rmse_difference_kg": _rmse(first) - _rmse(second),
                            "ci95_lower_kg": lower,
                            "ci95_upper_kg": upper,
                            "status": "INCONCLUSIVE"
                            if lower <= 0.0 <= upper
                            else "RESOLVED_IN_THIS_REALIZATION",
                        }
                    )
    return (
        _csv_bytes(
            [
                "population",
                "lift",
                "horizon_days",
                "method",
                "n_entities",
                "rmse_kg",
                "rmse_ci95_lower_kg",
                "rmse_ci95_upper_kg",
                "mae_kg",
                "mae_ci95_lower_kg",
                "mae_ci95_upper_kg",
                "signed_bias_kg",
                "signed_bias_ci95_lower_kg",
                "signed_bias_ci95_upper_kg",
                "status",
            ],
            metric_rows,
        ),
        _csv_bytes(
            [
                "population",
                "lift",
                "horizon_days",
                "contrast",
                "rmse_difference_kg",
                "ci95_lower_kg",
                "ci95_upper_kg",
                "status",
            ],
            contrast_rows,
        ),
        grouped_errors,
    )


def _csv_bytes(headers: list[str], rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (f"{value:.10f}" if isinstance(value, float) else value)
                for key, value in row.items()
            }
        )
    return output.getvalue().encode("utf-8")


def _schedule_signature(row: dict[str, Any]) -> str:
    schedules = {lift: row["inputs"]["lifts"][lift]["history_schedule"] for lift in LIFTS}
    return _file_sha256(canonical_json_bytes(schedules))


def _visible_hash(row: dict[str, Any]) -> str:
    inputs = dict(row["inputs"])
    inputs.pop("entity_id", None)
    return _file_sha256(canonical_json_bytes(inputs))


def _history_coverage_rows(
    datasets: dict[str, list[dict[str, Any]]],
    fitting: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fit_cells: dict[str, set[str]] = {}
    for row in fitting:
        cell = f"{row['inputs']['declared_future_plan']['plan_id']}:{row['inputs']['horizon_days']}"
        fit_cells.setdefault(cell, set()).add(_schedule_signature(row))
    result: list[dict[str, Any]] = []
    for name, rows in datasets.items():
        eval_cells: dict[str, set[str]] = {}
        for row in rows:
            cell = f"{row['inputs']['declared_future_plan']['plan_id']}:{row['inputs']['horizon_days']}"
            eval_cells.setdefault(cell, set()).add(_schedule_signature(row))
        for cell in sorted(eval_cells):
            fitting_sigs = fit_cells.get(cell, set())
            evaluation_sigs = eval_cells[cell]
            result.append(
                {
                    "evaluation_set": name,
                    "plan_horizon_cell": cell,
                    "n_rows": sum(
                        1
                        for row in rows
                        if f"{row['inputs']['declared_future_plan']['plan_id']}:{row['inputs']['horizon_days']}"
                        == cell
                    ),
                    "unique_history_combinations": len(evaluation_sigs),
                    "training_history_combinations": len(fitting_sigs),
                    "evaluation_combinations_also_in_training": len(fitting_sigs & evaluation_sigs),
                    "evaluation_combination_fraction_seen_in_training": (
                        len(fitting_sigs & evaluation_sigs) / len(evaluation_sigs)
                    ),
                }
            )
    return result


def _coverage_diagnostics(
    fitting: list[dict[str, Any]], datasets: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    from .public_surrogate_reconstruction_learner import _summary_features

    x_fit = np.asarray([_summary_features(row) for row in fitting])
    minimum = x_fit.min(axis=0)
    maximum = x_fit.max(axis=0)
    center = x_fit.mean(axis=0)
    scale = x_fit.std(axis=0)
    scale[scale == 0.0] = 1.0
    standardized = (x_fit - center) / scale
    coverage: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, float]] = {}
    for name, rows in datasets.items():
        x = np.asarray([_summary_features(row) for row in rows])
        outside = np.any((x < minimum) | (x > maximum), axis=1)
        test_standardized = (x - center) / scale
        squared = (
            np.sum(test_standardized * test_standardized, axis=1)[:, None]
            + np.sum(standardized * standardized, axis=1)[None, :]
            - 2.0 * test_standardized @ standardized.T
        )
        nearest = np.sqrt(np.maximum(0.0, squared.min(axis=1)))
        summaries[name] = {
            "n_rows": float(len(rows)),
            "n_outside_observed_training_extrema": float(outside.sum()),
            "fraction_outside_observed_training_extrema": float(outside.mean()),
            "nearest_training_distance_median": float(np.median(nearest)),
            "nearest_training_distance_p95": float(np.quantile(nearest, 0.95)),
        }
        coverage.append({"evaluation_set": name, **summaries[name]})
    return coverage, summaries


def _observable_distribution_rows(
    fitting: list[dict[str, Any]],
    sample: list[dict[str, Any]],
    evaluation: list[dict[str, Any]],
    seed: int,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    test_groups: dict[str, list[int]] = {}
    for index, item in enumerate(evaluation):
        cell = (
            f"{item['inputs']['declared_future_plan']['plan_id']}:{item['inputs']['horizon_days']}"
        )
        test_groups.setdefault(cell, []).append(index)
    bootstrap_test_indices = [
        [
            int(index)
            for cell in sorted(test_groups)
            for index in rng.choice(test_groups[cell], size=len(test_groups[cell]), replace=True)
        ]
        for _ in range(BOOTSTRAP_REPLICATES)
    ]
    test_signatures = [_schedule_signature(item) for item in evaluation]
    sample_signatures = [_schedule_signature(item) for item in sample]

    def total_variation(left: list[str], right: list[str]) -> float:
        support = set(left) | set(right)
        return 0.5 * math.fsum(
            abs(left.count(key) / len(left) - right.count(key) / len(right)) for key in support
        )

    sample_schedule_counts: dict[str, int] = {}
    evaluation_schedule_counts: dict[str, int] = {}
    for record, counts in (
        (sample, sample_schedule_counts),
        (evaluation, evaluation_schedule_counts),
    ):
        for item in record:
            key = _schedule_signature(item)
            counts[key] = counts.get(key, 0) + 1
    schedule_tvd = total_variation(sample_signatures, test_signatures)
    schedule_bootstrap = np.asarray(
        [
            total_variation(
                sample_signatures,
                [test_signatures[index] for index in selected],
            )
            for selected in bootstrap_test_indices
        ],
        dtype=np.float64,
    )
    schedule_lower, schedule_upper = np.quantile(schedule_bootstrap, (0.025, 0.975))
    rows.append(
        {
            "metric": "history_schedule_combination_total_variation",
            "lift": "all",
            "channel": "schedule",
            "unit": "probability",
            "value": schedule_tvd,
            "ci95_lower": float(schedule_lower),
            "ci95_upper": float(schedule_upper),
            "n_entities": len(evaluation),
        }
    )
    plan_names: set[str] = set()
    for record in (sample, evaluation):
        plan_names.update(
            f"{item['inputs']['declared_future_plan']['plan_id']}:{item['inputs']['horizon_days']}"
            for item in record
        )
    sample_plan_counts = {
        name: sum(
            1
            for item in sample
            if f"{item['inputs']['declared_future_plan']['plan_id']}:{item['inputs']['horizon_days']}"
            == name
        )
        for name in plan_names
    }
    eval_plan_counts = {
        name: sum(
            1
            for item in evaluation
            if f"{item['inputs']['declared_future_plan']['plan_id']}:{item['inputs']['horizon_days']}"
            == name
        )
        for name in plan_names
    }
    plan_tvd = 0.5 * math.fsum(
        abs(sample_plan_counts[name] / len(sample) - eval_plan_counts[name] / len(evaluation))
        for name in plan_names
    )
    rows.append(
        {
            "metric": "plan_horizon_total_variation",
            "lift": "all",
            "channel": "declared_plan",
            "unit": "probability",
            "value": plan_tvd,
            "ci95_lower": plan_tvd,
            "ci95_upper": plan_tvd,
            "n_entities": len(evaluation),
        }
    )

    from .public_surrogate_reconstruction_learner import _summary_features

    fit_summary = np.asarray([_summary_features(row) for row in fitting])
    sample_summary = np.asarray([_summary_features(row) for row in sample])
    eval_summary = np.asarray([_summary_features(row) for row in evaluation])

    fit_deviation = fit_summary.std(axis=0)
    keep = fit_deviation > 0.0

    def correlation(matrix: np.ndarray) -> np.ndarray:
        selected = matrix[:, keep]
        values = selected.std(axis=0)
        values[values == 0.0] = 1.0
        if not np.any(keep):
            return np.zeros((0, 0), dtype=np.float64)
        normalized = (selected - selected.mean(axis=0)) / values
        return np.asarray(normalized.T @ normalized / matrix.shape[0], dtype=np.float64)

    sample_corr = correlation(sample_summary)
    eval_corr = correlation(eval_summary)
    corr_error = float(np.linalg.norm(sample_corr - eval_corr, ord="fro"))
    corr_bootstrap = np.asarray(
        [
            float(
                np.linalg.norm(
                    sample_corr - correlation(eval_summary[selected]),
                    ord="fro",
                )
            )
            for selected in bootstrap_test_indices
        ],
        dtype=np.float64,
    )
    corr_lower, corr_upper = np.quantile(corr_bootstrap, (0.025, 0.975))
    rows.append(
        {
            "metric": "visible_summary_correlation_frobenius",
            "lift": "all",
            "channel": "58_summary_features",
            "unit": "correlation_matrix_frobenius",
            "value": corr_error,
            "ci95_lower": float(corr_lower),
            "ci95_upper": float(corr_upper),
            "n_entities": len(evaluation),
        }
    )

    bootstrap = np.empty((BOOTSTRAP_REPLICATES, len(LIFTS) * len(CHANNELS)), dtype=np.float64)
    train_values = {
        (lift, channel): np.asarray(
            [
                [observation[channel] for observation in item["inputs"]["lifts"][lift]["history"]]
                for item in fitting
            ],
            dtype=np.float64,
        )
        for lift in LIFTS
        for channel in CHANNELS
    }
    sample_values = {
        (lift, channel): np.asarray(
            [
                [observation[channel] for observation in item["inputs"]["lifts"][lift]["history"]]
                for item in sample
            ],
            dtype=np.float64,
        )
        for lift in LIFTS
        for channel in CHANNELS
    }
    evaluation_values = {
        (lift, channel): np.asarray(
            [
                [observation[channel] for observation in item["inputs"]["lifts"][lift]["history"]]
                for item in evaluation
            ],
            dtype=np.float64,
        )
        for lift in LIFTS
        for channel in CHANNELS
    }

    def normalized_w1(generated: np.ndarray, observed: np.ndarray, fit_scale: np.ndarray) -> float:
        distances = np.mean(np.abs(np.sort(generated, axis=0) - np.sort(observed, axis=0)), axis=0)
        return float(np.mean(distances / fit_scale))

    for feature_index, (lift, channel) in enumerate(
        (lift, channel) for lift in LIFTS for channel in CHANNELS
    ):
        train = train_values[(lift, channel)]
        synthetic = sample_values[(lift, channel)]
        observed = evaluation_values[(lift, channel)]
        feature_scale = train.std(axis=0)
        feature_scale[feature_scale == 0.0] = 1.0
        value = normalized_w1(synthetic, observed, feature_scale)
        for replicate, indices in enumerate(bootstrap_test_indices):
            bootstrap[replicate, feature_index] = normalized_w1(
                synthetic, observed[indices], feature_scale
            )
        lower, upper = np.quantile(bootstrap[:, feature_index], (0.025, 0.975))
        rows.append(
            {
                "metric": "visible_field_wasserstein_1_normalized",
                "lift": lift,
                "channel": channel,
                "unit": f"training_sd({channel})",
                "value": value,
                "ci95_lower": float(lower),
                "ci95_upper": float(upper),
                "n_entities": len(evaluation),
            }
        )
    return rows


def _noise_sensitivity_rows(
    predictions: list[dict[str, Any]],
    truths: dict[str, list[dict[str, Any]]],
    authority_keys: dict[str, dict[str, str]],
    seed: int,
) -> list[dict[str, Any]]:
    by_prediction = _index_predictions(predictions)
    available_methods = {row["method"] for row in predictions}
    truth_a = _index_truth(truths["test_a"])
    truth_b = _index_truth(truths["test_a_noise_replicate"])
    a_by_cluster = {authority_keys["test_a"][row_id]: row_id for row_id in truth_a}
    b_by_cluster = {authority_keys["test_a_noise_replicate"][row_id]: row_id for row_id in truth_b}
    if set(a_by_cluster) != set(b_by_cluster):
        raise ValueError("paired observation-noise replicate entities do not align")
    rows: list[dict[str, Any]] = []
    counter = 0
    for method in (
        "empirical_finite_support_resampler_v1",
        "summary_ridge_v1",
        "sequence_rff_ridge_v1",
    ):
        if method not in available_methods:
            rows.extend(
                {
                    "method": method,
                    "lift": lift,
                    "horizon_days": horizon,
                    "n_entities": 128,
                    "status": "MODEL_FIT_FAILED",
                }
                for lift in LIFTS
                for horizon in HORIZONS_DAYS
            )
            continue
        for lift_index, lift in enumerate(LIFTS):
            target = TARGETS[lift_index]
            for horizon in HORIZONS_DAYS:
                clusters = sorted(a_by_cluster)
                selected = [
                    cluster
                    for cluster in clusters
                    if truth_a[a_by_cluster[cluster]] and truth_b[b_by_cluster[cluster]]
                ]
                selected = [
                    cluster
                    for cluster in selected
                    if any(
                        item["row_id"] == a_by_cluster[cluster]
                        and item["inputs"]["horizon_days"] == horizon
                        for item in truths["test_a_visible"]
                    )
                ]
                errors_a = np.asarray(
                    [
                        by_prediction[("test_a", method, a_by_cluster[cluster])][target]
                        - truth_a[a_by_cluster[cluster]][target]
                        for cluster in selected
                    ]
                )
                errors_b = np.asarray(
                    [
                        by_prediction[("test_a_noise_replicate", method, b_by_cluster[cluster])][
                            target
                        ]
                        - truth_b[b_by_cluster[cluster]][target]
                        for cluster in selected
                    ]
                )
                if len(selected) != 128:
                    raise ValueError("paired noise replicate stratum must contain 128 entities")
                lower, upper = _paired_rmse_interval(errors_b, errors_a, selected, seed + counter)
                counter += 1
                pred_change = np.asarray(
                    [
                        by_prediction[("test_a_noise_replicate", method, b_by_cluster[cluster])][
                            target
                        ]
                        - by_prediction[("test_a", method, a_by_cluster[cluster])][target]
                        for cluster in selected
                    ]
                )
                pred_change_lower, pred_change_upper = _mean_interval(
                    np.abs(pred_change), selected, seed + counter
                )
                counter += 1
                rows.append(
                    {
                        "method": method,
                        "lift": lift,
                        "horizon_days": horizon,
                        "n_entities": len(selected),
                        "rmse_replicate_minus_test_a_kg": _rmse(errors_b) - _rmse(errors_a),
                        "ci95_lower_kg": lower,
                        "ci95_upper_kg": upper,
                        "mean_abs_prediction_change_kg": float(np.mean(np.abs(pred_change))),
                        "mean_abs_prediction_change_ci95_lower_kg": pred_change_lower,
                        "mean_abs_prediction_change_ci95_upper_kg": pred_change_upper,
                        "status": "INCONCLUSIVE"
                        if lower <= 0.0 <= upper
                        else "RESOLVED_IN_THIS_REALIZATION",
                    }
                )
    return rows


def _matched_response_rows(
    predictions: list[dict[str, Any]],
    truths: dict[str, list[dict[str, Any]]],
    authority_keys: dict[str, Any],
    seed: int,
) -> bytes:
    by_prediction = _index_predictions(predictions)
    available_methods = {row["method"] for row in predictions}
    truth = _index_truth(truths["matched"])
    row_ids = list(truth)
    groups: dict[str, dict[tuple[str, int], str]] = {}
    for row_id in row_ids:
        key = authority_keys["matched"][row_id]
        groups.setdefault(key["cluster_key"], {})[(key["plan_id"], int(key["horizon_days"]))] = (
            row_id
        )
    rows: list[dict[str, Any]] = []
    counter = 0
    for method in (
        "empirical_finite_support_resampler_v1",
        "summary_ridge_v1",
        "sequence_rff_ridge_v1",
    ):
        if method not in available_methods:
            for lift in LIFTS:
                for horizon in HORIZONS_DAYS:
                    for plan in ("cessation", "step_down", "step_up"):
                        rows.append(
                            {
                                "method": method,
                                "lift": lift,
                                "horizon_days": horizon,
                                "plan_contrast": f"{plan}_minus_continue",
                                "n_matched_entities": len(groups),
                                "status": "MODEL_FIT_FAILED",
                            }
                        )
            continue
        for lift_index, lift in enumerate(LIFTS):
            target = TARGETS[lift_index]
            for horizon in HORIZONS_DAYS:
                for plan in ("cessation", "step_down", "step_up"):
                    errors: list[float] = []
                    clusters: list[str] = []
                    for cluster, cases in groups.items():
                        base_id = cases[("continue", horizon)]
                        plan_id = cases[(plan, horizon)]
                        true_effect = truth[plan_id][target] - truth[base_id][target]
                        predicted_effect = (
                            by_prediction[("matched", method, plan_id)][target]
                            - by_prediction[("matched", method, base_id)][target]
                        )
                        errors.append(predicted_effect - true_effect)
                        clusters.append(cluster)
                    values = np.asarray(errors, dtype=np.float64)
                    intervals = _metric_intervals(values, clusters, seed + counter)
                    counter += 1
                    rmse, mae, bias = _metric_values(values)
                    rows.append(
                        {
                            "method": method,
                            "lift": lift,
                            "horizon_days": horizon,
                            "plan_contrast": f"{plan}_minus_continue",
                            "n_matched_entities": len(clusters),
                            "rmse_kg": rmse,
                            "rmse_ci95_lower_kg": intervals["rmse"][0],
                            "rmse_ci95_upper_kg": intervals["rmse"][1],
                            "mae_kg": mae,
                            "mae_ci95_lower_kg": intervals["mae"][0],
                            "mae_ci95_upper_kg": intervals["mae"][1],
                            "signed_bias_kg": bias,
                            "signed_bias_ci95_lower_kg": intervals["bias"][0],
                            "signed_bias_ci95_upper_kg": intervals["bias"][1],
                            "status": "COMPLETE",
                        }
                    )
    return _csv_bytes(
        [
            "method",
            "lift",
            "horizon_days",
            "plan_contrast",
            "n_matched_entities",
            "rmse_kg",
            "rmse_ci95_lower_kg",
            "rmse_ci95_upper_kg",
            "mae_kg",
            "mae_ci95_lower_kg",
            "mae_ci95_upper_kg",
            "signed_bias_kg",
            "signed_bias_ci95_lower_kg",
            "signed_bias_ci95_upper_kg",
            "status",
        ],
        rows,
    )


def _claims_rows(
    metric_csv: bytes,
    contrasts_csv: bytes,
    noise_rows: list[dict[str, Any]],
    matched_csv: bytes,
    overlap_count: int,
    learner_audit: dict[str, Any],
    method_failures: list[dict[str, Any]],
) -> bytes:
    metrics = list(csv.DictReader(io.StringIO(metric_csv.decode("utf-8"))))
    contrasts = list(csv.DictReader(io.StringIO(contrasts_csv.decode("utf-8"))))
    matched = list(csv.DictReader(io.StringIO(matched_csv.decode("utf-8"))))
    conditional_metrics = [
        row
        for row in metrics
        if row["method"] in {"summary_ridge_v1", "sequence_rff_ridge_v1"}
        and row.get("status") == "COMPLETE"
    ]
    baseline_metrics = [
        row
        for row in metrics
        if row["method"] == "empirical_finite_support_resampler_v1"
        and row.get("status") == "COMPLETE"
    ]
    better = sum(
        float(row["rmse_kg"])
        < min(
            float(other["rmse_kg"])
            for other in baseline_metrics
            if other["population"] == row["population"]
            and other["lift"] == row["lift"]
            and other["horizon_days"] == row["horizon_days"]
        )
        for row in conditional_metrics
    )
    rff_summary = [
        row
        for row in contrasts
        if row["contrast"] == "sequence_rff_ridge_v1_minus_summary_ridge_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    summary_empirical = [
        row
        for row in contrasts
        if row["contrast"] == "summary_ridge_v1_minus_empirical_finite_support_resampler_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    rff_higher = sum(float(row["rmse_difference_kg"]) > 0 for row in rff_summary)
    rff_resolved = sum(row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in rff_summary)
    summary_empirical_resolved = sum(
        row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in summary_empirical
    )
    summary_empirical_inconclusive = sum(
        row["status"] == "INCONCLUSIVE" for row in summary_empirical
    )
    response_cells = len(matched)
    noise_resolved = sum(row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in noise_rows)
    values = [
        {
            "claim": "Original historical G3 experiment was reproduced",
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "evidence": "historical-lineage.md",
            "limit": "No rights-cleared historical G3 protocol, data, model, or result survives in the public home.",
        },
        {
            "claim": "At least one conditional learner has lower point RMSE than the empirical plan-by-horizon prediction baseline",
            "status": f"LOWER_POINT_RMSE_CELLS_{better}_OF_{len(conditional_metrics)}",
            "evidence": "predictive-metrics.csv and paired-model-comparisons.csv",
            "limit": "Point-error cell count only; it does not assert an inferential improvement. See paired entity-bootstrap intervals.",
        },
        {
            "claim": "Sequence RFF and Summary Ridge have distinguishable prediction error",
            "status": f"RFF_HIGHER_RMSE_IN_{rff_higher}_OF_{len(rff_summary)};RESOLVED_{rff_resolved}_OF_{len(rff_summary)}",
            "evidence": "paired-model-comparisons.csv",
            "limit": "Entity-bootstrap result for this finite realization; method differences do not identify the source mechanism.",
        },
        {
            "claim": "Summary Ridge versus empirical plan-by-horizon error difference is resolved in some cells",
            "status": f"RESOLVED_{summary_empirical_resolved}_OF_{len(summary_empirical)};INCONCLUSIVE_{summary_empirical_inconclusive}_OF_{len(summary_empirical)}",
            "evidence": "paired-model-comparisons.csv",
            "limit": "Resolved contrasts have Summary Ridge higher RMSE; remaining cells are inconclusive.",
        },
        {
            "claim": "An observationally similar fitted pair with different matched response surfaces was demonstrated",
            "status": "NOT_DEMONSTRATED",
            "evidence": "paired-model-comparisons.csv and surrogate-disagreement.csv",
            "limit": "The two conditional models were distinguishable on held-out RMSE; no practical equivalence margin was frozen for declaring observational similarity.",
        },
        {
            "claim": "A with-replacement empirical generator learns a new support beyond its observed training rows",
            "status": "NO",
            "evidence": "support-coverage.csv and empirical-samples.jsonl",
            "limit": f"Generated rows are finite donor copies; exact held-out row overlap is {overlap_count}.",
        },
        {
            "claim": "Observation-noise re-realization changes conditional test error",
            "status": f"RESOLVED_CELLS_{noise_resolved}_OF_{len(noise_rows)}",
            "evidence": "noise-sensitivity.csv",
            "limit": "This compares independent native-noise draws at the same native noise law, not a noise-scale intervention.",
        },
        {
            "claim": "Matched supported future-plan response fidelity was measured",
            "status": f"MEASURED_{response_cells}_METHOD_CELLS",
            "evidence": "matched-response.csv",
            "limit": "Authority-generated synthetic matched interventions only; no real-world causal claim.",
        },
        {
            "claim": "Any predictive or observable-distribution match establishes source structural equivalence or system identification",
            "status": "NOT_ESTABLISHED",
            "evidence": "formal-specification.md and matched-response.csv",
            "limit": "Finite public samples and distinct fitted algorithms do not identify the source mechanism.",
        },
        {
            "claim": "Learner/evaluation information firewall passed",
            "status": "PASS" if learner_audit["passed"] else "FAIL",
            "evidence": "learner-input-audit.json and manifest.json",
            "limit": "Enforced process boundary, strict payload, runtime guard, and withheld test targets.",
        },
        {
            "claim": "A frozen surrogate family failed its declared fitting budget",
            "status": "MODEL_FIT_FAILED" if method_failures else "NO_METHOD_FAILURES",
            "evidence": "method-failures.json",
            "limit": "Every failed family and failed tuning configuration is retained; successful families continue independently.",
        },
        {
            "claim": "Extrapolation beyond declared public plan/schema support is characterized",
            "status": "UNSUPPORTED_BY_PROTOCOL",
            "evidence": "support-coverage.csv",
            "limit": "No off-support target is generated or scored.",
        },
        {
            "claim": "Real-athlete or causal training-effect transfer",
            "status": "PROHIBITED",
            "evidence": "formal-specification.md",
            "limit": "The source and every study realization are synthetic.",
        },
    ]
    headers = ["claim", "status", "evidence", "limit"]
    return _csv_bytes(headers, values)


def _authority_payload_audit(
    learner_source: bytes, payload: bytes, datasets: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    import ast

    tree = ast.parse(learner_source)
    allowed_imports = {"__future__", "json", "math", "sys", "typing", "numpy"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    if not imported <= allowed_imports:
        raise ValueError(
            f"learner imports outside allow-list: {sorted(imported - allowed_imports)}"
        )
    forbidden_calls = {"open", "eval", "exec", "compile", "__import__"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if calls & forbidden_calls:
        raise ValueError(
            f"learner contains a forbidden dynamic/file call: {sorted(calls & forbidden_calls)}"
        )
    forbidden_import_roots = {
        "benchmarks",
        "evaluation",
        "provenance",
        "audits",
    }
    if imported & forbidden_import_roots:
        raise ValueError("learner source imports authority-only repository modules")
    request = json.loads(payload)
    query_rows = [query["row"] for query in request["queries"]]
    if any("targets" in row for row in query_rows):
        raise ValueError("evaluation targets entered the learner payload")
    forbidden_keys = {
        "latent_states",
        "population_coordinates",
        "source_parameters",
        "true_parameters",
        "true_capacity",
        "latent_capacity",
        "evaluation_truth",
    }

    def walk(value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    found.append(key)
                found.extend(walk(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(walk(child))
        return found

    leaked = walk(request)
    if leaked:
        raise ValueError(f"forbidden authority fields entered the learner payload: {leaked}")
    fit = {row["row_id"] for row in request["fitting_rows"]}
    dev = {row["row_id"] for row in request["development_rows"]}
    query = {row["row_id"] for row in query_rows}
    if fit & dev or fit & query or dev & query:
        raise ValueError("participant-visible entity splits overlap")
    counts = {name: len(rows) for name, rows in datasets.items()}
    return {
        "passed": True,
        "allowed_imports": sorted(imported),
        "fitting_rows": len(fit),
        "development_rows": len(dev),
        "query_rows": len(query),
        "query_rows_by_evaluation_set": counts,
        "evaluation_target_fields_in_payload": 0,
        "forbidden_authority_fields_in_payload": 0,
        "fitting_development_test_entities_disjoint": True,
        "learner_source_sha256": "sha256:" + _file_sha256(learner_source),
        "payload_sha256": "sha256:" + _file_sha256(payload),
        "runtime": "isolated Python subprocess with file/network/subprocess audit guard",
    }


def _source_hashes(root: Path) -> dict[str, str]:
    paths = (
        PROTOCOL_RELATIVE,
        FROZEN_RELATIVE,
        LEARNER_RELATIVE,
        EVALUATOR_RELATIVE,
        "studies/public_surrogate_reconstruction/formal-specification.md",
        "studies/public_surrogate_reconstruction/historical-lineage.md",
    )
    return {path: "sha256:" + _file_sha256((root / path).read_bytes()) for path in paths}


def _build_inputs(root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    seeds = protocol["seeds"]
    fitting, _, fit_keys = _generate_split(
        seeds["fitting"], "fitting", "train", protocol["splits"]["fitting_rows"]
    )
    development, _, dev_keys = _generate_split(
        seeds["development"], "development", "validation", protocol["splits"]["development_rows"]
    )
    test_a, truth_a, keys_a = _generate_split(
        seeds["test_population_a"],
        "test-a",
        "validation",
        protocol["splits"]["test_population_a_rows"],
    )
    test_b, truth_b, keys_b = _generate_split(
        seeds["test_population_b"],
        "test-b",
        "validation",
        protocol["splits"]["test_population_b_rows"],
    )
    noise, truth_noise, noise_keys = _generate_split(
        seeds["test_a_noise_replicate"],
        "noise-replicate",
        "validation",
        protocol["splits"]["paired_noise_replicate_rows"],
    )
    matched, truth_matched, matched_keys = _generate_matched(
        seeds["matched_evaluation"], protocol["splits"]["matched_entities"]
    )
    truth_a_by_source = {keys_a[row["row_id"]]: row["targets"] for row in truth_a}
    truth_noise_by_source = {noise_keys[row["row_id"]]: row["targets"] for row in truth_noise}
    if truth_a_by_source != truth_noise_by_source:
        raise ValueError("paired noise replicate changed target truth or entity assignment")
    visible = {
        "test_a": test_a,
        "test_b": test_b,
        "test_a_noise_replicate": noise,
        "matched": matched,
    }
    if set(row["row_id"] for row in fitting) & set(row["row_id"] for row in development):
        raise ValueError("fitting and development row IDs overlap")
    all_entities = [
        {row["row_id"] for row in records}
        for records in [fitting, development, test_a, test_b, noise, matched]
    ]
    for i, left in enumerate(all_entities):
        for right in all_entities[i + 1 :]:
            if left & right:
                raise ValueError("study split identities overlap")
    truth = {
        "test_a": truth_a,
        "test_b": truth_b,
        "test_a_noise_replicate": truth_noise,
        "matched": truth_matched,
        "test_a_visible": test_a,
        "test_b_visible": test_b,
        "test_a_noise_replicate_visible": noise,
    }
    authority_keys: dict[str, Any] = {
        "test_a": keys_a,
        "test_b": keys_b,
        "test_a_noise_replicate": noise_keys,
        "matched": matched_keys,
    }
    return {
        "fitting": fitting,
        "development": development,
        "datasets": visible,
        "truth": truth,
        "authority_keys": authority_keys,
        "source_entity_keys": {
            "fitting": fit_keys,
            "development": dev_keys,
            "test_a": keys_a,
            "test_b": keys_b,
            "test_a_noise_replicate": noise_keys,
        },
    }


def _directory_artifacts(
    root: Path,
    protocol: dict[str, Any],
    experiment: dict[str, Any],
    learner_result: dict[str, Any],
    payload: bytes,
    output: bytes,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    fitting = experiment["fitting"]
    development = experiment["development"]
    datasets = experiment["datasets"]
    truths = experiment["truth"]
    authority_keys = experiment["authority_keys"]
    prediction_rows = learner_result["predictions"]

    learner_source = (root / LEARNER_RELATIVE).read_bytes()
    learner_audit = _authority_payload_audit(learner_source, payload, datasets)
    predictions_bytes = _jsonl(prediction_rows)
    predicted_seal = _file_sha256(predictions_bytes)
    # This value is checked before any truth is joined to a prediction.
    if predicted_seal != _file_sha256(_jsonl(learner_result["predictions"])):
        raise ValueError("prediction bytes did not seal deterministically")
    learner_audit["sealed_prediction_sha256"] = "sha256:" + predicted_seal
    learner_audit["learner_stdout_sha256"] = "sha256:" + _file_sha256(output)

    all_truth = {
        "test_a": truths["test_a"],
        "test_b": truths["test_b"],
        "test_a_noise_replicate": truths["test_a_noise_replicate"],
        "matched": truths["matched"],
    }
    realization_files: dict[str, bytes] = {
        "realizations/fitting.jsonl": _jsonl(fitting),
        "realizations/development.jsonl": _jsonl(development),
        "realizations/test-a-visible.jsonl": _jsonl(datasets["test_a"]),
        "realizations/test-a-truth.jsonl": _jsonl(all_truth["test_a"]),
        "realizations/test-b-visible.jsonl": _jsonl(datasets["test_b"]),
        "realizations/test-b-truth.jsonl": _jsonl(all_truth["test_b"]),
        "realizations/test-a-noise-replicate-visible.jsonl": _jsonl(
            datasets["test_a_noise_replicate"]
        ),
        "realizations/test-a-noise-replicate-truth.jsonl": _jsonl(
            all_truth["test_a_noise_replicate"]
        ),
        "realizations/matched-visible.jsonl": _jsonl(datasets["matched"]),
        "realizations/matched-authority-truth.jsonl": _jsonl(
            [
                {
                    **row,
                    "authority_cluster_key": authority_keys["matched"][row["row_id"]][
                        "cluster_key"
                    ],
                }
                for row in all_truth["matched"]
            ]
        ),
        "predictions.jsonl": predictions_bytes,
        "empirical-samples.jsonl": _jsonl(learner_result["empirical_sample"]),
    }

    dataset_manifest = _typed_realization_manifest(protocol, realization_files)
    realization_digest = dataset_manifest.realization_digest
    realization_id = dataset_manifest.identity_id
    manifest_digest = dataset_manifest.manifest_digest
    dataset_manifest_json = json.loads(dataset_manifest.canonical_serialization)
    dataset_manifest_json.update(
        {
            "identity_id": realization_id,
            "realization_digest": realization_digest,
            "manifest_digest": manifest_digest,
        }
    )
    realization_files["dataset-realization.json"] = (
        canonical_json_bytes(dataset_manifest_json) + b"\n"
    )

    predictive_csv, contrast_csv, grouped_errors = _predictive_tables(
        prediction_rows,
        truths,
        authority_keys,
        int(protocol["seeds"]["bootstrap"]),
    )
    matched_csv = _matched_response_rows(
        prediction_rows,
        truths,
        authority_keys,
        int(protocol["seeds"]["bootstrap"]) + 3000,
    )
    noise_rows = _noise_sensitivity_rows(
        prediction_rows,
        truths,
        authority_keys,
        int(protocol["seeds"]["bootstrap"]) + 6000,
    )
    coverage_datasets = {"fitting": fitting, "development": development, **datasets}
    coverage_rows = _history_coverage_rows(coverage_datasets, fitting)
    coverage_diagnostics, coverage_summary = _coverage_diagnostics(
        fitting, {"development": development, **datasets}
    )
    empirical_sample = learner_result["empirical_sample"]
    observable_rows = _observable_distribution_rows(
        fitting,
        empirical_sample,
        datasets["test_a"],
        int(protocol["seeds"]["bootstrap"]) + 9000,
    )
    train_hashes = {_visible_hash(row) for row in fitting}
    test_hashes = {_visible_hash(row) for row in datasets["test_a"]}
    exact_overlap = len(train_hashes & test_hashes)
    sample_donors = [row["donor_row_id"] for row in empirical_sample]
    unique_donors = len(set(sample_donors))
    memorization = {
        "generated_record_count": len(empirical_sample),
        "exact_donor_copy_fraction": sum(
            donor in {row["row_id"] for row in fitting} for donor in sample_donors
        )
        / len(empirical_sample),
        "unique_donor_count": unique_donors,
        "duplicate_draw_fraction": 1.0 - unique_donors / len(empirical_sample),
        "exact_fitting_test_visible_record_overlap": exact_overlap,
        "exact_fitting_test_visible_record_overlap_fraction": exact_overlap / len(test_hashes),
    }
    fit_hash = _file_sha256(realization_files["realizations/fitting.jsonl"])
    dev_hash = _file_sha256(realization_files["realizations/development.jsonl"])
    state_bytes = canonical_json_bytes(learner_result["fitted_models"])
    fitted_state_hash = _file_sha256(state_bytes)
    source_hashes = _source_hashes(root)
    fitted_models: list[dict[str, Any]] = []
    for family, state in sorted(learner_result["fitted_models"].items()):
        state_hash = _file_sha256(canonical_json_bytes(state))
        model_digest = sha256_record(
            {
                "format": "PSR_RES290_FITTED_SURROGATE_V1",
                "protocol_id": protocol["identities"]["study_id"],
                "family": family,
                "fitting_artifact_sha256": "sha256:" + fit_hash,
                "development_artifact_sha256": "sha256:" + dev_hash,
                "learner_source_sha256": source_hashes[LEARNER_RELATIVE],
                "state_sha256": "sha256:" + state_hash,
            }
        )
        fitted_instance_id = (
            "psr:fitted-instance:res290-"
            f"{family.removesuffix('_v1').replace('_', '-')}@1.0.0~"
            f"{model_digest[7:19]}"
        )
        require_scientific_id(
            fitted_instance_id, "RES-290 fitted instance", expected_class="fitted-instance"
        )
        fitted_models.append(
            {
                "family": family,
                "fitted_instance_id": fitted_instance_id,
                "identity_digest": model_digest,
                "fitting_artifact_sha256": "sha256:" + fit_hash,
                "development_artifact_sha256": "sha256:" + dev_hash,
                "state_sha256": "sha256:" + state_hash,
                "parameter_count": int(state.get("parameter_count", 0)),
                "selected_alpha": state.get("selected_alpha", state.get("alpha")),
                "selected_gamma": state.get("selected_gamma", state.get("gamma")),
            }
        )

    support_csv = _csv_bytes(
        [
            "evaluation_set",
            "plan_horizon_cell",
            "n_rows",
            "unique_history_combinations",
            "training_history_combinations",
            "evaluation_combinations_also_in_training",
            "evaluation_combination_fraction_seen_in_training",
        ],
        coverage_rows,
    )
    geometry_csv = _csv_bytes(
        [
            "evaluation_set",
            "n_rows",
            "n_outside_observed_training_extrema",
            "fraction_outside_observed_training_extrema",
            "nearest_training_distance_median",
            "nearest_training_distance_p95",
            "interpretation",
        ],
        [
            {
                **row,
                "interpretation": "sample-extrema diagnostic only; not true population support",
            }
            for row in coverage_diagnostics
        ],
    )
    observable_csv = _csv_bytes(
        [
            "metric",
            "lift",
            "channel",
            "unit",
            "value",
            "ci95_lower",
            "ci95_upper",
            "n_entities",
        ],
        observable_rows,
    )
    noise_csv = _csv_bytes(
        [
            "method",
            "lift",
            "horizon_days",
            "n_entities",
            "rmse_replicate_minus_test_a_kg",
            "ci95_lower_kg",
            "ci95_upper_kg",
            "mean_abs_prediction_change_kg",
            "mean_abs_prediction_change_ci95_lower_kg",
            "mean_abs_prediction_change_ci95_upper_kg",
            "status",
        ],
        noise_rows,
    )
    disagreement_csv = _surrogate_disagreement_rows(
        prediction_rows,
        datasets,
        authority_keys,
        int(protocol["seeds"]["bootstrap"]) + 12000,
    )
    selection_bytes = canonical_json_bytes(learner_result["development_selection"]) + b"\n"
    audit_bytes = canonical_json_bytes(learner_audit) + b"\n"
    fitted_bytes = canonical_json_bytes(learner_result["fitted_models"]) + b"\n"
    fitted_identity_bytes = canonical_json_bytes(fitted_models) + b"\n"
    method_failures = learner_result["method_failures"]
    method_failures_bytes = canonical_json_bytes(method_failures) + b"\n"
    tables = {
        "predictive-metrics.csv": predictive_csv,
        "paired-model-comparisons.csv": contrast_csv,
        "matched-response.csv": matched_csv,
        "observable-distribution.csv": observable_csv,
        "support-coverage.csv": support_csv,
        "sampling-geometry.csv": geometry_csv,
        "noise-sensitivity.csv": noise_csv,
        "surrogate-disagreement.csv": disagreement_csv,
        "development-selection.json": selection_bytes,
        "fitted-models.json": fitted_bytes,
        "fitted-model-identities.json": fitted_identity_bytes,
        "learner-input-audit.json": audit_bytes,
        "method-failures.json": method_failures_bytes,
    }
    return {
        **realization_files,
        **tables,
    }, {
        "protocol_id": protocol["identities"]["study_id"],
        "protocol_digest": protocol["identities"]["protocol_digest"],
        "realization_id": realization_id,
        "realization_digest": realization_digest,
        "manifest_digest": manifest_digest,
        "source_hashes": source_hashes,
        "fitted_models": fitted_models,
        "method_failures": method_failures,
        "learner_audit": learner_audit,
        "coverage_summary": coverage_summary,
        "coverage_rows": coverage_rows,
        "geometry_rows": coverage_diagnostics,
        "memorization": memorization,
        "exact_overlap": exact_overlap,
        "metrics": list(csv.DictReader(io.StringIO(predictive_csv.decode("utf-8")))),
        "contrasts": list(csv.DictReader(io.StringIO(contrast_csv.decode("utf-8")))),
        "matched": list(csv.DictReader(io.StringIO(matched_csv.decode("utf-8")))),
        "noise": noise_rows,
        "observable": observable_rows,
        "selection": learner_result["development_selection"],
        "fitted_state_sha256": "sha256:" + fitted_state_hash,
        "payload_sha256": learner_audit["payload_sha256"],
    }


def _summary_metric_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in metrics:
        if row.get("status") != "COMPLETE":
            continue
        groups.setdefault((row["population"], row["method"], row["lift"]), []).append(row)
    result: list[dict[str, Any]] = []
    for (population, method, lift), cells in sorted(groups.items()):
        n = sum(int(cell["n_entities"]) for cell in cells)
        result.append(
            {
                "population": population,
                "method": method,
                "lift": lift,
                "horizons_included": "14;28;56",
                "n_entities": n,
                "pooled_rmse_kg": math.sqrt(
                    sum(int(cell["n_entities"]) * float(cell["rmse_kg"]) ** 2 for cell in cells) / n
                ),
                "mean_mae_kg": sum(
                    int(cell["n_entities"]) * float(cell["mae_kg"]) for cell in cells
                )
                / n,
                "mean_signed_bias_kg": sum(
                    int(cell["n_entities"]) * float(cell["signed_bias_kg"]) for cell in cells
                )
                / n,
            }
        )
    return result


def _predictive_svg(metrics: list[dict[str, Any]]) -> bytes:
    colors = {
        "empirical_finite_support_resampler_v1": "#68707d",
        "summary_ridge_v1": "#277da1",
        "sequence_rff_ridge_v1": "#f3722c",
    }
    methods = tuple(colors)
    width, height = 1040, 760
    panel_w, panel_h = 500, 218
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#20242a}.small{font-size:11px}.title{font-size:15px;font-weight:bold}.axis{stroke:#444;stroke-width:1}.grid{stroke:#ddd;stroke-width:1}</style>",
        '<text x="520" y="24" text-anchor="middle" class="title">Held-out predictive RMSE (kg); lift and population kept separate</text>',
    ]
    for population_index, population in enumerate(("test_a", "test_b")):
        for lift_index, lift in enumerate(LIFTS):
            x0 = 20 + population_index * 510
            y0 = 42 + lift_index * 232
            left, top, right, bottom = 56, 44, 26, 30
            plot_x, plot_y = x0 + left, y0 + top
            plot_w, plot_h = panel_w - left - right, panel_h - top - bottom
            cell = [
                row for row in metrics if row["population"] == population and row["lift"] == lift
            ]
            completed = [row for row in cell if row.get("status") == "COMPLETE"]
            max_y = max(float(row["rmse_kg"]) for row in completed) * 1.15
            for tick in range(4):
                value = max_y * tick / 3
                y = plot_y + plot_h - plot_h * tick / 3
                parts.append(
                    f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_w}" y2="{y:.1f}" class="grid"/>'
                )
                parts.append(
                    f'<text x="{plot_x - 7}" y="{y + 4:.1f}" text-anchor="end" class="small">{value:.1f}</text>'
                )
            parts.extend(
                (
                    f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" class="axis"/>',
                    f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" class="axis"/>',
                    f'<text x="{plot_x}" y="{y0 + 15}" class="title">{escape(population)} - {escape(lift)}</text>',
                )
            )
            for horizon_index, horizon in enumerate(HORIZONS_DAYS):
                center = plot_x + plot_w * (horizon_index + 0.5) / 3
                parts.append(
                    f'<text x="{center:.1f}" y="{plot_y + plot_h + 17}" text-anchor="middle" class="small">{horizon} d</text>'
                )
                for method_index, method in enumerate(methods):
                    matching = [
                        row
                        for row in cell
                        if int(row["horizon_days"]) == horizon
                        and row["method"] == method
                        and row.get("status") == "COMPLETE"
                    ]
                    if not matching:
                        continue
                    value = float(matching[0]["rmse_kg"])
                    lower = float(matching[0]["rmse_ci95_lower_kg"])
                    upper = float(matching[0]["rmse_ci95_upper_kg"])
                    bar_w = 21
                    bar_h = plot_h * value / max_y
                    bar_x = center + (method_index - 1) * 24 - bar_w / 2
                    bar_y = plot_y + plot_h - bar_h
                    whisker_x = center + (method_index - 1) * 24
                    low_y = plot_y + plot_h - plot_h * lower / max_y
                    high_y = plot_y + plot_h - plot_h * upper / max_y
                    parts.append(
                        f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{colors[method]}"/>'
                    )
                    parts.append(
                        f'<line x1="{whisker_x:.1f}" y1="{high_y:.1f}" x2="{whisker_x:.1f}" y2="{low_y:.1f}" stroke="#20242a"/>'
                    )
    for index, method in enumerate(methods):
        x = 205 + index * 280
        parts.append(
            f'<rect x="{x}" y="{height - 14}" width="12" height="12" fill="{colors[method]}"/>'
        )
        parts.append(f'<text x="{x + 18}" y="{height - 4}" class="small">{escape(method)}</text>')
    parts.append("</svg>\n")
    return "".join(parts).encode("utf-8")


def _observable_svg(observable: list[dict[str, Any]]) -> bytes:
    rows = [row for row in observable if row["metric"] == "visible_field_wasserstein_1_normalized"]
    colors = {
        "assessment_kg": "#277da1",
        "prescribed_load_kg": "#43aa8b",
        "velocity_mps": "#f3722c",
    }
    width, height = 1000, 390
    plot_x, plot_y, plot_w, plot_h = 70, 54, 900, 250
    max_y = max(float(row["ci95_upper"]) for row in rows) * 1.12
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#20242a}.small{font-size:11px}.title{font-size:15px;font-weight:bold}.axis{stroke:#444;stroke-width:1}.grid{stroke:#ddd;stroke-width:1}</style>",
        '<text x="500" y="23" text-anchor="middle" class="title">Empirical donor sample vs independent test observables</text>',
    ]
    for tick in range(4):
        value = max_y * tick / 3
        y = plot_y + plot_h - plot_h * tick / 3
        parts.append(
            f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_w}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="{plot_x - 8}" y="{y + 4:.1f}" text-anchor="end" class="small">{value:.2f}</text>'
        )
    parts.append(
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" class="axis"/>'
    )
    parts.append(
        f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" class="axis"/>'
    )
    for index, row in enumerate(rows):
        center = plot_x + plot_w * (index + 0.5) / len(rows)
        bar_w = 50
        value = float(row["value"])
        lower, upper = float(row["ci95_lower"]), float(row["ci95_upper"])
        bar_h = plot_h * value / max_y
        bar_y = plot_y + plot_h - bar_h
        parts.append(
            f'<rect x="{center - bar_w / 2:.1f}" y="{bar_y:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{colors[row["channel"]]}"/>'
        )
        low_y, high_y = (
            plot_y + plot_h - plot_h * lower / max_y,
            plot_y + plot_h - plot_h * upper / max_y,
        )
        parts.append(
            f'<line x1="{center:.1f}" y1="{high_y:.1f}" x2="{center:.1f}" y2="{low_y:.1f}" stroke="#20242a"/>'
        )
        parts.append(
            f'<text x="{center:.1f}" y="{plot_y + plot_h + 18}" text-anchor="middle" class="small">{escape(row["lift"])}</text>'
        )
        channel = row["channel"].replace("_kg", "").replace("_mps", "")
        parts.append(
            f'<text x="{center:.1f}" y="{plot_y + plot_h + 31}" text-anchor="middle" class="small">{escape(channel)}</text>'
        )
    for index, (channel, color) in enumerate(colors.items()):
        x = 300 + index * 220
        parts.append(f'<rect x="{x}" y="{height - 16}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{x + 18}" y="{height - 6}" class="small">{escape(channel)}</text>')
    parts.append("</svg>\n")
    return "".join(parts).encode("utf-8")


def _report_bytes(
    protocol: dict[str, Any],
    metadata: dict[str, Any],
    summary_rows: list[dict[str, Any]],
    observable: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    geometry: list[dict[str, Any]],
    claims_csv: bytes,
) -> bytes:
    summary_table = [
        "| Population | Method | Lift | n | Pooled RMSE (kg) | Mean MAE (kg) | Mean bias (kg) |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        summary_table.append(
            f"| {row['population']} | {row['method']} | {row['lift']} | {row['n_entities']} | "
            f"{row['pooled_rmse_kg']:.4f} | {row['mean_mae_kg']:.4f} | "
            f"{row['mean_signed_bias_kg']:.4f} |"
        )
    w1_rows = [
        row for row in observable if row["metric"] == "visible_field_wasserstein_1_normalized"
    ]
    distribution_table = [
        "| Lift | Channel | W1 / training SD | 95% entity-bootstrap interval |",
        "|---|---|---:|---:|",
    ]
    for row in w1_rows:
        distribution_table.append(
            f"| {row['lift']} | {row['channel']} | {float(row['value']):.4f} | "
            f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] |"
        )
    distribution_other = [
        row for row in observable if row["metric"] != "visible_field_wasserstein_1_normalized"
    ]
    distribution_other_table = [
        "| Statistic | Value | 95% entity-bootstrap interval |",
        "|---|---:|---:|",
    ]
    distribution_other_table.extend(
        f"| {row['metric']} | {float(row['value']):.4f} | "
        f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] |"
        for row in distribution_other
    )
    test_a_coverage = [row for row in coverage_rows if row["evaluation_set"] == "test_a"]
    coverage_fraction = sum(
        float(row["evaluation_combination_fraction_seen_in_training"]) for row in test_a_coverage
    ) / max(1, len(test_a_coverage))
    geometry_table = [
        "| Set | Rows outside training sample extrema | Fraction | Median nearest training distance | 95th percentile |",
        "|---|---:|---:|---:|---:|",
    ]
    geometry_table.extend(
        f"| {row['evaluation_set']} | {row['n_outside_observed_training_extrema']} | "
        f"{float(row['fraction_outside_observed_training_extrema']):.3f} | "
        f"{float(row['nearest_training_distance_median']):.3f} | "
        f"{float(row['nearest_training_distance_p95']):.3f} |"
        for row in geometry
    )
    fitted_table = [
        "| Family | Fitted instance | Selected alpha | Selected gamma | Fit-state scalars |",
        "|---|---|---:|---:|---:|",
    ]
    fitted_table.extend(
        f"| {model['family']} | {model['fitted_instance_id']} | "
        f"{model['selected_alpha'] if model['selected_alpha'] is not None else 'not tuned'} | "
        f"{model['selected_gamma'] if model['selected_gamma'] is not None else 'not tuned'} | "
        f"{model['parameter_count']} |"
        for model in metadata["fitted_models"]
    )
    contrasts = metadata["contrasts"]
    rff_summary_contrasts = [
        row
        for row in contrasts
        if row["contrast"] == "sequence_rff_ridge_v1_minus_summary_ridge_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    summary_empirical_contrasts = [
        row
        for row in contrasts
        if row["contrast"] == "summary_ridge_v1_minus_empirical_finite_support_resampler_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    rff_resolved = sum(
        row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in rff_summary_contrasts
    )
    rff_higher = sum(float(row["rmse_difference_kg"]) > 0 for row in rff_summary_contrasts)
    summary_empirical_resolved = sum(
        row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in summary_empirical_contrasts
    )
    summary_empirical_inconclusive = sum(
        row["status"] == "INCONCLUSIVE" for row in summary_empirical_contrasts
    )
    lower_point_cells = sum(
        float(row["rmse_kg"])
        < min(
            float(base["rmse_kg"])
            for base in metadata["metrics"]
            if base["population"] == row["population"]
            and base["lift"] == row["lift"]
            and base["horizon_days"] == row["horizon_days"]
            and base["method"] == "empirical_finite_support_resampler_v1"
            and base.get("status") == "COMPLETE"
        )
        for row in metadata["metrics"]
        if row["method"] in {"summary_ridge_v1", "sequence_rff_ridge_v1"}
        and row.get("status") == "COMPLETE"
    )
    completed_matched = [row for row in metadata["matched"] if row.get("status") == "COMPLETE"]
    matched_summary = [
        "| Method | Lift | Matched-effect RMSE range across 9 plan/horizon cells (kg) |",
        "|---|---|---:|",
    ]
    for method in sorted({row["method"] for row in completed_matched}):
        for lift in LIFTS:
            values = [
                float(row["rmse_kg"])
                for row in completed_matched
                if row["method"] == method and row["lift"] == lift
            ]
            if values:
                matched_summary.append(
                    f"| {method} | {lift} | [{min(values):.3f}, {max(values):.3f}] |"
                )
    noise_resolved = sum(
        row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in metadata["noise"]
    )
    publication_repair = metadata.get("publication_repair")
    lines = [
        "# Public surrogate reconstruction: RES-290",
        "",
        f"Study identity: {metadata['protocol_id']}",
        f"Protocol SHA-256: {metadata['protocol_digest']}",
        f"Study realization: {metadata['realization_id']}",
        f"Realization digest: {metadata['realization_digest']}",
        "Evaluation: res290-public-surrogate-evaluation-v1",
        "",
        "This is a new public-native experiment, not a historical G3 reproduction. Historical G3 survives only as metadata and aliases; no original G3 method, data, fitted model, or score is recovered. See [historical lineage](../../../../studies/public_surrogate_reconstruction/historical-lineage.md).",
        "",
        "## Historical and scientific claim boundary",
        "",
        "G3 / ALI-543 and pl_study_g3_public_surrogate identify a retrospective study home. The original study question, protocol, participant rows, model, evaluation, and quantitative results are unsupported by surviving public evidence. RES-287 and RES-289 are independent public-native studies with their own identities and results. Their scores and historical G3 are not compared here.",
        "",
        "Predictive utility, observable-record distribution fidelity, matched conditional-response fidelity, finite-sample coverage, memorization, structural equivalence, and system identification are separate claims. Agreement on a finite predictive or distributional metric does not establish source-generator recovery, latent-state identification, causal equivalence, or transfer to real athletes.",
        "",
        "## Frozen design and firewall",
        "",
        f"The protocol was frozen at starting main {protocol['starting_main']} before any RES-290 realization was generated. It binds the public-native world, participant row contract, and M4/M5 references in [frozen evidence](../../../../studies/public_surrogate_reconstruction/frozen-evidence.json).",
        "",
        "Fitting has 384 rows, development 192, and each factual test population 384, balanced across 12 plan-by-horizon cells. Test A and test B use independent population and observation draws. A paired noise realization reuses test-A population and schedules with an independent observation seed. The matched set has 64 authority-only entities across four declared plans and three horizons.",
        "",
        "The learner receives only public fields and train/development target labels. Test rows have no target fields in the learner payload. Fitting runs in an isolated Python subprocess from a staged first-party learner module; imports outside NumPy and the Python standard library are rejected, and the audit hook blocks file, network, repository-import, and subprocess events. These subprocess and audit-hook controls provide procedural isolation for this controlled learner; they are not a security-grade sandbox for arbitrary hostile code. The authority keeps truth and matched-entity keys outside the payload, seals prediction bytes, then scores. The [payload audit](learner-input-audit.json) records the exact request digest, source, split counts, and firewall outcome.",
        "",
        "## Methods and fitted identities",
        "",
        "The empirical baseline resamples complete participant-visible fitting records with replacement within plan-by-horizon cells and predicts the cell mean. Summary Ridge uses predeclared visible summaries. Sequence RFF Ridge uses ordered observation and schedule fields with 128 generic random Fourier features and a fixed nine-configuration development search. Both conditional models return means only. Neither generates observable records. No source equation, latent coordinate, hidden state, exact population bound, historical artifact, or canonical M3/M4 fitted state enters learner fitting.",
        "",
        *fitted_table,
        "",
        "The exact fit states and input hashes are in [fitted models](fitted-models.json) and [fitted identities](fitted-model-identities.json). Every failed tuning configuration and any family-level fit failure is in [method-failures.json] and [development-selection.json]. The empirical generator is intentionally a row-copy baseline.",
        "",
        "## Predictive utility",
        "",
        "The table pools the three horizons with equal row counts, separately by population, method, and lift. Per-horizon RMSE, MAE, signed bias, and entity-bootstrap intervals for all three metrics remain in [predictive-metrics.csv](predictive-metrics.csv); paired method uncertainty is in [paired-model-comparisons.csv](paired-model-comparisons.csv). No target or lift is collapsed into a universal score.",
        "",
        *summary_table,
        "",
        f"Across 54 conditional-model/lift/horizon/population cells, {lower_point_cells} had lower point RMSE than the empirical plan-by-horizon mean. This point count does not establish an inferential improvement; the paired bootstrap contrasts below keep resolved and inconclusive cells separate.",
        "",
        "Figure: [predictive fidelity](predictive-fidelity.svg); the machine-readable table is the source alternative.",
        "",
        "## Observable-record distribution and memorization",
        "",
        "Only the empirical resampler generates complete observable records. Its output is compared with test-A inputs using field-wise 1-Wasserstein distance normalized by each fitting-sample standard deviation. Correlation discrepancy uses the 58 predeclared visible summary features. Plan and horizon frequencies are measured separately.",
        "",
        "These are conditional, evaluation-side percentile-bootstrap intervals: the empirical generated donor sample is fixed, and held-out evaluation entities are resampled within plan-by-horizon strata. The intervals do not include uncertainty in both empirical distributions and do not establish fully calibrated population-level two-sample discrepancy intervals. Point estimates use the observed evaluation sample and may fall outside their percentile intervals; the reported values are retained without silent correction. This publication repair leaves all numerical measurements, bootstrap draws, interval bounds, and seeds unchanged.",
        "",
        *distribution_table,
        "",
        *distribution_other_table,
        "",
        f"The empirical generator produced {metadata['memorization']['generated_record_count']} records from {metadata['memorization']['unique_donor_count']} unique fitting donors. Exact donor-copy fraction was {metadata['memorization']['exact_donor_copy_fraction']:.3f}; duplicate draw fraction was {metadata['memorization']['duplicate_draw_fraction']:.3f}. Exact fitting/test-A visible-record overlap was {metadata['memorization']['exact_fitting_test_visible_record_overlap']} of 384. These measurements quantify finite-sample reuse; they do not recover a generating world.",
        "",
        "Figure: [observable-distribution fidelity](observable-distribution.svg), with uncertainty by held-out entity.",
        "",
        "## Support coverage, sampling geometry, and noise",
        "",
        f"Within test A's plan-by-horizon cells, the mean fraction of observed history-schedule combinations also present in fitting was {coverage_fraction:.3f}. Cell counts for fitting, development, each test population, the paired noise draw, and matched support are in [support-coverage.csv](support-coverage.csv).",
        "",
        "The [sampling-geometry table](sampling-geometry.csv) reports held-out rows outside fitting-sample extrema and nearest fitting-row distances using the frozen 58 visible summary features. These diagnose this finite sample only; they do not estimate population bounds. The protocol scores no unsupported extrapolation state.",
        "",
        *geometry_table,
        "",
        f"Observation-noise sensitivity uses the test-A population and schedules with a new native observation seed. {noise_resolved} of {len(metadata['noise'])} method/lift/horizon paired RMSE contrasts were resolved by their 95% entity-bootstrap intervals. Full results are in [noise-sensitivity.csv](noise-sensitivity.csv). This is not a different noise-scale test.",
        "",
        "## Matched response and structural non-identification",
        "",
        f"The Evaluation Authority generated {len(metadata['matched'])} matched response metric cells across supported plan contrasts, lifts, horizons, and methods. Each contrast holds synthetic entity, history, historical schedule, and observation noise fixed while varying one declared future plan. The learner sees each public query but not the matching key or truth. Results and entity-level uncertainty are in [matched-response.csv](matched-response.csv).",
        "",
        *matched_summary,
        "",
        f"The predeclared paired prediction contrasts found sequence RFF Ridge higher than Summary Ridge in {rff_higher} of {len(rff_summary_contrasts)} cells, with {rff_resolved} resolved by the entity-bootstrap intervals. Summary Ridge had higher RMSE than the empirical plan-by-horizon baseline in {summary_empirical_resolved} of {len(summary_empirical_contrasts)} cells; {summary_empirical_inconclusive} cells were inconclusive.",
        "",
        "The experiment did not demonstrate a pair of observationally similar conditional surrogates with different matched response surfaces. The two conditional model families were distinguishable on held-out prediction error; no practical equivalence margin was frozen. The structural non-identification question therefore remains inconclusive. Their different internals and finite public-statistic agreement do not identify or reproduce the source mechanism.",
        "",
        "## Negative and inconclusive findings",
        "",
        "See [negative-results.csv](negative-results.csv) for the claim register and [method-failures.json](method-failures.json) for failed methods/configurations. Historical G3 outcomes remain unsupported. Finite empirical resampling copies its donor support by construction. Predictive, marginal, or conditional agreement does not establish system identification. Off-support extrapolation and real-athlete or causal transfer were not evaluated. Intervals spanning zero remain inconclusive.",
        "",
        "## Reproduction and provenance",
        "",
        "Replay from the repository root with:",
        "",
        "    uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction",
        "",
        "Verify source hashes, output identities, learner isolation, and deterministic regeneration with:",
        "",
        "    uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction --check",
        "",
        "Verify the generated report against frozen artifacts without rebuilding the experiment with:",
        "",
        "    uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction --check-report",
        "",
        "The [study manifest](manifest.json), [artifact manifest](artifact-manifest.json), and [SHA-256 index](SHA256SUMS.txt) bind the report, tables, figures, realizations, fitted states, predictions, and truth to the protocol, realization, fitted models, evaluation, source, and redistribution rights. No private historical artifact was used.",
    ]
    if publication_repair is not None:
        lines.extend(
            [
                "",
                "Post-merge documentation repair: `source_sha256` in the study manifest preserves the source hashes recorded for RES-290 execution. `publication_repair.generator_source_sha256` records the updated report-generator source and is not the source hash for the original experiment. This repair updates report links and interpretation only; no frozen numerical evidence was regenerated or rescored.",
            ]
        )
    lines.extend(
        [
            "",
            "RES-287 lineage and results: [study report](../../observation_inversion/report.md), [RES-289 handoff](../../observation_inversion/RES-289-handoff.md). RES-289 lineage and results: [study report](../../target_sufficient_structural_reconstruction/report.md), [RES-290 handoff](../../target_sufficient_structural_reconstruction/RES-290-handoff.md). Historical scores are not compared.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _handoff_bytes(metadata: dict[str, Any]) -> bytes:
    summary: dict[str, list[float]] = {}
    for row in metadata["metrics"]:
        if row["population"] == "test_a" and row.get("status") == "COMPLETE":
            summary.setdefault(row["method"], []).append(float(row["rmse_kg"]))
    method_lines = [
        f"- {method} test-A per-lift/horizon RMSE values in kg: "
        + ", ".join(f"{value:.3f}" for value in values)
        for method, values in sorted(summary.items())
    ]
    contrasts = metadata["contrasts"]
    rff_summary = [
        row
        for row in contrasts
        if row["contrast"] == "sequence_rff_ridge_v1_minus_summary_ridge_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    summary_empirical = [
        row
        for row in contrasts
        if row["contrast"] == "summary_ridge_v1_minus_empirical_finite_support_resampler_v1"
        and row["status"] != "MODEL_FIT_FAILED"
    ]
    rff_higher = sum(float(row["rmse_difference_kg"]) > 0 for row in rff_summary)
    rff_resolved = sum(row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in rff_summary)
    summary_resolved = sum(
        row["status"] == "RESOLVED_IN_THIS_REALIZATION" for row in summary_empirical
    )
    summary_inconclusive = sum(row["status"] == "INCONCLUSIVE" for row in summary_empirical)
    lines = [
        "# RES-292 scientific handoff",
        "",
        "This is a handoff only. RES-292 was not executed.",
        "",
        f"RES-290 study: {metadata['protocol_id']}",
        f"Protocol digest: {metadata['protocol_digest']}",
        f"Realization: {metadata['realization_id']}",
        f"Realization digest: {metadata['realization_digest']}",
        "Evaluation: res290-public-surrogate-evaluation-v1",
        "",
        "## Carried-forward evidence",
        "",
        "- Historical G3 survives as metadata only: name, aliases, retrospective purpose, and parent-benchmark attachment. Original G3 protocol, rows, model, and quantitative results remain unsupported.",
        "- RES-287 and RES-289 are separate public-native studies. Their outputs were read as lineage only and were not fit data, scoring truth, or historical score comparators.",
        "- RES-290 enforces learner/authority separation with a strict stdin payload, no held-out targets, an isolated process, runtime guards, and entity-disjoint training/development/test populations.",
        "- The empirical resampler generates donor copies. Summary Ridge and sequence RFF Ridge estimate conditional means and do not generate observable records.",
        "- Matched plan response results apply only to authority-generated synthetic entities under declared plan support. No real-world causal or structural-equivalence claim follows.",
        f"- Sequence RFF had higher predictive RMSE than Summary Ridge in {rff_higher}/{len(rff_summary)} paired cells ({rff_resolved} resolved); Summary Ridge was worse than the empirical mean in {summary_resolved} cells and inconclusive in {summary_inconclusive}.",
        "- The study did not demonstrate an observationally similar conditional-model pair with different response surfaces; that structural non-identification question remains inconclusive.",
        "",
        "## Result pointers",
        "",
        *method_lines,
        "- Predictive, matched-response, noise, support, and observable-distribution results are bound in the realization manifest and study report under results/studies/public_surrogate_reconstruction/public-native/.",
        "- The G3 reconstruction did not identify the source generator. Observational similarity and predictive utility remain separate from structural equivalence and system identification.",
        "",
        "## Suggested next boundary",
        "",
        "If RES-292 studies whether surrogate families that agree on public observables can differ in internal response, predeclare a separate protocol, use new authority-matched held-out populations, keep source truth outside learner fitting, and treat observational similarity as an operational finite-sample criterion rather than proof of mechanism equivalence.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _mean_interval(values: np.ndarray, clusters: list[str], seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for index in range(BOOTSTRAP_REPLICATES):
        selected = _bootstrap_indices(clusters, rng)
        samples[index] = float(np.mean(values[selected]))
    lower, upper = np.quantile(samples, (0.025, 0.975))
    return float(lower), float(upper)


def _surrogate_disagreement_rows(
    predictions: list[dict[str, Any]],
    visible: dict[str, list[dict[str, Any]]],
    authority_keys: dict[str, Any],
    seed: int,
) -> bytes:
    by_prediction = _index_predictions(predictions)
    available_methods = {row["method"] for row in predictions}
    rows: list[dict[str, Any]] = []
    counter = 0
    for evaluation_set in ("test_a", "test_b", "test_a_noise_replicate"):
        for lift_index, lift in enumerate(LIFTS):
            target = TARGETS[lift_index]
            for horizon in HORIZONS_DAYS:
                items = [
                    item
                    for item in visible[evaluation_set]
                    if item["inputs"]["horizon_days"] == horizon
                ]
                if (
                    not {
                        "summary_ridge_v1",
                        "sequence_rff_ridge_v1",
                    }
                    <= available_methods
                ):
                    rows.append(
                        {
                            "evaluation_set": evaluation_set,
                            "comparison": "sequence_rff_minus_summary",
                            "lift": lift,
                            "horizon_days": horizon,
                            "plan_contrast": "not_applicable",
                            "n_entities": len(items),
                            "status": "MODEL_FIT_FAILED",
                        }
                    )
                    continue
                differences = np.asarray(
                    [
                        by_prediction[(evaluation_set, "sequence_rff_ridge_v1", item["row_id"])][
                            target
                        ]
                        - by_prediction[(evaluation_set, "summary_ridge_v1", item["row_id"])][
                            target
                        ]
                        for item in items
                    ],
                    dtype=np.float64,
                )
                clusters = [authority_keys[evaluation_set][item["row_id"]] for item in items]
                lower, upper = _mean_interval(differences, clusters, seed + counter)
                counter += 1
                rows.append(
                    {
                        "evaluation_set": evaluation_set,
                        "comparison": "sequence_rff_minus_summary",
                        "lift": lift,
                        "horizon_days": horizon,
                        "plan_contrast": "not_applicable",
                        "n_entities": len(items),
                        "mean_signed_prediction_difference_kg": float(differences.mean()),
                        "mean_abs_prediction_difference_kg": float(np.abs(differences).mean()),
                        "ci95_lower_signed_difference_kg": lower,
                        "ci95_upper_signed_difference_kg": upper,
                        "status": "COMPLETE",
                    }
                )

    matched_keys = authority_keys["matched"]
    truth_ids = sorted(matched_keys)
    groups: dict[str, dict[tuple[str, int], str]] = {}
    for row_id in truth_ids:
        key = matched_keys[row_id]
        groups.setdefault(key["cluster_key"], {})[(key["plan_id"], int(key["horizon_days"]))] = (
            row_id
        )
    for lift_index, lift in enumerate(LIFTS):
        target = TARGETS[lift_index]
        for horizon in HORIZONS_DAYS:
            for plan in ("cessation", "step_down", "step_up"):
                if (
                    not {
                        "summary_ridge_v1",
                        "sequence_rff_ridge_v1",
                    }
                    <= available_methods
                ):
                    rows.append(
                        {
                            "evaluation_set": "matched",
                            "comparison": "sequence_rff_minus_summary_response",
                            "lift": lift,
                            "horizon_days": horizon,
                            "plan_contrast": f"{plan}_minus_continue",
                            "n_entities": len(groups),
                            "status": "MODEL_FIT_FAILED",
                        }
                    )
                    continue
                response_differences: list[float] = []
                response_clusters: list[str] = []
                for cluster, cases in groups.items():
                    base_id = cases[("continue", horizon)]
                    plan_id = cases[(plan, horizon)]
                    effect_rff = (
                        by_prediction[("matched", "sequence_rff_ridge_v1", plan_id)][target]
                        - by_prediction[("matched", "sequence_rff_ridge_v1", base_id)][target]
                    )
                    effect_summary = (
                        by_prediction[("matched", "summary_ridge_v1", plan_id)][target]
                        - by_prediction[("matched", "summary_ridge_v1", base_id)][target]
                    )
                    response_differences.append(effect_rff - effect_summary)
                    response_clusters.append(cluster)
                response_values = np.asarray(response_differences, dtype=np.float64)
                lower, upper = _mean_interval(response_values, response_clusters, seed + counter)
                counter += 1
                rows.append(
                    {
                        "evaluation_set": "matched",
                        "comparison": "sequence_rff_minus_summary_response",
                        "lift": lift,
                        "horizon_days": horizon,
                        "plan_contrast": f"{plan}_minus_continue",
                        "n_entities": len(response_values),
                        "mean_signed_prediction_difference_kg": float(response_values.mean()),
                        "mean_abs_prediction_difference_kg": float(np.abs(response_values).mean()),
                        "ci95_lower_signed_difference_kg": lower,
                        "ci95_upper_signed_difference_kg": upper,
                        "status": "COMPLETE",
                    }
                )
    return _csv_bytes(
        [
            "evaluation_set",
            "comparison",
            "lift",
            "horizon_days",
            "plan_contrast",
            "n_entities",
            "mean_signed_prediction_difference_kg",
            "mean_abs_prediction_difference_kg",
            "ci95_lower_signed_difference_kg",
            "ci95_upper_signed_difference_kg",
            "status",
        ],
        rows,
    )


def _claim_bindings(
    protocol: dict[str, Any],
    metadata: dict[str, Any],
    files: dict[str, bytes],
    negative_results: bytes,
) -> bytes:
    source_hashes = metadata["source_hashes"]
    output_hashes = _sha_map(files)
    fitted = {model["family"]: model["fitted_instance_id"] for model in metadata["fitted_models"]}
    methods = sorted(fitted.values())
    predictions = [row for row in csv.DictReader(io.StringIO(negative_results.decode("utf-8")))]
    bindings: list[dict[str, Any]] = []
    for row in predictions:
        claim = row["claim"]
        if claim.startswith("Original historical G3"):
            evidence = [
                "studies/public_surrogate_reconstruction/historical-lineage.md",
                FROZEN_RELATIVE,
            ]
            models: list[str] = []
        elif claim.startswith("At least one conditional learner"):
            evidence = ["predictive-metrics.csv", "paired-model-comparisons.csv"]
            models = methods
        elif claim.startswith("Sequence RFF and Summary Ridge"):
            evidence = [
                "predictive-metrics.csv",
                "paired-model-comparisons.csv",
                "surrogate-disagreement.csv",
            ]
            models = [
                fitted["summary_ridge_v1"],
                fitted["sequence_rff_ridge_v1"],
            ]
        elif claim.startswith("Summary Ridge versus empirical"):
            evidence = ["predictive-metrics.csv", "paired-model-comparisons.csv"]
            models = [
                fitted["summary_ridge_v1"],
                fitted["empirical_finite_support_resampler_v1"],
            ]
        elif claim.startswith("An observationally similar fitted pair"):
            evidence = [
                "paired-model-comparisons.csv",
                "surrogate-disagreement.csv",
                "matched-response.csv",
            ]
            models = [
                fitted["summary_ridge_v1"],
                fitted["sequence_rff_ridge_v1"],
            ]
        elif claim.startswith("A with-replacement empirical generator"):
            evidence = [
                "empirical-samples.jsonl",
                "support-coverage.csv",
                "observable-distribution.csv",
            ]
            models = [fitted["empirical_finite_support_resampler_v1"]]
        elif claim.startswith("Observation-noise"):
            evidence = ["noise-sensitivity.csv", "predictions.jsonl"]
            models = methods
        elif claim.startswith("Matched supported future-plan"):
            evidence = [
                "matched-response.csv",
                "realizations/matched-authority-truth.jsonl",
                "predictions.jsonl",
            ]
            models = methods
        elif claim.startswith("Any predictive"):
            evidence = [
                "predictive-metrics.csv",
                "matched-response.csv",
                "surrogate-disagreement.csv",
            ]
            models = methods
        elif claim.startswith("Learner/evaluation"):
            evidence = ["learner-input-audit.json", "predictions.jsonl"]
            models = methods
        elif claim.startswith("A frozen surrogate family"):
            evidence = ["method-failures.json", "development-selection.json"]
            models = methods
        elif claim.startswith("Extrapolation"):
            evidence = ["support-coverage.csv", "sampling-geometry.csv"]
            models = methods
        else:
            evidence = [
                "studies/public_surrogate_reconstruction/formal-specification.md",
                FROZEN_RELATIVE,
            ]
            models = methods
        evidence_rows: list[dict[str, str]] = []
        for path in evidence:
            if path in output_hashes:
                digest = output_hashes[path]
            elif path in source_hashes:
                digest = source_hashes[path]
            else:
                continue
            evidence_rows.append({"path": path, "sha256": digest})
        binding: dict[str, Any] = {
            "claim": claim,
            "status": row["status"],
            "study_id": protocol["identities"]["study_id"],
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": metadata["realization_id"],
            "realization_digest": metadata["realization_digest"],
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "fitted_instance_ids": models,
            "evidence_artifacts": evidence_rows,
            "claim_limit": row["limit"],
        }
        binding["claim_digest"] = sha256_record(binding)
        bindings.append(binding)
    return (
        canonical_json_bytes(
            {
                "format": "PSR_RES290_CLAIM_BINDINGS_V1",
                "claims": bindings,
            }
        )
        + b"\n"
    )


def _artifact_manifest_bytes(
    files: dict[str, bytes], protocol: dict[str, Any], metadata: dict[str, Any]
) -> bytes:
    artifacts: list[dict[str, Any]] = []
    for path, content in sorted(files.items()):
        suffix = Path(path).suffix
        license_expression = "CC-BY-4.0" if suffix == ".md" else "MIT"
        owner = "Powerlifting State Research contributors"
        digest = _file_sha256(content)
        slug = path.lower().replace("/", "-").replace(".", "-")
        artifact = ArtifactManifest(
            artifact_id=f"psr:artifact:res290-{slug}@1.0.0~{digest[:12]}",
            artifact_kind={
                ".jsonl": "application/x-ndjson",
                ".csv": "text/csv",
                ".svg": "image/svg+xml",
                ".md": "text/markdown",
                ".json": "application/json",
            }.get(suffix, "application/octet-stream"),
            license_expression=license_expression,
            copyright_holder=owner,
            origin_class="GENERATED_PUBLIC_ARTIFACT",
            source_reference=protocol["identities"]["study_id"],
            sha256=digest,
            redistribution_status=(
                "New public-native synthetic or derived RES-290 artifact; redistribute under the "
                f"listed license with attribution. Role: {'evaluation-authority-only' if 'truth' in path else 'public-study-output'}."
            ),
            access_conditions=None,
            generated_at=None,
            tool_identity=protocol["identities"]["study_id"],
        )
        artifacts.append({"path": path, **asdict(artifact)})
    return (
        canonical_json_bytes(
            {
                "format": "PSR_RES290_ARTIFACT_MANIFEST_V1",
                "study_id": protocol["identities"]["study_id"],
                "protocol_digest": protocol["identities"]["protocol_digest"],
                "realization_id": metadata["realization_id"],
                "artifacts": artifacts,
                "manifest_exclusions": [
                    "artifact-manifest.json",
                    "SHA256SUMS.txt",
                    "manifest.json",
                ],
            }
        )
        + b"\n"
    )


def _build_output_files(root: Path) -> dict[str, bytes]:
    protocol = verify_design(root)
    experiment = _build_inputs(root, protocol)
    learner_result, payload, stdout = _run_learner(
        root,
        experiment["fitting"],
        experiment["development"],
        experiment["datasets"],
        int(protocol["seeds"]["empirical_resampling"]),
    )
    files, metadata = _directory_artifacts(
        root, protocol, experiment, learner_result, payload, stdout
    )
    previous_manifest_path = _output_directory(root) / "manifest.json"
    previous_manifest = (
        json.loads(previous_manifest_path.read_text(encoding="utf-8"))
        if previous_manifest_path.is_file()
        else {}
    )
    execution_source_hashes = previous_manifest.get("execution_provenance", {}).get(
        "source_sha256", previous_manifest.get("source_sha256", metadata["source_hashes"])
    )
    execution_generator_hash = execution_source_hashes[EVALUATOR_RELATIVE]
    current_generator_hash = metadata["source_hashes"][EVALUATOR_RELATIVE]
    publication_repair = previous_manifest.get("publication_repair")
    if execution_generator_hash != current_generator_hash:
        publication_repair = {
            "kind": "POST_MERGE_DOCUMENTATION_REPAIR",
            "generator_source_sha256": current_generator_hash,
            "execution_source_sha256": execution_generator_hash,
            "scope": "report links, bootstrap interval interpretation, and learner isolation threat model",
        }
    metadata["execution_source_hashes"] = execution_source_hashes
    metadata["publication_repair"] = publication_repair
    negative_results = _claims_rows(
        files["predictive-metrics.csv"],
        files["paired-model-comparisons.csv"],
        metadata["noise"],
        files["matched-response.csv"],
        int(metadata["exact_overlap"]),
        metadata["learner_audit"],
        metadata["method_failures"],
    )
    summary_rows = _summary_metric_rows(metadata["metrics"])
    files["summary-metrics.csv"] = _csv_bytes(
        [
            "population",
            "method",
            "lift",
            "horizons_included",
            "n_entities",
            "pooled_rmse_kg",
            "mean_mae_kg",
            "mean_signed_bias_kg",
        ],
        summary_rows,
    )
    files["negative-results.csv"] = negative_results
    files["claims.json"] = _claim_bindings(protocol, metadata, files, negative_results)
    files["predictive-fidelity.svg"] = _predictive_svg(metadata["metrics"])
    files["observable-distribution.svg"] = _observable_svg(metadata["observable"])
    geometry_csv_rows = list(
        csv.DictReader(io.StringIO(files["sampling-geometry.csv"].decode("utf-8")))
    )
    files["report.md"] = _report_bytes(
        protocol,
        metadata,
        summary_rows,
        metadata["observable"],
        metadata["coverage_rows"],
        geometry_csv_rows,
        negative_results,
    )
    files["RES-292-handoff.md"] = _handoff_bytes(metadata)
    files["artifact-manifest.json"] = _artifact_manifest_bytes(files, protocol, metadata)
    index_rows = _sha_map(files)
    files["SHA256SUMS.txt"] = "".join(
        f"{digest.removeprefix('sha256:')}  {path}\n" for path, digest in sorted(index_rows.items())
    ).encode("utf-8")
    manifest = {
        "format": "PSR_RES290_PUBLIC_SURROGATE_STUDY_MANIFEST_V1",
        "study": {
            "study_id": protocol["identities"]["study_id"],
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "historical_study_slug": protocol["identities"]["historical_study_slug"],
            "historical_aliases": protocol["identities"]["historical_aliases"],
            "claim_classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
        },
        "benchmark": {
            "benchmark_id": protocol["identities"]["benchmark_id"],
            "dataset_spec_id": protocol["identities"]["dataset_spec_id"],
            "world_id": protocol["identities"]["world_id"],
            "canonical_evaluation_reference": protocol["identities"][
                "canonical_evaluation_reference"
            ],
            "study_evaluation_id": protocol["identities"]["study_evaluation_id"],
            "historical_scores_compared": False,
        },
        "realization": {
            "realization_id": metadata["realization_id"],
            "realization_digest": metadata["realization_digest"],
            "manifest_digest": metadata["manifest_digest"],
            "manifest_path": "dataset-realization.json",
            "starting_main": protocol["starting_main"],
            "role_separation": {
                "fitting_and_development_labels_visible": True,
                "evaluation_truth_in_learner_payload": False,
                "authority_truth_serialized_after_prediction_seal": True,
                "learner_input_sha256": metadata["payload_sha256"],
                "sealed_prediction_sha256": metadata["learner_audit"]["sealed_prediction_sha256"],
            },
        },
        "fitted_surrogates": metadata["fitted_models"],
        "learner_authority_audit": metadata["learner_audit"],
        "source_sha256": metadata["execution_source_hashes"],
        "execution_provenance": {
            "source_sha256": metadata["execution_source_hashes"],
            "realization_id": metadata["realization_id"],
            "realization_digest": metadata["realization_digest"],
            "learner_input_sha256": metadata["payload_sha256"],
            "sealed_prediction_sha256": metadata["learner_audit"]["sealed_prediction_sha256"],
        },
        "publication_repair": metadata["publication_repair"],
        "claim_bindings": {
            "path": "claims.json",
            "sha256": "sha256:" + _file_sha256(files["claims.json"]),
        },
        "rights": {
            "historical_private_artifacts_used": False,
            "dataset_license": "MIT",
            "prose_license": "CC-BY-4.0",
            "source_and_machine_readable_outputs_license": "MIT",
            "access_conditions": None,
        },
        "checksum_index": {
            "path": "SHA256SUMS.txt",
            "excludes": ["SHA256SUMS.txt", "manifest.json"],
        },
        "outputs": _sha_map(files),
    }
    files["manifest.json"] = canonical_json_bytes(manifest) + b"\n"
    return files


def _output_directory(root: Path) -> Path:
    return root / OUTPUT_RELATIVE


def _frozen_report_bytes(root: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    def rows(path: str) -> list[dict[str, Any]]:
        return list(csv.DictReader(io.StringIO(files[path].decode("utf-8"))))

    def jsonl(path: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in files[path].splitlines()]

    fitting = jsonl("realizations/fitting.jsonl")
    test_a = jsonl("realizations/test-a-visible.jsonl")
    empirical_sample = jsonl("empirical-samples.jsonl")
    fitting_ids = {row["row_id"] for row in fitting}
    donor_ids = [row["donor_row_id"] for row in empirical_sample]
    metadata: dict[str, Any] = {
        "protocol_id": manifest["study"]["study_id"],
        "protocol_digest": manifest["study"]["protocol_digest"],
        "realization_id": manifest["realization"]["realization_id"],
        "realization_digest": manifest["realization"]["realization_digest"],
        "fitted_models": manifest["fitted_surrogates"],
        "metrics": rows("predictive-metrics.csv"),
        "contrasts": rows("paired-model-comparisons.csv"),
        "matched": rows("matched-response.csv"),
        "noise": rows("noise-sensitivity.csv"),
        "publication_repair": manifest.get("publication_repair"),
        "memorization": {
            "generated_record_count": len(empirical_sample),
            "unique_donor_count": len(set(donor_ids)),
            "exact_donor_copy_fraction": sum(donor in fitting_ids for donor in donor_ids)
            / len(empirical_sample),
            "duplicate_draw_fraction": 1.0 - len(set(donor_ids)) / len(empirical_sample),
            "exact_fitting_test_visible_record_overlap": len(
                {_visible_hash(row) for row in fitting} & {_visible_hash(row) for row in test_a}
            ),
        },
    }
    summary_rows: list[dict[str, Any]] = []
    for row in rows("summary-metrics.csv"):
        summary_rows.append(
            {
                **row,
                "n_entities": int(row["n_entities"]),
                "pooled_rmse_kg": float(row["pooled_rmse_kg"]),
                "mean_mae_kg": float(row["mean_mae_kg"]),
                "mean_signed_bias_kg": float(row["mean_signed_bias_kg"]),
            }
        )
    return _report_bytes(
        verify_design(root),
        metadata,
        summary_rows,
        rows("observable-distribution.csv"),
        rows("support-coverage.csv"),
        rows("sampling-geometry.csv"),
        files["negative-results.csv"],
    )


def check_report(root: Path) -> None:
    destination = _output_directory(root)
    stored_manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    actual_files = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    actual_hashes = _sha_map(
        {path: data for path, data in actual_files.items() if path != "manifest.json"}
    )
    if actual_hashes != stored_manifest["outputs"]:
        raise ValueError("RES-290 artifact manifest or SHA-256 outputs do not verify")
    listed = {
        line.split("  ", maxsplit=1)[1]: "sha256:" + line.split("  ", maxsplit=1)[0]
        for line in actual_files["SHA256SUMS.txt"].decode("utf-8").splitlines()
    }
    indexed_hashes = {
        path: digest for path, digest in actual_hashes.items() if path != "SHA256SUMS.txt"
    }
    if listed != indexed_hashes:
        raise ValueError("RES-290 SHA256SUMS.txt is incomplete or incorrect")
    artifact_manifest = json.loads(actual_files["artifact-manifest.json"])
    for artifact in artifact_manifest["artifacts"]:
        if _file_sha256(actual_files[artifact["path"]]) != artifact["sha256"]:
            raise ValueError(f"RES-290 artifact manifest digest mismatch: {artifact['path']}")
    repair = stored_manifest.get("publication_repair")
    if stored_manifest.get("execution_provenance", {}).get("source_sha256") != stored_manifest.get(
        "source_sha256"
    ):
        raise ValueError("RES-290 execution source provenance does not verify")
    if repair is not None:
        current_hash = "sha256:" + _file_sha256((root / EVALUATOR_RELATIVE).read_bytes())
        if (
            repair["kind"] != "POST_MERGE_DOCUMENTATION_REPAIR"
            or repair["generator_source_sha256"] != current_hash
            or repair["execution_source_sha256"]
            != stored_manifest["source_sha256"][EVALUATOR_RELATIVE]
        ):
            raise ValueError("RES-290 publication repair provenance does not verify")
    if _frozen_report_bytes(root, actual_files, stored_manifest) != actual_files["report.md"]:
        raise ValueError("RES-290 deterministic report render mismatch")
    print("PASS: RES-290 frozen-evidence report render, provenance, and artifact hashes")


def _write_output_atomically(root: Path, files: dict[str, bytes]) -> Path:
    destination = _output_directory(root)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite immutable RES-290 output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".res290-public-surrogate-", dir=destination.parent))
    try:
        for relative, content in files.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        os.replace(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return destination


def check_outputs(root: Path) -> None:
    destination = _output_directory(root)
    manifest_path = destination / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("RES-290 output manifest is missing")
    stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_files = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    expected_hashes = stored_manifest["outputs"]
    actual_hashes = _sha_map(
        {path: data for path, data in actual_files.items() if path != "manifest.json"}
    )
    if actual_hashes != expected_hashes:
        raise ValueError("RES-290 artifact manifest or SHA-256 outputs do not verify")
    listed = {
        line.split("  ", maxsplit=1)[1]: "sha256:" + line.split("  ", maxsplit=1)[0]
        for line in actual_files["SHA256SUMS.txt"].decode("utf-8").splitlines()
    }
    indexed_hashes = {
        path: digest for path, digest in actual_hashes.items() if path not in {"SHA256SUMS.txt"}
    }
    if listed != indexed_hashes:
        raise ValueError("RES-290 SHA256SUMS.txt is incomplete or incorrect")
    rebuilt = _build_output_files(root)
    if rebuilt != actual_files:
        mismatches = sorted(
            path
            for path in set(rebuilt) | set(actual_files)
            if rebuilt.get(path) != actual_files.get(path)
        )
        raise ValueError(f"RES-290 deterministic replay mismatch: {mismatches[:8]}")
    print(
        "PASS: RES-290 protocol, frozen source hashes, learner firewall, "
        f"{len(actual_files)} artifact bytes, and deterministic replay"
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    if sys.argv[1:] == ["--check"]:
        check_outputs(root)
        return
    if sys.argv[1:] == ["--check-report"]:
        check_report(root)
        return
    if sys.argv[1:]:
        raise SystemExit(
            "usage: python -m powerlifting_state_research.studies.public_surrogate_reconstruction [--check|--check-report]"
        )
    protocol = verify_design(root)
    destination = _output_directory(root)
    if destination.exists():
        raise FileExistsError(
            f"immutable RES-290 output already exists at {destination}; use --check to verify it"
        )
    files = _build_output_files(root)
    written = _write_output_atomically(root, files)
    print(
        f"PASS: wrote {len(files)} RES-290 public-native artifacts to "
        f"{written.relative_to(root)} under {protocol['identities']['study_id']}"
    )


if __name__ == "__main__":
    main()
