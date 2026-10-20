"""Data, feature, and analysis code for the bounded RES-293 study."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset,
    evaluate,
    interventions,
)
from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..evaluation.identity import EVALUATION_ID, METRIC_IDENTITIES
from ..evaluation.metrics import MetricName, canonical_target_metrics
from ..evaluation.prediction import parse_prediction_jsonl
from ..models.comparators import feature_matrix
from ..models.temporal_expert import (
    PLAN_ORDER,
    NormalizationStats,
    TemporalModelInput,
    prepare_batch,
)
from ..models.train_temporal_expert import _stratum_key, make_internal_split

FloatArray = NDArray[np.float64]
FeatureArray = NDArray[np.float32]
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = (
    ROOT
    / "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production"
)
EXPECTED_MANIFEST = (
    ROOT
    / "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting"
    / "iid-production.json"
)
TRAIN_SHA256 = "914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550"
VALIDATION_SHA256 = "0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a"
MANIFEST_DIGEST = "sha256:2655965129f99fa98857f6c9363aa28a0dd964c2d7d8554156c17073e0277e35"
REALIZATION_ID = (
    "psr:dataset-realization:latent-capacity-transient-iid-production"
    "@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
)
REALIZATION_DIGEST = "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
DATASET_SPEC_ID = (
    "psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed"
)
BENCHMARK_ID = (
    "psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting"
    "@1.0.0~f99463d55ba0"
)
SPLIT_DIGEST = "9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"
EXPECTED_GENERATOR_SHA256 = "284266740cdaebdbe7108a5abe1acf4a2eeb3c055852b6ebc3c439ec164d1ad3"
EXPECTED_CONFIG_SHA256 = "979aad4cea7be05ec8c4861ac9025f282c45903e0db0cab72c22d1fcdd87d850"
PROTOCOL_PATH = ROOT / "studies/res293_representation_learner_information/protocol.json"
INIT_SEEDS = (293201, 293202, 293203, 293204, 293205)
BATCH_SEEDS = (293301, 293302, 293303, 293304, 293305)
CONFIGS = ("C1", "C2", "C3", "C4", "C5", "C6")
CONTRASTS: tuple[tuple[str, str, dict[str, int]], ...] = (
    ("C2_minus_C1", "ordered minus summary, affine learner", {"C2": 1, "C1": -1}),
    ("C4_minus_C3", "ordered minus summary, compact nonlinear learner", {"C4": 1, "C3": -1}),
    ("C3_minus_C1", "nonlinear minus affine, summary encoding", {"C3": 1, "C1": -1}),
    ("C4_minus_C2", "nonlinear minus affine, ordered encoding", {"C4": 1, "C2": -1}),
    (
        "encoding_by_learner_interaction",
        "(C4 minus C3) minus (C2 minus C1)",
        {"C4": 1, "C3": -1, "C2": -1, "C1": 1},
    ),
    (
        "C3_minus_C5",
        "full summary minus context-only, compact nonlinear learner",
        {"C3": 1, "C5": -1},
    ),
    (
        "C3_minus_C6",
        "full summary minus assessment/load omission, compact nonlinear learner",
        {"C3": 1, "C6": -1},
    ),
)
EXPECTED_TARGETS = (
    "squat_delta_capacity_kg",
    "bench_press_delta_capacity_kg",
    "deadlift_delta_capacity_kg",
)


class QualificationError(RuntimeError):
    """A fail-closed RES-293 data, identity, or analysis gate."""


@dataclass(frozen=True, slots=True)
class QualifiedData:
    data_root: Path
    train_rows: tuple[dataset.PublicForecastRow, ...]
    validation_rows: tuple[dataset.PublicForecastRow, ...]
    split: Any
    manifest: Any
    train_sha256: str
    validation_sha256: str
    stratum_counts: tuple[dict[str, object], ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> bytes:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _read_rows(path: Path, expected_count: int) -> tuple[dataset.PublicForecastRow, ...]:
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n") or raw.count(b"\n") != expected_count:
        raise QualificationError(f"{path.name} is not the frozen newline-terminated row count")
    rows: list[dataset.PublicForecastRow] = []
    for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
        content = line.removesuffix(b"\n")
        try:
            value = json.loads(
                content,
                object_pairs_hook=cast(Any, evaluate)._object,
                parse_constant=cast(Any, evaluate)._reject_constant,
            )
            if canonical_json_bytes(value) != content:
                raise ValueError("noncanonical row bytes")
            rows.append(evaluate._parse_truth_row(value))
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as error:
            raise QualificationError(f"invalid {path.name} row {line_number}: {error}") from error
    if len(rows) != expected_count:
        raise QualificationError(f"{path.name} row count differs from the frozen contract")
    row_ids = [row.row_id for row in rows]
    entity_ids = [row.inputs.entity_id for row in rows]
    if len(set(row_ids)) != expected_count or len(set(entity_ids)) != expected_count:
        raise QualificationError(f"{path.name} has duplicate row or entity identities")
    if row_ids != entity_ids:
        raise QualificationError(f"{path.name} requires row_id == entity_id")
    return tuple(rows)


def _expected_strata() -> set[tuple[object, ...]]:
    output: set[tuple[object, ...]] = set()
    schedules = tuple(
        tuple(
            (item.start_day, item.end_day, item.dose, item.intensity)
            for item in interventions.history_segments(index)
        )
        for index in range(len(interventions.HISTORY_TEMPLATES))
    )
    for plan_id in interventions.PLAN_IDS:
        for horizon in interventions.HORIZONS_DAYS:
            for template_indexes in itertools.product(range(4), repeat=3):
                output.add(
                    (
                        plan_id,
                        horizon,
                        *(schedules[index] for index in template_indexes),
                    )
                )
    return output


def qualify_canonical_data(data_root: Path = DEFAULT_DATA_ROOT) -> QualifiedData:
    """Verify existing canonical bytes, exact memberships, and all frozen strata."""
    root = data_root.resolve()
    manifest_path = root / "manifest.json"
    train_path = root / "train.jsonl"
    validation_path = root / "validation.jsonl"
    try:
        expected_manifest_bytes = EXPECTED_MANIFEST.read_bytes()
        local_manifest_bytes = manifest_path.read_bytes()
        if local_manifest_bytes != expected_manifest_bytes:
            raise QualificationError(
                "local canonical manifest bytes differ from repository authority"
            )
        manifest = evaluate._parse_manifest(manifest_path, evaluate.CANONICAL_VALIDATION)
        train_sha = sha256_file(train_path)
        validation_sha = sha256_file(validation_path)
        if train_sha != TRAIN_SHA256 or validation_sha != VALIDATION_SHA256:
            raise QualificationError("canonical data file SHA-256 mismatch")
    except OSError as error:
        raise QualificationError(f"canonical IID bytes are unavailable: {error}") from error
    generator_sha = dataset.generator_source_sha256().removeprefix("sha256:")
    config_sha = sha256_record(dataset.PUBLIC_GENERATION_CONFIGURATION).removeprefix("sha256:")
    if generator_sha != EXPECTED_GENERATOR_SHA256 or config_sha != EXPECTED_CONFIG_SHA256:
        raise QualificationError("public generator source or configuration identity mismatch")
    if (
        manifest.dataset_spec_id != DATASET_SPEC_ID
        or manifest.identity_id != REALIZATION_ID
        or manifest.realization_digest != REALIZATION_DIGEST
        or manifest.manifest_digest != MANIFEST_DIGEST
    ):
        raise QualificationError("canonical realization identity differs from the frozen contract")
    if tuple((item.artifact_id, item.sha256) for item in manifest.artifact_hashes) != (
        ("train", TRAIN_SHA256),
        ("validation", VALIDATION_SHA256),
    ):
        raise QualificationError("manifest artifact hashes differ from frozen train/validation")
    train_rows = _read_rows(train_path, 12_288)
    validation_rows = _read_rows(validation_path, 3_072)
    train_ids = {row.row_id for row in train_rows}
    validation_ids = {row.row_id for row in validation_rows}
    if train_ids & validation_ids:
        raise QualificationError("TRAIN and validation entity memberships overlap")
    split = make_internal_split(
        train_rows,
        realization_id=REALIZATION_ID,
        realization_digest=REALIZATION_DIGEST,
        protocol_id="res293-v02-executable",
    )
    if str(split.manifest["split_digest"]).removeprefix("sha256:") != SPLIT_DIGEST:
        raise QualificationError("internal fit/development membership digest mismatch")
    fit_ids = set(cast(tuple[str, ...], split.manifest["fit_row_ids"]))
    development_ids = set(cast(tuple[str, ...], split.manifest["selection_row_ids"]))
    if len(fit_ids) != 9_984 or len(development_ids) != 2_304 or fit_ids & development_ids:
        raise QualificationError("internal split row counts or disjointness mismatch")
    grouped_train: dict[tuple[object, ...], list[dataset.PublicForecastRow]] = {}
    grouped_validation: dict[tuple[object, ...], list[dataset.PublicForecastRow]] = {}
    for row in train_rows:
        grouped_train.setdefault(_stratum_key(row), []).append(row)
    for row in validation_rows:
        grouped_validation.setdefault(_stratum_key(row), []).append(row)
    expected = _expected_strata()
    if set(grouped_train) != expected or set(grouped_validation) != expected:
        raise QualificationError(
            "canonical train/validation strata do not match the 768 frozen keys"
        )
    counts: list[dict[str, object]] = []
    for key in sorted(
        expected, key=lambda item: hashlib.sha256(canonical_json_bytes(item)).hexdigest()
    ):
        train_group = grouped_train[key]
        validation_group = grouped_validation[key]
        fit_count = sum(row.row_id in fit_ids for row in train_group)
        development_count = sum(row.row_id in development_ids for row in train_group)
        if (len(train_group), fit_count, development_count, len(validation_group)) != (
            16,
            13,
            3,
            4,
        ):
            raise QualificationError("one or more frozen design-stratum counts differ")
        schedules = key[2:]
        counts.append(
            {
                "stratum_sha256": hashlib.sha256(canonical_json_bytes(key)).hexdigest(),
                "plan_id": key[0],
                "horizon_days": key[1],
                "schedule_sha256": [
                    hashlib.sha256(canonical_json_bytes(schedule)).hexdigest()
                    for schedule in schedules
                ],
                "train_count": len(train_group),
                "fit_count": fit_count,
                "development_count": development_count,
                "validation_count": len(validation_group),
            }
        )
    if len(counts) != 768:
        raise QualificationError("expected exactly 768 evaluation strata")
    return QualifiedData(
        root, train_rows, validation_rows, split, manifest, train_sha, validation_sha, tuple(counts)
    )


def write_qualification_receipts(data: QualifiedData, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    split_payload = dict(data.split.manifest)
    split_payload["training_protocol_id"] = "psr:training-protocol:res293-fixed-60-epoch-adamw-v1"
    _write_json(output / "split-membership.json", split_payload)
    with (output / "stratum-counts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "stratum_sha256",
                "plan_id",
                "horizon_days",
                "schedule_sha256",
                "train_count",
                "fit_count",
                "development_count",
                "validation_count",
            ),
        )
        writer.writeheader()
        for item in data.stratum_counts:
            writer.writerow(
                {
                    **item,
                    "schedule_sha256": json.dumps(item["schedule_sha256"], separators=(",", ":")),
                }
            )
    receipt = {
        "format": "PSR_RES293_DATA_QUALIFICATION_V1",
        "status": "PASS",
        "canonical_bytes_mode": "preexisting_ignored_bytes_reused_without_regeneration",
        "data_root_is_read_only_input": True,
        "dataset_spec_id": DATASET_SPEC_ID,
        "benchmark_spec_id": BENCHMARK_ID,
        "realization_id": REALIZATION_ID,
        "realization_digest": REALIZATION_DIGEST,
        "manifest_digest": data.manifest.manifest_digest,
        "manifest_file_sha256": sha256_file(data.data_root / "manifest.json"),
        "train_sha256": data.train_sha256,
        "validation_sha256": data.validation_sha256,
        "generator_source_sha256": EXPECTED_GENERATOR_SHA256,
        "generator_configuration_sha256": EXPECTED_CONFIG_SHA256,
        "schema_identity": data.manifest.schema_identity,
        "rights": {
            "license_expression": data.manifest.rights.license_expression,
            "copyright_holder": data.manifest.rights.copyright_holder,
            "redistribution_status": data.manifest.rights.redistribution_status,
            "access_conditions": data.manifest.rights.access_conditions,
        },
        "train_rows": len(data.train_rows),
        "validation_rows": len(data.validation_rows),
        "row_id_equals_entity_id": True,
        "train_validation_disjoint": True,
        "fit_rows": len(data.split.fit_rows),
        "development_rows": len(data.split.selection_rows),
        "split_digest": data.split.manifest["split_digest"],
        "fit_row_ids_sha256": data.split.manifest["fit_row_ids_sha256"],
        "development_row_ids_sha256": data.split.manifest["selection_row_ids_sha256"],
        "validation_row_ids_sha256": hashlib.sha256(
            canonical_json_bytes(sorted(row.row_id for row in data.validation_rows))
        ).hexdigest(),
        "fit_membership_exact": True,
        "stratum_count_file": "stratum-counts.csv",
        "stratum_count_file_sha256": sha256_file(output / "stratum-counts.csv"),
        "stratum_count_rows": len(data.stratum_counts),
        "all_768_validation_counts_equal_four": True,
        "target_schema_and_finiteness_checked_without_summary_export": True,
        "evaluation_targets_used_for_feature_or_feasibility_work": False,
    }
    _write_json(output / "data-qualification.json", receipt)
    return receipt


def _model_inputs(rows: tuple[dataset.PublicForecastRow, ...]) -> tuple[TemporalModelInput, ...]:
    return tuple(TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in rows)


def _ordered_features(
    rows: tuple[dataset.PublicForecastRow, ...], stats: NormalizationStats
) -> FloatArray:
    batch = prepare_batch(_model_inputs(rows), stats).tensors
    history = batch.history.detach().cpu().numpy().astype(np.float64, copy=False)
    plan = batch.plan_numeric.detach().cpu().numpy().astype(np.float64, copy=False)
    index = batch.plan_index.detach().cpu().numpy()
    return np.concatenate(
        (history[:, :, :, :9].reshape(len(rows), 864), plan, np.eye(4, dtype=np.float64)[index]),
        axis=1,
    )


def _fit_standardization(
    fit: FloatArray, values: FloatArray
) -> tuple[FeatureArray, FeatureArray, FloatArray, FloatArray]:
    mean = fit.mean(axis=0, dtype=np.float64)
    scale = np.maximum(fit.std(axis=0, ddof=0, dtype=np.float64), 1e-6)
    standardized_fit = ((fit - mean) / scale).astype(np.float32)
    standardized_values = ((values - mean) / scale).astype(np.float32)
    return standardized_fit, standardized_values, mean, scale


def _pack_summary(values: FeatureArray) -> FeatureArray:
    packed = np.zeros((len(values), 874), dtype=np.float32)
    packed[:, :117] = values[:, :117]
    packed[:, 864:] = values[:, 117:127]
    return packed


def array_payload_digest(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256(b"PSR_RES293_FEATURE_PAYLOAD_V1\0")
    for name in sorted(arrays):
        array = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(array.dtype).encode("ascii") + b"\0")
        digest.update(canonical_json_bytes(array.shape))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def prepare_fit_payload(data: QualifiedData, output_dir: Path) -> dict[str, object]:
    """Create fit-only numeric input; validation and development labels are omitted."""
    started = time.perf_counter()
    fit_ids = set(cast(tuple[str, ...], data.split.manifest["fit_row_ids"]))
    development_ids = set(cast(tuple[str, ...], data.split.manifest["selection_row_ids"]))
    row_by_id = {row.row_id: row for row in data.train_rows}
    fit_rows = tuple(row_by_id[row_id] for row_id in sorted(fit_ids))
    development_rows = tuple(row_by_id[row_id] for row_id in sorted(development_ids))
    validation_rows = tuple(sorted(data.validation_rows, key=lambda row: row.row_id))
    if len(fit_rows) != 9_984 or len(development_rows) != 2_304 or len(validation_rows) != 3_072:
        raise QualificationError("feature staging row counts differ from the frozen protocol")
    fit_inputs = _model_inputs(fit_rows)
    fit_targets: tuple[tuple[float, float, float], ...] = tuple(
        _truth_target(row) for row in fit_rows
    )
    normalization = NormalizationStats.fit_train(fit_inputs, fit_targets)
    summary_fit_raw = feature_matrix(fit_rows, normalization)
    ordered_fit_raw = _ordered_features(fit_rows, normalization)
    summary_development_raw = feature_matrix(development_rows, normalization)
    ordered_development_raw = _ordered_features(development_rows, normalization)
    summary_validation_raw = feature_matrix(validation_rows, normalization)
    ordered_validation_raw = _ordered_features(validation_rows, normalization)
    summary_fit_std, summary_development_std, summary_mean, summary_scale = _fit_standardization(
        summary_fit_raw, summary_development_raw
    )
    _, summary_validation_std, _, _ = _fit_standardization(summary_fit_raw, summary_validation_raw)
    ordered_fit_std, ordered_development_std, ordered_mean, ordered_scale = _fit_standardization(
        ordered_fit_raw, ordered_development_raw
    )
    _, ordered_validation_std, _, _ = _fit_standardization(ordered_fit_raw, ordered_validation_raw)
    arrays: dict[str, np.ndarray] = {
        "fit_s": _pack_summary(summary_fit_std),
        "fit_o": ordered_fit_std,
        "fit_y_kg": np.asarray(fit_targets, dtype=np.float64),
        "development_s": _pack_summary(summary_development_std),
        "development_o": ordered_development_std,
        "development_row_ids": np.asarray([row.row_id for row in development_rows], dtype="U64"),
        "validation_s": _pack_summary(summary_validation_std),
        "validation_o": ordered_validation_std,
        "validation_row_ids": np.asarray([row.row_id for row in validation_rows], dtype="U64"),
    }
    if any(
        not np.isfinite(value).all() for name, value in arrays.items() if value.dtype.kind in "f"
    ):
        raise QualificationError("feature staging produced a non-finite learner payload")
    payload_path = output_dir / "fit-input.npz"
    output_dir.mkdir(parents=True, exist_ok=True)
    cast(Any, np.savez)(payload_path, **arrays)
    payload_digest = array_payload_digest(arrays)
    context_matrix = np.asarray(
        [
            [
                1.0,
                horizon / 56.0,
                plan.dose / 1.2,
                plan.intensity,
                plan.dose * plan.intensity / 1.2,
                (plan.end_day - plan.start_day + 1) / 56.0,
                *np.eye(4, dtype=np.float64)[PLAN_ORDER.index(plan.plan_id)],
            ]
            for plan_id in interventions.PLAN_IDS
            for horizon in interventions.HORIZONS_DAYS
            for plan in (interventions.declared_plan(plan_id),)
            for _fixture_family in ("A", "B")
            for _rotation in range(4)
        ],
        dtype=np.float64,
    )
    centered_context = context_matrix - context_matrix.mean(axis=0)
    singular_values = np.linalg.svd(centered_context, compute_uv=False)
    context_rank = int(np.count_nonzero(singular_values > singular_values[0] * 1e-6))
    if context_matrix.shape != (96, 10) or context_rank != 4:
        raise QualificationError("balanced support context matrix rank is not the frozen rank 4")
    normalization_payload = {
        "format": "PSR_RES293_FIT_NORMALIZATION_V1",
        "fit_row_count": len(fit_rows),
        "fit_row_ids_sha256": data.split.manifest["fit_row_ids_sha256"],
        "first_stage_input_target_stats": normalization.to_dict(),
        "summary_feature_mean": summary_mean.tolist(),
        "summary_feature_scale": summary_scale.tolist(),
        "ordered_feature_mean": ordered_mean.tolist(),
        "ordered_feature_scale": ordered_scale.tolist(),
        "summary_feature_mean_sha256": hashlib.sha256(
            summary_mean.astype("<f8").tobytes()
        ).hexdigest(),
        "summary_feature_scale_sha256": hashlib.sha256(
            summary_scale.astype("<f8").tobytes()
        ).hexdigest(),
        "ordered_feature_mean_sha256": hashlib.sha256(
            ordered_mean.astype("<f8").tobytes()
        ).hexdigest(),
        "ordered_feature_scale_sha256": hashlib.sha256(
            ordered_scale.astype("<f8").tobytes()
        ).hexdigest(),
        "input_feature_payload_sha256": payload_digest,
        "input_feature_payload_bytes_sha256": sha256_file(payload_path),
        "input_feature_payload_bytes": payload_path.stat().st_size,
        "context_support": {
            "balanced_fixture_rows": 96,
            "features": 10,
            "centered_singular_values": singular_values.tolist(),
            "relative_rank_tolerance": 1e-6,
            "centered_rank": context_rank,
            "constant_slots": [864, 867, 869],
            "algebraic_dependencies": [
                "origin_day_div_224 = 1",
                "future_intensity_div_1 = 0.75",
                "full_plan_duration_days_div_56 = 1",
                "sum(plan_one_hot) = 1",
                "future_dose_x_intensity_div_1.2 = 0.75 * future_dose_div_1.2",
                "future_dose_div_1.2 = (2/3)*continue + (1/3)*step_down + step_up",
            ],
            "interpretation": (
                "three plan-category degrees of freedom plus one horizon degree of freedom"
            ),
        },
        "fit_only": True,
        "development_or_validation_labels_in_payload": False,
    }
    _write_json(output_dir / "normalization.json", normalization_payload)
    return {
        "format": "PSR_RES293_INPUT_STAGING_V1",
        "status": "PASS",
        "payload": str(payload_path),
        "payload_sha256": payload_digest,
        "payload_bytes_sha256": sha256_file(payload_path),
        "payload_bytes": payload_path.stat().st_size,
        "feature_rows": {
            "fit": len(fit_rows),
            "development": len(development_rows),
            "validation": len(validation_rows),
        },
        "fit_y_kg_only": True,
        "development_validation_labels_absent": True,
        "validation_predictions_or_scores_not_computed": True,
        "elapsed_wall_seconds": time.perf_counter() - started,
        "normalization_sha256": sha256_file(output_dir / "normalization.json"),
    }


def verify_sealed_run(run_dir: Path, *, expected_run_id: str | None = None) -> dict[str, Any]:
    seal_path = run_dir / "seal-manifest.json"
    try:
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError("the complete fit seal is missing or malformed") from error
    if seal.get("format") != "PSR_RES293_SEAL_V1" or seal.get("fit_count") != 30:
        raise QualificationError("fit seal does not bind the complete 30-fit campaign")
    if expected_run_id is not None and seal.get("run_id") != expected_run_id:
        raise QualificationError("fit seal run identity mismatch")
    keys = {(record["config"], record["initialization_seed"]) for record in seal["fits"]}
    expected = {(config, seed) for config in CONFIGS for seed in INIT_SEEDS}
    if keys != expected or len(seal["fits"]) != 30:
        raise QualificationError("fit seal is missing or duplicates a config/seed pair")
    if seal.get("development_validation_labels_in_payload") is not False:
        raise QualificationError("fit seal does not verify target isolation")
    if seal.get("evaluation_truth_opened_by_worker") is not False:
        raise QualificationError("fit worker opened evaluation truth")
    for record in seal["fits"]:
        config = record["config"]
        seed = record["initialization_seed"]
        expected_parameters = 2_625 if config in {"C1", "C2"} else 28_099
        if (
            record["epochs"] != 60
            or record["updates"] != 2_340
            or record["fit_rows"] != 9_984
            or record["batch_size"] != 256
            or record["parameter_count"] != expected_parameters
            or record["final_epoch_only"] is not True
            or record["bias_initialization"]["nonzero_count"] != 0
        ):
            raise QualificationError(f"fit protocol receipt mismatch for {config}/{seed}")
        if any(
            value != 0.0
            for tensor in record["bias_initialization"]["tensors"]
            for value in tensor["values"]
        ):
            raise QualificationError(f"fit recorded a nonzero initial bias for {config}/{seed}")
        for item in (record["state_artifact"], *record["prediction_artifacts"].values()):
            path = run_dir / item["file"]
            if (
                not path.is_file()
                or sha256_file(path) != item["sha256"]
                or path.stat().st_size != item["bytes"]
            ):
                raise QualificationError(f"sealed artifact hash mismatch: {path.name}")
        for split, expected_count in (("development", 2_304), ("validation", 3_072)):
            path = run_dir / record["prediction_artifacts"][split]["file"]
            rows = parse_prediction_jsonl(path.read_bytes())
            if len(rows) != expected_count:
                raise QualificationError(
                    f"sealed {split} prediction count mismatch for {config}/{seed}"
                )
    for config_set in (("C1", "C2"), ("C3", "C4", "C5", "C6")):
        for seed in INIT_SEEDS:
            initial = {
                record["config"]: record["initial_state_sha256"]
                for record in seal["fits"]
                if record["initialization_seed"] == seed
            }
            if len({initial[config] for config in config_set}) != 1:
                raise QualificationError(
                    "paired configurations do not share their learner-family start"
                )
    return cast(dict[str, Any], seal)


def _truth_target(row: dataset.PublicForecastRow) -> tuple[float, float, float]:
    return (
        float(row.targets["squat_delta_capacity_kg"]),
        float(row.targets["bench_press_delta_capacity_kg"]),
        float(row.targets["deadlift_delta_capacity_kg"]),
    )


def analyze_sealed_run(
    run_dir: Path,
    output_dir: Path,
    *,
    train_path: Path = DEFAULT_DATA_ROOT / "train.jsonl",
    validation_path: Path = DEFAULT_DATA_ROOT / "validation.jsonl",
    expected_run_id: str | None = None,
) -> dict[str, object]:
    """Verify all sealed outputs first, then open development and validation truth."""
    seal = verify_sealed_run(run_dir, expected_run_id=expected_run_id)
    if sha256_file(train_path) != TRAIN_SHA256 or sha256_file(validation_path) != VALIDATION_SHA256:
        raise QualificationError("truth bytes changed after the sealed run")
    train_rows = _read_rows(train_path, 12_288)
    validation_rows = tuple(sorted(_read_rows(validation_path, 3_072), key=lambda row: row.row_id))
    split = make_internal_split(
        train_rows,
        realization_id=REALIZATION_ID,
        realization_digest=REALIZATION_DIGEST,
        protocol_id="res293-v02-executable",
    )
    if str(split.manifest["split_digest"]).removeprefix("sha256:") != SPLIT_DIGEST:
        raise QualificationError("development-label split differs from the sealed split")
    development_by_id = {row.row_id: row for row in split.selection_rows}
    development_rows = tuple(development_by_id[key] for key in sorted(development_by_id))
    if len(development_rows) != 2_304:
        raise QualificationError("development truth row count mismatch")
    validation_ids = tuple(row.row_id for row in validation_rows)
    development_ids = tuple(row.row_id for row in development_rows)
    metrics_rows: list[dict[str, object]] = []
    development_metrics: list[dict[str, object]] = []
    validation_predictions: dict[tuple[str, int], np.ndarray] = {}
    rmse: dict[tuple[str, int, int], float] = {}
    prediction_inventory: list[dict[str, object]] = []
    for fit in sorted(seal["fits"], key=lambda item: (item["config"], item["initialization_seed"])):
        config = str(fit["config"])
        seed = int(fit["initialization_seed"])
        for split_name, rows, ids, destination in (
            ("validation", validation_rows, validation_ids, metrics_rows),
            ("development", development_rows, development_ids, development_metrics),
        ):
            artifact = fit["prediction_artifacts"][split_name]
            raw = (run_dir / artifact["file"]).read_bytes()
            predictions = parse_prediction_jsonl(raw)
            if tuple(row.row_id for row in predictions) != ids:
                raise QualificationError(
                    f"{config}/{seed} {split_name} keys/order differ from truth"
                )
            prediction_values = np.asarray([row.values for row in predictions], dtype=np.float64)
            truth_values = np.asarray([_truth_target(row) for row in rows], dtype=np.float64)
            for target_index, target in enumerate(EXPECTED_TARGETS):
                result = canonical_target_metrics(
                    target,
                    truth_values[:, target_index].tolist(),
                    prediction_values[:, target_index].tolist(),
                    unit="kg",
                )
                by_metric = {metric.metric.value: metric for metric in result.metrics}
                metric_row: dict[str, object] = {
                    "evaluation_id": EVALUATION_ID,
                    "config": config,
                    "seed": seed,
                    "split": split_name,
                    "target": target,
                    "n": len(rows),
                }
                for metric_name in MetricName:
                    item = by_metric[metric_name.value]
                    metric_row[f"{metric_name.value}_value"] = item.value
                    metric_row[f"{metric_name.value}_status"] = item.status.value
                    metric_row[f"{metric_name.value}_reason"] = item.reason
                    metric_row[f"{metric_name.value}_unit"] = item.unit
                destination.append(metric_row)
                if split_name == "validation":
                    metric_value = by_metric[MetricName.RMSE.value].value
                    if metric_value is None or not math.isfinite(metric_value):
                        raise QualificationError(
                            "canonical validation RMSE is undefined/non-finite"
                        )
                    rmse[(config, seed, target_index)] = float(metric_value)
            if split_name == "validation":
                validation_predictions[(config, seed)] = prediction_values
                prediction_inventory.append(
                    {
                        "config": config,
                        "seed": seed,
                        "file": artifact["file"],
                        "sha256": artifact["sha256"],
                        "rows": len(predictions),
                    }
                )

    seed_contrasts: list[dict[str, object]] = []
    contrast_points: dict[tuple[str, str], np.ndarray] = {}
    for target_index, target in enumerate(EXPECTED_TARGETS):
        for contrast_id, _description, coefficients in CONTRASTS:
            per_seed: list[float] = []
            for seed in INIT_SEEDS:
                estimate = sum(
                    coefficient * rmse[(config, seed, target_index)]
                    for config, coefficient in coefficients.items()
                )
                per_seed.append(float(estimate))
                seed_contrasts.append(
                    {
                        "target": target,
                        "contrast_id": contrast_id,
                        "seed": seed,
                        "estimate_kg": estimate,
                        "interpretation": (
                            "difference between fixed finite-budget training procedures"
                        ),
                    }
                )
            contrast_points[(target, contrast_id)] = np.asarray(per_seed, dtype=np.float64)

    validation_strata = [_stratum_key(row) for row in validation_rows]
    stratum_groups: dict[tuple[object, ...], list[int]] = {}
    for index, key in enumerate(validation_strata):
        stratum_groups.setdefault(key, []).append(index)
    if len(stratum_groups) != 768 or any(len(indices) != 4 for indices in stratum_groups.values()):
        raise QualificationError("post-seal validation stratum membership/counts changed")
    influence_by_config_target: dict[tuple[str, int], np.ndarray] = {}
    influence_supported = True
    truth = np.asarray([_truth_target(row) for row in validation_rows], dtype=np.float64)
    for config in CONFIGS:
        for target_index in range(3):
            seed_errors = np.stack(
                [
                    validation_predictions[(config, seed)][:, target_index] - truth[:, target_index]
                    for seed in INIT_SEEDS
                ]
            )
            scales = np.asarray(
                [rmse[(config, seed, target_index)] for seed in INIT_SEEDS], dtype=np.float64
            )
            if not np.isfinite(scales).all() or np.any(scales <= 0):
                influence_supported = False
                continue
            influence_by_config_target[(config, target_index)] = np.mean(
                (np.square(seed_errors) - np.square(scales)[:, None]) / (2.0 * scales[:, None]),
                axis=0,
            )
    envelope_supported = influence_supported
    multiplier_maxima: list[float] = []
    multiplier_digest: str | None = None
    multiplier_coordinates: dict[tuple[str, str], np.ndarray] = {}
    multiplier_coordinate_sums = np.zeros(21, dtype=np.float64)
    multiplier_coordinate_squares = np.zeros(21, dtype=np.float64)
    q = 0.0
    if envelope_supported:
        contrast_influences = np.empty((3_072, 21), dtype=np.float64)
        column = 0
        for target_index, target in enumerate(EXPECTED_TARGETS):
            for contrast_id, _description, coefficients in CONTRASTS:
                influence = np.zeros(3_072, dtype=np.float64)
                for config, coefficient in coefficients.items():
                    influence += coefficient * influence_by_config_target[(config, target_index)]
                for indices in stratum_groups.values():
                    local = influence[indices]
                    influence[indices] = np.sqrt(4.0 / 3.0) * (local - local.mean()) / 3_072
                contrast_influences[:, column] = influence
                multiplier_coordinates[(target, contrast_id)] = influence
                column += 1
        generator = np.random.Generator(np.random.PCG64(293901))
        draw_hash = hashlib.sha256(b"PSR_RES293_RADEMACHER_0_1_DRAWS_V1\0")
        for _ in range(200):
            bits = generator.integers(0, 2, size=(100, 3_072), dtype=np.int64)
            draw_hash.update(bits.astype("<i8", copy=False).tobytes(order="C"))
            weights = np.where(bits == 0, -1.0, 1.0)
            deltas = weights @ contrast_influences
            if not np.isfinite(deltas).all():
                envelope_supported = False
                break
            multiplier_maxima.extend(np.max(np.abs(deltas), axis=1).tolist())
            multiplier_coordinate_sums += deltas.sum(axis=0)
            multiplier_coordinate_squares += np.square(deltas).sum(axis=0)
        multiplier_digest = draw_hash.hexdigest()
        if (
            envelope_supported
            and len(multiplier_maxima) == 20_000
            and np.isfinite(multiplier_maxima).all()
        ):
            q = float(np.quantile(np.asarray(multiplier_maxima), 0.95, method="higher"))
            if q == 0.0:
                envelope_supported = False
        else:
            envelope_supported = False

    contrast_rows: list[dict[str, object]] = []
    coordinate_rows: list[dict[str, object]] = []
    column = 0
    for target in EXPECTED_TARGETS:
        for contrast_id, description, _coefficients in CONTRASTS:
            seed_values = contrast_points[(target, contrast_id)]
            estimate = float(seed_values.mean())
            coordinate = (
                multiplier_coordinates.get((target, contrast_id)) if influence_supported else None
            )
            zero_variability = coordinate is None or not bool(np.any(coordinate))
            coordinate_rows.append(
                {
                    "target": target,
                    "contrast_id": contrast_id,
                    "influence_coordinate_all_zero": zero_variability,
                    "influence_coordinate_sd": None
                    if coordinate is None
                    else float(coordinate.std(ddof=0)),
                    "multiplier_delta_sd_kg": (
                        None
                        if len(multiplier_maxima) != 20_000
                        else float(
                            np.sqrt(
                                max(
                                    0.0,
                                    multiplier_coordinate_squares[column] / 20_000
                                    - (multiplier_coordinate_sums[column] / 20_000) ** 2,
                                )
                            )
                        )
                    ),
                }
            )
            contrast_rows.append(
                {
                    "evaluation_id": EVALUATION_ID,
                    "target": target,
                    "contrast_id": contrast_id,
                    "definition": description,
                    "estimate_kg": estimate,
                    "seed_count": len(seed_values),
                    "per_seed_min_kg": float(seed_values.min()),
                    "per_seed_max_kg": float(seed_values.max()),
                    "descriptive_envelope_method": (
                        "shared-entity Rademacher multiplier; 20,000 draws; method=higher"
                        if envelope_supported
                        else "UNSUPPORTED"
                    ),
                    "envelope_sampling_coverage": "not qualified",
                    "envelope_min_kg": estimate - q if envelope_supported else None,
                    "envelope_max_kg": estimate + q if envelope_supported else None,
                    "shared_envelope_half_width_kg": q if envelope_supported else None,
                    "interpretation": (
                        "difference between these fixed finite-budget training procedures"
                    ),
                    "decision_classification": (
                        "none; no significance, equivalence, or materiality rule"
                    ),
                }
            )
            column += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "canonical-metrics.csv", metrics_rows)
    _write_csv(output_dir / "development-metrics.csv", development_metrics)
    _write_csv(output_dir / "per-seed-primary-contrasts.csv", seed_contrasts)
    _write_csv(output_dir / "primary-contrasts.csv", contrast_rows)
    _write_csv(output_dir / "contrast-influence-diagnostics.csv", coordinate_rows)
    if multiplier_maxima:
        with (output_dir / "multiplier-maxima.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            csv_writer = csv.writer(stream)
            csv_writer.writerow(("draw", "maximum_absolute_influence_kg"))
            csv_writer.writerows(
                (index + 1, value) for index, value in enumerate(multiplier_maxima)
            )
    with (output_dir / "prediction-seal-index.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        dict_writer = csv.DictWriter(
            stream, fieldnames=("config", "seed", "file", "sha256", "rows")
        )
        dict_writer.writeheader()
        dict_writer.writerows(prediction_inventory)
    for item in seal["fits"]:
        source = run_dir / item["state_artifact"]["file"]
        local_state_root = ROOT / "models/checkpoints/res293-definition-b"
        local_state_root.mkdir(parents=True, exist_ok=True)
        destination = local_state_root / source.name
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
        if sha256_file(destination) != item["state_artifact"]["sha256"]:
            raise QualificationError(f"private sealed state copy mismatch: {destination.name}")
    try:
        protocol_file = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError(
            "frozen executable protocol is unavailable during analysis"
        ) from error
    protocol_digest = str(protocol_file["protocol_digest"])
    protocol_id = str(protocol_file["protocol_id"])
    analysis_identity = sha256_record(
        {
            "format": "PSR_RES293_ANALYSIS_ID_V1",
            "protocol_digest": protocol_digest,
            "realization_digest": REALIZATION_DIGEST,
            "evaluation_id": EVALUATION_ID,
            "prediction_seal_sha256": sha256_file(run_dir / "seal-manifest.json"),
            "contrast_definitions": CONTRASTS,
            "uncertainty": "descriptive 20k Rademacher envelope, no coverage or decision claims",
        }
    )
    analysis_receipt = {
        "format": "PSR_RES293_ANALYSIS_RECEIPT_V1",
        "status": "COMPLETE"
        if len(contrast_rows) == 21 and len(seed_contrasts) == 105
        else "INCOMPLETE",
        "run_id": seal["run_id"],
        "protocol_id": protocol_id,
        "protocol_digest": protocol_digest,
        "analysis_identity": analysis_identity,
        "realization_id": REALIZATION_ID,
        "realization_digest": REALIZATION_DIGEST,
        "dataset_spec_id": DATASET_SPEC_ID,
        "benchmark_spec_id": BENCHMARK_ID,
        "evaluation_id": EVALUATION_ID,
        "canonical_metric_identities": [item.metric_id for item in METRIC_IDENTITIES],
        "train_sha256": TRAIN_SHA256,
        "validation_sha256": VALIDATION_SHA256,
        "split_digest": SPLIT_DIGEST,
        "fit_count": seal["fit_count"],
        "primary_contrast_count": len(contrast_rows),
        "per_seed_contrast_count": len(seed_contrasts),
        "uncertainty": {
            "status": "DESCRIPTIVE_ONLY" if envelope_supported else "UNSUPPORTED",
            "draw_count": len(multiplier_maxima),
            "seed": 293901,
            "draw_sha256": multiplier_digest,
            "quantile": 0.95,
            "quantile_method": "higher",
            "label": "descriptive first-order multiplier envelope; sampling coverage not qualified",
            "all_seed_target_rmse_positive": influence_supported,
            "shared_envelope_half_width_kg": q if envelope_supported else None,
            "no_significance_equivalence_materiality_or_superiority_classifications": True,
            "zero_multiplier_maxima": bool(multiplier_maxima)
            and all(value == 0.0 for value in multiplier_maxima),
        },
        "claims": {
            "estimand": "differences between fixed finite-budget training procedures",
            "nonlinear_architecture_necessary": False,
            "optimal_linear_frontier_established": False,
            "human_athlete_validity": False,
            "independent_confirmation": False,
        },
        "evaluation_truth_accessed_after_complete_fit_seal": True,
        "prediction_seal_sha256": sha256_file(run_dir / "seal-manifest.json"),
        "checkpoint_distribution": "withheld; local ignored state files retained by SHA-256 only",
        "output_hashes": {},
    }
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "analysis-receipt.json":
            analysis_receipt["output_hashes"][path.name] = sha256_file(path)
    _write_json(output_dir / "analysis-receipt.json", analysis_receipt)
    return cast(dict[str, object], analysis_receipt)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise QualificationError(f"cannot write empty evidence table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
