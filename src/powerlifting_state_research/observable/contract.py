"""Frozen scientific contract for the RES-616 observable-assessment forecasting study.

The target is a *synthetic noisy strength assessment* ``Y`` measured on a future day under the
simulator's declared measurement law. It is distinct from latent capacity ``C`` and from expressed
performance ``E``. It is not a real competition one-repetition maximum.
"""

from __future__ import annotations

from typing import Any

from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..probabilistic import contract as ref_contract

STUDY_SLUG = "observable-strength-assessment-forecasting"
STUDY_VERSION = "1.0.0"
OBSERVED_TARGET_KIND = "observed_assessment_kg"
LATENT_TARGET_KIND = "latent_capacity_change_kg"

LIFTS = ("squat", "bench_press", "deadlift")
PLANS = ("cessation", "step_down", "continue", "step_up")
HORIZONS = (14, 28, 56)
ORIGIN_DAY = 224
HISTORY_LAST_DAY = 223
ASSESSMENT_DAYS = {14: 237, 28: 251, 56: 279}
INTERVAL_LEVELS = (0.8, 0.9)
SCENARIOS = ("CONTROL", "VELOCITY_NOISE_SHIFT", "ADAPTATION_TIMESCALE_SHIFT")
PARENTS = ("TEST_A", "TEST_B")
SHIFTED_COORDINATES = (4, 8, 12)  # adaptation-retention coordinates of squat/bench/deadlift
BOOTSTRAP_REPLICATES = 1000
MODELS = ("M0", "M1", "M2")
ARMS = ("M0_C", "M1_C", "M1_G", "M2_C", "M2_G")

ROLE_ROWS = {
    "FIT": 12_288,
    "DEV": 3_072,
    "CAL_C": 3_072,
    "CAL_G": 3_072,
    "TEST_A": 3_072,
    "TEST_B": 3_072,
}
ROLE_BASE = {
    "FIT": 616101,
    "DEV": 616201,
    "CAL_C": 616301,
    "CAL_G": 616401,
    "TEST_A": 616501,
    "TEST_B": 616601,
}
SMOKE_ROLE_ROWS = {"FIT": 240, "DEV": 60, "CAL_C": 60, "CAL_G": 60, "TEST_A": 60, "TEST_B": 60}
SMOKE_ROLE_BASE = {
    "FIT": 616811,
    "DEV": 616821,
    "CAL_C": 616831,
    "CAL_G": 616841,
    "TEST_A": 616851,
    "TEST_B": 616861,
}
MODEL_SEED = 616701
SMOKE_MODEL_SEED = 616871


def role_seeds(base: int) -> dict[str, int]:
    """Five generation seeds plus separate future-assessment, shift-noise, bootstrap streams."""
    return {
        "population": base,
        "intervention": base + 1,
        "observation": base + 2,
        "split": base + 3,
        "serialization": base + 4,
        "future_assessment": base + 5,
        "velocity_shift_noise": base + 6,
        "bootstrap": base + 7,
    }


def all_seed_values(smoke: bool = False) -> list[int]:
    bases = SMOKE_ROLE_BASE if smoke else ROLE_BASE
    values = [v for base in bases.values() for v in role_seeds(base).values()]
    return [*values, SMOKE_MODEL_SEED if smoke else MODEL_SEED]


def prior_seed_values() -> set[int]:
    """Seeds of canonical and earlier studies that must never be reused."""
    values = set(ref_contract.CANONICAL_IID_SEEDS)
    for cohorts in (ref_contract.COHORTS, ref_contract.SMOKE_COHORTS):
        for item in cohorts.values():
            values |= set(item["seeds"])
    values |= {383001, 383002, 383003}
    for start in (847200, 847300, 847400, 847500, 848100, 848200, 848300, 849200, 849300):
        values |= set(range(start, start + 10))
    return values


def check_target_compatibility(target_kind: str, plan_id: str) -> bool:
    """Return False (never truncate). Reject any attempt to treat this target as latent change."""
    if target_kind == LATENT_TARGET_KIND:
        raise ValueError("the RES-616 target is observed assessment Y, not latent capacity change")
    if target_kind != OBSERVED_TARGET_KIND:
        raise ValueError(f"unknown target kind: {target_kind!r}")
    return False  # expressed performance can rise under cessation as suppression dissipates


def _id(component_class: str, slug: str, semantics: dict[str, Any]) -> str:
    digest = sha256_record(
        {
            "format": "PSR_RES616_COMPONENT_ID_V1",
            "component_class": component_class,
            "slug": slug,
            "version": STUDY_VERSION,
            "semantics": semantics,
        }
    )
    return f"psr:{component_class}:{slug}@{STUDY_VERSION}~{digest[7:19]}"


TASK_SEMANTICS: dict[str, Any] = {
    "origin_day": ORIGIN_DAY,
    "history_last_day": HISTORY_LAST_DAY,
    "horizons_days": HORIZONS,
    "assessment_days": {str(k): v for k, v in ASSESSMENT_DAYS.items()},
    "lifts": LIFTS,
    "declared_plans": PLANS,
    "information": "histories through day 223, schedule through day 223, declared plan, horizon; "
    "no latent state, parameter, entity id, or future observation",
}
QOI_SEMANTICS: dict[str, Any] = {
    "quantity": "future noisy standardized synthetic strength assessment Y",
    "unit": "kg",
    "form": "absolute (not change)",
    "definition": "Y = E[t]*(1+Normal(0,cv_lift)) at t=origin+horizon-1 via the simulator's "
    "declared assessment law; E is expressed performance, C is latent capacity (both hidden)",
    "not": "real competition 1RM; latent capacity; expressed performance",
}
OBSERVATION_SEMANTICS: dict[str, Any] = {
    "history": "existing PerformanceObservation law on days 6,13,...,223",
    "future": "same law via sample_performance_observation with an independent future RNG stream",
    "assessment_cv": {"squat": "0.05", "bench_press": "0.04", "deadlift": "0.05"},
}
EVALUATION_SEMANTICS: dict[str, Any] = {
    "primary": "paired macro CRPS difference M2_C minus M1_C on CONTROL, per TEST parent",
    "scores": ["CRPS", "NLL", "MAE", "central 80/90 coverage and width"],
    "bootstrap": "1000 stratified entity-cluster replicates per parent, PCG64",
}
TASK_ID = _id("task", "future-observed-strength-assessment-forecasting", TASK_SEMANTICS)
QOI_ID = _id("qoi", "future-observed-strength-assessment-kg", QOI_SEMANTICS)
OBSERVATION_PROTOCOL_ID = _id(
    "observation-model", "future-assessment-measurement-protocol", OBSERVATION_SEMANTICS
)
EVALUATION_ID = _id(
    "evaluation", "observable-assessment-proper-score-evaluation", EVALUATION_SEMANTICS
)

DISPOSITION_RULES = {
    "OBSERVABLE_FORECASTING_QUALIFIED_WITHIN_SYNTHETIC_WORLD": "primary superiority screen met on "
    "both parents AND M2_C macro CRPS below M0_C on both control parents AND pooled M2_C 90% "
    "coverage within [85,95]% on both control parents AND no nonfinite predictions",
    "OBSERVABLE_FORECASTING_NOT_QUALIFIED": "M2_C macro CRPS not below M1_C on both control "
    "parents, OR M2_C not below M0_C on both control parents",
    "OBSERVABLE_FORECASTING_MIXED_OR_INCONCLUSIVE": "every other completed outcome",
    "BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE": "a ceiling, rights check or technical failure "
    "prevented completion; no budget extension",
}

PROTOCOL: dict[str, Any] = {
    "format": "PSR_RES616_OBSERVABLE_FORECASTING_PROTOCOL_V1",
    "linear_issue": "RES-616",
    "identities": {
        "task": TASK_ID,
        "qoi": QOI_ID,
        "observation_protocol": OBSERVATION_PROTOCOL_ID,
        "evaluation": EVALUATION_ID,
    },
    "target": {
        "kind": OBSERVED_TARGET_KIND,
        "semantics": QOI_SEMANTICS,
        "cessation_rule": "NO truncation. Cessation lowers capacity C but expressed performance E "
        "may rise as suppression dissipates, so Y<=0-type support rules from RES-615 are forbidden "
        "(check_target_compatibility rejects the latent kind and never truncates)",
        "negative_mass": "report P(Y<0) under each Gaussian; introduce no support transformation",
    },
    "task": TASK_SEMANTICS,
    "firewall": {
        "feature_permissions": "RES-615 visible-feature builder (history summaries, schedule, plan "
        "numerics, plan indicators) plus plan/horizon one-hots; entity ids, C, E, parameters and "
        "future draws are never inputs",
        "future_noise": "separate random.Random stream per role (seed base+5), consumed only when "
        "the target is generated; paired scenarios reuse the same stream",
        "truth_order": [
            "generate FIT, DEV, CAL_C, CAL_G; fit M1 (alpha on DEV), M2 (FIT, DEV early stop)",
            "fit sigma tables on DEV, c on CAL_C, G on CAL_G; freeze and hash all parameters",
            "generate TEST_A/TEST_B scenarios; compute and hash all predictions (seal)",
            "open TEST truth once; score; no refitting or rescoring",
        ],
        "strength": "in-process organizational barrier recorded by hashes; not adversarial",
    },
    "roles": {
        "rows": ROLE_ROWS,
        "strata_balance": "256 entities per plan/horizon stratum in each 3072-row cohort",
        "seed_bases": ROLE_BASE,
        "seed_layout": [
            "population",
            "intervention",
            "observation",
            "split",
            "serialization",
            "future_assessment (base+5)",
            "velocity_shift_noise (base+6, TEST only)",
            "bootstrap (base+7, TEST only)",
        ],
        "model_seed": MODEL_SEED,
        "smoke": {
            "rows": SMOKE_ROLE_ROWS,
            "seed_bases": SMOKE_ROLE_BASE,
            "model_seed": SMOKE_MODEL_SEED,
        },
        "generation": "GenerationConfig(train_rows=N, validation_rows=12); keep the N train rows",
        "test_parents": "exactly two independent parents; no replacement after results",
    },
    "models": {
        "M0": "persistence: latest admissible assessment (day 223) for the lift",
        "M1": {
            "family": "ridge",
            "target": "Y minus latest assessment, per lift",
            "features": "127 RES-615 visible summaries + 12 plan/horizon one-hots + 12 one-hots x "
            "that lift's last assessment and assessment slope (24) = 163, FIT-standardized",
            "penalty": "minimize mean squared error + alpha*||beta||^2, unpenalized intercept",
            "alpha_candidates": ["0.01", "0.1", "1", "10"],
            "alpha_selection": "DEV only: lowest mean over lifts of DEV RMSE",
        },
        "M2": {
            "family": "GRU (LiftSharedTemporalExpert, unchanged architecture, new random init)",
            "target": "Y minus latest assessment, FIT-standardized per lift; "
            "prediction = last + delta",
            "normalization": "FIT-only input/target statistics",
            "optimizer": "AdamW lr 1e-3, weight decay 1e-4, betas (0.9,0.999), batch 256, "
            "gradient clip 1.0, constant lr, dropout as in architecture",
            "loss": "equal-target MSE in standardized space",
            "max_epochs": 20,
            "early_stopping": "DEV standardized MSE, patience 4, min improvement 1e-4, "
            "best state kept",
            "attempts": 1,
            "seed": MODEL_SEED,
            "training_seed_stability": "NOT TESTED",
            "note": "historical latent-capacity GRU outputs are NOT used as observable predictors",
        },
    },
    "calibration": {
        "sigma_raw": "per lift x plan x horizon RMS of DEV residuals, clipped to [0.25,100] kg "
        "(all three models)",
        "global_c": "per-lift c = clip(sqrt(mean_CAL_C(r^2/sigma_raw^2)),0.25,4); sigma_C = "
        "clip(c*sigma_raw,0.25,100)  [arms M0_C, M1_C, M2_C]",
        "group_G": "per lift x plan x horizon g = clip(sqrt((n*R+kappa)/(n+kappa)),0.70,1.40), "
        "R=mean_CAL_G(r^2/sigma_C^2), n=group rows (256), kappa=256; sigma_G = clip(g*sigma_C,"
        "0.25,100)  [arms M1_G, M2_G; the contender for the temporal model is M2_G vs M2_C]",
        "no_other_proposal": True,
        "refit_after_test": False,
    },
    "endpoints": {
        "primary": "paired macro CRPS difference M2_C - M1_C on CONTROL, each TEST parent; "
        "absolute, relative %, 95% percentile entity-cluster bootstrap interval",
        "superiority_screen": "relative improvement >= 1% on EACH parent and interval upper bound "
        "< 0 on EACH parent (exploratory criterion, not a clinical meaningful change)",
        "secondary_descriptive": [
            "MAE",
            "NLL",
            "CRPS per lift",
            "80/90 coverage and width",
            "lift x plan x horizon calibration",
            "groupwise regressions",
            "nonfinite counts and denominators",
            "M2_G vs M2_C",
            "M2_G vs M1_G",
        ],
        "multiplicity": "primary is the only confirmatory inference; everything else is "
        "descriptive "
        "with unadjusted intervals and overlapping, non-independent metrics",
    },
    "bootstrap": {
        "replicates": BOOTSTRAP_REPLICATES,
        "design": "within each of 12 strata resample 256 entities with replacement; indices shared "
        "across lifts, models and scenarios; PCG64(seed base+7); percentile 2.5/97.5, linear",
    },
    "shifts": {
        "VELOCITY_NOISE_SHIFT": "add independent Normal(0, source lift velocity SD) to every "
        "history velocity only; seed base+6; targets byte-identical to CONTROL",
        "ADAPTATION_TIMESCALE_SHIFT": "population coordinates 4, 8, 12 u -> sqrt(u) before the "
        "original parameter mapping; histories and Y regenerated with the same seeds and noise "
        "streams; equations unchanged",
        "refit": False,
        "claim": "two named within-support mechanisms; 2 parents x 3 scenarios = 6 dependent "
        "scenario sets, not six populations; no claim of robustness to arbitrary shifts",
    },
    "resources": {
        "workers": 1,
        "threads": 1,
        "gpu": False,
        "cloud": False,
        "max_process_ram_bytes": 2 * 1024**3,
        "max_gru_fit_cpu_seconds": 2400,
        "max_campaign_cpu_seconds": 5400,
        "max_wall_seconds": 7200,
        "temporal_fit_attempts": 1,
        "retries": 0,
        "on_ceiling": "stop; report INCOMPLETE/BLOCKED; no extension",
        "after_test_truth_opened": "preserve records and stop on failure; never adjust and rescore",
    },
    "rights": {
        "inputs": "MIT project code and the public synthetic generator only; new seeds; no "
        "athlete data, no private RES-576/577 bytes, no historical H/H_GT/G parameters",
        "historical_checkpoints": "not loaded or used; the RES-274 latent-capacity GRU is not an "
        "observable predictor",
        "outputs": "aggregate tables, figures and manifests are project-generated (MIT); cohort "
        "rows and fitted GRU weights are not committed (weights identified by SHA-256)",
        "fail_closed": "non-empty output directory, nonfinite values or a breached ceiling stop "
        "the run",
    },
    "disposition_rules": DISPOSITION_RULES,
    "reused_from_res615": "scoring mathematics (Gaussian CRPS/NLL, intervals), visible-feature "
    "builder, group-factor and scale formulas, array/CSV helpers, rights-checked released assets",
    "nonclaims": [
        "synthetic assessment measurements, not competition 1RM records",
        "no real-athlete validity, physiological identification or causal prescription",
        "training-seed stability NOT TESTED (one fitted GRU)",
        "no robustness claim beyond two named within-support shifts",
        "pooled calibration is not subgroup calibration; statistical is not practical significance",
    ],
}

PROTOCOL_DIGEST = sha256_record(PROTOCOL)
STUDY_ID = f"psr:study:{STUDY_SLUG}@{STUDY_VERSION}~{PROTOCOL_DIGEST[7:19]}"


def protocol_document() -> dict[str, Any]:
    return {"study_id": STUDY_ID, "protocol_digest": PROTOCOL_DIGEST, "protocol": PROTOCOL}


def protocol_bytes() -> bytes:
    return canonical_json_bytes(protocol_document()) + b"\n"
