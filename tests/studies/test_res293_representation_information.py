from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from itertools import product
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.models.comparators import feature_matrix
from powerlifting_state_research.models.temporal_expert import (
    PLAN_ORDER,
    NormalizationStats,
    TemporalModelInput,
    _raw_history,
    prepare_batch,
)
from powerlifting_state_research.studies.res293_public_verification import (
    PublicVerificationError,
    verify_public_run,
    verify_published_artifacts,
)
from powerlifting_state_research.studies.res293_representation_information import (
    EXPECTED_TARGETS,
    _ordered_features,
    _pack_summary,
    array_payload_digest,
)
from powerlifting_state_research.studies.res293_representation_information import (
    ROOT as STUDY_ROOT,
)

_benchmark_package = (
    "powerlifting_state_research.benchmarks."
    "latent_capacity_change_with_transient_expression_forecasting"
)
dataset = import_module(f"{_benchmark_package}.dataset")
evaluate = import_module(f"{_benchmark_package}.evaluate")
interventions = import_module(f"{_benchmark_package}.interventions")
observations = import_module(f"{_benchmark_package}.observations")
worker = SimpleNamespace(
    **run_path(
        Path(__file__).resolve().parents[2] / "scripts/res293_fit_worker.py",
        run_name="res293_fit_worker",
    )
)
run_res293 = SimpleNamespace(
    **run_path(
        Path(__file__).resolve().parents[2] / "scripts/run_res293.py",
        run_name="run_res293",
    )
)
FIXTURE_MEAN = np.linspace(-0.75, 0.85, 127, dtype=np.float64)
FIXTURE_SCALE = np.linspace(0.7, 2.1, 127, dtype=np.float64)


def _fixed_stats() -> NormalizationStats:
    return NormalizationStats(
        input_mean=tuple(
            tuple(float((lift + 1) * (channel + 2)) for channel in range(6)) for lift in range(3)
        ),
        input_scale=tuple(
            tuple(float(0.5 + (lift + channel + 1) / 7) for channel in range(6))
            for lift in range(3)
        ),
        target_mean=(1.0, -2.0, 3.0),
        target_scale=(2.0, 3.0, 4.0),
    )


def _fixtures(family: str = "both") -> tuple[dataset.PublicForecastRow, ...]:
    rows = []
    families = ("A", "B") if family == "both" else (family,)
    for fixture_family in families:
        for plan_id, horizon, rotation in product(
            interventions.PLAN_IDS, interventions.HORIZONS_DAYS, range(4)
        ):
            lifts = {}
            for lift_index, lift_name in enumerate(("squat", "bench_press", "deadlift")):
                history = []
                for index, day in enumerate(observations.HISTORY_OBSERVATION_DAYS):
                    if fixture_family == "A":
                        assessment = 100.0 + 20.0 * lift_index + index
                        prescribed = (0.50 + 0.05 * (index % 3)) * assessment
                        velocity = 0.20 + 0.01 * lift_index + 0.001 * index
                    else:
                        assessment = 150.0 + 10.0 * lift_index + 2.0 * index
                        prescribed = (0.65 - 0.05 * (index % 3)) * assessment
                        velocity = 0.40 + 0.02 * lift_index + 0.002 * index
                    history.append(
                        observations.PerformanceObservation(day, assessment, prescribed, velocity)
                    )
                lifts[lift_name] = dataset.LiftInputs(
                    tuple(history), interventions.history_segments((rotation + lift_index) % 4)
                )
            rows.append(
                dataset.PublicForecastRow(
                    f"fixture-{plan_id}-{horizon}-{rotation}-{fixture_family}",
                    dataset.ForecastInputs(
                        f"fixture-{plan_id}-{horizon}-{rotation}-{fixture_family}",
                        interventions.ORIGIN_DAY,
                        horizon,
                        interventions.declared_plan(plan_id),
                        lifts,
                    ),
                    {
                        "squat_delta_capacity_kg": float(rotation),
                        "bench_press_delta_capacity_kg": float(horizon),
                        "deadlift_delta_capacity_kg": float(lift_index),
                    },
                )
            )
    assert len(rows) == (96 if family == "both" else 48)
    return tuple(rows)


def _with_history(
    row: dataset.PublicForecastRow,
    *,
    family: str | None = None,
    rotation_delta: int = 0,
    assessment_factor: float = 1.0,
    load_factor: float = 1.0,
    velocity_delta: tuple[int, int, float] | None = None,
) -> dataset.PublicForecastRow:
    lifts = {}
    for lift_index, lift_name in enumerate(("squat", "bench_press", "deadlift")):
        old = row.inputs.lifts[lift_name]
        history = []
        for index, observation in enumerate(old.history):
            if family is None:
                assessment = observation.assessment_kg * assessment_factor
                prescribed = observation.prescribed_load_kg * load_factor
                velocity = observation.velocity_mps
            else:
                if family == "A":
                    assessment = 100.0 + 20.0 * lift_index + index
                    prescribed = (0.50 + 0.05 * (index % 3)) * assessment
                    velocity = 0.20 + 0.01 * lift_index + 0.001 * index
                else:
                    assessment = 150.0 + 10.0 * lift_index + 2.0 * index
                    prescribed = (0.65 - 0.05 * (index % 3)) * assessment
                    velocity = 0.40 + 0.02 * lift_index + 0.002 * index
            if velocity_delta is not None:
                selected_lift, selected_index, amount = velocity_delta
                if lift_index == selected_lift and index == selected_index:
                    velocity += amount
            history.append(
                replace(
                    observation,
                    assessment_kg=assessment,
                    prescribed_load_kg=prescribed,
                    velocity_mps=velocity,
                )
            )
        schedule_template = (int(row.row_id.rsplit("-", 2)[-2]) + lift_index + rotation_delta) % 4
        lifts[lift_name] = dataset.LiftInputs(
            tuple(history), interventions.history_segments(schedule_template)
        )
    inputs = replace(row.inputs, lifts=lifts)
    updated = replace(row, inputs=inputs)
    dataset.validate_public_row(updated)
    return updated


def _rekey(row: dataset.PublicForecastRow, key: str) -> dataset.PublicForecastRow:
    return replace(row, row_id=key, inputs=replace(row.inputs, entity_id=key))


def _fixed_summary_payload(rows: tuple[dataset.PublicForecastRow, ...]) -> np.ndarray:
    raw = feature_matrix(rows, _fixed_stats())
    normalized = ((raw - FIXTURE_MEAN) / FIXTURE_SCALE).astype(np.float32)
    return _pack_summary(normalized)


def _c6_deleted_positions() -> list[int]:
    return [
        39 * lift + 5 * channel + summary
        for lift in range(3)
        for channel in (0, 1, 3, 4)
        for summary in range(5)
    ]


def _oracle_ordered(row: dataset.PublicForecastRow, stats: NormalizationStats) -> np.ndarray:
    values = []
    for lift_name in ("squat", "bench_press", "deadlift"):
        lift = row.inputs.lifts[lift_name]
        previous = None
        for observation in lift.history:
            segment = next(
                item
                for item in lift.history_schedule
                if item.start_day <= observation.day <= item.end_day
            )
            assessment = observation.assessment_kg
            prescribed = observation.prescribed_load_kg
            velocity = observation.velocity_mps
            values.append(
                [
                    assessment,
                    prescribed,
                    velocity,
                    prescribed / assessment,
                    0.0 if previous is None else assessment - previous.assessment_kg,
                    0.0 if previous is None else velocity - previous.velocity_mps,
                    segment.dose,
                    segment.intensity,
                    segment.dose * segment.intensity,
                ]
            )
            previous = observation
    values_array = np.asarray(values, dtype=np.float64).reshape(3, 32, 9)
    for lift_index in range(3):
        for channel_index in range(6):
            values_array[lift_index, :, channel_index] = (
                values_array[lift_index, :, channel_index]
                - stats.input_mean[lift_index][channel_index]
            ) / stats.input_scale[lift_index][channel_index]
        values_array[lift_index, :, 6] /= 1.2
        values_array[lift_index, :, 7] /= 1.0
        values_array[lift_index, :, 8] /= 1.2
    plan = row.inputs.declared_future_plan
    context = np.asarray(
        [
            row.inputs.origin_day / interventions.ORIGIN_DAY,
            row.inputs.horizon_days / 56.0,
            plan.dose / 1.2,
            plan.intensity,
            plan.dose * plan.intensity / 1.2,
            (plan.end_day - plan.start_day + 1) / 56.0,
            *np.eye(4)[PLAN_ORDER.index(plan.plan_id)],
        ],
        dtype=np.float64,
    )
    return np.concatenate((values_array.reshape(864), context))


def test_t1_summary_parity_and_independent_scalar_formula() -> None:
    rows = _fixtures()
    stats = _fixed_stats()
    observed = feature_matrix(rows, stats)
    prepared = prepare_batch(
        tuple(TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in rows),
        stats,
    ).tensors
    history = prepared.history.numpy().astype(np.float64)
    times = np.arange(32, dtype=np.float64)
    centered_times = times - times.mean()
    denominator = float(centered_times @ centered_times)
    for row_index in range(96):
        cursor = 0
        for lift_index in range(3):
            for channel_index in range(6):
                series = history[row_index, lift_index, :, channel_index]
                expected = (
                    series[0],
                    series[-1],
                    float(series.mean()),
                    float(series.std(ddof=0)),
                    float(centered_times @ (series - series.mean()) / denominator),
                )
                np.testing.assert_allclose(
                    observed[row_index, cursor : cursor + 5], expected, atol=1e-6, rtol=1e-6
                )
                cursor += 5
            for channel_index in range(3):
                schedule = history[row_index, lift_index, :, 6 + channel_index]
                expected = (
                    float(schedule.mean()),
                    float(schedule[-4:].mean()),
                    float(schedule[-1]),
                )
                np.testing.assert_allclose(
                    observed[row_index, cursor : cursor + 3], expected, atol=1e-6, rtol=1e-6
                )
                cursor += 3
        np.testing.assert_array_equal(
            observed[row_index], feature_matrix((rows[row_index],), stats)[0]
        )
        assert cursor == 117


def test_t2_ordered_history_parity_and_chronological_oracle() -> None:
    rows = _fixtures()
    stats = _fixed_stats()
    ordered = _ordered_features(rows, stats)
    prepared = prepare_batch(
        tuple(TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in rows),
        stats,
    ).tensors
    history = prepared.history[:, :, :, :9].numpy().astype(np.float64).reshape(96, 864)
    plan = prepared.plan_numeric.numpy().astype(np.float64)
    one_hot = np.eye(4, dtype=np.float64)[prepared.plan_index.numpy()]
    expected = np.concatenate((history, plan, one_hot), axis=1)
    np.testing.assert_array_equal(ordered, expected)
    for row_index, row in enumerate(rows):
        for lift_index, lift_name in enumerate(("squat", "bench_press", "deadlift")):
            assert tuple(item.day for item in row.inputs.lifts[lift_name].history) == (
                observations.HISTORY_OBSERVATION_DAYS
            )
            for date_index, day in enumerate(observations.HISTORY_OBSERVATION_DAYS):
                assert row.inputs.lifts[lift_name].history[date_index].day == day
                for channel_index in range(9):
                    index = (lift_index * 32 + date_index) * 9 + channel_index
                    assert (
                        ordered[row_index, index]
                        == history[row_index, (lift_index * 32 + date_index) * 9 + channel_index]
                    )
    raw = _raw_history(TemporalModelInput.from_forecast_inputs(rows[0].row_id, rows[0].inputs))
    assert torch.count_nonzero(raw[:, 0, 4:6]) == 0
    swapped_lifts = dict(rows[0].inputs.lifts)
    first_lift = swapped_lifts["squat"]
    history_values = list(first_lift.history)
    left, right = history_values[10], history_values[20]
    history_values[10] = replace(
        left,
        assessment_kg=right.assessment_kg,
        prescribed_load_kg=right.prescribed_load_kg,
        velocity_mps=right.velocity_mps,
    )
    history_values[20] = replace(
        right,
        assessment_kg=left.assessment_kg,
        prescribed_load_kg=left.prescribed_load_kg,
        velocity_mps=left.velocity_mps,
    )
    swapped_lifts["squat"] = replace(first_lift, history=tuple(history_values))
    swapped = replace(rows[0], inputs=replace(rows[0].inputs, lifts=swapped_lifts))
    dataset.validate_public_row(swapped)
    actual = _ordered_features((swapped,), stats)[0]
    oracle = _oracle_ordered(swapped, stats)
    np.testing.assert_allclose(actual, oracle, atol=1e-6, rtol=1e-6)
    assert not np.array_equal(actual, ordered[0])


def test_t3_packed_padding_and_exact_feature_masks() -> None:
    rows = _fixtures()
    payload = _fixed_summary_payload(rows)
    raw = feature_matrix(rows, _fixed_stats())
    normalized = ((raw - FIXTURE_MEAN) / FIXTURE_SCALE).astype(np.float32)
    np.testing.assert_array_equal(payload[:, :117], normalized[:, :117])
    assert np.all(payload[:, 117:864] == np.float32(0.0))
    np.testing.assert_array_equal(payload[:, 864:], normalized[:, 117:127])
    c3 = payload
    c5 = worker._config_features("C5", c3)
    c6 = worker._config_features("C6", c3)
    assert np.all(c5[:, :864] == np.float32(0.0))
    np.testing.assert_array_equal(c5[:, 864:], c3[:, 864:])
    deleted = _c6_deleted_positions()
    assert len(deleted) == 60 and len(set(deleted)) == 60
    assert np.all(c6[:, deleted] == np.float32(0.0))
    retained = sorted(set(range(874)) - set(deleted))
    np.testing.assert_array_equal(c6[:, retained], c3[:, retained])
    for values in (c5[:, :864], c6[:, deleted], payload[:, 117:864]):
        assert not np.signbit(values).any()
        assert np.all(values.view(np.uint32) == 0)


def test_t4_context_only_ignores_recomputed_history_and_schedule() -> None:
    rows = _fixtures("A")
    alternate = tuple(_with_history(row, family="B", rotation_delta=1) for row in rows)
    first = worker._config_features("C5", _fixed_summary_payload(rows))
    second = worker._config_features("C5", _fixed_summary_payload(alternate))
    np.testing.assert_array_equal(first, second)


def test_t5_assessment_load_omission_is_invariant_at_every_lift_and_date() -> None:
    rows = _fixtures("A")
    stats = _fixed_stats()
    mean = FIXTURE_MEAN
    scale = FIXTURE_SCALE
    for context_index, base in enumerate(rows[::4]):
        variants = []
        for lift_index in range(3):
            for observation_index in range(32):
                for assessment_factor, load_factor in ((1.1, 1.0), (1.0, 0.9), (1.2, 0.8)):
                    lift_name = ("squat", "bench_press", "deadlift")[lift_index]
                    original_lift = base.inputs.lifts[lift_name]
                    observations_list = list(original_lift.history)
                    current = observations_list[observation_index]
                    observations_list[observation_index] = replace(
                        current,
                        assessment_kg=current.assessment_kg * assessment_factor,
                        prescribed_load_kg=current.prescribed_load_kg * load_factor,
                    )
                    changed_lifts = dict(base.inputs.lifts)
                    changed_lifts[lift_name] = replace(
                        original_lift, history=tuple(observations_list)
                    )
                    variants.append(
                        _rekey(
                            replace(base, inputs=replace(base.inputs, lifts=changed_lifts)),
                            f"{base.row_id}-variant-{len(variants)}",
                        )
                    )
        for assessment_factor, load_factor in ((1.1, 1.0), (1.0, 0.9), (1.2, 0.8)):
            joint = _with_history(
                base, assessment_factor=assessment_factor, load_factor=load_factor
            )
            variants.append(_rekey(joint, f"{base.row_id}-variant-{len(variants)}"))
        raw = feature_matrix(tuple(variants), stats)
        standardized = ((raw - mean) / scale).astype(np.float32)
        changed_payload = worker._config_features("C6", _pack_summary(standardized))
        baseline = worker._config_features("C6", _fixed_summary_payload((base,)))[0]
        np.testing.assert_array_equal(
            changed_payload, np.broadcast_to(baseline, changed_payload.shape)
        )
        assert context_index < 12


def test_t6_identity_order_target_and_sidecar_isolation() -> None:
    rows = _fixtures()
    stats = _fixed_stats()
    baseline = feature_matrix(rows, stats)
    renamed = tuple(
        replace(
            row,
            row_id=f"renamed-{index}",
            inputs=replace(row.inputs, entity_id=f"renamed-{index}"),
            targets={target: float(index + 1000) for target in EXPECTED_TARGETS},
        )
        for index, row in enumerate(rows)
    )
    for index, value in enumerate(feature_matrix(renamed, stats)):
        np.testing.assert_array_equal(value, baseline[index])
    reversed_rows = feature_matrix(tuple(reversed(rows)), stats)
    by_id = {row.row_id: value for row, value in zip(reversed(rows), reversed_rows, strict=True)}
    for row, value in zip(rows, baseline, strict=True):
        np.testing.assert_array_equal(by_id[row.row_id], value)
    model_input = TemporalModelInput.from_forecast_inputs(rows[0].row_id, rows[0].inputs)
    assert not {"targets", "latent_state", "future_state"} & set(model_input.__dataclass_fields__)
    value = json.loads(canonical_json_bytes(rows[0]))
    with pytest.raises(ValueError, match="truth row fields invalid"):
        evaluate._parse_truth_row({**value, "latent_state": {"canary": 1}})
    future = json.loads(canonical_json_bytes(rows[0]))
    future["inputs"]["lifts"]["squat"]["history"][0]["day"] = 224
    with pytest.raises(ValueError):
        evaluate._parse_truth_row(future)


def test_t7_fit_only_normalization_and_refitted_ablation_invariance() -> None:
    rows = _fixtures()
    fit_rows = rows[:64]
    development_rows = rows[64:]
    fit_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in fit_rows
    )
    fit_targets = tuple(
        tuple(row.targets[target] for target in EXPECTED_TARGETS) for row in fit_rows
    )
    first = NormalizationStats.fit_train(fit_inputs, fit_targets)
    altered_development = tuple(
        replace(row, targets={target: float(index + 2000) for target in EXPECTED_TARGETS})
        for index, row in enumerate(development_rows)
    )
    _ = altered_development
    again = NormalizationStats.fit_train(fit_inputs, fit_targets)
    assert first == again

    modified_fit = tuple(
        _with_history(row, assessment_factor=1.1, load_factor=1.0) for row in fit_rows
    )
    modified_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in modified_fit
    )
    modified_stats = NormalizationStats.fit_train(modified_inputs, fit_targets)
    original_summary = feature_matrix(fit_rows, first)
    modified_summary = feature_matrix(modified_fit, modified_stats)
    original_mean = original_summary.mean(axis=0)
    original_scale = np.maximum(original_summary.std(axis=0, ddof=0), 1e-6)
    modified_mean = modified_summary.mean(axis=0)
    modified_scale = np.maximum(modified_summary.std(axis=0, ddof=0), 1e-6)
    retained = sorted(set(range(127)) - set(_c6_deleted_positions()))
    np.testing.assert_array_equal(original_mean[retained], modified_mean[retained])
    np.testing.assert_array_equal(original_scale[retained], modified_scale[retained])
    original_c6 = worker._config_features(
        "C6",
        _pack_summary(((original_summary - original_mean) / original_scale).astype(np.float32)),
    )
    modified_c6 = worker._config_features(
        "C6",
        _pack_summary(((modified_summary - modified_mean) / modified_scale).astype(np.float32)),
    )
    np.testing.assert_array_equal(original_c6, modified_c6)
    assert first.target_mean == modified_stats.target_mean
    assert first.target_scale == modified_stats.target_scale

    history_changed = tuple(_with_history(row, family="B", rotation_delta=1) for row in fit_rows)
    changed_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in history_changed
    )
    changed_stats = NormalizationStats.fit_train(changed_inputs, fit_targets)
    original_context_raw = feature_matrix(fit_rows, first)[:, 117:127]
    changed_context_raw = feature_matrix(history_changed, changed_stats)[:, 117:127]
    np.testing.assert_array_equal(
        original_context_raw.mean(axis=0), changed_context_raw.mean(axis=0)
    )
    np.testing.assert_array_equal(original_context_raw.std(axis=0), changed_context_raw.std(axis=0))
    original_context = worker._config_features(
        "C5",
        _pack_summary(
            (
                (feature_matrix(fit_rows, first) - feature_matrix(fit_rows, first).mean(axis=0))
                / np.maximum(feature_matrix(fit_rows, first).std(axis=0), 1e-6)
            ).astype(np.float32)
        ),
    )
    changed_summary = feature_matrix(history_changed, changed_stats)
    changed_context_payload = worker._config_features(
        "C5",
        _pack_summary(
            (
                (changed_summary - changed_summary.mean(axis=0))
                / np.maximum(changed_summary.std(axis=0), 1e-6)
            ).astype(np.float32)
        ),
    )
    np.testing.assert_array_equal(original_context, changed_context_payload)


def test_t8_positive_controls_and_context_support_rank() -> None:
    assert STUDY_ROOT == Path(__file__).resolve().parents[2]
    rows = _fixtures("A")
    stats = _fixed_stats()
    base = rows[0]
    velocity_changed = _with_history(base, velocity_delta=(0, 10, 0.01))
    base_c6 = worker._config_features("C6", _fixed_summary_payload((base,)))[0]
    changed_c6 = worker._config_features("C6", _fixed_summary_payload((velocity_changed,)))[0]
    assert np.any(base_c6 != changed_c6)
    later_horizon = replace(base, inputs=replace(base.inputs, horizon_days=28))
    context_base = worker._config_features("C5", _fixed_summary_payload((base,)))[0]
    context_later = worker._config_features("C5", _fixed_summary_payload((later_horizon,)))[0]
    assert context_base[865] != context_later[865]
    assessment_changed = _with_history(base, assessment_factor=1.1)
    assert not np.array_equal(
        _fixed_summary_payload((base,)), _fixed_summary_payload((assessment_changed,))
    )
    context = []
    for plan_id, horizon in product(interventions.PLAN_IDS, interventions.HORIZONS_DAYS):
        plan = interventions.declared_plan(plan_id)
        context.append(
            [
                1.0,
                horizon / 56,
                plan.dose / 1.2,
                plan.intensity,
                plan.dose * plan.intensity / 1.2,
                1.0,
                *np.eye(4)[PLAN_ORDER.index(plan_id)],
            ]
        )
    context_matrix = np.repeat(np.asarray(context, dtype=np.float64), 8, axis=0)
    singular = np.linalg.svd(context_matrix - context_matrix.mean(axis=0), compute_uv=False)
    assert np.count_nonzero(singular > singular[0] * 1e-6) == 4
    assert context_matrix.shape == (96, 10)
    assert np.array_equal(context_matrix[:, [0, 3, 5]], np.asarray([[1, 0.75, 1]] * 96))
    fixture_context = feature_matrix(_fixtures(), stats)[:, 117:127]
    fixture_singular = np.linalg.svd(
        fixture_context - fixture_context.mean(axis=0), compute_uv=False
    )
    assert fixture_context.shape == (96, 10)
    assert np.count_nonzero(fixture_singular > fixture_singular[0] * 1e-6) == 4
    assert stats.input_scale[0][0] > 0


def test_initialization_biases_shapes_and_deterministic_batch_stream() -> None:
    for learner, parameter_count, expected_bias_count in (("L", 2_625, 3), ("N", 28_099, 35)):
        starts = []
        for _ in range(2):
            model = worker._new_model(learner)
            receipt = worker.initialize_model(model, 293201)
            starts.append(receipt["initial_state_sha256"])
            assert receipt["bias_parameter_count"] == expected_bias_count
            assert receipt["bias_nonzero_count"] == 0
            assert sum(parameter.numel() for parameter in model.parameters()) == parameter_count
            assert all(
                not torch.count_nonzero(parameter)
                for name, parameter in model.named_parameters()
                if name.endswith("bias")
            )
        assert starts[0] == starts[1]
    orders = []
    for _ in range(2):
        generator = torch.Generator(device="cpu").manual_seed(293301)
        epoch_orders = [torch.randperm(9_984, generator=generator) for _ in range(60)]
        orders.append(epoch_orders)
    for left, right in zip(*orders, strict=True):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
        assert len(torch.unique(left)) == 9_984


def test_fit_payload_has_no_development_or_validation_labels(tmp_path: Path) -> None:
    arrays = {
        "fit_s": np.zeros((9_984, 874), dtype=np.float32),
        "fit_o": np.zeros((9_984, 874), dtype=np.float32),
        "fit_y_kg": np.zeros((9_984, 3), dtype=np.float64),
        "development_s": np.zeros((2_304, 874), dtype=np.float32),
        "development_o": np.zeros((2_304, 874), dtype=np.float32),
        "development_row_ids": np.asarray([f"d-{index}" for index in range(2_304)]),
        "validation_s": np.zeros((3_072, 874), dtype=np.float32),
        "validation_o": np.zeros((3_072, 874), dtype=np.float32),
        "validation_row_ids": np.asarray([f"v-{index}" for index in range(3_072)]),
    }
    payload = tmp_path / "fit-input.npz"
    np.savez(payload, **arrays)
    assert set(worker._load_payload(payload)) == set(arrays)
    arrays["validation_y_kg"] = np.zeros((3_072, 3), dtype=np.float64)
    np.savez(payload, **arrays)
    with pytest.raises(ValueError, match="missing or forbidden fields"):
        worker._load_payload(payload)
    assert len(array_payload_digest({"x": np.zeros(1, dtype=np.float32)})) == 64


def test_memory_admission_boundary_15_98_available_and_12_projected_passes() -> None:
    gib = 1024**3
    decision = run_res293.memory_admission(
        projected_peak_rss_bytes=12 * gib,
        available_ram_bytes=int(15.98 * gib),
        effective_memory_headroom_bytes=int(19.54 * gib),
    )
    assert decision["status"] == "PASS"
    assert decision["required_available_ram_and_limit_bytes"] == 14 * gib
    assert decision["checks"]["projected_peak_within_hard_process_ceiling"] is True


def test_preliminary_e_keeps_memory_admission_pending() -> None:
    gib = 1024**3
    pending = run_res293.preliminary_memory_admission(
        {
            "available_ram_bytes": int(15.98 * gib),
            "effective_memory_limit_bytes": int(19.54 * gib),
            "effective_memory_headroom_bytes": int(19.54 * gib),
        }
    )
    assert pending["status"] == "PENDING_UNTIL_F_PROJECTION"
    assert pending["available_ram_threshold_not_applied_before_F"] is True


def test_memory_admission_missing_f_projection_is_not_qualified() -> None:
    gib = 1024**3
    decision = run_res293.memory_admission(None, 20 * gib, 20 * gib)
    assert decision["status"] == "NOT_QUALIFIED"
    assert decision["checks"]["f_projection_present_and_finite"] is False


def test_memory_admission_projection_over_12_gib_fails() -> None:
    gib = 1024**3
    decision = run_res293.memory_admission(12 * gib + 1, 20 * gib, 20 * gib)
    assert decision["status"] == "FAIL"
    assert decision["checks"]["projected_peak_within_f_gate"] is False


def test_memory_admission_available_ram_below_projection_plus_reserve_fails() -> None:
    gib = 1024**3
    decision = run_res293.memory_admission(10 * gib, 12 * gib - 1, 20 * gib)
    assert decision["status"] == "FAIL"
    assert decision["checks"]["available_ram_covers_projection_plus_host_reserve"] is False


def test_memory_admission_host_limit_below_projection_plus_reserve_fails() -> None:
    gib = 1024**3
    decision = run_res293.memory_admission(10 * gib, 20 * gib, 12 * gib - 1)
    assert decision["status"] == "FAIL"
    assert decision["checks"]["host_container_limit_covers_projection_plus_host_reserve"] is False


def test_public_res293_verification_recomputes_saved_validation_evidence() -> None:
    receipt = verify_public_run()
    assert receipt["published_artifacts_verified"] == 102
    assert receipt["fit_records_verified"] == 30
    assert receipt["validation_metrics_recomputed"] == 90
    assert receipt["per_seed_contrasts_recomputed"] == 105
    assert receipt["primary_contrasts_recomputed"] == 21
    assert receipt["checkpoint_files_read"] == 0


def test_public_res293_verification_rejects_missing_published_artifacts(tmp_path: Path) -> None:
    receipt_path = (
        STUDY_ROOT
        / "results/studies/res293_representation_learner_information/analysis-receipt.json"
    )
    (tmp_path / receipt_path.name).write_bytes(receipt_path.read_bytes())
    with pytest.raises(PublicVerificationError, match="missing published artifact"):
        verify_published_artifacts(tmp_path)


def test_public_res293_verification_rejects_altered_published_artifact(tmp_path: Path) -> None:
    result_root = STUDY_ROOT / "results/studies/res293_representation_learner_information"
    for name in ("analysis-receipt.json", "report.md", "canonical-metrics.csv"):
        (tmp_path / name).write_bytes((result_root / name).read_bytes())
    metrics_path = tmp_path / "canonical-metrics.csv"
    metrics_path.write_bytes(metrics_path.read_bytes() + b"altered")
    with pytest.raises(PublicVerificationError, match="hash/size mismatch"):
        verify_published_artifacts(tmp_path)
