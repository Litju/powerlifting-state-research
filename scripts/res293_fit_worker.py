"""Outcome-blind CPU fitter for the frozen RES-293 six-configuration study."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import signal
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn

CONFIGS = {
    "C1": ("S", "L"),
    "C2": ("O", "L"),
    "C3": ("S", "N"),
    "C4": ("O", "N"),
    "C5": ("S_CONTEXT", "N"),
    "C6": ("S_ASSESSMENT_LOAD_OMITTED", "N"),
}
INIT_SEEDS = (293201, 293202, 293203, 293204, 293205)
BATCH_SEEDS = (293301, 293302, 293303, 293304, 293305)
TARGETS = (
    "squat_delta_capacity_kg",
    "bench_press_delta_capacity_kg",
    "deadlift_delta_capacity_kg",
)
METRIC_EPOCHS = frozenset((1, 10, 20, 30, 40, 50, 60))
N_FIT = 9_984
N_DEVELOPMENT = 2_304
N_VALIDATION = 3_072
WIDTH = 874
BATCH_SIZE = 256
EPOCHS = 60
UPDATES_PER_EPOCH = 39
GIB = 1024**3
HARD_RSS_CEILING_BYTES = 16 * GIB
HOST_OS_RESERVE_BYTES = 2 * GIB


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_json_bytes(value))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_digest(name: str, value: np.ndarray) -> bytes:
    array = np.ascontiguousarray(value)
    return (
        name.encode("utf-8")
        + b"\0"
        + str(array.dtype).encode("ascii")
        + b"\0"
        + _json_bytes(array.shape)
        + array.tobytes(order="C")
    )


def _state_digest(model: nn.Module) -> str:
    digest = hashlib.sha256(b"PSR_RES293_STATE_V1\0")
    for name, parameter in model.named_parameters():
        value = parameter.detach().cpu().numpy().astype("<f4", copy=False)
        digest.update(_array_digest(name, value))
    return digest.hexdigest()


def _new_model(learner: str) -> nn.Module:
    if learner == "L":
        return nn.Linear(WIDTH, 3, bias=True)
    if learner == "N":
        return nn.Sequential(nn.Linear(WIDTH, 32), nn.ReLU(), nn.Linear(32, 3))
    raise ValueError(f"unknown learner {learner}")


def initialize_model(model: nn.Module, seed: int) -> dict[str, object]:
    """Use only the dedicated initialization stream; all biases are exactly zero."""
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    for module in model.modules():
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.01, generator=generator)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
    bias_tensors = [
        {"name": name, "shape": list(parameter.shape), "values": parameter.tolist()}
        for name, parameter in model.named_parameters()
        if name.endswith("bias")
    ]
    biases = [parameter for name, parameter in model.named_parameters() if name.endswith("bias")]
    if any(bool(torch.count_nonzero(value)) for value in biases):
        raise RuntimeError("learner initialization produced a nonzero bias")
    return {
        "seed": seed,
        "weight_distribution": "independent_normal_mean_0_sd_0.01_layer_order",
        "biases": "exact_zero",
        "bias_parameter_count": sum(value.numel() for value in biases),
        "bias_nonzero_count": sum(int(torch.count_nonzero(value)) for value in biases),
        "initial_bias_tensors": bias_tensors,
        "initial_state_sha256": _state_digest(model),
    }


def _model_arrays(model: nn.Module) -> dict[str, np.ndarray]:
    return {
        name: parameter.detach().cpu().numpy().astype("<f4", copy=True)
        for name, parameter in model.named_parameters()
    }


def _canonical_predictions(row_ids: np.ndarray, values: np.ndarray) -> bytes:
    if values.shape != (len(row_ids), 3) or not np.isfinite(values).all():
        raise ValueError("prediction matrix has wrong shape or a non-finite value")
    if len(set(str(value) for value in row_ids.tolist())) != len(row_ids):
        raise ValueError("prediction row IDs are not unique")
    records = []
    for row_id, row in zip(row_ids.tolist(), values.tolist(), strict=True):
        records.append(
            {
                "row_id": str(row_id),
                TARGETS[0]: float(row[0]),
                TARGETS[1]: float(row[1]),
                TARGETS[2]: float(row[2]),
            }
        )
    return b"".join(_json_bytes(row) for row in records)


def _predict(model: nn.Module, features: np.ndarray, mean: Tensor, scale: Tensor) -> np.ndarray:
    model.eval()
    result: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(features), 512):
            batch = torch.from_numpy(features[start : start + 512])
            standardized = model(batch).cpu().numpy().astype(np.float64, copy=False)
            result.append(standardized * scale.numpy() + mean.numpy())
    return np.concatenate(result, axis=0)


def _config_features(config: str, values: np.ndarray) -> np.ndarray:
    masked = values.copy()
    if config == "C5":
        masked[:, :864] = np.float32(0.0)
    elif config == "C6":
        positions = [
            39 * lift + 5 * channel + summary
            for lift in range(3)
            for channel in (0, 1, 3, 4)
            for summary in range(5)
        ]
        masked[:, positions] = np.float32(0.0)
    if not np.isfinite(masked).all():
        raise ValueError(f"masked feature matrix is non-finite for {config}")
    return masked


def _load_payload(path: Path) -> dict[str, np.ndarray]:
    required = {
        "fit_s",
        "fit_o",
        "fit_y_kg",
        "development_s",
        "development_o",
        "development_row_ids",
        "validation_s",
        "validation_o",
        "validation_row_ids",
    }
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != required:
            raise ValueError("fit payload has missing or forbidden fields")
        arrays = {key: archive[key] for key in required}
    expected = {
        "fit_s": (N_FIT, WIDTH),
        "fit_o": (N_FIT, WIDTH),
        "fit_y_kg": (N_FIT, 3),
        "development_s": (N_DEVELOPMENT, WIDTH),
        "development_o": (N_DEVELOPMENT, WIDTH),
        "development_row_ids": (N_DEVELOPMENT,),
        "validation_s": (N_VALIDATION, WIDTH),
        "validation_o": (N_VALIDATION, WIDTH),
        "validation_row_ids": (N_VALIDATION,),
    }
    if any(arrays[name].shape != shape for name, shape in expected.items()):
        raise ValueError("fit payload shape differs from the frozen study contract")
    for name in (
        "fit_s",
        "fit_o",
        "development_s",
        "development_o",
        "validation_s",
        "validation_o",
    ):
        if arrays[name].dtype != np.dtype("float32"):
            raise ValueError(f"fit feature array {name} must be float32")
        if not np.isfinite(arrays[name]).all():
            raise ValueError(f"fit payload array {name} has a non-finite value")
    if arrays["fit_y_kg"].dtype != np.dtype("float64"):
        raise ValueError("fit targets must be float64 kg values")
    for name in ("development_row_ids", "validation_row_ids"):
        if arrays[name].dtype.kind not in ("U", "S"):
            raise ValueError(f"fit payload array {name} is not a string key vector")
        if len(set(arrays[name].tolist())) != len(arrays[name]):
            raise ValueError(f"fit payload array {name} contains duplicate keys")
    return arrays


def _fit_one(
    *,
    payload: dict[str, np.ndarray],
    config: str,
    seed_index: int,
    output: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    representation, learner = CONFIGS[config]
    init_seed = INIT_SEEDS[seed_index]
    batch_seed = BATCH_SEEDS[seed_index]
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    features = torch.from_numpy(
        _config_features(config, payload["fit_s"])
        if representation.startswith("S")
        else payload["fit_o"]
    )
    fit_targets = torch.from_numpy(payload["fit_y_kg"].astype(np.float64, copy=False))
    target_mean = fit_targets.mean(dim=0)
    target_scale = fit_targets.std(dim=0, unbiased=False).clamp_min(1e-6)
    targets = ((fit_targets - target_mean) / target_scale).to(torch.float32)
    torch.manual_seed(init_seed)
    model = _new_model(learner).to(device="cpu", dtype=torch.float32)
    init_record = initialize_model(model, init_seed)
    initial_digest = str(init_record["initial_state_sha256"])
    weight_parameters = [
        parameter for name, parameter in model.named_parameters() if name.endswith("weight")
    ]
    bias_parameters = [
        parameter for name, parameter in model.named_parameters() if name.endswith("bias")
    ]
    optimizer = torch.optim.AdamW(
        (
            {"params": weight_parameters, "weight_decay": 1e-4},
            {"params": bias_parameters, "weight_decay": 0.0},
        ),
        lr=0.003,
        betas=(0.9, 0.999),
        eps=1e-8,
        foreach=False,
        fused=False,
    )
    batch_generator = torch.Generator(device="cpu")
    batch_generator.manual_seed(batch_seed)
    diagnostics: list[dict[str, object]] = []
    update_count = 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        permutation = torch.randperm(N_FIT, generator=batch_generator)
        for start in range(0, N_FIT, BATCH_SIZE):
            indices = permutation[start : start + BATCH_SIZE]
            batch_x = features.index_select(0, indices)
            batch_y = targets.index_select(0, indices)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_x)
            loss = torch.mean((prediction - batch_y) ** 2)
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError(f"non-finite training loss at {config}, seed {init_seed}")
            loss.backward()
            optimizer.step()
            update_count += 1
        if epoch in METRIC_EPOCHS:
            model.eval()
            with torch.no_grad():
                full_loss = torch.mean((model(features) - targets) ** 2).item()
            if not np.isfinite(full_loss):
                raise FloatingPointError(
                    f"non-finite training diagnostic at {config}, seed {init_seed}"
                )
            diagnostics.append(
                {
                    "config": config,
                    "seed": init_seed,
                    "epoch": epoch,
                    "updates": update_count,
                    "fit_standardized_mse": float(full_loss),
                }
            )
        _check_runtime_memory()
    if update_count != EPOCHS * UPDATES_PER_EPOCH:
        raise AssertionError(f"fit update count mismatch: {update_count}")
    model.eval()
    if any(not bool(torch.isfinite(parameter).all()) for parameter in model.parameters()):
        raise FloatingPointError(f"non-finite final parameter at {config}, seed {init_seed}")
    final_digest = _state_digest(model)
    state_name = f"{config}-seed-{init_seed}.state.npz"
    state_path = output / state_name
    np.savez(state_path, **_model_arrays(model))
    state_file_digest = _sha256(state_path)
    validation_x = payload["validation_s" if representation.startswith("S") else "validation_o"]
    development_x = payload["development_s" if representation.startswith("S") else "development_o"]
    if representation.startswith("S"):
        validation_x = _config_features(config, validation_x)
        development_x = _config_features(config, development_x)
    validation_yhat = _predict(model, validation_x, target_mean, target_scale)
    development_yhat = _predict(model, development_x, target_mean, target_scale)
    validation_name = f"{config}-seed-{init_seed}-validation.jsonl"
    development_name = f"{config}-seed-{init_seed}-development.jsonl"
    validation_path = output / validation_name
    development_path = output / development_name
    validation_path.write_bytes(
        _canonical_predictions(payload["validation_row_ids"], validation_yhat)
    )
    development_path.write_bytes(
        _canonical_predictions(payload["development_row_ids"], development_yhat)
    )
    record: dict[str, object] = {
        "config": config,
        "representation": representation,
        "learner": learner,
        "initialization_seed": init_seed,
        "batch_seed": batch_seed,
        "initial_state_sha256": initial_digest,
        "final_state_sha256": final_digest,
        "state_artifact": {
            "file": state_name,
            "sha256": state_file_digest,
            "bytes": state_path.stat().st_size,
        },
        "prediction_artifacts": {
            "validation": {
                "file": validation_name,
                "sha256": _sha256(validation_path),
                "bytes": validation_path.stat().st_size,
                "rows": N_VALIDATION,
            },
            "development": {
                "file": development_name,
                "sha256": _sha256(development_path),
                "bytes": development_path.stat().st_size,
                "rows": N_DEVELOPMENT,
            },
        },
        "bias_initialization": {
            "parameter_count": init_record["bias_parameter_count"],
            "nonzero_count": init_record["bias_nonzero_count"],
            "policy": init_record["biases"],
            "tensors": init_record["initial_bias_tensors"],
        },
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "epochs": EPOCHS,
        "updates": update_count,
        "fit_rows": N_FIT,
        "batch_size": BATCH_SIZE,
        "row_presentations": N_FIT * EPOCHS,
        "target_mean_kg": target_mean.tolist(),
        "target_scale_kg": target_scale.tolist(),
        "final_epoch_only": True,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "runtime_memory_snapshot": _runtime_memory_snapshot(),
        "wall_seconds": time.perf_counter() - wall_start,
        "cpu_seconds": time.process_time() - cpu_start,
    }
    _write_json(output / f"{config}-seed-{init_seed}.fit.json", record)
    return record, diagnostics


def _environment() -> dict[str, object]:
    if torch.cuda.is_available() or torch.version.cuda is not None:
        raise RuntimeError("RES-293 fit worker requires a CPU-only PyTorch runtime")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
        raise RuntimeError("RES-293 worker did not configure one PyTorch compute thread")
    expected = {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("RES-293 worker thread environment is not single-threaded")
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "torch_cuda_available": torch.cuda.is_available(),
        "torch_version_cuda": torch.version.cuda,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "thread_environment": expected,
        "memory_resources": _runtime_memory_snapshot(),
    }


def _runtime_memory_snapshot() -> dict[str, object]:
    memory: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable"}:
            memory[f"{key}_bytes"] = int(raw.split()[0]) * 1024
    cgroup_path = None
    for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
        fields = line.split(":", 2)
        if len(fields) == 3 and fields[0] == "0" and fields[1] == "":
            cgroup_path = fields[2]
            break
    records = []
    limits: list[int] = []
    current: int | None = None
    if cgroup_path is not None:
        components = [part for part in cgroup_path.strip("/").split("/") if part]
        for length in range(len(components), -1, -1):
            directory = Path("/sys/fs/cgroup").joinpath(*components[:length])
            record: dict[str, object] = {"path": str(directory)}
            for name in ("memory.max", "memory.current", "cpu.max"):
                try:
                    value = (directory / name).read_text(encoding="utf-8").strip()
                except OSError:
                    continue
                record[name] = value
                if name == "memory.max" and value != "max":
                    try:
                        limits.append(int(value))
                    except ValueError:
                        pass
                if name == "memory.current" and current is None:
                    try:
                        current = int(value)
                    except ValueError:
                        pass
            records.append(record)
    return {
        **memory,
        "cgroup_path": cgroup_path,
        "cgroup_ancestors": records,
        "finite_cgroup_memory_limit_bytes": min(limits) if limits else None,
        "cgroup_memory_current_bytes": current,
        "wsl2_guest": "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower(),
        "hard_process_rss_ceiling_bytes": HARD_RSS_CEILING_BYTES,
        "host_os_reserve_bytes": HOST_OS_RESERVE_BYTES,
    }


def _check_runtime_memory() -> None:
    snapshot = _runtime_memory_snapshot()
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if peak_rss > HARD_RSS_CEILING_BYTES:
        raise MemoryError("runtime process RSS exceeded the 16 GiB hard cap")
    if int(snapshot.get("MemAvailable_bytes", 0)) < HOST_OS_RESERVE_BYTES:
        raise MemoryError("runtime available RAM fell below the 2 GiB host reserve")
    cgroup_limit = snapshot.get("finite_cgroup_memory_limit_bytes")
    cgroup_current = snapshot.get("cgroup_memory_current_bytes")
    if (
        isinstance(cgroup_limit, int)
        and isinstance(cgroup_current, int)
        and cgroup_current > cgroup_limit
    ):
        raise MemoryError("runtime cgroup memory use exceeded its finite memory.max")


def execute(payload_path: Path, output: Path, run_id: str) -> None:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("fit output directory is not empty; the fixed campaign is one-shot")
    output.mkdir(parents=True, exist_ok=True)
    _write_json(
        output / "execution-started.json",
        {"format": "PSR_RES293_EXECUTION_START_V1", "run_id": run_id, "started_utc": time.time()},
    )
    env = _environment()
    payload = _load_payload(payload_path)
    records: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    campaign_wall_start = time.perf_counter()
    campaign_cpu_start = time.process_time()

    def per_fit_deadline(_signum: int, _frame: object) -> None:
        raise TimeoutError("hard per-fit 180 second wall-time ceiling exceeded")

    try:
        for config in CONFIGS:
            for seed_index in range(len(INIT_SEEDS)):
                prior_handler = signal.signal(signal.SIGALRM, per_fit_deadline)
                signal.setitimer(signal.ITIMER_REAL, 180.0)
                try:
                    record, losses = _fit_one(
                        payload=payload,
                        config=config,
                        seed_index=seed_index,
                        output=output,
                    )
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0.0)
                    signal.signal(signal.SIGALRM, prior_handler)
                records.append(record)
                diagnostics.extend(losses)
                if float(record["wall_seconds"]) > 180.0:
                    raise TimeoutError("hard per-fit wall-time ceiling exceeded")
                if time.perf_counter() - campaign_wall_start > 21_600.0:
                    raise TimeoutError("hard campaign wall-time ceiling exceeded")
                if time.process_time() - campaign_cpu_start > 21_600.0:
                    raise TimeoutError("hard campaign CPU-time ceiling exceeded")
                if int(record["peak_rss_bytes"]) > HARD_RSS_CEILING_BYTES:
                    raise MemoryError("hard campaign RSS ceiling exceeded")
                runtime_memory = record["runtime_memory_snapshot"]
                if runtime_memory.get("MemAvailable_bytes", 0) < HOST_OS_RESERVE_BYTES or (
                    runtime_memory.get("finite_cgroup_memory_limit_bytes") is not None
                    and runtime_memory.get("cgroup_memory_current_bytes", 0)
                    > runtime_memory["finite_cgroup_memory_limit_bytes"]
                ):
                    raise MemoryError("runtime host reserve or cgroup memory limit was violated")
                disk_bytes = payload_path.stat().st_size + sum(
                    path.stat().st_size for path in output.iterdir() if path.is_file()
                )
                if disk_bytes > 10 * 1024**3:
                    raise OSError("hard temporary/output disk ceiling exceeded")
                _write_json(
                    output / "fit-progress.json",
                    {"completed_fits": len(records), "expected_fits": 30},
                )
    except Exception as error:
        _write_json(
            output / "campaign-failure.json",
            {
                "format": "PSR_RES293_CAMPAIGN_FAILURE_V1",
                "run_id": run_id,
                "completed_fits": len(records),
                "failure_type": type(error).__name__,
                "failure": str(error),
                "fit_records": records,
            },
        )
        raise
    if len(records) != 30:
        raise AssertionError(f"campaign completed {len(records)} fits, expected 30")
    with (output / "training-loss.csv").open("w", encoding="utf-8", newline="") as stream:
        stream.write("config,seed,epoch,updates,fit_standardized_mse\n")
        for item in diagnostics:
            stream.write(
                f"{item['config']},{item['seed']},{item['epoch']},{item['updates']},{item['fit_standardized_mse']:.17g}\n"
            )
    artifacts = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name not in {"seal-manifest.json", "fit-progress.json"}:
            artifacts.append(
                {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
            )
    seal = {
        "format": "PSR_RES293_SEAL_V1",
        "run_id": run_id,
        "state": "all_30_final_states_and_development_validation_predictions_sealed",
        "fit_count": len(records),
        "configs": list(CONFIGS),
        "initialization_seeds": list(INIT_SEEDS),
        "batch_seeds": list(BATCH_SEEDS),
        "environment": env,
        "elapsed_wall_seconds": time.perf_counter() - campaign_wall_start,
        "elapsed_cpu_seconds": time.process_time() - campaign_cpu_start,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "fits": records,
        "artifacts": artifacts,
        "fit_payload_fields": [
            "fit_s",
            "fit_o",
            "fit_y_kg",
            "development_s",
            "development_o",
            "development_row_ids",
            "validation_s",
            "validation_o",
            "validation_row_ids",
        ],
        "development_validation_labels_in_payload": False,
        "checkpoint_distribution": "withheld; hashes retained in evidence",
        "evaluation_truth_opened_by_worker": False,
    }
    _write_json(output / "seal-manifest.json", seal)
    (output / "fit-progress.json").unlink(missing_ok=True)


def _probe_update(model: nn.Module, inputs: Tensor, targets: Tensor, learner: str) -> None:
    weights = [parameter for name, parameter in model.named_parameters() if name.endswith("weight")]
    biases = [parameter for name, parameter in model.named_parameters() if name.endswith("bias")]
    optimizer = torch.optim.AdamW(
        (
            {"params": weights, "weight_decay": 1e-4},
            {"params": biases, "weight_decay": 0.0},
        ),
        lr=0.003,
        betas=(0.9, 0.999),
        eps=1e-8,
        foreach=False,
        fused=False,
    )
    batch_indices = torch.arange(BATCH_SIZE, dtype=torch.int64)
    batch_x = inputs.index_select(0, batch_indices)
    batch_y = targets.index_select(0, batch_indices)
    optimizer.zero_grad(set_to_none=True)
    prediction = model(batch_x)
    output_gradient = 2.0 * (prediction - batch_y) / (BATCH_SIZE * 3)
    torch.autograd.backward(prediction, output_gradient)
    optimizer.step()


def probe(output_path: Path) -> None:
    env = _environment()
    rng = np.random.Generator(np.random.PCG64(293901))
    fit_x = torch.from_numpy(rng.standard_normal((N_FIT, WIDTH), dtype=np.float32))
    _fit_o = torch.zeros((N_FIT, WIDTH), dtype=torch.float32)
    fit_y = torch.from_numpy(rng.standard_normal((N_FIT, 3), dtype=np.float32))
    _development_s = torch.zeros((N_DEVELOPMENT, WIDTH), dtype=torch.float32)
    _development_o = torch.zeros((N_DEVELOPMENT, WIDTH), dtype=torch.float32)
    _validation_s = torch.zeros((N_VALIDATION, WIDTH), dtype=torch.float32)
    _validation_o = torch.zeros((N_VALIDATION, WIDTH), dtype=torch.float32)
    timings: dict[str, list[float]] = {"L": [], "N": []}
    for learner in ("L", "N"):
        _probe_update(_new_model(learner), fit_x, fit_y, learner)
        for _ in range(5):
            model = _new_model(learner)
            start = time.perf_counter()
            _probe_update(model, fit_x, fit_y, learner)
            timings[learner].append(time.perf_counter() - start)
            del model
    # The multiplier dimensions are fixed study arrays, not observed predictions.
    influence = rng.standard_normal((N_VALIDATION, 21), dtype=np.float64)
    sealed_prediction_store = np.zeros((30, N_VALIDATION, 3), dtype=np.float64)
    validation_truth_scratch = np.zeros((N_VALIDATION, 3), dtype=np.float64)
    seed_error_scratch = np.zeros((5, N_VALIDATION, 3), dtype=np.float64)
    multiplier_delta_scratch = np.zeros((100, 21), dtype=np.float64)
    analysis_workspace_bytes = sum(
        array.nbytes
        for array in (
            influence,
            sealed_prediction_store,
            validation_truth_scratch,
            seed_error_scratch,
            multiplier_delta_scratch,
        )
    )
    multiplier_times: list[float] = []
    for _repetition in range(5):
        bits = rng.integers(0, 2, size=(100, N_VALIDATION), dtype=np.int8)
        weights = np.where(bits == 0, -1, 1)
        start = time.perf_counter()
        _ = weights.astype(np.float64) @ influence
        multiplier_times.append(time.perf_counter() - start)
    t_l = max(timings["L"])
    t_n = max(timings["N"])
    u_l = 30.0 + 3.0 * 2340 * t_l
    u_n = 30.0 + 3.0 * 2340 * t_n
    multiplier_chunk_seconds = max(multiplier_times)
    t_post = 3.0 * (200 * multiplier_chunk_seconds + 600.0)
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "format": "PSR_RES293_FEASIBILITY_PROBE_V1",
        "scope": "outcome_blind_scratch_arrays_only_no_learner_fit_or_prediction",
        "warmup_count_per_learner": 1,
        "measured_repetitions_per_learner": 5,
        "per_batch_seconds": timings,
        "t_l_seconds": t_l,
        "t_n_seconds": t_n,
        "projected_fit_l_seconds": u_l,
        "projected_fit_n_seconds": u_n,
        "projected_campaign_fit_seconds": 10 * u_l + 20 * u_n,
        "multiplier_chunk_seconds_max": multiplier_chunk_seconds,
        "projected_post_analysis_seconds": t_post,
        "projected_preprocess_seconds": None,
        "projected_verify_seconds": 600.0,
        "projected_qualification_seconds": 600.0,
        "peak_rss_kib": memory,
        "analysis_workspace_bytes": analysis_workspace_bytes,
        "environment": env,
        "memory_bound_components": {
            "probe_peak_rss_bytes": memory * 1024,
            "feature_arrays_bytes": (N_FIT + N_DEVELOPMENT + N_VALIDATION) * WIDTH * 4 * 2,
            "optimizer_and_model_state_in_probe_peak": True,
            "analysis_workspace_bytes": analysis_workspace_bytes,
            "analysis_workspace_is_included_in_probe_peak": True,
        },
        "temporary_output_disk_bound_bytes": 10 * 1024**3,
        "hard_stops": {
            "each_fit_projection_seconds": 180,
            "fit_campaign_projection_seconds": 5400,
            "total_cpu_and_wall_seconds": 21600,
            "peak_rss_bytes": 16 * 1024**3,
            "temporary_output_disk_bytes": 10 * 1024**3,
        },
    }
    output_path.write_bytes(_json_bytes(result))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("execute")
    run_parser.add_argument("--payload", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--run-id", required=True)
    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "execute":
        execute(args.payload, args.output, args.run_id)
    else:
        probe(args.output)


if __name__ == "__main__":
    main()
