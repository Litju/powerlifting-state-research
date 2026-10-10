from __future__ import annotations

import ast
import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from powerlifting_state_research.audits.res283_analysis import (
    CONFIG_PATH,
    METRIC_DIRECTIONS,
    OUTPUT_DIR,
    TARGETS,
    Candidate,
    _fit_seed_pairwise_rows,
    _seed_panel_ranks,
    _uncertainty_evidence_rows,
    align_rows,
    build_analysis_artifacts,
    numerical_comparison_status,
    rank_values,
    require_complete_result_targets,
    seed_interpretation,
    validate_model_identity,
    verify_output_index,
    write_analysis,
)

ROOT = Path(__file__).resolve().parents[2]


def _candidate(candidate_id: str = "family:seed1") -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        family="family",
        seed="383001",
        role="fit_seed",
        model_id="psr:model:family@1.0.0~000000000000",
        fitted_instance_id="psr:fitted-instance:family-seed@sha256:0000000000000000",
        evaluation_result_id="psr:evaluation-result@sha256:0000000000000000",
        evaluation_sample_count=2,
        prediction_artifact_identity="psr:prediction-artifact:sample@sha256:0000000000000000",
        evaluation_path="eval.json",
        prediction_path="predictions.jsonl",
        fitted_instance_path="fit.json",
        evaluation_sha256="0" * 64,
        prediction_sha256="0" * 64,
        fitted_instance_sha256="0" * 64,
        metrics={
            target: {
                "RMSE": 1.0,
                "MAE": 1.0,
                "R²": 0.5,
                "SRE(ddof=0)": 0.5,
            }
            for target in TARGETS
        },
        benchmark_id="psr:benchmark-spec:benchmark@1.0.0~000000000000",
        dataset_realization_id="psr:dataset-realization:data@sha256:0000000000000000",
        evaluation_id="psr:evaluation:evaluation@1.0.0~000000000000",
        metric_ids=("psr:metric:rmse@1.0.0~000000000000",),
        rights="MIT",
    )


def test_numerical_comparison_rejects_different_evaluation() -> None:
    shared: dict[str, Any] = {
        "benchmark_id": "benchmark-a",
        "world_id": "world-a",
        "dataset_spec_id": "spec-a",
        "dataset_realization_id": "realization-a",
        "evaluation_id": "evaluation-a",
        "task_id": "task-a",
        "qoi_id": "qoi-a",
        "metric_ids": ("rmse",),
        "information_boundary": "same",
        "row_ids": ("row-1",),
    }
    other = {**shared, "evaluation_id": "evaluation-b"}
    status, failed = numerical_comparison_status(shared, other)
    assert status == "REJECTED_FOR_NUMERICAL_COMPARISON"
    assert failed == ("evaluation_id",)
    assert numerical_comparison_status(shared, {**shared, "world_id": "world-b"}) == (
        "REJECTED_FOR_NUMERICAL_COMPARISON",
        ("world_id",),
    )
    assert numerical_comparison_status(shared, shared) == ("ADMISSIBLE", ())
    assert numerical_comparison_status(shared, {**shared, "row_ids": ("row-2",)}) == (
        "REJECTED_FOR_NUMERICAL_COMPARISON",
        ("matched_prediction_row_support",),
    )
    assert numerical_comparison_status(
        shared, {key: value for key, value in shared.items() if key != "qoi_id"}
    )[0] == ("UNSUPPORTED_BY_EVIDENCE")


def test_model_and_fitted_instance_identities_must_match() -> None:
    result = {
        "model": {"model_id": "model-1"},
        "fitted_instance": {"fitted_instance_id": "fit-1"},
        "prediction_artifact": {"artifact_id": "pred-1"},
    }
    row = {
        "model_id": "model-1",
        "fitted_instance_id": "fit-1",
        "evaluation_result_id": "result-1",
        "prediction_artifact_identity": "prediction-1",
    }
    validate_model_identity(
        result,
        row,
        result_id="result-1",
        prediction_identity="prediction-1",
    )
    with pytest.raises(ValueError, match="fitted_instance_id"):
        validate_model_identity(
            result,
            {**row, "fitted_instance_id": "different-fit"},
            result_id="result-1",
            prediction_identity="prediction-1",
        )


def test_metric_directions_and_exact_rank_ties() -> None:
    assert METRIC_DIRECTIONS == {
        "RMSE": "lower",
        "MAE": "lower",
        "R²": "higher",
        "SRE(ddof=0)": "lower",
    }
    assert rank_values([2.0, 1.0, 1.0], "lower") == (3.0, 1.5, 1.5)
    assert rank_values([0.2, 0.8, 0.8], "higher") == (3.0, 1.5, 1.5)
    with pytest.raises(ValueError, match="non-finite"):
        rank_values([1.0, float("nan")], "lower")


def test_deterministic_seed_labels_are_not_fit_replications() -> None:
    assert seed_interpretation("ridge", ["same"] * 3, ["neural"], ["ridge"]).startswith(
        "DETERMINISTIC_REPEATS"
    )
    assert seed_interpretation("neural", ["a", "b", "c"], ["neural"], ["ridge"]).startswith(
        "THREE_DISTINCT_FIT_SEEDS"
    )
    with pytest.raises(ValueError, match="changed predictions"):
        seed_interpretation("ridge", ["a", "b", "c"], ["neural"], ["ridge"])


def test_fit_seed_ranks_use_the_matched_same_seed_family_panel() -> None:
    candidates = []
    values = {"1": {"A": 1.0, "B": 2.0}, "2": {"A": 3.0, "B": 2.0}, "3": {"A": 1.0, "B": 2.0}}
    for seed, family_values in values.items():
        for family, rmse in family_values.items():
            candidate = _candidate(f"{family}:{seed}")
            candidates.append(
                replace(
                    candidate,
                    family=family,
                    seed=seed,
                    metrics={
                        target: {**metrics, "RMSE": rmse}
                        for target, metrics in candidate.metrics.items()
                    },
                )
            )
    seeds, families, ranks = _seed_panel_ranks(candidates)
    assert seeds == ("1", "2", "3")
    assert families == ("A", "B")
    assert [ranks[("squat_delta_capacity_kg", "RMSE", seed)]["A"] for seed in seeds] == [
        1.0,
        2.0,
        1.0,
    ]
    reversals = _fit_seed_pairwise_rows(candidates)
    squat_rmse = next(
        row
        for row in reversals
        if row["target"] == "squat_delta_capacity_kg"
        and row["metric"] == "RMSE"
        and row["model_family_a"] == "A"
        and row["model_family_b"] == "B"
    )
    assert squat_rmse["ordered_seed_pairs"] == 3
    assert squat_rmse["pairwise_seed_rank_reversals"] == 2


def test_missing_model_results_are_rejected() -> None:
    expected = {("result-1", "squat"), ("result-1", "bench")}
    require_complete_result_targets(list(expected), expected)
    with pytest.raises(ValueError, match="missing or unexpected model results"):
        require_complete_result_targets([("result-1", "squat")], expected)


def test_prediction_rows_align_by_key_and_keep_entities_grouped() -> None:
    validation = [
        {"row_id": "r2", "inputs": {"entity_id": "athlete-a"}, "targets": {"y": 2.0}},
        {"row_id": "r1", "inputs": {"entity_id": "athlete-a"}, "targets": {"y": 1.0}},
        {"row_id": "r3", "inputs": {"entity_id": "athlete-b"}, "targets": {"y": 3.0}},
    ]
    predictions = [
        {"row_id": "r3", "y": 2.5},
        {"row_id": "r1", "y": 0.5},
        {"row_id": "r2", "y": 1.5},
    ]
    row_ids, entities, truth, pred = align_rows(validation, predictions, target_names=("y",))
    assert row_ids == ["r1", "r2", "r3"]
    assert entities == ["athlete-a", "athlete-a", "athlete-b"]
    assert truth == {"y": [1.0, 2.0, 3.0]}
    assert pred == {"y": [0.5, 1.5, 2.5]}
    assert entities.count("athlete-a") == 2
    with pytest.raises(ValueError, match="exact paired support"):
        align_rows(validation, predictions[:-1], target_names=("y",))
    with pytest.raises(ValueError, match="unique row IDs"):
        align_rows(validation, [*predictions, predictions[0]], target_names=("y",))


def test_uncertainty_is_unsupported_without_tracked_truth_and_entity_mapping() -> None:
    result = _uncertainty_evidence_rows(
        [_candidate()],
        {
            "paired_uncertainty": {
                "method": "Entity-cluster bootstrap",
                "resamples": 2000,
                "seed": 283001,
            }
        },
    )
    assert len(result) == 12
    assert {row["status"] for row in result} == {"UNSUPPORTED_BY_EVIDENCE"}
    assert {row["inference_status"] for row in result} == {"INCONCLUSIVE"}
    assert all(row["completed_resamples"] == 0 for row in result)
    assert all("validation target truth rows" in row["reason"] for row in result)
    assert all("rank_p2_5" not in row for row in result)


@pytest.fixture(scope="module")
def artifacts() -> dict[str, bytes]:
    return build_analysis_artifacts(ROOT)


def test_analysis_replay_and_checksum_index_are_deterministic(artifacts: dict[str, bytes]) -> None:
    verify_output_index(artifacts)
    replay = build_analysis_artifacts(ROOT)
    assert replay == artifacts
    manifest = json.loads(artifacts[f"{OUTPUT_DIR.as_posix()}/run-manifest.json"])
    assert manifest["candidate_count"] == 22
    assert len(manifest["source_model_ids"]) == 7
    assert len(manifest["candidate_identity_bindings"]) == 22
    assert manifest["cross_version_pair_count"] == 36
    assert manifest["admissible_cross_version_pair_count"] == 0
    assert manifest["res281_public_native_model_ranking_status"] == "INCONCLUSIVE"
    assert manifest["res281_public_native_baseline_domination_status"] == "INCONCLUSIVE"
    assert manifest["validation_target_truth_available"] is False
    assert manifest["row_to_entity_mapping_available"] is False
    assert manifest["completed_entity_bootstrap_resamples"] == 0
    matrix = list(
        csv.DictReader(
            artifacts[f"{OUTPUT_DIR.as_posix()}/version-by-model-evidence.csv"]
            .decode()
            .splitlines()
        )
    )
    iid_rows = [row for row in matrix if row["benchmark_version"].startswith("iid_")]
    historical_rows = [row for row in matrix if not row["benchmark_version"].startswith("iid_")]
    assert len(iid_rows) == 7
    assert {row["model_family_evidence_status"] for row in iid_rows} == {"AVAILABLE_PUBLIC_FIT"}
    assert len(historical_rows) == 56
    assert {row["model_family_evidence_status"] for row in historical_rows} == {
        "UNSUPPORTED_BY_EVIDENCE"
    }
    assert all(row["candidate_count"] == "0" for row in historical_rows)
    assert not any(
        item["path"].endswith(("train.jsonl", "validation.jsonl"))
        for item in manifest["input_artifacts"]
    )
    assert not any(
        item["path"].startswith("data/synthetic/") for item in manifest["input_artifacts"]
    )


def test_checksum_integrity_detects_changed_analysis_output(artifacts: dict[str, bytes]) -> None:
    changed = dict(artifacts)
    path = f"{OUTPUT_DIR.as_posix()}/frozen-iid-target-wise-rankings.csv"
    changed[path] += b"tampered"
    with pytest.raises(ValueError, match="analysis (size|checksum) mismatch"):
        verify_output_index(changed)


def test_frozen_evidence_is_unchanged_by_analysis_write(
    artifacts: dict[str, bytes], tmp_path: Path
) -> None:
    paths = (
        "results/audits/res281/audit-results.json",
        "results/manifests/public-native-comparator-suite.json",
        "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-temporal-expert/ensemble.evaluation-result.json",
    )
    before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    write_analysis(artifacts, tmp_path)
    after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    assert before == after
    assert (tmp_path / CONFIG_PATH).is_file()


def test_analysis_notebook_is_saved_with_reproducible_outputs(artifacts: dict[str, bytes]) -> None:
    notebook = json.loads(artifacts[f"{OUTPUT_DIR.as_posix()}/analysis-notebook.ipynb"])
    assert notebook["nbformat"] == 4
    assert [cell["cell_type"] for cell in notebook["cells"]].count("code") == 4
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]))
    assert any(
        "image/svg+xml" in output.get("data", {})
        for cell in notebook["cells"]
        for output in cell.get("outputs", [])
    )
