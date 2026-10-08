from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)
from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.models import train_temporal_expert as training
from powerlifting_state_research.models.temporal_expert import NormalizationStats
from powerlifting_state_research.models.train_temporal_expert import (
    TrainingError,
    _inputs_and_targets,
    _verify_normalization_stats,
    make_internal_split,
)
from powerlifting_state_research.models.training import (
    PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL,
    TRAINING_PROTOCOL_ID,
    training_protocol_manifest,
)


def _row(
    row_id: str, plan: str = "continue", horizon: int = 28
) -> benchmark.dataset.PublicForecastRow:
    history = tuple(
        benchmark.observations.PerformanceObservation(
            day,
            100.0 + index,
            70.0 + index * 0.5,
            0.6 - index * 0.004,
        )
        for index, day in enumerate(benchmark.observations.HISTORY_OBSERVATION_DAYS)
    )
    lift = benchmark.dataset.LiftInputs(
        history,
        (benchmark.interventions.HistorySegment(0, 223, 0.8, 0.75),),
    )
    inputs = benchmark.dataset.ForecastInputs(
        row_id,
        224,
        horizon,
        benchmark.interventions.declared_plan(plan),
        {"squat": lift, "bench_press": lift, "deadlift": lift},
    )
    row = benchmark.dataset.PublicForecastRow(
        row_id,
        inputs,
        {
            "squat_delta_capacity_kg": 1.0,
            "bench_press_delta_capacity_kg": 0.5,
            "deadlift_delta_capacity_kg": 1.5,
        },
    )
    benchmark.dataset.validate_public_row(row)
    return row


def test_training_protocol_manifest_is_generated_from_typed_authority() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "artifacts/training-protocols/public-native-temporal-expert.json"
    )
    assert path.read_bytes() == canonical_json_bytes(training_protocol_manifest()) + b"\n"
    assert TRAINING_PROTOCOL_ID.startswith("psr:training-protocol:")
    assert PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.seeds == (383001, 383002, 383003)
    assert PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.dataset_train_sha256 == (
        "914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550"
    )
    assert PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.internal_fit_row_count == 9_984
    assert PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.internal_selection_row_count == 2_304
    assert PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.internal_selection_split_id == (
        "psr:internal-selection-split:public-native-temporal-expert@sha256:"
        "9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"
    )


def test_internal_split_is_deterministic_disjoint_and_support_preserving() -> None:
    rows = tuple(_row(f"entity-{index:02d}", "continue", 28) for index in range(3)) + tuple(
        _row(f"entity-{index:02d}", "step_up", 56) for index in range(3, 6)
    )
    first = make_internal_split(
        rows,
        realization_id="fixture-realization",
        realization_digest="fixture-digest",
    )
    second = make_internal_split(
        tuple(reversed(rows)),
        realization_id="fixture-realization",
        realization_digest="fixture-digest",
    )

    assert first.manifest == second.manifest
    assert set(first.manifest["fit_row_ids"]).isdisjoint(first.manifest["selection_row_ids"])
    assert first.manifest["support_preserved"] is True
    assert first.manifest["fit_row_count"] == 4
    assert first.manifest["selection_row_count"] == 2
    assert len(first.manifest["strata"]) == 2


def test_normalization_replay_uses_computational_fit_order_not_identity_order() -> None:
    rows = tuple(_row(f"entity-{index:02d}") for index in range(24))
    initial_split = make_internal_split(
        rows,
        realization_id="fixture-realization",
        realization_digest="fixture-digest",
    )
    fit_targets = dict(
        zip(
            (row.row_id for row in initial_split.fit_rows),
            (1e16, 1.0, -1e16, 1.0) * 5,
            strict=True,
        )
    )
    rows = tuple(
        replace(
            row,
            targets={
                "squat_delta_capacity_kg": fit_targets.get(row.row_id, 10.0),
                "bench_press_delta_capacity_kg": fit_targets.get(row.row_id, 10.0),
                "deadlift_delta_capacity_kg": fit_targets.get(row.row_id, 10.0),
            },
        )
        for row in rows
    )
    expected_split = make_internal_split(
        rows,
        realization_id="fixture-realization",
        realization_digest="fixture-digest",
    )

    fit_ids = expected_split.manifest["fit_row_ids"]
    assert fit_ids == tuple(sorted(fit_ids))
    assert tuple(row.row_id for row in expected_split.fit_rows) != fit_ids
    assert set(fit_ids).isdisjoint(expected_split.manifest["selection_row_ids"])

    fit_inputs, fit_targets_in_order = _inputs_and_targets(expected_split.fit_rows)
    expected_stats = NormalizationStats.fit_train(fit_inputs, fit_targets_in_order)
    stored_stats = NormalizationStats.from_dict(expected_stats.to_dict())
    assert stored_stats == expected_stats
    _verify_normalization_stats(expected_split, stored_stats)

    fit_id_set = set(fit_ids)
    canonical_fit_rows = tuple(row for row in rows if row.row_id in fit_id_set)
    canonical_inputs, canonical_targets = _inputs_and_targets(canonical_fit_rows)
    reordered_stats = NormalizationStats.fit_train(canonical_inputs, canonical_targets)
    assert reordered_stats != expected_stats
    mean_differences = tuple(
        abs(left - right)
        for left, right in zip(expected_stats.target_mean, reordered_stats.target_mean, strict=True)
    )
    assert 0.0 < max(mean_differences) < 1.0
    with pytest.raises(TrainingError, match="normalization statistics were not fitted"):
        _verify_normalization_stats(expected_split, reordered_stats)

    all_inputs, all_targets = _inputs_and_targets(
        expected_split.fit_rows + expected_split.selection_rows
    )
    assert NormalizationStats.fit_train(all_inputs, all_targets) != expected_stats


def test_existing_run_verification_keeps_run_read_only_and_receipt_external(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive_root = tmp_path / "res274"
    run_root = drive_root / "runs" / training.EXISTING_GATE_B_RUN_ID
    bundle_path = drive_root / "bundles" / f"res274-{training.EXISTING_GATE_B_RUN_ID}.zip"
    run_root.mkdir(parents=True)
    (run_root / "immutable-marker").write_bytes(b"preserved")
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_bytes(b"preserved-bundle")
    monkeypatch.setattr(training, "REQUIRED_DRIVE_RES274_ROOT", drive_root)
    monkeypatch.setattr(
        training,
        "_git_identity",
        lambda sha: {"code_sha": sha, "git_tree_status": "clean"},
    )
    monkeypatch.setattr(training, "_verify_drive_paths", lambda *args: None)

    def snapshot() -> tuple[tuple[str, int, bytes | None], ...]:
        return tuple(
            sorted(
                (
                    path.relative_to(run_root).as_posix(),
                    path.stat().st_mtime_ns,
                    path.read_bytes() if path.is_file() else None,
                )
                for path in run_root.rglob("*")
            )
        )

    before = snapshot()

    with pytest.raises(TrainingError, match="run tree is incomplete"):
        training.verify_existing_run(
            tmp_path / "dataset",
            run_root,
            bundle_path,
            drive_root,
            artifact_code_sha=training.EXISTING_GATE_B_ARTIFACT_CODE_SHA,
            verifier_code_sha="a" * 40,
        )
    assert snapshot() == before
    assert not (drive_root / "verifications").exists()

    monkeypatch.setattr(
        training,
        "_verify_run_contents",
        lambda *args, **kwargs: training.EXISTING_GATE_B_BUNDLE_SHA256,
    )
    receipt_path = training.verify_existing_run(
        tmp_path / "dataset",
        run_root,
        bundle_path,
        drive_root,
        artifact_code_sha=training.EXISTING_GATE_B_ARTIFACT_CODE_SHA,
        verifier_code_sha="a" * 40,
    )
    assert snapshot() == before
    assert (
        receipt_path
        == drive_root / "verifications" / training.EXISTING_GATE_B_RUN_ID / f"{'a' * 40}.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["run_id"] == training.EXISTING_GATE_B_RUN_ID
    assert receipt["artifact_code_sha"] == training.EXISTING_GATE_B_ARTIFACT_CODE_SHA
    assert receipt["verifier_code_sha"] == "a" * 40
    assert receipt["bundle_sha256"] == training.EXISTING_GATE_B_BUNDLE_SHA256
    assert receipt["status"] == "PASS"


def test_verify_existing_cli_passes_separate_source_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def verify(
        dataset_root: Path,
        output_root: Path,
        bundle_path: Path,
        drive_res274_root: Path,
        *,
        artifact_code_sha: str,
        verifier_code_sha: str,
    ) -> Path:
        captured.update(
            {
                "dataset_root": dataset_root,
                "output_root": output_root,
                "bundle_path": bundle_path,
                "drive_res274_root": drive_res274_root,
                "artifact_code_sha": artifact_code_sha,
                "verifier_code_sha": verifier_code_sha,
            }
        )
        return tmp_path / "verification.json"

    monkeypatch.setattr(training, "verify_existing_run", verify)
    paths = (tmp_path / "dataset", tmp_path / "run", tmp_path / "bundle.zip", tmp_path / "drive")
    assert (
        training.main(
            [
                "verify-existing",
                "--dataset-root",
                str(paths[0]),
                "--output-root",
                str(paths[1]),
                "--bundle-path",
                str(paths[2]),
                "--drive-res274-root",
                str(paths[3]),
                "--artifact-code-sha",
                training.EXISTING_GATE_B_ARTIFACT_CODE_SHA,
                "--verifier-code-sha",
                "a" * 40,
            ]
        )
        == 0
    )
    assert captured == {
        "dataset_root": paths[0].resolve(),
        "output_root": paths[1].resolve(),
        "bundle_path": paths[2].resolve(),
        "drive_res274_root": paths[3].resolve(),
        "artifact_code_sha": training.EXISTING_GATE_B_ARTIFACT_CODE_SHA,
        "verifier_code_sha": "a" * 40,
    }
