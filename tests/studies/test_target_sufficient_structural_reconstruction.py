from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import numpy as np
import pytest

from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (  # noqa: E501
    simulate_lift,
)
from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.interventions import (  # noqa: E501
    declared_plan,
    training_sessions,
)
from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (  # noqa: E501
    LIFTS,
    parameters_from_coordinates,
)
from powerlifting_state_research.contracts.serialization import sha256_record
from powerlifting_state_research.studies.target_sufficient_structural_reconstruction import (
    OBSERVATION_DAYS,
    StudyInputs,
    _acceptance_probability,
    _accepted_fraction_weight,
    _finite_difference_jacobian,
    _laplace_posterior,
    _negative_result_rows,
    _parameter_estimate_values,
    _physical_parameters,
    _source_hashes,
    assessment_nll_and_gradient,
    csv_bytes,
    fit_coordinates,
    fit_residual_model,
    generate_data,
    model_with_jacobian,
    predict_residual,
    schedule_products,
    study_inputs_from_row,
    verify_design,
)


@pytest.fixture(scope="module")
def generated_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    observations, truth = generate_data()
    return observations, truth


def test_protocol_and_frozen_evidence_are_intact() -> None:
    verify_design(Path.cwd())
    hashes = _source_hashes(Path.cwd())
    assert hashes
    assert all(value.startswith("sha256:") for value in hashes.values())
    assert sha256_record(hashes).startswith("sha256:")


def test_public_native_generation_replays_and_keeps_truth_separate(
    generated_data: tuple[list[dict[str, object]], list[dict[str, object]]],
) -> None:
    observations, truth = generated_data
    replay_observations, replay_truth = generate_data()
    assert observations == replay_observations
    assert truth == replay_truth
    assert len(observations) == len(truth) == 64
    assert {row["entity_id"] for row in observations} == {row["entity_id"] for row in truth}
    for row in observations:
        assert not {"targets", "population_coordinates", "latent_states", "truth"} & set(row)
    fields = {field.name for field in dataclasses.fields(StudyInputs)}
    assert not {"truth", "targets", "population_coordinates", "latent_states"} & fields
    first_public = observations[0]
    first_truth = truth[0]
    zero_noise = first_public["observations_by_noise_scale"]["0.0"]
    for lift in LIFTS:
        latest = zero_noise[lift][-1]
        assert latest["day"] == 223
        assert latest["assessment_kg"] == first_truth["lifts"][lift]["P_223_kg"]
        assert 0.68 <= latest["prescribed_load_kg"] / latest["assessment_kg"] < 0.71


def test_native_equations_match_generator_and_jacobian() -> None:
    coordinates = np.linspace(0.1, 0.9, 16, dtype=np.float64)
    templates = (0, 1, 2)
    plan = declared_plan("continue")
    products = schedule_products(templates, plan.plan_id)
    output = model_with_jacobian(coordinates, products)
    world = parameters_from_coordinates(coordinates.tolist())
    for lift_index, lift in enumerate(LIFTS):
        trajectory = simulate_lift(
            world.lifts[lift],
            training_sessions(templates[lift_index], plan),
            world.stimulus_reference,
            last_day=279,
        )
        offset = lift_index * len(OBSERVATION_DAYS)
        expected_history = np.asarray(
            [trajectory.expressed_performance_kg[day] for day in OBSERVATION_DAYS]
        )
        np.testing.assert_allclose(
            output.history_performance[offset : offset + len(OBSERVATION_DAYS)],
            expected_history,
            atol=1e-11,
            rtol=1e-12,
        )
        assert output.p223[lift_index] == pytest.approx(
            trajectory.expressed_performance_kg[223], abs=1e-11
        )
        assert output.c223[lift_index] == pytest.approx(trajectory.latent_capacity_kg[223])
        assert output.a223[lift_index] == pytest.approx(trajectory.chronic_adaptation[223])
        assert output.r223[lift_index] == pytest.approx(trajectory.transient_suppression[223])
        assert output.delta_c56[lift_index] == pytest.approx(
            trajectory.latent_capacity_kg[279] - trajectory.latent_capacity_kg[223]
        )
        assert output.c223[lift_index] > 0 and output.p223[lift_index] > 0
        assert 0 <= output.a223[lift_index] <= 1 and 0 <= output.r223[lift_index] <= 1
    numerical = _finite_difference_jacobian(coordinates, products, 5e-6)
    np.testing.assert_allclose(output.history_jacobian, numerical, rtol=2e-4, atol=2e-5)


def test_accepted_assessment_likelihood_gradient_and_zero_noise_rule(
    generated_data: tuple[list[dict[str, object]], list[dict[str, object]]],
) -> None:
    observations, truth = generated_data
    inputs = study_inputs_from_row(observations[4], 1.0)
    coordinates = np.asarray(truth[4]["population_coordinates"], dtype=np.float64)
    value, gradient = assessment_nll_and_gradient(coordinates, inputs)
    assert np.isfinite(value)
    assert _accepted_fraction_weight(1.0) == pytest.approx(1.0)
    assert 0 < _acceptance_probability(0.05) <= 1
    step = 1e-6
    numeric = np.empty(16, dtype=np.float64)
    for index in range(16):
        plus = coordinates.copy()
        minus = coordinates.copy()
        plus[index] += step
        minus[index] -= step
        numeric[index] = (
            assessment_nll_and_gradient(plus, inputs)[0]
            - assessment_nll_and_gradient(minus, inputs)[0]
        ) / (2 * step)
    np.testing.assert_allclose(gradient, numeric, rtol=2e-3, atol=2e-3)
    zero_noise = study_inputs_from_row(observations[4], 0.0)
    with pytest.raises(ValueError, match="degenerate likelihood"):
        assessment_nll_and_gradient(coordinates, zero_noise)


def test_bounded_full_fit_and_posterior_diagnostics(
    generated_data: tuple[list[dict[str, object]], list[dict[str, object]]],
) -> None:
    observations, truth = generated_data
    noise_free = study_inputs_from_row(observations[4], 0.0)
    fit = fit_coordinates(noise_free)
    assert fit.coordinates is not None
    assert fit.output is not None
    assert np.all((fit.coordinates >= 0) & (fit.coordinates <= 1))
    assert len(fit.starts) == 4
    assert any(bool(item["converged"]) for item in fit.starts)
    assert all("status" in item for item in fit.starts)
    for lift_index, lift in enumerate(LIFTS):
        assert fit.output.p223[lift_index] == pytest.approx(
            truth[4]["lifts"][lift]["P_223_kg"], abs=1e-8
        )
        assert fit.output.c223[lift_index] == pytest.approx(
            truth[4]["lifts"][lift]["C_223_kg"], abs=1e-8
        )
        assert fit.output.delta_c56[lift_index] == pytest.approx(
            truth[4]["lifts"][lift]["DeltaC_56_kg"], abs=1e-8
        )

    noisy = study_inputs_from_row(observations[4], 1.0)
    noisy_fit = fit_coordinates(noisy)
    posterior = _laplace_posterior(noisy, noisy_fit, "uniform")
    assert posterior["status"] in {
        "LAPLACE_APPROXIMATION_VALID",
        "POSTERIOR_BOUNDARY_MODE",
        "POSTERIOR_NON_POSITIVE_HESSIAN",
        "POSTERIOR_ILL_CONDITIONED",
        "POSTERIOR_SUPPORT_FAILURE",
        "MAP_OPTIMIZATION_FAILED",
    }
    if posterior["status"] == "LAPLACE_APPROXIMATION_VALID":
        assert posterior["accepted_draws"] == 512
        assert posterior["hessian_condition_number"] <= 1e10
        assert len(posterior["physical_parameters"]) == 17


def test_residual_training_uses_only_development_rows_and_is_bounded() -> None:
    rng = random.Random(17)
    features = np.asarray([[rng.random() for _ in range(4)] for _ in range(12)])
    residuals = np.linspace(-30.0, 30.0, 12)
    development_ids = ["dev-a", "dev-b", "dev-c", "dev-d"]
    model = fit_residual_model(features, residuals, development_ids)
    assert model["development_entity_ids"] == sorted(development_ids)
    assert not set(model["development_entity_ids"]) & {"test-a", "test-b"}
    prediction = predict_residual(model, np.full((3, 4), 1e6, dtype=np.float64))
    assert np.all(prediction <= 20.0) and np.all(prediction >= -20.0)
    point_values = _parameter_estimate_values(np.full(16, 0.5, dtype=np.float64))
    global_values, lift_values = _physical_parameters(np.full(16, 0.5, dtype=np.float64))
    assert point_values["reference_stimulus"] == pytest.approx(global_values["reference_stimulus"])
    assert point_values["squat.baseline_kg"] == pytest.approx(lift_values["squat"]["baseline_kg"])


def test_failed_optimization_posterior_and_negative_finding_are_retained() -> None:
    binding = {
        "study_id": "study-test",
        "protocol_digest": "sha256:test",
        "realization_id": "realization-test",
        "evaluation_id": "evaluation-test",
        "source_set_digest": "sha256:sources",
        "truth_sha256": "sha256:truth",
        "observations_sha256": "sha256:observations",
    }
    optimizer = csv_bytes(
        [
            {
                "eligible_final": True,
                "status": "NONCONVERGED_FEASIBLE",
            }
        ],
        ("eligible_final", "status"),
    )
    posterior = csv_bytes(
        [
            {"noise_scale": 0.0, "status": "NOT_DEFINED_NOISE_FREE_POSTERIOR"},
            {"noise_scale": 1.0, "status": "POSTERIOR_BOUNDARY_MODE"},
        ],
        ("noise_scale", "status"),
    )
    paired = csv_bytes(
        [
            {
                "contrast_id": "hybrid_minus_full_deltaC56",
                "noise_scale_a": 1.0,
                "lift": "squat",
                "rmse_difference_ci95_low": -2.0,
                "rmse_difference_ci95_high": -0.1,
            }
        ],
        (
            "contrast_id",
            "noise_scale_a",
            "lift",
            "rmse_difference_ci95_low",
            "rmse_difference_ci95_high",
        ),
    )
    identifiability = {
        "constant_input_equivalence": {
            "equivalence_status": "EXACT_COUNTEREXAMPLE_OUTSIDE_CANONICAL_TEMPLATES",
            "maximum_performance_difference_kg": 0.0,
        },
        "native_template_global_identification": "INCONCLUSIVE",
        "native_template_equivalent_solution_count": 0,
    }
    rows = _negative_result_rows(
        identifiability,
        {
            "optimizer-diagnostics.csv": optimizer,
            "posterior-diagnostics.csv": posterior,
            "paired-comparisons.csv": paired,
        },
        binding,
    )
    by_id = {row["result_id"]: row for row in rows}
    assert by_id["OPTIMIZER-FAILURE-PRESERVATION"]["status"] == "FAILURES_RETAINED"
    assert by_id["POSTERIOR-DIAGNOSTIC-FAILURES"]["status"] == "FAILURES_RETAINED"
    assert by_id["CANONICAL-TEMPLATE-GLOBAL-IDENTIFICATION"]["status"] == "INCONCLUSIVE"
    assert by_id["RESIDUAL-1.0-squat"]["status"] == "HYBRID_LOWER_TEST_RMSE_IN_THIS_CONDITION"
