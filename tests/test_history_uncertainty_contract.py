"""RES-639 frozen contract: identity, seeds, Ridge reference, decision rules, source pins."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from powerlifting_state_research.contracts.serialization import sha256_record
from powerlifting_state_research.history_uncertainty import contract as K
from powerlifting_state_research.observable import contract as base

ROOT = Path(__file__).resolve().parents[1]
RES616 = ROOT / "results/studies/observable_strength_forecasting"
RESULT_DIR = ROOT / "results/studies/history_conditional_uncertainty"

# Pinned SHA-256 of every file that defines the RES-616 Ridge replay (unchanged since 978fa53).
# A change to any of them could silently alter the frozen location forecast; update only with an
# explicit new Ridge-identity verification, never to make this test pass.
PINNED_REPLAY_SOURCES = {
    "src/powerlifting_state_research/observable/contract.py": "4c184515a5ae6d7a33738320324476c2c09f287e1c9e299a17ef6e088d4866c5",
    "src/powerlifting_state_research/observable/data.py": "4296e10c9d8b78f1aacc2d1361b69d2468d796e2f6cfc35ca246925f1e0de124",
    "src/powerlifting_state_research/observable/models.py": "b97af574c2c79ff1954264829b4c8071e74f237c0bdfed4d786638b75a9b9f42",
    "src/powerlifting_state_research/probabilistic/reference.py": "a32f4349496844c9f512baba492b1524293bbcc6bf76463bb3ae0aa59c0cc829",
    "src/powerlifting_state_research/probabilistic/scoring.py": "531d71d319c7ed2807da819e19f2e2cb2c9e17476620f28d9269cb3f6af6b4da",
    "src/powerlifting_state_research/models/temporal_expert.py": "4ac7144d3bfd3b4fe9edc6bc672a2fa7aceb2bd1b00fd9bfc168c224969a42a7",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py": "273feab777b054928955c05ec9b93dcae57bb789cde231fd5e75664d2442b16f",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py": "f349dc6b8f6abdf76c8d93747d6a92710d2de9f25366a7d697bdafae13356f84",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py": "f04500db820b9a08408a67efa89a0bc8c0ac4cb9574c265f70b357aa8a413fb5",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py": "8888a476cab856c3266b53dfbf6519223697768af8512dac7b6983771c2fcf9e",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py": "28234fff0385b0294e98053211315a5c12327bec0dd8f07965899f33bd170992",
    "uv.lock": "1fb0aba23cc139f4f6c4781755907f5a207be97554479b77837f50fa047c3748",
}


def test_frozen_protocol_file_is_the_code_contract() -> None:
    assert (RESULT_DIR / "protocol.json").read_bytes() == K.protocol_bytes()
    assert K.PROTOCOL_DIGEST == sha256_record(K.PROTOCOL)
    assert K.STUDY_ID.endswith("~" + K.PROTOCOL_DIGEST[7:19])


def test_identities_are_content_bound_and_distinct_from_res616() -> None:
    ids = [K.QOI_ID, K.UNCERTAINTY_MODEL_ID, K.EVALUATION_ID]
    assert len(set(ids)) == 3
    assert not set(ids) & {base.TASK_ID, base.QOI_ID, base.EVALUATION_ID, base.STUDY_ID}
    assert K.STUDY_ID != base.STUDY_ID
    assert all(i.startswith("psr:") and "@1.0.0~" in i for i in ids)


def test_mission_baseline_and_authorization_gate_are_recorded() -> None:
    assert K.MISSION == "PSR_OBSERVABLE_HISTORY_CONDITIONAL_UNCERTAINTY_ONE_SHOT"
    assert K.BASELINE_MAINLINE_SHA == "6696bebe61adbc57abf406445acfe92e008d2fcf"
    assert "separate owner authorization" in K.PROTOCOL["authorization"]


@pytest.mark.parametrize("smoke", [False, True])
def test_seed_streams_are_unique_and_disjoint_from_every_prior_study(smoke: bool) -> None:
    values = K.all_seed_values(smoke)
    assert len(values) == len(set(values)) == 4 * 8
    assert not set(values) & K.prior_seed_values()
    assert not set(values) & set(base.all_seed_values(smoke))
    assert not set(K.all_seed_values(True)) & set(K.all_seed_values(False))
    assert base.MODEL_SEED not in values and base.SMOKE_MODEL_SEED not in values


def test_test_parents_are_independent_and_roles_balanced() -> None:
    assert K.ROLE_ROWS == {"SCALE_FIT": 6144, "SCALE_CAL": 3072, "TEST_A": 3072, "TEST_B": 3072}
    for rows in (K.ROLE_ROWS, K.SMOKE_ROLE_ROWS):
        assert all(n % K.STRATA == 0 for n in rows.values())
    assert K.PARENTS == ("TEST_A", "TEST_B")
    a, b = (set(K.role_seeds(K.ROLE_BASE[p]).values()) for p in K.PARENTS)
    assert not a & b
    bases = sorted(K.ROLE_BASE.values())
    assert all(y - x >= 8 for x, y in zip(bases, bases[1:], strict=False))


def test_task_semantics_are_the_res616_task_unchanged() -> None:
    assert (K.LIFTS, K.PLANS, K.HORIZONS) == (base.LIFTS, base.PLANS, base.HORIZONS)
    assert K.ASSESSMENT_DAYS == {14: 237, 28: 251, 56: 279}
    assert (base.ORIGIN_DAY, base.HISTORY_LAST_DAY) == (224, 223)
    assert K.PROTOCOL["task"] == base.TASK_SEMANTICS
    assert K.PROTOCOL["target"]["kind"] == "observed_assessment_kg"
    assert "NO truncation" in K.PROTOCOL["target"]["cessation_rule"]
    with pytest.raises(ValueError):
        base.check_target_compatibility(base.LATENT_TARGET_KIND, "cessation")
    assert base.check_target_compatibility(base.OBSERVED_TARGET_KIND, "cessation") is False


def test_frozen_estimator_constants() -> None:
    assert (K.ERROR_FLOOR_KG, K.RIDGE_PENALTY) == (0.25, 0.05)
    assert (K.SIGMA_MIN_KG, K.SIGMA_MAX_KG) == (0.25, 100.0)
    assert (K.SCALE_C_MIN, K.SCALE_C_MAX) == (0.25, 4.0)
    assert K.MODELS == ("B_GROUP", "B_MAG", "H_HISTORY")
    assert (K.PRIMARY_CONTENDER, K.PRIMARY_COMPARATOR) == ("H_HISTORY", "B_MAG")
    assert (K.N_MAG_FEATURES, K.N_HISTORY_FEATURES) == (14, 141)
    assert K.BOOTSTRAP_REPLICATES == 1000
    assert K.INTERVAL_LEVELS == (0.5, 0.8, 0.9)


def test_resource_limits_match_the_authorization() -> None:
    r = K.RESOURCES
    assert r["max_campaign_cpu_seconds"] == 2400 and r["max_wall_seconds"] == 3600
    assert r["max_process_ram_bytes"] == 2 * 1024**3
    assert (r["workers"], r["threads"], r["retries"]) == (1, 1, 0)
    assert r["gpu"] is False and r["cloud"] is False and r["automatic_budget_increase"] is False


def test_ridge_reference_matches_committed_res616_artifacts() -> None:
    ref = K.RIDGE_REFERENCE
    frozen_bytes = (RES616 / "full/frozen-parameters.json").read_bytes()
    frozen = json.loads(frozen_bytes)
    manifest = json.loads((RES616 / "full/manifest.json").read_text())
    seal = json.loads((RES616 / "full/freeze-seal.json").read_text())
    import hashlib

    digest = hashlib.sha256(frozen_bytes).hexdigest()
    assert digest == ref["frozen_parameters_sha256"] == seal["frozen_parameters_sha256"]
    assert manifest["output_sha256"]["frozen-parameters.json"] == digest
    assert frozen["ridge"]["alpha"] == ref["alpha"] == 0.01
    assert frozen["ridge"]["beta_sha256"] == ref["beta_sha256"]
    assert frozen["ridge"]["beta_sha256"].startswith("e360665d7c568dff")
    assert frozen["ridge"]["dev_rmse_by_alpha"] == ref["dev_rmse_by_alpha"]
    assert frozen["cohort_row_id_sha256"]["FIT"] == ref["cohort_row_id_sha256"]["FIT"]
    assert frozen["cohort_row_id_sha256"]["DEV"] == ref["cohort_row_id_sha256"]["DEV"]
    assert frozen["study_id"] == ref["study_id"] == base.STUDY_ID == manifest["study_id"]
    assert manifest["protocol_digest"] == ref["protocol_digest"] == base.PROTOCOL_DIGEST
    assert (RES616 / "protocol.json").read_bytes() == base.protocol_bytes()
    assert (ref["fit_rows"], ref["dev_rows"]) == (12288, 3072)
    assert (ref["fit_base_seed"], ref["dev_base_seed"]) == (616101, 616201)


def test_res616_disposition_is_unchanged() -> None:
    summary = json.loads((RES616 / "full/summary.json").read_text())
    assert summary["disposition"] == "OBSERVABLE_FORECASTING_NOT_QUALIFIED"


def test_replay_source_files_are_byte_identical_to_the_pinned_digests() -> None:
    assert set(PINNED_REPLAY_SOURCES) == set(K.REPLAY_SOURCE_FILES)
    assert K.source_digests(ROOT) == PINNED_REPLAY_SOURCES


def test_ridge_hyperparameters_in_the_replayed_implementation_are_unchanged() -> None:
    from powerlifting_state_research.observable import models

    assert models.ALPHAS == (0.01, 0.1, 1.0, 10.0)
    assert models.N_RIDGE_FEATURES == 163


# ------------------------------------------------------------------ decision rules


def _evidence(**changes: Any) -> dict[str, Any]:
    def parent() -> dict[str, Any]:
        return {
            "primary_rel_pct": -1.5,
            "primary_ci_hi": -0.02,
            "crps": {"B_GROUP": 6.70, "B_MAG": 6.60, "H_HISTORY": 6.50},
            "nll": {"B_GROUP": 3.9, "B_MAG": 3.87, "H_HISTORY": 3.86},
            "cov90": 0.90,
            "cov90_by_lift": [0.90, 0.90, 0.90],
            "severe_cells": 0,
            "conditional_cov90": [0.9] * 15,
            "width90": {"B_MAG": 22.0, "H_HISTORY": 21.5},
            "shift": {
                "VELOCITY_NOISE_SHIFT": {
                    "crps": {"B_MAG": 6.9, "H_HISTORY": 6.8},
                    "cov90": 0.89,
                },
                "ADAPTATION_TIMESCALE_SHIFT": {
                    "crps": {"B_MAG": 7.1, "H_HISTORY": 7.0},
                    "cov90": 0.88,
                },
            },
        }

    out: dict[str, Any] = {"blocked": None, "nonfinite": 0}
    for p in K.PARENTS:
        out[p] = parent()
    for key, value in changes.items():
        parent_name, _, field = key.partition("__")
        if field:
            out[parent_name][field] = value
        else:
            out[key] = value
    return out


def test_all_guardrails_pass_gives_qualified() -> None:
    assert K.decide(_evidence())["disposition"] == K.DISPOSITIONS[0]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"TEST_A__primary_rel_pct": -0.99}, 2),
        ({"TEST_B__primary_rel_pct": 0.5}, 2),
        ({"TEST_A__primary_ci_hi": 0.0}, 2),
        ({"TEST_B__primary_ci_hi": 0.01}, 2),
    ],
)
def test_primary_screen_must_hold_on_both_parents(change: dict[str, Any], expected: int) -> None:
    assert K.decide(_evidence(**change))["disposition"] == K.DISPOSITIONS[expected]


@pytest.mark.parametrize(
    "change",
    [
        {"TEST_A__nll": {"B_GROUP": 3.9, "B_MAG": 3.87, "H_HISTORY": 3.876}},
        {"TEST_B__cov90": 0.84},
        {"TEST_B__cov90": 0.96},
        {"TEST_A__cov90_by_lift": [0.90, 0.84, 0.90]},
        {"TEST_A__severe_cells": 1},
        {"TEST_B__conditional_cov90": [0.9] * 14 + [0.83]},
        {"TEST_A__width90": {"B_MAG": 22.0, "H_HISTORY": 24.3}},
        {"TEST_A__crps": {"B_GROUP": 6.40, "B_MAG": 6.60, "H_HISTORY": 6.50}},
        {
            "TEST_B__shift": {
                "VELOCITY_NOISE_SHIFT": {"crps": {"B_MAG": 6.9, "H_HISTORY": 6.91}, "cov90": 0.89}
            }
        },
        {
            "TEST_B__shift": {
                "ADAPTATION_TIMESCALE_SHIFT": {
                    "crps": {"B_MAG": 7.1, "H_HISTORY": 7.0},
                    "cov90": 0.79,
                }
            }
        },
    ],
)
def test_any_failed_guardrail_downgrades_a_score_gain(change: dict[str, Any]) -> None:
    result = K.decide(_evidence(**change))
    assert result["disposition"] == K.DISPOSITIONS[1]
    assert result["criteria"]["both_parent_screens"] is True
    assert not all(result["criteria"]["guardrails"].values())


def test_guardrail_boundaries_are_inclusive_and_not_relaxed() -> None:
    edge = _evidence(
        TEST_A__nll={"B_GROUP": 3.9, "B_MAG": 3.87, "H_HISTORY": 3.875},
        TEST_A__cov90=0.85,
        TEST_B__cov90=0.95,
        TEST_A__primary_rel_pct=-1.0,
        TEST_A__width90={"B_MAG": 20.0, "H_HISTORY": 22.0},
    )
    assert K.decide(edge)["disposition"] == K.DISPOSITIONS[0]


def test_blocked_and_nonfinite_are_fail_closed() -> None:
    assert K.decide(_evidence(blocked="ridge"))["disposition"] == K.DISPOSITIONS[3]
    assert K.decide(_evidence(nonfinite=1))["disposition"] == K.DISPOSITIONS[3]


def test_a_negative_result_is_a_complete_disposition() -> None:
    worse = _evidence(TEST_A__primary_rel_pct=2.0, TEST_B__primary_rel_pct=1.0)
    assert K.decide(worse)["disposition"] == K.DISPOSITIONS[2]


def test_four_required_dispositions_exist_with_rules() -> None:
    assert set(K.DISPOSITION_RULES) == set(K.DISPOSITIONS)
    assert len(K.DISPOSITIONS) == 4


def test_protocol_guardrails_equal_the_executable_ones() -> None:
    for key, value in K.GUARDRAILS.items():
        assert K.PROTOCOL["guardrails"][key] == ([*value] if isinstance(value, tuple) else value)


def test_sensitivity_note_matches_the_gaussian_oracle_calculation() -> None:
    rng = np.random.default_rng(0)

    def crps(sp: Any, st: Any) -> Any:
        return np.sqrt(2 / np.pi) * np.sqrt(sp**2 + st**2) - sp / np.sqrt(np.pi)

    st = np.exp(rng.normal(0, 0.20, 1_000_000))
    st /= np.sqrt(np.mean(st**2))
    gain = 100 * (crps(1.0, st).mean() - crps(st, st).mean()) / crps(1.0, st).mean()
    assert 0.9 < gain < 1.1
    assert "0.25/0.56/0.99/1.54" in K.PROTOCOL["endpoints"]["sensitivity_note"]
