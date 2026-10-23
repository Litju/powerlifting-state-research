"""Read-only verification of the published RES-293 evidence."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import numpy as np

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import dataset
from ..contracts.serialization import sha256_record
from ..evaluation.identity import EVALUATION_ID, METRIC_IDENTITIES
from ..evaluation.metrics import MetricName, canonical_target_metrics
from ..evaluation.prediction import parse_prediction_jsonl
from .res293_representation_information import (
    BENCHMARK_ID,
    CONFIGS,
    CONTRASTS,
    DATASET_SPEC_ID,
    DEFAULT_DATA_ROOT,
    EXPECTED_TARGETS,
    INIT_SEEDS,
    PROTOCOL_PATH,
    REALIZATION_DIGEST,
    REALIZATION_ID,
    ROOT,
    SPLIT_DIGEST,
    TRAIN_SHA256,
    VALIDATION_SHA256,
    QualificationError,
    _truth_target,
    prepare_fit_payload,
    qualify_canonical_data,
    sha256_file,
)

RESULTS_ROOT = ROOT / "results/studies/res293_representation_learner_information"
ANALYSIS_RECEIPT_SHA256 = "47cb4a76c01dd111e3b6d058fb3b43689c1508e5526d673e4a3d1fba3b5f3502"
REPORT_SHA256 = "bec302bcf054a2f140e3a4c0ef83167ea573d07cdc7574b63d8f6ea06e08f2dc"
EXPECTED_ANALYSIS_OUTPUTS = {
    "canonical-metrics.csv",
    "contrast-influence-diagnostics.csv",
    "development-metrics.csv",
    "execution-receipt.json",
    "multiplier-maxima.csv",
    "per-seed-primary-contrasts.csv",
    "prediction-seal-index.csv",
    "primary-contrasts.csv",
    "seal-manifest.json",
    "training-loss.csv",
}


class PublicVerificationError(RuntimeError):
    """A fail-closed public RES-293 verification error."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublicVerificationError(f"missing or malformed artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise PublicVerificationError(f"expected a JSON object: {path.name}")
    return cast(dict[str, Any], value)


def _check_hash(path: Path, expected: str, expected_bytes: int | None = None) -> None:
    try:
        actual_hash = sha256_file(path)
        actual_bytes = path.stat().st_size
    except OSError as error:
        raise PublicVerificationError(f"missing published artifact: {path}") from error
    if actual_hash != expected or (expected_bytes is not None and actual_bytes != expected_bytes):
        raise PublicVerificationError(f"published artifact hash/size mismatch: {path.name}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise PublicVerificationError(f"CSV header missing: {path.name}")
            return [
                {key: value or "" for key, value in row.items() if key is not None}
                for row in reader
            ]
    except OSError as error:
        raise PublicVerificationError(f"missing published artifact: {path}") from error


def _read_truth(data_root: Path) -> tuple[Any, str]:
    inputs = (
        data_root / "manifest.json",
        data_root / "train.jsonl",
        data_root / "validation.jsonl",
    )
    present = tuple(path.exists() for path in inputs)
    if any(present) and not all(present):
        raise PublicVerificationError(
            "canonical IID data are incomplete; refusing partial recovery"
        )
    try:
        if all(present):
            return qualify_canonical_data(data_root), "existing"
        with tempfile.TemporaryDirectory(prefix="psr-res293-public-truth-") as temporary:
            generated = dataset.write_public_realization(Path(temporary) / "iid-production")
            return qualify_canonical_data(
                generated.output_directory
            ), "deterministically regenerated"
    except (OSError, QualificationError, ValueError) as error:
        raise PublicVerificationError(
            f"canonical IID truth failed identity checks: {error}"
        ) from error


def verify_published_artifacts(results_root: Path = RESULTS_ROOT) -> dict[str, Any]:
    """Verify public receipts, predictions, fit summaries, and their cross-identities."""
    receipt_path = results_root / "analysis-receipt.json"
    report_path = results_root / "report.md"
    _check_hash(receipt_path, ANALYSIS_RECEIPT_SHA256)
    _check_hash(report_path, REPORT_SHA256)
    checked_paths = {receipt_path, report_path}
    analysis = _json(results_root / "analysis-receipt.json")
    if set(analysis.get("output_hashes", {})) != EXPECTED_ANALYSIS_OUTPUTS:
        raise PublicVerificationError("analysis receipt output inventory changed")
    for name, digest in analysis["output_hashes"].items():
        if Path(name).name != name:
            raise PublicVerificationError(f"unsafe output path in analysis receipt: {name}")
        output_path = results_root / name
        _check_hash(output_path, digest)
        checked_paths.add(output_path)

    seal_path = results_root / "seal-manifest.json"
    seal_hash = sha256_file(seal_path)
    seal = _json(seal_path)
    execution = _json(results_root / "execution-receipt.json")
    protocol = _json(PROTOCOL_PATH)
    protocol_id = protocol.get("protocol_id")
    protocol_digest = protocol.get("protocol_digest")
    if not isinstance(protocol_id, str) or not isinstance(protocol_digest, str):
        raise PublicVerificationError("frozen protocol identity is missing")
    if (
        seal.get("format") != "PSR_RES293_SEAL_V1"
        or seal.get("run_id") != "res293-definition-b-fixed-campaign-20261020"
        or seal.get("fit_count") != 30
        or seal.get("configs") != list(CONFIGS)
        or seal.get("initialization_seeds") != list(INIT_SEEDS)
        or seal.get("batch_seeds") != [293301, 293302, 293303, 293304, 293305]
        or seal.get("development_validation_labels_in_payload") is not False
        or seal.get("evaluation_truth_opened_by_worker") is not False
    ):
        raise PublicVerificationError("prediction seal identity or scope mismatch")
    expected_receipt_identity = {
        "format": "PSR_RES293_ANALYSIS_RECEIPT_V1",
        "status": "COMPLETE",
        "run_id": seal["run_id"],
        "protocol_id": protocol_id,
        "protocol_digest": protocol_digest,
        "realization_id": REALIZATION_ID,
        "realization_digest": REALIZATION_DIGEST,
        "dataset_spec_id": DATASET_SPEC_ID,
        "benchmark_spec_id": BENCHMARK_ID,
        "evaluation_id": EVALUATION_ID,
        "train_sha256": TRAIN_SHA256,
        "validation_sha256": VALIDATION_SHA256,
        "split_digest": SPLIT_DIGEST,
        "fit_count": 30,
        "primary_contrast_count": 21,
        "per_seed_contrast_count": 105,
        "prediction_seal_sha256": seal_hash,
    }
    if any(analysis.get(key) != value for key, value in expected_receipt_identity.items()):
        raise PublicVerificationError("analysis receipt scientific identity mismatch")
    if analysis.get("canonical_metric_identities") != [
        item.metric_id for item in METRIC_IDENTITIES
    ]:
        raise PublicVerificationError("canonical metric identities changed")
    expected_analysis_identity = sha256_record(
        {
            "format": "PSR_RES293_ANALYSIS_ID_V1",
            "protocol_digest": protocol_digest,
            "realization_digest": REALIZATION_DIGEST,
            "evaluation_id": EVALUATION_ID,
            "prediction_seal_sha256": seal_hash,
            "contrast_definitions": CONTRASTS,
            "uncertainty": "descriptive 20k Rademacher envelope, no coverage or decision claims",
        }
    )
    if analysis.get("analysis_identity") != expected_analysis_identity:
        raise PublicVerificationError("analysis identity digest mismatch")

    expected_execution = {
        "format": "PSR_RES293_EXECUTION_RECEIPT_V1",
        "status": "30_FITS_SEALED",
        "run_id": seal["run_id"],
        "protocol_id": protocol_id,
        "protocol_digest": protocol_digest,
        "split_digest": SPLIT_DIGEST,
        "train_sha256": TRAIN_SHA256,
        "validation_sha256": VALIDATION_SHA256,
        "fit_count": 30,
        "configuration_count": 6,
        "seed_count": 5,
        "epochs_per_fit": 60,
        "updates_per_fit": 2340,
        "prediction_artifact_count": 60,
        "sealed_state_count": 30,
        "evaluation_truth_opened": False,
        "seal_manifest": "seal-manifest.json",
        "seal_manifest_sha256": seal_hash,
    }
    if any(execution.get(key) != value for key, value in expected_execution.items()):
        raise PublicVerificationError("execution receipt identity or frozen protocol mismatch")

    artifact_items = seal.get("artifacts")
    fit_records = seal.get("fits")
    execution_fits = execution.get("fits")
    if not isinstance(artifact_items, list) or not isinstance(fit_records, list):
        raise PublicVerificationError("seal artifact inventory is malformed")
    if not isinstance(execution_fits, list) or len(fit_records) != 30 or len(execution_fits) != 30:
        raise PublicVerificationError("sealed fit inventory is incomplete")
    artifacts: dict[str, dict[str, Any]] = {}
    for item in artifact_items:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise PublicVerificationError("seal artifact inventory contains an invalid entry")
        name = item["file"]
        if Path(name).name != name or name in artifacts:
            raise PublicVerificationError("seal artifact names are unsafe or duplicated")
        artifacts[name] = cast(dict[str, Any], item)
    expected_fit_keys = {(config, seed) for config in CONFIGS for seed in INIT_SEEDS}
    fit_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    execution_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for record in fit_records:
        key = (str(record.get("config")), int(record.get("initialization_seed", -1)))
        if key in fit_by_key:
            raise PublicVerificationError("duplicate fit identity in seal")
        fit_by_key[key] = cast(dict[str, Any], record)
    for record in execution_fits:
        key = (str(record.get("config")), int(record.get("seed", -1)))
        if key in execution_by_key:
            raise PublicVerificationError("duplicate fit identity in execution receipt")
        execution_by_key[key] = cast(dict[str, Any], record)
    if set(fit_by_key) != expected_fit_keys or set(execution_by_key) != expected_fit_keys:
        raise PublicVerificationError(
            "fit config/seed identities differ from the frozen 30-fit set"
        )

    expected_public_names = {"training-loss.csv"}
    expected_private_names = {"execution-started.json"}
    for config, seed in expected_fit_keys:
        expected_public_names.add(f"{config}-seed-{seed}.fit.json")
        expected_public_names.update(
            f"{config}-seed-{seed}-{split}.jsonl" for split in ("development", "validation")
        )
        expected_private_names.add(f"{config}-seed-{seed}.state.npz")
    if set(artifacts) != expected_public_names | expected_private_names:
        raise PublicVerificationError("seal artifact inventory has missing or unexpected entries")

    validation_predictions: dict[tuple[str, int], np.ndarray] = {}
    prediction_ids: dict[tuple[str, int, str], tuple[str, ...]] = {}
    for config, seed in sorted(expected_fit_keys):
        fit = fit_by_key[(config, seed)]
        execution_fit = execution_by_key[(config, seed)]
        if fit.get("epochs") != 60 or fit.get("updates") != 2340 or fit.get("fit_rows") != 9984:
            raise PublicVerificationError(f"fit protocol identity mismatch: {config}/{seed}")
        if fit.get("final_epoch_only") is not True:
            raise PublicVerificationError(
                f"checkpoint selection identity mismatch: {config}/{seed}"
            )
        state = fit.get("state_artifact", {})
        state_name = state.get("file")
        state_item = artifacts.get(state_name)
        if (
            not isinstance(state_item, dict)
            or state_item.get("sha256") != state.get("sha256")
            or state_item.get("bytes") != state.get("bytes")
            or execution_fit.get("state_file_sha256") != state.get("sha256")
        ):
            raise PublicVerificationError(f"withheld checkpoint identity mismatch: {config}/{seed}")
        fit_name = f"{config}-seed-{seed}.fit.json"
        fit_item = artifacts[fit_name]
        fit_path = results_root / "fits" / fit_name
        _check_hash(fit_path, str(fit_item["sha256"]), int(fit_item["bytes"]))
        checked_paths.add(fit_path)
        fit_summary = _json(fit_path)
        if (
            fit_summary.get("config") != config
            or fit_summary.get("initialization_seed") != seed
            or fit_summary.get("state_artifact") != state
            or fit_summary.get("prediction_artifacts") != fit.get("prediction_artifacts")
            or fit_summary.get("final_state_sha256") != fit.get("final_state_sha256")
        ):
            raise PublicVerificationError(f"fit summary identity mismatch: {config}/{seed}")
        for split, expected_rows in (("development", 2304), ("validation", 3072)):
            prediction_ref = fit["prediction_artifacts"][split]
            name = prediction_ref["file"]
            if Path(name).name != name:
                raise PublicVerificationError(f"unsafe prediction path: {name}")
            artifact = artifacts.get(name)
            if (
                not isinstance(artifact, dict)
                or artifact.get("sha256") != prediction_ref.get("sha256")
                or artifact.get("bytes") != prediction_ref.get("bytes")
                or prediction_ref.get("rows") != expected_rows
            ):
                raise PublicVerificationError(f"prediction identity mismatch: {name}")
            prediction_path = results_root / "predictions" / name
            _check_hash(
                prediction_path, str(prediction_ref["sha256"]), int(prediction_ref["bytes"])
            )
            checked_paths.add(prediction_path)
            try:
                predictions = parse_prediction_jsonl(prediction_path.read_bytes())
            except (OSError, ValueError, json.JSONDecodeError) as error:
                raise PublicVerificationError(f"invalid saved predictions: {name}") from error
            if len(predictions) != expected_rows:
                raise PublicVerificationError(f"prediction row count mismatch: {name}")
            ids = tuple(row.row_id for row in predictions)
            if not all(math.isfinite(value) for row in predictions for value in row.values):
                raise PublicVerificationError(f"non-finite saved prediction: {name}")
            prediction_ids[(config, seed, split)] = ids
            if split == "validation":
                validation_predictions[(config, seed)] = np.asarray(
                    [row.values for row in predictions], dtype=np.float64
                )
        if (
            execution_fit.get("epochs") != 60
            or execution_fit.get("updates") != 2340
            or execution_fit.get("state_file_sha256") != state.get("sha256")
            or execution_fit.get("development_prediction_sha256")
            != fit["prediction_artifacts"]["development"]["sha256"]
            or execution_fit.get("validation_prediction_sha256")
            != fit["prediction_artifacts"]["validation"]["sha256"]
        ):
            raise PublicVerificationError(f"execution fit identity mismatch: {config}/{seed}")

    training_loss = artifacts["training-loss.csv"]
    training_loss_path = results_root / "training-loss.csv"
    _check_hash(training_loss_path, str(training_loss["sha256"]), int(training_loss["bytes"]))
    checked_paths.add(training_loss_path)
    started_path = results_root / "execution-started.json"
    if started_path.exists():
        started = artifacts["execution-started.json"]
        _check_hash(started_path, str(started["sha256"]), int(started["bytes"]))
        checked_paths.add(started_path)

    return {
        "analysis": analysis,
        "seal": seal,
        "execution": execution,
        "protocol_id": protocol_id,
        "protocol_digest": protocol_digest,
        "validation_predictions": validation_predictions,
        "prediction_ids": prediction_ids,
        "published_artifacts_verified": len(checked_paths),
        "fit_records_verified": len(fit_records),
    }


def _check_number(actual: str, expected: float, label: str) -> None:
    try:
        value = float(actual)
    except ValueError as error:
        raise PublicVerificationError(f"missing numeric result for {label}") from error
    if not math.isclose(value, expected, rel_tol=1e-13, abs_tol=1e-13):
        raise PublicVerificationError(f"recomputed value differs for {label}")


def verify_public_run(
    results_root: Path = RESULTS_ROOT, data_root: Path = DEFAULT_DATA_ROOT
) -> dict[str, Any]:
    """Verify published RES-293 artifacts and replay validation metrics and contrasts."""
    evidence = verify_published_artifacts(results_root)
    qualified, truth_source = _read_truth(data_root)
    validation = tuple(sorted(qualified.validation_rows, key=lambda row: row.row_id))
    development_ids = tuple(sorted(row.row_id for row in qualified.split.selection_rows))
    validation_ids = tuple(row.row_id for row in validation)
    predictions_by_fit = cast(dict[tuple[str, int], np.ndarray], evidence["validation_predictions"])
    saved_ids = cast(dict[tuple[str, int, str], tuple[str, ...]], evidence["prediction_ids"])
    rmse: dict[tuple[str, int, int], float] = {}
    metric_rows: dict[tuple[str, int, str], dict[str, str]] = {}
    validation_truth = np.asarray([_truth_target(row) for row in validation], dtype=np.float64)

    for config in CONFIGS:
        for seed in INIT_SEEDS:
            if saved_ids[(config, seed, "validation")] != validation_ids:
                raise PublicVerificationError(f"validation row identities differ: {config}/{seed}")
            if saved_ids[(config, seed, "development")] != development_ids:
                raise PublicVerificationError(f"development row identities differ: {config}/{seed}")
            values = predictions_by_fit[(config, seed)]
            if values.shape != validation_truth.shape or not np.isfinite(values).all():
                raise PublicVerificationError(
                    f"validation predictions are invalid: {config}/{seed}"
                )
            for target_index, target in enumerate(EXPECTED_TARGETS):
                result = canonical_target_metrics(
                    target,
                    validation_truth[:, target_index].tolist(),
                    values[:, target_index].tolist(),
                    unit="kg",
                )
                by_metric = {metric.metric.value: metric for metric in result.metrics}
                row = {
                    "evaluation_id": EVALUATION_ID,
                    "config": config,
                    "seed": str(seed),
                    "split": "validation",
                    "target": target,
                    "n": str(len(validation)),
                }
                for metric_name in MetricName:
                    item = by_metric[metric_name.value]
                    row[f"{metric_name.value}_value"] = (
                        "" if item.value is None else repr(item.value)
                    )
                    row[f"{metric_name.value}_status"] = item.status.value
                    row[f"{metric_name.value}_reason"] = item.reason or ""
                    row[f"{metric_name.value}_unit"] = item.unit
                metric_rows[(config, seed, target)] = row
                metric_value = by_metric[MetricName.RMSE.value].value
                if metric_value is None or not math.isfinite(metric_value):
                    raise PublicVerificationError("canonical validation RMSE is undefined")
                rmse[(config, seed, target_index)] = float(metric_value)

    saved_metrics = [
        row
        for row in _read_csv(results_root / "canonical-metrics.csv")
        if row.get("split") == "validation"
    ]
    saved_metrics_by_key = {
        (row["config"], int(row["seed"]), row["target"]): row for row in saved_metrics
    }
    if len(saved_metrics_by_key) != 90 or set(saved_metrics_by_key) != set(metric_rows):
        raise PublicVerificationError("canonical validation metric row inventory mismatch")
    for metric_key, expected_metric in metric_rows.items():
        actual_metric = saved_metrics_by_key[metric_key]
        for field in ("evaluation_id", "n"):
            if actual_metric.get(field) != expected_metric[field]:
                raise PublicVerificationError(
                    f"canonical metric identity mismatch: {metric_key}/{field}"
                )
        for metric_name in MetricName:
            for suffix in ("_status", "_reason", "_unit"):
                field = f"{metric_name.value}{suffix}"
                if actual_metric.get(field, "") != expected_metric[field]:
                    raise PublicVerificationError(
                        f"canonical metric mismatch: {metric_key}/{field}"
                    )
            field = f"{metric_name.value}_value"
            value = expected_metric[field]
            if value:
                _check_number(actual_metric.get(field, ""), float(value), f"{metric_key}/{field}")
            elif actual_metric.get(field, ""):
                raise PublicVerificationError(
                    f"undefined canonical metric has a value: {metric_key}/{field}"
                )

    expected_per_seed: dict[tuple[str, str, int], float] = {}
    expected_primary: dict[tuple[str, str], dict[str, Any]] = {}
    for target_index, target in enumerate(EXPECTED_TARGETS):
        for contrast_id, description, coefficients in CONTRASTS:
            values = np.asarray(
                [
                    sum(
                        coefficient * rmse[(config, seed, target_index)]
                        for config, coefficient in coefficients.items()
                    )
                    for seed in INIT_SEEDS
                ],
                dtype=np.float64,
            )
            for seed, estimate in zip(INIT_SEEDS, values, strict=True):
                expected_per_seed[(target, contrast_id, seed)] = float(estimate)
            expected_primary[(target, contrast_id)] = {
                "definition": description,
                "estimate_kg": float(values.mean()),
                "seed_count": len(values),
                "per_seed_min_kg": float(values.min()),
                "per_seed_max_kg": float(values.max()),
            }

    saved_per_seed = _read_csv(results_root / "per-seed-primary-contrasts.csv")
    saved_per_seed_by_key = {
        (row["target"], row["contrast_id"], int(row["seed"])): row for row in saved_per_seed
    }
    if len(saved_per_seed_by_key) != 105 or set(saved_per_seed_by_key) != set(expected_per_seed):
        raise PublicVerificationError("per-seed contrast inventory mismatch")
    for seed_key, estimate in expected_per_seed.items():
        row = saved_per_seed_by_key[seed_key]
        if (
            row.get("interpretation")
            != "difference between fixed finite-budget training procedures"
        ):
            raise PublicVerificationError(f"per-seed contrast identity mismatch: {seed_key}")
        _check_number(row.get("estimate_kg", ""), estimate, str(seed_key))

    saved_primary = _read_csv(results_root / "primary-contrasts.csv")
    saved_primary_by_key = {(row["target"], row["contrast_id"]): row for row in saved_primary}
    if len(saved_primary_by_key) != 21 or set(saved_primary_by_key) != set(expected_primary):
        raise PublicVerificationError("primary contrast inventory mismatch")
    for primary_key, summary in expected_primary.items():
        row = saved_primary_by_key[primary_key]
        if (
            row.get("evaluation_id") != EVALUATION_ID
            or row.get("definition") != summary["definition"]
            or row.get("seed_count") != "5"
            or row.get("interpretation")
            != "difference between these fixed finite-budget training procedures"
            or row.get("decision_classification")
            != "none; no significance, equivalence, or materiality rule"
        ):
            raise PublicVerificationError(f"primary contrast identity mismatch: {primary_key}")
        for field in ("estimate_kg", "per_seed_min_kg", "per_seed_max_kg"):
            _check_number(row.get(field, ""), float(summary[field]), f"{primary_key}/{field}")

    return {
        "truth_source": truth_source,
        "published_artifacts_verified": evidence["published_artifacts_verified"],
        "fit_records_verified": evidence["fit_records_verified"],
        "validation_metrics_recomputed": len(metric_rows),
        "per_seed_contrasts_recomputed": len(expected_per_seed),
        "primary_contrasts_recomputed": len(expected_primary),
        "checkpoint_files_read": 0,
    }


def replay_saved_predictions(
    results_root: Path = RESULTS_ROOT, data_root: Path = DEFAULT_DATA_ROOT
) -> dict[str, int]:
    """Replay all sealed RES-293 predictions from released final states, without fitting."""
    import torch

    evidence = verify_published_artifacts(results_root)
    qualified, _ = _read_truth(data_root)
    worker_path = ROOT / "models/published/res293-definition-b/source-evidence/res293_fit_worker.py"
    spec = importlib.util.spec_from_file_location("res293_replay_worker", worker_path)
    if spec is None or spec.loader is None:
        raise PublicVerificationError("frozen RES-293 worker is unavailable")
    worker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = worker
    spec.loader.exec_module(worker)
    if torch.cuda.is_available():
        raise PublicVerificationError("RES-293 prediction replay requires CPU-only PyTorch")
    torch.set_num_threads(1)

    release_path = ROOT / "models/published/res293-definition-b/artifact-manifest.json"
    release = _json(release_path)
    states_by_source = {item["source_member"]: item for item in release.get("artifacts", ())}
    fit_records = evidence["seal"]["fits"]
    replayed = 0
    with tempfile.TemporaryDirectory(prefix="psr-res293-replay-") as temporary:
        payload_info = prepare_fit_payload(qualified, Path(temporary))
        payload = worker._load_payload(Path(str(payload_info["payload"])))
        for fit in fit_records:
            config = fit["config"]
            seed = int(fit["initialization_seed"])
            state_ref = fit["state_artifact"]
            state_record = states_by_source.get(state_ref["file"])
            if (
                state_record is None
                or state_record["sha256"] != state_ref["sha256"]
                or state_record["bytes"] != state_ref["bytes"]
                or state_record["scientific_identity"]["configuration"] != config
                or state_record["scientific_identity"]["initialization_seed"] != seed
                or state_record["scientific_identity"]["final_state_sha256"]
                != fit["final_state_sha256"]
            ):
                raise PublicVerificationError(
                    f"published RES-293 state identity mismatch: {config}/{seed}"
                )
            state_path = ROOT / state_record["path"]
            _check_hash(state_path, state_ref["sha256"], int(state_ref["bytes"]))
            model = worker._new_model(fit["learner"])
            with np.load(state_path, allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            model.load_state_dict(
                {name: torch.from_numpy(array.copy()) for name, array in arrays.items()},
                strict=True,
            )
            if worker._state_digest(model) != fit["final_state_sha256"]:
                raise PublicVerificationError(f"RES-293 state digest mismatch: {config}/{seed}")

            summary = _json(results_root / "fits" / f"{config}-seed-{seed}.fit.json")
            mean = torch.tensor(summary["target_mean_kg"], dtype=torch.float64)
            scale = torch.tensor(summary["target_scale_kg"], dtype=torch.float64)
            for split in ("development", "validation"):
                representation = fit["representation"]
                features = payload[f"{split}_{'s' if representation.startswith('S') else 'o'}"]
                if representation.startswith("S"):
                    features = worker._config_features(config, features)
                prediction_bytes = worker._canonical_predictions(
                    payload[f"{split}_row_ids"], worker._predict(model, features, mean, scale)
                )
                prediction_path = (
                    results_root / "predictions" / fit["prediction_artifacts"][split]["file"]
                )
                if prediction_bytes != prediction_path.read_bytes():
                    raise PublicVerificationError(
                        f"RES-293 {split} prediction replay differs: {config}/{seed}"
                    )
                replayed += 1
    if replayed != 60:
        raise PublicVerificationError(f"expected 60 RES-293 prediction replays, found {replayed}")
    return {"prediction_files_replayed": replayed, "byte_identical_prediction_files": replayed}
