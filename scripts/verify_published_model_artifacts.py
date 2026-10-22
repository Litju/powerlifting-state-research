#!/usr/bin/env python3
"""Verify released model bytes and run safe inference smoke checks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_worker_path = ROOT / "models/published/res293-definition-b/source-evidence/res293_fit_worker.py"
_worker_spec = importlib.util.spec_from_file_location("res293_fit_worker", _worker_path)
if _worker_spec is None or _worker_spec.loader is None:
    raise ImportError("frozen RES-293 model implementation is unavailable")
res293_worker = importlib.util.module_from_spec(_worker_spec)
sys.modules[_worker_spec.name] = res293_worker
_worker_spec.loader.exec_module(res293_worker)

from powerlifting_state_research.artifacts.manifests import ArtifactManifest  # noqa: E402
from powerlifting_state_research.benchmarks import (  # noqa: E402
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)
from powerlifting_state_research.models.temporal_expert import (  # noqa: E402
    LiftSharedTemporalExpert,
    NormalizationStats,
    TemporalModelInput,
    load_weights,
    parameter_count,
    predict,
    predict_three_seed_ensemble,
)

INVENTORY_PATH = ROOT / "models/published/model-artifact-inventory.json"
dataset = benchmark.dataset
interventions = benchmark.interventions
observations = benchmark.observations


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _smoke_input() -> TemporalModelInput:
    history = tuple(
        observations.PerformanceObservation(day, 100.0 + day / 100, 80.0, 0.5)
        for day in observations.HISTORY_OBSERVATION_DAYS
    )
    dose, intensity = interventions.DOSE_INTENSITY_PAIRS["continue"]
    schedule = (interventions.HistorySegment(0, 223, dose, intensity),)
    lifts = {
        name: dataset.LiftInputs(history=history, history_schedule=schedule)
        for name in ("squat", "bench_press", "deadlift")
    }
    inputs = dataset.ForecastInputs(
        entity_id="published-model-smoke",
        origin_day=224,
        horizon_days=14,
        declared_future_plan=interventions.declared_plan("continue"),
        lifts=lifts,
    )
    return TemporalModelInput.from_forecast_inputs("published-model-smoke", inputs)


def _verify_records(manifest: dict[str, Any]) -> set[str]:
    records = list(manifest.get("artifacts", ())) + list(manifest.get("source_evidence", ()))
    seen: set[str] = set()
    binaries: set[str] = set()
    for record in records:
        relative = record["path"]
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError(f"invalid or duplicate artifact path: {relative}")
        seen.add(relative)
        artifact = ArtifactManifest(**record["artifact_manifest"])
        target = ROOT / relative
        if (
            not target.is_file()
            or target.stat().st_size != record["bytes"]
            or _sha256(target) != record["sha256"]
            or artifact.sha256 != record["sha256"]
            or artifact.license_expression != "MIT"
        ):
            raise ValueError(f"published artifact hash, size, or rights mismatch: {relative}")
        if target.suffix.lower() in {".pt", ".npz"}:
            if path.parts[:2] != ("models", "published"):
                raise ValueError(f"model bytes are outside the published model layout: {relative}")
            binaries.add(relative)
    return binaries


def verify() -> dict[str, Any]:
    inventory = _json(INVENTORY_PATH)
    if inventory.get("format") != "PSR_MODEL_ARTIFACT_RECOVERY_INVENTORY_V1":
        raise ValueError("unknown published model artifact inventory format")
    manifest_paths = inventory["published_model_artifact_manifests"]
    manifests = {path: _json(ROOT / path) for path in manifest_paths}
    binaries: set[str] = set()
    for manifest in manifests.values():
        binaries |= _verify_records(manifest)

    expert = manifests["models/published/public-native-temporal-expert/artifact-manifest.json"]
    source_inventory_info = expert["source_inventory"]
    source_inventory_path = ROOT / source_inventory_info["path"]
    if _sha256(source_inventory_path) != source_inventory_info["sha256"]:
        raise ValueError("RES-274 source inventory hash mismatch")
    source_inventory = _json(source_inventory_path)
    source_entries = {item["path"]: item for item in source_inventory["entries"]}
    if len(source_entries) != 31 or len(expert["artifacts"]) != 33:
        raise ValueError("RES-274 bundle inventory must account for all 33 original files")
    receipt_info = expert["original_run_verification_receipt"]
    receipt_path = ROOT / receipt_info["path"]
    receipt = _json(receipt_path)
    if (
        _sha256(receipt_path) != receipt_info["sha256"]
        or receipt_info["status"] != "PASS"
        or receipt.get("run_id") != expert["run_id"]
        or receipt.get("bundle_sha256") != expert["source_bundle_sha256"]
    ):
        raise ValueError("RES-274 independent source verification receipt mismatch")
    expert_records = {item["source_member"]: item for item in expert["artifacts"]}
    for member, item in source_entries.items():
        published = expert_records.get(member)
        if (
            published is None
            or published["sha256"] != item["sha256"]
            or published["bytes"] != item["size_bytes"]
        ):
            raise ValueError(f"RES-274 source member does not match sealed inventory: {member}")
    final_inventory = _json(
        ROOT
        / "models/published/public-native-temporal-expert/source-run/receipts/final-sha256.json"
    )
    final_entries = {item["path"]: item for item in final_inventory["entries"]}
    if set(final_entries) != set(source_entries):
        raise ValueError("RES-274 final receipt inventory member set changed")
    for member, item in source_entries.items():
        if final_entries[member]["sha256"] != item["sha256"]:
            raise ValueError(f"RES-274 final receipt hash differs: {member}")
    final_receipt = _json(
        ROOT
        / "models/published/public-native-temporal-expert/source-run/receipts/final-receipt.json"
    )
    if (
        final_receipt["sha256_inventory_sha256"]
        != _sha256(
            ROOT
            / "models/published/public-native-temporal-expert/source-run/receipts/final-sha256.json"
        )
        or final_receipt["bundle_excludes_historical_private_artifacts"] is not True
    ):
        raise ValueError("RES-274 final run receipt binding mismatch")
    normalization = _json(ROOT / expert["normalization"]["path"])
    stats = NormalizationStats.from_dict(normalization["stats"])
    if normalization["normalization_stats_id"] != expert["normalization"]["normalization_stats_id"]:
        raise ValueError("PUBLIC_NATIVE normalization identity mismatch")
    smoke_input = (_smoke_input(),)
    models: list[LiftSharedTemporalExpert] = []
    for record in expert["artifacts"]:
        if record["kind"] != "trained checkpoint":
            continue
        model = load_weights(ROOT / record["path"], LiftSharedTemporalExpert())
        identity = record["scientific_identity"]
        source_manifest = _json(
            ROOT
            / "models/checkpoint-manifests/public-native-temporal-expert"
            / f"seed-{identity['seed']}.checkpoint-manifest.json"
        )
        if (
            model.model_spec_id != expert["model_id"]
            or parameter_count(model) != 118_571
            or identity["checkpoint_sha256"] != record["sha256"]
            or source_manifest["checkpoint_sha256"] != record["sha256"]
            or source_manifest["model_id"] != expert["model_id"]
            or source_manifest["normalization_stats_id"]
            != expert["normalization"]["normalization_stats_id"]
        ):
            raise ValueError(f"PUBLIC_NATIVE checkpoint identity mismatch: {record['path']}")
        result = predict(model, smoke_input, stats)
        if len(result) != 1 or not all(np.isfinite(result[0].values)):
            raise ValueError(f"PUBLIC_NATIVE inference smoke failed: {record['path']}")
        models.append(model)
    if len(models) != 3:
        raise ValueError("the temporal expert release must contain exactly three seed models")
    ensemble = predict_three_seed_ensemble(models, smoke_input, stats)
    if len(ensemble) != 1 or not all(np.isfinite(ensemble[0].values)):
        raise ValueError("PUBLIC_NATIVE ensemble inference smoke failed")

    res293_manifest = manifests["models/published/res293-definition-b/artifact-manifest.json"]
    seal_path = ROOT / res293_manifest["source_seal_manifest_path"]
    if _sha256(seal_path) != res293_manifest["source_seal_manifest_sha256"]:
        raise ValueError("RES-293 source seal manifest hash mismatch")
    seal = _json(seal_path)
    protocol_path = ROOT / "models/published/res293-definition-b/source-evidence/protocol.json"
    freeze_path = ROOT / "models/published/res293-definition-b/source-evidence/protocol-freeze.json"
    protocol = _json(protocol_path)
    freeze = _json(freeze_path)
    worker_path = ROOT / "models/published/res293-definition-b/source-evidence/res293_fit_worker.py"
    if (
        protocol["protocol_id"] != res293_manifest["study_protocol_id"]
        or protocol["protocol_digest"] != freeze["protocol_digest"]
        or _sha256(protocol_path) != freeze["protocol_file_sha256"]
        or _sha256(worker_path) != freeze["source_file_sha256"]["scripts/res293_fit_worker.py"]
        or protocol["payload"]["data"]["realization_id"]
        != res293_manifest["dataset_realization_id"]
    ):
        raise ValueError("RES-293 protocol, implementation, or dataset identity mismatch")
    fits = {item["state_artifact"]["file"]: item for item in seal["fits"]}
    sealed_states = {
        item["file"]: item for item in seal["artifacts"] if item["file"].endswith(".state.npz")
    }
    if len(fits) != 30 or len(sealed_states) != 30 or len(res293_manifest["artifacts"]) != 30:
        raise ValueError("RES-293 release does not bind exactly 30 original fitted states")
    states = 0
    for record in res293_manifest["artifacts"]:
        identity = record["scientific_identity"]
        fit = fits.get(record["source_member"])
        sealed = sealed_states.get(record["source_member"])
        if fit is None or identity["configuration"] != fit["config"]:
            raise ValueError(f"RES-293 fitted identity mismatch: {record['path']}")
        if (
            sealed is None
            or record["sha256"] != sealed["sha256"]
            or record["bytes"] != sealed["bytes"]
        ):
            raise ValueError(f"RES-293 state does not match the original seal: {record['path']}")
        learner = fit["learner"]
        model = res293_worker._new_model(learner)
        with np.load(ROOT / record["path"], allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
        if set(arrays) != set(dict(model.named_parameters())):
            raise ValueError(f"RES-293 tensor names mismatch: {record['path']}")
        if any(
            array.dtype != np.dtype("float32") or not np.isfinite(array).all()
            for array in arrays.values()
        ):
            raise ValueError(f"RES-293 tensor dtype or finiteness mismatch: {record['path']}")
        model.load_state_dict(
            {name: torch.from_numpy(array.copy()) for name, array in arrays.items()}, strict=True
        )
        if (
            res293_worker._state_digest(model) != fit["final_state_sha256"]
            or parameter_count(model) != fit["parameter_count"]
            or identity["dataset_realization_id"] != res293_manifest["dataset_realization_id"]
        ):
            raise ValueError(f"RES-293 fitted state identity mismatch: {record['path']}")
        output = model(torch.zeros((1, res293_worker.WIDTH), dtype=torch.float32))
        if output.shape != (1, 3) or not bool(torch.isfinite(output).all()):
            raise ValueError(f"RES-293 inference smoke failed: {record['path']}")
        states += 1
    if states != 30:
        raise ValueError(f"expected 30 sealed RES-293 states, found {states}")
    return {
        "public_native_checkpoints": len(models),
        "res293_states": states,
        "binary_paths": sorted(binaries),
    }


if __name__ == "__main__":
    print(json.dumps({"status": "PASS", **verify()}, sort_keys=True))
