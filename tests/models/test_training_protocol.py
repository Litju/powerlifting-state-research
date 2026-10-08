from __future__ import annotations

from pathlib import Path

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)
from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.models.train_temporal_expert import make_internal_split
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
