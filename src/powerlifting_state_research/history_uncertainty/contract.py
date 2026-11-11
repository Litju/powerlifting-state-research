"""Frozen scientific contract for RES-639: history-conditioned predictive uncertainty.

The location forecast is the *unchanged* RES-616 Ridge (M1). Only the predictive standard
deviation of the future noisy synthetic strength assessment ``Y`` is studied. Nothing here is a
real competition one-repetition maximum, a latent-capacity quantity, or a G2 mechanistic claim.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..observable import contract as base  # RES-616 contract: read only, never mutated

STUDY_SLUG = "history-conditioned-assessment-uncertainty"
STUDY_VERSION = "1.0.0"
LINEAR_ISSUE = "RES-639"
MISSION = "PSR_OBSERVABLE_HISTORY_CONDITIONAL_UNCERTAINTY_ONE_SHOT"
BASELINE_MAINLINE_SHA = "6696bebe61adbc57abf406445acfe92e008d2fcf"

# ------------------------------------------------------------------ re-used task semantics
LIFTS = base.LIFTS
PLANS = base.PLANS
HORIZONS = base.HORIZONS
ASSESSMENT_DAYS = base.ASSESSMENT_DAYS
SCENARIOS = base.SCENARIOS
PARENTS = base.PARENTS
OBSERVED_TARGET_KIND = base.OBSERVED_TARGET_KIND
STRATA = len(PLANS) * len(HORIZONS)

# ------------------------------------------------------------------ models
MODELS = ("B_GROUP", "B_MAG", "H_HISTORY")
PRIMARY_CONTENDER = "H_HISTORY"
PRIMARY_COMPARATOR = "B_MAG"
INTERVAL_LEVELS = (0.5, 0.8, 0.9)
PIT_BINS = 10
CONDITIONAL_BINS = 5

# ------------------------------------------------------------------ populations and seeds
ROLE_ROWS = {"SCALE_FIT": 6_144, "SCALE_CAL": 3_072, "TEST_A": 3_072, "TEST_B": 3_072}
ROLE_BASE = {"SCALE_FIT": 639101, "SCALE_CAL": 639201, "TEST_A": 639301, "TEST_B": 639401}
SMOKE_ROLE_ROWS = {"SCALE_FIT": 240, "SCALE_CAL": 120, "TEST_A": 60, "TEST_B": 60}
SMOKE_ROLE_BASE = {
    "SCALE_FIT": 639811,
    "SCALE_CAL": 639821,
    "TEST_A": 639831,
    "TEST_B": 639841,
}
BOOTSTRAP_REPLICATES = 1000
SMOKE_BOOTSTRAP_REPLICATES = 50

# ------------------------------------------------------------------ estimator constants
ERROR_FLOOR_KG = 0.25  # epsilon in z = log((Y-mu)^2 + epsilon^2)
RIDGE_PENALTY = 0.05  # lambda in mean-squared-error + lambda*||beta||^2, intercept unpenalized
LOG_MU_FLOOR_KG = 1.0  # log(max(mu, floor)); guards the log feature only
SIGMA_MIN_KG = 0.25
SIGMA_MAX_KG = 100.0
SCALE_C_MIN = 0.25
SCALE_C_MAX = 4.0
N_BASE_FEATURES = 127
N_MAG_FEATURES = 2 + STRATA  # mu, log mu, 12 plan x horizon indicators
N_HISTORY_FEATURES = N_BASE_FEATURES + N_MAG_FEATURES

# ------------------------------------------------------------------ RES-616 Ridge identity
RIDGE_REFERENCE: dict[str, Any] = {
    "study_id": base.STUDY_ID,
    "protocol_digest": base.PROTOCOL_DIGEST,
    "alpha": 0.01,
    "beta_sha256": "e360665d7c568dffc7e076072bf34d6fb286bbf7ecece0fbb97e358a0781f9d9",
    "dev_rmse_by_alpha": {
        "0.01": 12.110506034691115,
        "0.1": 12.188229391518668,
        "1.0": 12.965569096413377,
        "10.0": 15.077399903796083,
    },
    "frozen_parameters_sha256": "18caaf9c7bfdfa192cf077fb5a9968265cd92a01070dd58355d14d560c4556a3",
    "fit_role": "FIT",
    "dev_role": "DEV",
    "fit_rows": base.ROLE_ROWS["FIT"],
    "dev_rows": base.ROLE_ROWS["DEV"],
    "fit_base_seed": base.ROLE_BASE["FIT"],
    "dev_base_seed": base.ROLE_BASE["DEV"],
    "cohort_row_id_sha256": {
        "FIT": "5ed815f0437c39c6738aca4ff972927d84813d45421fac73e2041b808238c941",
        "DEV": "998da1e1adc77a559ab4358e1cd2dd586584f68b3a9ad1aeebac2e4297dfb7a0",
    },
    "environment": {
        "python": "3.12.13",
        "numpy": "2.4.4",
        "torch": "2.9.1+cpu",
        "platform": "Linux x86_64",
        "threads": 1,
    },
    "dev_rmse_cross_environment_tolerance_kg": 1e-6,
}
SMOKE_RIDGE_REFERENCE_PATH = (
    "results/studies/observable_strength_forecasting/smoke/frozen-parameters.json"
)

# Source files whose bytes define the RES-616 Ridge replay. Unchanged since the RES-616 evaluation
# commit 978fa53 (verified by `git diff 978fa53 HEAD` over these paths at RES-639 freeze).
REPLAY_SOURCE_FILES = (
    "src/powerlifting_state_research/observable/contract.py",
    "src/powerlifting_state_research/observable/data.py",
    "src/powerlifting_state_research/observable/models.py",
    "src/powerlifting_state_research/probabilistic/reference.py",
    "src/powerlifting_state_research/probabilistic/scoring.py",
    "src/powerlifting_state_research/models/temporal_expert.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py",
    "uv.lock",
)


def source_digests(root: Path) -> dict[str, str]:
    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in REPLAY_SOURCE_FILES}


def role_seeds(base_seed: int) -> dict[str, int]:
    """Same eight-stream layout as RES-616 so shared generators are reused unchanged."""
    return base.role_seeds(base_seed)


def all_seed_values(smoke: bool = False) -> list[int]:
    bases = SMOKE_ROLE_BASE if smoke else ROLE_BASE
    return [v for b in bases.values() for v in role_seeds(b).values()]


def prior_seed_values() -> set[int]:
    """Every seed of RES-615/616 (full and smoke) plus the canonical earlier registries."""
    values = set(base.prior_seed_values()) | set(base.all_seed_values(False))
    values |= set(base.all_seed_values(True))
    return values


# ------------------------------------------------------------------ resources
RESOURCES: dict[str, Any] = {
    "workers": 1,
    "threads": 1,
    "gpu": False,
    "cloud": False,
    "max_process_ram_bytes": 2 * 1024**3,
    "max_campaign_cpu_seconds": 2400,
    "max_wall_seconds": 3600,
    "retries": 0,
    "automatic_budget_increase": False,
    "includes": "Ridge replay, population generation, head fitting, calibration, prediction, "
    "scoring, bootstrap and report writing",
    "on_ceiling": "stop; write BLOCKED record; never extend, retry or reduce scope",
    "after_test_truth_opened": "preserve records and stop on failure; never adjust and rescore",
    "expected_cpu_seconds_estimate": "about 250 (RES-616 receipts: 3.7 ms/row/scenario generation; "
    "no GRU training); an estimate, not a bound",
}

# ------------------------------------------------------------------ decision rules
GUARDRAILS: dict[str, Any] = {
    "primary_relative_improvement_pct": 1.0,
    "primary_ci_upper_bound": 0.0,
    "nll_deterioration_max_nats": 0.005,
    "coverage90_band": (0.85, 0.95),
    "coverage90_per_lift_band": (0.85, 0.95),
    "severe_subgroup_coverage90_band": (0.80, 0.97),
    "severe_subgroup_cells_allowed": 0,
    "conditional_scale_bin_coverage90_band": (0.84, 0.96),
    "width90_ratio_max_vs_comparator": 1.10,
    "shift_crps_reversal_allowed": False,
    "shift_pooled_coverage90_band": (0.80, 0.97),
    "nonfinite_allowed": 0,
}
DISPOSITIONS = (
    "HISTORY_UNCERTAINTY_QUALIFIED_WITHIN_SYNTHETIC_WORLD",
    "SCORE_GAIN_ONLY_CONDITIONAL_RELIABILITY_UNSUPPORTED",
    "MIXED_OR_NOT_QUALIFIED",
    "BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE",
)
DISPOSITION_RULES = {
    DISPOSITIONS[3]: "Ridge identity unverifiable, a ceiling/rights/technical failure, nonfinite "
    "predictions or scores, or scoring-denominator/identity mismatch prevented a valid completion",
    DISPOSITIONS[0]: "primary screen met on BOTH independent CONTROL parents AND "
    "H_HISTORY CRPS < B_GROUP CRPS on both AND every reliability guardrail passes on both CONTROL "
    "parents AND the shift guardrails pass on all four shifted parent/scenario sets",
    DISPOSITIONS[1]: "primary screen met on BOTH CONTROL parents but at least one reliability "
    "guardrail (NLL, pooled/per-lift coverage, severe subgroup, scale-conditional coverage, width, "
    "H_HISTORY vs B_GROUP, or shift) failed",
    DISPOSITIONS[2]: "every other completed outcome, including a statistically distinguishable "
    "gain below the 1% screen, a gain on only one parent, or no gain",
}


# ------------------------------------------------------------------ identities
def _id(component_class: str, slug: str, semantics: dict[str, Any]) -> str:
    digest = sha256_record(
        {
            "format": "PSR_RES639_COMPONENT_ID_V1",
            "component_class": component_class,
            "slug": slug,
            "version": STUDY_VERSION,
            "semantics": semantics,
        }
    )
    return f"psr:{component_class}:{slug}@{STUDY_VERSION}~{digest[7:19]}"


QOI_SEMANTICS: dict[str, Any] = {
    "quantity": "predictive standard deviation of the future noisy synthetic strength assessment Y",
    "unit": "kg",
    "location": "frozen RES-616 Ridge M1 forecast mu = last assessment + ridge delta; "
    "never changed",
    "law": "Y | x ~ Normal(mu, sigma^2) with sigma estimated per lift",
    "not": "latent capacity; expressed performance; real competition 1RM; G2 parameters",
}
EVALUATION_SEMANTICS: dict[str, Any] = {
    "primary": "paired macro CRPS difference H_HISTORY minus B_MAG on CONTROL, per TEST parent",
    "bootstrap": f"{BOOTSTRAP_REPLICATES} stratified entity-cluster replicates per parent, PCG64",
    "guardrails": {k: str(v) for k, v in GUARDRAILS.items()},
}
UNCERTAINTY_MODEL_SEMANTICS: dict[str, Any] = {
    "B_GROUP": "per lift x plan x horizon RMS of SCALE_FIT residuals",
    "B_MAG": "per-lift log-squared-residual ridge on mu, log mu and 12 plan/horizon indicators",
    "H_HISTORY": "B_MAG columns plus the 127 RES-616 participant-visible summaries",
    "floor": ERROR_FLOOR_KG,
    "penalty": RIDGE_PENALTY,
}
QOI_ID = _id("qoi", "assessment-predictive-scale-kg", QOI_SEMANTICS)
UNCERTAINTY_MODEL_ID = _id("model", "history-conditioned-scale", UNCERTAINTY_MODEL_SEMANTICS)
EVALUATION_ID = _id("evaluation", "history-uncertainty-proper-score", EVALUATION_SEMANTICS)

PROTOCOL: dict[str, Any] = {
    "format": "PSR_RES639_HISTORY_UNCERTAINTY_PROTOCOL_V1",
    "linear_issue": LINEAR_ISSUE,
    "mission": MISSION,
    "baseline_mainline_sha": BASELINE_MAINLINE_SHA,
    "authorization": "DESIGN AND IMPLEMENTATION ONLY. The full run, new scientific populations, "
    "scale fitting and TEST truth require separate owner authorization of this protocol digest.",
    "identities": {
        "qoi": QOI_ID,
        "uncertainty_models": UNCERTAINTY_MODEL_ID,
        "evaluation": EVALUATION_ID,
        "res616_task": base.TASK_ID,
        "res616_observation_protocol": base.OBSERVATION_PROTOCOL_ID,
    },
    "research_question": "Does participant-visible training history give incremental information "
    "about future strength-assessment uncertainty beyond the forecast magnitude and lift x plan x "
    "horizon? Because mu is itself history-dependent, the answer is incremental to the frozen "
    "point forecast, not the total influence of history.",
    "target": {
        "kind": OBSERVED_TARGET_KIND,
        "formula": "Y_t = E_t * (1 + eps_t), eps_t ~ Normal(0, cv_lift); E is hidden",
        "assessment_cv": base.OBSERVATION_SEMANTICS["assessment_cv"],
        "cessation_rule": "NO truncation anywhere; RES-615 latent-capacity truncation is forbidden "
        "for this target (base.check_target_compatibility enforces it)",
    },
    "task": base.TASK_SEMANTICS,
    "location_model": {
        "name": "RES-616 Ridge M1",
        "frozen": True,
        "never_refit_on_new_populations": True,
        "reconstruction": "regenerate RES-616 FIT and DEV from their published seeds; "
        "observable.models.fit_ridge; require alpha, DEV RMSE per alpha and beta SHA-256 to match",
        "reference": RIDGE_REFERENCE,
        "replay_source_sha256_pinned_in_tests": True,
        "if_unverifiable": "BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE; no substitute Ridge is allowed",
        "gru": "not trained, not loaded, not used",
    },
    "firewall": {
        "features": "mu, log mu, plan x horizon indicators, and the 127 RES-616 visible summaries "
        "(history through day 223, schedule, plan numerics, plan indicators); never entity id, "
        "latent state, expressed performance, simulator parameters or any future draw",
        "calibration_roles": ["SCALE_FIT", "SCALE_CAL"],
        "truth_order": [
            "verify Ridge identity (FIT/DEV regenerated, then discarded)",
            "generate SCALE_FIT and SCALE_CAL; fit all three scale models on SCALE_FIT only",
            "fit one RMS scale c per lift and model on SCALE_CAL only; freeze and hash",
            "generate TEST_A/TEST_B scenarios; compute and hash every prediction (seal)",
            "recompute and match the seal; open TEST truth once; score; no refitting or rescoring",
        ],
        "strength": "in-process organizational barrier recorded by hashes; not adversarial",
    },
    "roles": {
        "rows": ROLE_ROWS,
        "seed_bases": ROLE_BASE,
        "seed_layout": "base+0..4 generation, base+5 future assessment, base+6 velocity shift "
        "noise, base+7 bootstrap",
        "strata_balance": "512 (SCALE_FIT) or 256 per plan/horizon stratum",
        "independence": "seeds disjoint from RES-615/RES-616 and each other; TEST_A and TEST_B are "
        "independent parents",
        "smoke": {"rows": SMOKE_ROLE_ROWS, "seed_bases": SMOKE_ROLE_BASE, "scientific": False},
    },
    "estimator": {
        "target": "z = log((Y - mu)^2 + epsilon^2), per lift",
        "epsilon_kg": ERROR_FLOOR_KG,
        "ridge": "minimize mean((z - b - x'beta)^2) + lambda*||beta||^2, unpenalized intercept, "
        "design standardized with SCALE_FIT mean/SD (SD floor 1e-6)",
        "lambda": RIDGE_PENALTY,
        "sigma_raw": f"clip(exp(zhat/2), {SIGMA_MIN_KG}, {SIGMA_MAX_KG})",
        "calibration": f"c_l = clip(sqrt(mean_SCALE_CAL((Y-mu)^2/sigma_raw^2)), {SCALE_C_MIN}, "
        f"{SCALE_C_MAX}); sigma_final = clip(c_l*sigma_raw, {SIGMA_MIN_KG}, {SIGMA_MAX_KG})",
        "calibration_meaning": "RMS-scale calibration only; it does not establish conditional "
        "distributional calibration",
        "B_GROUP": "sigma_raw = per lift x stratum RMS of SCALE_FIT residuals; same c and clipping",
        "B_MAG": "columns: mu, log(max(mu,1 kg)), 12 stratum indicators (14)",
        "H_HISTORY": "B_MAG columns + 127 visible summaries (141); identical family, floor, "
        "penalty, standardization, calibration and clipping",
        "jensen_note": "E[log chi2_1] = -1.2704, so exp(zhat/2) is biased low for Gaussian "
        "errors; a constant shift in zhat is absorbed exactly by c (invariance tested) unless c "
        "hits a clip, which is recorded",
        "magnitude_repair": "log mu added to B_MAG because Y = E(1+eps) makes measurement SD "
        "proportional to E; a linear-in-mu term alone would understate the primary comparator",
        "settings_status": "prospectively justified, not tuned; never changed after TEST "
        "inspection",
    },
    "endpoints": {
        "primary": "paired macro CRPS difference H_HISTORY - B_MAG on CONTROL, each TEST parent; "
        "absolute kg, relative %, 95% percentile entity-cluster bootstrap interval",
        "superiority_screen": "relative improvement >= 1% AND interval upper bound < 0 on EACH "
        "parent (intersection of two independent parent tests); a pragmatic screen, not a "
        "clinically meaningful difference",
        "secondary_descriptive": [
            "CRPS and Gaussian NLL for every model",
            "lift-specific CRPS",
            "plan x horizon subgroup scores",
            "central 50/80/90 coverage, width and sharpness",
            "PIT histograms",
            "coverage conditional on predicted scale",
            "within-group variation of predicted scale",
            "subgroup under/overcoverage",
            "nonfinite counts and denominators",
            "absolute degradation and model ranking under both shifts",
        ],
        "multiplicity": "primary is the only confirmatory inference; secondary and subgroup "
        "intervals are exploratory, unadjusted and dependent",
        "sensitivity_note": "Gaussian oracle calculation: if true log-scale heterogeneity left "
        "after B_MAG has SD 0.10/0.15/0.20/0.25, even a perfect scale model gains only about "
        "0.25/0.56/0.99/1.54% CRPS; the 1% screen therefore needs large unexplained scale "
        "heterogeneity AND near-perfect recovery. A negative result is an informative finding.",
    },
    "guardrails": {k: [*v] if isinstance(v, tuple) else v for k, v in GUARDRAILS.items()},
    "disposition_rules": DISPOSITION_RULES,
    "bootstrap": {
        "replicates": BOOTSTRAP_REPLICATES,
        "design": "within each of 12 strata resample entities with replacement; indices shared "
        "across models, lifts and scenarios; PCG64(seed base+7); percentile 2.5/97.5 linear",
    },
    "shifts": {
        "VELOCITY_NOISE_SHIFT": "extra Normal(0, lift velocity SD) on history velocity only; "
        "targets byte-identical to CONTROL",
        "ADAPTATION_TIMESCALE_SHIFT": "adaptation-retention coordinates u -> sqrt(u); equations "
        "and measurement law unchanged",
        "refit": False,
        "claim": "2 parents x 3 scenarios are six dependent scenario sets from two independent "
        "parents; no robustness claim beyond two named within-support shifts",
    },
    "resources": RESOURCES,
    "rights": {
        "inputs": "MIT project code and the public synthetic generator; new seeds; no athlete "
        "data, no private bytes",
        "outputs": "aggregate tables, figures and manifests only; cohort rows, fitted Ridge "
        "coefficients and fitted scale-head coefficients are never committed (SHA-256 only)",
        "fail_closed": "non-empty output directory, missing authorization record, nonfinite "
        "values or a breached ceiling stop the run",
    },
    "nonclaims": [
        "synthetic assessment measurements, not competition 1RM records",
        "no real-athlete validity, physiological identification or causal prescription",
        "G2 identification, fitting and mechanistic reconstruction are not reopened",
        "RMS-scale calibration is not conditional distributional calibration",
        "pooled calibration is not individual or subgroup calibration",
        "statistical distinguishability is not practical significance",
        "the 1% screen is pragmatic and was not validated against any meaningful difference",
        "two parents and two named shifts give no general robustness claim",
        "no independent human peer review has occurred",
    ],
}

PROTOCOL_DIGEST = sha256_record(PROTOCOL)
STUDY_ID = f"psr:study:{STUDY_SLUG}@{STUDY_VERSION}~{PROTOCOL_DIGEST[7:19]}"


def protocol_document() -> dict[str, Any]:
    return {"study_id": STUDY_ID, "protocol_digest": PROTOCOL_DIGEST, "protocol": PROTOCOL}


def protocol_bytes() -> bytes:
    return canonical_json_bytes(protocol_document()) + b"\n"


# ------------------------------------------------------------------ decision procedure
def _within(value: float, band: tuple[float, float]) -> bool:
    return band[0] <= value <= band[1]


def decide(evidence: dict[str, Any]) -> dict[str, Any]:
    """Pure, machine-checkable disposition from per-parent evidence (see tests for the schema).

    ``evidence`` keys: ``blocked`` (reason string or None), ``nonfinite`` (int) and, per parent in
    PARENTS: ``primary_rel_pct``, ``primary_ci_hi``, ``crps`` {model: float}, ``nll`` {model},
    ``cov90`` {pooled}, ``cov90_by_lift`` [3], ``severe_cells`` int, ``conditional_cov90``
    [floats], ``width90`` {model}, and ``shift`` {scenario: {"crps": {model}, "cov90": float}}.
    """
    g = GUARDRAILS
    if evidence.get("blocked") or evidence.get("nonfinite", 0) > g["nonfinite_allowed"]:
        return {"disposition": DISPOSITIONS[3], "criteria": {"blocked": evidence.get("blocked")}}
    screen: dict[str, bool] = {}
    checks: dict[str, bool] = {}
    for p in PARENTS:
        e = evidence[p]
        screen[p] = bool(
            e["primary_rel_pct"] <= -g["primary_relative_improvement_pct"]
            and e["primary_ci_hi"] < g["primary_ci_upper_bound"]
        )
        checks[f"{p}:beats_B_GROUP"] = bool(e["crps"]["H_HISTORY"] < e["crps"]["B_GROUP"])
        checks[f"{p}:nll"] = bool(
            e["nll"]["H_HISTORY"] - e["nll"]["B_MAG"] <= g["nll_deterioration_max_nats"]
        )
        checks[f"{p}:coverage90"] = _within(e["cov90"], g["coverage90_band"])
        checks[f"{p}:coverage90_per_lift"] = all(
            _within(v, g["coverage90_per_lift_band"]) for v in e["cov90_by_lift"]
        )
        checks[f"{p}:severe_subgroup"] = e["severe_cells"] <= g["severe_subgroup_cells_allowed"]
        checks[f"{p}:scale_conditional"] = all(
            _within(v, g["conditional_scale_bin_coverage90_band"]) for v in e["conditional_cov90"]
        )
        checks[f"{p}:width"] = bool(
            e["width90"]["H_HISTORY"]
            <= g["width90_ratio_max_vs_comparator"] * e["width90"]["B_MAG"]
        )
        for scenario, s in e["shift"].items():
            checks[f"{p}:{scenario}:no_crps_reversal"] = bool(
                s["crps"]["H_HISTORY"] <= s["crps"]["B_MAG"]
            )
            checks[f"{p}:{scenario}:coverage90"] = _within(
                s["cov90"], g["shift_pooled_coverage90_band"]
            )
    both = all(screen.values())
    if not both:
        name = DISPOSITIONS[2]
    elif all(checks.values()):
        name = DISPOSITIONS[0]
    else:
        name = DISPOSITIONS[1]
    return {
        "disposition": name,
        "criteria": {"screen": screen, "both_parent_screens": both, "guardrails": checks},
    }


def log_floor(mu: float) -> float:
    return math.log(max(mu, LOG_MU_FLOOR_KG))
