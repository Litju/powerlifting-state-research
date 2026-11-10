"""RES-616 task contract, observation target, firewall, independence and pairing checks."""

import math
import random
from pathlib import Path

import numpy as np
import pytest

from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting import (  # noqa: E501
    dataset,
    interventions,
    observations,
    population,
)
from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.dynamics import (  # noqa: E501
    simulate_lift,
)
from powerlifting_state_research.contracts.serialization import (
    require_scientific_id,
    sha256_record,
)
from powerlifting_state_research.observable import contract as C
from powerlifting_state_research.observable import data as D
from powerlifting_state_research.probabilistic import scoring

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results/studies/observable_strength_forecasting"
SMOKE_A = C.SMOKE_ROLE_BASE["TEST_A"]


@pytest.fixture(scope="module")
def cohorts() -> dict[str, D.ObsCohort]:
    return D.build_cohorts("TEST_A", 120, SMOKE_A, C.SCENARIOS)


# ----------------------------------------------------------------------------- identity


def test_frozen_protocol_file_is_the_code_contract() -> None:
    assert (RESULT_DIR / "protocol.json").read_bytes() == C.protocol_bytes()
    assert C.PROTOCOL_DIGEST == sha256_record(C.PROTOCOL)
    assert C.STUDY_ID.endswith("~" + C.PROTOCOL_DIGEST[7:19])


def test_new_identities_are_valid_distinct_and_content_bound() -> None:
    expected = {
        "task": "task",
        "qoi": "qoi",
        "observation_protocol": "observation-model",
        "evaluation": "evaluation",
    }
    ids = C.PROTOCOL["identities"]
    for key, cls in expected.items():
        require_scientific_id(ids[key], key, expected_class=cls)
    latent = {
        "psr:task:latent-capacity-change@1.0.0~44fc77353e7a",
        "psr:qoi:latent-capacity-change@1.0.0~675491124046",
        "psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8",
        "psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f",
    }
    assert not latent & set(ids.values())
    assert len(set(ids.values())) == 4 and C.STUDY_ID not in ids.values()
    changed = {**C.TASK_SEMANTICS, "horizons_days": (14, 28)}
    assert C._id("task", "future-observed-strength-assessment-forecasting", changed) != C.TASK_ID
    assert ids["task"] == C.TASK_ID


def test_roles_are_sized_balanced_and_seeded_as_frozen() -> None:
    assert C.ROLE_ROWS == {
        "FIT": 12288,
        "DEV": 3072,
        "CAL_C": 3072,
        "CAL_G": 3072,
        "TEST_A": 3072,
        "TEST_B": 3072,
    }
    assert C.ROLE_BASE == {
        "FIT": 616101,
        "DEV": 616201,
        "CAL_C": 616301,
        "CAL_G": 616401,
        "TEST_A": 616501,
        "TEST_B": 616601,
    }
    for rows in C.ROLE_ROWS.values():
        assert rows % 12 == 0
    assert all(C.ROLE_ROWS[r] // 12 == 256 for r in ("DEV", "CAL_C", "CAL_G", "TEST_A", "TEST_B"))
    for base in C.ROLE_BASE.values():
        seeds = C.role_seeds(base)
        assert [
            seeds[k]
            for k in ("population", "intervention", "observation", "split", "serialization")
        ] == list(range(base, base + 5))


@pytest.mark.parametrize("smoke", [False, True])
def test_seed_streams_are_unique_and_never_collide_with_prior_studies(smoke: bool) -> None:
    values = C.all_seed_values(smoke)
    assert len(values) == len(set(values)) == 6 * 8 + 1
    assert not set(values) & C.prior_seed_values()
    assert not set(C.all_seed_values(True)) & set(C.all_seed_values(False))
    assert C.MODEL_SEED not in {v for b in C.ROLE_BASE.values() for v in C.role_seeds(b).values()}


# ----------------------------------------------------------------------------- target contract


def test_task_constants_match_the_declared_task() -> None:
    assert (C.ORIGIN_DAY, C.HISTORY_LAST_DAY, C.HORIZONS) == (224, 223, (14, 28, 56))
    assert C.ASSESSMENT_DAYS == {14: 237, 28: 251, 56: 279}
    assert all(day == C.ORIGIN_DAY + h - 1 for h, day in C.ASSESSMENT_DAYS.items())
    assert set(C.PLANS) == {"cessation", "step_down", "continue", "step_up"}
    assert C.PROTOCOL["models"]["M2"]["training_seed_stability"] == "NOT TESTED"
    assert len(C.MODELS) == 3


def test_latent_truncation_cannot_be_applied_to_the_observed_target() -> None:
    assert C.check_target_compatibility(C.OBSERVED_TARGET_KIND, "cessation") is False
    for plan in C.PLANS:
        assert C.check_target_compatibility(C.OBSERVED_TARGET_KIND, plan) is False
    with pytest.raises(ValueError, match="not latent capacity change"):
        C.check_target_compatibility(C.LATENT_TARGET_KIND, "cessation")
    with pytest.raises(ValueError, match="unknown target kind"):
        C.check_target_compatibility("something_else", "cessation")
    # the RES-615 support rule rejects the observed target outright
    with pytest.raises(ValueError, match="latent capacity change"):
        scoring.require_support_target(C.OBSERVED_TARGET_KIND, "cessation")
    assert "NO truncation" in C.PROTOCOL["target"]["cessation_rule"]


# ----------------------------------------------------------------------------- generation


def test_control_histories_equal_the_public_generator(cohorts: dict[str, D.ObsCohort]) -> None:
    config = D.generation_config(120, SMOKE_A)
    public = [row for split, row in dataset.iter_public_rows(config) if split == "train"]
    control = cohorts["CONTROL"]
    assert [f"TEST_A-{row.row_id}" for row in public] == list(control.row_ids)
    for lift_index, lift in enumerate(C.LIFTS):
        for column, field in enumerate(("assessment_kg", "prescribed_load_kg", "velocity_mps")):
            expected = [[getattr(o, field) for o in r.inputs.lifts[lift].history] for r in public]
            assert np.array_equal(
                np.asarray(expected), control.raw_history[:, lift_index, :, column]
            )
    assert control.raw_history.shape == (120, 3, 32, 10)
    days = control.raw_history  # history stops at day 223
    assert observations.HISTORY_OBSERVATION_DAYS[-1] == 223 and days.shape[2] == 32


def test_target_is_assessment_on_the_correct_day_and_distinct_from_E_and_C(
    cohorts: dict[str, D.ObsCohort],
) -> None:
    control = cohorts["CONTROL"]
    truth = control.truth.open()
    config = D.generation_config(120, SMOKE_A)
    population_rng = random.Random(config.population_seed)
    records = dataset._row_records(config)
    checked = 0
    for split, index, plan_id, horizon, templates in records:
        coordinates = tuple(population_rng.random() for _ in range(16))
        if split != "train":
            continue
        athlete = population.parameters_from_coordinates(coordinates)
        plan = interventions.declared_plan(plan_id)
        row = control.row_ids.index(f"TEST_A-entity-{index:06d}")
        for lift_index, lift in enumerate(C.LIFTS):
            sessions = interventions.training_sessions(templates[lift_index], plan)
            trajectory = simulate_lift(
                athlete.lifts[lift], sessions, athlete.stimulus_reference, 279
            )
            day = 224 + horizon - 1
            assert trajectory.expressed_performance_kg[day] == truth.e[row, lift_index]
            assert trajectory.latent_capacity_kg[day] == truth.c[row, lift_index]
            assert trajectory.expressed_performance_kg[223] == truth.last_e[row, lift_index]
            # not the neighbouring day: indexing is origin + horizon - 1
            assert (
                trajectory.expressed_performance_kg[day + (1 if day < 279 else -1)]
                != truth.e[row, lift_index]
            )
        checked += 1
        if checked == 20:
            break
    assert checked == 20
    assert not np.array_equal(truth.y, truth.e) and not np.array_equal(truth.e, truth.c)
    cv = np.array([observations.ASSESSMENT_CV[lift] for lift in C.LIFTS])
    z = (truth.y / truth.e - 1.0) / cv
    assert abs(z.mean()) < 0.2 and 0.85 < z.std() < 1.15 and (truth.y > 0).all()


def test_future_stream_changes_target_only_never_inputs() -> None:
    base = D.generation_config(60, C.SMOKE_ROLE_BASE["DEV"])
    rows_a = [r for r in D.iter_raw_rows(base, 111) if r.split == "train"]
    rows_b = [r for r in D.iter_raw_rows(base, 222) if r.split == "train"]
    a = D._assemble("DEV", "CONTROL", rows_a, [r.inputs for r in rows_a])
    b = D._assemble("DEV", "CONTROL", rows_b, [r.inputs for r in rows_b])
    assert np.array_equal(a.raw_history, b.raw_history) and np.array_equal(
        a.base_features, b.base_features
    )
    assert np.array_equal(a.truth.open().e, b.truth.open().e)  # same trajectories
    assert not np.array_equal(a.truth.open().y, b.truth.open().y)  # different future draws


def test_no_future_information_in_model_inputs(cohorts: dict[str, D.ObsCohort]) -> None:
    control = cohorts["CONTROL"]
    fields = set(D.ObsCohort.__dataclass_fields__)
    assert fields == {
        "role",
        "scenario",
        "row_ids",
        "stratum",
        "raw_history",
        "plan_numeric",
        "base_features",
        "truth",
    }
    assert control.raw_history.shape[2] == 32  # 32 weekly observations through day 223
    truth = control.truth.open()
    # no model-visible array reproduces the target, E or C
    for array in (control.raw_history[:, :, :, 0], control.base_features):
        flat = array.reshape(array.shape[0], -1)
        for hidden in (truth.y, truth.e, truth.c):
            for lift in range(3):
                assert not any(
                    np.array_equal(flat[:, col], hidden[:, lift]) for col in range(flat.shape[1])
                )
    assert all(rid.startswith("TEST_A-") for rid in control.row_ids)
    assert control.last_assessment.shape == (120, 3)
    assert np.array_equal(control.last_assessment, control.raw_history[:, :, 31, 0])


def test_truth_is_sealed_until_opened(cohorts: dict[str, D.ObsCohort]) -> None:
    fresh = D.build_cohorts("DEV", 60, C.SMOKE_ROLE_BASE["DEV"])["CONTROL"]
    assert fresh.truth.opened is False
    fresh.truth.open()
    assert fresh.truth.opened is True


def test_cessation_lowers_capacity_but_observed_performance_can_rise(
    cohorts: dict[str, D.ObsCohort],
) -> None:
    control = cohorts["CONTROL"]
    truth = control.truth.open()
    cess = control.plan == C.PLANS.index("cessation")
    assert cess.sum() == 30
    assert ((truth.c - truth.last_c)[cess] <= 1e-12).all()  # latent change nonpositive
    assert ((truth.e - truth.last_e)[cess] > 0).any()  # expressed performance rises somewhere
    assert (
        truth.y[cess] > control.last_assessment[cess]
    ).any()  # so Y > last, impossible if truncated
    assert (truth.y - control.last_assessment)[cess].max() > 0


# ----------------------------------------------------------------------------- pairing and shifts


def test_scenarios_are_entity_paired(cohorts: dict[str, D.ObsCohort]) -> None:
    control = cohorts["CONTROL"]
    for name in ("VELOCITY_NOISE_SHIFT", "ADAPTATION_TIMESCALE_SHIFT"):
        other = cohorts[name]
        assert other.row_ids == control.row_ids and np.array_equal(other.stratum, control.stratum)
        assert np.array_equal(other.plan_numeric, control.plan_numeric)


def test_velocity_shift_changes_only_history_velocity(cohorts: dict[str, D.ObsCohort]) -> None:
    control, shifted = cohorts["CONTROL"], cohorts["VELOCITY_NOISE_SHIFT"]
    assert np.array_equal(control.truth.open().y, shifted.truth.open().y)
    assert np.array_equal(control.truth.open().e, shifted.truth.open().e)
    difference = shifted.raw_history - control.raw_history
    # velocity (channel 2) differs; assessment/load/schedule/age channels are identical
    for channel in (0, 1, 6, 7, 8, 9):
        assert not difference[:, :, :, channel].any()
    assert np.abs(difference[:, :, :, 2]).max() > 0
    sd = difference[:, :, :, 2].std(axis=(0, 2))
    expected = [observations.VELOCITY_SD_MPS[lift] for lift in C.LIFTS]
    assert np.allclose(sd, expected, rtol=0.1)
    # derived channels (observed relative load is unchanged; velocity delta is recomputed)
    assert not (shifted.raw_history[:, :, 1:, 5] - control.raw_history[:, :, 1:, 5]).std() == 0


def test_adaptation_shift_transform_and_paired_noise(cohorts: dict[str, D.ObsCohort]) -> None:
    coordinates = tuple(i / 16 + 0.01 for i in range(16))
    moved = D.adaptation_shift_transform(coordinates)
    for index in range(16):
        expected = (
            math.sqrt(coordinates[index]) if index in C.SHIFTED_COORDINATES else coordinates[index]
        )
        assert moved[index] == expected
    names = population.COORDINATE_ORDER
    assert [names[i] for i in C.SHIFTED_COORDINATES] == [
        "squat_adaptation_retention_28d",
        "bench_adaptation_retention_28d",
        "deadlift_adaptation_retention_28d",
    ]
    original = population.parameters_from_coordinates(coordinates).lifts["squat"]
    shifted = population.parameters_from_coordinates(moved).lifts["squat"]
    assert shifted.adaptation_time_days < original.adaptation_time_days  # shorter time constant
    assert (
        shifted.baseline_kg == original.baseline_kg
        and shifted.suppression_gain == original.suppression_gain
    )
    control, shifted_cohort = cohorts["CONTROL"], cohorts["ADAPTATION_TIMESCALE_SHIFT"]
    ct, st = control.truth.open(), shifted_cohort.truth.open()
    assert not np.array_equal(ct.y, st.y) and not np.array_equal(
        control.raw_history, shifted_cohort.raw_history
    )
    cv = np.array([observations.ASSESSMENT_CV[lift] for lift in C.LIFTS])
    # identical future noise draws: the relative measurement error is paired entity by entity
    assert np.allclose(ct.y / ct.e - 1.0, st.y / st.e - 1.0, atol=1e-12)
    assert np.abs((ct.y / ct.e - 1.0) / cv).max() < 6


def test_roles_are_independent_populations() -> None:
    a = D.build_cohorts("FIT", 60, C.SMOKE_ROLE_BASE["FIT"])["CONTROL"]
    b = D.build_cohorts("DEV", 60, C.SMOKE_ROLE_BASE["DEV"])["CONTROL"]
    assert not set(a.row_ids) & set(b.row_ids)
    left = {tuple(np.round(r, 6)) for r in a.raw_history[:, 0, :, 0]}
    right = {tuple(np.round(r, 6)) for r in b.raw_history[:, 0, :, 0]}
    assert not left & right
    with pytest.raises(ValueError, match="balanced|wrong size"):
        D._check_cohort("X", [], 12)
