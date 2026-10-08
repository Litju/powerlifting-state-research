from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path

import pytest
import torch

from powerlifting_state_research.contracts.serialization import sha256_record
from powerlifting_state_research.evaluation.identity import TARGETS
from powerlifting_state_research.evaluation.prediction import PredictionRow
from powerlifting_state_research.models import temporal_expert as expert
from powerlifting_state_research.models.families import MODEL_FAMILIES
from powerlifting_state_research.models.references import CheckpointReference, ModelReference
from powerlifting_state_research.models.temporal_expert import (
    MODEL_SPEC_ID,
    MODEL_SPEC_SEMANTICS,
    LiftSharedTemporalExpert,
    NormalizationStats,
    TemporalModelBatch,
    TemporalModelInput,
    load_weights,
    model_spec_id,
    parameter_count,
    predict,
    predict_three_seed_ensemble,
    prepare_batch,
    save_weights,
)

ForecastInputs = expert.dataset.ForecastInputs
LiftInputs = expert.dataset.LiftInputs
HistorySegment = expert.interventions.HistorySegment
HISTORY_OBSERVATION_DAYS = expert.HISTORY_OBSERVATION_DAYS
PerformanceObservation = expert.observations.PerformanceObservation
declared_plan = expert.interventions.declared_plan
PREDICTION_CONTRACT = expert.PREDICTION_CONTRACT


def _input(row_id: str = "row-1") -> TemporalModelInput:
    history = tuple(
        PerformanceObservation(day, 100.0 + index, 70.0 + index * 0.7, 0.6 - index * 0.005)
        for index, day in enumerate(HISTORY_OBSERVATION_DAYS)
    )
    lift = LiftInputs(history, (HistorySegment(0, 223, 0.8, 0.75),))
    forecast = ForecastInputs(
        "alignment-only-entity",
        224,
        28,
        declared_plan("continue"),
        {"squat": lift, "bench_press": lift, "deadlift": lift},
    )
    return TemporalModelInput.from_forecast_inputs(row_id, forecast)


def _stats() -> NormalizationStats:
    return NormalizationStats(
        ((0.0,) * 6,) * 3,
        ((1.0,) * 6,) * 3,
        (10.0, -5.0, 20.0),
        (2.0, 3.0, 4.0),
    )


def _constant_model(output: tuple[float, float, float]) -> LiftSharedTemporalExpert:
    model = LiftSharedTemporalExpert()
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    with torch.no_grad():
        model.output_head[-1].bias.copy_(torch.tensor(output))
    return model


def test_public_input_has_no_target_or_latent_fields_and_builds_fixed_shapes() -> None:
    model_input = _input()
    assert {field.name for field in fields(TemporalModelInput)} == {
        "row_id",
        "origin_day",
        "horizon_days",
        "declared_future_plan",
        "squat",
        "bench_press",
        "deadlift",
    }
    assert {field.name for field in fields(TemporalModelBatch)} == {
        "history",
        "history_mask",
        "plan_numeric",
        "plan_index",
    }
    assert not {"targets", "latent", "capacity_trajectory", "future_observations"}.intersection(
        field.name for field in fields(TemporalModelInput)
    )

    first = prepare_batch((model_input,), _stats())
    second = prepare_batch((model_input,), _stats())
    assert first.row_ids == ("row-1",)
    assert first.tensors.history.shape == (1, 3, 32, 10)
    assert first.tensors.history_mask.shape == (1, 3, 32)
    assert first.tensors.plan_numeric.shape == (1, 6)
    assert first.tensors.plan_index.shape == (1,)
    assert first.tensors.plan_index.dtype is torch.int64
    assert torch.equal(first.tensors.history, second.tensors.history)
    assert torch.equal(first.tensors.plan_numeric, second.tensors.plan_numeric)


def test_malformed_history_and_tensor_batches_are_rejected() -> None:
    source = _input()
    with pytest.raises(ValueError, match="32 ordered observations"):
        replace(source, squat=LiftInputs(source.squat.history[:-1], source.squat.history_schedule))

    malformed = TemporalModelBatch(
        torch.zeros((1, 3, 31, 10)),
        torch.ones((1, 3, 31)),
        torch.zeros((1, 6)),
        torch.zeros((1,), dtype=torch.int64),
    )
    with pytest.raises(ValueError, match="history tensor must"):
        malformed.validate()

    with pytest.raises(ValueError, match="gap, overlap, or invalid day"):
        replace(
            source,
            squat=LiftInputs(
                source.squat.history,
                (HistorySegment(0, 100, 0.8, 0.75), HistorySegment(102, 223, 0.8, 0.75)),
            ),
        )


def test_contract_output_order_and_deterministic_cpu_inference() -> None:
    PREDICTION_CONTRACT.validate()
    assert tuple(field.name for field in PREDICTION_CONTRACT.outputs) == TARGETS
    assert TARGETS == (
        "squat_delta_capacity_kg",
        "bench_press_delta_capacity_kg",
        "deadlift_delta_capacity_kg",
    )

    model = _constant_model((0.5, -1.0, 2.0))
    first = predict(model, (_input(),), _stats())
    second = predict(model, (_input(),), _stats())
    assert first == second
    assert first == (PredictionRow("row-1", 11.0, -8.0, 28.0),)


def test_model_spec_identity_is_weight_independent_and_weights_round_trip(tmp_path: Path) -> None:
    reference = ModelReference(MODEL_SPEC_ID)
    assert reference.model_id == MODEL_SPEC_ID
    assert MODEL_FAMILIES == (MODEL_SPEC_ID,)
    digest = sha256_record(
        {
            "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
            "component_class": "model",
            "slug": "public-native-lift-shared-temporal-gru-capacity-change",
            "version": "1.0.0",
            "semantics": MODEL_SPEC_SEMANTICS,
        },
        reject_floats=True,
    )
    assert MODEL_SPEC_ID.endswith(f"~{digest[7:19]}")
    assert MODEL_SPEC_ID.startswith(
        "psr:model:public-native-lift-shared-temporal-gru-capacity-change@"
    )
    assert "checkpoint" not in str(MODEL_SPEC_SEMANTICS).lower()
    assert "seed" not in str(MODEL_SPEC_SEMANTICS).lower()
    assert parameter_count(LiftSharedTemporalExpert()) == 118_571

    original = _constant_model((0.2, 0.4, 0.6))
    path = tmp_path / "fixture-state.pt"
    save_weights(path, original)
    checkpoint_payload = torch.load(path, map_location="cpu", weights_only=True)
    assert checkpoint_payload["model_spec_id"] == MODEL_SPEC_ID
    assert "input_mean" not in checkpoint_payload and "target_mean" not in checkpoint_payload
    checkpoint_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    checkpoint = CheckpointReference("fixture:temporal-expert", f"sha256:{checkpoint_digest}")
    assert checkpoint.checkpoint_id != reference.model_id

    other_path = tmp_path / "other-fixture-state.pt"
    save_weights(other_path, _constant_model((0.3, 0.5, 0.7)))
    other_digest = hashlib.sha256(other_path.read_bytes()).hexdigest()
    assert other_digest != checkpoint_digest
    other_payload = torch.load(other_path, map_location="cpu", weights_only=True)
    assert other_payload["model_spec_id"] == checkpoint_payload["model_spec_id"] == MODEL_SPEC_ID
    assert model_spec_id(MODEL_SPEC_SEMANTICS) == MODEL_SPEC_ID
    assert ModelReference(MODEL_SPEC_ID).model_id == reference.model_id
    mismatch_path = tmp_path / "mismatched-spec.pt"
    torch.save(
        {
            "model_spec_id": "psr:model:other-spec@1.0.0~000000000000",
            "state_dict": original.state_dict(),
        },
        mismatch_path,
    )
    with pytest.raises(ValueError, match="model specification mismatch"):
        load_weights(mismatch_path, LiftSharedTemporalExpert())

    restored = load_weights(path, LiftSharedTemporalExpert())
    assert predict(restored, (_input(),), _stats()) == predict(original, (_input(),), _stats())
    assert restored.model_spec_id == reference.model_id


def test_model_identity_binds_direct_task_qoi_and_prediction_contract() -> None:
    contract = MODEL_SPEC_SEMANTICS["prediction_contract"]
    assert MODEL_SPEC_SEMANTICS["task_id"] == PREDICTION_CONTRACT.task_id
    assert MODEL_SPEC_SEMANTICS["qoi_ids"] == PREDICTION_CONTRACT.qoi_ids
    assert contract["inputs"] == tuple(
        (field.name, field.kind.value) for field in PREDICTION_CONTRACT.inputs
    )
    assert contract["outputs"] == tuple(
        (field.name, field.qoi_id, field.unit) for field in PREDICTION_CONTRACT.outputs
    )
    lowered = str(MODEL_SPEC_SEMANTICS).lower()
    assert all(value not in lowered for value in ("benchmark", "evaluation", "metric"))


def test_model_identity_is_independent_of_evaluation_only_benchmark_change() -> None:
    original_benchmark = {
        "benchmark_spec_id": "benchmark-before-evaluation-change",
        "evaluation_id": "evaluation-before-change",
        "model_semantics": deepcopy(MODEL_SPEC_SEMANTICS),
    }
    changed_benchmark = {
        **original_benchmark,
        "benchmark_spec_id": "benchmark-after-evaluation-change",
        "evaluation_id": "evaluation-after-change",
        "model_semantics": deepcopy(MODEL_SPEC_SEMANTICS),
    }

    assert original_benchmark["benchmark_spec_id"] != changed_benchmark["benchmark_spec_id"]
    assert original_benchmark["evaluation_id"] != changed_benchmark["evaluation_id"]
    assert model_spec_id(original_benchmark["model_semantics"]) == MODEL_SPEC_ID
    assert model_spec_id(changed_benchmark["model_semantics"]) == MODEL_SPEC_ID


def test_training_seed_does_not_participate_in_model_identity() -> None:
    first_run = {"training_seed": 383001, "model_semantics": deepcopy(MODEL_SPEC_SEMANTICS)}
    second_run = {"training_seed": 383002, "model_semantics": deepcopy(MODEL_SPEC_SEMANTICS)}

    assert first_run["training_seed"] != second_run["training_seed"]
    assert (
        model_spec_id(first_run["model_semantics"])
        == model_spec_id(second_run["model_semantics"])
        == MODEL_SPEC_ID
    )


def test_model_identity_changes_with_model_defining_semantics() -> None:
    variants: list[dict[str, object]] = []

    hidden_size = deepcopy(MODEL_SPEC_SEMANTICS)
    hidden_size["temporal_architecture"]["temporal_encoder"] = (
        "GRU(input=72, hidden=65, layers=2, batch_first=true)"
    )
    variants.append(hidden_size)

    history_channel = deepcopy(MODEL_SPEC_SEMANTICS)
    history_channel["input_representation"]["history_channels"] = (
        *history_channel["input_representation"]["history_channels"],
        "extra_channel",
    )
    variants.append(history_channel)

    output_order = deepcopy(MODEL_SPEC_SEMANTICS)
    output_order["output_order"] = tuple(reversed(output_order["output_order"]))
    variants.append(output_order)

    input_representation = deepcopy(MODEL_SPEC_SEMANTICS)
    input_representation["input_representation"]["sequence_order"] = "newest_to_oldest"
    variants.append(input_representation)

    assert all(model_spec_id(semantics) != MODEL_SPEC_ID for semantics in variants)


def test_three_seed_ensemble_means_standardized_outputs_before_inverse_transform() -> None:
    models = (
        _constant_model((0.0, 0.0, 0.0)),
        _constant_model((1.0, 2.0, 3.0)),
        _constant_model((2.0, 4.0, 6.0)),
    )
    expected = (PredictionRow("row-1", 12.0, 1.0, 32.0),)
    assert predict_three_seed_ensemble(models, (_input(),), _stats()) == expected
    with pytest.raises(ValueError, match="exactly three"):
        predict_three_seed_ensemble(models[:2], (_input(),), _stats())


def test_normalization_stats_round_trip_and_reject_wrong_schema() -> None:
    stats = _stats()
    assert NormalizationStats.from_dict(stats.to_dict()) == stats
    with pytest.raises(ValueError, match="schema mismatch"):
        NormalizationStats.from_dict({"schema_id": "wrong"})
