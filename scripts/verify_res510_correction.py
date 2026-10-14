"""Independently verify sealed RES-510 outputs by direct indexed-error reduction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
SPEC_SHA256 = "sha256:cfa026bdfab6a97cbea2e7a92633339bfc158cd64418bf1000ce9c4f5ac2017c"
SPEC_PATH = "studies/corrections/RES-510-v1/analysis-specification.json"
ORIGINAL = "results/studies/synthetic_pretraining_transfer/public-native"
RESULTS = "results/corrections/RES-510-v1"
Cell = tuple[str, str, int, str, str]
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            require(
                reader.fieldnames is not None
                and len(reader.fieldnames) == len(set(reader.fieldnames)),
                "malformed CSV header",
            )
            records = list(reader)
            require(
                all(None not in r and all(v is not None for v in r.values()) for r in records),
                "malformed CSV row",
            )
            return records
    return [json.loads(line) for line in path.read_text().splitlines()]


def cell(row: dict[str, Any]) -> Cell:
    return (
        row["population"],
        row["lift"],
        int(row["horizon_days"]),
        row["treatment_arm"],
        row["control_arm"],
    )


def classify(lower: float, upper: float) -> str:
    require(
        math.isfinite(lower) and math.isfinite(upper) and lower <= upper,
        "nonfinite or inverted interval",
    )
    if upper < -1.0:
        return "PRACTICAL_BENEFIT"
    if lower > 1.0:
        return "PRACTICAL_HARM"
    if lower >= -1.0 and upper <= 1.0:
        return "PRACTICAL_EQUIVALENCE"
    return "INCONCLUSIVE"


def close(actual: Any, expected: float, name: str) -> float:
    value = float(actual)
    require(math.isfinite(value) and math.isfinite(expected), f"nonfinite {name}")
    error = abs(value - expected)
    require(error <= 1e-10, f"numerical disagreement {name}: {value} != {expected}")
    return error


def unique(records: list[dict[str, Any]], keys: list[Any], name: str) -> dict[Any, Any]:
    require(len(records) == len(set(keys)), f"duplicate {name}")
    return dict(zip(keys, records, strict=True))


def bootstrap(
    treatment: FloatArray,
    control: FloatArray,
    strata: list[IntArray],
    seed: int,
    replicates: int,
) -> tuple[FloatArray, FloatArray, str]:
    """Use direct row indexing, independently of count-weighted generator arithmetic."""
    rng = np.random.Generator(np.random.PCG64(seed))
    selected = rng.integers(0, 5, size=(replicates, 5))
    indices = np.concatenate(
        [rng.choice(group, size=(replicates, len(group)), replace=True) for group in strata],
        axis=1,
    )
    draw_hash = hashlib.sha256()
    draw_hash.update(selected.astype("<i8").tobytes())
    draw_hash.update(indices.astype("<i8").tobytes())
    differences = np.empty((replicates, 5), dtype=np.float64)
    for start in range(0, replicates, 2000):
        stop = min(replicates, start + 2000)
        sampled = indices[start:stop]
        for fit in range(5):
            differences[start:stop, fit] = np.sqrt(
                np.mean(treatment[fit, sampled] ** 2, axis=1)
            ) - np.sqrt(np.mean(control[fit, sampled] ** 2, axis=1))
    crossed = np.take_along_axis(differences, selected, axis=1).mean(axis=1)
    conditional = differences.mean(axis=1)
    return crossed, conditional, draw_hash.hexdigest()


def original_interval(
    treatment: FloatArray,
    control: FloatArray,
    strata: list[IntArray],
    cell_key: Cell,
    shared: bool = False,
) -> tuple[float, float]:
    parts = (292170, "pooled", *cell_key)
    seed = int(hashlib.sha256("\0".join(map(str, parts)).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(1000):
        selected = rng.choice(list(range(292201, 292206)), size=5, replace=True)
        deltas = []
        common_indices = None
        for selected_seed in selected:
            indices = (
                common_indices
                if shared and common_indices is not None
                else np.concatenate(
                    [rng.choice(group, size=(1, len(group)), replace=True) for group in strata],
                    axis=1,
                )[0]
            )
            common_indices = indices
            fit = int(selected_seed) - 292201
            deltas.append(
                float(
                    np.sqrt(np.mean(treatment[fit, indices] ** 2))
                    - np.sqrt(np.mean(control[fit, indices] ** 2))
                )
            )
        draws.append(float(np.mean(deltas)))
    lower, upper = np.quantile(draws, [0.025, 0.975], method="linear")
    return float(lower), float(upper)


def interval(draw: FloatArray, epsilon: float) -> tuple[float, float, float, float]:
    lower, upper = np.quantile(draw, [0.025, 0.975], method="linear")
    mc_lower = np.quantile(draw, 0.025 - epsilon, method="lower")
    mc_upper = np.quantile(draw, 0.975 + epsilon, method="higher")
    return float(lower), float(upper), float(mc_lower), float(mc_upper)


def stable_status(run_rows: list[dict[str, Any]], prefix: str) -> str:
    states = {r[f"{prefix}_percentile_status"] for r in run_rows}
    states.update(r[f"{prefix}_mc_status"] for r in run_rows)
    return states.pop() if len(states) == 1 else "INCONCLUSIVE"


def safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe manifest path")
    full = root / path
    require(
        full.is_file() and not any(p.is_symlink() for p in (full, *full.parents)),
        f"missing/unsafe file: {relative}",
    )
    require(full.resolve().is_relative_to(root.resolve()), "path leaves checkout")
    return full


def verify(root: Path) -> dict[str, Any]:
    spec_bytes = safe_file(root, SPEC_PATH).read_bytes()
    require(digest(spec_bytes) == SPEC_SHA256, "frozen specification changed")
    spec = json.loads(spec_bytes)
    manifest = read_json(root / RESULTS / "manifest.json")
    require(manifest["specification_sha256"] == digest(spec_bytes), "specification hash")
    require(
        manifest["baseline_commit"] == spec["baseline_commit"]
        and manifest["correction_id"] == spec["correction_id"]
        and manifest["cells"] == 108
        and manifest["runs"] == 324,
        "manifest scientific identity/scope",
    )
    require(
        manifest["units"] == "kg"
        and manifest["practical_margin_kg"] == 1.0
        and manifest["no_model_training"] is True,
        "manifest units/training claims",
    )
    require(
        manifest["random_seed_coverage"] == "INCONCLUSIVE"
        and manifest["external_scientific_review"] == "NOT_RUN"
        and manifest["release_gate"] == "BLOCKED",
        "unresolved qualification misrepresented",
    )
    require(manifest["original_inputs"] == spec["original_inputs"], "input inventory differs")
    require(spec["replicates"] == 50000 and len(spec["runs"]) == 3, "campaign scope")
    git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    git_env["GIT_NO_REPLACE_OBJECTS"] = "1"
    for relative, expected in spec["original_inputs"].items():
        require(
            relative.startswith(ORIGINAL + "/")
            or relative == "studies/synthetic_pretraining_transfer/protocol.json",
            "unauthorized input",
        )
        data = safe_file(root, relative).read_bytes()
        baseline = subprocess.check_output(
            ["git", "--no-replace-objects", "show", f"{spec['baseline_commit']}:{relative}"],
            cwd=root,
            env=git_env,
        )
        require(digest(data) == expected and data == baseline, f"original changed: {relative}")
    require(
        {"comparison.csv", "bootstrap-runs.csv", "changed-classifications.csv"}
        <= set(manifest["outputs"]),
        "manifest missing required outputs",
    )
    require(
        {SPEC_PATH, "scripts/res510_correct_inference.py", "scripts/verify_res510_correction.py"}
        <= set(manifest["source_hashes"]),
        "manifest missing implementation proof",
    )
    for section in ("source_hashes", "outputs"):
        for relative, expected in manifest[section].items():
            require(
                digest(
                    safe_file(
                        root, RESULTS + "/" + relative if section == "outputs" else relative
                    ).read_bytes()
                )
                == expected,
                f"manifest hash mismatch: {relative}",
            )
    checksum_lines = (root / RESULTS / "SHA256SUMS.txt").read_text().splitlines()
    checksum_entries = [line.split("  ", 1) for line in checksum_lines]
    require(all(len(entry) == 2 for entry in checksum_entries), "malformed checksum index")
    require(
        len({entry[1] for entry in checksum_entries}) == len(checksum_entries),
        "duplicate checksum path",
    )
    require(
        set(manifest["outputs"]) | {"manifest.json"} <= {entry[1] for entry in checksum_entries},
        "incomplete checksum index",
    )
    for expected_hash, relative in checksum_entries:
        require(
            hashlib.sha256(safe_file(root, RESULTS + "/" + relative).read_bytes()).hexdigest()
            == expected_hash,
            "checksum index mismatch",
        )
    base = root / ORIGINAL
    expected_cells = {
        (p, lift, h, treatment, control)
        for p, lift, h, (treatment, control) in itertools.product(
            spec["populations"], spec["lifts"], spec["horizons"], spec["contrasts"]
        )
    }
    comparisons = rows(root / RESULTS / "comparison.csv")
    comparison = unique(comparisons, [cell(r) for r in comparisons], "comparison cells")
    original_rows = [
        r
        for r in rows(base / "paired-transfer-effects.csv")
        if r["aggregation"] == "pooled_hierarchical"
    ]
    original = unique(original_rows, [cell(r) for r in original_rows], "original cells")
    require(
        set(comparison) == set(original) == expected_cells and len(expected_cells) == 108,
        "108-cell coverage",
    )
    run_records = rows(root / RESULTS / "bootstrap-runs.csv")
    runs = unique(run_records, [(cell(r), r["run_id"]) for r in run_records], "run cells")
    require(set(runs) == set(itertools.product(expected_cells, spec["runs"])), "324-run coverage")
    run_fields = {
        "population",
        "lift",
        "horizon_days",
        "treatment_arm",
        "control_arm",
        "run_id",
        "rng_seed",
        "draw_sha256",
    } | {
        f"{prefix}_{suffix}"
        for prefix in ("corrected", "conditional")
        for suffix in (
            "ci95_lower_kg",
            "ci95_upper_kg",
            "percentile_status",
            "mc_lower_kg",
            "mc_upper_kg",
            "mc_status",
        )
    }
    require(all(set(r) == run_fields for r in run_records), "unexpected run columns")
    extra_fields = {
        "n_entities",
        "n_fit_seeds",
        "n_entities_per_plan",
        "bootstrap_replicates",
        "monte_carlo_runs",
        "per_seed_delta_kg",
        "audit_diagnostic_ci95_lower_kg",
        "audit_diagnostic_ci95_upper_kg",
        "audit_diagnostic_status",
        "status_changed",
        "percentile_status_changed",
        "random_seed_coverage_qualification",
    } | {
        f"{prefix}_{suffix}"
        for prefix in ("corrected", "conditional")
        for suffix in ("ci95_lower_kg", "ci95_upper_kg", "percentile_status", "status")
    }
    require(
        all(set(r) == set(original_rows[0]) | extra_fields for r in comparisons),
        "unexpected comparison columns",
    )
    protocol = read_json(root / "studies/synthetic_pretraining_transfer/protocol.json")
    identities = protocol["identities"]
    original_manifest = read_json(base / "manifest.json")
    realization_id = original_manifest["dataset_realization"]["realization_id"]
    models = read_json(base / "fitted-instance-identities.json")
    model_index = unique(models, [(r["arm"], r["fit_seed"]) for r in models], "models")
    prediction_rows = rows(base / "predictions.jsonl")
    pred = unique(
        prediction_rows,
        [(r["arm"], r["fit_seed"], r["evaluation_set"], r["row_id"]) for r in prediction_rows],
        "predictions",
    )
    require(len(pred) == 23040 and len(model_index) == 30, "prediction/model counts")
    for r in prediction_rows:
        require(
            r["model_id"] == model_index[r["arm"], r["fit_seed"]]["fitted_instance_id"],
            "prediction model identity",
        )
        for identity_key in ("study_id", "protocol_digest", "study_evaluation_id"):
            field = "evaluation_id" if identity_key == "study_evaluation_id" else identity_key
            require(r[field] == identities[identity_key], f"prediction identity {field}")
        require(r["realization_id"] == realization_id, "prediction realization identity")
        require(
            set(r["targets"]) == {lift + "_delta_capacity_kg" for lift in spec["lifts"]},
            "prediction target coverage",
        )
        require(all(math.isfinite(float(v)) for v in r["targets"].values()), "nonfinite prediction")
    split = read_json(base / "realizations/split.json")
    require(
        split["entity_disjoint"] is True
        and split["authority_source_entity_keys_serialized"] is False,
        "split receipt",
    )
    roles = {r["role"]: r for r in split["roles"]}
    role_rows: dict[str, list[dict[str, Any]]] = {}
    entity_sets = []
    for role in ("fitting", "development", *spec["populations"]):
        filename = (
            "fitting.jsonl" if role == "fitting" else role.replace("_", "-") + "-visible.jsonl"
        )
        data_rows = rows(base / "realizations" / filename)
        entity_ids = [r["inputs"]["entity_id"] for r in data_rows]
        require(
            len(entity_ids) == len(set(entity_ids)) == roles[role]["entity_count"],
            f"entity uniqueness {role}",
        )
        require(set(entity_ids) == {r["row_id"] for r in data_rows}, "row/entity identity")
        require(roles[role]["row_count"] == len(data_rows), "split row count")
        require(
            digest("\n".join(sorted(entity_ids)).encode()) == roles[role]["entity_ids_sha256"],
            "split membership hash",
        )
        entity_sets.append(set(entity_ids))
        role_rows[role] = data_rows
    require(
        all(not a.intersection(b) for a, b in itertools.combinations(entity_sets, 2)),
        "entity split leakage",
    )
    audits = read_json(base / "learner-input-audit.json")
    require(len(audits) == 30, "firewall audit counts")
    for audit in audits:
        require(
            audit["passed"] is True
            and audit["query_targets_in_payload"] == 0
            and audit["authority_only_fields_in_payload"] == 0
            and audit["fitting_development_test_entities_disjoint"] is True
            and audit["sealed_prediction_sha256"]
            == spec["original_inputs"][ORIGINAL + "/predictions.jsonl"],
            "firewall/seal receipt",
        )
    truths = {}
    for population in spec["populations"]:
        truth_rows = rows(base / "realizations" / (population.replace("_", "-") + "-truth.jsonl"))
        truths[population] = unique(truth_rows, [r["row_id"] for r in truth_rows], "truth")
        require(
            set(truths[population]) == {r["row_id"] for r in role_rows[population]},
            "truth/visible coverage",
        )
    epsilon = math.sqrt(math.log(2 * 648 / 0.01) / (2 * 50000))
    max_error = 0.0
    for key in sorted(expected_cells):
        population, lift, horizon, treatment, control = key
        current = comparison[key]
        old = original[key]
        require(all(current[k] == v for k, v in old.items()), "original comparison altered")
        require(float(current["practical_margin_kg"]) == 1.0, "practical margin")
        visible = sorted(
            (r for r in role_rows[population] if r["inputs"]["horizon_days"] == horizon),
            key=lambda r: r["row_id"],
        )
        require(
            len(visible) == 128
            and int(current["n_entities"]) == 128
            and int(current["n_fit_seeds"]) == 5,
            "cell counts",
        )
        plans = [r["inputs"]["declared_future_plan"]["plan_id"] for r in visible]
        strata = [
            np.asarray([i for i, plan in enumerate(plans) if plan == expected], dtype=np.int64)
            for expected in spec["plans"]
        ]
        require(all(len(group) == 32 for group in strata), "plan strata")
        arrays = []
        for arm in (treatment, control):
            require(
                old["treatment_model_id" if arm == treatment else "control_model_id"]
                == ";".join(
                    model_index[arm, seed]["fitted_instance_id"] for seed in spec["fit_seeds"]
                ),
                "pooled model identities",
            )
            arrays.append(
                np.asarray(
                    [
                        [
                            float(
                                pred[arm, seed, population, r["row_id"]]["targets"][
                                    lift + "_delta_capacity_kg"
                                ]
                            )
                            - float(
                                truths[population][r["row_id"]]["targets"][
                                    lift + "_delta_capacity_kg"
                                ]
                            )
                            for r in visible
                        ]
                        for seed in spec["fit_seeds"]
                    ],
                    dtype=np.float64,
                )
            )
        t, c = arrays
        require(bool(np.isfinite(t).all() and np.isfinite(c).all()), "nonfinite truth/error")
        deltas = np.sqrt(np.mean(t**2, axis=1)) - np.sqrt(np.mean(c**2, axis=1))
        max_error = max(max_error, close(current["delta_rmse_kg"], float(deltas.mean()), "point"))
        original_lo, original_hi = original_interval(t, c, strata, key)
        max_error = max(
            max_error,
            close(old["ci95_lower_kg"], original_lo, "original lower"),
            close(old["ci95_upper_kg"], original_hi, "original upper"),
        )
        require(old["status"] == classify(original_lo, original_hi), "original decision")
        diagnostic_lo, diagnostic_hi = original_interval(t, c, strata, key, shared=True)
        max_error = max(
            max_error,
            close(
                current["audit_diagnostic_ci95_lower_kg"], diagnostic_lo, "audit diagnostic lower"
            ),
            close(
                current["audit_diagnostic_ci95_upper_kg"], diagnostic_hi, "audit diagnostic upper"
            ),
        )
        require(
            current["audit_diagnostic_status"] == classify(diagnostic_lo, diagnostic_hi),
            "audit diagnostic decision",
        )
        require(
            int(current["n_entities_per_plan"]) == 32
            and int(current["bootstrap_replicates"]) == 50000
            and int(current["monte_carlo_runs"]) == 3
            and current["random_seed_coverage_qualification"] == "INCONCLUSIVE",
            "campaign qualification metadata",
        )
        stored_deltas = json.loads(current["per_seed_delta_kg"])
        require(len(stored_deltas) == 5, "per-seed delta count")
        for stored, expected_delta in zip(stored_deltas, deltas, strict=True):
            max_error = max(max_error, close(stored, float(expected_delta), "seed point"))
        checked_runs = []
        for run_id in spec["runs"]:
            run = runs[key, run_id]
            seed_string = "\0".join(map(str, ("RES510-v1", run_id, *key)))
            seed = int(hashlib.sha256(seed_string.encode()).hexdigest()[:16], 16)
            require(int(run["rng_seed"]) == seed, "RNG identity")
            crossed, conditional, draw_hash = bootstrap(t, c, strata, seed, 50000)
            require(run["draw_sha256"].removeprefix("sha256:") == draw_hash, "draw hash")
            for prefix, draws in (("corrected", crossed), ("conditional", conditional)):
                lo, hi, mc_lo, mc_hi = interval(draws, epsilon)
                for suffix, value in (
                    ("ci95_lower_kg", lo),
                    ("ci95_upper_kg", hi),
                    ("mc_lower_kg", mc_lo),
                    ("mc_upper_kg", mc_hi),
                ):
                    max_error = max(max_error, close(run[f"{prefix}_{suffix}"], value, suffix))
                require(run[f"{prefix}_percentile_status"] == classify(lo, hi), "run decision")
                require(run[f"{prefix}_mc_status"] == classify(mc_lo, mc_hi), "MC decision")
                if run_id == spec["runs"][0]:
                    max_error = max(
                        max_error,
                        close(current[f"{prefix}_ci95_lower_kg"], lo, "primary lower"),
                        close(current[f"{prefix}_ci95_upper_kg"], hi, "primary upper"),
                    )
                    require(
                        current[f"{prefix}_percentile_status"] == classify(lo, hi),
                        "primary percentile decision",
                    )
            checked_runs.append(run)
        for prefix in ("corrected", "conditional"):
            require(
                current[f"{prefix}_status"] == stable_status(checked_runs, prefix),
                "final stability decision",
            )
        require(
            str(current["status_changed"]).lower()
            == str(current["status"] != current["corrected_status"]).lower(),
            "change flag",
        )
        require(
            str(current["percentile_status_changed"]).lower()
            == str(current["status"] != current["corrected_percentile_status"]).lower(),
            "percentile change flag",
        )
    changed = rows(root / RESULTS / "changed-classifications.csv")
    changed_index = unique(changed, [cell(r) for r in changed], "changed cells")
    require(
        set(changed_index)
        == {
            key
            for key, record in comparison.items()
            if record["status"] != record["corrected_status"]
        },
        "changed classifications coverage",
    )
    require(
        all(
            all(comparison[key].get(k) == v for k, v in record.items())
            for key, record in changed_index.items()
        ),
        "changed table disagrees",
    )
    return {
        "status": "PASS",
        "scope": "independent direct-index numerical verification",
        "cells": 108,
        "runs": 324,
        "max_abs_difference_kg": max_error,
        "specification_sha256": digest(spec_bytes),
        "scientific_release_qualification": "INCONCLUSIVE",
        "external_scientific_review": "NOT_RUN",
    }


def safe_receipt_path(path: Path, root: Path) -> None:
    output = path.resolve()
    parent = output.parent
    while not parent.exists():
        parent = parent.parent
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        check=False,
        env=environment,
    )
    require(
        not output.is_relative_to(root.resolve()) and result.stdout.strip() != b"true",
        "verification receipt must be outside all Git worktrees",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.json_out:
        safe_receipt_path(args.json_out, args.root)
    try:
        receipt = verify(args.root)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        receipt = {"status": "FAIL", "reason": str(error)}
    encoded = json.dumps(receipt, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=args.json_out.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        try:
            os.replace(temporary, args.json_out)
        finally:
            temporary.unlink(missing_ok=True)
    print(encoded, end="")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
