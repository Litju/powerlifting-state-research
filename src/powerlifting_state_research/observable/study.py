"""RES-616 executable study: freeze, seal, open once, score, bootstrap, report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import signal
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import numpy as np
import numpy.typing as npt
import torch

from ..contracts.serialization import canonical_json_bytes
from ..probabilistic import reference as ref
from ..probabilistic import scoring
from . import contract as C
from . import data as D
from . import models as M

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ROOT = Path(__file__).resolve().parents[3]
EXPECTED_RELATIVE = "results/studies/observable_strength_forecasting"
MAX_RSS = C.PROTOCOL["resources"]["max_process_ram_bytes"]
MAX_CPU = C.PROTOCOL["resources"]["max_campaign_cpu_seconds"]
MAX_WALL = C.PROTOCOL["resources"]["max_wall_seconds"]
MAX_GRU_CPU = float(C.PROTOCOL["resources"]["max_gru_fit_cpu_seconds"])


class CeilingReached(RuntimeError):
    """A frozen resource ceiling was reached; the run stops without extension."""


def _fmt(value: float) -> str:
    return f"{value:.9f}"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Budget:
    def __init__(self) -> None:
        self.cpu0 = time.process_time()
        self.wall0 = time.time()

    def check(self) -> None:
        if int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024 > MAX_RSS:
            raise CeilingReached("peak resident memory exceeded 2 GiB")
        if time.process_time() - self.cpu0 > MAX_CPU:
            raise CeilingReached("charged CPU time exceeded 5400 s")
        if time.time() - self.wall0 > MAX_WALL:
            raise CeilingReached("wall time exceeded 7200 s")


# ------------------------------------------------------------------------------ scoring


def score_arm(mu: FloatArray, sigma: FloatArray, y: FloatArray) -> dict[str, FloatArray]:
    """Per-row, per-lift scores of N(mu, sigma^2) for the observed assessment (no truncation)."""
    out: dict[str, FloatArray] = {
        "crps": scoring.gaussian_crps(mu, sigma, y),
        "nll": scoring.gaussian_nll(mu, sigma, y),
        "abs_error": np.abs(mu - y),
        "negative_mass": scoring.positive_mass(-mu, sigma),  # P(Y < 0)
    }
    no_trunc = np.zeros(mu.shape, dtype=bool)
    cover = scoring.central_coverage_and_width(mu, sigma, y, no_trunc, C.INTERVAL_LEVELS)
    for level in C.INTERVAL_LEVELS:
        out[f"cov{int(100 * level)}"] = cover[level][0]
        out[f"width{int(100 * level)}"] = cover[level][1]
    return out


METRICS = ("crps", "nll", "abs_error", "cov80", "cov90", "width80", "width90", "negative_mass")


def stratum_matrix(stratum: IntArray) -> IntArray:
    """Entity positions arranged (12, per_stratum)."""
    order = np.argsort(stratum, kind="stable")
    per = len(stratum) // 12
    if not (np.bincount(stratum, minlength=12) == per).all():
        raise ValueError("unbalanced strata")
    out: IntArray = order.reshape(12, per)
    return out


def bootstrap_indices(seed: int, per_stratum: int, replicates: int) -> IntArray:
    rng = np.random.Generator(np.random.PCG64(seed))
    out: IntArray = rng.integers(0, per_stratum, size=(replicates, 12, per_stratum))
    return out


def bootstrap_means(values: FloatArray, strata: IntArray, indices: IntArray) -> FloatArray:
    """Per-replicate mean of per-entity ``values`` (n,) under stratified resampling."""
    arranged = values[strata]  # (12, per)
    rows = np.arange(12)[None, :, None]
    out: FloatArray = arranged[rows, indices].mean(axis=(1, 2))
    return out


def percentile_interval(samples: FloatArray) -> tuple[float, float]:
    low, high = np.percentile(samples, [2.5, 97.5], method="linear")
    return float(low), float(high)


def macro_per_entity(array: FloatArray) -> FloatArray:
    out: FloatArray = array.mean(axis=1)
    return out


# ------------------------------------------------------------------------------ run


def require_pinned_threads() -> None:
    ref.require_pinned_threads()


def _write(out: Path, name: str, data: bytes, files: dict[str, bytes]) -> None:
    (out / name).write_bytes(data)
    files[name] = data


def _json(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def run(profile: str, out_dir: Path) -> dict[str, Any]:  # noqa: C901
    if profile not in ("smoke", "full"):
        raise ValueError("profile must be 'smoke' or 'full'")
    require_pinned_threads()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to write into a non-empty directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    smoke = profile == "smoke"
    rows = C.SMOKE_ROLE_ROWS if smoke else C.ROLE_ROWS
    bases = C.SMOKE_ROLE_BASE if smoke else C.ROLE_BASE
    model_seed = C.SMOKE_MODEL_SEED if smoke else C.MODEL_SEED
    max_epochs = 2 if smoke else 20
    replicates = 50 if smoke else C.BOOTSTRAP_REPLICATES
    budget = Budget()
    files: dict[str, bytes] = {}
    phases: dict[str, float] = {}

    def timed(label: str, t0: float) -> None:
        phases[label] = round(time.process_time() - t0, 3)
        budget.check()

    # ---- stage 1: fit and freeze (no TEST data exists yet)
    t0 = time.process_time()
    roles = {
        r: D.build_cohorts(r, rows[r], bases[r])["CONTROL"]
        for r in ("FIT", "DEV", "CAL_C", "CAL_G")
    }
    timed("generate_fit_dev_cal", t0)
    fit, dev, cal_c, cal_g = (roles[r] for r in ("FIT", "DEV", "CAL_C", "CAL_G"))
    all_ids = [set(c.row_ids) for c in roles.values()]
    if sum(len(i) for i in all_ids) != len(set().union(*all_ids)):
        raise ValueError("fit/development/calibration cohorts share row ids")

    t0 = time.process_time()
    ridge, alpha_scores = M.fit_ridge(fit, dev)
    timed("fit_ridge", t0)

    t0 = time.process_time()
    stats = M.gru_stats(fit)
    train = M.train_gru(
        M.make_batch(fit, stats),
        M.target_z(fit, stats),
        M.make_batch(dev, stats),
        M.target_z(dev, stats),
        seed=model_seed,
        max_epochs=max_epochs,
        cpu_budget_seconds=MAX_GRU_CPU,
    )
    timed("train_gru", t0)
    partial = M.Frozen(ridge, alpha_scores, train.model, stats, {}, train)
    t0 = time.process_time()
    chains = {m: M.fit_chain(m, partial, dev, cal_c, cal_g) for m in C.MODELS}
    frozen = M.Frozen(ridge, alpha_scores, train.model, stats, chains, train)
    timed("calibration", t0)

    frozen_doc = {
        "study_id": C.STUDY_ID,
        "ridge": {
            "alpha": ridge.alpha,
            "dev_rmse_by_alpha": alpha_scores,
            "beta_sha256": ref.array_digest(ridge.beta),
        },
        "gru": {
            "state_sha256": M.state_digest(train.model),
            "best_epoch": train.best_epoch,
            "epochs_run": train.epochs_run,
            "stop_reason": train.stop_reason,
            "forward_backward_calls": train.forward_backward_calls,
            "history": [
                {k: round(v, 9) for k, v in h.items() if k != "cpu_seconds"} for h in train.history
            ],
            "seed": model_seed,
            "attempts": 1,
            "training_seed_stability": "NOT TESTED",
        },
        "calibration": {
            m: {
                "c": [round(float(v), 9) for v in chains[m].c],
                "g_min": round(float(chains[m].g.min()), 9),
                "g_max": round(float(chains[m].g.max()), 9),
                "g_clipped": int(
                    ((chains[m].g <= 0.7 + 1e-12) | (chains[m].g >= 1.4 - 1e-12)).sum()
                ),
                "raw_sha256": ref.array_digest(chains[m].raw),
                "g_sha256": ref.array_digest(chains[m].g),
            }
            for m in C.MODELS
        },
        "cohort_row_id_sha256": {r: _sha("\n".join(c.row_ids).encode()) for r, c in roles.items()},
    }
    _write(out_dir, "frozen-parameters.json", _json(frozen_doc), files)
    freeze_seal = _sha(files["frozen-parameters.json"])
    _write(
        out_dir,
        "freeze-seal.json",
        _json({"frozen_parameters_sha256": freeze_seal, "test_cohorts_generated": False}),
        files,
    )
    del roles, fit, dev, cal_c, cal_g

    # ---- stage 2: TEST inputs, predictions, seal (truth stays sealed)
    t0 = time.process_time()
    test: dict[str, dict[str, D.ObsCohort]] = {}
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]] = {}
    for parent in C.PARENTS:
        test[parent] = D.build_cohorts(parent, rows[parent], bases[parent], C.SCENARIOS)
        predictions[parent] = {s: M.predictive_arms(frozen, c) for s, c in test[parent].items()}
        budget.check()
    timed("generate_and_predict_test", t0)
    control = {p: test[p]["CONTROL"] for p in C.PARENTS}
    for p in C.PARENTS:  # paired design checks
        for s in C.SCENARIOS:
            if test[p][s].row_ids != control[p].row_ids or not np.array_equal(
                test[p][s].stratum, control[p].stratum
            ):
                raise ValueError("scenario cohorts are not entity-paired")
    if set(control["TEST_A"].row_ids) & set(control["TEST_B"].row_ids):
        raise ValueError("TEST parents share row ids")
    nonfinite = 0
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            for mu, sg in predictions[p][s].values():
                nonfinite += int((~np.isfinite(mu)).sum() + (~np.isfinite(sg)).sum())
    seal_arrays = [
        a for p in C.PARENTS for s in C.SCENARIOS for arm in C.ARMS for a in predictions[p][s][arm]
    ]
    prediction_seal = ref.array_digest(*seal_arrays)
    if any(test[p][s].truth.opened for p in C.PARENTS for s in C.SCENARIOS):
        raise RuntimeError("TEST truth opened before predictions were sealed")
    _write(
        out_dir,
        "prediction-seal.json",
        _json(
            {
                "prediction_seal_sha256": prediction_seal,
                "frozen_parameters_sha256": freeze_seal,
                "test_truth_opened": False,
            }
        ),
        files,
    )

    # ---- stage 3: open truth once and score
    try:
        result = _score_and_report(
            profile, out_dir, files, test, predictions, bases, replicates, nonfinite, frozen
        )
    except Exception as error:
        (out_dir / "FAILED-AFTER-TEST-TRUTH.json").write_bytes(
            _json(
                {
                    "error": repr(error),
                    "note": "TEST truth was opened; preserve and stop; never adjust and rescore",
                }
            )
        )
        raise
    manifest: dict[str, Any] = {
        "study_id": C.STUDY_ID,
        "protocol_digest": C.PROTOCOL_DIGEST,
        "identities": C.PROTOCOL["identities"],
        "profile": profile,
        "frozen_parameters_sha256": freeze_seal,
        "prediction_seal_sha256": prediction_seal,
        "cohorts": {
            f"{p}/{s}": {
                "rows": c.n,
                "row_id_sha256": _sha("\n".join(c.row_ids).encode()),
                "feature_sha256": ref.array_digest(c.base_features),
                "seeds": C.role_seeds(bases[p]),
            }
            for p, scenarios in test.items()
            for s, c in scenarios.items()
        },
        "disposition": result["disposition"],
        "output_sha256": {k: _sha(v) for k, v in sorted(files.items())},
        "nonclaims": C.PROTOCOL["nonclaims"],
    }
    _write(out_dir, "manifest.json", _json(manifest), files)
    receipt = {
        "study_id": C.STUDY_ID,
        "manifest_sha256": _sha(files["manifest.json"]),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "platform": f"{platform.system()} {platform.machine()}",
            "device": "cpu",
            "torch_threads": torch.get_num_threads(),
            "threads": {v: os.environ.get(v) for v in ref.THREAD_VARIABLES},
        },
        "resources": {
            "cpu_seconds": round(time.process_time() - budget.cpu0, 3),
            "wall_seconds": round(time.time() - budget.wall0, 3),
            "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024,
            "phase_cpu_seconds": phases,
            "gru_fit_cpu_seconds": round(train.cpu_seconds, 3),
            "gru_epochs": train.epochs_run,
            "gru_forward_backward_calls": train.forward_backward_calls,
            "ceilings": C.PROTOCOL["resources"],
        },
    }
    budget.check()
    (out_dir / "execution-receipt.json").write_bytes(_json(receipt))
    return {"manifest": manifest, "receipt": receipt, "summary": result}


def _score_and_report(
    profile: str,
    out_dir: Path,
    files: dict[str, bytes],
    test: dict[str, dict[str, D.ObsCohort]],
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]],
    bases: dict[str, int],
    replicates: int,
    nonfinite: int,
    frozen: M.Frozen,
) -> dict[str, Any]:
    truth = {p: {s: c.truth.open() for s, c in test[p].items()} for p in C.PARENTS}
    scores: dict[tuple[str, str, str], dict[str, FloatArray]] = {}
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            y = truth[p][s].y
            for arm, (mu, sg) in predictions[p][s].items():
                scores[(p, s, arm)] = score_arm(mu, sg, y)
    strata = {p: stratum_matrix(test[p]["CONTROL"].stratum) for p in C.PARENTS}
    boot = {
        p: bootstrap_indices(C.role_seeds(bases[p])["bootstrap"], strata[p].shape[1], replicates)
        for p in C.PARENTS
    }

    # scores.csv
    rows: list[list[str]] = [["parent", "scenario", "arm", "lift", "n", *METRICS]]
    for (p, s, arm), sc in scores.items():
        n = test[p][s].n
        for i, lift in enumerate((*C.LIFTS, "macro")):
            vals = [float(sc[m].mean() if i == 3 else sc[m][:, i].mean()) for m in METRICS]
            rows.append([p, s, arm, lift, str(n), *[_fmt(v) for v in vals]])
    _write(out_dir, "scores.csv", ref.csv_bytes(rows), files)

    # primary + descriptive contrasts
    contrasts = [
        ("M2_C", "M1_C"),
        ("M2_C", "M0_C"),
        ("M1_C", "M0_C"),
        ("M2_G", "M2_C"),
        ("M2_G", "M1_G"),
    ]
    crows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "contrast",
            "status",
            "diff_crps_kg",
            "ci_lo",
            "ci_hi",
            "rel_pct",
            "rel_ci_lo_pct",
            "rel_ci_hi_pct",
            "reference_crps_kg",
        ]
    ]
    primary: dict[str, dict[str, float | bool]] = {}
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            for a, b in contrasts:
                da, db = (
                    macro_per_entity(scores[(p, s, a)]["crps"]),
                    macro_per_entity(scores[(p, s, b)]["crps"]),
                )
                diff = float(da.mean() - db.mean())
                samples = bootstrap_means(da, strata[p], boot[p]) - bootstrap_means(
                    db, strata[p], boot[p]
                )
                ref_samples = bootstrap_means(db, strata[p], boot[p])
                lo, hi = percentile_interval(samples)
                rlo, rhi = percentile_interval(100.0 * samples / ref_samples)
                is_primary = (a, b) == ("M2_C", "M1_C") and s == "CONTROL"
                crows.append(
                    [
                        p,
                        s,
                        f"{a}-{b}",
                        "PRIMARY" if is_primary else "descriptive",
                        _fmt(diff),
                        _fmt(lo),
                        _fmt(hi),
                        _fmt(100 * diff / float(db.mean())),
                        _fmt(rlo),
                        _fmt(rhi),
                        _fmt(float(db.mean())),
                    ]
                )
                if is_primary:
                    rel = 100 * diff / float(db.mean())
                    primary[p] = {
                        "diff": diff,
                        "ci_lo": lo,
                        "ci_hi": hi,
                        "rel_pct": rel,
                        "screen": bool(rel <= -1.0 and hi < 0),
                    }
    _write(out_dir, "paired_contrasts.csv", ref.csv_bytes(crows), files)

    # shift degradation (absolute) and ranking
    srows: list[list[str]] = [
        [
            "parent",
            "arm",
            "scenario",
            "crps_kg",
            "d_crps_vs_control_kg",
            "d_crps_pct",
            "nll_nats",
            "d_nll",
            "cov90",
            "d_cov90",
            "rank_by_crps",
        ]
    ]
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            order = sorted(C.ARMS, key=lambda arm: float(scores[(p, s, arm)]["crps"].mean()))
            for arm in C.ARMS:
                now, base = scores[(p, s, arm)], scores[(p, "CONTROL", arm)]
                d = float(now["crps"].mean() - base["crps"].mean())
                srows.append(
                    [
                        p,
                        arm,
                        s,
                        _fmt(float(now["crps"].mean())),
                        _fmt(d),
                        _fmt(100 * d / float(base["crps"].mean())),
                        _fmt(float(now["nll"].mean())),
                        _fmt(float(now["nll"].mean() - base["nll"].mean())),
                        _fmt(float(now["cov90"].mean())),
                        _fmt(float(now["cov90"].mean() - base["cov90"].mean())),
                        str(order.index(arm) + 1),
                    ]
                )
    _write(out_dir, "shift_degradation.csv", ref.csv_bytes(srows), files)

    # group calibration and regressions
    grows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "arm",
            "plan_horizon",
            "lift",
            "n",
            "crps_kg",
            "nll_nats",
            "cov90",
            "width90_kg",
        ]
    ]
    summary_rows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "comparison",
            "groups",
            "crps_worse",
            "nll_worse",
            "cov90_outside_85_95",
            "cov90_min",
            "cov90_max",
        ]
    ]
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            stratum = test[p][s].stratum
            table: dict[str, dict[str, FloatArray]] = {}
            for arm in ("M1_C", "M2_C", "M2_G"):
                sc = scores[(p, s, arm)]
                per_group = {m: np.zeros((12, 3)) for m in ("crps", "nll", "cov90", "width90")}
                for g in range(12):
                    take = stratum == g
                    for m in per_group:
                        per_group[m][g] = sc[m][take].mean(axis=0)
                    for i, lift in enumerate(C.LIFTS):
                        grows.append(
                            [
                                p,
                                s,
                                arm,
                                ref.stratum_label(g),
                                lift,
                                str(int(take.sum())),
                                *[
                                    _fmt(float(per_group[m][g, i]))
                                    for m in ("crps", "nll", "cov90", "width90")
                                ],
                            ]
                        )
                table[arm] = per_group
            for a, b in (("M2_C", "M1_C"), ("M2_G", "M2_C"), ("M2_G", "M1_G")):
                if b == "M1_G":
                    continue
                cov = table[a]["cov90"]
                summary_rows.append(
                    [
                        p,
                        s,
                        f"{a} vs {b}",
                        "36",
                        str(int((table[a]["crps"] > table[b]["crps"]).sum())),
                        str(int((table[a]["nll"] > table[b]["nll"]).sum())),
                        str(int(((cov < 0.85) | (cov > 0.95)).sum())),
                        _fmt(float(cov.min())),
                        _fmt(float(cov.max())),
                    ]
                )
    _write(out_dir, "group_calibration.csv", ref.csv_bytes(grows), files)
    _write(out_dir, "group_summary.csv", ref.csv_bytes(summary_rows), files)

    # integrity and cessation audit
    irows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "rows_expected",
            "rows_scored",
            "nonfinite_predictions",
            "sigma_at_lower_bound",
            "sigma_at_upper_bound",
            "mean_negative_mass_M2_C",
        ]
    ]
    arows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "cessation_rows",
            "capacity_change_nonpositive_frac",
            "expressed_rises_frac",
            "assessment_above_last_frac",
            "mean_y_minus_last_kg",
        ]
    ]
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            c, t = test[p][s], truth[p][s]
            sig = np.concatenate([predictions[p][s][a][1].ravel() for a in C.ARMS])
            irows.append(
                [
                    p,
                    s,
                    str(len(c.row_ids)),
                    str(int(t.y.shape[0])),
                    "0" if nonfinite == 0 else "see-manifest",
                    str(int((sig <= 0.25 + 1e-12).sum())),
                    str(int((sig >= 100 - 1e-12).sum())),
                    _fmt(float(scores[(p, s, "M2_C")]["negative_mass"].mean())),
                ]
            )
            cess = c.plan == 0
            arows.append(
                [
                    p,
                    s,
                    str(int(cess.sum())),
                    _fmt(float(((t.c - t.last_c)[cess] <= 1e-12).mean())),
                    _fmt(float(((t.e - t.last_e)[cess] > 0).mean())),
                    _fmt(float((t.y[cess] > c.last_assessment[cess]).mean())),
                    _fmt(float((t.y[cess] - c.last_assessment[cess]).mean())),
                ]
            )
    _write(out_dir, "integrity.csv", ref.csv_bytes(irows), files)
    _write(out_dir, "cessation_audit.csv", ref.csv_bytes(arows), files)

    # disposition
    macro_crps = {
        (p, s, a): float(scores[(p, s, a)]["crps"].mean())
        for p in C.PARENTS
        for s in C.SCENARIOS
        for a in C.ARMS
    }
    cov90_m2 = {p: float(scores[(p, "CONTROL", "M2_C")]["cov90"].mean()) for p in C.PARENTS}
    both_screens = all(bool(primary[p]["screen"]) for p in C.PARENTS)
    beats_m0 = all(
        macro_crps[(p, "CONTROL", "M2_C")] < macro_crps[(p, "CONTROL", "M0_C")] for p in C.PARENTS
    )
    beats_m1 = all(
        macro_crps[(p, "CONTROL", "M2_C")] < macro_crps[(p, "CONTROL", "M1_C")] for p in C.PARENTS
    )
    coverage_ok = all(0.85 <= v <= 0.95 for v in cov90_m2.values())
    if both_screens and beats_m0 and coverage_ok and nonfinite == 0:
        disposition = "OBSERVABLE_FORECASTING_QUALIFIED_WITHIN_SYNTHETIC_WORLD"
    elif not beats_m1 or not beats_m0:
        disposition = "OBSERVABLE_FORECASTING_NOT_QUALIFIED"
    else:
        disposition = "OBSERVABLE_FORECASTING_MIXED_OR_INCONCLUSIVE"
    summary = {
        "disposition": disposition,
        "primary": primary,
        "criteria": {
            "both_parent_screens": both_screens,
            "m2_below_m0_on_both_controls": beats_m0,
            "m2_below_m1_on_both_controls": beats_m1,
            "m2_c_cov90_control": cov90_m2,
            "coverage_in_85_95": coverage_ok,
            "nonfinite_predictions": nonfinite,
        },
        "profile": profile,
    }
    _write(out_dir, "summary.json", _json(summary), files)
    for name, data in figures(scores, primary, test).items():
        _write(out_dir, name, data, files)
    return summary


# ------------------------------------------------------------------------------ figures


def figures(
    scores: dict[tuple[str, str, str], dict[str, FloatArray]],
    primary: dict[str, dict[str, float | bool]],
    test: dict[str, dict[str, D.ObsCohort]],
) -> dict[str, bytes]:
    colors = ["a", "a", "a", "b", "b"]  # orange = temporal model arms
    f2 = ""
    f3 = ""
    k = 0
    for p in C.PARENTS:
        for s in C.SCENARIOS:
            x0 = 40 + (k % 3) * 250
            y0 = 60 + (k // 3) * 250
            vals = [float(scores[(p, s, a)]["crps"].mean()) for a in C.ARMS]
            f2 += ref._panel(
                x0,
                y0,
                220,
                150,
                f"{p[-1]} {s.split('_')[0].title()} CRPS (kg)",
                C.ARMS,
                vals,
                colors,
                max(vals) * 1.15,
                "",
            )
            cov = [float(scores[(p, s, a)]["cov90"].mean()) for a in C.ARMS]
            f3 += ref._panel(
                x0,
                y0,
                220,
                150,
                f"{p[-1]} {s.split('_')[0].title()} 90% coverage",
                C.ARMS,
                cov,
                colors,
                1.0,
                "",
                reference=0.9,
            )
            k += 1
    fig2 = ref._svg(800, 520, f2, "Macro CRPS by arm for both TEST parents and three scenarios")
    fig3 = ref._svg(800, 520, f3, "Central 90 percent coverage by arm and scenario")
    # primary paired difference with bootstrap interval
    lo = min(float(primary[p]["ci_lo"]) for p in C.PARENTS)
    hi = max(float(primary[p]["ci_hi"]) for p in C.PARENTS)
    span = max(abs(lo), abs(hi), 1e-6) * 1.3
    body = [
        '<text x="40" y="30">Primary: M2_C minus M1_C macro CRPS (kg), control; '
        "negative favors the GRU</text>"
    ]
    zero_x = 400.0
    scale = 320.0 / span
    body.append(f'<line x1="{zero_x}" y1="50" x2="{zero_x}" y2="170" stroke="var(--g)"/>')
    for i, p in enumerate(C.PARENTS):
        yv = 90 + 50 * i
        d, a, b = float(primary[p]["diff"]), float(primary[p]["ci_lo"]), float(primary[p]["ci_hi"])
        body.append(
            f'<line x1="{zero_x + a * scale:.1f}" y1="{yv}" '
            f'x2="{zero_x + b * scale:.1f}" y2="{yv}" '
            'stroke="var(--b)" stroke-width="2"/>'
        )
        body.append(f'<circle cx="{zero_x + d * scale:.1f}" cy="{yv}" r="5" fill="var(--b)"/>')
        body.append(
            f'<text class="m" x="40" y="{yv + 4}">{p}: {d:+.4f} [{a:+.4f}, {b:+.4f}] '
            f"({float(primary[p]['rel_pct']):+.2f}%)</text>"
        )
    body.append(
        '<text class="m" x="400" y="190" text-anchor="middle">'
        "0 = no difference; 1% screen not drawn</text>"
    )
    fig1 = ref._svg(
        800, 210, "".join(body), "Primary paired CRPS difference with bootstrap intervals"
    )
    del test
    return {
        "figure-1-primary-difference.svg": fig1,
        "figure-2-crps-by-scenario.svg": fig2,
        "figure-3-coverage-by-scenario.svg": fig3,
    }


CROSS_ENVIRONMENT_TOLERANCE = {
    "crps": 0.05,
    "nll": 0.05,
    "abs_error": 0.05,
    "cov80": 0.05,
    "cov90": 0.05,
    "width80": 0.5,
    "width90": 0.5,
    "negative_mass": 1e-3,
}


def compare_to_expected(
    out_dir: Path, expected_dir: Path, *, same_environment: bool
) -> dict[str, float]:
    """Compare a fresh run with committed expected outputs; the expected files are never edited."""
    import csv

    mine = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    theirs = json.loads((expected_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in mine["output_sha256"].items():
        if _sha((out_dir / name).read_bytes()) != digest:
            raise ValueError(f"output file does not match its manifest hash: {name}")
    for key in ("study_id", "protocol_digest", "identities", "profile"):
        if mine[key] != theirs[key]:
            raise ValueError(f"manifest identity differs: {key}")
    for key, item in mine["cohorts"].items():
        for field in ("rows", "row_id_sha256", "feature_sha256", "seeds"):
            if item[field] != theirs["cohorts"][key][field]:
                raise ValueError(f"cohort {key} differs: {field}")
    if same_environment and (
        mine["output_sha256"] != theirs["output_sha256"]
        or mine["prediction_seal_sha256"] != theirs["prediction_seal_sha256"]
        or mine["frozen_parameters_sha256"] != theirs["frozen_parameters_sha256"]
    ):
        raise ValueError("same-environment run is not byte-identical")
    worst = {metric: 0.0 for metric in CROSS_ENVIRONMENT_TOLERANCE}
    with (
        (out_dir / "scores.csv").open(newline="") as a,
        (expected_dir / "scores.csv").open(newline="") as b,
    ):
        for r1, r2 in zip(csv.DictReader(a), csv.DictReader(b), strict=True):
            if [r1[k] for k in ("parent", "scenario", "arm", "lift")] != [
                r2[k] for k in ("parent", "scenario", "arm", "lift")
            ]:
                raise ValueError("score rows are not aligned")
            for metric in worst:
                worst[metric] = max(worst[metric], abs(float(r1[metric]) - float(r2[metric])))
    for metric, value in worst.items():
        if value > CROSS_ENVIRONMENT_TOLERANCE[metric]:
            raise ValueError(f"{metric} differs from expected by {value}")
    return worst


# ------------------------------------------------------------------------------ CLI


def _stop(signum: int, frame: Any) -> NoReturn:
    raise CeilingReached("CPU time limit signal received")


def main(argv: Sequence[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    if any(os.environ.get(v) != "1" for v in ref.THREAD_VARIABLES):
        env = {**os.environ, **{v: "1" for v in ref.THREAD_VARIABLES}}
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "powerlifting_state_research.observable", *args_in],
            env,
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--out", type=Path, required=True, help="new empty output directory")
    parser.add_argument("--expected", type=Path, help="compare with committed expected outputs")
    parser.add_argument(
        "--cross-environment",
        action="store_true",
        help="use cross-environment tolerances instead of byte identity",
    )
    args = parser.parse_args(args_in)
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU, MAX_CPU + 60))
    signal.signal(signal.SIGXCPU, _stop)
    try:
        result = run(args.profile, args.out)
    except CeilingReached as error:
        print(json.dumps({"status": "BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE", "reason": str(error)}))
        return 3
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "disposition": result["summary"]["disposition"],
                "resources": result["receipt"]["resources"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
