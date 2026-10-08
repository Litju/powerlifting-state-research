"""Train and evaluate the frozen three-seed PUBLIC_NATIVE temporal expert."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import tempfile
import uuid
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import torch
from torch import Tensor

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset,
    evaluate,
)
from ..contracts.datasets import DatasetRealizationManifest
from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..evaluation.prediction import (
    PredictionRow,
    canonical_prediction_jsonl,
    parse_prediction_jsonl,
)
from ..evaluation.protocols import EvaluationResult
from ..models.references import (
    CheckpointReference,
    DeterminismStatus,
    EnvironmentProvenance,
    FittedInstanceReference,
    RNGProvenance,
    TrainingProtocolReference,
)
from .temporal_expert import (
    LIFT_KEYS,
    MODEL_SPEC_ID,
    LiftSharedTemporalExpert,
    NormalizationStats,
    TemporalModelBatch,
    TemporalModelInput,
    load_weights,
    predict,
    predict_three_seed_ensemble,
    prepare_batch,
    save_weights,
)
from .training import (
    PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL as PROTOCOL,
)
from .training import (
    TRAINING_PROTOCOL_ID,
    training_protocol_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_DRIVE_RES274_ROOT = Path("/content/drive/MyDrive/powerlifting-state-research/res274")
PROTOCOL_MANIFEST_PATH = (
    REPOSITORY_ROOT / "artifacts/training-protocols/public-native-temporal-expert.json"
)
PROTOCOL_SCHEMA = "PSR_TRAINING_PROTOCOL_V1"
SPLIT_SCHEMA = "PSR_INTERNAL_SELECTION_SPLIT_V1"
NORMALIZATION_SCHEMA = "PSR_NORMALIZATION_STATS_V1"
CHECKPOINT_SCHEMA = "PSR_CHECKPOINT_MANIFEST_V1"
HISTORY_SCHEMA = "PSR_TRAINING_HISTORY_V1"
TRAINING_RUN_SCHEMA = "PSR_TRAINING_RUN_V1"
RUN_RECEIPT_SCHEMA = "PSR_RUN_RECEIPT_V1"
SEAL_SCHEMA = "PSR_SEED_CHECKPOINT_SEAL_V1"
EVALUATION_ORDER_SCHEMA = "PSR_VALIDATION_EVALUATION_ORDER_V1"
ENSEMBLE_SCHEMA = "PSR_ENSEMBLE_MANIFEST_V1"
INVENTORY_SCHEMA = "PSR_SHA256_INVENTORY_V1"
FINAL_RECEIPT_SCHEMA = "PSR_FINAL_RUN_RECEIPT_V1"
EXPECTED_SEEDS = (383001, 383002, 383003)
EXPECTED_DATASET_MANIFEST = (
    REPOSITORY_ROOT
    / "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/"
    "iid-production.json"
)
HISTORICAL_CHECKPOINT_HASHES = frozenset(
    {
        "b41fd12298fffb44d86087198fbfec1151acef4f34d6446a8f40e249da1984fb",
        "6169d437ff152ecb75c5d3d9f2bc7b84d522d059e191faf10798bba8c81899a5",
        "7d2994106ae0ee33a44973f8550836ac099fdbf59c253d533da4f3c0424ad0c0",
    }
)


class TrainingError(RuntimeError):
    """A frozen-protocol, data-qualification, or artifact verification failure."""


@dataclass(frozen=True, slots=True)
class InternalSplit:
    fit_rows: tuple[dataset.PublicForecastRow, ...]
    selection_rows: tuple[dataset.PublicForecastRow, ...]
    manifest: dict[str, object]


@dataclass(frozen=True, slots=True)
class QualifiedDataset:
    root: Path
    manifest_path: Path
    manifest: DatasetRealizationManifest
    train_sha256: str
    validation_sha256: str
    train_row_count: int
    validation_row_count: int
    train_rows: tuple[dataset.PublicForecastRow, ...]
    smoke_only: bool = False


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_json(path: Path, value: object) -> bytes:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TrainingError(f"invalid JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise TrainingError(f"JSON artifact must be an object: {path.name}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_committed_protocol() -> None:
    expected = canonical_json_bytes(training_protocol_manifest()) + b"\n"
    try:
        actual = PROTOCOL_MANIFEST_PATH.read_bytes()
    except OSError as error:
        raise TrainingError("committed training protocol manifest is missing") from error
    if actual != expected:
        raise TrainingError("committed training protocol manifest differs from Python authority")


def _git_identity(code_sha: str, *, require_clean: bool = True) -> dict[str, object]:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise TrainingError("Git source identity is unavailable") from error
    if len(code_sha) != 40 or any(char not in "0123456789abcdef" for char in code_sha.lower()):
        raise TrainingError("CODE_SHA must be a full 40-character Git commit SHA")
    if head.lower() != code_sha.lower():
        raise TrainingError(f"source HEAD {head} differs from CODE_SHA")
    if require_clean and status:
        raise TrainingError("source worktree must be clean before training/evaluation")
    return {
        "code_sha": head,
        "git_tree_sha": tree,
        "git_tree_status": "clean" if not status else "dirty",
    }


def configure_determinism(seed: int) -> dict[str, object]:
    """Apply and report the frozen deterministic controls before model creation."""
    if type(seed) is not int or seed < 0:
        raise ValueError("training seed must be a non-negative integer")
    workspace = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if workspace not in (None, ":4096:8"):
        raise TrainingError("CUBLAS_WORKSPACE_CONFIG must be :4096:8")
    if workspace is None:
        if torch.cuda.is_initialized():  # type: ignore[no-untyped-call]
            raise TrainingError("CUBLAS_WORKSPACE_CONFIG must be set before CUDA initialization")
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    return {
        "seed": seed,
        "python_seed": seed,
        "numpy_seed": seed,
        "torch_cpu_seed": seed,
        "torch_cuda_seeds": seed if cuda_available else None,
        "torch_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "cross_gpu_bitwise_guarantee": False,
    }


def _parse_row_line(line: bytes, line_number: int) -> dataset.PublicForecastRow:
    raw = line.removesuffix(b"\n")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=evaluate._object,  # type: ignore[attr-defined]
            parse_constant=evaluate._reject_constant,  # type: ignore[attr-defined]
        )
        if canonical_json_bytes(value) != raw:
            raise ValueError("row is not canonical compact JSON")
        return evaluate._parse_truth_row(value)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as error:
        raise TrainingError(f"invalid canonical row {line_number}: {error}") from error


def _read_train_rows(path: Path, expected_count: int) -> tuple[dataset.PublicForecastRow, ...]:
    content = path.read_bytes()
    if not content or not content.endswith(b"\n"):
        raise TrainingError("TRAIN JSONL must be non-empty and newline-terminated")
    rows = tuple(
        _parse_row_line(line, index)
        for index, line in enumerate(content.splitlines(keepends=True), 1)
    )
    if len(rows) != expected_count:
        raise TrainingError(f"TRAIN row count mismatch: {len(rows)} != {expected_count}")
    row_ids = [row.row_id for row in rows]
    entity_ids = [row.inputs.entity_id for row in rows]
    if len(set(row_ids)) != len(rows) or len(set(entity_ids)) != len(rows):
        raise TrainingError("TRAIN rows contain duplicate row or entity identities")
    if row_ids != entity_ids:
        raise TrainingError("the frozen dataset requires row_id == entity_id")
    return rows


def qualify_dataset(dataset_root: Path) -> QualifiedDataset:
    """Verify canonical IID manifest and hashes; parse TRAIN, never score validation."""
    root = dataset_root.resolve()
    if root == REPOSITORY_ROOT or REPOSITORY_ROOT in root.parents:
        raise TrainingError("generated IID data must remain outside the source checkout")
    manifest_path = root / "manifest.json"
    train_path = root / "train.jsonl"
    validation_path = root / "validation.jsonl"
    try:
        expected_manifest_bytes = EXPECTED_DATASET_MANIFEST.read_bytes()
        expected_manifest = json.loads(expected_manifest_bytes)
        if canonical_json_bytes(expected_manifest) + b"\n" != expected_manifest_bytes:
            raise ValueError("checked-in DatasetRealization manifest is not canonical")
        expected_train_artifact = next(
            item for item in expected_manifest["artifact_hashes"] if item["artifact_id"] == "train"
        )
        expected_train_split = next(
            item for item in expected_manifest["split_identities"] if item["split_id"] == "train"
        )
        expected_validation_split = next(
            item
            for item in expected_manifest["split_identities"]
            if item["split_id"] == "validation"
        )
        manifest = evaluate._parse_manifest(manifest_path, evaluate.CANONICAL_VALIDATION)
        train_bytes = train_path.read_bytes()
        validation_bytes = validation_path.read_bytes()
    except (OSError, ValueError) as error:
        raise TrainingError(f"canonical IID dataset qualification failed: {error}") from error
    train_sha = hashlib.sha256(train_bytes).hexdigest()
    validation_sha = hashlib.sha256(validation_bytes).hexdigest()
    binding = evaluate.CANONICAL_VALIDATION
    if manifest_path.read_bytes() != expected_manifest_bytes:
        raise TrainingError(
            "regenerated DatasetRealization manifest differs from checked-in authority"
        )
    expected_train_sha = str(expected_train_artifact["sha256"])
    expected_train_rows = int(expected_train_split["row_count"])
    expected_validation_rows = int(expected_validation_split["row_count"])
    if train_sha != expected_train_sha:
        raise TrainingError("canonical TRAIN SHA-256 mismatch")
    if (
        validation_sha != binding.validation_sha256
        or validation_sha != PROTOCOL.dataset_validation_sha256
    ):
        raise TrainingError("canonical validation SHA-256 mismatch")
    if expected_train_sha != PROTOCOL.dataset_train_sha256:
        raise TrainingError("checked-in TRAIN SHA differs from frozen training protocol")
    if expected_train_rows != PROTOCOL.train_row_count:
        raise TrainingError("checked-in TRAIN row count differs from frozen training protocol")
    if expected_validation_rows != PROTOCOL.validation_row_count:
        raise TrainingError("checked-in validation row count differs from frozen training protocol")
    if not train_bytes.endswith(b"\n") or train_bytes.count(b"\n") != expected_train_rows:
        raise TrainingError("canonical TRAIN row count or JSONL termination mismatch")
    if (
        not validation_bytes.endswith(b"\n")
        or validation_bytes.count(b"\n") != expected_validation_rows
    ):
        raise TrainingError("canonical validation row count or JSONL termination mismatch")
    rows = _read_train_rows(train_path, expected_train_rows)
    if (
        manifest.dataset_spec_id != PROTOCOL.dataset_spec_id
        or manifest.identity_id != binding.realization_id
        or manifest.realization_digest != binding.realization_digest
    ):
        raise TrainingError("DatasetRealization differs from frozen protocol")
    return QualifiedDataset(
        root,
        manifest_path,
        manifest,
        train_sha,
        validation_sha,
        expected_train_rows,
        expected_validation_rows,
        rows,
    )


def _history_template(
    row: dataset.PublicForecastRow,
    lift_key: Literal["squat", "bench_press", "deadlift"],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (segment.start_day, segment.end_day, segment.dose, segment.intensity)
        for segment in row.inputs.lifts[lift_key].history_schedule
    )


def _stratum_key(row: dataset.PublicForecastRow) -> tuple[object, ...]:
    return (
        row.inputs.declared_future_plan.plan_id,
        row.inputs.horizon_days,
        *(
            _history_template(row, cast(Literal["squat", "bench_press", "deadlift"], lift))
            for lift in LIFT_KEYS
        ),
    )


def _id_list_sha256(row_ids: Sequence[str]) -> str:
    return hashlib.sha256(canonical_json_bytes(sorted(row_ids))).hexdigest()


def _split_identity_payload(
    *,
    realization_id: str,
    realization_digest: str,
    fit_row_ids: Sequence[str],
    selection_row_ids: Sequence[str],
    strata: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "format": SPLIT_SCHEMA,
        "split_rule_digest": sha256_record(PROTOCOL.internal_split),
        "dataset_realization_id": realization_id,
        "dataset_realization_digest": realization_digest,
        "fit_row_count": len(fit_row_ids),
        "selection_row_count": len(selection_row_ids),
        "fit_row_ids_sha256": _id_list_sha256(fit_row_ids),
        "selection_row_ids_sha256": _id_list_sha256(selection_row_ids),
        "strata": tuple(strata),
    }


def make_internal_split(
    rows: Sequence[dataset.PublicForecastRow],
    *,
    realization_id: str,
    realization_digest: str,
    protocol_id: str = TRAINING_PROTOCOL_ID,
) -> InternalSplit:
    """Hash-rank rows within plan × horizon × three-lift schedule-template strata."""
    if not rows:
        raise TrainingError("cannot split an empty TRAIN set")
    if len({row.row_id for row in rows}) != len(rows):
        raise TrainingError("TRAIN row IDs must be unique before splitting")
    groups: dict[tuple[object, ...], list[dataset.PublicForecastRow]] = defaultdict(list)
    for row in rows:
        if row.row_id != row.inputs.entity_id:
            raise TrainingError("internal splitting requires row_id == entity_id")
        groups[_stratum_key(row)].append(row)

    fit_rows: list[dataset.PublicForecastRow] = []
    selection_rows: list[dataset.PublicForecastRow] = []
    strata: list[dict[str, object]] = []
    for key, group in groups.items():
        if len(group) < 2:
            raise TrainingError(
                "every plan/horizon/history-template stratum needs at least two rows"
            )
        count = max(1, min(len(group) - 1, len(group) // 5))
        ranked = sorted(
            group,
            key=lambda row: (hashlib.sha256(row.row_id.encode("utf-8")).hexdigest(), row.row_id),
        )
        selection = ranked[:count]
        fit = ranked[count:]
        selection_rows.extend(selection)
        fit_rows.extend(fit)
        strata.append(
            {
                "stratum_sha256": hashlib.sha256(canonical_json_bytes(key)).hexdigest(),
                "row_count": len(group),
                "fit_row_count": len(fit),
                "selection_row_count": len(selection),
            }
        )

    fit_ids = tuple(sorted(row.row_id for row in fit_rows))
    selection_ids = tuple(sorted(row.row_id for row in selection_rows))
    if set(fit_ids) & set(selection_ids):
        raise TrainingError("internal fit and selection rows overlap")
    if len(fit_ids) + len(selection_ids) != len(rows):
        raise TrainingError("internal split does not cover the complete TRAIN set")
    if {_stratum_key(row) for row in fit_rows} != {_stratum_key(row) for row in selection_rows}:
        raise TrainingError("fit/selection split failed to preserve exact declared support")
    strata.sort(key=lambda item: cast(str, item["stratum_sha256"]))
    identity = _split_identity_payload(
        realization_id=realization_id,
        realization_digest=realization_digest,
        fit_row_ids=fit_ids,
        selection_row_ids=selection_ids,
        strata=strata,
    )
    digest = sha256_record(identity)
    manifest: dict[str, object] = {
        **identity,
        "training_protocol_id": protocol_id,
        "internal_selection_split_id": (
            "psr:internal-selection-split:public-native-temporal-expert@sha256:"
            f"{digest.removeprefix('sha256:')}"
        ),
        "split_digest": digest,
        "selection_rule": PROTOCOL.identity_payload()["internal_split"],
        "entity_disjoint": True,
        "support_preserved": True,
        "fit_row_ids": fit_ids,
        "selection_row_ids": selection_ids,
    }
    return InternalSplit(tuple(fit_rows), tuple(selection_rows), manifest)


def _inputs_and_targets(
    rows: Sequence[dataset.PublicForecastRow],
) -> tuple[tuple[TemporalModelInput, ...], tuple[tuple[float, float, float], ...]]:
    targets = tuple(
        (
            float(row.targets["squat_delta_capacity_kg"]),
            float(row.targets["bench_press_delta_capacity_kg"]),
            float(row.targets["deadlift_delta_capacity_kg"]),
        )
        for row in rows
    )
    return (
        tuple(TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in rows),
        targets,
    )


def _stats_payload(stats: NormalizationStats, split: InternalSplit) -> dict[str, object]:
    values = stats.to_dict()
    digest = sha256_record(values)
    return {
        "format": NORMALIZATION_SCHEMA,
        "normalization_stats_id": (
            "psr:normalization-stats:public-native-temporal-expert@sha256:"
            f"{digest.removeprefix('sha256:')}"
        ),
        "stats_digest": digest,
        "stats": values,
        "fit_only": True,
        "fit_row_count": len(split.fit_rows),
        "fit_row_ids_sha256": split.manifest["fit_row_ids_sha256"],
        "selection_used_for_fit": False,
    }


def _protocol_setting(name: str) -> object:
    return dict(PROTOCOL.checkpoint_selection)[name]


def _indexed_batch(batch: TemporalModelBatch, indices: Tensor) -> TemporalModelBatch:
    return TemporalModelBatch(
        batch.history.index_select(0, indices),
        batch.history_mask.index_select(0, indices),
        batch.plan_numeric.index_select(0, indices),
        batch.plan_index.index_select(0, indices),
    )


def _selection_loss(
    model: LiftSharedTemporalExpert,
    batch: TemporalModelBatch,
    targets: Tensor,
    batch_size: int,
) -> float:
    total_squared_error = 0.0
    count = 0
    model.eval()
    with torch.inference_mode():
        for start in range(0, targets.shape[0], batch_size):
            stop = min(start + batch_size, targets.shape[0])
            indexes = torch.arange(start, stop, device=targets.device)
            prediction_z = model(_indexed_batch(batch, indexes))
            errors = prediction_z - targets[start:stop]
            total_squared_error += float(torch.square(errors).sum(dtype=torch.float64).item())
            count += errors.numel()
    if count == 0:
        raise TrainingError("internal selection subset is empty")
    result = total_squared_error / count
    if not math.isfinite(result):
        raise TrainingError("internal selection loss is non-finite")
    return result


def _set_learning_rate(
    optimizer: torch.optim.Optimizer,
    step: int,
    *,
    base_lr: float,
    min_lr: float,
    warmup_steps: int,
    total_steps: int,
) -> float:
    if warmup_steps and step < warmup_steps:
        learning_rate = base_lr * (step + 1) / warmup_steps
    else:
        span = max(total_steps - warmup_steps - 1, 1)
        progress = min(max((step - warmup_steps) / span, 0.0), 1.0)
        learning_rate = min_lr + (base_lr - min_lr) * (1 + math.cos(math.pi * progress)) / 2
    for group in optimizer.param_groups:
        group["lr"] = learning_rate
    return learning_rate


def _train_one_seed(
    seed: int,
    fit_inputs: Sequence[TemporalModelInput],
    fit_targets: Sequence[tuple[float, float, float]],
    selection_inputs: Sequence[TemporalModelInput],
    selection_targets: Sequence[tuple[float, float, float]],
    stats: NormalizationStats,
    output_dir: Path,
    *,
    protocol: Any,
    device: torch.device,
    runtime_receipt: Mapping[str, Any],
    runtime_receipt_sha256: str,
    normalization_id: str,
    split_id: str,
) -> dict[str, object]:
    settings = dict(protocol.checkpoint_selection)
    configure_determinism(seed)
    model = LiftSharedTemporalExpert().to(device)
    fit_batch = prepare_batch(fit_inputs, stats).tensors.to(device)
    selection_batch = prepare_batch(selection_inputs, stats).tensors.to(device)
    mean = torch.tensor(stats.target_mean, dtype=torch.float32, device=device)
    scale = torch.tensor(stats.target_scale, dtype=torch.float32, device=device)
    y_fit = (torch.tensor(fit_targets, dtype=torch.float32, device=device) - mean) / scale
    y_selection = (
        torch.tensor(selection_targets, dtype=torch.float32, device=device) - mean
    ) / scale

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=protocol.learning_rate,
        betas=protocol.betas,
        eps=protocol.epsilon,
        weight_decay=protocol.weight_decay,
    )
    batch_size = protocol.batch_size
    steps_per_epoch = math.ceil(len(fit_inputs) / batch_size)
    warmup_steps = protocol.warmup_epochs * steps_per_epoch
    total_steps = protocol.maximum_epochs * steps_per_epoch
    order_generator = torch.Generator(device="cpu").manual_seed(seed)
    best_loss = math.inf
    best_epoch = 0
    best_state: dict[str, Tensor] | None = None
    stale_epochs = 0
    global_step = 0
    epochs: list[dict[str, object]] = []

    for epoch in range(1, protocol.maximum_epochs + 1):
        model.train()
        epoch_loss_sum = 0.0
        epoch_count = 0
        epoch_lrs: list[float] = []
        order = torch.randperm(len(fit_inputs), generator=order_generator)
        for start in range(0, len(fit_inputs), batch_size):
            indexes = order[start : start + batch_size].to(device)
            learning_rate = _set_learning_rate(
                optimizer,
                global_step,
                base_lr=protocol.learning_rate,
                min_lr=protocol.minimum_learning_rate,
                warmup_steps=warmup_steps,
                total_steps=total_steps,
            )
            epoch_lrs.append(learning_rate)
            optimizer.zero_grad(set_to_none=True)
            prediction_z = model(_indexed_batch(fit_batch, indexes))
            errors = prediction_z - y_fit.index_select(0, indexes)
            loss = torch.square(errors).mean()
            loss_value = float(loss.detach().item())
            if not math.isfinite(loss_value):
                raise TrainingError(f"seed {seed} produced a non-finite fitting loss")
            loss.backward()  # type: ignore[no-untyped-call]
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), protocol.gradient_clip_norm, error_if_nonfinite=True
            )
            optimizer.step()
            epoch_loss_sum += loss_value * len(indexes)
            epoch_count += len(indexes)
            global_step += 1

        train_loss = epoch_loss_sum / epoch_count
        selection_loss = _selection_loss(model, selection_batch, y_selection, batch_size)
        if not math.isfinite(train_loss):
            raise TrainingError(f"seed {seed} produced a non-finite epoch fitting loss")
        improved = best_epoch == 0 or selection_loss < best_loss - float(
            settings["minimum_improvement"]
        )
        if improved:
            best_loss = selection_loss
            best_epoch = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            stale_epochs = 0
        else:
            stale_epochs += 1
        epochs.append(
            {
                "epoch": epoch,
                "train_standardized_mse": train_loss,
                "selection_standardized_mse": selection_loss,
                "learning_rate_min": min(epoch_lrs),
                "learning_rate_max": max(epoch_lrs),
                "checkpoint_improved": improved,
                "epochs_since_improvement": stale_epochs,
            }
        )
        if epoch >= int(settings["minimum_epochs"]) and stale_epochs >= int(settings["patience"]):
            break

    if best_state is None or best_epoch == 0:
        raise TrainingError(f"seed {seed} produced no selectable checkpoint")
    model.load_state_dict(best_state, strict=True)
    model.eval()
    output_dir.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_dir / "checkpoint.pt"
    save_weights(checkpoint_path, model)
    checkpoint_sha = _file_sha256(checkpoint_path)
    if checkpoint_sha in HISTORICAL_CHECKPOINT_HASHES:
        raise TrainingError("new checkpoint unexpectedly matches a historical checkpoint hash")
    checkpoint_id = (
        f"psr:checkpoint:public-native-temporal-expert-seed-{seed}@sha256:{checkpoint_sha}"
    )
    history_payload: dict[str, object] = {
        "format": HISTORY_SCHEMA,
        "training_protocol_id": protocol.training_protocol_id,
        "training_seed": seed,
        "fit_row_count": len(fit_inputs),
        "selection_row_count": len(selection_inputs),
        "selection_metric": settings["metric"],
        "best_epoch": best_epoch,
        "best_selection_loss": best_loss,
        "epochs_completed": len(epochs),
        "epochs": tuple(epochs),
    }
    history_digest = sha256_record(history_payload)
    history_id = (
        f"psr:training-history:public-native-temporal-expert-seed-{seed}"
        f"@sha256:{history_digest.removeprefix('sha256:')}"
    )
    history_payload.update({"training_history_id": history_id, "history_digest": history_digest})
    _write_json(output_dir / "training-history.json", history_payload)
    fitted_payload: dict[str, object] = {
        "format": "PSR_FITTED_INSTANCE_V1",
        "model_id": protocol.model_id,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_realization_id": protocol.dataset_realization_id,
        "internal_selection_split_id": split_id,
        "normalization_stats_id": normalization_id,
        "training_seed": seed,
        "selected_epoch": best_epoch,
        "checkpoint_id": checkpoint_id,
        "checkpoint_sha256": checkpoint_sha,
    }
    fitted_digest = sha256_record(fitted_payload)
    fitted_id = (
        f"psr:fitted-instance:public-native-temporal-expert-seed-{seed}"
        f"@sha256:{fitted_digest.removeprefix('sha256:')}"
    )
    fitted_payload.update(
        {"fitted_instance_id": fitted_id, "fitted_instance_digest": fitted_digest}
    )
    _write_json(output_dir / "fitted-instance.json", fitted_payload)
    checkpoint_manifest: dict[str, object] = {
        "format": CHECKPOINT_SCHEMA,
        "checkpoint_id": checkpoint_id,
        "checkpoint_sha256": checkpoint_sha,
        "model_id": protocol.model_id,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_realization_id": protocol.dataset_realization_id,
        "training_seed": seed,
        "normalization_stats_id": normalization_id,
        "internal_selection_split_id": split_id,
        "training_history_id": history_id,
        "fitted_instance_id": fitted_id,
        "best_internal_selection_epoch": best_epoch,
        "best_internal_selection_loss": best_loss,
        "selection_metric": settings["metric"],
        "selection_only": True,
        "canonical_validation_used": False,
        "checkpoint_finalized": True,
        "runtime_receipt_sha256": runtime_receipt_sha256,
        "runtime_fingerprint": dict(runtime_receipt),
        "runtime_seed_controls": configure_determinism(seed),
    }
    _write_json(output_dir / "checkpoint-manifest.json", checkpoint_manifest)
    return checkpoint_manifest


def _require_runtime_receipt(path: Path, code_sha: str) -> dict[str, Any]:
    receipt = _read_json(path)
    missing = [field for field in PROTOCOL.runtime_receipt_fields if field not in receipt]
    if missing:
        raise TrainingError(f"runtime receipt is missing fields: {', '.join(missing)}")
    if receipt["code_sha"] != code_sha or receipt["git_tree_status"] != "clean":
        raise TrainingError("runtime receipt does not bind the clean CODE_SHA checkout")
    return receipt


def _persist_protocol_and_dataset(
    output_root: Path,
    qualified: QualifiedDataset,
    *,
    protocol: Any = PROTOCOL,
) -> None:
    protocol_dir = output_root / "training-protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)
    protocol_payload = (
        training_protocol_manifest()
        if protocol is PROTOCOL
        else {
            "format": PROTOCOL_SCHEMA,
            "training_protocol_id": protocol.training_protocol_id,
            "protocol_digest": protocol.digest,
            "protocol": protocol.identity_payload(),
            "smoke_only": True,
        }
    )
    protocol_bytes = canonical_json_bytes(protocol_payload) + b"\n"
    path = protocol_dir / "manifest.json"
    if path.exists() and path.read_bytes() != protocol_bytes:
        raise TrainingError("output contains a different training protocol manifest")
    if not path.exists():
        _write_json(path, protocol_payload)
    dataset_dir = output_root / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = dataset_dir / "manifest.json"
    snapshot_bytes = qualified.manifest_path.read_bytes()
    if snapshot_path.exists() and snapshot_path.read_bytes() != snapshot_bytes:
        raise TrainingError("output contains a different DatasetRealization manifest")
    if not snapshot_path.exists():
        snapshot_path.write_bytes(snapshot_bytes)


def _train_qualified(
    qualified: QualifiedDataset,
    output_root: Path,
    runtime_receipt: Mapping[str, Any],
    source_identity: Mapping[str, object],
    *,
    require_cuda: bool,
    protocol: Any = PROTOCOL,
) -> dict[str, object]:
    output_root = output_root.resolve()
    if output_root == REPOSITORY_ROOT or REPOSITORY_ROOT in output_root.parents:
        raise TrainingError("training artifacts must remain outside the source checkout")
    if (
        not qualified.smoke_only
        and output_root.parent != (REQUIRED_DRIVE_RES274_ROOT / "runs").resolve()
    ):
        raise TrainingError("PUBLIC_NATIVE production artifacts must be written directly to Drive")
    if any(
        (output_root / relative).exists()
        for relative in (
            "receipts/checkpoint-seal.json",
            "receipts/validation-evaluation.json",
            "receipts/training-run.json",
            "receipts/seed-evaluation-run.json",
            "receipts/ensemble-evaluation-run.json",
            "receipts/final-sha256.json",
            "receipts/final-receipt.json",
            "ensemble/ensemble-manifest.json",
        )
    ) or any((output_root / f"seed-{seed}").exists() for seed in protocol.seeds):
        raise TrainingError(
            "training cannot replace checkpoints or continue after a run has started"
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if require_cuda and device.type != "cuda":
        raise TrainingError(
            "CUDA is required for PUBLIC_NATIVE production training; CPU fallback is forbidden"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    _persist_protocol_and_dataset(output_root, qualified, protocol=protocol)
    split = make_internal_split(
        qualified.train_rows,
        realization_id=qualified.manifest.identity_id,
        realization_digest=qualified.manifest.realization_digest,
        protocol_id=protocol.training_protocol_id,
    )
    if not qualified.smoke_only and (
        split.manifest["internal_selection_split_id"] != protocol.internal_selection_split_id
        or split.manifest["split_digest"] != protocol.internal_selection_split_digest
        or len(split.fit_rows) != protocol.internal_fit_row_count
        or len(split.selection_rows) != protocol.internal_selection_row_count
    ):
        raise TrainingError("generated internal split differs from frozen training protocol")
    split_dir = output_root / "split"
    split_dir.mkdir(parents=True, exist_ok=True)
    _write_json(split_dir / "internal-selection-split.json", split.manifest)

    fit_inputs, fit_targets = _inputs_and_targets(split.fit_rows)
    selection_inputs, selection_targets = _inputs_and_targets(split.selection_rows)
    stats = NormalizationStats.fit_train(fit_inputs, fit_targets)
    stats_payload = _stats_payload(stats, split)
    normalization_id = cast(str, stats_payload["normalization_stats_id"])
    normalization_dir = output_root / "normalization"
    normalization_dir.mkdir(parents=True, exist_ok=True)
    _write_json(normalization_dir / "normalization-stats.json", stats_payload)

    seed_records: list[dict[str, object]] = []
    runtime_sha = hashlib.sha256(canonical_json_bytes(runtime_receipt) + b"\n").hexdigest()
    for seed in protocol.seeds:
        seed_dir = output_root / f"seed-{seed}"
        if seed_dir.exists():
            raise TrainingError(f"seed output already exists: seed-{seed}")
        record = _train_one_seed(
            seed,
            fit_inputs,
            fit_targets,
            selection_inputs,
            selection_targets,
            stats,
            seed_dir,
            protocol=protocol,
            device=device,
            runtime_receipt=runtime_receipt,
            runtime_receipt_sha256=runtime_sha,
            normalization_id=normalization_id,
            split_id=cast(str, split.manifest["internal_selection_split_id"]),
        )
        seed_records.append(record)

    if tuple(record["training_seed"] for record in seed_records) != tuple(protocol.seeds):
        raise TrainingError("training did not finalize the exact declared seed sequence")
    sealed_at = _now()
    seal_payload: dict[str, object] = {
        "format": SEAL_SCHEMA,
        "training_protocol_id": protocol.training_protocol_id,
        "declared_seeds": tuple(protocol.seeds),
        "seed_checkpoints": tuple(seed_records),
        "sealed_at_utc": sealed_at,
        "all_seed_checkpoints_sealed": True,
        "canonical_validation_scored": False,
    }
    seal_digest = sha256_record(seal_payload)
    seal_payload.update(
        {"checkpoint_seal_id": f"psr:checkpoint-seal@{seal_digest}", "seal_digest": seal_digest}
    )
    receipt_dir = output_root / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    seal_bytes = _write_json(receipt_dir / "checkpoint-seal.json", seal_payload)

    training_run: dict[str, object] = {
        "format": TRAINING_RUN_SCHEMA,
        "run_uuid": str(uuid.uuid4()),
        "created_at_utc": sealed_at,
        "status": "CHECKPOINTS_SEALED",
        "smoke_only": qualified.smoke_only,
        "model_id": protocol.model_id,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_spec_id": protocol.dataset_spec_id,
        "dataset_realization_id": qualified.manifest.identity_id,
        "dataset_realization_digest": qualified.manifest.realization_digest,
        "train_sha256": qualified.train_sha256,
        "validation_sha256": qualified.validation_sha256,
        "train_row_count": len(qualified.train_rows),
        "validation_row_count": qualified.validation_row_count,
        "internal_selection_split_id": split.manifest["internal_selection_split_id"],
        "normalization_stats_id": normalization_id,
        "declared_seeds": tuple(protocol.seeds),
        "checkpoint_ids": tuple(record["checkpoint_id"] for record in seed_records),
        "checkpoint_sha256": tuple(record["checkpoint_sha256"] for record in seed_records),
        "checkpoint_seal_sha256": hashlib.sha256(seal_bytes).hexdigest(),
        "runtime_receipt_sha256": runtime_sha,
        "source": dict(source_identity),
        "runtime": dict(runtime_receipt),
        "validation_isolation": {
            "canonical_validation_scored": False,
            "checkpoint_selection_source": "TRAIN-internal selection subset only",
        },
    }
    run_digest = sha256_record(training_run)
    training_run.update(
        {
            "training_run_id": (
                f"psr:training-run:public-native-temporal-expert@sha256:"
                f"{run_digest.removeprefix('sha256:')}"
            ),
            "training_run_digest": run_digest,
        }
    )
    _write_json(receipt_dir / "training-run.json", training_run)
    for record in seed_records:
        print(
            "SEED_CHECKPOINT_SEALED "
            f"seed={record['training_seed']} "
            f"best_internal_selection_epoch={record['best_internal_selection_epoch']} "
            f"selection_loss={cast(float, record['best_internal_selection_loss']):.10g} "
            f"checkpoint_id={record['checkpoint_id']} "
            f"checkpoint_sha256={record['checkpoint_sha256']}"
        )
    print("ALL_SEED_CHECKPOINTS_SEALED=1")
    return training_run


def _load_seal(
    output_root: Path, protocol: Any = PROTOCOL
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    seal = _read_json(output_root / "receipts/checkpoint-seal.json")
    if seal.get("format") != SEAL_SCHEMA or seal.get("all_seed_checkpoints_sealed") is not True:
        raise TrainingError("all declared seed checkpoints have not been sealed")
    if tuple(seal.get("declared_seeds", ())) != tuple(protocol.seeds):
        raise TrainingError("checkpoint seal seed list differs from frozen protocol")
    if seal.get("canonical_validation_scored") is not False:
        raise TrainingError("checkpoint seal must precede canonical validation scoring")
    seal_identity = {
        key: value
        for key, value in seal.items()
        if key not in {"checkpoint_seal_id", "seal_digest"}
    }
    seal_digest = sha256_record(seal_identity)
    if (
        seal.get("seal_digest") != seal_digest
        or seal.get("checkpoint_seal_id") != f"psr:checkpoint-seal@{seal_digest}"
    ):
        raise TrainingError("checkpoint seal identity/hash verification failed")
    records = seal.get("seed_checkpoints")
    if not isinstance(records, list) or tuple(
        item.get("training_seed") for item in records
    ) != tuple(protocol.seeds):
        raise TrainingError("checkpoint seal does not contain exactly the frozen seeds")
    by_seed: dict[int, dict[str, Any]] = {}
    for record in records:
        seed = int(record["training_seed"])
        checkpoint = output_root / f"seed-{seed}/checkpoint.pt"
        manifest = _read_json(output_root / f"seed-{seed}/checkpoint-manifest.json")
        if canonical_json_bytes(record) != canonical_json_bytes(manifest):
            raise TrainingError(f"seal/checkpoint manifest differs for seed {seed}")
        if not checkpoint.is_file() or _file_sha256(checkpoint) != manifest.get(
            "checkpoint_sha256"
        ):
            raise TrainingError(f"sealed checkpoint SHA mismatch for seed {seed}")
        if record.get("checkpoint_sha256") != manifest.get("checkpoint_sha256"):
            raise TrainingError(f"seal/checkpoint manifest mismatch for seed {seed}")
        checkpoint_sha = str(manifest.get("checkpoint_sha256"))
        expected_checkpoint_id = (
            f"psr:checkpoint:public-native-temporal-expert-seed-{seed}@sha256:{checkpoint_sha}"
        )
        if (
            manifest.get("checkpoint_id") != expected_checkpoint_id
            or record.get("checkpoint_id") != expected_checkpoint_id
            or manifest.get("training_seed") != seed
            or manifest.get("model_id") != protocol.model_id
            or manifest.get("training_protocol_id") != protocol.training_protocol_id
        ):
            raise TrainingError(f"checkpoint identity binding mismatch for seed {seed}")
        if manifest.get("checkpoint_finalized") is not True:
            raise TrainingError(f"checkpoint {seed} was not finalized")
        by_seed[seed] = manifest
    return seal, by_seed


def _runtime_environment(receipt: Mapping[str, Any]) -> EnvironmentProvenance:
    identity = {
        key: receipt[key]
        for key in (
            "code_sha",
            "python",
            "package_version",
            "torch_version",
            "torch_build",
            "torch_cuda_version",
            "cudnn_version",
            "nvidia_driver",
            "gpu_name",
            "gpu_memory_bytes",
            "platform",
            "dependency_fingerprint",
        )
    }
    digest = sha256_record(identity)
    gpu_name = str(receipt["gpu_name"] or "CPU")
    hardware = (
        f"{gpu_name}; CUDA {receipt['torch_cuda_version']}; cuDNN {receipt['cudnn_version']}; "
        f"driver {receipt['nvidia_driver']}"
    )
    return EnvironmentProvenance(
        environment_id=f"psr:training-environment@{digest}",
        python_version=str(receipt["python"]),
        platform=str(receipt["platform"]),
        dependency_identity=str(receipt["dependency_fingerprint"]),
        hardware=hardware,
    )


def _bind_training_result(
    result: EvaluationResult,
    *,
    protocol: Any,
    runtime: Mapping[str, Any],
    fitted_instance_id: str,
    fitted_instance_sha256: str,
    checkpoint_id: str | None,
    checkpoint_sha256: str | None,
    seeds: Sequence[int],
) -> EvaluationResult:
    checkpoint_ref = (
        None
        if checkpoint_id is None or checkpoint_sha256 is None
        else CheckpointReference(checkpoint_id, f"sha256:{checkpoint_sha256}")
    )
    return replace(
        result,
        training_protocol=TrainingProtocolReference(protocol.training_protocol_id),
        fitted_instance=FittedInstanceReference(
            fitted_instance_id, f"sha256:{fitted_instance_sha256}"
        ),
        checkpoint=checkpoint_ref,
        environment=_runtime_environment(runtime),
        rng=RNGProvenance(
            DeterminismStatus.SEEDED,
            seeds=tuple(
                (f"{name}_seed_{seed}", int(seed))
                for seed in seeds
                for name in ("python", "numpy", "torch", "torch_cuda")
            ),
        ),
    )


def _predict_batched(
    models: Sequence[LiftSharedTemporalExpert],
    inputs: Sequence[TemporalModelInput],
    stats: NormalizationStats,
    batch_size: int,
) -> tuple[PredictionRow, ...]:
    rows: list[PredictionRow] = []
    for start in range(0, len(inputs), batch_size):
        chunk = inputs[start : start + batch_size]
        if len(models) == 1:
            rows.extend(predict(models[0], chunk, stats))
        else:
            rows.extend(predict_three_seed_ensemble(models, chunk, stats))
    return tuple(rows)


def _load_validation(
    dataset_root: Path,
    *,
    binding: evaluate.ValidationBinding = evaluate.CANONICAL_VALIDATION,
) -> tuple[dataset.PublicForecastRow, ...]:
    try:
        return evaluate._load_truth(
            dataset_root / "validation.jsonl",
            dataset_root / "manifest.json",
            binding,
        )
    except (OSError, ValueError) as error:
        raise TrainingError(
            f"validation qualification failed after checkpoint sealing: {error}"
        ) from error


def _result_payload(result: EvaluationResult) -> dict[str, object]:
    return {
        "format": "PSR_EVALUATION_RESULT_V1",
        "result_id": result.result_id,
        "result": result,
    }


def evaluate_seed_checkpoints(
    dataset_root: Path,
    output_root: Path,
    runtime_receipt_path: Path,
    *,
    code_sha: str,
    protocol: Any = PROTOCOL,
    binding: evaluate.ValidationBinding = evaluate.CANONICAL_VALIDATION,
) -> dict[str, object]:
    """Score canonical validation only after verifying the three-checkpoint seal."""
    _require_committed_protocol()
    source = _git_identity(code_sha)
    runtime = _require_runtime_receipt(runtime_receipt_path, code_sha)
    seal, records = _load_seal(output_root, protocol)
    order_path = output_root / "receipts/validation-evaluation.json"
    if order_path.exists():
        raise TrainingError("canonical validation evaluation has already started for this run")
    started_at = _now()
    order: dict[str, object] = {
        "format": EVALUATION_ORDER_SCHEMA,
        "started_at_utc": started_at,
        "checkpoint_seal_sha256": _file_sha256(output_root / "receipts/checkpoint-seal.json"),
        "checkpoint_sealed_at_utc": seal["sealed_at_utc"],
        "validation_sha256": binding.validation_sha256,
        "seed_checkpoints_sealed_before_scoring": True,
        "canonical_validation_scored": True,
    }
    _write_json(order_path, order)

    truth_rows = _load_validation(dataset_root, binding=binding)
    validation_inputs, _ = _inputs_and_targets(truth_rows)
    stats_payload = _read_json(output_root / "normalization/normalization-stats.json")
    stats = NormalizationStats.from_dict(cast(Mapping[str, Any], stats_payload["stats"]))
    evaluation_records: list[dict[str, object]] = []
    for seed in protocol.seeds:
        seed_dir = output_root / f"seed-{seed}"
        manifest = records[seed]
        model = load_weights(seed_dir / "checkpoint.pt", LiftSharedTemporalExpert())
        model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        predictions = _predict_batched((model,), validation_inputs, stats, protocol.batch_size)
        prediction_path = seed_dir / "predictions.jsonl"
        prediction_path.write_bytes(canonical_prediction_jsonl(predictions))
        raw_result = evaluate.evaluate_files(
            dataset_root / "validation.jsonl",
            prediction_path,
            protocol.model_id,
            manifest_path=dataset_root / "manifest.json",
            validation_binding=binding,
        )
        fitted_payload = _read_json(seed_dir / "fitted-instance.json")
        result = _bind_training_result(
            raw_result,
            protocol=protocol,
            runtime=runtime,
            fitted_instance_id=str(manifest["fitted_instance_id"]),
            fitted_instance_sha256=str(fitted_payload["fitted_instance_digest"]).removeprefix(
                "sha256:"
            ),
            checkpoint_id=str(manifest["checkpoint_id"]),
            checkpoint_sha256=str(manifest["checkpoint_sha256"]),
            seeds=(seed,),
        )
        result_path = seed_dir / "evaluation-result.json"
        _write_json(result_path, _result_payload(result))
        evaluation_records.append(
            {
                "seed": seed,
                "prediction_sha256": _file_sha256(prediction_path),
                "result_id": result.result_id,
                "result_sha256": _file_sha256(result_path),
            }
        )
    evaluation_run = {
        "format": "PSR_SEED_EVALUATION_RUN_V1",
        "started_at_utc": started_at,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_realization_id": binding.realization_id,
        "validation_sha256": binding.validation_sha256,
        "checkpoint_seal_sha256": _file_sha256(output_root / "receipts/checkpoint-seal.json"),
        "seed_results": tuple(evaluation_records),
        "canonical_evaluator": "RES-271 evaluate.evaluate_files",
        "source": dict(source),
    }
    _write_json(output_root / "receipts/seed-evaluation-run.json", evaluation_run)
    return evaluation_run


def build_ensemble(
    dataset_root: Path,
    output_root: Path,
    runtime_receipt_path: Path,
    *,
    code_sha: str,
    protocol: Any = PROTOCOL,
    binding: evaluate.ValidationBinding = evaluate.CANONICAL_VALIDATION,
) -> dict[str, object]:
    _require_committed_protocol()
    source = _git_identity(code_sha)
    runtime = _require_runtime_receipt(runtime_receipt_path, code_sha)
    seal, records = _load_seal(output_root, protocol)
    if not (output_root / "receipts/seed-evaluation-run.json").is_file():
        raise TrainingError("seed results must be evaluated after sealing before the ensemble")
    _read_json(output_root / "receipts/validation-evaluation.json")
    truth_rows = _load_validation(dataset_root, binding=binding)
    validation_inputs, _ = _inputs_and_targets(truth_rows)
    stats_payload = _read_json(output_root / "normalization/normalization-stats.json")
    stats = NormalizationStats.from_dict(cast(Mapping[str, Any], stats_payload["stats"]))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models: list[LiftSharedTemporalExpert] = []
    fitted_ids: list[str] = []
    for seed in protocol.seeds:
        manifest = records[seed]
        model = load_weights(
            output_root / f"seed-{seed}/checkpoint.pt", LiftSharedTemporalExpert()
        ).to(device)
        models.append(model)
        fitted_ids.append(str(manifest["fitted_instance_id"]))
    prediction_rows = _predict_batched(models, validation_inputs, stats, protocol.batch_size)
    ensemble_dir = output_root / "ensemble"
    if ensemble_dir.exists():
        raise TrainingError("ensemble output already exists")
    ensemble_dir.mkdir(parents=True)
    prediction_path = ensemble_dir / "predictions.jsonl"
    prediction_path.write_bytes(canonical_prediction_jsonl(prediction_rows))
    ensemble_identity = {
        "format": ENSEMBLE_SCHEMA,
        "model_id": protocol.model_id,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_realization_id": binding.realization_id,
        "member_fitted_instance_ids": tuple(fitted_ids),
        "seed_order": tuple(protocol.seeds),
        "rule": "equal arithmetic mean in standardized target space; inverse transform once",
        "prediction_sha256": _file_sha256(prediction_path),
    }
    ensemble_digest = sha256_record(ensemble_identity)
    ensemble_id = (
        "psr:ensemble:public-native-temporal-expert-three-seed-standardized-mean"
        f"@sha256:{ensemble_digest.removeprefix('sha256:')}"
    )
    fitted_payload = {
        "format": "PSR_FITTED_INSTANCE_V1",
        "model_id": protocol.model_id,
        "training_protocol_id": protocol.training_protocol_id,
        "dataset_realization_id": binding.realization_id,
        "member_fitted_instance_ids": tuple(fitted_ids),
        "ensemble_id": ensemble_id,
    }
    fitted_digest = sha256_record(fitted_payload)
    fitted_id = (
        "psr:fitted-instance:public-native-temporal-expert-three-seed-ensemble"
        f"@sha256:{fitted_digest.removeprefix('sha256:')}"
    )
    raw_result = evaluate.evaluate_files(
        dataset_root / "validation.jsonl",
        prediction_path,
        protocol.model_id,
        manifest_path=dataset_root / "manifest.json",
        validation_binding=binding,
    )
    result = _bind_training_result(
        raw_result,
        protocol=protocol,
        runtime=runtime,
        fitted_instance_id=fitted_id,
        fitted_instance_sha256=fitted_digest.removeprefix("sha256:"),
        checkpoint_id=None,
        checkpoint_sha256=None,
        seeds=protocol.seeds,
    )
    _write_json(ensemble_dir / "evaluation-result.json", _result_payload(result))
    ensemble_payload = {
        **ensemble_identity,
        "ensemble_id": ensemble_id,
        "ensemble_digest": ensemble_digest,
        "ensemble_fitted_instance_id": fitted_id,
        "ensemble_fitted_instance_digest": fitted_digest,
        "fitted_instance": fitted_payload,
        "evaluation_result_id": result.result_id,
        "evaluation_result_sha256": _file_sha256(ensemble_dir / "evaluation-result.json"),
        "checkpoint_seal_sha256": _file_sha256(output_root / "receipts/checkpoint-seal.json"),
        "checkpoint_sealed_at_utc": seal["sealed_at_utc"],
    }
    _write_json(ensemble_dir / "ensemble-manifest.json", ensemble_payload)
    _write_json(
        output_root / "receipts/ensemble-evaluation-run.json",
        {
            "format": "PSR_ENSEMBLE_EVALUATION_RUN_V1",
            "training_protocol_id": protocol.training_protocol_id,
            "dataset_realization_id": binding.realization_id,
            "validation_sha256": binding.validation_sha256,
            "checkpoint_seal_sha256": _file_sha256(output_root / "receipts/checkpoint-seal.json"),
            "ensemble_id": ensemble_id,
            "prediction_sha256": _file_sha256(prediction_path),
            "result_id": result.result_id,
            "source": dict(source),
        },
    )
    return ensemble_payload


def _summary(output_root: Path) -> None:
    targets = (
        "squat_delta_capacity_kg",
        "bench_press_delta_capacity_kg",
        "deadlift_delta_capacity_kg",
    )
    for label, result_path in (
        *(
            (f"seed-{seed}", output_root / f"seed-{seed}/evaluation-result.json")
            for seed in EXPECTED_SEEDS
        ),
        ("ensemble", output_root / "ensemble/evaluation-result.json"),
    ):
        envelope = _read_json(result_path)
        result = envelope["result"]
        if not isinstance(result, dict):
            raise TrainingError(f"result payload malformed: {result_path.name}")
        print(label)
        print("target RMSE MAE R2 SRE(ddof=0)")
        for target_record in cast(list[dict[str, Any]], result["targets"]):
            if target_record["target"] not in targets:
                raise TrainingError("EvaluationResult contains an unknown target")
            metrics = {item["metric"]: item["value"] for item in target_record["metrics"]}
            print(
                f"{target_record['target']} {metrics['RMSE']} {metrics['MAE']} "
                f"{metrics['R²']} {metrics['SRE(ddof=0)']}"
            )


def _expected_files() -> set[str]:
    expected = {
        "runtime/runtime-receipt.json",
        "training-protocol/manifest.json",
        "dataset/manifest.json",
        "split/internal-selection-split.json",
        "normalization/normalization-stats.json",
        "receipts/checkpoint-seal.json",
        "receipts/training-run.json",
        "receipts/validation-evaluation.json",
        "receipts/seed-evaluation-run.json",
        "receipts/ensemble-evaluation-run.json",
        "receipts/final-sha256.json",
        "receipts/final-receipt.json",
        "ensemble/predictions.jsonl",
        "ensemble/evaluation-result.json",
        "ensemble/ensemble-manifest.json",
    }
    for seed in EXPECTED_SEEDS:
        prefix = f"seed-{seed}/"
        expected.update(
            {
                prefix + "checkpoint.pt",
                prefix + "checkpoint-manifest.json",
                prefix + "fitted-instance.json",
                prefix + "training-history.json",
                prefix + "predictions.jsonl",
                prefix + "evaluation-result.json",
            }
        )
    return expected


def _run_files(output_root: Path) -> set[str]:
    return {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }


def _build_inventory(output_root: Path) -> dict[str, object]:
    excluded = {"receipts/final-sha256.json", "receipts/final-receipt.json"}
    entries = tuple(
        {
            "path": relative,
            "sha256": _file_sha256(output_root / relative),
            "size_bytes": (output_root / relative).stat().st_size,
        }
        for relative in sorted(_run_files(output_root) - excluded)
    )
    return {"format": INVENTORY_SCHEMA, "algorithm": "SHA-256", "entries": entries}


def _bundle(output_root: Path, bundle_path: Path, *, code_sha: str) -> tuple[str, str]:
    if not (output_root / "ensemble/ensemble-manifest.json").is_file():
        raise TrainingError("cannot bundle before seed and ensemble evaluation")
    drive_root = REQUIRED_DRIVE_RES274_ROOT.resolve()
    if output_root.resolve().parent != (drive_root / "runs").resolve():
        raise TrainingError("RUN_OUTPUT must be directly beneath the required Drive runs directory")
    if bundle_path.resolve().parent != (drive_root / "bundles").resolve():
        raise TrainingError(
            "BUNDLE_PATH must be directly beneath the required Drive bundles directory"
        )
    if bundle_path.exists():
        raise TrainingError("bundle path already exists; run IDs are never overwritten")
    if bundle_path.resolve().is_relative_to(output_root.resolve()):
        raise TrainingError("bundle must be outside the run artifact directory")
    expected = _expected_files() - {"receipts/final-sha256.json", "receipts/final-receipt.json"}
    actual = _run_files(output_root)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise TrainingError(f"run artifact layout differs; extra={extra}, missing={missing}")
    inventory = _build_inventory(output_root)
    inventory_bytes = _write_json(output_root / "receipts/final-sha256.json", inventory)
    receipt = {
        "format": FINAL_RECEIPT_SCHEMA,
        "status": "ARTIFACTS_COMPLETE_PENDING_FINAL_VERIFICATION",
        "code_sha": code_sha,
        "model_id": MODEL_SPEC_ID,
        "training_protocol_id": TRAINING_PROTOCOL_ID,
        "dataset_realization_id": PROTOCOL.dataset_realization_id,
        "declared_seeds": EXPECTED_SEEDS,
        "checkpoint_seal_sha256": _file_sha256(output_root / "receipts/checkpoint-seal.json"),
        "validation_evaluation_started_at_utc": _read_json(
            output_root / "receipts/validation-evaluation.json"
        )["started_at_utc"],
        "sha256_inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "bundle_excludes_historical_private_artifacts": True,
    }
    receipt_digest = sha256_record(receipt)
    receipt.update(
        {
            "run_receipt_id": f"psr:run-receipt:public-native-temporal-expert@{receipt_digest}",
            "receipt_digest": receipt_digest,
        }
    )
    _write_json(output_root / "receipts/final-receipt.json", receipt)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        bundle_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for relative in sorted(_run_files(output_root)):
            archive.write(output_root / relative, arcname=relative)
    return str(bundle_path), _file_sha256(bundle_path)


def _verify_split_manifest(split: Mapping[str, Any], protocol: Any) -> None:
    fit_ids = tuple(split.get("fit_row_ids", ()))
    selection_ids = tuple(split.get("selection_row_ids", ()))
    if not fit_ids or not selection_ids or set(fit_ids) & set(selection_ids):
        raise TrainingError("fit and selection row IDs are missing or overlap")
    if tuple(sorted(fit_ids)) != fit_ids or tuple(sorted(selection_ids)) != selection_ids:
        raise TrainingError("split row IDs must be sorted canonically")
    strata = split.get("strata")
    if not isinstance(strata, list) or any(
        item.get("fit_row_count", 0) < 1 or item.get("selection_row_count", 0) < 1
        for item in strata
    ):
        raise TrainingError("split does not preserve support in every stratum")
    identity = _split_identity_payload(
        realization_id=str(split["dataset_realization_id"]),
        realization_digest=str(split["dataset_realization_digest"]),
        fit_row_ids=fit_ids,
        selection_row_ids=selection_ids,
        strata=strata,
    )
    digest = sha256_record(identity)
    if (
        split.get("split_digest") != digest
        or split.get("internal_selection_split_id")
        != (
            "psr:internal-selection-split:public-native-temporal-expert@sha256:"
            f"{digest.removeprefix('sha256:')}"
        )
        or split.get("fit_row_count") != len(fit_ids)
        or split.get("selection_row_count") != len(selection_ids)
        or split.get("fit_row_ids_sha256") != _id_list_sha256(fit_ids)
        or split.get("selection_row_ids_sha256") != _id_list_sha256(selection_ids)
        or split.get("training_protocol_id") != protocol.training_protocol_id
        or split.get("internal_selection_split_id") != protocol.internal_selection_split_id
        or split.get("split_digest") != protocol.internal_selection_split_digest
        or split.get("fit_row_count") != protocol.internal_fit_row_count
        or split.get("selection_row_count") != protocol.internal_selection_row_count
    ):
        raise TrainingError("internal selection split identity/hash verification failed")


def _verify_result(
    result_path: Path,
    prediction_path: Path,
    dataset_root: Path,
    runtime: Mapping[str, Any],
    *,
    protocol: Any,
    binding: evaluate.ValidationBinding,
    fitted_instance_id: str,
    fitted_instance_sha256: str,
    checkpoint_id: str | None,
    checkpoint_sha256: str | None,
    seeds: Sequence[int],
) -> None:
    parse_prediction_jsonl(prediction_path.read_bytes())
    raw_result = evaluate.evaluate_files(
        dataset_root / "validation.jsonl",
        prediction_path,
        protocol.model_id,
        manifest_path=dataset_root / "manifest.json",
        validation_binding=binding,
    )
    expected_result = _bind_training_result(
        raw_result,
        protocol=protocol,
        runtime=runtime,
        fitted_instance_id=fitted_instance_id,
        fitted_instance_sha256=fitted_instance_sha256,
        checkpoint_id=checkpoint_id,
        checkpoint_sha256=checkpoint_sha256,
        seeds=seeds,
    )
    actual = _read_json(result_path)
    if actual.get("result_id") != expected_result.result_id:
        raise TrainingError(f"EvaluationResult identity mismatch: {result_path.name}")
    if canonical_json_bytes(actual.get("result")) != canonical_json_bytes(expected_result):
        raise TrainingError(f"EvaluationResult content mismatch: {result_path.name}")


def _verify_fitted_instance(path: Path, seed: int, protocol: Any) -> dict[str, Any]:
    fitted = _read_json(path)
    identity = {
        key: value
        for key, value in fitted.items()
        if key not in {"fitted_instance_id", "fitted_instance_digest"}
    }
    digest = sha256_record(identity)
    expected_id = (
        f"psr:fitted-instance:public-native-temporal-expert-seed-{seed}"
        f"@sha256:{digest.removeprefix('sha256:')}"
    )
    if (
        fitted.get("fitted_instance_digest") != digest
        or fitted.get("fitted_instance_id") != expected_id
        or fitted.get("training_seed") != seed
        or fitted.get("model_id") != protocol.model_id
        or fitted.get("training_protocol_id") != protocol.training_protocol_id
    ):
        raise TrainingError(f"fitted-instance identity/hash verification failed for seed {seed}")
    return fitted


def _verify_training_history(path: Path, seed: int, protocol: Any) -> dict[str, Any]:
    history = _read_json(path)
    identity = {
        key: value
        for key, value in history.items()
        if key not in {"training_history_id", "history_digest"}
    }
    digest = sha256_record(identity)
    expected_id = (
        f"psr:training-history:public-native-temporal-expert-seed-{seed}"
        f"@sha256:{digest.removeprefix('sha256:')}"
    )
    settings = dict(protocol.checkpoint_selection)
    best_loss = math.inf
    best_epoch = 0
    stale = 0
    completed = 0
    for epoch_record in cast(list[dict[str, Any]], history.get("epochs", [])):
        completed += 1
        epoch = int(epoch_record["epoch"])
        loss = float(epoch_record["selection_standardized_mse"])
        improved = best_epoch == 0 or loss < best_loss - float(settings["minimum_improvement"])
        if improved:
            best_epoch = epoch
            best_loss = loss
            stale = 0
        else:
            stale += 1
        if epoch_record.get("checkpoint_improved") is not improved:
            raise TrainingError(f"selection history improvement flag mismatch for seed {seed}")
        if epoch_record.get("epochs_since_improvement") != stale:
            raise TrainingError(f"selection history patience count mismatch for seed {seed}")
        if epoch >= int(settings["minimum_epochs"]) and stale >= int(settings["patience"]):
            break
    checks = {
        "digest": history.get("history_digest") == digest,
        "id": history.get("training_history_id") == expected_id,
        "seed": history.get("training_seed") == seed,
        "protocol": history.get("training_protocol_id") == protocol.training_protocol_id,
        "best_epoch": history.get("best_epoch") == best_epoch,
        "best_selection_loss": history.get("best_selection_loss") == best_loss,
        "epochs_completed": history.get("epochs_completed") == completed,
    }
    failures = tuple(key for key, passed in checks.items() if not passed)
    if failures:
        raise TrainingError(f"training-history verification failed for seed {seed}: {failures}")
    return history


def _verify_drive_paths(
    drive_res274_root: Path,
    output_root: Path,
    bundle_path: Path,
) -> None:
    expected_root = REQUIRED_DRIVE_RES274_ROOT.resolve()
    drive_root = drive_res274_root.resolve()
    runs_root = (drive_root / "runs").resolve()
    bundles_root = (drive_root / "bundles").resolve()
    output = output_root.resolve()
    bundle = bundle_path.resolve()
    source = REPOSITORY_ROOT.resolve()
    if drive_root != expected_root:
        raise TrainingError("Gate-B Drive root differs from the required project-owned path")
    if output.parent != runs_root or not output.is_dir():
        raise TrainingError("RUN_OUTPUT must exist directly beneath the Drive runs directory")
    if bundle.parent != bundles_root or not bundle.is_file():
        raise TrainingError("BUNDLE_PATH must exist directly beneath the Drive bundles directory")
    if source != Path("/content/psr-src").resolve() or source.is_relative_to(drive_root):
        raise TrainingError(
            "source checkout must be /content/psr-src outside the Drive artifact root"
        )


def verify_run(
    dataset_root: Path,
    output_root: Path,
    bundle_path: Path,
    drive_res274_root: Path,
    *,
    code_sha: str,
) -> None:
    """Verify the sealed run, canonical evaluation artifacts, bundle, and safe layout."""
    _require_committed_protocol()
    _git_identity(code_sha)
    _verify_drive_paths(drive_res274_root, output_root, bundle_path)
    expected = _expected_files()
    actual = _run_files(output_root)
    if actual != expected:
        raise TrainingError(
            f"run tree is incomplete or contains unexpected files: {sorted(actual ^ expected)}"
        )
    if any((output_root / relative).is_symlink() for relative in actual):
        raise TrainingError("run artifacts cannot be symbolic links")
    protocol_bytes = (output_root / "training-protocol/manifest.json").read_bytes()
    if protocol_bytes != canonical_json_bytes(training_protocol_manifest()) + b"\n":
        raise TrainingError("run training protocol manifest differs from committed authority")
    manifest = evaluate._parse_manifest(
        output_root / "dataset/manifest.json", evaluate.CANONICAL_VALIDATION
    )
    if manifest.identity_id != PROTOCOL.dataset_realization_id:
        raise TrainingError("run DatasetRealization identity mismatch")
    qualified = qualify_dataset(dataset_root)
    if (output_root / "dataset/manifest.json").read_bytes() != qualified.manifest_path.read_bytes():
        raise TrainingError("persisted DatasetRealization manifest differs from regenerated data")
    split = _read_json(output_root / "split/internal-selection-split.json")
    _verify_split_manifest(split, PROTOCOL)
    expected_split = make_internal_split(
        qualified.train_rows,
        realization_id=qualified.manifest.identity_id,
        realization_digest=qualified.manifest.realization_digest,
    )
    if canonical_json_bytes(split) != canonical_json_bytes(expected_split.manifest):
        raise TrainingError("internal split does not match the deterministic TRAIN-only derivation")
    stats_payload = _read_json(output_root / "normalization/normalization-stats.json")
    stats = NormalizationStats.from_dict(cast(Mapping[str, Any], stats_payload["stats"]))
    stats_digest = sha256_record(stats.to_dict())
    if (
        stats_payload.get("stats_digest") != stats_digest
        or stats_payload.get("fit_only") is not True
        or stats_payload.get("selection_used_for_fit") is not False
        or stats_payload.get("fit_row_ids_sha256") != split.get("fit_row_ids_sha256")
    ):
        raise TrainingError("normalization artifact identity or fit-only provenance is invalid")
    expected_norm_id = (
        f"psr:normalization-stats:public-native-temporal-expert@sha256:"
        f"{stats_digest.removeprefix('sha256:')}"
    )
    if stats_payload.get("normalization_stats_id") != expected_norm_id:
        raise TrainingError("normalization stats identity mismatch")
    fit_ids = set(cast(list[str], split["fit_row_ids"]))
    fit_rows = tuple(row for row in qualified.train_rows if row.row_id in fit_ids)
    fit_inputs, fit_targets = _inputs_and_targets(fit_rows)
    if NormalizationStats.fit_train(fit_inputs, fit_targets) != stats:
        raise TrainingError("normalization statistics were not fitted on the frozen fit rows")

    seal, checkpoint_records = _load_seal(output_root)
    if tuple(seal["declared_seeds"]) != EXPECTED_SEEDS:
        raise TrainingError("run must contain exactly the frozen three seeds")
    order = _read_json(output_root / "receipts/validation-evaluation.json")
    if order.get("seed_checkpoints_sealed_before_scoring") is not True:
        raise TrainingError("canonical validation was not gated behind checkpoint sealing")
    if datetime.fromisoformat(
        str(order["started_at_utc"]).replace("Z", "+00:00")
    ) < datetime.fromisoformat(str(seal["sealed_at_utc"]).replace("Z", "+00:00")):
        raise TrainingError("validation scoring started before checkpoint sealing")
    runtime_path = output_root / "runtime/runtime-receipt.json"
    runtime = _read_json(runtime_path)
    _require_runtime_receipt(runtime_path, code_sha)
    runtime_sha = hashlib.sha256(canonical_json_bytes(runtime) + b"\n").hexdigest()
    training_run = _read_json(output_root / "receipts/training-run.json")
    if (
        training_run.get("training_protocol_id") != TRAINING_PROTOCOL_ID
        or tuple(training_run.get("declared_seeds", ())) != EXPECTED_SEEDS
        or training_run.get("validation_isolation", {}).get("canonical_validation_scored")
        is not False
        or training_run.get("dataset_realization_id") != qualified.manifest.identity_id
        or training_run.get("train_sha256") != qualified.train_sha256
        or training_run.get("validation_sha256") != qualified.validation_sha256
        or training_run.get("train_row_count") != qualified.train_row_count
        or training_run.get("validation_row_count") != qualified.validation_row_count
        or tuple(training_run.get("checkpoint_ids", ()))
        != tuple(checkpoint_records[seed]["checkpoint_id"] for seed in EXPECTED_SEEDS)
        or tuple(training_run.get("checkpoint_sha256", ()))
        != tuple(checkpoint_records[seed]["checkpoint_sha256"] for seed in EXPECTED_SEEDS)
        or training_run.get("runtime_receipt_sha256") != runtime_sha
    ):
        raise TrainingError("training run receipt is incomplete or used canonical validation")
    run_identity = {
        key: value
        for key, value in training_run.items()
        if key not in {"training_run_id", "training_run_digest"}
    }
    run_digest = sha256_record(run_identity)
    if (
        training_run.get("training_run_digest") != run_digest
        or training_run.get("training_run_id")
        != (
            "psr:training-run:public-native-temporal-expert@sha256:"
            f"{run_digest.removeprefix('sha256:')}"
        )
        or training_run.get("runtime_receipt_sha256")
        != hashlib.sha256(canonical_json_bytes(runtime) + b"\n").hexdigest()
        or training_run.get("source", {}).get("code_sha") != code_sha
        or training_run.get("source", {}).get("git_tree_status") != "clean"
    ):
        raise TrainingError("training-run identity/hash verification failed")

    for seed in EXPECTED_SEEDS:
        checkpoint_manifest = checkpoint_records[seed]
        fitted = _verify_fitted_instance(
            output_root / f"seed-{seed}/fitted-instance.json", seed, PROTOCOL
        )
        history = _verify_training_history(
            output_root / f"seed-{seed}/training-history.json", seed, PROTOCOL
        )
        checkpoint_bytes_sha = _file_sha256(output_root / f"seed-{seed}/checkpoint.pt")
        if checkpoint_bytes_sha != checkpoint_manifest.get("checkpoint_sha256"):
            raise TrainingError(f"checkpoint SHA mismatch for seed {seed}")
        if checkpoint_bytes_sha in HISTORICAL_CHECKPOINT_HASHES:
            raise TrainingError("a historical checkpoint entered the public run")
        if (
            fitted.get("checkpoint_id") != checkpoint_manifest.get("checkpoint_id")
            or fitted.get("checkpoint_sha256") != checkpoint_bytes_sha
            or fitted.get("normalization_stats_id") != expected_norm_id
            or fitted.get("internal_selection_split_id") != split["internal_selection_split_id"]
            or history.get("best_epoch") != checkpoint_manifest.get("best_internal_selection_epoch")
            or history.get("best_selection_loss")
            != checkpoint_manifest.get("best_internal_selection_loss")
            or checkpoint_manifest.get("normalization_stats_id") != expected_norm_id
            or checkpoint_manifest.get("internal_selection_split_id")
            != split["internal_selection_split_id"]
            or checkpoint_manifest.get("runtime_receipt_sha256") != runtime_sha
            or checkpoint_manifest.get("runtime_fingerprint") != runtime
        ):
            raise TrainingError(f"seed {seed} checkpoint/fitted/history binding mismatch")
        _verify_result(
            output_root / f"seed-{seed}/evaluation-result.json",
            output_root / f"seed-{seed}/predictions.jsonl",
            dataset_root,
            runtime,
            protocol=PROTOCOL,
            binding=evaluate.CANONICAL_VALIDATION,
            fitted_instance_id=str(fitted["fitted_instance_id"]),
            fitted_instance_sha256=str(fitted["fitted_instance_digest"]).removeprefix("sha256:"),
            checkpoint_id=str(checkpoint_manifest["checkpoint_id"]),
            checkpoint_sha256=checkpoint_bytes_sha,
            seeds=(seed,),
        )
    ensemble = _read_json(output_root / "ensemble/ensemble-manifest.json")
    ensemble_fitted = cast(dict[str, Any], ensemble["fitted_instance"])
    ensemble_identity = {
        key: ensemble[key]
        for key in (
            "format",
            "model_id",
            "training_protocol_id",
            "dataset_realization_id",
            "member_fitted_instance_ids",
            "seed_order",
            "rule",
            "prediction_sha256",
        )
    }
    ensemble_digest = sha256_record(ensemble_identity)
    fitted_identity = {
        key: value
        for key, value in ensemble_fitted.items()
        if key not in {"ensemble_fitted_instance_id", "ensemble_fitted_instance_digest"}
    }
    fitted_digest = sha256_record(fitted_identity)
    if (
        ensemble.get("ensemble_digest") != ensemble_digest
        or ensemble.get("ensemble_id")
        != "psr:ensemble:public-native-temporal-expert-three-seed-standardized-mean"
        f"@sha256:{ensemble_digest.removeprefix('sha256:')}"
        or ensemble.get("ensemble_fitted_instance_digest") != fitted_digest
        or ensemble.get("ensemble_fitted_instance_id")
        != "psr:fitted-instance:public-native-temporal-expert-three-seed-ensemble"
        f"@sha256:{fitted_digest.removeprefix('sha256:')}"
        or ensemble.get("prediction_sha256")
        != _file_sha256(output_root / "ensemble/predictions.jsonl")
    ):
        raise TrainingError("ensemble/fitted-instance identity verification failed")
    _verify_result(
        output_root / "ensemble/evaluation-result.json",
        output_root / "ensemble/predictions.jsonl",
        dataset_root,
        runtime,
        protocol=PROTOCOL,
        binding=evaluate.CANONICAL_VALIDATION,
        fitted_instance_id=str(ensemble["ensemble_fitted_instance_id"]),
        fitted_instance_sha256=str(ensemble["ensemble_fitted_instance_digest"]).removeprefix(
            "sha256:"
        ),
        checkpoint_id=None,
        checkpoint_sha256=None,
        seeds=EXPECTED_SEEDS,
    )
    if (
        tuple(ensemble.get("seed_order", ())) != EXPECTED_SEEDS
        or len(ensemble.get("member_fitted_instance_ids", ())) != 3
    ):
        raise TrainingError("ensemble does not contain exactly the three frozen seed fits")
    if ensemble_fitted.get("member_fitted_instance_ids") != ensemble.get(
        "member_fitted_instance_ids"
    ):
        raise TrainingError("ensemble fitted-instance membership mismatch")

    inventory_path = output_root / "receipts/final-sha256.json"
    inventory_bytes = inventory_path.read_bytes()
    inventory = _read_json(inventory_path)
    entries = cast(list[dict[str, Any]], inventory.get("entries", []))
    actual_entries = _build_inventory(output_root)
    if canonical_json_bytes(inventory) != canonical_json_bytes(actual_entries):
        raise TrainingError("SHA-256 inventory does not match run files")
    receipt = _read_json(output_root / "receipts/final-receipt.json")
    receipt_identity = {
        key: value
        for key, value in receipt.items()
        if key not in {"run_receipt_id", "receipt_digest"}
    }
    receipt_digest = sha256_record(receipt_identity)
    if (
        receipt.get("format") != FINAL_RECEIPT_SCHEMA
        or receipt.get("status") != "ARTIFACTS_COMPLETE_PENDING_FINAL_VERIFICATION"
        or receipt.get("code_sha") != code_sha
        or receipt.get("training_protocol_id") != TRAINING_PROTOCOL_ID
        or tuple(receipt.get("declared_seeds", ())) != EXPECTED_SEEDS
        or receipt.get("sha256_inventory_sha256") != hashlib.sha256(inventory_bytes).hexdigest()
        or receipt.get("receipt_digest") != receipt_digest
        or receipt.get("run_receipt_id")
        != f"psr:run-receipt:public-native-temporal-expert@{receipt_digest}"
    ):
        raise TrainingError("final run receipt is incomplete or inconsistent")
    if len(entries) != len(expected) - 2:
        raise TrainingError("SHA-256 inventory is incomplete")

    for relative in actual:
        lowered = relative.lower()
        if any(token in lowered for token in ("ali383", "ali386", "historical")):
            raise TrainingError("historical/private artifact name found in run output")
        digest = _file_sha256(output_root / relative)
        if digest in HISTORICAL_CHECKPOINT_HASHES:
            raise TrainingError("historical checkpoint bytes found in run output")
        if (output_root / relative).suffix in {".json", ".jsonl", ".txt"}:
            content = (output_root / relative).read_bytes()
            if any(
                marker in content for marker in (b"/home/", b"/Users/", b"/mnt/", b"C:\\Users\\")
            ):
                raise TrainingError("private absolute path found in run artifacts")
    for member in zipfile.ZipFile(bundle_path).namelist():
        if member.startswith("/") or ".." in Path(member).parts:
            raise TrainingError("bundle contains a non-relative or unsafe member path")
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        if names != actual:
            raise TrainingError("bundle contents differ from verified run artifacts")
        for name in sorted(names):
            if archive.read(name) != (output_root / name).read_bytes():
                raise TrainingError(f"bundle file differs from run artifact: {name}")
    print(f"BUNDLE_SHA256={_file_sha256(bundle_path)}")
    print("RES274_COLAB_RUN=PASS")


def _training_summary(qualified: QualifiedDataset) -> dict[str, object]:
    split = make_internal_split(
        qualified.train_rows,
        realization_id=qualified.manifest.identity_id,
        realization_digest=qualified.manifest.realization_digest,
    )
    return {
        "MODEL_ID": MODEL_SPEC_ID,
        "TRAINING_PROTOCOL_ID": TRAINING_PROTOCOL_ID,
        "BenchmarkSpec": {
            "id": PROTOCOL.benchmark_id,
            "digest": PROTOCOL.benchmark_digest,
        },
        "DatasetSpec": PROTOCOL.dataset_spec_id,
        "DatasetRealization": qualified.manifest.identity_id,
        "EVALUATION": PROTOCOL.evaluation_id,
        "train_sha256": qualified.train_sha256,
        "validation_sha256": qualified.validation_sha256,
        "train_row_count": qualified.train_row_count,
        "validation_row_count": qualified.validation_row_count,
        "M3_PredictionContract_sha256": PROTOCOL.prediction_contract_digest,
        "fit_count": len(split.fit_rows),
        "selection_count": len(split.selection_rows),
        "internal_selection_split_id": split.manifest["internal_selection_split_id"],
        "internal_selection_split_sha256": split.manifest["split_digest"],
        "normalization": dict(PROTOCOL.normalization),
        "seeds": PROTOCOL.seeds,
        "optimizer": {
            "name": PROTOCOL.optimizer,
            "lr": PROTOCOL.learning_rate,
            "weight_decay": PROTOCOL.weight_decay,
            "betas": PROTOCOL.betas,
            "eps": PROTOCOL.epsilon,
        },
        "scheduler": PROTOCOL.scheduler,
        "warmup_epochs": PROTOCOL.warmup_epochs,
        "minimum_lr": PROTOCOL.minimum_learning_rate,
        "max_epochs": PROTOCOL.maximum_epochs,
        "selection_metric": dict(PROTOCOL.checkpoint_selection)["metric"],
        "ensemble": dict(PROTOCOL.ensemble),
        "canonical_validation_scored": False,
    }


def _write_smoke_runtime(root: Path) -> tuple[Path, dict[str, Any]]:
    package_version = "0.1.0"
    try:
        from .. import __version__

        package_version = __version__
    except ImportError:
        pass
    deps = sorted(
        (str(dist.metadata["Name"]), dist.version)
        for dist in distributions()
        if dist.metadata.get("Name")
    )
    receipt: dict[str, Any] = {
        "format": "PSR_RUNTIME_RECEIPT_V1",
        "code_sha": "smoke-only",
        "git_tree_status": "clean",
        "python": platform.python_version(),
        "package_version": package_version,
        "torch_version": torch.__version__,
        "torch_build": torch.version.git_version,
        "torch_cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),  # type: ignore[no-untyped-call]
        "gpu_name": "CPU smoke",
        "gpu_memory_bytes": 0,
        "nvidia_driver": None,
        "platform": platform.platform(),
        "dependency_fingerprint": "sha256:"
        + hashlib.sha256(canonical_json_bytes(deps)).hexdigest(),
        "determinism_controls": configure_determinism(EXPECTED_SEEDS[0]),
    }
    path = root / "runtime/runtime-receipt.json"
    _write_json(path, receipt)
    return path, receipt


def smoke() -> None:
    """Run the complete helper pipeline on temporary, tiny synthetic data on CPU."""
    from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting.dataset import (
        GenerationConfig,
        write_public_realization,
    )

    smoke_protocol = replace(
        PROTOCOL,
        maximum_epochs=1,
        warmup_epochs=0,
        checkpoint_selection=(
            ("metric", "equal-target standardized MSE"),
            ("minimum_epochs", 1),
            ("patience", 1),
            ("minimum_improvement", 0.0),
            ("maximum_epochs", 1),
            ("tie_break", "earliest epoch"),
            ("validation_use", "tiny smoke fixture only"),
        ),
    )
    with tempfile.TemporaryDirectory(prefix="psr-res274-smoke-") as temporary:
        root = Path(temporary)
        fixture = write_public_realization(
            root / "fixture",
            GenerationConfig(train_rows=1_548, validation_rows=24),
        )
        smoke_protocol = replace(
            smoke_protocol,
            dataset_realization_id=fixture.manifest.identity_id,
            dataset_realization_digest=fixture.manifest.realization_digest,
        )
        binding = evaluate.ValidationBinding(
            dataset_spec_id=fixture.manifest.dataset_spec_id,
            realization_id=fixture.manifest.identity_id,
            realization_digest=fixture.manifest.realization_digest,
            manifest_digest=fixture.manifest.manifest_digest,
            validation_sha256=fixture.validation_sha256,
            validation_rows=24,
            realization_rows=1_572,
        )
        generated_train_rows = _read_train_rows(fixture.output_directory / "train.jsonl", 1_548)
        groups: dict[tuple[object, ...], list[dataset.PublicForecastRow]] = defaultdict(list)
        for row in generated_train_rows:
            groups[_stratum_key(row)].append(row)
        train_rows = next(tuple(group[:3]) for group in groups.values() if len(group) >= 3)
        validation_rows = evaluate._load_truth(
            fixture.output_directory / "validation.jsonl",
            fixture.output_directory / "manifest.json",
            binding,
        )
        qualified = QualifiedDataset(
            fixture.output_directory,
            fixture.output_directory / "manifest.json",
            fixture.manifest,
            hashlib.sha256(
                b"".join(canonical_json_bytes(row) + b"\n" for row in train_rows)
            ).hexdigest(),
            fixture.validation_sha256,
            len(train_rows),
            24,
            train_rows,
            smoke_only=True,
        )
        smoke_protocol = replace(
            smoke_protocol,
            dataset_train_sha256=qualified.train_sha256,
            dataset_validation_sha256=qualified.validation_sha256,
            train_row_count=qualified.train_row_count,
            validation_row_count=qualified.validation_row_count,
        )
        output_root = root / "run"
        runtime_path, runtime = _write_smoke_runtime(output_root)
        initial_split = make_internal_split(
            train_rows,
            realization_id=fixture.manifest.identity_id,
            realization_digest=fixture.manifest.realization_digest,
            protocol_id=smoke_protocol.training_protocol_id,
        )
        smoke_protocol = replace(
            smoke_protocol,
            internal_selection_split_id=str(initial_split.manifest["internal_selection_split_id"]),
            internal_selection_split_digest=str(initial_split.manifest["split_digest"]),
            internal_fit_row_count=len(initial_split.fit_rows),
            internal_selection_row_count=len(initial_split.selection_rows),
        )
        split = make_internal_split(
            train_rows,
            realization_id=fixture.manifest.identity_id,
            realization_digest=fixture.manifest.realization_digest,
            protocol_id=smoke_protocol.training_protocol_id,
        )
        assert (
            split.manifest
            == make_internal_split(
                train_rows,
                realization_id=fixture.manifest.identity_id,
                realization_digest=fixture.manifest.realization_digest,
                protocol_id=smoke_protocol.training_protocol_id,
            ).manifest
        )
        _train_qualified(
            qualified,
            output_root,
            runtime,
            {"code_sha": "smoke-only", "git_tree_sha": "smoke-only", "git_tree_status": "clean"},
            require_cuda=False,
            protocol=smoke_protocol,
        )
        seal, records = _load_seal(output_root, smoke_protocol)
        assert seal["all_seed_checkpoints_sealed"] is True
        for seed in smoke_protocol.seeds:
            _verify_fitted_instance(
                output_root / f"seed-{seed}/fitted-instance.json", seed, smoke_protocol
            )
            history = _verify_training_history(
                output_root / f"seed-{seed}/training-history.json", seed, smoke_protocol
            )
            assert history["best_epoch"] == 1
        stats_payload = _read_json(output_root / "normalization/normalization-stats.json")
        stats = NormalizationStats.from_dict(cast(Mapping[str, Any], stats_payload["stats"]))
        validation_inputs, _ = _inputs_and_targets(validation_rows)
        receipt_dir = output_root / "receipts"
        receipt_dir.mkdir(exist_ok=True)
        _write_json(
            receipt_dir / "validation-evaluation.json",
            {
                "format": EVALUATION_ORDER_SCHEMA,
                "started_at_utc": _now(),
                "checkpoint_seal_sha256": _file_sha256(receipt_dir / "checkpoint-seal.json"),
                "checkpoint_sealed_at_utc": seal["sealed_at_utc"],
                "validation_sha256": fixture.validation_sha256,
                "seed_checkpoints_sealed_before_scoring": True,
                "canonical_validation_scored": False,
                "smoke_fixture_only": True,
            },
        )
        models: list[LiftSharedTemporalExpert] = []
        for seed in smoke_protocol.seeds:
            seed_dir = output_root / f"seed-{seed}"
            model = load_weights(seed_dir / "checkpoint.pt", LiftSharedTemporalExpert())
            predictions = _predict_batched(
                (model,), validation_inputs, stats, smoke_protocol.batch_size
            )
            prediction_path = seed_dir / "predictions.jsonl"
            prediction_path.write_bytes(canonical_prediction_jsonl(predictions))
            result = evaluate.evaluate_files(
                fixture.output_directory / "validation.jsonl",
                prediction_path,
                smoke_protocol.model_id,
                manifest_path=fixture.output_directory / "manifest.json",
                validation_binding=binding,
            )
            fitted = _read_json(seed_dir / "fitted-instance.json")
            bound = _bind_training_result(
                result,
                protocol=smoke_protocol,
                runtime=runtime,
                fitted_instance_id=str(records[seed]["fitted_instance_id"]),
                fitted_instance_sha256=str(fitted["fitted_instance_digest"]).removeprefix(
                    "sha256:"
                ),
                checkpoint_id=str(records[seed]["checkpoint_id"]),
                checkpoint_sha256=str(records[seed]["checkpoint_sha256"]),
                seeds=(seed,),
            )
            _write_json(seed_dir / "evaluation-result.json", _result_payload(bound))
            models.append(model)
        ensemble_rows = _predict_batched(
            models, validation_inputs, stats, smoke_protocol.batch_size
        )
        ensemble_dir = output_root / "ensemble"
        ensemble_dir.mkdir()
        ensemble_predictions = ensemble_dir / "predictions.jsonl"
        ensemble_predictions.write_bytes(canonical_prediction_jsonl(ensemble_rows))
        ensemble_result = evaluate.evaluate_files(
            fixture.output_directory / "validation.jsonl",
            ensemble_predictions,
            smoke_protocol.model_id,
            manifest_path=fixture.output_directory / "manifest.json",
            validation_binding=binding,
        )
        parse_prediction_jsonl(ensemble_predictions.read_bytes())
        assert ensemble_result.targets
        member_ids = tuple(
            str(records[seed]["fitted_instance_id"]) for seed in smoke_protocol.seeds
        )
        ensemble_identity = {
            "format": ENSEMBLE_SCHEMA,
            "model_id": smoke_protocol.model_id,
            "training_protocol_id": smoke_protocol.training_protocol_id,
            "dataset_realization_id": binding.realization_id,
            "member_fitted_instance_ids": member_ids,
            "seed_order": tuple(smoke_protocol.seeds),
            "rule": "equal arithmetic mean in standardized target space; inverse transform once",
            "prediction_sha256": _file_sha256(ensemble_predictions),
        }
        ensemble_digest = sha256_record(ensemble_identity)
        ensemble_id = (
            "psr:ensemble:public-native-temporal-expert-three-seed-standardized-mean"
            f"@sha256:{ensemble_digest.removeprefix('sha256:')}"
        )
        fitted_payload = {
            "format": "PSR_FITTED_INSTANCE_V1",
            "model_id": smoke_protocol.model_id,
            "training_protocol_id": smoke_protocol.training_protocol_id,
            "dataset_realization_id": binding.realization_id,
            "member_fitted_instance_ids": member_ids,
            "ensemble_id": ensemble_id,
        }
        fitted_digest = sha256_record(fitted_payload)
        fitted_id = (
            "psr:fitted-instance:public-native-temporal-expert-three-seed-ensemble"
            f"@sha256:{fitted_digest.removeprefix('sha256:')}"
        )
        bound_ensemble_result = _bind_training_result(
            ensemble_result,
            protocol=smoke_protocol,
            runtime=runtime,
            fitted_instance_id=fitted_id,
            fitted_instance_sha256=fitted_digest.removeprefix("sha256:"),
            checkpoint_id=None,
            checkpoint_sha256=None,
            seeds=smoke_protocol.seeds,
        )
        result_path = ensemble_dir / "evaluation-result.json"
        _write_json(result_path, _result_payload(bound_ensemble_result))
        _write_json(
            ensemble_dir / "ensemble-manifest.json",
            {
                **ensemble_identity,
                "ensemble_id": ensemble_id,
                "ensemble_digest": ensemble_digest,
                "ensemble_fitted_instance_id": fitted_id,
                "ensemble_fitted_instance_digest": fitted_digest,
                "fitted_instance": fitted_payload,
                "evaluation_result_id": bound_ensemble_result.result_id,
                "evaluation_result_sha256": _file_sha256(result_path),
            },
        )
        assert all(
            (output_root / f"seed-{seed}/checkpoint.pt").is_file() for seed in EXPECTED_SEEDS
        )
    print("SMOKE_NOT_SCIENTIFIC_RESULT=1")
    print("TINY_CPU_SMOKE=PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser(
        "inspect", help="qualify IID data and print frozen split/protocol"
    )
    inspect.add_argument("--dataset-root", type=Path, required=True)
    inspect.add_argument("--code-sha", required=True)
    train = commands.add_parser("train", help="train and seal exactly the three production seeds")
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--output-root", type=Path, required=True)
    train.add_argument("--runtime-receipt", type=Path, required=True)
    train.add_argument("--code-sha", required=True)
    seed_eval = commands.add_parser("evaluate-seeds", help="evaluate sealed seed checkpoints")
    seed_eval.add_argument("--dataset-root", type=Path, required=True)
    seed_eval.add_argument("--output-root", type=Path, required=True)
    seed_eval.add_argument("--runtime-receipt", type=Path, required=True)
    seed_eval.add_argument("--code-sha", required=True)
    ensemble = commands.add_parser("ensemble", help="build/evaluate the exact three-seed ensemble")
    ensemble.add_argument("--dataset-root", type=Path, required=True)
    ensemble.add_argument("--output-root", type=Path, required=True)
    ensemble.add_argument("--runtime-receipt", type=Path, required=True)
    ensemble.add_argument("--code-sha", required=True)
    summary = commands.add_parser("summary", help="print target-wise seed and ensemble metrics")
    summary.add_argument("--output-root", type=Path, required=True)
    bundle = commands.add_parser(
        "bundle", help="write inventory, receipt, and compressed run bundle"
    )
    bundle.add_argument("--output-root", type=Path, required=True)
    bundle.add_argument("--bundle-path", type=Path, required=True)
    bundle.add_argument("--code-sha", required=True)
    verify = commands.add_parser("verify", help="verify run, evaluation, bundle, and receipts")
    verify.add_argument("--dataset-root", type=Path, required=True)
    verify.add_argument("--output-root", type=Path, required=True)
    verify.add_argument("--bundle-path", type=Path, required=True)
    verify.add_argument("--drive-res274-root", type=Path, required=True)
    verify.add_argument("--code-sha", required=True)
    commands.add_parser("smoke", help="run the temporary CPU smoke pipeline")
    args = parser.parse_args(argv)
    try:
        if args.command == "smoke":
            smoke()
            return 0
        if args.command == "summary":
            _summary(args.output_root)
            return 0
        if args.command == "inspect":
            _require_committed_protocol()
            _git_identity(args.code_sha)
            qualified = qualify_dataset(args.dataset_root)
            print(json.dumps(_training_summary(qualified), indent=2, sort_keys=True))
            return 0
        if args.command == "train":
            _require_committed_protocol()
            _git_identity(args.code_sha)
            runtime = _require_runtime_receipt(args.runtime_receipt, args.code_sha)
            qualified = qualify_dataset(args.dataset_root)
            _train_qualified(
                qualified,
                args.output_root.resolve(),
                runtime,
                _git_identity(args.code_sha),
                require_cuda=True,
            )
            return 0
        if args.command == "evaluate-seeds":
            evaluate_seed_checkpoints(
                args.dataset_root.resolve(),
                args.output_root.resolve(),
                args.runtime_receipt.resolve(),
                code_sha=args.code_sha,
            )
            return 0
        if args.command == "ensemble":
            build_ensemble(
                args.dataset_root.resolve(),
                args.output_root.resolve(),
                args.runtime_receipt.resolve(),
                code_sha=args.code_sha,
            )
            return 0
        if args.command == "bundle":
            _require_committed_protocol()
            _git_identity(args.code_sha)
            path, digest = _bundle(
                args.output_root.resolve(), args.bundle_path.resolve(), code_sha=args.code_sha
            )
            print(f"BUNDLE_PATH={path}")
            print(f"BUNDLE_SHA256={digest}")
            return 0
        if args.command == "verify":
            verify_run(
                args.dataset_root.resolve(),
                args.output_root.resolve(),
                args.bundle_path.resolve(),
                args.drive_res274_root.resolve(),
                code_sha=args.code_sha,
            )
            return 0
    except (TrainingError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
