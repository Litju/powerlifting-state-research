"""RES-639 executable study: verify Ridge, fit scale, freeze, seal, open once, score, report.

The full profile is refused unless an owner authorization record names the frozen protocol digest.
The smoke profile uses non-scientific seeds and tiny cohorts to verify the machinery only.
"""

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
from ..observable import data as observable_data
from ..observable import study as observable_study
from ..probabilistic import reference as ref
from ..probabilistic import scoring
from . import contract as K
from . import heads as H
from . import replay as R

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ROOT = Path(__file__).resolve().parents[3]
EXPECTED_RELATIVE = "results/studies/history_conditional_uncertainty"
MAX_RSS = int(K.RESOURCES["max_process_ram_bytes"])
MAX_CPU = int(K.RESOURCES["max_campaign_cpu_seconds"])
MAX_WALL = int(K.RESOURCES["max_wall_seconds"])
METRICS = (
    "crps",
    "nll",
    "abs_error",
    "cov50",
    "cov80",
    "cov90",
    "width50",
    "width80",
    "width90",
    "negative_mass",
)
SOURCE_FILES = tuple(
    f"src/powerlifting_state_research/history_uncertainty/{n}.py"
    for n in ("contract", "heads", "replay", "study")
)


class CeilingReached(RuntimeError):
    """A frozen resource ceiling was reached; the run stops without extension."""


class NotAuthorized(RuntimeError):
    """The full profile was requested without a valid owner authorization record."""


class SealViolation(RuntimeError):
    """TEST truth was requested without matching sealed predictions."""


def _fmt(value: float) -> str:
    return f"{value:.9f}"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _write(out: Path, name: str, data: bytes, files: dict[str, bytes]) -> None:
    (out / name).write_bytes(data)
    files[name] = data


class Budget:
    def __init__(self) -> None:
        self.cpu0 = time.process_time()
        self.wall0 = time.time()

    def check(self) -> None:
        if int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024 > MAX_RSS:
            raise CeilingReached("peak resident memory exceeded 2 GiB")
        if time.process_time() - self.cpu0 > MAX_CPU:
            raise CeilingReached(f"charged CPU time exceeded {MAX_CPU} s")
        if time.time() - self.wall0 > MAX_WALL:
            raise CeilingReached(f"wall time exceeded {MAX_WALL} s")


def check_authorization(path: Path | None) -> str:
    """Return the SHA-256 of a valid authorization record, or raise ``NotAuthorized``."""
    if path is None or not path.is_file():
        raise NotAuthorized("the full profile needs --authorization-record from the owner")
    data = path.read_bytes()
    try:
        record = json.loads(data)
    except json.JSONDecodeError as error:
        raise NotAuthorized("authorization record is not valid JSON") from error
    if (
        not isinstance(record, dict)
        or record.get("protocol_digest") != K.PROTOCOL_DIGEST
        or record.get("owner_authorized_full_run") is not True
    ):
        raise NotAuthorized(
            "authorization record must set owner_authorized_full_run=true and name protocol_digest "
            f"{K.PROTOCOL_DIGEST}"
        )
    return _sha(data)


# ------------------------------------------------------------------ scoring


def score_arm(mu: FloatArray, sigma: FloatArray, y: FloatArray) -> dict[str, FloatArray]:
    """Per-row, per-lift scores of Normal(mu, sigma^2); no truncation anywhere."""
    out: dict[str, FloatArray] = {
        "crps": scoring.gaussian_crps(mu, sigma, y),
        "nll": scoring.gaussian_nll(mu, sigma, y),
        "abs_error": np.abs(mu - y),
        "negative_mass": scoring.positive_mass(-mu, sigma),
    }
    cover = scoring.central_coverage_and_width(
        mu, sigma, y, np.zeros(mu.shape, dtype=bool), K.INTERVAL_LEVELS
    )
    for level in K.INTERVAL_LEVELS:
        out[f"cov{int(round(100 * level))}"] = cover[level][0]
        out[f"width{int(round(100 * level))}"] = cover[level][1]
    return out


def pit_values(mu: FloatArray, sigma: FloatArray, y: FloatArray) -> FloatArray:
    return scoring.gaussian_cdf(mu, sigma, y)


def pit_counts(values: FloatArray) -> IntArray:
    edges = np.linspace(0.0, 1.0, K.PIT_BINS + 1)
    counts, _ = np.histogram(values.ravel(), bins=edges)
    return np.asarray(counts, dtype=np.int64)


def scale_bins(sigma_lift: FloatArray) -> list[IntArray]:
    """Equal-count quintiles of one lift's predicted scale (stable order)."""
    order = np.argsort(sigma_lift, kind="stable")
    return [np.asarray(c, dtype=np.int64) for c in np.array_split(order, K.CONDITIONAL_BINS)]


# ------------------------------------------------------------------ sealed truth


def prediction_digest(
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]],
) -> str:
    arrays = [
        a for p in K.PARENTS for s in K.SCENARIOS for m in K.MODELS for a in predictions[p][s][m]
    ]
    return ref.array_digest(*arrays)


def open_sealed_truth(
    cohort: observable_data.ObsCohort,
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]],
    seal_sha256: str,
) -> observable_data.ObsTruth:
    """Open TEST truth only if the in-memory predictions still hash to the recorded seal."""
    if prediction_digest(predictions) != seal_sha256:
        raise SealViolation("predictions no longer match the recorded prediction seal")
    return cohort.truth.open()


def check_identity(
    cohort: observable_data.ObsCohort,
    predictions: dict[str, tuple[FloatArray, FloatArray]],
    y: FloatArray,
) -> None:
    """Predictions, cohort identities and truth must be aligned and finite."""
    if y.shape != (cohort.n, 3):
        raise ValueError(f"{cohort.role}/{cohort.scenario}: truth is not aligned with the cohort")
    for name, (mu, sigma) in predictions.items():
        if mu.shape != (cohort.n, 3) or sigma.shape != (cohort.n, 3):
            raise ValueError(f"{name}: prediction shape is not aligned with {cohort.role}")
        if not (np.isfinite(mu).all() and np.isfinite(sigma).all() and (sigma > 0).all()):
            raise ValueError(f"{name}: nonfinite location or invalid scale")


# ------------------------------------------------------------------ run


def require_pinned_threads() -> None:
    ref.require_pinned_threads()


def _source_digests() -> dict[str, str]:
    return {p: _sha((ROOT / p).read_bytes()) for p in SOURCE_FILES}


def run(  # noqa: C901
    profile: str,
    out_dir: Path,
    *,
    authorization: Path | None = None,
    cross_environment_ridge: bool = False,
) -> dict[str, Any]:
    if profile not in ("smoke", "full"):
        raise ValueError("profile must be 'smoke' or 'full'")
    authorization_sha = check_authorization(authorization) if profile == "full" else None
    require_pinned_threads()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to write into a non-empty directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    smoke = profile == "smoke"
    rows = K.SMOKE_ROLE_ROWS if smoke else K.ROLE_ROWS
    bases = K.SMOKE_ROLE_BASE if smoke else K.ROLE_BASE
    replicates = K.SMOKE_BOOTSTRAP_REPLICATES if smoke else K.BOOTSTRAP_REPLICATES
    budget = Budget()
    files: dict[str, bytes] = {}
    phases: dict[str, float] = {}

    def timed(label: str, t0: float) -> None:
        phases[label] = round(time.process_time() - t0, 3)
        budget.check()

    # ---- stage 1: verify and freeze the Ridge location model (no TEST data exists)
    t0 = time.process_time()
    replay = R.replay_ridge(profile)
    ridge_check = R.verify_replay(
        replay, R.reference_for(profile, ROOT), cross_environment=cross_environment_ridge
    )
    timed("ridge_replay", t0)

    # ---- stage 2: scale populations, fit on SCALE_FIT, calibrate on SCALE_CAL
    t0 = time.process_time()
    scale_fit = observable_data.build_cohorts("SCALE_FIT", rows["SCALE_FIT"], bases["SCALE_FIT"])[
        "CONTROL"
    ]
    scale_cal = observable_data.build_cohorts("SCALE_CAL", rows["SCALE_CAL"], bases["SCALE_CAL"])[
        "CONTROL"
    ]
    timed("generate_scale_populations", t0)
    t0 = time.process_time()
    frozen = H.fit_scale_models(replay.ridge, scale_fit, scale_cal)
    timed("fit_and_calibrate_scale", t0)

    frozen_doc = {
        "study_id": K.STUDY_ID,
        "protocol_digest": K.PROTOCOL_DIGEST,
        "profile": profile,
        "ridge_replay": ridge_check,
        "models": {
            name: {
                "c": [round(float(v), 9) for v in m.c],
                "c_clipped": m.c_clipped,
                "beta_sha256": (
                    ref.array_digest(m.head.beta, m.head.intercept) if m.head else None
                ),
                "group_sha256": ref.array_digest(m.group) if m.group is not None else None,
            }
            for name, m in frozen.models.items()
        },
        "cohort_row_id_sha256": {
            "SCALE_FIT": _sha("\n".join(scale_fit.row_ids).encode()),
            "SCALE_CAL": _sha("\n".join(scale_cal.row_ids).encode()),
            **{f"RES616_{k}": v for k, v in replay.row_id_sha256.items()},
        },
        "source_sha256": _source_digests(),
        "replay_source_sha256": K.source_digests(ROOT),
    }
    _write(out_dir, "frozen-parameters.json", _json(frozen_doc), files)
    freeze_seal = _sha(files["frozen-parameters.json"])
    _write(
        out_dir,
        "freeze-seal.json",
        _json({"frozen_parameters_sha256": freeze_seal, "test_cohorts_generated": False}),
        files,
    )
    del scale_fit, scale_cal

    # ---- stage 3: TEST inputs, sealed predictions (truth stays sealed)
    t0 = time.process_time()
    test: dict[str, dict[str, observable_data.ObsCohort]] = {}
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]] = {}
    for parent in K.PARENTS:
        test[parent] = observable_data.build_cohorts(
            parent, rows[parent], bases[parent], K.SCENARIOS
        )
        predictions[parent] = {s: H.predict_arms(frozen, c) for s, c in test[parent].items()}
        budget.check()
    timed("generate_and_predict_test", t0)
    control = {p: test[p]["CONTROL"] for p in K.PARENTS}
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            if test[p][s].row_ids != control[p].row_ids or not np.array_equal(
                test[p][s].stratum, control[p].stratum
            ):
                raise ValueError("scenario cohorts are not entity-paired")
    if set(control["TEST_A"].row_ids) & set(control["TEST_B"].row_ids):
        raise ValueError("TEST parents share row ids")
    nonfinite = 0
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            for mu, sg in predictions[p][s].values():
                nonfinite += int((~np.isfinite(mu)).sum() + (~np.isfinite(sg)).sum())
    if nonfinite:
        raise ValueError(f"{nonfinite} nonfinite predictions before scoring")
    seal = prediction_digest(predictions)
    if any(test[p][s].truth.opened for p in K.PARENTS for s in K.SCENARIOS):
        raise RuntimeError("TEST truth opened before predictions were sealed")
    _write(
        out_dir,
        "prediction-seal.json",
        _json(
            {
                "prediction_seal_sha256": seal,
                "frozen_parameters_sha256": freeze_seal,
                "test_truth_opened": False,
            }
        ),
        files,
    )

    # ---- stage 4: open truth once, score, decide
    try:
        result = _score_and_report(
            profile, out_dir, files, test, predictions, bases, replicates, seal
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
        "study_id": K.STUDY_ID,
        "protocol_digest": K.PROTOCOL_DIGEST,
        "identities": K.PROTOCOL["identities"],
        "profile": profile,
        "authorization_record_sha256": authorization_sha,
        "frozen_parameters_sha256": freeze_seal,
        "prediction_seal_sha256": seal,
        "cohorts": {
            f"{p}/{s}": {
                "rows": c.n,
                "row_id_sha256": _sha("\n".join(c.row_ids).encode()),
                "feature_sha256": ref.array_digest(c.base_features),
                "seeds": K.role_seeds(bases[p]),
            }
            for p, scenarios in test.items()
            for s, c in scenarios.items()
        },
        "disposition": result["disposition"],
        "output_sha256": {k: _sha(v) for k, v in sorted(files.items())},
        "nonclaims": K.PROTOCOL["nonclaims"],
    }
    _write(out_dir, "manifest.json", _json(manifest), files)
    receipt = {
        "study_id": K.STUDY_ID,
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
            "ceilings": K.RESOURCES,
        },
    }
    budget.check()
    (out_dir / "execution-receipt.json").write_bytes(_json(receipt))
    return {"manifest": manifest, "receipt": receipt, "summary": result}


def _score_and_report(  # noqa: C901
    profile: str,
    out_dir: Path,
    files: dict[str, bytes],
    test: dict[str, dict[str, observable_data.ObsCohort]],
    predictions: dict[str, dict[str, dict[str, tuple[FloatArray, FloatArray]]]],
    bases: dict[str, int],
    replicates: int,
    seal: str,
) -> dict[str, Any]:
    truth = {
        p: {s: open_sealed_truth(c, predictions, seal) for s, c in test[p].items()}
        for p in K.PARENTS
    }
    scores: dict[tuple[str, str, str], dict[str, FloatArray]] = {}
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            check_identity(test[p][s], predictions[p][s], truth[p][s].y)
            for m, (mu, sg) in predictions[p][s].items():
                scores[(p, s, m)] = score_arm(mu, sg, truth[p][s].y)
    strata = {p: observable_study.stratum_matrix(test[p]["CONTROL"].stratum) for p in K.PARENTS}
    boot = {
        p: observable_study.bootstrap_indices(
            K.role_seeds(bases[p])["bootstrap"], strata[p].shape[1], replicates
        )
        for p in K.PARENTS
    }

    # scores.csv: every model, parent, scenario and lift (plus macro)
    srows: list[list[str]] = [["parent", "scenario", "model", "lift", "n", *METRICS]]
    for (p, s, m), sc in scores.items():
        n = test[p][s].n
        for i, lift in enumerate((*K.LIFTS, "macro")):
            vals = [float(sc[k].mean() if i == 3 else sc[k][:, i].mean()) for k in METRICS]
            srows.append([p, s, m, lift, str(n), *[_fmt(v) for v in vals]])
    _write(out_dir, "scores.csv", ref.csv_bytes(srows), files)

    # paired contrasts with entity-cluster bootstrap
    contrasts = (
        ("H_HISTORY", "B_MAG"),
        ("H_HISTORY", "B_GROUP"),
        ("B_MAG", "B_GROUP"),
    )
    crows: list[list[str]] = [
        [
            "parent",
            "scenario",
            "contrast",
            "status",
            "metric",
            "diff",
            "ci_lo",
            "ci_hi",
            "rel_pct",
            "rel_ci_lo_pct",
            "rel_ci_hi_pct",
            "reference_value",
        ]
    ]
    primary: dict[str, dict[str, float | bool]] = {}
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            for a, b in contrasts:
                for metric in ("crps", "nll"):
                    da = observable_study.macro_per_entity(scores[(p, s, a)][metric])
                    db = observable_study.macro_per_entity(scores[(p, s, b)][metric])
                    diff = float(da.mean() - db.mean())
                    ba = observable_study.bootstrap_means(da, strata[p], boot[p])
                    bb = observable_study.bootstrap_means(db, strata[p], boot[p])
                    lo, hi = observable_study.percentile_interval(ba - bb)
                    rlo, rhi = observable_study.percentile_interval(100.0 * (ba - bb) / bb)
                    is_primary = (a, b, metric, s) == ("H_HISTORY", "B_MAG", "crps", "CONTROL")
                    rel = 100.0 * diff / float(db.mean())
                    crows.append(
                        [
                            p,
                            s,
                            f"{a}-{b}",
                            "PRIMARY" if is_primary else "descriptive",
                            metric,
                            _fmt(diff),
                            _fmt(lo),
                            _fmt(hi),
                            _fmt(rel),
                            _fmt(rlo),
                            _fmt(rhi),
                            _fmt(float(db.mean())),
                        ]
                    )
                    if is_primary:
                        primary[p] = {
                            "diff": diff,
                            "ci_lo": lo,
                            "ci_hi": hi,
                            "rel_pct": rel,
                            "screen": bool(
                                rel <= -K.GUARDRAILS["primary_relative_improvement_pct"]
                                and hi < K.GUARDRAILS["primary_ci_upper_bound"]
                            ),
                            "ci_excludes_zero": bool(hi < 0 or lo > 0),
                        }
    _write(out_dir, "paired_contrasts.csv", ref.csv_bytes(crows), files)

    # shift degradation and ranking stability
    drows: list[list[str]] = [
        [
            "parent",
            "model",
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
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            order = sorted(K.MODELS, key=lambda m: float(scores[(p, s, m)]["crps"].mean()))
            for m in K.MODELS:
                now, ctl = scores[(p, s, m)], scores[(p, "CONTROL", m)]
                d = float(now["crps"].mean() - ctl["crps"].mean())
                drows.append(
                    [
                        p,
                        m,
                        s,
                        _fmt(float(now["crps"].mean())),
                        _fmt(d),
                        _fmt(100 * d / float(ctl["crps"].mean())),
                        _fmt(float(now["nll"].mean())),
                        _fmt(float(now["nll"].mean() - ctl["nll"].mean())),
                        _fmt(float(now["cov90"].mean())),
                        _fmt(float(now["cov90"].mean() - ctl["cov90"].mean())),
                        str(order.index(m) + 1),
                    ]
                )
    _write(out_dir, "shift_degradation.csv", ref.csv_bytes(drows), files)

    # subgroup calibration, scale variation, scale-conditional coverage, PIT
    grows: list[list[str]] = [
        ["parent", "scenario", "model", "plan_horizon", "lift", "n"]
        + ["crps_kg", "nll_nats", "cov90", "width90_kg"]
    ]
    vrows: list[list[str]] = [
        ["parent", "scenario", "model", "plan_horizon", "lift", "sd_log_sigma", "min", "max"]
    ]
    brows: list[list[str]] = [
        ["parent", "scenario", "model", "lift", "scale_quintile", "n", "mean_sigma_kg"]
        + ["cov50", "cov80", "cov90"]
    ]
    prows: list[list[str]] = [["parent", "scenario", "model", "pit_bin", "count", "fraction"]]
    cell_cov: dict[tuple[str, str, str], FloatArray] = {}
    bin_cov: dict[tuple[str, str, str], list[float]] = {}
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            stratum = test[p][s].stratum
            y = truth[p][s].y
            for m in K.MODELS:
                mu, sg = predictions[p][s][m]
                sc = scores[(p, s, m)]
                cells = np.zeros((K.STRATA, 3))
                for g in range(K.STRATA):
                    take = stratum == g
                    for i, lift in enumerate(K.LIFTS):
                        cells[g, i] = float(sc["cov90"][take, i].mean())
                        log_s = np.log(sg[take, i])
                        grows.append(
                            [p, s, m, ref.stratum_label(g), lift, str(int(take.sum()))]
                            + [_fmt(float(sc[k][take, i].mean())) for k in ("crps", "nll")]
                            + [_fmt(cells[g, i]), _fmt(float(sc["width90"][take, i].mean()))]
                        )
                        vrows.append(
                            [p, s, m, ref.stratum_label(g), lift]
                            + [_fmt(float(log_s.std())), _fmt(float(sg[take, i].min()))]
                            + [_fmt(float(sg[take, i].max()))]
                        )
                cell_cov[(p, s, m)] = cells
                conditional: list[float] = []
                for i, lift in enumerate(K.LIFTS):
                    for q, idx in enumerate(scale_bins(sg[:, i])):
                        c90 = float(sc["cov90"][idx, i].mean())
                        conditional.append(c90)
                        brows.append(
                            [p, s, m, lift, str(q + 1), str(len(idx))]
                            + [_fmt(float(sg[idx, i].mean()))]
                            + [_fmt(float(sc[k][idx, i].mean())) for k in ("cov50", "cov80")]
                            + [_fmt(c90)]
                        )
                bin_cov[(p, s, m)] = conditional
                counts = pit_counts(pit_values(mu, sg, y))
                for bin_index, count in enumerate(counts):
                    prows.append(
                        [p, s, m, str(bin_index + 1), str(int(count)), _fmt(count / counts.sum())]
                    )
    _write(out_dir, "group_calibration.csv", ref.csv_bytes(grows), files)
    _write(out_dir, "scale_variation.csv", ref.csv_bytes(vrows), files)
    _write(out_dir, "conditional_coverage.csv", ref.csv_bytes(brows), files)
    _write(out_dir, "pit.csv", ref.csv_bytes(prows), files)

    # integrity and denominators
    low, high = K.GUARDRAILS["severe_subgroup_coverage90_band"]
    irows: list[list[str]] = [
        ["parent", "scenario", "rows_expected", "rows_scored", "nonfinite_predictions"]
        + ["sigma_at_lower_bound", "sigma_at_upper_bound", "severe_cells_H_HISTORY"]
        + ["mean_negative_mass_H_HISTORY"]
    ]
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            sig = np.concatenate([predictions[p][s][m][1].ravel() for m in K.MODELS])
            cells = cell_cov[(p, s, "H_HISTORY")]
            irows.append(
                [p, s, str(test[p][s].n), str(int(truth[p][s].y.shape[0])), "0"]
                + [str(int((sig <= K.SIGMA_MIN_KG + 1e-12).sum()))]
                + [str(int((sig >= K.SIGMA_MAX_KG - 1e-12).sum()))]
                + [str(int(((cells < low) | (cells > high)).sum()))]
                + [_fmt(float(scores[(p, s, "H_HISTORY")]["negative_mass"].mean()))]
            )
    _write(out_dir, "integrity.csv", ref.csv_bytes(irows), files)

    # disposition
    evidence: dict[str, Any] = {"blocked": None, "nonfinite": 0}
    for p in K.PARENTS:
        mean = {
            m: {k: float(scores[(p, "CONTROL", m)][k].mean()) for k in ("crps", "nll", "width90")}
            for m in K.MODELS
        }
        evidence[p] = {
            "primary_rel_pct": float(primary[p]["rel_pct"]),
            "primary_ci_hi": float(primary[p]["ci_hi"]),
            "crps": {m: mean[m]["crps"] for m in K.MODELS},
            "nll": {m: mean[m]["nll"] for m in K.MODELS},
            "cov90": float(scores[(p, "CONTROL", "H_HISTORY")]["cov90"].mean()),
            "cov90_by_lift": [
                float(scores[(p, "CONTROL", "H_HISTORY")]["cov90"][:, i].mean()) for i in range(3)
            ],
            "severe_cells": int(
                (
                    (cell_cov[(p, "CONTROL", "H_HISTORY")] < low)
                    | (cell_cov[(p, "CONTROL", "H_HISTORY")] > high)
                ).sum()
            ),
            "conditional_cov90": bin_cov[(p, "CONTROL", "H_HISTORY")],
            "width90": {m: mean[m]["width90"] for m in K.MODELS},
            "shift": {
                s: {
                    "crps": {m: float(scores[(p, s, m)]["crps"].mean()) for m in K.MODELS},
                    "cov90": float(scores[(p, s, "H_HISTORY")]["cov90"].mean()),
                }
                for s in K.SCENARIOS
                if s != "CONTROL"
            },
        }
    decision = K.decide(evidence)
    summary = {
        "disposition": decision["disposition"],
        "criteria": decision["criteria"],
        "primary": primary,
        "profile": profile,
        "statistical_vs_practical": {
            p: (
                "distinguishable_and_meets_screen"
                if primary[p]["screen"]
                else "distinguishable_below_screen"
                if primary[p]["ci_excludes_zero"]
                else "not_distinguishable"
            )
            for p in K.PARENTS
        },
    }
    _write(out_dir, "summary.json", _json(summary), files)
    for name, data in figures(scores, primary).items():
        _write(out_dir, name, data, files)
    return summary


def figures(
    scores: dict[tuple[str, str, str], dict[str, FloatArray]],
    primary: dict[str, dict[str, float | bool]],
) -> dict[str, bytes]:
    colors = ["a", "a", "b"]
    f2 = ""
    k = 0
    for p in K.PARENTS:
        for s in K.SCENARIOS:
            x0, y0 = 40 + (k % 3) * 250, 60 + (k // 3) * 250
            vals = [float(scores[(p, s, m)]["crps"].mean()) for m in K.MODELS]
            f2 += ref._panel(
                x0,
                y0,
                220,
                150,
                f"{p[-1]} {s.split('_')[0].title()} CRPS (kg)",
                K.MODELS,
                vals,
                colors,
                max(vals) * 1.15,
                "",
            )
            k += 1
    fig2 = ref._svg(800, 520, f2, "Macro CRPS by uncertainty model, parent and scenario")
    lo = min(float(primary[p]["ci_lo"]) for p in K.PARENTS)
    hi = max(float(primary[p]["ci_hi"]) for p in K.PARENTS)
    span = max(abs(lo), abs(hi), 1e-6) * 1.3
    body = [
        '<text x="40" y="30">Primary: H_HISTORY minus B_MAG macro CRPS (kg), control; '
        "negative favors history</text>"
    ]
    zero_x, scale = 400.0, 320.0 / span
    body.append(f'<line x1="{zero_x}" y1="50" x2="{zero_x}" y2="170" stroke="var(--g)"/>')
    for i, p in enumerate(K.PARENTS):
        yv = 90 + 50 * i
        d, a, b = float(primary[p]["diff"]), float(primary[p]["ci_lo"]), float(primary[p]["ci_hi"])
        body.append(
            f'<line x1="{zero_x + a * scale:.1f}" y1="{yv}" x2="{zero_x + b * scale:.1f}" '
            f'y2="{yv}" stroke="var(--b)" stroke-width="2"/>'
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
    fig1 = ref._svg(800, 210, "".join(body), "Primary paired CRPS difference with intervals")
    return {"figure-1-primary-difference.svg": fig1, "figure-2-crps-by-scenario.svg": fig2}


# ------------------------------------------------------------------ comparison and CLI

CROSS_ENVIRONMENT_TOLERANCE = {
    "crps": 0.05,
    "nll": 0.05,
    "abs_error": 0.05,
    "cov50": 0.05,
    "cov80": 0.05,
    "cov90": 0.05,
    "width50": 0.5,
    "width80": 0.5,
    "width90": 0.5,
    "negative_mass": 1e-3,
}


def compare_to_expected(
    out_dir: Path, expected_dir: Path, *, same_environment: bool
) -> dict[str, float]:
    """Compare a fresh run with committed expected outputs; expected files are never edited."""
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
            keys = ("parent", "scenario", "model", "lift")
            if [r1[k] for k in keys] != [r2[k] for k in keys]:
                raise ValueError("score rows are not aligned")
            for metric in worst:
                worst[metric] = max(worst[metric], abs(float(r1[metric]) - float(r2[metric])))
    for metric, value in worst.items():
        if value > CROSS_ENVIRONMENT_TOLERANCE[metric]:
            raise ValueError(f"{metric} differs from expected by {value}")
    return worst


def _stop(signum: int, frame: Any) -> NoReturn:
    raise CeilingReached("CPU time limit signal received")


def main(argv: Sequence[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    if any(os.environ.get(v) != "1" for v in ref.THREAD_VARIABLES):
        env = {**os.environ, **{v: "1" for v in ref.THREAD_VARIABLES}}
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "powerlifting_state_research.history_uncertainty", *args_in],
            env,
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--out", type=Path, required=True, help="new empty output directory")
    parser.add_argument("--authorization-record", type=Path, help="owner record for --profile full")
    parser.add_argument("--expected", type=Path, help="compare with committed expected outputs")
    parser.add_argument("--cross-environment", action="store_true")
    args = parser.parse_args(args_in)
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU, MAX_CPU + 60))
    signal.signal(signal.SIGXCPU, _stop)
    try:
        result = run(
            args.profile,
            args.out,
            authorization=args.authorization_record,
            cross_environment_ridge=args.cross_environment,
        )
    except NotAuthorized as error:
        print(json.dumps({"status": "BLOCKED_NOT_AUTHORIZED", "reason": str(error)}))
        return 4
    except (CeilingReached, R.RidgeIdentityError) as error:
        print(
            json.dumps({"status": K.DISPOSITIONS[3], "reason": str(error)}),
        )
        return 3
    if args.expected is not None:
        compare_to_expected(args.out, args.expected, same_environment=not args.cross_environment)
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
