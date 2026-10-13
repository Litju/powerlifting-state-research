"""RES-292 new public-native synthetic-pretraining transfer experiment."""

# ruff: noqa: E501

from __future__ import annotations

import ast
import copy
import csv
import hashlib
import io
import json
import math
import os
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
    GenerationConfig,
    PublicCapacityTargets,
    PublicForecastRow,
    iter_public_rows,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (
    LIFTS,
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
from .synthetic_pretraining_transfer_learner import TARGETS, _features

PROTOCOL_RELATIVE = "studies/synthetic_pretraining_transfer/protocol.json"
FROZEN_RELATIVE = "studies/synthetic_pretraining_transfer/frozen-evidence.json"
FORMAL_RELATIVE = "studies/synthetic_pretraining_transfer/formal-specification.md"
LINEAGE_RELATIVE = "studies/synthetic_pretraining_transfer/historical-lineage.md"
LEARNER_RELATIVE = (
    "src/powerlifting_state_research/studies/synthetic_pretraining_transfer_learner.py"
)
EVALUATOR_RELATIVE = "src/powerlifting_state_research/studies/synthetic_pretraining_transfer.py"
OUTPUT_RELATIVE = "results/studies/synthetic_pretraining_transfer/public-native"
PUBLIC_SOURCE_PATHS = (
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py",
    "src/powerlifting_state_research/contracts/serialization.py",
)
ARMS = (
    "PUBLIC_ONLY",
    "SYNTHETIC_ONLY_BOOTSTRAP",
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP",
    "COMPUTE_MATCHED_PUBLIC_ONLY",
    "SYNTHETIC_ONLY_PSEUDOLABEL",
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL",
)
ARM_DATA = {
    "PUBLIC_ONLY": ("public", "NONE"),
    "SYNTHETIC_ONLY_BOOTSTRAP": ("bootstrap", "BOOTSTRAP_DUPLICATE_LABEL"),
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP": (
        "public+bootstrap",
        "BOOTSTRAP_DUPLICATE_LABEL",
    ),
    "COMPUTE_MATCHED_PUBLIC_ONLY": ("public", "NONE"),
    "SYNTHETIC_ONLY_PSEUDOLABEL": ("pseudolabel", "SURROGATE_PSEUDO_LABEL"),
    "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL": (
        "public+pseudolabel",
        "SURROGATE_PSEUDO_LABEL",
    ),
}
CONTRASTS = (
    ("SYNTHETIC_ONLY_BOOTSTRAP", "PUBLIC_ONLY"),
    ("SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP", "PUBLIC_ONLY"),
    ("SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP", "COMPUTE_MATCHED_PUBLIC_ONLY"),
    ("SYNTHETIC_ONLY_PSEUDOLABEL", "PUBLIC_ONLY"),
    ("SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL", "PUBLIC_ONLY"),
    ("SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL", "COMPUTE_MATCHED_PUBLIC_ONLY"),
)
PLAN_NAMES = ("cessation", "step_down", "continue", "step_up")
HORIZONS = (14, 28, 56)
FIT_SEEDS = (292201, 292202, 292203, 292204, 292205)
BOOTSTRAP_REPLICATES = 1000
PRACTICAL_MARGIN_KG = 1.0
EXPECTED_STARTING_MAIN = "0489029384af4503d175220e9a9a090845b38cc6"


def _sha(data: bytes) -> str:
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
    return "sha256:" + _sha(encoded)


def verify_design(root: Path) -> dict[str, Any]:
    protocol = json.loads((root / PROTOCOL_RELATIVE).read_text(encoding="utf-8"))
    frozen_path = root / FROZEN_RELATIVE
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if protocol["starting_main"] != EXPECTED_STARTING_MAIN:
        raise ValueError("RES-292 starting-main identity changed")
    if _protocol_digest(protocol) != protocol["identities"]["protocol_digest"]:
        raise ValueError("RES-292 protocol digest does not match its frozen contents")
    if protocol["frozen_evidence"]["sha256"] != "sha256:" + _sha(frozen_path.read_bytes()):
        raise ValueError("RES-292 frozen-evidence digest does not match")
    expected_id = (
        "psr:study:synthetic-pretraining-transfer-public-native@1.0.0~"
        + protocol["identities"]["protocol_digest"][7:19]
    )
    if protocol["identities"]["study_id"] != expected_id:
        raise ValueError("RES-292 study identity does not match the frozen protocol")
    if frozen["starting_main"] != EXPECTED_STARTING_MAIN:
        raise ValueError("RES-292 frozen evidence uses a different starting main")
    for relative, expected in frozen["files"].items():
        actual = "sha256:" + _sha((root / relative).read_bytes())
        if actual != expected:
            raise ValueError(f"frozen M0-M5/G1-G3 or G4 evidence changed: {relative}")
    base_files = frozen["historical_g4"]["baseline_homes"]
    for relative, expected in base_files.items():
        result = subprocess.run(
            ["git", "show", f"{EXPECTED_STARTING_MAIN}:{relative}"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        if "sha256:" + _sha(result.stdout) != expected:
            raise ValueError(f"historical G4 baseline metadata differs at {relative}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_STARTING_MAIN, "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError("RES-292 starting main is not an ancestor of this checkout")
    return cast(dict[str, Any], protocol)


def _opaque_id(role: str, source_id: str) -> str:
    return "res292-" + _sha(f"{role}\0{source_id}".encode())[:24]


def _target_values(targets: PublicCapacityTargets) -> dict[str, float]:
    values = cast(dict[str, float], targets)
    return {name: float(values[name]) for name in TARGETS}


def _public_record(row: PublicForecastRow, role: str) -> dict[str, Any]:
    record = asdict(row)
    identifier = _opaque_id(role, str(record["row_id"]))
    inputs = cast(dict[str, Any], record["inputs"])
    inputs["entity_id"] = identifier
    record["row_id"] = identifier
    return {"row_id": identifier, "inputs": inputs}


def _generate_split(
    seeds: dict[str, int], role: str, selected_split: str, count: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    if selected_split == "train":
        train_count, validation_count = count, 12
    elif selected_split == "validation":
        train_count, validation_count = 12, count
    else:
        raise ValueError("unknown public split role")
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
    source_ids: dict[str, str] = {}
    for split, row in iter_public_rows(config):
        if split != selected_split:
            continue
        public = _public_record(row, role)
        visible.append(public)
        truth.append({"row_id": public["row_id"], "targets": _target_values(row.targets)})
        source_ids[public["row_id"]] = row.row_id
    if len(visible) != count:
        raise ValueError(f"{role} split count mismatch")
    return visible, truth, source_ids


def _cell(row: dict[str, Any]) -> tuple[str, int]:
    inputs = row["inputs"]
    return (str(inputs["declared_future_plan"]["plan_id"]), int(inputs["horizon_days"]))


def _labeled_rows(
    visible: list[dict[str, Any]], truth: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    labels = {row["row_id"]: row["targets"] for row in truth}
    return [
        {"row_id": row["row_id"], "inputs": row["inputs"], "targets": labels[row["row_id"]]}
        for row in visible
    ]


def _make_bootstrap(
    fitting: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in fitting:
        by_cell.setdefault(_cell(row), []).append(row)
    rng = np.random.default_rng(seed)
    synthetic: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []
    for plan, horizon in sorted(by_cell):
        donors = by_cell[(plan, horizon)]
        for draw, selected in enumerate(rng.integers(0, len(donors), size=len(donors))):
            donor = donors[int(selected)]
            synthetic_id = f"res292-bootstrap-{len(synthetic):06d}"
            copied_inputs = copy.deepcopy(donor["inputs"])
            copied_inputs["entity_id"] = synthetic_id
            synthetic_row = {
                "row_id": synthetic_id,
                "inputs": copied_inputs,
                "targets": dict(donor["targets"]),
            }
            synthetic.append(synthetic_row)
            lineage.append(
                {
                    "synthetic_row_id": synthetic_id,
                    "donor_row_id": donor["row_id"],
                    "plan_id": plan,
                    "horizon_days": horizon,
                    "label_provenance": "BOOTSTRAP_DUPLICATE_LABEL",
                    "draw_within_cell": draw,
                    "donor_record_sha256": "sha256:" + _sha(canonical_json_bytes(donor)),
                }
            )
    if len(synthetic) != len(fitting):
        raise ValueError("bootstrap row count differs from fitting donors")
    return synthetic, lineage


def _teacher_fit(
    rows: list[dict[str, Any]], excluded_fold: int, folds: dict[str, int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    training = [row for row in rows if folds[row["row_id"]] != excluded_fold]
    heldout = [row for row in rows if folds[row["row_id"]] == excluded_fold]
    x = np.asarray([_features(row) for row in training], dtype=np.float64)
    y = np.asarray(
        [[row["targets"][target] for target in TARGETS] for row in training], dtype=np.float64
    )
    x_mean = x.mean(axis=0)
    x_scale = x.std(axis=0)
    x_scale[x_scale == 0.0] = 1.0
    y_mean = y.mean(axis=0)
    y_scale = y.std(axis=0)
    y_scale[y_scale == 0.0] = 1.0
    design = (x - x_mean) / x_scale
    response = (y - y_mean) / y_scale
    alpha = 100.0
    coefficients = np.linalg.solve(
        design.T @ design + alpha * np.eye(design.shape[1], dtype=np.float64),
        design.T @ response,
    )
    state = {
        "fold": excluded_fold,
        "alpha": alpha,
        "x_mean": x_mean.tolist(),
        "x_scale": x_scale.tolist(),
        "y_mean": y_mean.tolist(),
        "y_scale": y_scale.tolist(),
        "coefficients": coefficients.tolist(),
        "training_rows": len(training),
        "heldout_rows": len(heldout),
        "parameter_count": int(coefficients.size),
    }
    x_heldout = np.asarray([_features(row) for row in heldout], dtype=np.float64)
    prediction = (((x_heldout - x_mean) / x_scale) @ coefficients) * y_scale + y_mean
    predicted = [
        {
            "row_id": row["row_id"],
            "targets": {
                target: float(value) for target, value in zip(TARGETS, values, strict=True)
            },
        }
        for row, values in zip(heldout, prediction, strict=True)
    ]
    return state, predicted


def _make_pseudo_labels(
    fitting: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
    lineage: list[dict[str, Any]],
    seed: int,
    protocol_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in fitting:
        by_cell.setdefault(_cell(row), []).append(row)
    rng = np.random.default_rng(seed)
    folds: dict[str, int] = {}
    for key in sorted(by_cell):
        ids = [row["row_id"] for row in by_cell[key]]
        for fold, index in enumerate(rng.permutation(len(ids))):
            folds[ids[int(index)]] = fold % 4
    teacher_rows: list[dict[str, Any]] = []
    predictions_by_donor: dict[str, dict[str, float]] = {}
    for fold in range(4):
        state, predictions = _teacher_fit(fitting, fold, folds)
        state_sha = "sha256:" + _sha(canonical_json_bytes(state))
        fitted_id = (
            f"psr:fitted-instance:res292-summary-ridge-crossfit-fold{fold}@1.0.0~{state_sha[7:19]}"
        )
        teacher_rows.append(
            {
                "fitted_instance_id": fitted_id,
                "fold": fold,
                "alpha": state["alpha"],
                "training_rows": state["training_rows"],
                "heldout_rows": state["heldout_rows"],
                "parameter_count": state["parameter_count"],
                "state_sha256": state_sha,
                "fitted_state": state,
                "fitting_rule": "cross-fitted public Summary Ridge; alpha fixed at 100",
                "protocol_id": protocol_id,
            }
        )
        predictions_by_donor.update({row["row_id"]: row["targets"] for row in predictions})
    pseudo: list[dict[str, Any]] = []
    pseudo_lineage: list[dict[str, Any]] = []
    for bootstrap_row, donor_item in zip(bootstrap, lineage, strict=True):
        donor_id = donor_item["donor_row_id"]
        pseudo_row = {
            "row_id": bootstrap_row["row_id"],
            "inputs": bootstrap_row["inputs"],
            "targets": predictions_by_donor[donor_id],
        }
        pseudo.append(pseudo_row)
        pseudo_lineage.append(
            {
                **donor_item,
                "label_provenance": "SURROGATE_PSEUDO_LABEL",
                "teacher_fitted_instance": teacher_rows[folds[donor_id]]["fitted_instance_id"],
                "teacher_prediction_sha256": "sha256:"
                + _sha(canonical_json_bytes(predictions_by_donor[donor_id])),
                "donor_original_label_copied": False,
            }
        )
    return pseudo, teacher_rows, pseudo_lineage


def _build_inputs(protocol: dict[str, Any]) -> dict[str, Any]:
    seeds = protocol["protocol"]["seeds"]
    splits = protocol["protocol"]["splits"]["rows"]
    fitting_visible, fitting_truth, fitting_keys = _generate_split(
        seeds["fitting"], "fitting", "train", splits["fitting"]
    )
    development, development_truth, development_keys = _generate_split(
        seeds["development"], "development", "validation", splits["development"]
    )
    test_a, truth_a, keys_a = _generate_split(
        seeds["test_population_a"], "test-population-a", "validation", splits["test_population_a"]
    )
    test_b, truth_b, keys_b = _generate_split(
        seeds["test_population_b"], "test-population-b", "validation", splits["test_population_b"]
    )
    fitting = _labeled_rows(fitting_visible, fitting_truth)
    bootstrap, bootstrap_lineage = _make_bootstrap(fitting, seeds["bootstrap"])
    pseudo, teacher_rows, pseudo_lineage = _make_pseudo_labels(
        fitting,
        bootstrap,
        bootstrap_lineage,
        seeds["teacher_crossfit"],
        protocol["identities"]["study_id"],
    )
    groups = [fitting, development, test_a, test_b]
    entity_sets = [{row["row_id"] for row in group} for group in groups]
    for index, left in enumerate(entity_sets):
        if len(left) != len(groups[index]):
            raise ValueError("study split contains duplicate entity IDs")
        for right in entity_sets[index + 1 :]:
            if left & right:
                raise ValueError("fitting, development, and test entities overlap")
    if {row["row_id"] for row in bootstrap} & {row["row_id"] for row in fitting}:
        raise ValueError("bootstrap row IDs expose donor IDs")
    if {row["row_id"] for row in pseudo} != {row["row_id"] for row in bootstrap}:
        raise ValueError("pseudo-label donor rows differ from bootstrap inputs")
    if any(set(row) != {"row_id", "inputs"} for row in development + test_a + test_b):
        raise ValueError("held-out targets entered a participant-visible realization")
    return {
        "fitting": fitting,
        "development": development,
        "development_truth": development_truth,
        "test_population_a": test_a,
        "test_population_a_truth": truth_a,
        "test_population_b": test_b,
        "test_population_b_truth": truth_b,
        "bootstrap": bootstrap,
        "bootstrap_lineage": bootstrap_lineage,
        "pseudolabel": pseudo,
        "pseudolabel_lineage": pseudo_lineage,
        "teacher_fits": teacher_rows,
        "source_entity_keys": {
            "fitting": fitting_keys,
            "development": development_keys,
            "test_population_a": keys_a,
            "test_population_b": keys_b,
        },
    }


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _input_payload_audit(
    source: bytes, payload: bytes, arm: str, fitting: dict[str, Any]
) -> dict[str, Any]:
    tree = ast.parse(source)
    allowed_imports = {"__future__", "json", "math", "sys", "typing", "numpy"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    if not imported <= allowed_imports:
        raise ValueError(f"learner import escaped allow-list: {sorted(imported - allowed_imports)}")
    forbidden_calls = {"open", "eval", "exec", "compile", "__import__"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if calls & forbidden_calls:
        raise ValueError(
            f"learner source contains forbidden calls: {sorted(calls & forbidden_calls)}"
        )
    request = json.loads(payload)
    if request["arm"] != arm:
        raise ValueError("learner payload arm does not match its execution")
    queries = request["queries"]
    if any("targets" in query["row"] for query in queries):
        raise ValueError("development or evaluation targets entered the learner payload")
    forbidden = {
        "evaluation_truth",
        "hidden_states",
        "latent_states",
        "population_coordinates",
        "source_parameters",
        "exact_population_bounds",
        "authority_keys",
        "donor_row_id",
        "matched_key",
    }

    def hidden_keys(value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden:
                    found.append(key)
                found.extend(hidden_keys(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(hidden_keys(child))
        return found

    leaked = hidden_keys(request)
    if leaked:
        raise ValueError(f"authority-only fields entered the learner payload: {leaked}")
    expected_public = fitting["fitting"] if "public" in ARM_DATA[arm][0] else []
    expected_synthetic = (
        fitting["bootstrap"]
        if ARM_DATA[arm][1] == "BOOTSTRAP_DUPLICATE_LABEL"
        else fitting["pseudolabel"]
        if ARM_DATA[arm][1] == "SURROGATE_PSEUDO_LABEL"
        else []
    )
    expected_provenance = ARM_DATA[arm][1]
    if canonical_json_bytes(request["public_rows"]) != canonical_json_bytes(
        expected_public
    ) or canonical_json_bytes(request["synthetic_rows"]) != canonical_json_bytes(
        expected_synthetic
    ):
        raise ValueError(f"{arm} did not receive its predeclared fitting records")
    if request["synthetic_label_provenance"] != expected_provenance:
        raise ValueError("learner label provenance does not match the declared treatment")
    training_ids = {row["row_id"] for row in request["public_rows"] + request["synthetic_rows"]}
    query_ids = {query["row"]["row_id"] for query in queries}
    if training_ids & query_ids or len(query_ids) != len(queries):
        raise ValueError("learner fitting and held-out entities overlap")
    return {
        "passed": True,
        "arm": arm,
        "allowed_imports": sorted(imported),
        "public_fitting_rows": len(request["public_rows"]),
        "synthetic_fitting_rows": len(request["synthetic_rows"]),
        "synthetic_label_provenance": expected_provenance,
        "development_and_test_query_rows": len(queries),
        "query_targets_in_payload": 0,
        "authority_only_fields_in_payload": 0,
        "fitting_development_test_entities_disjoint": True,
        "learner_source_sha256": "sha256:" + _sha(source),
        "payload_sha256": "sha256:" + _sha(payload),
        "runtime": "isolated Python subprocess with first-party file/network/import guards",
    }


class LearnerExecutionError(RuntimeError):
    """A frozen arm failed within its declared fitting budget."""


def _run_learner(
    root: Path,
    arm: str,
    fit_seed: int,
    fitting: dict[str, Any],
    queries: list[dict[str, Any]],
    source: bytes,
    protocol_id: str,
) -> tuple[dict[str, Any], bytes, bytes, dict[str, Any]]:
    synthetic_kind, provenance = ARM_DATA[arm]
    request = {
        "protocol_id": protocol_id,
        "arm": arm,
        "fit_seed": fit_seed,
        "public_rows": fitting["fitting"] if "public" in synthetic_kind else [],
        "synthetic_rows": (
            fitting["bootstrap"]
            if provenance == "BOOTSTRAP_DUPLICATE_LABEL"
            else fitting["pseudolabel"]
            if provenance == "SURROGATE_PSEUDO_LABEL"
            else []
        ),
        "synthetic_label_provenance": provenance,
        "queries": queries,
    }
    payload = canonical_json_bytes(request)
    audit = _input_payload_audit(source, payload, arm, fitting)
    with tempfile.TemporaryDirectory(prefix="res292-learner-") as temporary:
        sandbox = Path(temporary)
        learner_script = sandbox / "learner.py"
        learner_script.write_bytes(source)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        try:
            process = subprocess.run(
                [sys.executable, "-I", str(learner_script)],
                cwd=sandbox,
                env=environment,
                input=payload,
                capture_output=True,
                check=False,
                timeout=180,
            )
        except subprocess.TimeoutExpired as error:
            raise LearnerExecutionError("learner exceeded its frozen 180-second budget") from error
    if process.returncode != 0:
        raise LearnerExecutionError(
            "isolated learner failed: " + process.stderr.decode("utf-8", errors="replace")[-2000:]
        )
    output = process.stdout
    result = cast(dict[str, Any], json.loads(output))
    if (
        result.get("protocol_id") != protocol_id
        or result.get("arm") != arm
        or result.get("fit_seed") != fit_seed
        or result.get("parameter_count") != 177
    ):
        raise ValueError("learner returned an unexpected identity or architecture")
    if not np.all(np.isfinite(np.asarray(result["weights"], dtype=np.float64))):
        raise ValueError("learner returned nonfinite fitted weights")
    audit["learner_stdout_sha256"] = "sha256:" + _sha(output)
    return result, payload, output, audit


def _run_all_arms(
    root: Path, protocol: dict[str, Any], fitting: dict[str, Any]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    source = (root / LEARNER_RELATIVE).read_bytes()
    queries = [{"evaluation_set": "development", "row": row} for row in fitting["development"]] + [
        {"evaluation_set": population, "row": row}
        for population in ("test_population_a", "test_population_b")
        for row in fitting[population]
    ]
    fits: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    learning_curve_predictions: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for arm in ARMS:
        for fit_seed in FIT_SEEDS:
            try:
                result, payload, output, audit = _run_learner(
                    root,
                    arm,
                    fit_seed,
                    fitting,
                    queries,
                    source,
                    protocol["identities"]["study_id"],
                )
            except LearnerExecutionError as error:
                failures.append(
                    {
                        "arm": arm,
                        "fit_seed": fit_seed,
                        "status": "MODEL_FIT_FAILED",
                        "failure": str(error),
                    }
                )
                continue
            predictions.extend(result["predictions"])
            learning_curve_predictions.extend(result["learning_curve_predictions"])
            fits.append(
                {
                    "arm": arm,
                    "fit_seed": fit_seed,
                    "weights": result["weights"],
                    "parameter_count": result["parameter_count"],
                    "public_updates": result["public_updates"],
                    "synthetic_updates": result["synthetic_updates"],
                    "public_row_presentations": result["public_row_presentations"],
                    "synthetic_row_presentations": result["synthetic_row_presentations"],
                    "payload_sha256": "sha256:" + _sha(payload),
                    "learner_stdout_sha256": "sha256:" + _sha(output),
                    "state_sha256": "sha256:" + _sha(canonical_json_bytes(result["weights"])),
                }
            )
            audit["fit_seed"] = fit_seed
            audits.append(audit)
    if len(predictions) != len(fits) * 2 * 384:
        raise ValueError("learner prediction row count does not match fitted instances")
    return fits, predictions, learning_curve_predictions, audits, failures


def _csv_bytes(headers: list[str], rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return stream.getvalue().encode("utf-8")


def _data_artifacts(fitting: dict[str, Any]) -> dict[str, bytes]:
    outputs = {
        "realizations/fitting.jsonl": _jsonl(fitting["fitting"]),
        "realizations/development-visible.jsonl": _jsonl(fitting["development"]),
        "realizations/development-truth.jsonl": _jsonl(fitting["development_truth"]),
        "realizations/test-population-a-visible.jsonl": _jsonl(fitting["test_population_a"]),
        "realizations/test-population-a-truth.jsonl": _jsonl(fitting["test_population_a_truth"]),
        "realizations/test-population-b-visible.jsonl": _jsonl(fitting["test_population_b"]),
        "realizations/test-population-b-truth.jsonl": _jsonl(fitting["test_population_b_truth"]),
        "synthetic/donor-copy-bootstrap.jsonl": _jsonl(fitting["bootstrap"]),
        "synthetic/surrogate-pseudo-labels.jsonl": _jsonl(fitting["pseudolabel"]),
        "synthetic/donor-lineage.jsonl": _jsonl(fitting["bootstrap_lineage"]),
        "synthetic/pseudo-label-lineage.jsonl": _jsonl(fitting["pseudolabel_lineage"]),
        "synthetic/teacher-crossfit.jsonl": _jsonl(fitting["teacher_fits"]),
    }
    split_rows = []
    for role, rows in (
        ("fitting", fitting["fitting"]),
        ("development", fitting["development"]),
        ("test_population_a", fitting["test_population_a"]),
        ("test_population_b", fitting["test_population_b"]),
    ):
        ids = sorted(row["row_id"] for row in rows)
        split_rows.append(
            {
                "role": role,
                "entity_count": len(ids),
                "row_count": len(rows),
                "entity_ids_sha256": "sha256:" + _sha("\n".join(ids).encode()),
            }
        )
    outputs["realizations/split.json"] = (
        canonical_json_bytes(
            {
                "format": "PSR_RES292_SPLIT_V1",
                "roles": split_rows,
                "entity_disjoint": True,
                "authority_source_entity_keys_serialized": False,
            }
        )
        + b"\n"
    )
    label_rows: list[dict[str, Any]] = []
    for row in fitting["fitting"]:
        label_rows.extend(
            {
                "row_id": row["row_id"],
                "target": target,
                "label_provenance": "ORIGINAL_PUBLIC_LABEL",
                "donor_row_id": "",
                "teacher_fitted_instance": "",
            }
            for target in TARGETS
        )
    for source_name, source_rows, lineage_rows in (
        ("BOOTSTRAP_DUPLICATE_LABEL", fitting["bootstrap"], fitting["bootstrap_lineage"]),
        ("SURROGATE_PSEUDO_LABEL", fitting["pseudolabel"], fitting["pseudolabel_lineage"]),
    ):
        lineage_by_id = {row["synthetic_row_id"]: row for row in lineage_rows}
        for row in source_rows:
            lineage = lineage_by_id[row["row_id"]]
            label_rows.extend(
                {
                    "row_id": row["row_id"],
                    "target": target,
                    "label_provenance": source_name,
                    "donor_row_id": lineage["donor_row_id"],
                    "teacher_fitted_instance": lineage.get("teacher_fitted_instance", ""),
                }
                for target in TARGETS
            )
    outputs["synthetic/training-label-provenance.csv"] = _csv_bytes(
        [
            "row_id",
            "target",
            "label_provenance",
            "donor_row_id",
            "teacher_fitted_instance",
        ],
        label_rows,
    )
    return outputs


def _realization_manifest(
    protocol: dict[str, Any], artifacts: dict[str, bytes], fitting: dict[str, Any]
) -> tuple[bytes, str, str]:
    jsonl_paths = sorted(path for path in artifacts if path.endswith(".jsonl"))
    artifact_hashes = tuple(
        ArtifactHash(path, _sha(artifacts[path]), "application/x-ndjson") for path in jsonl_paths
    )
    public_count = sum(
        len(fitting[name])
        for name in ("fitting", "development", "test_population_a", "test_population_b")
    )
    splits = (
        SplitIdentity(
            "fitting", "original public training rows with ORIGINAL_PUBLIC_LABEL", 384, 384
        ),
        SplitIdentity(
            "development", "public development inputs and authority-only labels", 192, 192
        ),
        SplitIdentity("test_population_a", "held-out population A; truth authority-only", 384, 384),
        SplitIdentity(
            "test_population_b", "independent held-out population B; truth authority-only", 384, 384
        ),
        SplitIdentity(
            "donor_bootstrap", "dependent donor-copy records; no independent entities", 0, 384
        ),
        SplitIdentity(
            "surrogate_pseudo_labels",
            "dependent conditional predictions; no independent entities",
            0,
            384,
        ),
    )
    seeds = (
        ("fitting_population", 292101),
        ("fitting_intervention", 292102),
        ("fitting_observation", 292103),
        ("fitting_split", 292104),
        ("development_population", 292111),
        ("development_intervention", 292112),
        ("development_observation", 292113),
        ("development_split", 292114),
        ("test_population_a_population", 292121),
        ("test_population_a_intervention", 292122),
        ("test_population_a_observation", 292123),
        ("test_population_a_split", 292124),
        ("test_population_b_population", 292131),
        ("test_population_b_intervention", 292132),
        ("test_population_b_observation", 292133),
        ("test_population_b_split", 292134),
        ("donor_bootstrap", 292180),
        ("teacher_crossfit", 292190),
    )
    manifest = DatasetRealizationManifest(
        dataset_spec_id=protocol["identities"]["dataset_spec_id"],
        realization_id="synthetic-pretraining-transfer-public-native",
        generator_identity=(
            "Evaluation Authority only; frozen public-native dataset iterator; source-set="
            + sha256_record(
                {
                    path: "sha256:"
                    + _sha((Path(__file__).resolve().parents[3] / path).read_bytes())
                    for path in PUBLIC_SOURCE_PATHS
                }
            )
        ),
        source_identity=PROTOCOL_RELATIVE,
        seeds=seeds,
        replicate_ids=("test-population-a", "test-population-b"),
        entity_count=public_count,
        row_count=public_count + 768,
        split_identities=splits,
        artifact_hashes=artifact_hashes,
        schema_identity="latent-capacity-transient-participant-row-v2+res292-role-splits-v1",
        temporal_coverage=TemporalCoverage("day", 0, 279),
        realized_intervention_support=tuple(
            SupportSummary(f"plan:{plan}", "Declared public plan; no off-support plan evaluated.")
            for plan in PLAN_NAMES
        ),
        observation_availability=tuple(
            ObservationAvailability(
                name,
                public_count * len(LIFTS) * 32,
                0,
            )
            for name in ("assessment_kg", "prescribed_load_kg", "velocity_mps")
        ),
        provenance=(
            "New public-native synthetic realization. Bootstrap and pseudo-label data are dependent "
            "copies or predictions; they are not additional independent entities. Evaluation truth "
            "is stored separately and joined only after prediction sealing."
        ),
        rights=RightsMetadata(
            "MIT",
            "Powerlifting State Research contributors",
            "Generated public-native synthetic rows and derived labels; no private historical material.",
        ),
    )
    payload = json.loads(manifest.canonical_serialization)
    payload["identity_id"] = manifest.identity_id
    payload["realization_digest"] = manifest.realization_digest
    payload["manifest_digest"] = manifest.manifest_digest
    return (
        canonical_json_bytes(payload) + b"\n",
        manifest.identity_id,
        manifest.realization_digest,
    )


def _seed_from(*parts: object) -> int:
    value = "\0".join(str(part) for part in parts)
    return int(_sha(value.encode())[:8], 16)


def _rmse(errors: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(errors))))


def _metric_values(errors: np.ndarray) -> tuple[float, float, float]:
    return (
        _rmse(errors),
        float(np.mean(np.abs(errors))),
        float(np.mean(errors)),
    )


def _plan_bootstrap_indices(
    plan_ids: list[str], rng: np.random.Generator, replicates: int
) -> np.ndarray:
    indices: list[np.ndarray] = []
    for plan in PLAN_NAMES:
        cell = np.flatnonzero(np.asarray(plan_ids) == plan)
        if not len(cell):
            raise ValueError(f"paired bootstrap has no entities in plan {plan}")
        indices.append(rng.choice(cell, size=(replicates, len(cell)), replace=True))
    return np.concatenate(indices, axis=1)


def _metric_intervals(
    errors: np.ndarray, plan_ids: list[str], seed: int
) -> dict[str, tuple[float, float]]:
    indices = _plan_bootstrap_indices(plan_ids, np.random.default_rng(seed), BOOTSTRAP_REPLICATES)
    sampled = errors[indices]
    values = np.column_stack(
        (
            np.sqrt(np.mean(np.square(sampled), axis=1)),
            np.mean(np.abs(sampled), axis=1),
            np.mean(sampled, axis=1),
        )
    )
    quantiles = np.quantile(values, (0.025, 0.975), axis=0)
    return {
        metric: (float(quantiles[0, index]), float(quantiles[1, index]))
        for index, metric in enumerate(("rmse", "mae", "bias"))
    }


def _paired_rmse_deltas(
    treatment: np.ndarray,
    control: np.ndarray,
    plan_ids: list[str],
    seed: int,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> np.ndarray:
    indices = _plan_bootstrap_indices(plan_ids, np.random.default_rng(seed), replicates)
    values = np.sqrt(np.mean(np.square(treatment[indices]), axis=1)) - np.sqrt(
        np.mean(np.square(control[indices]), axis=1)
    )
    return np.asarray(values, dtype=np.float64)


def _decision_status(lower: float, upper: float) -> str:
    if upper < -PRACTICAL_MARGIN_KG:
        return "PRACTICAL_BENEFIT"
    if lower > PRACTICAL_MARGIN_KG:
        return "PRACTICAL_HARM"
    if lower >= -PRACTICAL_MARGIN_KG and upper <= PRACTICAL_MARGIN_KG:
        return "PRACTICAL_EQUIVALENCE"
    return "INCONCLUSIVE"


def _fitted_instances(
    fits: list[dict[str, Any]],
    input_hashes: dict[str, str],
    protocol: dict[str, Any],
    realization_id: str,
    learner_source_sha: str,
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], str]]:
    identities: list[dict[str, Any]] = []
    ids: dict[tuple[str, int], str] = {}
    for fit in fits:
        arm = fit["arm"]
        synthetic_kind = ARM_DATA[arm][1]
        fitting_inputs = {
            "public": input_hashes["realizations/fitting.jsonl"]
            if "public" in ARM_DATA[arm][0]
            else None,
            "synthetic": input_hashes[
                "synthetic/donor-copy-bootstrap.jsonl"
                if synthetic_kind == "BOOTSTRAP_DUPLICATE_LABEL"
                else "synthetic/surrogate-pseudo-labels.jsonl"
            ]
            if synthetic_kind != "NONE"
            else None,
        }
        digest = sha256_record(
            {
                "format": "PSR_RES292_FITTED_INSTANCE_V1",
                "protocol_id": protocol["identities"]["study_id"],
                "realization_id": realization_id,
                "arm": arm,
                "fit_seed": fit["fit_seed"],
                "fitting_artifact_sha256": fitting_inputs,
                "learner_source_sha256": learner_source_sha,
                "state_sha256": fit["state_sha256"],
            }
        )
        arm_slug = arm.lower().replace("_", "-")
        fitted_id = (
            f"psr:fitted-instance:res292-{arm_slug}-seed-{fit['fit_seed']}@1.0.0~{digest[7:19]}"
        )
        require_scientific_id(
            fitted_id, "RES-292 fitted instance", expected_class="fitted-instance"
        )
        identity = {
            "fitted_instance_id": fitted_id,
            "identity_digest": digest,
            "study_id": protocol["identities"]["study_id"],
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "arm": arm,
            "fit_seed": fit["fit_seed"],
            "parameter_count": fit["parameter_count"],
            "fitting_artifact_sha256": fitting_inputs,
            "learner_source_sha256": learner_source_sha,
            "state_sha256": fit["state_sha256"],
            "update_count": fit["public_updates"] + fit["synthetic_updates"],
        }
        identities.append(identity)
        ids[(arm, int(fit["fit_seed"]))] = fitted_id
    return identities, ids


def _sealed_predictions(
    prediction_rows: list[dict[str, Any]],
    instance_ids: dict[tuple[str, int], str],
    protocol: dict[str, Any],
    realization_id: str,
) -> tuple[list[dict[str, Any]], bytes, str]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, str]] = set()
    for raw in prediction_rows:
        key = (raw["arm"], int(raw["fit_seed"]), raw["evaluation_set"], raw["row_id"])
        if key in seen:
            raise ValueError("duplicate learner prediction row")
        seen.add(key)
        if set(raw["targets"]) != set(TARGETS) or any(
            not math.isfinite(float(value)) for value in raw["targets"].values()
        ):
            raise ValueError("learner prediction has invalid targets")
        output.append(
            {
                **raw,
                "model_id": instance_ids[(raw["arm"], int(raw["fit_seed"]))],
                "study_id": protocol["identities"]["study_id"],
                "protocol_digest": protocol["identities"]["protocol_digest"],
                "realization_id": realization_id,
                "evaluation_id": protocol["identities"]["study_evaluation_id"],
            }
        )
    output.sort(
        key=lambda row: (
            row["arm"],
            row["fit_seed"],
            row["evaluation_set"],
            row["row_id"],
        )
    )
    content = _jsonl(output)
    return output, content, "sha256:" + _sha(content)


def _index_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["row_id"]: row for row in rows}


def _evaluation_tables(
    prediction_rows: list[dict[str, Any]],
    curve_rows: list[dict[str, Any]],
    fitting: dict[str, Any],
    instance_ids: dict[tuple[str, int], str],
    protocol: dict[str, Any],
    realization_id: str,
    prediction_sha: str,
) -> tuple[bytes, bytes, bytes]:
    truth_by_population = {
        population: _index_rows(fitting[f"{population}_truth"])
        for population in ("test_population_a", "test_population_b")
    }
    prediction_index = {
        (row["arm"], int(row["fit_seed"]), row["evaluation_set"], row["row_id"]): row["targets"]
        for row in prediction_rows
    }
    metric_rows: list[dict[str, Any]] = []
    errors_by_key: dict[tuple[str, int, str, str, int], tuple[np.ndarray, list[str]]] = {}
    for population in ("test_population_a", "test_population_b"):
        visible = fitting[population]
        for horizon in HORIZONS:
            rows = [row for row in visible if row["inputs"]["horizon_days"] == horizon]
            rows.sort(key=lambda row: row["row_id"])
            plans = [str(row["inputs"]["declared_future_plan"]["plan_id"]) for row in rows]
            truth = truth_by_population[population]
            for lift_index, target in enumerate(TARGETS):
                for arm in ARMS:
                    for fit_seed in FIT_SEEDS:
                        model_id = instance_ids.get((arm, fit_seed))
                        if model_id is None:
                            metric_rows.append(
                                {
                                    "study_id": protocol["identities"]["study_id"],
                                    "protocol_digest": protocol["identities"]["protocol_digest"],
                                    "realization_id": realization_id,
                                    "evaluation_id": protocol["identities"]["study_evaluation_id"],
                                    "prediction_sha256": prediction_sha,
                                    "population": population,
                                    "lift": LIFTS[lift_index],
                                    "target": target,
                                    "horizon_days": horizon,
                                    "arm": arm,
                                    "fit_seed": fit_seed,
                                    "model_id": "",
                                    "n_entities": len(rows),
                                    "status": "MODEL_FIT_FAILED",
                                }
                            )
                            continue
                        errors = np.asarray(
                            [
                                prediction_index[(arm, fit_seed, population, row["row_id"])][target]
                                - float(truth[row["row_id"]]["targets"][target])
                                for row in rows
                            ],
                            dtype=np.float64,
                        )
                        point = _metric_values(errors)
                        ci = _metric_intervals(
                            errors,
                            plans,
                            _seed_from(
                                292170,
                                "metrics",
                                population,
                                LIFTS[lift_index],
                                horizon,
                                arm,
                                fit_seed,
                            ),
                        )
                        metric_rows.append(
                            {
                                "study_id": protocol["identities"]["study_id"],
                                "protocol_digest": protocol["identities"]["protocol_digest"],
                                "realization_id": realization_id,
                                "evaluation_id": protocol["identities"]["study_evaluation_id"],
                                "prediction_sha256": prediction_sha,
                                "population": population,
                                "lift": LIFTS[lift_index],
                                "target": target,
                                "horizon_days": horizon,
                                "arm": arm,
                                "fit_seed": fit_seed,
                                "model_id": model_id,
                                "n_entities": len(rows),
                                "rmse_kg": point[0],
                                "rmse_ci95_lower_kg": ci["rmse"][0],
                                "rmse_ci95_upper_kg": ci["rmse"][1],
                                "mae_kg": point[1],
                                "mae_ci95_lower_kg": ci["mae"][0],
                                "mae_ci95_upper_kg": ci["mae"][1],
                                "signed_bias_kg": point[2],
                                "bias_ci95_lower_kg": ci["bias"][0],
                                "bias_ci95_upper_kg": ci["bias"][1],
                                "status": "COMPLETE",
                            }
                        )
                        errors_by_key[(arm, fit_seed, population, LIFTS[lift_index], horizon)] = (
                            errors,
                            plans,
                        )
    effect_rows: list[dict[str, Any]] = []
    for population in ("test_population_a", "test_population_b"):
        for lift in LIFTS:
            for horizon in HORIZONS:
                for treatment, control in CONTRASTS:
                    per_seed: dict[int, tuple[float, np.ndarray, list[str]]] = {}
                    for fit_seed in FIT_SEEDS:
                        first = errors_by_key.get((treatment, fit_seed, population, lift, horizon))
                        second = errors_by_key.get((control, fit_seed, population, lift, horizon))
                        common = {
                            "study_id": protocol["identities"]["study_id"],
                            "protocol_digest": protocol["identities"]["protocol_digest"],
                            "realization_id": realization_id,
                            "evaluation_id": protocol["identities"]["study_evaluation_id"],
                            "prediction_sha256": prediction_sha,
                            "population": population,
                            "lift": lift,
                            "target": f"{lift}_delta_capacity_kg",
                            "horizon_days": horizon,
                            "treatment_arm": treatment,
                            "control_arm": control,
                            "treatment_model_id": instance_ids.get((treatment, fit_seed), ""),
                            "control_model_id": instance_ids.get((control, fit_seed), ""),
                        }
                        if first is None or second is None:
                            effect_rows.append(
                                {
                                    **common,
                                    "fit_seed": fit_seed,
                                    "aggregation": "per_seed",
                                    "delta_rmse_kg": "",
                                    "ci95_lower_kg": "",
                                    "ci95_upper_kg": "",
                                    "status": "MODEL_FIT_FAILED",
                                }
                            )
                            continue
                        first_errors, plans = first
                        second_errors, _ = second
                        delta = _rmse(first_errors) - _rmse(second_errors)
                        samples = _paired_rmse_deltas(
                            first_errors,
                            second_errors,
                            plans,
                            _seed_from(
                                292170,
                                "paired",
                                population,
                                lift,
                                horizon,
                                treatment,
                                control,
                                fit_seed,
                            ),
                        )
                        lower, upper = np.quantile(samples, (0.025, 0.975))
                        per_seed[fit_seed] = (delta, samples, plans)
                        effect_rows.append(
                            {
                                **common,
                                "fit_seed": fit_seed,
                                "aggregation": "per_seed",
                                "delta_rmse_kg": delta,
                                "ci95_lower_kg": float(lower),
                                "ci95_upper_kg": float(upper),
                                "practical_margin_kg": PRACTICAL_MARGIN_KG,
                                "status": _decision_status(float(lower), float(upper)),
                            }
                        )
                    if len(per_seed) != len(FIT_SEEDS):
                        effect_rows.append(
                            {
                                "study_id": protocol["identities"]["study_id"],
                                "protocol_digest": protocol["identities"]["protocol_digest"],
                                "realization_id": realization_id,
                                "evaluation_id": protocol["identities"]["study_evaluation_id"],
                                "prediction_sha256": prediction_sha,
                                "population": population,
                                "lift": lift,
                                "target": f"{lift}_delta_capacity_kg",
                                "horizon_days": horizon,
                                "treatment_arm": treatment,
                                "control_arm": control,
                                "treatment_model_id": ";".join(
                                    instance_ids.get((treatment, seed), "") for seed in FIT_SEEDS
                                ),
                                "control_model_id": ";".join(
                                    instance_ids.get((control, seed), "") for seed in FIT_SEEDS
                                ),
                                "fit_seed": "",
                                "aggregation": "pooled_hierarchical",
                                "delta_rmse_kg": "",
                                "ci95_lower_kg": "",
                                "ci95_upper_kg": "",
                                "status": "MODEL_FIT_FAILED",
                            }
                        )
                        continue
                    rng = np.random.default_rng(
                        _seed_from(292170, "pooled", population, lift, horizon, treatment, control)
                    )
                    pooled = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
                    seed_order = list(FIT_SEEDS)
                    for replicate in range(BOOTSTRAP_REPLICATES):
                        sampled_seeds = rng.choice(seed_order, size=len(seed_order), replace=True)
                        deltas = []
                        for selected_seed in sampled_seeds:
                            treatment_errors, control_errors = (
                                errors_by_key[
                                    (treatment, int(selected_seed), population, lift, horizon)
                                ][0],
                                errors_by_key[
                                    (control, int(selected_seed), population, lift, horizon)
                                ][0],
                            )
                            plan_ids = per_seed[int(selected_seed)][2]
                            indices = _plan_bootstrap_indices(
                                plan_ids,
                                rng,
                                1,
                            )[0]
                            deltas.append(
                                _rmse(treatment_errors[indices]) - _rmse(control_errors[indices])
                            )
                        pooled[replicate] = float(np.mean(deltas))
                    low, high = np.quantile(pooled, (0.025, 0.975))
                    means = [per_seed[seed][0] for seed in FIT_SEEDS]
                    effect_rows.append(
                        {
                            "study_id": protocol["identities"]["study_id"],
                            "protocol_digest": protocol["identities"]["protocol_digest"],
                            "realization_id": realization_id,
                            "evaluation_id": protocol["identities"]["study_evaluation_id"],
                            "prediction_sha256": prediction_sha,
                            "population": population,
                            "lift": lift,
                            "target": f"{lift}_delta_capacity_kg",
                            "horizon_days": horizon,
                            "treatment_arm": treatment,
                            "control_arm": control,
                            "treatment_model_id": ";".join(
                                instance_ids[(treatment, seed)] for seed in FIT_SEEDS
                            ),
                            "control_model_id": ";".join(
                                instance_ids[(control, seed)] for seed in FIT_SEEDS
                            ),
                            "fit_seed": "",
                            "aggregation": "pooled_hierarchical",
                            "delta_rmse_kg": float(np.mean(means)),
                            "ci95_lower_kg": float(low),
                            "ci95_upper_kg": float(high),
                            "practical_margin_kg": PRACTICAL_MARGIN_KG,
                            "status": _decision_status(float(low), float(high)),
                        }
                    )

    development_truth = _index_rows(fitting["development_truth"])
    curve_groups: dict[
        tuple[str, int, str, int, int], list[tuple[dict[str, Any], dict[str, Any]]]
    ] = {}
    for row in curve_rows:
        source = development_truth[row["row_id"]]
        key = (
            row["arm"],
            int(row["fit_seed"]),
            row["stage"],
            int(row["public_updates"]),
            int(row["synthetic_updates"]),
        )
        curve_groups.setdefault(key, []).append((row, source))
    curve_metrics: list[dict[str, Any]] = []
    for key, pairs in sorted(curve_groups.items()):
        arm, fit_seed, stage, public_updates, synthetic_updates = key
        for lift_index, target in enumerate(TARGETS):
            horizon_values = sorted({int(row["inputs"]["horizon_days"]) for row, _ in pairs})
            for horizon in horizon_values:
                values = [
                    (row, truth)
                    for row, truth in pairs
                    if int(row["inputs"]["horizon_days"]) == horizon
                ]
                error = np.asarray(
                    [
                        float(row["targets"][target]) - float(truth["targets"][target])
                        for row, truth in values
                    ],
                    dtype=np.float64,
                )
                rmse, mae, bias = _metric_values(error)
                curve_metrics.append(
                    {
                        "study_id": protocol["identities"]["study_id"],
                        "protocol_digest": protocol["identities"]["protocol_digest"],
                        "realization_id": realization_id,
                        "evaluation_id": protocol["identities"]["study_evaluation_id"],
                        "model_id": instance_ids[(arm, fit_seed)],
                        "arm": arm,
                        "fit_seed": fit_seed,
                        "stage": stage,
                        "public_updates": public_updates,
                        "synthetic_updates": synthetic_updates,
                        "lift": LIFTS[lift_index],
                        "target": target,
                        "horizon_days": horizon,
                        "n_entities": len(values),
                        "rmse_kg": rmse,
                        "mae_kg": mae,
                        "signed_bias_kg": bias,
                        "status": "COMPLETE",
                    }
                )
    eval_headers = [
        "study_id",
        "protocol_digest",
        "realization_id",
        "evaluation_id",
        "prediction_sha256",
        "population",
        "lift",
        "target",
        "horizon_days",
        "arm",
        "fit_seed",
        "model_id",
        "n_entities",
        "rmse_kg",
        "rmse_ci95_lower_kg",
        "rmse_ci95_upper_kg",
        "mae_kg",
        "mae_ci95_lower_kg",
        "mae_ci95_upper_kg",
        "signed_bias_kg",
        "bias_ci95_lower_kg",
        "bias_ci95_upper_kg",
        "status",
    ]
    effect_headers = [
        "study_id",
        "protocol_digest",
        "realization_id",
        "evaluation_id",
        "prediction_sha256",
        "population",
        "lift",
        "target",
        "horizon_days",
        "treatment_arm",
        "control_arm",
        "treatment_model_id",
        "control_model_id",
        "fit_seed",
        "aggregation",
        "delta_rmse_kg",
        "ci95_lower_kg",
        "ci95_upper_kg",
        "practical_margin_kg",
        "status",
    ]
    curve_headers = [
        "study_id",
        "protocol_digest",
        "realization_id",
        "evaluation_id",
        "model_id",
        "arm",
        "fit_seed",
        "stage",
        "public_updates",
        "synthetic_updates",
        "lift",
        "target",
        "horizon_days",
        "n_entities",
        "rmse_kg",
        "mae_kg",
        "signed_bias_kg",
        "status",
    ]
    return (
        _csv_bytes(eval_headers, metric_rows),
        _csv_bytes(effect_headers, effect_rows),
        _csv_bytes(curve_headers, curve_metrics),
    )


def _visible_hash(row: dict[str, Any]) -> str:
    inputs = copy.deepcopy(row["inputs"])
    inputs.pop("entity_id", None)
    return _sha(canonical_json_bytes(inputs))


def _schedule_hash(row: dict[str, Any]) -> str:
    schedules = {lift: row["inputs"]["lifts"][lift]["history_schedule"] for lift in LIFTS}
    return _sha(canonical_json_bytes(schedules))


def _support_tables(
    fitting: dict[str, Any], protocol: dict[str, Any], realization_id: str
) -> tuple[bytes, bytes, bytes]:
    train = fitting["fitting"]
    train_by_cell: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in train:
        train_by_cell.setdefault(_cell(row), []).append(row)
    train_visible_hashes = {_visible_hash(row) for row in train}
    train_schedules = {_schedule_hash(row) for row in train}
    coverage_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    train_features = np.asarray([_features(row) for row in train], dtype=np.float64)
    feature_scale = train_features.std(axis=0)
    feature_scale[feature_scale == 0.0] = 1.0
    standardized_train = train_features / feature_scale
    train_min = standardized_train.min(axis=0)
    train_max = standardized_train.max(axis=0)
    for population in ("test_population_a", "test_population_b"):
        for plan in PLAN_NAMES:
            for horizon in HORIZONS:
                rows = [row for row in fitting[population] if _cell(row) == (plan, horizon)]
                donors = train_by_cell.get((plan, horizon), [])
                known = sum(_schedule_hash(row) in train_schedules for row in rows)
                exact_visible = sum(_visible_hash(row) in train_visible_hashes for row in rows)
                coverage_rows.append(
                    {
                        "study_id": protocol["identities"]["study_id"],
                        "protocol_digest": protocol["identities"]["protocol_digest"],
                        "realization_id": realization_id,
                        "evaluation_id": protocol["identities"]["study_evaluation_id"],
                        "model_id": "not_applicable",
                        "population": population,
                        "plan_id": plan,
                        "horizon_days": horizon,
                        "test_entities": len(rows),
                        "fitting_donors_in_cell": len(donors),
                        "test_history_schedule_signatures_seen": known,
                        "test_history_schedule_fraction_seen": known / len(rows),
                        "exact_test_training_visible_record_overlaps": exact_visible,
                        "interpretation": "finite sample coverage only; not a population-support bound",
                    }
                )
        for horizon in HORIZONS:
            rows = [
                row for row in fitting[population] if int(row["inputs"]["horizon_days"]) == horizon
            ]
            values = np.asarray([_features(row) for row in rows], dtype=np.float64)
            standardized = values / feature_scale
            outside = np.any((standardized < train_min) | (standardized > train_max), axis=1)
            distances = np.sqrt(
                np.min(
                    np.sum(
                        np.square(standardized[:, None, :] - standardized_train[None, :, :]),
                        axis=2,
                    ),
                    axis=1,
                )
            )
            geometry_rows.append(
                {
                    "study_id": protocol["identities"]["study_id"],
                    "protocol_digest": protocol["identities"]["protocol_digest"],
                    "realization_id": realization_id,
                    "evaluation_id": protocol["identities"]["study_evaluation_id"],
                    "model_id": "not_applicable",
                    "population": population,
                    "horizon_days": horizon,
                    "n_entities": len(rows),
                    "entities_outside_fitting_feature_extrema": int(np.sum(outside)),
                    "fraction_outside_fitting_feature_extrema": float(np.mean(outside)),
                    "nearest_fitting_summary_distance_median": float(np.median(distances)),
                    "nearest_fitting_summary_distance_p95": float(np.quantile(distances, 0.95)),
                    "distance": "Euclidean on 58 public summary features scaled by fitting SD",
                    "interpretation": "observed sample geometry only; not true source support",
                }
            )
    donor_ids = [row["donor_row_id"] for row in fitting["bootstrap_lineage"]]
    train_ids = {row["row_id"] for row in train}
    bootstrap_count = len(donor_ids)
    unique_donors = len(set(donor_ids))
    synthetic_summary = {
        "format": "PSR_RES292_FINITE_SUPPORT_SUMMARY_V1",
        "study_id": protocol["identities"]["study_id"],
        "protocol_digest": protocol["identities"]["protocol_digest"],
        "realization_id": realization_id,
        "evaluation_id": protocol["identities"]["study_evaluation_id"],
        "model_id": "not_applicable",
        "bootstrap_seed": 292180,
        "bootstrap_draws": bootstrap_count,
        "unique_fitting_donors": unique_donors,
        "duplicate_draw_fraction": 1.0 - unique_donors / bootstrap_count,
        "donor_copy_fraction": sum(donor in train_ids for donor in donor_ids) / bootstrap_count,
        "genuinely_novel_synthetic_rows": 0,
        "independently_generated_synthetic_truth_labels": 0,
        "pseudo_label_rows": len(fitting["pseudolabel"]),
        "cross_fitted_teacher_folds": len(fitting["teacher_fits"]),
        "bootstrap_test_exact_visible_overlap": {
            population: sum(
                _visible_hash(row) in train_visible_hashes for row in fitting[population]
            )
            for population in ("test_population_a", "test_population_b")
        },
        "synthetic_copies_are_independent_entities": False,
        "rights": "MIT",
    }
    summary_bytes = canonical_json_bytes(synthetic_summary) + b"\n"
    coverage_bytes = _csv_bytes(
        [
            "study_id",
            "protocol_digest",
            "realization_id",
            "evaluation_id",
            "model_id",
            "population",
            "plan_id",
            "horizon_days",
            "test_entities",
            "fitting_donors_in_cell",
            "test_history_schedule_signatures_seen",
            "test_history_schedule_fraction_seen",
            "exact_test_training_visible_record_overlaps",
            "interpretation",
        ],
        coverage_rows,
    )
    geometry_bytes = _csv_bytes(
        [
            "study_id",
            "protocol_digest",
            "realization_id",
            "evaluation_id",
            "model_id",
            "population",
            "horizon_days",
            "n_entities",
            "entities_outside_fitting_feature_extrema",
            "fraction_outside_fitting_feature_extrema",
            "nearest_fitting_summary_distance_median",
            "nearest_fitting_summary_distance_p95",
            "distance",
            "interpretation",
        ],
        geometry_rows,
    )
    return summary_bytes, coverage_bytes, geometry_bytes


def _source_target_discrepancy(
    fitting: dict[str, Any], protocol: dict[str, Any], realization_id: str
) -> bytes:
    sources = {
        "ORIGINAL_PUBLIC_LABEL": fitting["fitting"],
        "BOOTSTRAP_DUPLICATE_LABEL": fitting["bootstrap"],
        "SURROGATE_PSEUDO_LABEL": fitting["pseudolabel"],
    }
    rows: list[dict[str, Any]] = []
    for population in ("test_population_a", "test_population_b"):
        test = fitting[f"{population}_truth"]
        for source_name, source in sources.items():
            for horizon in HORIZONS:
                source_rows = [
                    row for row in source if int(row["inputs"]["horizon_days"]) == horizon
                ]
                truth_rows = [
                    row
                    for row in test
                    if int(
                        next(
                            item for item in fitting[population] if item["row_id"] == row["row_id"]
                        )["inputs"]["horizon_days"]
                    )
                    == horizon
                ]
                for lift_index, target in enumerate(TARGETS):
                    left = np.sort(np.asarray([row["targets"][target] for row in source_rows]))
                    right = np.sort(np.asarray([row["targets"][target] for row in truth_rows]))
                    if len(left) != len(right):
                        raise ValueError("source-target discrepancy groups are unbalanced")
                    rows.append(
                        {
                            "study_id": protocol["identities"]["study_id"],
                            "protocol_digest": protocol["identities"]["protocol_digest"],
                            "realization_id": realization_id,
                            "evaluation_id": protocol["identities"]["study_evaluation_id"],
                            "model_id": "not_applicable",
                            "population": population,
                            "source_label_provenance": source_name,
                            "lift": LIFTS[lift_index],
                            "target": target,
                            "horizon_days": horizon,
                            "source_rows": len(left),
                            "heldout_entities": len(right),
                            "source_mean_kg": float(np.mean(left)),
                            "heldout_mean_kg": float(np.mean(right)),
                            "mean_difference_kg": float(np.mean(left) - np.mean(right)),
                            "source_sd_kg": float(np.std(left)),
                            "heldout_sd_kg": float(np.std(right)),
                            "empirical_wasserstein1_kg": float(np.mean(np.abs(left - right))),
                            "interpretation": "finite-sample label discrepancy; not source-law identification",
                        }
                    )
    return _csv_bytes(
        [
            "study_id",
            "protocol_digest",
            "realization_id",
            "evaluation_id",
            "model_id",
            "population",
            "source_label_provenance",
            "lift",
            "target",
            "horizon_days",
            "source_rows",
            "heldout_entities",
            "source_mean_kg",
            "heldout_mean_kg",
            "mean_difference_kg",
            "source_sd_kg",
            "heldout_sd_kg",
            "empirical_wasserstein1_kg",
            "interpretation",
        ],
        rows,
    )


def _compute_accounting(
    fits: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    teacher_fits: list[dict[str, Any]],
    instance_ids: dict[tuple[str, int], str],
) -> bytes:
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        for seed in FIT_SEEDS:
            fit = next(
                (item for item in fits if item["arm"] == arm and item["fit_seed"] == seed),
                None,
            )
            failure = next(
                (item for item in failures if item["arm"] == arm and item["fit_seed"] == seed),
                None,
            )
            synthetic_kind, provenance = ARM_DATA[arm]
            expected_public = (
                256
                if arm == "COMPUTE_MATCHED_PUBLIC_ONLY"
                else 128
                if "public" in synthetic_kind
                else 0
            )
            expected_synthetic = 128 if provenance != "NONE" else 0
            rows.append(
                {
                    "record_type": "learner_fit",
                    "arm": arm,
                    "fit_seed": seed,
                    "status": "MODEL_FIT_FAILED" if failure else "COMPLETE",
                    "fitted_instance_id": instance_ids.get((arm, seed), ""),
                    "update_count": fit["public_updates"] + fit["synthetic_updates"]
                    if fit
                    else expected_public + expected_synthetic,
                    "public_updates": fit["public_updates"] if fit else expected_public,
                    "synthetic_updates": fit["synthetic_updates"] if fit else expected_synthetic,
                    "public_label_presentations": fit["public_row_presentations"]
                    if fit
                    else expected_public * 32,
                    "synthetic_label_presentations": fit["synthetic_row_presentations"]
                    if fit
                    else expected_synthetic * 32,
                    "total_row_presentations": (
                        fit["public_row_presentations"] + fit["synthetic_row_presentations"]
                        if fit
                        else (expected_public + expected_synthetic) * 32
                    ),
                    "parameter_count": fit["parameter_count"] if fit else 177,
                    "teacher_fits": 0,
                    "teacher_training_rows": 0,
                    "teacher_parameter_count": 0,
                    "teacher_estimated_flop_operations": 0,
                    "teacher_cost_shared_across_fit_seeds": False,
                    "compute_unit": "deterministic optimizer updates and row presentations; not elapsed time",
                }
            )
    teacher_training_rows = sum(int(row["training_rows"]) for row in teacher_fits)
    teacher_parameters = sum(int(row["parameter_count"]) for row in teacher_fits)
    dimension = 58
    per_fit_ops = 2 * 288 * dimension * dimension + dimension**3
    rows.append(
        {
            "record_type": "pseudo_label_teacher",
            "arm": "SUMMARY_RIDGE_CROSSFIT",
            "fit_seed": "",
            "status": "COMPLETE" if len(teacher_fits) == 4 else "MODEL_FIT_FAILED",
            "fitted_instance_id": ";".join(row["fitted_instance_id"] for row in teacher_fits),
            "update_count": 0,
            "public_updates": 0,
            "synthetic_updates": 0,
            "public_label_presentations": teacher_training_rows,
            "synthetic_label_presentations": 0,
            "total_row_presentations": teacher_training_rows,
            "parameter_count": 0,
            "teacher_fits": len(teacher_fits),
            "teacher_training_rows": teacher_training_rows,
            "teacher_parameter_count": teacher_parameters,
            "teacher_estimated_flop_operations": per_fit_ops * len(teacher_fits),
            "teacher_cost_shared_across_fit_seeds": True,
            "compute_unit": "approximate dense ridge solve operations; not elapsed time",
        }
    )
    return _csv_bytes(
        [
            "record_type",
            "arm",
            "fit_seed",
            "status",
            "fitted_instance_id",
            "update_count",
            "public_updates",
            "synthetic_updates",
            "public_label_presentations",
            "synthetic_label_presentations",
            "total_row_presentations",
            "parameter_count",
            "teacher_fits",
            "teacher_training_rows",
            "teacher_parameter_count",
            "teacher_estimated_flop_operations",
            "teacher_cost_shared_across_fit_seeds",
            "compute_unit",
        ],
        rows,
    )


def _read_csv(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"))))


def _status_counts(effect_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for treatment, control in CONTRASTS:
        for population in ("test_population_a", "test_population_b"):
            rows = [
                row
                for row in effect_rows
                if row["aggregation"] == "pooled_hierarchical"
                and row["treatment_arm"] == treatment
                and row["control_arm"] == control
                and row["population"] == population
            ]
            result.append(
                {
                    "treatment_arm": treatment,
                    "control_arm": control,
                    "population": population,
                    "n_target_lift_horizon_cells": len(rows),
                    "practical_benefit": sum(row["status"] == "PRACTICAL_BENEFIT" for row in rows),
                    "practical_harm": sum(row["status"] == "PRACTICAL_HARM" for row in rows),
                    "practical_equivalence": sum(
                        row["status"] == "PRACTICAL_EQUIVALENCE" for row in rows
                    ),
                    "inconclusive": sum(row["status"] == "INCONCLUSIVE" for row in rows),
                    "model_fit_failed": sum(row["status"] == "MODEL_FIT_FAILED" for row in rows),
                }
            )
    return result


def _negative_results(
    effect_csv: bytes,
    support_summary: bytes,
    protocol: dict[str, Any],
    realization_id: str,
) -> bytes:
    effects = _read_csv(effect_csv)
    support = json.loads(support_summary)
    rows: list[dict[str, Any]] = [
        {
            "finding": "Original G4 method and quantitative result",
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "evidence": LINEAGE_RELATIVE,
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "model_id": "not_applicable",
            "limit": "The public historical record contains registry metadata only; no G4 finding is invented.",
        },
        {
            "finding": "Bootstrap examples provide independent source-world information",
            "status": "NO_INDEPENDENT_INFORMATION_BY_CONSTRUCTION",
            "evidence": "finite-support-summary.json; synthetic/donor-lineage.jsonl",
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "model_id": "not_applicable",
            "limit": (
                f"{support['bootstrap_draws']} rows copy {support['unique_fitting_donors']} unique "
                "public donors; duplicates do not add source-world information."
            ),
        },
        {
            "finding": "Genuinely novel synthetic records with independently generated truth labels",
            "status": "NOT_EXECUTED_BY_PROTOCOL",
            "evidence": "protocol.json; formal-specification.md",
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "model_id": "not_applicable",
            "limit": "The public empirical resampler copies donor records; no source equations are used as learner truth.",
        },
        {
            "finding": "Source-system identification or structural equivalence",
            "status": "NOT_ESTIMATED",
            "evidence": "formal-specification.md",
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "model_id": "not_applicable",
            "limit": "Predictive results do not establish recovery of the generating mechanism.",
        },
        {
            "finding": "Real-athlete transfer or causal training effect",
            "status": "NOT_EVALUATED",
            "evidence": "formal-specification.md",
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "model_id": "not_applicable",
            "limit": "All held-out rows are synthetic draws from the public-native source distribution.",
        },
    ]
    for row in effects:
        if row["aggregation"] != "pooled_hierarchical":
            continue
        rows.append(
            {
                "finding": (
                    f"Paired transfer {row['treatment_arm']} minus {row['control_arm']} "
                    f"for {row['population']}, {row['lift']}, {row['horizon_days']} days"
                ),
                "status": row["status"],
                "evidence": "paired-transfer-effects.csv",
                "protocol_digest": row["protocol_digest"],
                "realization_id": row["realization_id"],
                "model_id": f"{row['treatment_model_id']} | {row['control_model_id']}",
                "estimate_delta_rmse_kg": row["delta_rmse_kg"],
                "ci95_lower_kg": row["ci95_lower_kg"],
                "ci95_upper_kg": row["ci95_upper_kg"],
                "limit": (
                    "This finite-sample status applies only to the declared cell; an inconclusive "
                    "or nonbeneficial cell does not show that all synthetic pretraining is ineffective."
                ),
            }
        )
    return _csv_bytes(
        [
            "finding",
            "status",
            "evidence",
            "protocol_digest",
            "realization_id",
            "model_id",
            "estimate_delta_rmse_kg",
            "ci95_lower_kg",
            "ci95_upper_kg",
            "limit",
        ],
        rows,
    )


def _claims(
    metric_csv: bytes,
    effect_csv: bytes,
    support_summary: bytes,
    discrepancy_csv: bytes,
    compute_csv: bytes,
    protocol: dict[str, Any],
    realization_id: str,
    instance_rows: list[dict[str, Any]],
) -> bytes:
    ids_by_arm: dict[str, list[str]] = {}
    for item in instance_rows:
        ids_by_arm.setdefault(item["arm"], []).append(item["fitted_instance_id"])
    effect_rows = _read_csv(effect_csv)
    primary_rows = [
        row
        for row in effect_rows
        if row["aggregation"] == "pooled_hierarchical"
        and row["treatment_arm"]
        in {
            "SYNTHETIC_ONLY_BOOTSTRAP",
            "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP",
        }
    ]
    claims = [
        {
            "claim_id": "HISTORICAL_G4_EVIDENCE",
            "claim": "Historical G4 findings are recovered only as metadata, not as scientific results.",
            "quantitative": False,
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "source_artifact": LINEAGE_RELATIVE,
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": "not_applicable",
        },
        {
            "claim_id": "PREDICTIVE_UTILITY_AND_SYNTHETIC_ONLY_LEARNING",
            "claim": "Per-arm errors for all predeclared target, lift, horizon, population, and fitting-seed cells.",
            "quantitative": True,
            "source_artifact": "evaluation-results.csv",
            "source_sha256": "sha256:" + _sha(metric_csv),
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": ids_by_arm,
        },
        {
            "claim_id": "PRETRAINING_INCREMENTAL_VALUE_AND_COMPUTE_MATCH",
            "claim": "Paired bootstrap transfer contrasts versus equal-public-label and equal-update public-only controls.",
            "quantitative": True,
            "source_artifact": "paired-transfer-effects.csv",
            "source_sha256": "sha256:" + _sha(effect_csv),
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": {
                "treatment": ids_by_arm.get("SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP", []),
                "public_only": ids_by_arm.get("PUBLIC_ONLY", []),
                "compute_matched_public_only": ids_by_arm.get("COMPUTE_MATCHED_PUBLIC_ONLY", []),
            },
            "cell_count": len(primary_rows),
            "decision_rule": "predeclared ±1.0 kg practical RMSE margin; INCONCLUSIVE preserved",
        },
        {
            "claim_id": "FINITE_SUPPORT_AND_MEMORIZATION",
            "claim": "Donor duplication and finite-sample support diagnostics; no donor copies counted as independent entities.",
            "quantitative": True,
            "source_artifact": "finite-support-summary.json",
            "source_sha256": "sha256:" + _sha(support_summary),
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": "not_applicable",
        },
        {
            "claim_id": "SOURCE_TARGET_DISTRIBUTION_MISMATCH",
            "claim": "Finite-sample label discrepancies between training/synthetic sources and held-out target rows.",
            "quantitative": True,
            "source_artifact": "source-target-discrepancy.csv",
            "source_sha256": "sha256:" + _sha(discrepancy_csv),
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": "not_applicable",
        },
        {
            "claim_id": "COMPUTE_AND_PARAMETER_COUNTS",
            "claim": "Fixed optimizer updates, label presentations, parameter counts, and separately counted pseudo-label teacher fits.",
            "quantitative": True,
            "source_artifact": "compute-accounting.csv",
            "source_sha256": "sha256:" + _sha(compute_csv),
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "model_identity": ids_by_arm,
        },
    ]
    return (
        canonical_json_bytes(
            {
                "format": "PSR_RES292_CLAIM_BINDINGS_V1",
                "study_id": protocol["identities"]["study_id"],
                "protocol_digest": protocol["identities"]["protocol_digest"],
                "realization_id": realization_id,
                "evaluation_id": protocol["identities"]["study_evaluation_id"],
                "claims": claims,
            }
        )
        + b"\n"
    )


def _paired_effects_svg(effect_csv: bytes) -> bytes:
    rows = [
        row
        for row in _read_csv(effect_csv)
        if row["aggregation"] == "pooled_hierarchical"
        and row["treatment_arm"] == "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP"
        and row["control_arm"] in {"PUBLIC_ONLY", "COMPUTE_MATCHED_PUBLIC_ONLY"}
    ]
    rows.sort(
        key=lambda row: (
            row["population"],
            row["control_arm"],
            row["lift"],
            int(row["horizon_days"]),
        )
    )
    width = 1040
    top = 78
    row_height = 20
    height = top + row_height * len(rows) + 44
    values = [
        abs(float(row[key]))
        for row in rows
        for key in ("delta_rmse_kg", "ci95_lower_kg", "ci95_upper_kg")
        if row[key]
    ]
    bound = max(2.0, math.ceil(max(values, default=2.0) / 2.0) * 2.0)
    left = 320
    plot_width = 640

    def x_coordinate(value: float) -> float:
        return left + (value + bound) * plot_width / (2.0 * bound)

    def xml_escape(value: str) -> str:
        return escape(value)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#18212f}.axis{stroke:#64748b;stroke-width:1}.ci{stroke-width:3}.zero{stroke:#111827;stroke-dasharray:4 4}.margin{stroke:#94a3b8;stroke-dasharray:3 4}</style>",
        '<text x="24" y="30" font-size="18" font-weight="700">Bootstrap pretraining plus public fine-tuning</text>',
        '<text x="24" y="52" font-size="12">Paired delta RMSE (treatment − control), kg; hierarchical 95% entity/seed interval</text>',
        f'<line class="axis" x1="{left}" y1="64" x2="{left + plot_width}" y2="64"/>',
    ]
    for tick in np.linspace(-bound, bound, 5):
        xpos = x_coordinate(float(tick))
        parts.append(
            f'<line class="axis" x1="{xpos:.1f}" y1="64" x2="{xpos:.1f}" y2="{height - 24}"/>'
        )
        parts.append(
            f'<text x="{xpos:.1f}" y="60" text-anchor="middle" font-size="10">{tick:.0f}</text>'
        )
    parts.append(
        f'<line class="zero" x1="{x_coordinate(0):.1f}" y1="64" '
        f'x2="{x_coordinate(0):.1f}" y2="{height - 24}"/>'
    )
    parts.append(
        f'<line class="margin" x1="{x_coordinate(-1):.1f}" y1="64" '
        f'x2="{x_coordinate(-1):.1f}" y2="{height - 24}"/>'
    )
    parts.append(
        f'<line class="margin" x1="{x_coordinate(1):.1f}" y1="64" '
        f'x2="{x_coordinate(1):.1f}" y2="{height - 24}"/>'
    )
    for index, row in enumerate(rows):
        y = top + index * row_height
        label = (
            f"{row['population'].replace('test_population_', 'test ')} · "
            f"{'equal updates' if row['control_arm'] == 'COMPUTE_MATCHED_PUBLIC_ONLY' else 'equal public labels'} · "
            f"{row['lift']} · {row['horizon_days']}d"
        )
        if not row["delta_rmse_kg"]:
            parts.append(f'<text x="20" y="{y + 4}" font-size="10">{xml_escape(label)}</text>')
            parts.append(
                f'<text x="{left + plot_width + 8}" y="{y + 4}" font-size="9">'
                f"{xml_escape(row['status'])}</text>"
            )
            continue
        color = "#b45309" if row["status"] == "PRACTICAL_HARM" else "#176b87"
        x1, x2 = (
            x_coordinate(float(row["ci95_lower_kg"])),
            x_coordinate(float(row["ci95_upper_kg"])),
        )
        estimate = x_coordinate(float(row["delta_rmse_kg"]))
        parts.append(f'<text x="20" y="{y + 4}" font-size="10">{xml_escape(label)}</text>')
        parts.append(
            f'<line class="ci" stroke="{color}" x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}"/>'
        )
        parts.append(f'<circle cx="{estimate:.1f}" cy="{y}" r="3.5" fill="{color}"/>')
        parts.append(
            f'<text x="{left + plot_width + 8}" y="{y + 4}" font-size="9">'
            f"{xml_escape(row['status'])}</text>"
        )
    parts.append("</svg>\n")
    return "".join(parts).encode("utf-8")


def _finite_support_svg(support_summary: bytes) -> bytes:
    summary = json.loads(support_summary)
    count = int(summary["bootstrap_draws"])
    values = [
        ("Original fitting rows", count),
        ("Bootstrap rows", int(summary["bootstrap_draws"])),
        ("Unique donors", int(summary["unique_fitting_donors"])),
        ("Duplicate draws", count - int(summary["unique_fitting_donors"])),
        ("Novel generated rows", int(summary["genuinely_novel_synthetic_rows"])),
    ]
    width, height = 720, 240
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#18212f}.bar{fill:#176b87}</style>",
        '<text x="24" y="30" font-size="18" font-weight="700">Finite donor support in bootstrap pretraining</text>',
        f'<text x="24" y="51" font-size="11">Row counts; donor copies are dependent observations (n={count} synthetic draws)</text>',
    ]
    max_count = max(count, 1)
    for index, (label, value) in enumerate(values):
        y = 76 + index * 31
        bar_width = 400 * value / max_count
        parts.append(f'<text x="24" y="{y + 14}" font-size="11">{escape(label)}</text>')
        parts.append(
            f'<rect class="bar" x="205" y="{y}" width="{bar_width:.1f}" height="18" rx="2"/>'
        )
        parts.append(f'<text x="{215 + bar_width:.1f}" y="{y + 14}" font-size="11">{value}</text>')
    parts.append("</svg>\n")
    return "".join(parts).encode("utf-8")


def _report_bytes(
    protocol: dict[str, Any],
    realization_id: str,
    realization_digest: str,
    support_summary: bytes,
    metric_csv: bytes,
    effect_csv: bytes,
    compute_csv: bytes,
    failures: list[dict[str, Any]],
) -> bytes:
    metrics = _read_csv(metric_csv)
    effects = _read_csv(effect_csv)
    support = json.loads(support_summary)
    summaries = _status_counts(effects)
    primary = [
        row
        for row in effects
        if row["aggregation"] == "pooled_hierarchical"
        and row["treatment_arm"] == "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP"
        and row["control_arm"] in {"PUBLIC_ONLY", "COMPUTE_MATCHED_PUBLIC_ONLY"}
    ]
    primary.sort(
        key=lambda row: (
            row["population"],
            row["control_arm"],
            row["lift"],
            int(row["horizon_days"]),
        )
    )
    synthetic_only = [
        row
        for row in metrics
        if row["arm"]
        in {
            "PUBLIC_ONLY",
            "SYNTHETIC_ONLY_BOOTSTRAP",
            "SYNTHETIC_ONLY_PSEUDOLABEL",
        }
        and row["status"] == "COMPLETE"
    ]
    groups: dict[tuple[str, str, str, str, str], list[float]] = {}
    for row in synthetic_only:
        key = (
            row["population"],
            row["lift"],
            row["target"],
            row["horizon_days"],
            row["arm"],
        )
        groups.setdefault(key, []).append(float(row["rmse_kg"]))
    keys = sorted({key[:4] for key in groups})
    perf_lines = [
        "| Population | Lift | Horizon | Public only | Bootstrap only | Pseudo-label only |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for population, lift, target, horizon in keys:
        cells = []
        for arm in (
            "PUBLIC_ONLY",
            "SYNTHETIC_ONLY_BOOTSTRAP",
            "SYNTHETIC_ONLY_PSEUDOLABEL",
        ):
            values = groups.get((population, lift, target, horizon, arm), [])
            cells.append(
                f"{np.mean(values):.3f} ({min(values):.3f}–{max(values):.3f})"
                if values
                else "MODEL_FIT_FAILED"
            )
        perf_lines.append(
            f"| {population} | {lift} | {horizon} days | {cells[0]} | {cells[1]} | {cells[2]} |"
        )
    status_lines = [
        "| Contrast (treatment − control) | Population | Benefit | Harm | Equivalent | Inconclusive | Fit failed |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        if row["treatment_arm"] not in {
            "SYNTHETIC_ONLY_BOOTSTRAP",
            "SYNTHETIC_ONLY_PSEUDOLABEL",
            "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP",
            "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL",
        }:
            continue
        status_lines.append(
            "| "
            + f"{row['treatment_arm']} − {row['control_arm']} | {row['population']} | "
            + f"{row['practical_benefit']} | {row['practical_harm']} | "
            + f"{row['practical_equivalence']} | {row['inconclusive']} | "
            + f"{row['model_fit_failed']} |"
        )
    effect_lines = [
        "| Population | Control | Lift | Horizon | Δ RMSE, kg | Hierarchical 95% interval, kg | Status |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in primary:
        estimate = f"{float(row['delta_rmse_kg']):.3f}" if row["delta_rmse_kg"] else "—"
        interval = (
            f"[{float(row['ci95_lower_kg']):.3f}, {float(row['ci95_upper_kg']):.3f}]"
            if row["ci95_lower_kg"] and row["ci95_upper_kg"]
            else "—"
        )
        effect_lines.append(
            f"| {row['population']} | {row['control_arm']} | {row['lift']} | "
            f"{row['horizon_days']} | {estimate} | {interval} | "
            f"{row['status']} |"
        )
    if failures:
        failure_table = "\n".join(
            f"| {item['arm']} | {item['fit_seed']} | {item['status']} | {escape(item['failure'])} |"
            for item in failures
        )
    else:
        failure_table = "| None | — | NO_FIT_FAILURES | All frozen learner fits completed. |"
    text = f"""# Synthetic pretraining transfer: RES-292

Study: {protocol["identities"]["study_id"]}<br>
Protocol digest: {protocol["identities"]["protocol_digest"]}<br>
Dataset realization: {realization_id}<br>
Realization digest: {realization_digest}<br>
Evaluation: {protocol["identities"]["study_evaluation_id"]}<br>
Classification: NEW_PUBLIC_NATIVE_EXPERIMENT

This study executes Linear RES-292 as a new experiment. Historical G4 / ALI-544
survives as study metadata and aliases; no original G4 method, model, score,
report, or negative result was recovered. Nothing in this report is attributed
to historical G4. See [historical lineage](../../../studies/synthetic_pretraining_transfer/historical-lineage.md)
and the frozen [protocol](../../../studies/synthetic_pretraining_transfer/protocol.json).

## Scope and information boundary

Here “real” means a held-out row from the public-native synthetic benchmark's
original generating distribution. The test populations are synthetic; this is
not real-athlete transfer. The learner receives only authorized fitting
records and unlabeled development/test inputs. Evaluation targets, source
equations, latent states, population coordinates, exact parameter bounds,
private material, and authority-only keys stay outside the learner. Prediction
bytes were sealed before the authority joined test truth. The firewall audit,
payload digests, and exact source hashes are in
[learner-input-audit.json](learner-input-audit.json).

Fitting, development, test A, and test B each use independent population,
intervention, observation, and split seeds and disjoint opaque entity IDs.
There are 384 public fitting rows, 192 development rows, and two independent
384-row test populations, balanced over four plans and three horizons. The
fitting rows have three lift-specific targets in kg. Development predictions
are learning-curve checks only; they do not select hyperparameters or stopping
points.

## Synthetic label provenance

The empirical bootstrap drew {support["bootstrap_draws"]} complete records from
{support["unique_fitting_donors"]} unique public fitting donors. Its duplicate
draw fraction is {support["duplicate_draw_fraction"]:.3f}; the exact donor-copy
fraction is {support["donor_copy_fraction"]:.3f}. Bootstrap targets are
BOOTSTRAP_DUPLICATE_LABEL values copied with their donor rows. The separate
SURROGATE_PSEUDO_LABEL rows copy donor inputs and use cross-fitted Summary Ridge
predictions. ORIGINAL_PUBLIC_LABEL values remain attached to the original
training rows. Pseudo-labels are conditional model predictions, not source
truth. The study generated no novel participant rows and no independently
generated source-truth labels.

![Finite donor support](finite-support.svg)

Exact donor lineage, teacher folds and coefficients, per-target label
provenance, and duplicate counts are in [donor-lineage.jsonl](synthetic/donor-lineage.jsonl),
[teacher-crossfit.jsonl](synthetic/teacher-crossfit.jsonl), and
[training-label-provenance.csv](synthetic/training-label-provenance.csv).
Held-out sample-extrema and nearest-donor metrics are in
[sample-geometry.csv](sample-geometry.csv) and
[support-coverage.csv](support-coverage.csv). They describe this finite
realization and do not estimate population bounds.

## Frozen arms and compute controls

Every arm uses the same fixed 58-input, three-output linear model with 177
parameters, initialization, optimizer, feature map, 32-row batches, and
learning rate. The six declared arms separate donor-copy labels from surrogate
pseudo-labels. PUBLIC_ONLY and each fine-tuning phase expose the same 4,096
public row-label presentations. COMPUTE_MATCHED_PUBLIC_ONLY uses the same 256
optimizer updates and 8,192 total row presentations as bootstrap pretraining
plus fine-tuning, but spends them on public rows. This gives a public-label
exposure-matched contrast and a separate update-matched contrast. Teacher-fit
work is counted separately for pseudo-label arms.

Exact per-seed learner states and instance IDs are in
[fitted-models.json](fitted-models.json) and
[fitted-instance-identities.json](fitted-instance-identities.json).
[Compute accounting](compute-accounting.csv) records every update, row
presentation, teacher fit, parameter count, and failed fit. The
[development learning curves](development-learning-curves.csv) retain each
arm, target, lift, horizon, and training seed.

## Predictive utility and transfer

Metrics are RMSE, MAE, and signed bias in kg, reported separately by arm,
population, lift, horizon, and fitting seed. The complete cell-level table is
[evaluation-results.csv](evaluation-results.csv); exact sealed predictions
are [predictions.jsonl](predictions.jsonl). Five fitting seeds are retained.
No score is pooled across lifts, targets, or horizons in the primary results.
The following compact table shows direct-public, donor-bootstrap-only, and
pseudo-label-only RMSE as the mean and range across the five fitting seeds for
each target/lift/horizon. The pseudo-label-only student sees copied inputs and
surrogate predictions derived from public training labels; it is not an
independent synthetic-only label source. Per-seed rows remain in the results table.

{chr(10).join(perf_lines)}

Paired uncertainty resamples held-out entities within each plan and horizon,
using the same sampled entities for both arms. The pooled interval first
resamples fitting seeds and then entities. The practical RMSE margin was fixed
at ±1.0 kg before fitting. An interval wholly below −1.0 kg is
PRACTICAL_BENEFIT; wholly above +1.0 kg is PRACTICAL_HARM; wholly within the
margin is PRACTICAL_EQUIVALENCE; other cells remain INCONCLUSIVE.

Status counts below summarize the 18 predeclared lift/horizon cells per
population; they are a count of resolved cells, not a universal leaderboard.
The full per-seed and pooled contrasts, including pseudo-label arms, are in
[paired-transfer-effects.csv](paired-transfer-effects.csv).

{chr(10).join(status_lines)}

| Test population | Control | Lift | Horizon | Δ RMSE, kg | Hierarchical 95% interval, kg | Status |
| --- | --- | --- | ---: | ---: | --- | --- |
{chr(10).join(effect_lines[2:])}

![Paired bootstrap transfer effects](paired-transfer-effects.svg)

## Negative and inconclusive findings

[Negative-results.csv](negative-results.csv) preserves the historical evidence
limit, every paired cell state, finite-support interpretation, and prohibited
claims. A resolved or inconclusive result applies only to this frozen learner,
realization, and target cell. Repeated public donors do not add independent
information about the source world. A transfer gain over PUBLIC_ONLY alone
does not show incremental value beyond additional public optimization; the
compute-matched contrast is reported separately. A lack of observed benefit
does not establish that all synthetic pretraining is ineffective.

Source-to-target label distribution discrepancies are in
[source-target-discrepancy.csv](source-target-discrepancy.csv). They compare
finite training/synthetic rows with same-law held-out entities by population,
lift, and horizon; they do not prove source-system recovery or structural
equivalence.

| Arm | Fit seed | Status | Failure |
| --- | ---: | --- | --- |
{failure_table}

No causal training effect, real-athlete transfer, or source-system
identification is claimed.

## Reproduction, claims, and rights

Replay the frozen realization, learner runs, tables, figures, report, and
hashes from the repository root:

    uv run --locked python -m powerlifting_state_research.studies.synthetic_pretraining_transfer
    uv run --locked python -m powerlifting_state_research.studies.synthetic_pretraining_transfer --check

[claims.json](claims.json) binds each quantitative claim family to source
artifacts, protocol digest, realization, evaluation identity, and fitted
instance identities. [manifest.json](manifest.json),
[artifact-manifest.json](artifact-manifest.json), and
[SHA256SUMS.txt](SHA256SUMS.txt) contain the artifact and checksum indexes.
New code and machine-readable results are MIT; authored prose and this report
are CC BY 4.0. No private historical artifact was used.

## RES-293 handoff

RES-292 hands off a new, same-distribution synthetic study with donor-copy and
cross-fitted pseudo-label treatments. A later RES-293 may ask whether a
separately specified synthetic source with genuinely novel support and
authorized labels adds predictive value under the same public-label and
compute controls. It must freeze its generator, label authority, targets,
splits, and practical margin before fitting. This handoff does not execute
RES-293 and does not change RES-293 or RES-294.
"""
    return text.encode("utf-8")


def _res293_handoff(
    protocol: dict[str, Any],
    realization_id: str,
    effect_csv: bytes,
    support_summary: bytes,
) -> bytes:
    effects = _status_counts(_read_csv(effect_csv))
    support = json.loads(support_summary)
    primary = [
        row
        for row in effects
        if row["treatment_arm"] == "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP"
    ]
    lines = [
        "| Contrast | Population | Benefit cells | Harm cells | Equivalent cells | Inconclusive cells |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        lines.append(
            f"| {row['treatment_arm']} − {row['control_arm']} | {row['population']} | "
            f"{row['practical_benefit']} | {row['practical_harm']} | "
            f"{row['practical_equivalence']} | {row['inconclusive']} |"
        )
    text = f"""# RES-293 scientific handoff

RES-292 is a separate NEW_PUBLIC_NATIVE_EXPERIMENT, not a recovery of the
historical G4 result. Its protocol is {protocol["identities"]["study_id"]}
with digest {protocol["identities"]["protocol_digest"]}. The new realization
is {realization_id}.

## Evidence handed off

- {support["bootstrap_draws"]} empirical bootstrap records were drawn from
  {support["unique_fitting_donors"]} unique public fitting donors
  (duplicate fraction {support["duplicate_draw_fraction"]:.3f}). These copies
  contain BOOTSTRAP_DUPLICATE_LABEL values and are not independent entities.
- A separate donor-copy dataset carries cross-fitted Summary Ridge predictions
  labeled SURROGATE_PSEUDO_LABEL. Those are conditional predictions; they are
  not generating-distribution truth. No novel source-supported rows or
  independently generated source-truth labels were created.
- ORIGINAL_PUBLIC_LABEL rows, held-out truths, donor mappings, and teacher
  folds are retained as distinct artifacts. The learner firewall sealed
  predictions before test scoring.
- Per-seed and pooled entity-paired effects, fit identities, target-wise
  metrics, learning curves, and update/data-exposure accounting are in the
  linked study report and artifact manifest.

The predeclared bootstrap transfer status counts are:

{chr(10).join(lines)}

See [the RES-292 report](report.md),
[paired-transfer-effects.csv](paired-transfer-effects.csv),
[evaluation-results.csv](evaluation-results.csv),
[finite-support-summary.json](finite-support-summary.json), and
[compute-accounting.csv](compute-accounting.csv) for the bound evidence.
The issue's result remains conditional on this fixed learner, support,
realization, and practical margin. A positive result against PUBLIC_ONLY alone
does not establish benefit beyond the compute-matched public-only arm. An
inconclusive or nonbeneficial result does not establish that every synthetic
pretraining method is ineffective.

## Open question for RES-293

If RES-293 tests a source with genuinely novel synthetic support, it must
identify the authorized source of every synthetic label, freeze support and
target-generation rules before fitting, and preserve independent held-out
populations. It should reuse equal-public-label and equal-compute controls,
entity-clustered paired uncertainty, and explicit distinctions between
predictive utility, source-target mismatch, source identification, causal
effects, and real-athlete transfer. This file is a handoff only. RES-293 and
RES-294 remain unchanged, and this handoff executes neither issue.
"""
    return text.encode("utf-8")


def _artifact_manifest(files: dict[str, bytes], protocol: dict[str, Any]) -> bytes:
    study_id = protocol["identities"]["study_id"]
    artifacts: list[dict[str, Any]] = []
    for path, content in sorted(files.items()):
        suffix = Path(path).suffix
        digest = _sha(content)
        slug = path.lower().replace("/", "-").replace(".", "-")
        artifact = ArtifactManifest(
            artifact_id=f"psr:artifact:res292-{slug}@1.0.0~{digest[:12]}",
            artifact_kind={
                ".jsonl": "application/x-ndjson",
                ".csv": "text/csv",
                ".svg": "image/svg+xml",
                ".md": "text/markdown",
                ".json": "application/json",
            }.get(suffix, "text/plain"),
            license_expression="CC-BY-4.0" if suffix == ".md" else "MIT",
            copyright_holder="Powerlifting State Research contributors",
            origin_class="GENERATED_PUBLIC_ARTIFACT",
            source_reference=study_id,
            sha256=digest,
            redistribution_status=(
                "New public-native synthetic or derived RES-292 artifact; redistribute under its "
                f"listed license. Role: {'evaluation-authority-only' if 'truth' in path else 'public-study-output'}."
            ),
            access_conditions=None,
            generated_at=None,
            tool_identity=study_id,
        )
        artifacts.append(
            {
                "path": path,
                **asdict(artifact),
            }
        )
    return (
        canonical_json_bytes(
            {
                "format": "PSR_RES292_ARTIFACT_MANIFEST_V1",
                "study_id": study_id,
                "protocol_digest": protocol["identities"]["protocol_digest"],
                "manifest_exclusions": [
                    "artifact-manifest.json",
                    "manifest.json",
                    "SHA256SUMS.txt",
                ],
                "artifacts": artifacts,
            }
        )
        + b"\n"
    )


def _source_hashes(root: Path) -> dict[str, str]:
    paths = (
        PROTOCOL_RELATIVE,
        FROZEN_RELATIVE,
        FORMAL_RELATIVE,
        LINEAGE_RELATIVE,
        LEARNER_RELATIVE,
        EVALUATOR_RELATIVE,
        *PUBLIC_SOURCE_PATHS,
        "src/powerlifting_state_research/studies/registry.py",
        "src/powerlifting_state_research/provenance/historical_sources.py",
        "artifacts/registries/benchmark-registry.json",
        "studies/synthetic_pretraining_transfer/README.md",
        "results/studies/synthetic_pretraining_transfer/README.md",
    )
    return {path: "sha256:" + _sha((root / path).read_bytes()) for path in sorted(set(paths))}


def _protocol_freeze_commit(root: Path) -> str:
    commits = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", "--", PROTOCOL_RELATIVE],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    if not commits:
        raise ValueError("the frozen protocol has no committed freeze point")
    return commits[0]


def _build_output_files(root: Path) -> dict[str, bytes]:
    protocol = verify_design(root)
    fitting = _build_inputs(protocol)
    files = _data_artifacts(fitting)
    realization_bytes, realization_id, realization_digest = _realization_manifest(
        protocol, files, fitting
    )
    files["dataset-realization.json"] = realization_bytes
    data_hashes = {path: "sha256:" + _sha(content) for path, content in files.items()}
    fits, raw_predictions, curve_predictions, audits, failures = _run_all_arms(
        root, protocol, fitting
    )
    learner_source = (root / LEARNER_RELATIVE).read_bytes()
    instances, instance_ids = _fitted_instances(
        fits,
        data_hashes,
        protocol,
        realization_id,
        "sha256:" + _sha(learner_source),
    )
    prediction_rows, prediction_bytes, prediction_sha = _sealed_predictions(
        raw_predictions,
        instance_ids,
        protocol,
        realization_id,
    )
    for audit in audits:
        audit.update(
            {
                "study_id": protocol["identities"]["study_id"],
                "protocol_digest": protocol["identities"]["protocol_digest"],
                "realization_id": realization_id,
                "evaluation_id": protocol["identities"]["study_evaluation_id"],
                "sealed_prediction_sha256": prediction_sha,
            }
        )
    metric_csv, effect_csv, curve_csv = _evaluation_tables(
        prediction_rows,
        curve_predictions,
        fitting,
        instance_ids,
        protocol,
        realization_id,
        prediction_sha,
    )
    support_summary, coverage_csv, geometry_csv = _support_tables(fitting, protocol, realization_id)
    discrepancy_csv = _source_target_discrepancy(fitting, protocol, realization_id)
    compute_csv = _compute_accounting(fits, failures, fitting["teacher_fits"], instance_ids)
    negative_csv = _negative_results(effect_csv, support_summary, protocol, realization_id)
    claims_bytes = _claims(
        metric_csv,
        effect_csv,
        support_summary,
        discrepancy_csv,
        compute_csv,
        protocol,
        realization_id,
        instances,
    )
    teacher_identities = [
        {
            "fitted_instance_id": row["fitted_instance_id"],
            "study_id": protocol["identities"]["study_id"],
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "realization_id": realization_id,
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
            "fold": row["fold"],
            "alpha": row["alpha"],
            "training_rows": row["training_rows"],
            "heldout_rows": row["heldout_rows"],
            "parameter_count": row["parameter_count"],
            "state_sha256": row["state_sha256"],
            "label_source": "cross-fitted public training labels",
        }
        for row in fitting["teacher_fits"]
    ]
    files.update(
        {
            "finite-support-summary.json": support_summary,
            "support-coverage.csv": coverage_csv,
            "sample-geometry.csv": geometry_csv,
            "source-target-discrepancy.csv": discrepancy_csv,
            "predictions.jsonl": prediction_bytes,
            "evaluation-results.csv": metric_csv,
            "paired-transfer-effects.csv": effect_csv,
            "development-learning-curves.csv": curve_csv,
            "compute-accounting.csv": compute_csv,
            "negative-results.csv": negative_csv,
            "claims.json": claims_bytes,
            "learner-input-audit.json": canonical_json_bytes(audits) + b"\n",
            "method-failures.json": canonical_json_bytes(failures) + b"\n",
            "fitted-models.json": canonical_json_bytes(
                [
                    {
                        **identity,
                        "state": fit["weights"],
                        "public_updates": fit["public_updates"],
                        "synthetic_updates": fit["synthetic_updates"],
                        "public_row_presentations": fit["public_row_presentations"],
                        "synthetic_row_presentations": fit["synthetic_row_presentations"],
                    }
                    for identity in instances
                    for fit in fits
                    if identity["arm"] == fit["arm"] and identity["fit_seed"] == fit["fit_seed"]
                ]
            )
            + b"\n",
            "fitted-instance-identities.json": canonical_json_bytes(instances) + b"\n",
            "teacher-fitted-instance-identities.json": canonical_json_bytes(teacher_identities)
            + b"\n",
            "paired-transfer-effects.svg": _paired_effects_svg(effect_csv),
            "finite-support.svg": _finite_support_svg(support_summary),
            "RES-293-handoff.md": _res293_handoff(
                protocol, realization_id, effect_csv, support_summary
            ),
        }
    )
    files["report.md"] = _report_bytes(
        protocol,
        realization_id,
        realization_digest,
        support_summary,
        metric_csv,
        effect_csv,
        compute_csv,
        failures,
    )
    sources = _source_hashes(root)
    model_state_sha = "sha256:" + _sha(files["fitted-models.json"])
    artifact_manifest = _artifact_manifest(files, protocol)
    files["artifact-manifest.json"] = artifact_manifest
    checksum_paths = sorted(path for path in files if path not in {"SHA256SUMS.txt"})
    files["SHA256SUMS.txt"] = "".join(
        f"{_sha(files[path])}  {path}\n" for path in checksum_paths
    ).encode("utf-8")
    output_hashes = {path: "sha256:" + _sha(content) for path, content in sorted(files.items())}
    manifest = {
        "format": "PSR_RES292_PUBLIC_NATIVE_TRANSFER_MANIFEST_V1",
        "study": {
            "classification": "NEW_PUBLIC_NATIVE_EXPERIMENT",
            "historical_aliases": protocol["identities"]["historical_aliases"],
            "study_id": protocol["identities"]["study_id"],
            "protocol_digest": protocol["identities"]["protocol_digest"],
            "evaluation_id": protocol["identities"]["study_evaluation_id"],
        },
        "starting_main": EXPECTED_STARTING_MAIN,
        "protocol_frozen_before_fit": True,
        "protocol_freeze_commit": _protocol_freeze_commit(root),
        "dataset_realization": {
            "realization_id": realization_id,
            "realization_digest": realization_digest,
            "manifest_sha256": "sha256:" + _sha(realization_bytes),
            "evaluation_truth_separate_from_learner_payload": True,
        },
        "source_hashes": sources,
        "input_artifact_sha256": data_hashes,
        "learner": {
            "source_sha256": "sha256:" + _sha(learner_source),
            "input_firewall_passed": all(audit["passed"] for audit in audits),
            "prediction_seal_sha256": prediction_sha,
            "fit_failure_count": len(failures),
            "fitted_instance_count": len(instances),
            "fitted_state_artifact_sha256": model_state_sha,
        },
        "fitted_instances": instances,
        "teacher_fitted_instances": teacher_identities,
        "rights": {
            "dataset_license": "MIT",
            "machine_readable_outputs_license": "MIT",
            "prose_license": "CC-BY-4.0",
            "historical_private_artifacts_used": False,
            "access_conditions": None,
        },
        "checksum_index": "SHA256SUMS.txt",
        "manifest_exclusions": ["manifest.json"],
        "outputs": output_hashes,
    }
    files["manifest.json"] = canonical_json_bytes(manifest) + b"\n"
    return files


def _output_directory(root: Path) -> Path:
    return root / OUTPUT_RELATIVE


def _write_output_atomically(root: Path, files: dict[str, bytes]) -> Path:
    destination = _output_directory(root)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite immutable RES-292 results: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".res292-synthetic-transfer-", dir=destination.parent))
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
    stored_manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    actual = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    expected = stored_manifest["outputs"]
    actual_hashes = {
        path: "sha256:" + _sha(data)
        for path, data in sorted(actual.items())
        if path != "manifest.json"
    }
    if actual_hashes != expected:
        raise ValueError("RES-292 output manifest does not match artifact bytes")
    checksum_rows = {
        line.split("  ", maxsplit=1)[1]: "sha256:" + line.split("  ", maxsplit=1)[0]
        for line in actual["SHA256SUMS.txt"].decode("utf-8").splitlines()
    }
    checksum_expected = {
        path: digest
        for path, digest in actual_hashes.items()
        if path not in {"SHA256SUMS.txt", "manifest.json"}
    }
    if checksum_rows != checksum_expected:
        raise ValueError("RES-292 checksum index is incomplete or invalid")
    rebuilt = _build_output_files(root)
    if rebuilt != actual:
        mismatches = sorted(
            path for path in set(rebuilt) | set(actual) if rebuilt.get(path) != actual.get(path)
        )
        raise ValueError(f"RES-292 deterministic replay mismatch: {mismatches[:10]}")
    print(
        "PASS: RES-292 protocol, upstream frozen evidence, learner firewall, "
        f"{len(actual)} artifacts, hashes, and deterministic replay"
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    if sys.argv[1:] in (["--check"], ["--check-report"]):
        check_outputs(root)
        return
    if sys.argv[1:]:
        raise SystemExit(
            "usage: python -m powerlifting_state_research.studies.synthetic_pretraining_transfer "
            "[--check|--check-report]"
        )
    protocol = verify_design(root)
    destination = _output_directory(root)
    if destination.exists():
        raise FileExistsError(
            f"immutable RES-292 output already exists at {destination}; use --check to verify it"
        )
    files = _build_output_files(root)
    written = _write_output_atomically(root, files)
    print(
        f"PASS: wrote {len(files)} RES-292 artifacts to {written.relative_to(root)} "
        f"under {protocol['identities']['study_id']}"
    )


if __name__ == "__main__":
    main()
