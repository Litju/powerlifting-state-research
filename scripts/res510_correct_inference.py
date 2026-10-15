#!/usr/bin/env python3
"""Post-seal RES-510 inference correction; never imports or invokes a learner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

SPEC = "studies/corrections/RES-510-v1/analysis-specification.json"
SPEC_SHA = "cfa026bdfab6a97cbea2e7a92633339bfc158cd64418bf1000ce9c4f5ac2017c"
PUBLIC = "results/studies/synthetic_pretraining_transfer/public-native/"
OUTPUT = "results/corrections/RES-510-v1"
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def cell_key(row: dict[str, Any]) -> tuple[str, str, int, str, str]:
    return (
        row["population"],
        row["lift"],
        int(row["horizon_days"]),
        row["treatment_arm"],
        row["control_arm"],
    )


def decision(lower: float, upper: float) -> str:
    require(
        math.isfinite(lower) and math.isfinite(upper) and lower <= upper,
        "invalid confidence interval",
    )
    if upper < -1.0:
        return "PRACTICAL_BENEFIT"
    if lower > 1.0:
        return "PRACTICAL_HARM"
    if lower >= -1.0 and upper <= 1.0:
        return "PRACTICAL_EQUIVALENCE"
    return "INCONCLUSIVE"


def json_rows(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.splitlines()]


def unique_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {row["row_id"]: row for row in rows}
    require(len(result) == len(rows), "duplicate row identity")
    return result


def load(
    root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, bytes],
    list[dict[str, Any]],
    dict[tuple[str, str, int], tuple[FloatArray, list[str]]],
]:
    specification = (root / SPEC).read_bytes()
    require(hashlib.sha256(specification).hexdigest() == SPEC_SHA, "corrective spec changed")
    spec = json.loads(specification)
    inputs = {}
    for path, expected in spec["original_inputs"].items():
        file = root / path
        require(not any(p.is_symlink() for p in (file, *file.parents)), "symlink input")
        data = file.read_bytes()
        require(sha(data) == expected, f"changed original input: {path}")
        original = subprocess.check_output(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(root),
                "show",
                f"{spec['baseline_commit']}:{path}",
            ]
        )
        require(original == data, f"input differs from frozen Git object: {path}")
        inputs[path] = data
    protocol = json.loads(inputs["studies/synthetic_pretraining_transfer/protocol.json"])
    manifest = json.loads(inputs[PUBLIC + "manifest.json"])
    require(manifest["learner"]["input_firewall_passed"] is True, "original firewall not passed")
    require(
        manifest["learner"]["prediction_seal_sha256"] == sha(inputs[PUBLIC + "predictions.jsonl"]),
        "prediction seal mismatch",
    )
    fitting = unique_rows(json_rows(inputs[PUBLIC + "realizations/fitting.jsonl"]))
    development = unique_rows(json_rows(inputs[PUBLIC + "realizations/development-visible.jsonl"]))
    used_entities = set(fitting) | set(development)
    require(not set(fitting) & set(development), "fitting/development overlap")
    visible = {}
    truth = {}
    for population in spec["populations"]:
        suffix = population.removeprefix("test_population_")
        rows = unique_rows(
            json_rows(inputs[PUBLIC + f"realizations/test-population-{suffix}-visible.jsonl"])
        )
        authority = unique_rows(
            json_rows(inputs[PUBLIC + f"realizations/test-population-{suffix}-truth.jsonl"])
        )
        require(set(rows) == set(authority) and len(rows) == 384, "truth/visible coverage")
        entities = [row["inputs"]["entity_id"] for row in rows.values()]
        require(
            len(set(entities)) == len(rows) and set(entities) == set(rows),
            "entity identity mismatch",
        )
        require(not used_entities & set(entities), "split leakage")
        used_entities.update(entities)
        visible[population] = rows
        truth[population] = authority
    models = json.loads(inputs[PUBLIC + "fitted-instance-identities.json"])
    model_ids = {(row["arm"], row["fit_seed"]): row["fitted_instance_id"] for row in models}
    require(len(model_ids) == len(models) == 30, "model identity coverage")
    arms = [row["id"] for row in protocol["protocol"]["arms"]]
    predictions = {}
    for row in json_rows(inputs[PUBLIC + "predictions.jsonl"]):
        population = row["evaluation_set"]
        require(population in visible, "prediction population")
        key = (row["arm"], row["fit_seed"], population, row["row_id"])
        require(key not in predictions, "duplicate prediction")
        require(row["row_id"] in visible[population], "unknown prediction row")
        require(
            row["model_id"] == model_ids[(row["arm"], row["fit_seed"])], "prediction model mismatch"
        )
        for key_name in ("study_id", "protocol_digest"):
            require(row[key_name] == protocol["identities"][key_name], "protocol identity mismatch")
        require(
            row["evaluation_id"] == protocol["identities"]["study_evaluation_id"],
            "evaluation identity",
        )
        require(
            row["realization_id"] == manifest["dataset_realization"]["realization_id"],
            "realization identity",
        )
        require(
            set(row["targets"]) == set(protocol["protocol"]["participant_schema"]["targets"]),
            "target coverage",
        )
        require(all(math.isfinite(v) for v in row["targets"].values()), "nonfinite prediction")
        predictions[key] = row["targets"]
    require(len(predictions) == 23040, "missing prediction")
    arrays = {}
    for population, lift, horizon in itertools.product(
        spec["populations"], spec["lifts"], spec["horizons"]
    ):
        cell_rows = [
            v
            for _, v in sorted(visible[population].items())
            if v["inputs"]["horizon_days"] == horizon
        ]
        plans = [v["inputs"]["declared_future_plan"]["plan_id"] for v in cell_rows]
        require(
            len(cell_rows) == 128 and all(plans.count(p) == 32 for p in spec["plans"]),
            "stratum coverage",
        )
        target = lift + "_delta_capacity_kg"
        errors = np.asarray(
            [
                [
                    [
                        predictions[arm, seed, population, v["row_id"]][target]
                        - truth[population][v["row_id"]]["targets"][target]
                        for v in cell_rows
                    ]
                    for seed in spec["fit_seeds"]
                ]
                for arm in arms
            ],
            dtype=np.float64,
        )
        require(bool(np.isfinite(errors).all()), "nonfinite truth/error")
        arrays[population, lift, horizon] = (errors, plans)
    published = list(
        csv.DictReader(io.StringIO(inputs[PUBLIC + "paired-transfer-effects.csv"].decode()))
    )
    pooled = [r for r in published if r["aggregation"] == "pooled_hierarchical"]
    keys = {cell_key(r) for r in pooled}
    expected_keys = {
        (p, lift, h, t, c)
        for p, lift, h, (t, c) in itertools.product(
            spec["populations"], spec["lifts"], spec["horizons"], spec["contrasts"]
        )
    }
    require(len(pooled) == len(keys) == 108 and keys == expected_keys, "pooled cell coverage")
    for row in pooled:
        for arm_name in ("treatment", "control"):
            require(
                row[arm_name + "_model_id"]
                == ";".join(model_ids[row[arm_name + "_arm"], s] for s in spec["fit_seeds"]),
                "published model identity",
            )
        require(float(row["practical_margin_kg"]) == 1.0, "margin changed")
    spec["arms"] = arms
    return spec, inputs, sorted(pooled, key=cell_key), arrays


def draw(plans: list[str], runs: int, seed: int, order: list[str]) -> tuple[IntArray, IntArray]:
    rng = np.random.Generator(np.random.PCG64(seed))
    seeds = rng.integers(0, 5, size=(runs, 5), dtype=np.int64)
    plan_array = np.asarray(plans)
    entities = np.concatenate(
        [
            rng.choice(np.flatnonzero(plan_array == p), size=(runs, plans.count(p)), replace=True)
            for p in order
        ],
        axis=1,
    )
    return seeds, entities


def distribution(
    treatment: FloatArray, control: FloatArray, seeds: IntArray, entities: IntArray
) -> tuple[FloatArray, FloatArray]:
    require(treatment.shape == control.shape and treatment.shape[0] == 5, "paired array dimensions")
    n = treatment.shape[1]
    require(entities.shape[1] == n and seeds.shape == (len(entities), 5), "resampling dimensions")
    # Multiplicity weights are identical across every fit and both arms.
    offsets = np.arange(len(entities), dtype=np.int64)[:, None] * n
    counts = np.bincount((entities + offsets).ravel(), minlength=len(entities) * n).reshape(-1, n)
    deltas = np.sqrt(counts @ (treatment * treatment).T / n) - np.sqrt(
        counts @ (control * control).T / n
    )
    return np.take_along_axis(deltas, seeds, axis=1).mean(axis=1), deltas.mean(axis=1)


def interval(samples: FloatArray, epsilon: float) -> dict[str, Any]:
    lower, upper = np.quantile(samples, [0.025, 0.975], method="linear")
    outer_lower = np.quantile(samples, 0.025 - epsilon, method="lower")
    outer_upper = np.quantile(samples, 0.975 + epsilon, method="higher")
    return {
        "ci95_lower_kg": float(lower),
        "ci95_upper_kg": float(upper),
        "percentile_status": decision(float(lower), float(upper)),
        "mc_lower_kg": float(outer_lower),
        "mc_upper_kg": float(outer_upper),
        "mc_status": decision(float(outer_lower), float(outer_upper)),
    }


def final_status(rows: list[dict[str, Any]], prefix: str) -> str:
    statuses = {r[prefix + "percentile_status"] for r in rows} | {
        r[prefix + "mc_status"] for r in rows
    }
    return statuses.pop() if len(statuses) == 1 else "INCONCLUSIVE"


def legacy(
    treatment: FloatArray,
    control: FloatArray,
    plans: list[str],
    key: tuple[str, str, int, str, str],
    common: bool,
) -> tuple[float, float]:
    seed = int(
        hashlib.sha256("\0".join(map(str, (292170, "pooled", *key))).encode()).hexdigest()[:8], 16
    )
    rng = np.random.Generator(np.random.PCG64(seed))
    samples = []
    plan_array = np.asarray(plans)
    for _ in range(1000):
        selected = rng.choice(list(range(292201, 292206)), size=5, replace=True) - 292201
        indices = None
        values = []
        for s in selected:
            if indices is None or not common:
                indices = np.concatenate(
                    [
                        rng.choice(
                            np.flatnonzero(plan_array == p), size=plans.count(p), replace=True
                        )
                        for p in ("cessation", "step_down", "continue", "step_up")
                    ]
                )
            values.append(
                float(
                    np.sqrt(np.mean(treatment[s, indices] ** 2))
                    - np.sqrt(np.mean(control[s, indices] ** 2))
                )
            )
        samples.append(float(np.mean(values)))
    lower, upper = np.quantile(samples, [0.025, 0.975], method="linear")
    return float(lower), float(upper)


def csv_bytes(rows: list[dict[str, Any]], fields: list[str] | None = None) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=fields if fields is not None else list(rows[0]), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path) -> dict[str, bytes]:
    spec, inputs, original, arrays = load(root)
    runs = []
    comparison = []
    epsilon = math.sqrt(math.log(2 * 648 / 0.01) / (2 * spec["replicates"]))
    for row in original:
        key = cell_key(row)
        errors, plans = arrays[key[:3]]
        treatment, control = (errors[spec["arms"].index(a)] for a in key[3:])
        point = np.sqrt((treatment**2).mean(axis=1)) - np.sqrt((control**2).mean(axis=1))
        require(
            abs(float(point.mean()) - float(row["delta_rmse_kg"])) < 1e-10, "original point differs"
        )
        old_lower, old_upper = legacy(treatment, control, plans, key, False)
        require(
            abs(old_lower - float(row["ci95_lower_kg"])) < 1e-10
            and abs(old_upper - float(row["ci95_upper_kg"])) < 1e-10,
            "original interval replay differs",
        )
        require(decision(old_lower, old_upper) == row["status"], "original decision differs")
        diagnostic = legacy(treatment, control, plans, key, True)
        cell_runs = []
        for run_id in spec["runs"]:
            seed = int(
                hashlib.sha256(
                    "\0".join(map(str, ("RES510-v1", run_id, *key))).encode()
                ).hexdigest()[:16],
                16,
            )
            seeds, entities = draw(plans, spec["replicates"], seed, spec["plans"])
            crossed, conditional = distribution(treatment, control, seeds, entities)
            result = {
                "population": key[0],
                "lift": key[1],
                "horizon_days": key[2],
                "treatment_arm": key[3],
                "control_arm": key[4],
                "run_id": run_id,
                "rng_seed": seed,
                "draw_sha256": sha(
                    seeds.astype("<i8").tobytes() + entities.astype("<i8").tobytes()
                ),
            }
            for prefix, values in (("corrected_", crossed), ("conditional_", conditional)):
                result.update({prefix + k: v for k, v in interval(values, epsilon).items()})
            runs.append(result)
            cell_runs.append(result)
        result = dict(row)
        for prefix in ("corrected_", "conditional_"):
            for name in ("ci95_lower_kg", "ci95_upper_kg", "percentile_status"):
                result[prefix + name] = cell_runs[0][prefix + name]
            result[prefix + "status"] = final_status(cell_runs, prefix)
        result.update(
            {
                "n_entities": 128,
                "n_fit_seeds": 5,
                "n_entities_per_plan": 32,
                "bootstrap_replicates": spec["replicates"],
                "monte_carlo_runs": 3,
                "per_seed_delta_kg": json.dumps(point.tolist(), separators=(",", ":")),
                "audit_diagnostic_ci95_lower_kg": diagnostic[0],
                "audit_diagnostic_ci95_upper_kg": diagnostic[1],
                "audit_diagnostic_status": decision(*diagnostic),
                "status_changed": row["status"] != result["corrected_status"],
                "percentile_status_changed": row["status"] != result["corrected_percentile_status"],
                "random_seed_coverage_qualification": "INCONCLUSIVE",
            }
        )
        comparison.append(result)
        print(f"Scored {len(comparison)}/108: {key}", flush=True)
    outputs = {
        "comparison.csv": csv_bytes(comparison),
        "bootstrap-runs.csv": csv_bytes(runs),
        "changed-classifications.csv": csv_bytes(
            [r for r in comparison if r["status_changed"]], list(comparison[0])
        ),
    }
    sources = {
        path: sha((root / path).read_bytes())
        for path in (
            "studies/corrections/RES-510-v1/analysis-specification.json",
            "scripts/res510_correct_inference.py",
            "scripts/verify_res510_correction.py",
            "tests/test_res510_correction.py",
            "tests/test_res510_verifier.py",
            "studies/corrections/RES-510-v1/methods.md",
            "studies/corrections/RES-510-v1/method-freeze.json",
            "studies/corrections/RES-510-v1/input-verification.json",
            "studies/corrections/RES-510-v1/interpretation.md",
        )
    }
    manifest = {
        "format": "PSR_RES510_CORRECTION_MANIFEST_V1",
        "correction_id": spec["correction_id"],
        "baseline_commit": spec["baseline_commit"],
        "specification_sha256": "sha256:" + SPEC_SHA,
        "original_inputs": spec["original_inputs"],
        "source_hashes": sources,
        "outputs": {p: sha(b) for p, b in outputs.items()},
        "cells": 108,
        "runs": 324,
        "dependency_status": spec["dependency_status"],
        "random_seed_coverage": "INCONCLUSIVE",
        "external_scientific_review": "NOT_RUN",
        "release_gate": "BLOCKED",
        "original_inference": (
            "Superseded for inference only, conditional on independent review; "
            "original artifacts preserved"
        ),
        "no_model_training": True,
        "units": "kg",
        "practical_margin_kg": 1.0,
    }
    outputs["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    outputs["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(b).hexdigest()}  {p}\n" for p, b in sorted(outputs.items())
    ).encode()
    return outputs


def require_exact_output_set(directory: Path, expected: set[str]) -> None:
    """Require the correction directory to contain exactly the declared artifacts."""
    require(directory.is_dir(), "correction output directory missing")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*")}
    require(
        actual == expected,
        f"correction output set differs: missing={sorted(expected - actual)}; "
        f"extra={sorted(actual - expected)}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        outputs = build(root)
        destination = root / OUTPUT
        require(
            not any(p.is_symlink() for p in (destination, *destination.parents)), "symlink output"
        )
        if args.check:
            require_exact_output_set(destination, set(outputs))
            for path, data in outputs.items():
                require(
                    (destination / path).read_bytes() == data, f"correction replay differs: {path}"
                )
        else:
            destination.mkdir(parents=True, exist_ok=True)
            for path, data in outputs.items():
                require(not (destination / path).is_symlink(), "symlink output file")
                require(
                    not (destination / path).exists() or (destination / path).stat().st_nlink == 1,
                    "hardlink output file",
                )
                (destination / path).write_bytes(data)
        print("PASS: 108 original contrasts replayed and corrected; release remains BLOCKED")
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
