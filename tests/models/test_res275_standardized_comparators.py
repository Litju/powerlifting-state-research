from dataclasses import replace

import numpy as np

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as dataset,
)
from powerlifting_state_research.evaluation.identity import TARGETS
from powerlifting_state_research.models.comparators import (
    FEATURE_COUNT,
    MODEL_SPECS,
    _standardize_features,
    feature_matrix,
    fit_comparator,
    predict_comparator,
)
from powerlifting_state_research.models.temporal_expert import (
    NormalizationStats,
    TemporalModelInput,
)
from powerlifting_state_research.models.train_temporal_expert import configure_determinism


def _small_splits() -> tuple[
    tuple[dataset.PublicForecastRow, ...], tuple[dataset.PublicForecastRow, ...]
]:
    config = dataset.GenerationConfig(train_rows=12, validation_rows=12)
    rows = dataset.iter_public_rows(config)
    train: list[dataset.PublicForecastRow] = []
    validation: list[dataset.PublicForecastRow] = []
    for split, row in rows:
        (train if split == "train" else validation).append(row)
    return tuple(train), tuple(validation)


def test_shared_feature_matrix_is_fixed_sized_and_target_free() -> None:
    train_rows, validation_rows = _small_splits()
    inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in train_rows
    )
    targets = tuple(tuple(row.targets[target] for target in TARGETS) for row in train_rows)
    stats = NormalizationStats.fit_train(inputs, targets)
    features = feature_matrix(validation_rows, stats)
    changed_targets = tuple(
        replace(
            row,
            targets={name: value + 1000.0 for name, value in row.targets.items()},
        )
        for row in validation_rows
    )

    assert features.shape == (12, FEATURE_COUNT)
    assert np.isfinite(features).all()
    assert np.array_equal(feature_matrix(changed_targets, stats), features)
    assert len({item.model_id for item in MODEL_SPECS}) == 6
    assert all(
        item.semantics["classification"] == "NEW_STANDARDIZED_COMPARATOR" for item in MODEL_SPECS
    )


def test_all_frozen_comparators_fit_and_predict_from_participant_inputs() -> None:
    train_rows, selection_rows = _small_splits()
    train_inputs = tuple(
        TemporalModelInput.from_forecast_inputs(row.row_id, row.inputs) for row in train_rows
    )
    targets = np.asarray(
        [[row.targets[target] for target in TARGETS] for row in train_rows],
        dtype=np.float64,
    )
    stats = NormalizationStats.fit_train(
        train_inputs,
        tuple(tuple(float(value) for value in row) for row in targets),
    )
    fit_features = feature_matrix(train_rows, stats)
    selection_features = feature_matrix(selection_rows, stats)
    _, _, (feature_mean, feature_scale) = _standardize_features(fit_features, selection_features)
    target_mean = targets.mean(axis=0)
    target_scale = np.maximum(targets.std(axis=0, ddof=0), 1e-6)
    selection_targets = np.asarray(
        [[row.targets[target] for target in TARGETS] for row in selection_rows],
        dtype=np.float64,
    )

    for spec in MODEL_SPECS:
        configure_determinism(383001)
        fitted = fit_comparator(
            spec.method,
            train_rows,
            selection_rows,
            fit_features,
            selection_features,
            targets,
            selection_targets,
            feature_mean,
            feature_scale,
            target_mean,
            target_scale,
            383001,
        )
        prediction = predict_comparator(
            spec.method,
            {"model_state": fitted.model_state},
            selection_rows,
            selection_features,
        )
        assert prediction.shape == (12, 3)
        assert np.isfinite(prediction).all()
        assert fitted.parameter_count >= 0
        if spec.method in {"histogram_boosted_stumps", "compact_neural"}:
            assert fitted.selection_loss is not None
            assert fitted.selected_steps is not None
        else:
            assert fitted.selection_loss is None
            assert fitted.selected_steps is None


def test_small_feature_split_keeps_each_plan_horizon_group_in_fit() -> None:
    train_rows, _ = _small_splits()
    groups = {
        (row.inputs.declared_future_plan.plan_id, row.inputs.horizon_days) for row in train_rows
    }
    assert len(groups) == 12
