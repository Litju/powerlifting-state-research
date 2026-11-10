"""Frozen public contract for the RES-615 probabilistic reference experiment (Route B).

This is a NEW public reference. It reimplements publicly specified procedures and does not
reproduce historical M10-M12 numerical results: the original fitted parameters, calibration
factors, scoring adapters, cohorts and predictions have no recorded redistribution grant.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts.serialization import canonical_json_bytes, sha256_record
from .scoring import LATENT_CAPACITY_CHANGE

REFERENCE_SLUG = "public-probabilistic-latent-capacity-change-reference"
REFERENCE_VERSION = "1.0.0"

PLANS = ("cessation", "step_down", "continue", "step_up")
HORIZONS = (14, 28, 56)
LIFTS = ("squat", "bench_press", "deadlift")
ARMS = ("B1", "B1_T", "H", "H_T", "H_G", "H_GT")
INTERVAL_LEVELS = (0.5, 0.8, 0.9)

# Seeds are (population, intervention, observation, split, serialization). None equals a seed of
# the canonical IID realization (26901-26905), and no two roles share a seed.
COHORTS: dict[str, dict[str, Any]] = {
    "FIT": {"rows": 12_288, "seeds": [615101, 615102, 615103, 615104, 615105]},
    "CAL_C": {"rows": 3_072, "seeds": [615201, 615202, 615203, 615204, 615205]},
    "CAL_G": {"rows": 3_072, "seeds": [615301, 615302, 615303, 615304, 615305]},
    "TEST": {"rows": 3_072, "seeds": [615401, 615402, 615403, 615404, 615405]},
}
SMOKE_COHORTS: dict[str, dict[str, Any]] = {
    "FIT": {"rows": 240, "seeds": [615111, 615112, 615113, 615114, 615115]},
    "CAL_C": {"rows": 60, "seeds": [615211, 615212, 615213, 615214, 615215]},
    "CAL_G": {"rows": 60, "seeds": [615311, 615312, 615313, 615314, 615315]},
    "TEST": {"rows": 60, "seeds": [615411, 615412, 615413, 615414, 615415]},
}
CANONICAL_IID_SEEDS = (26901, 26902, 26903, 26904, 26905)

GRU_ID = "psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f"
GRU_CHECKPOINT_SHA256 = {
    "seed-383001": "f8889305226cbac69874a2a983809e2b12adfdbfb8dd6446dbce932ac02904bb",
    "seed-383002": "eb6c858e20e3a0cba5a542db605494359df83c15fac54b068ed938866d1398c4",
    "seed-383003": "c8f6bb329ee6b9e37155d95515e071b98d0aacf720f163bbe060804a0ecdef18",
}
GRU_NORMALIZATION_FILE_SHA256 = "f5aade7089c5bd962140501f842d9aacd39a34df45928077c1228fbbbf6d21ca"
GRU_MANIFEST_PATH = "models/published/public-native-temporal-expert/artifact-manifest.json"

RESOURCE_LIMITS = {
    "workers": 1,
    "blas_and_torch_threads": 1,
    "gpu": False,
    "cloud": False,
    "max_process_memory_bytes": 2 * 1024**3,
    "max_cpu_seconds": 1800,
    "retries": 0,
    "on_limit": "stop; report an honest limitation; no automatic expansion",
}

# Reproducibility tolerances for a fresh execution against the committed expected values.
# Same machine and locked environment: byte-identical tables are expected. Across CPUs/BLAS
# builds the RES-274 record bounds GRU location differences by 0.0167 kg per prediction; CRPS is
# 1-Lipschitz in the location, so no mean CRPS can move by more than that (hard bound). The
# tighter score tolerances are frozen engineering expectations, not proven bounds; the measured
# differences are reported in the closeout, and a violation is reported, never silently widened.
TOLERANCES = {
    "same_environment": "tables byte-identical",
    "crps_hard_bound_kg_abs": 0.0167,
    "cross_environment_crps_kg_abs": 1.0e-3,
    "cross_environment_nll_abs": 2.0e-3,
    "cross_environment_coverage_abs": 4.0e-3,
    "cross_environment_width_kg_abs": 5.0e-3,
    "formula_reference_abs": 1.0e-10,
}

# Every rights decision below is a record-based provenance assessment, not legal advice.
# Access, use, modification and redistribution are decided separately; a matching checksum,
# a local file, the repository MIT license or project ownership alone grants none of them.
RIGHTS_REGISTER: tuple[dict[str, Any], ...] = (
    {
        "artifact": "RES-274 PUBLIC_NATIVE GRU checkpoints seed-383001/2/3",
        "decision": "REUSED",
        "access": "public",
        "use": "permitted",
        "modification": "not needed; weights loaded unchanged",
        "redistribution": "permitted: MIT, named in the owner authorization of 2026-10-22",
        "basis": "provenance/model-artifact-redistribution.md; per-file artifact manifests",
    },
    {
        "artifact": "RES-274 normalization statistics (actual file bytes)",
        "decision": "REUSED",
        "access": "public",
        "use": "permitted",
        "modification": "not needed",
        "redistribution": "permitted: MIT artifact-manifest entry",
        "basis": (
            "artifact entry hash is authoritative; the frozen top-level summary hash conflict "
            "is preserved (provenance/normalization-and-rights-clarification.md)"
        ),
    },
    {
        "artifact": "Public synthetic generator source",
        "decision": "REUSED",
        "access": "public",
        "use": "permitted",
        "modification": "not needed; called with new seeds",
        "redistribution": "MIT repository license",
        "basis": "LICENSE; provenance/PUBLIC_FILE_ORIGINS.csv",
    },
    {
        "artifact": "Canonical IID synthetic dataset",
        "decision": "NOT_USED",
        "access": "public with attribution",
        "use": "not needed",
        "modification": "not applicable",
        "redistribution": "CC-BY-4.0 with attribution; no rows are copied here",
        "basis": "artifacts/dataset-cards; data manifest",
    },
    {
        "artifact": "New reference cohorts FIT/CAL_C/CAL_G/TEST",
        "decision": "GENERATED_AT_RUNTIME",
        "access": "regenerated from the MIT generator and frozen seeds",
        "use": "permitted",
        "modification": "not applicable",
        "redistribution": "rows are not committed; only aggregate outputs are published (MIT)",
        "basis": "generated by project-owned code; contains no athlete data",
    },
    {
        "artifact": "Original H / H_GT fitted ridge coefficients and feature standardization",
        "decision": "EXCLUDED",
        "access": "private",
        "use": "not authorized for publication",
        "modification": "not authorized",
        "redistribution": "no grant: outside the named-artifact authorization",
        "basis": "private records label model PUBLIC_NATIVE but evidence/output private",
    },
    {
        "artifact": "Original B1 calibration scale, development c multipliers and G factors",
        "decision": "EXCLUDED",
        "access": "private",
        "use": "not authorized for publication",
        "modification": "not authorized",
        "redistribution": "no grant",
        "basis": "new private parameter artifacts not named in provenance authorization",
    },
    {
        "artifact": "Original scoring, prediction and generator adapters",
        "decision": "EXCLUDED",
        "access": "private",
        "use": "not authorized for publication",
        "modification": "not authorized",
        "redistribution": "no grant; adapters also contain transient source paths",
        "basis": "docs/reproducibility.md public/restricted reproduction table",
    },
    {
        "artifact": "Original M10-M12 cohorts, truth, predictions, evaluations and receipts",
        "decision": "EXCLUDED",
        "access": "private",
        "use": "not authorized for publication",
        "modification": "not authorized",
        "redistribution": "no grant; inconsistent generic dataset-MIT shorthand not relied upon",
        "basis": "private rights disposition; dataset terms are artifact-specific",
    },
    {
        "artifact": "Public methods and aggregate summary of the original studies",
        "decision": "REFERENCED_ONLY",
        "access": "public",
        "use": "citation",
        "modification": "frozen",
        "redistribution": "newly authored CC-BY-4.0 documentation already public",
        "basis": "docs/studies/probabilistic-capacity-forecasting.md",
    },
)

PROTOCOL: dict[str, Any] = {
    "format": "PSR_PUBLIC_PROBABILISTIC_REFERENCE_PROTOCOL_V1",
    "route": "B: independent public reference implementation; NOT a reproduction of M10-M12",
    "linear_issue": "RES-615",
    "target": {
        "kind": LATENT_CAPACITY_CHANGE,
        "definition": "C[origin+h-1]-C[origin-1] in kg; simulated latent capacity, not 1RM",
        "origin_day": 224,
        "horizons_days": HORIZONS,
        "plans": PLANS,
        "lifts": LIFTS,
        "truncation_rule": (
            "upper-truncate the Gaussian at 0 for plan cessation only; valid because zero dose "
            "makes adaptation decay so the latent change is nonpositive; never applied to any "
            "other plan or target"
        ),
    },
    "location": {
        "model_id": GRU_ID,
        "checkpoint_sha256": GRU_CHECKPOINT_SHA256,
        "normalization_file_sha256": GRU_NORMALIZATION_FILE_SHA256,
        "ensemble": "arithmetic mean of three seed outputs in standardized space, then "
        "de-standardized once; weights never refit",
    },
    "cohorts": {
        "generator": "benchmarks.latent_capacity_change_with_transient_expression_forecasting"
        ".dataset.iter_public_rows",
        "construction": "GenerationConfig(train_rows=N, validation_rows=12, seeds); keep the "
        "N train-split rows; discard 12 validation rows; row ids prefixed by role",
        "roles": COHORTS,
        "smoke_roles": SMOKE_COHORTS,
        "canonical_iid_seeds_excluded": CANONICAL_IID_SEEDS,
        "split_use": {
            "FIT": "ridge scale head and B1 residual RMS only",
            "CAL_C": "per-lift scale multiplier c for B1 and H only",
            "CAL_G": "36 plan/horizon/lift group multipliers for H only",
            "TEST": "scored once after every parameter is frozen; no selection",
        },
    },
    "methods": {
        "arms": ARMS,
        "B1": "per plan/horizon/lift RMS of (y-mu) on FIT, clipped to [0.25,100] kg",
        "H": {
            "target": "log((y-mu)^2+0.25^2) per lift",
            "features": "127 visible summaries + that lift's mu + 12 plan/horizon one-hots = 140",
            "visible_summaries": "per lift and observed channel (assessment, prescribed load, "
            "velocity, observed relative load, assessment delta, velocity delta) first, last, "
            "mean, population SD, OLS slope over index 0..31 (90); per lift and schedule channel "
            "(dose, intensity, dose x intensity) mean, last-4 mean, last (27); six plan numerics "
            "and four plan indicators (10)",
            "standardization": "FIT mean and population SD, floor 1e-6",
            "ridge": "unpenalized intercept; minimize mean squared error + 0.05*||beta||^2",
            "sigma_raw": "clip(exp((b+z.beta)/2), 0.25, 100)",
        },
        "calibration_c": "c=clip(sqrt(mean_CAL_C((y-mu)^2/sigma_raw^2)),0.25,4) per method and "
        "lift; sigma=clip(c*sigma_raw,0.25,100)",
        "calibration_G": "g=clip(sqrt((n*R+kappa)/(n+kappa)),0.70,1.40), "
        "n=rows in the group (256 in the full profile), kappa=256, "
        "R=mean_CAL_G((y-mu)^2/sigma_H^2) per plan/horizon/lift; sigma_HG=clip(g*sigma_H,"
        "0.25,100)",
        "truncation_T": "applied to cessation rows of B1_T, H_T, H_GT; identical to the "
        "Gaussian arm for all other plans",
        "no_selection": "no hyperparameter search, no model selection, no winner chosen; every "
        "constant above is fixed before any scientific call",
    },
    "scoring": {
        "metrics": ["CRPS_kg", "NLL_nats", "central_coverage", "central_width_kg", "PIT_mean"],
        "interval_levels": INTERVAL_LEVELS,
        "macro": "equal mean of the three per-lift means",
        "point_forecast": "GRU location mu; separate from the truncated predictive mean",
        "joint_calibration": "not evaluated",
    },
    "truth_firewall": {
        "order": [
            "generate FIT, fit head",
            "generate CAL_C, fit c",
            "generate CAL_G, fit G",
            "compute and hash all TEST mu and sigma",
            "open TEST truth and score once",
        ],
        "strength": "in-process organizational barrier recorded by receipt hashes; not "
        "adversarial isolation",
    },
    "resources": RESOURCE_LIMITS,
    "tolerances": TOLERANCES,
    "stopping": "report the limitation if any resource ceiling is reached; do not retry or "
    "expand scope",
    "nonclaims": [
        "does not reproduce historical M11/M12 scores or parameters",
        "no real-athlete or observed-performance claim",
        "not an observable-performance benchmark (RES-616)",
        "no conditional-reliability or distribution-shift claim; M12 shifts are not run",
        "not an independent external scientific review",
    ],
}

GRU_ARTIFACT_LICENSE = "MIT"
PROTOCOL_DIGEST = sha256_record(PROTOCOL)
REFERENCE_ID = (
    f"psr:reference-experiment:{REFERENCE_SLUG}@{REFERENCE_VERSION}~{PROTOCOL_DIGEST[7:19]}"
)
RIGHTS_DIGEST = sha256_record(RIGHTS_REGISTER)


def verify_released_assets(repo_root: Path) -> dict[str, Path]:
    """Return the only redistributable model bytes this reference may load, after verifying them.

    Anything not listed in the published manifest with an MIT record and a matching SHA-256 is
    refused: a hash alone is never treated as permission.
    """
    manifest_path = repo_root / GRU_MANIFEST_PATH
    if not manifest_path.is_file():
        raise FileNotFoundError(f"released GRU manifest is missing: {GRU_MANIFEST_PATH}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_id") != GRU_ID:
        raise ValueError("released GRU model identity does not match the frozen protocol")
    records = {item["path"]: item for item in manifest["artifacts"]}
    wanted = {
        f"models/published/public-native-temporal-expert/checkpoints/{name}.pt": digest
        for name, digest in GRU_CHECKPOINT_SHA256.items()
    }
    wanted[manifest["normalization"]["path"]] = GRU_NORMALIZATION_FILE_SHA256
    resolved: dict[str, Path] = {}
    for relative, expected in wanted.items():
        record = records.get(relative)
        rights: dict[str, Any] = {} if record is None else record.get("artifact_manifest", {})
        if (
            record is None
            or record.get("sha256") != expected
            or rights.get("sha256") != expected
            or rights.get("license_expression") != GRU_ARTIFACT_LICENSE
        ):
            raise ValueError(f"artifact is not a cleared, hash-pinned release record: {relative}")
        target = repo_root / relative
        if not target.is_file():
            raise FileNotFoundError(f"cleared artifact is missing from this checkout: {relative}")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f"artifact bytes do not match the pinned SHA-256: {relative}")
        resolved[Path(relative).name] = target
    return resolved


def protocol_document() -> dict[str, Any]:
    return {
        "reference_id": REFERENCE_ID,
        "protocol_digest": PROTOCOL_DIGEST,
        "rights_register_digest": RIGHTS_DIGEST,
        "protocol": PROTOCOL,
        "rights_register": RIGHTS_REGISTER,
    }


def protocol_bytes() -> bytes:
    return canonical_json_bytes(protocol_document()) + b"\n"
