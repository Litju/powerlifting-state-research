from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ERRATUM = ROOT / "studies/corrections/RES-511-v1"
RESULTS = ROOT / "results/corrections/RES-511-v1"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_res511_erratum_records_the_historical_initialization() -> None:
    record = json.loads((ERRATUM / "deviation-record.json").read_text())
    protocol_path = ROOT / record["source_artifacts"]["protocol"]["path"]
    learner_path = ROOT / record["source_artifacts"]["learner"]["path"]
    protocol = json.loads(protocol_path.read_text())
    learner_source = learner_path.read_text()
    identities_path = ROOT / record["source_artifacts"]["fitted_instances"]["path"]
    identities = json.loads(identities_path.read_text())
    models_path = ROOT / record["source_artifacts"]["fitted_models"]["path"]
    models = json.loads(models_path.read_text())
    realization = json.loads(
        (ROOT / record["source_artifacts"]["dataset_realization"]["path"]).read_text()
    )
    result_manifest = json.loads(
        (ROOT / record["source_artifacts"]["result_manifest"]["path"]).read_text()
    )

    assert np.__version__ == record["reconstruction"]["numpy_version"] == "2.4.4"
    assert record["status"] == "HISTORICAL_DEVIATION_CONFIRMED"
    for artifact in record["source_artifacts"].values():
        assert _sha256(ROOT / artifact["path"]) == artifact["sha256"]
    assert protocol["identities"]["protocol_digest"] == record["study_identity"]["protocol_digest"]
    assert realization["identity_id"] == record["study_identity"]["realization_id"]
    assert realization["realization_id"] == record["study_identity"]["realization_slug"]
    assert result_manifest["study"]["study_id"] == record["study_identity"]["study_id"]
    assert (
        result_manifest["study"]["protocol_digest"] == record["study_identity"]["protocol_digest"]
    )
    assert (
        result_manifest["dataset_realization"]["realization_id"]
        == record["study_identity"]["realization_id"]
    )
    assert (
        result_manifest["learner"]["fitted_state_artifact_sha256"]
        == record["source_artifacts"]["fitted_models"]["sha256"]
    )
    assert (
        result_manifest["learner"]["prediction_seal_sha256"]
        == record["source_artifacts"]["predictions"]["sha256"]
    )
    assert protocol["protocol"]["learner"]["initialization"] == record["intended_initialization"]
    assert record["intended_initialization_contract"]["weight_shape"] == [58, 3]
    assert record["intended_initialization_contract"]["bias_values"] == [0.0, 0.0, 0.0]
    assert "rng_init = _random.default_rng(fit_seed)" in learner_source
    assert "weights = rng_init.normal(0.0, 0.01, size=(59, 3)).astype(np.float64)" in learner_source
    assert "gradient[:-1] += L2 * weights[:-1]" in learner_source
    assert "BATCH_SIZE = 32" in learner_source
    assert "LEARNING_RATE = 0.01" in learner_source
    assert "L2 = 1e-4" in learner_source
    expected_updates = {item["id"]: item["updates"] for item in protocol["protocol"]["arms"]}
    assert record["optimization_contract"]["expected_updates_by_arm"] == expected_updates

    original = {item["fitted_instance_id"]: item for item in identities}
    original_models = {item["fitted_instance_id"]: item for item in models}
    recorded = {
        item["fitted_instance_id"]: item
        for seed in record["seeds"]
        for item in seed["fitted_instances"]
    }
    assert len(original) == len(original_models) == len(recorded) == 30
    assert recorded.keys() == original.keys() == original_models.keys()
    assert all(item["update_count"] == expected_updates[item["arm"]] for item in identities)
    assert result_manifest["learner"]["fitted_instance_count"] == 30

    with (RESULTS / "initial-biases.csv").open(newline="") as file:
        table = {int(row["fit_seed"]): row for row in csv.DictReader(file)}
    assert table.keys() == {item["fit_seed"] for item in record["seeds"]}

    for seed in record["seeds"]:
        fit_seed = seed["fit_seed"]
        initial = np.random.default_rng(fit_seed).normal(0.0, 0.01, size=(59, 3)).astype(np.float64)
        matrix_digest = (
            "sha256:"
            + hashlib.sha256(initial.astype("<f8", copy=False).tobytes(order="C")).hexdigest()
        )
        assert initial.shape == (59, 3)
        assert initial[-1].tolist() == seed["initial_bias_parameters"]
        assert matrix_digest == seed["initial_parameter_matrix_sha256"]
        assert len(seed["fitted_instances"]) == 6
        assert {item["arm"] for item in seed["fitted_instances"]} == set(expected_updates)
        assert all(
            item["fit_seed"] == fit_seed
            and item["initial_parameter_matrix_sha256"] == matrix_digest
            and item["identity_digest"] == original[item["fitted_instance_id"]]["identity_digest"]
            and item["state_sha256"] == original[item["fitted_instance_id"]]["state_sha256"]
            and item["update_count"] == original[item["fitted_instance_id"]]["update_count"]
            and item["state_sha256"] == original_models[item["fitted_instance_id"]]["state_sha256"]
            for item in seed["fitted_instances"]
        )
        for item in seed["fitted_instances"]:
            model = original_models[item["fitted_instance_id"]]
            phase_updates = record["optimization_contract"]["expected_phase_updates_by_arm"][
                item["arm"]
            ]
            assert (
                item["public_updates"] == model["public_updates"] == phase_updates["public_updates"]
            )
            assert (
                item["synthetic_updates"]
                == model["synthetic_updates"]
                == phase_updates["synthetic_updates"]
            )
            assert item["public_row_presentations"] == model["public_row_presentations"]
            assert item["synthetic_row_presentations"] == model["synthetic_row_presentations"]
            assert item["public_row_presentations"] == phase_updates["public_updates"] * 32
            assert item["synthetic_row_presentations"] == phase_updates["synthetic_updates"] * 32
        row = table[fit_seed]
        assert [
            float(row[name]) for name in ("squat_bias", "bench_press_bias", "deadlift_bias")
        ] == initial[-1].tolist()

    manifest = json.loads((RESULTS / "manifest.json").read_text())
    for relative, digest in manifest["published_artifacts"].items():
        assert _sha256(ROOT / relative) == digest
    for line in (RESULTS / "SHA256SUMS.txt").read_text().splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
