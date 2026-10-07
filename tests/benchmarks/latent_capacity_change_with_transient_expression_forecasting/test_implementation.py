from __future__ import annotations

import random
from collections import Counter
from dataclasses import asdict, replace

import pytest

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)
from powerlifting_state_research.contracts.serialization import canonical_json_bytes

DEFAULT_CONFIG = benchmark.DEFAULT_CONFIG
GenerationConfig = benchmark.dataset.GenerationConfig
iter_public_rows = benchmark.iter_public_rows
validate_public_row = benchmark.validate_public_row
LiftParameters = benchmark.dynamics.LiftParameters
TrainingSession = benchmark.dynamics.TrainingSession
bounded_training_stimulus = benchmark.dynamics.bounded_training_stimulus
latent_capacity_change = benchmark.dynamics.latent_capacity_change
simulate_lift = benchmark.dynamics.simulate_lift
sample_training_plan = benchmark.interventions.declared_plan
sample_history_template_combinations = benchmark.interventions.sample_history_template_combinations
training_sessions = benchmark.interventions.training_sessions
simulate_athlete = benchmark.dataset.simulate_athlete
HISTORY_OBSERVATION_DAYS = benchmark.observations.HISTORY_OBSERVATION_DAYS
sample_performance_history = benchmark.observations.sample_performance_history
LIFTS = benchmark.population.LIFTS
sample_athlete = benchmark.population.sample_athlete


def test_bounded_world_states_and_latent_target_exclude_expression() -> None:
    assert bounded_training_stimulus(1.2, 0.75, 1.0) == pytest.approx(0.9 / 1.9)
    sessions = {day: TrainingSession(day, 0.8, 0.75) for day in (224, 226, 228, 231, 233, 235)}
    low_suppression = LiftParameters(150.0, 0.4, 35.0, 0.2, 5.0)
    high_suppression = replace(low_suppression, suppression_gain=0.5)
    first = simulate_lift(low_suppression, sessions, 1.3)
    second = simulate_lift(high_suppression, sessions, 1.3)
    assert first.latent_capacity_kg == second.latent_capacity_kg
    assert first.expressed_performance_kg != second.expressed_performance_kg
    assert all(0 <= value < 1 for value in first.stimulus)
    assert all(0 <= value <= 1 for value in first.chronic_adaptation)
    assert all(0 <= value <= 1 for value in first.transient_suppression)
    assert latent_capacity_change(first, 224, 14) == (
        first.latent_capacity_kg[237] - first.latent_capacity_kg[223]
    )
    assert latent_capacity_change(first, 224, 14) == latent_capacity_change(second, 224, 14)


def test_fixed_seed_population_plan_and_dynamics_are_deterministic() -> None:
    athlete_a = sample_athlete(3, random.Random(71))
    athlete_b = sample_athlete(3, random.Random(71))
    assert athlete_a == athlete_b
    plan_a = sample_training_plan("step_up")
    plan_b = sample_training_plan("step_up")
    assert plan_a == plan_b
    sessions = {
        day: TrainingSession(day, plan_a.dose, plan_a.intensity)
        for day in range(plan_a.start_day, plan_a.end_day + 1)
    }
    trajectory_a = simulate_lift(
        athlete_a.parameters.lifts["squat"],
        sessions,
        athlete_a.parameters.stimulus_reference,
    )
    trajectory_b = simulate_lift(
        athlete_b.parameters.lifts["squat"],
        sessions,
        athlete_b.parameters.stimulus_reference,
    )
    assert trajectory_a == trajectory_b


def test_lift_dynamics_have_no_cross_lift_edges() -> None:
    athlete = sample_athlete(5, random.Random(72))
    plan = sample_training_plan("continue")
    sessions = {lift: training_sessions(0, plan) for lift in LIFTS}
    first = simulate_athlete(athlete, sessions)
    sessions["bench_press"] = {
        **sessions["bench_press"],
        224: TrainingSession(224, 1.2, 0.75),
    }
    second = simulate_athlete(athlete, sessions)
    assert first["squat"] == second["squat"]
    assert first["deadlift"] == second["deadlift"]
    assert first["bench_press"] != second["bench_press"]


def test_history_templates_and_observation_noise_are_seeded() -> None:
    templates_a = sample_history_template_combinations(random.Random(81), 64)
    templates_b = sample_history_template_combinations(random.Random(81), 64)
    assert templates_a == templates_b
    assert set(Counter(templates_a).values()) == {1}
    profile = sample_athlete(2, random.Random(82))
    trajectory = simulate_lift(
        profile.parameters.lifts["squat"],
        {},
        profile.parameters.stimulus_reference,
    )
    first = sample_performance_history(
        trajectory.expressed_performance_kg, "squat", random.Random(83)
    )
    second = sample_performance_history(
        trajectory.expressed_performance_kg, "squat", random.Random(83)
    )
    assert first == second
    assert tuple(point.day for point in first) == HISTORY_OBSERVATION_DAYS
    assert len(first) == 32 and first[-1].day == 223


def test_participant_fields_and_row_temporal_boundary() -> None:
    config = GenerationConfig(train_rows=12, validation_rows=12)
    _, row = next(iter_public_rows(config))
    validate_public_row(row)
    visible = asdict(row.inputs)
    assert set(visible) == {
        "entity_id",
        "origin_day",
        "horizon_days",
        "declared_future_plan",
        "lifts",
    }
    assert set(visible["declared_future_plan"]) == {
        "plan_id",
        "start_day",
        "end_day",
        "dose",
        "intensity",
    }
    assert set(asdict(row)) == {"row_id", "inputs", "targets"}
    for lift in LIFTS:
        lift_input = visible["lifts"][lift]
        assert set(lift_input) == {"history", "history_schedule"}
        assert all(
            set(item) == {"day", "assessment_kg", "prescribed_load_kg", "velocity_mps"}
            for item in lift_input["history"]
        )
        assert all(item["day"] <= 223 for item in lift_input["history"])
        assert all(
            set(item) == {"start_day", "end_day", "dose", "intensity"}
            for item in lift_input["history_schedule"]
        )
        assert all(item["end_day"] <= 223 for item in lift_input["history_schedule"])
    assert visible["declared_future_plan"]["start_day"] == 224
    assert visible["declared_future_plan"]["end_day"] == 279

    squat = row.inputs.lifts["squat"]
    invalid_observation = replace(squat.history[-1], day=224)
    invalid_inputs = replace(
        row.inputs,
        lifts={
            **row.inputs.lifts,
            "squat": replace(squat, history=(*squat.history[:-1], invalid_observation)),
        },
    )
    with pytest.raises(ValueError, match="32 weekly observations"):
        validate_public_row(replace(row, inputs=invalid_inputs))


def test_production_counts_strata_disjointness_and_repeat_serialization() -> None:
    assert (DEFAULT_CONFIG.train_rows, DEFAULT_CONFIG.validation_rows) == (12_288, 3_072)
    config = GenerationConfig(train_rows=24, validation_rows=12)

    def serialize() -> tuple[bytes, bytes, set[str], set[str], dict[tuple[str, int], int]]:
        chunks: dict[str, list[bytes]] = {"train": [], "validation": []}
        entities = {"train": set(), "validation": set()}
        strata: dict[tuple[str, int], int] = {}
        for split, row in iter_public_rows(config):
            assert row.row_id not in entities["train"] | entities["validation"]
            entities[split].add(row.inputs.entity_id)
            strata[(row.inputs.declared_future_plan.plan_id, row.inputs.horizon_days)] = strata.get(
                (row.inputs.declared_future_plan.plan_id, row.inputs.horizon_days), 0
            ) + (1 if split == "train" else 100)
            chunks[split].append(canonical_json_bytes(row) + b"\n")
        assert len(chunks["train"]) == config.train_rows
        assert len(chunks["validation"]) == config.validation_rows
        return (
            b"".join(chunks["train"]),
            b"".join(chunks["validation"]),
            entities["train"],
            entities["validation"],
            strata,
        )

    first = serialize()
    second = serialize()
    assert first == second
    assert not first[2] & first[3]
    assert all(first[4][stratum] == 102 for stratum in first[4])
