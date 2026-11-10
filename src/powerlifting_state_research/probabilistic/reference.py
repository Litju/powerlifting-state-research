"""CPU-only public probabilistic reference workflow (RES-615, Route B).

Pipeline: verify released GRU bytes -> generate disjoint FIT / CAL_C / CAL_G / TEST cohorts with the
public generator -> ensemble GRU location -> fit B1 and H on FIT, scale c on CAL_C, group factors G
on CAL_G -> seal TEST predictive parameters -> open TEST truth once -> score, verify, write.

This is a NEW reference, not a reproduction of historical M10-M12 results. See ``contract.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import resource
import signal
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import numpy as np
import numpy.typing as npt
import torch

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import dataset
from ..contracts.serialization import canonical_json_bytes
from ..models import temporal_expert as te
from . import scoring
from .contract import (
    ARMS,
    COHORTS,
    HORIZONS,
    INTERVAL_LEVELS,
    LIFTS,
    PLANS,
    PROTOCOL,
    PROTOCOL_DIGEST,
    REFERENCE_ID,
    RESOURCE_LIMITS,
    RIGHTS_DIGEST,
    SMOKE_COHORTS,
    TOLERANCES,
    verify_released_assets,
)

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ROOT = Path(__file__).resolve().parents[3]
N_BASE_FEATURES = 127
N_FEATURES = 140
STRATA = len(PLANS) * len(HORIZONS)
RIDGE_PENALTY = 0.05
ERROR_FLOOR_KG = 0.25
KAPPA = 256.0
BATCH = 256
MAX_RSS_BYTES = 2 * 1024**3
MAX_CPU_SECONDS = 1800
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
EXPECTED_RELATIVE = "results/references/public-probabilistic-latent-capacity-change-v1"
CESSATION = PLANS.index("cessation")
# Arms whose predictive law is upper-truncated at zero on cessation rows (names are not suffixes).
TRUNCATED_ARMS = frozenset({"B1_T", "H_T", "H_GT"})


class ResourceLimitReached(RuntimeError):
    """A frozen resource ceiling was reached; the run stops without retrying."""


class SealedTruth:
    """Hold targets until explicitly opened; the open event is recorded for the receipt."""

    def __init__(self, values: FloatArray) -> None:
        self._values = values
        self.opened = False

    def open(self) -> FloatArray:
        self.opened = True
        return self._values


@dataclass(frozen=True)
class Cohort:
    role: str
    row_ids: tuple[str, ...]
    stratum: IntArray
    features: FloatArray
    mu: FloatArray
    truth: SealedTruth

    @property
    def n(self) -> int:
        return len(self.row_ids)

    @property
    def plan(self) -> IntArray:
        return self.stratum // len(HORIZONS)


def stratum_index(plan_id: str, horizon: int) -> int:
    return PLANS.index(plan_id) * len(HORIZONS) + HORIZONS.index(horizon)


def stratum_label(index: int) -> str:
    return f"{PLANS[index // len(HORIZONS)]}/{HORIZONS[index % len(HORIZONS)]}"


# ----------------------------------------------------------------------------- features


def visible_features(history: FloatArray, plan_numeric: FloatArray, plan: IntArray) -> FloatArray:
    """127 participant-visible summaries from raw history ``(n,3,32,10)``; no target is used."""
    n = history.shape[0]
    obs = history[:, :, :, :6]
    sched = history[:, :, :, 6:9]
    steps = np.arange(obs.shape[2], dtype=np.float64)
    centered = steps - steps.mean()
    mean = obs.mean(axis=2)
    slope = np.einsum("t,nltc->nlc", centered, obs - mean[:, :, None, :]) / (centered**2).sum()
    observed = np.stack(
        [obs[:, :, 0, :], obs[:, :, -1, :], mean, obs.std(axis=2), slope], axis=-1
    ).reshape(n, -1)
    schedule = np.stack(
        [sched.mean(axis=2), sched[:, :, -4:, :].mean(axis=2), sched[:, :, -1, :]], axis=-1
    ).reshape(n, -1)
    one_hot = np.eye(len(PLANS))[plan]
    out: FloatArray = np.hstack([observed, schedule, plan_numeric, one_hot])
    if out.shape[1] != N_BASE_FEATURES:
        raise ValueError(f"expected {N_BASE_FEATURES} visible features, found {out.shape[1]}")
    return out


def head_design(base: FloatArray, mu_lift: FloatArray, stratum: IntArray) -> FloatArray:
    out: FloatArray = np.hstack([base, mu_lift[:, None], np.eye(STRATA)[stratum]])
    if out.shape[1] != N_FEATURES:
        raise ValueError(f"expected {N_FEATURES} head features, found {out.shape[1]}")
    return out


# ----------------------------------------------------------------------------- cohorts


def load_gru(
    repo_root: Path,
) -> tuple[list[te.LiftSharedTemporalExpert], te.NormalizationStats, dict[str, str]]:
    assets = verify_released_assets(repo_root)
    models = [
        te.load_weights(assets[f"seed-{seed}.pt"], te.LiftSharedTemporalExpert())
        for seed in (383001, 383002, 383003)
    ]
    payload = json.loads(assets["normalization-stats.json"].read_text(encoding="utf-8"))
    stats = te.NormalizationStats.from_dict(payload["stats"])
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in assets.items()}
    return models, stats, dict(sorted(hashes.items()))


def build_cohort(
    role: str,
    spec: dict[str, Any],
    models: Sequence[te.LiftSharedTemporalExpert],
    stats: te.NormalizationStats,
) -> Cohort:
    """Generate one cohort with the public generator and compute GRU locations and features."""
    seeds = spec["seeds"]
    config = dataset.GenerationConfig(
        train_rows=spec["rows"],
        validation_rows=len(PLANS) * len(HORIZONS),
        population_seed=seeds[0],
        intervention_seed=seeds[1],
        observation_seed=seeds[2],
        split_seed=seeds[3],
        serialization_seed=seeds[4],
    )
    ids: list[str] = []
    strata: list[int] = []
    features: list[FloatArray] = []
    mus: list[FloatArray] = []
    truths: list[list[float]] = []
    pending: list[te.TemporalModelInput] = []

    def flush() -> None:
        if not pending:
            return
        history = torch.stack([te._raw_history(row) for row in pending]).numpy()
        numeric = np.asarray([te._plan_numeric(row) for row in pending], dtype=np.float64)
        plan = np.asarray(
            [PLANS.index(row.declared_future_plan.plan_id) for row in pending], dtype=np.int64
        )
        features.append(visible_features(history, numeric, plan))
        rows = te.predict_three_seed_ensemble(models, pending, stats)
        if tuple(row.row_id for row in rows) != tuple(row.row_id for row in pending):
            raise ValueError("prediction rows are not aligned with their inputs")
        mus.append(np.asarray([row.values for row in rows], dtype=np.float64))
        pending.clear()

    for split, row in dataset.iter_public_rows(config):
        if split != "train":
            continue
        identifier = f"{role}-{row.row_id}"
        inputs = te.TemporalModelInput.from_forecast_inputs(identifier, row.inputs)
        ids.append(identifier)
        strata.append(
            stratum_index(row.inputs.declared_future_plan.plan_id, row.inputs.horizon_days)
        )
        truths.append([row.targets[f"{lift}_delta_capacity_kg"] for lift in LIFTS])  # type: ignore[literal-required]
        pending.append(inputs)
        if len(pending) == BATCH:
            flush()
    flush()
    if len(ids) != spec["rows"] or len(set(ids)) != len(ids):
        raise ValueError(f"{role} cohort has the wrong size or duplicate row ids")
    stratum = np.asarray(strata, dtype=np.int64)
    if (np.bincount(stratum, minlength=STRATA) != spec["rows"] // STRATA).any():
        raise ValueError(f"{role} cohort is not balanced across plan/horizon strata")
    return Cohort(
        role,
        tuple(ids),
        stratum,
        np.vstack(features),
        np.vstack(mus),
        SealedTruth(np.asarray(truths, dtype=np.float64)),
    )


# ----------------------------------------------------------------------------- fitting


@dataclass(frozen=True)
class HeadFit:
    mean: FloatArray  # (3,140)
    sd: FloatArray  # (3,140)
    intercept: FloatArray  # (3,)
    beta: FloatArray  # (3,140)


def fit_b1(stratum: IntArray, mu: FloatArray, y: FloatArray) -> FloatArray:
    """Per plan/horizon/lift residual RMS, shape (12,3), clipped to [0.25, 100] kg."""
    table = np.zeros((STRATA, len(LIFTS)))
    for group in range(STRATA):
        rows = stratum == group
        table[group] = np.sqrt(np.mean((y[rows] - mu[rows]) ** 2, axis=0))
    return scoring.clip_sigma(table)


def fit_h(base: FloatArray, stratum: IntArray, mu: FloatArray, y: FloatArray) -> HeadFit:
    """One ridge head per lift on the log-error proxy; unpenalized intercept, penalty 0.05."""
    means, sds, intercepts, betas = [], [], [], []
    n = base.shape[0]
    for lift in range(len(LIFTS)):
        design = head_design(base, mu[:, lift], stratum)
        mean = design.mean(axis=0)
        sd = np.maximum(design.std(axis=0), 1e-6)
        z = (design - mean) / sd
        target = np.log((y[:, lift] - mu[:, lift]) ** 2 + ERROR_FLOOR_KG**2)
        intercept = float(target.mean())
        augmented = np.vstack([z / math.sqrt(n), math.sqrt(RIDGE_PENALTY) * np.eye(N_FEATURES)])
        rhs = np.concatenate([(target - intercept) / math.sqrt(n), np.zeros(N_FEATURES)])
        beta = np.linalg.lstsq(augmented, rhs, rcond=None)[0]
        means.append(mean)
        sds.append(sd)
        intercepts.append(intercept)
        betas.append(beta)
    return HeadFit(np.vstack(means), np.vstack(sds), np.asarray(intercepts), np.vstack(betas))


def h_sigma_raw(head: HeadFit, base: FloatArray, stratum: IntArray, mu: FloatArray) -> FloatArray:
    out = np.zeros_like(mu)
    for lift in range(len(LIFTS)):
        design = head_design(base, mu[:, lift], stratum)
        z = (design - head.mean[lift]) / head.sd[lift]
        out[:, lift] = np.exp((head.intercept[lift] + z @ head.beta[lift]) / 2.0)
    return scoring.clip_sigma(out)


def fit_scale_c(sigma_raw: FloatArray, mu: FloatArray, y: FloatArray) -> FloatArray:
    out: FloatArray = np.clip(np.sqrt(np.mean((y - mu) ** 2 / sigma_raw**2, axis=0)), 0.25, 4.0)
    return out


def fit_group_factors(
    sigma_h: FloatArray, stratum: IntArray, mu: FloatArray, y: FloatArray
) -> FloatArray:
    table = np.ones((STRATA, len(LIFTS)))
    for group in range(STRATA):
        rows = stratum == group
        n = float(rows.sum())
        ratio = np.mean((y[rows] - mu[rows]) ** 2 / sigma_h[rows] ** 2, axis=0)
        table[group] = np.clip(np.sqrt((n * ratio + KAPPA) / (n + KAPPA)), 0.70, 1.40)
    return table


@dataclass(frozen=True)
class Fitted:
    b1_raw: FloatArray
    head: HeadFit
    c_b1: FloatArray
    c_h: FloatArray
    g: FloatArray


def predictive_arms(
    fit: Fitted, cohort: Cohort
) -> dict[str, tuple[FloatArray, npt.NDArray[np.bool_]]]:
    """Per-arm scale (n,3) and truncation mask. Only the cessation plan is ever truncated."""
    scoring.require_support_target(scoring.LATENT_CAPACITY_CHANGE, "cessation")
    b1 = scoring.clip_sigma(fit.c_b1 * fit.b1_raw[cohort.stratum])
    raw_h = h_sigma_raw(fit.head, cohort.features, cohort.stratum, cohort.mu)
    h = scoring.clip_sigma(fit.c_h * raw_h)
    hg = scoring.clip_sigma(h * fit.g[cohort.stratum])
    cess = cohort.plan == CESSATION
    none = np.zeros(cohort.n, dtype=bool)
    sigma = {"B1": b1, "B1_T": b1, "H": h, "H_T": h, "H_G": hg, "H_GT": hg}
    truncated = {a: (cess if a in TRUNCATED_ARMS else none) for a in ARMS}
    return {arm: (sigma[arm], truncated[arm]) for arm in ARMS}


def calibrate(fit_cohort: Cohort, cal_c: Cohort, cal_g: Cohort) -> Fitted:
    """Fit every parameter; each stage sees only its own cohort's truth."""
    y_fit = fit_cohort.truth.open()
    b1_raw = fit_b1(fit_cohort.stratum, fit_cohort.mu, y_fit)
    head = fit_h(fit_cohort.features, fit_cohort.stratum, fit_cohort.mu, y_fit)
    y_c = cal_c.truth.open()
    c_b1 = fit_scale_c(b1_raw[cal_c.stratum], cal_c.mu, y_c)
    raw_h_c = h_sigma_raw(head, cal_c.features, cal_c.stratum, cal_c.mu)
    c_h = fit_scale_c(raw_h_c, cal_c.mu, y_c)
    partial = Fitted(b1_raw, head, c_b1, c_h, np.ones((STRATA, len(LIFTS))))
    sigma_h_g = predictive_arms(partial, cal_g)["H"][0]
    g = fit_group_factors(sigma_h_g, cal_g.stratum, cal_g.mu, cal_g.truth.open())
    return Fitted(b1_raw, head, c_b1, c_h, g)


# ----------------------------------------------------------------------------- scoring


@dataclass(frozen=True)
class ArmScores:
    crps: FloatArray
    nll: FloatArray
    pit: FloatArray
    hit: dict[float, FloatArray]
    width: dict[float, FloatArray]


def score_arm(
    mu: FloatArray, sigma: FloatArray, y: FloatArray, truncated: npt.NDArray[np.bool_]
) -> ArmScores:
    crps = scoring.gaussian_crps(mu, sigma, y)
    nll = scoring.gaussian_nll(mu, sigma, y)
    pit = scoring.gaussian_cdf(mu, sigma, y)
    mask = np.broadcast_to(truncated[:, None], mu.shape)
    if mask.any():
        crps[mask] = scoring.truncated_crps(mu[mask], sigma[mask], y[mask])
        nll[mask] = scoring.truncated_nll(mu[mask], sigma[mask], y[mask])
        pit[mask] = scoring.truncated_cdf(mu[mask], sigma[mask], y[mask])
    cover = scoring.central_coverage_and_width(mu, sigma, y, mask, INTERVAL_LEVELS)
    return ArmScores(
        crps, nll, pit, {k: v[0] for k, v in cover.items()}, {k: v[1] for k, v in cover.items()}
    )


def _macro(per_lift: FloatArray) -> float:
    return float(np.mean(per_lift))


def _fmt(value: float) -> str:
    return f"{value:.9f}"


def build_tables(
    cohort: Cohort, arms: dict[str, tuple[FloatArray, npt.NDArray[np.bool_]]], y: FloatArray
) -> dict[str, list[list[str]]]:
    scores = {a: score_arm(cohort.mu, s, y, t) for a, (s, t) in arms.items()}
    score_rows: list[list[str]] = [
        ["arm", "lift", "crps_kg", "nll_nats", "pit_mean"]
        + [f"coverage_{int(100 * q)}" for q in INTERVAL_LEVELS]
        + [f"width_{int(100 * q)}_kg" for q in INTERVAL_LEVELS]
    ]
    for arm, sc in scores.items():
        for lift in (*range(len(LIFTS)), None):

            def take(a: FloatArray, i: int | None = lift) -> float:
                # macro = equal mean of the three per-lift means
                return float(a.mean() if i is None else a.mean(axis=0)[i])

            score_rows.append(
                [arm, "macro" if lift is None else LIFTS[lift]]
                + [_fmt(float(take(sc.crps))), _fmt(float(take(sc.nll))), _fmt(float(take(sc.pit)))]
                + [_fmt(float(take(sc.hit[q]))) for q in INTERVAL_LEVELS]
                + [_fmt(float(take(sc.width[q]))) for q in INTERVAL_LEVELS]
            )
    error = cohort.mu - y
    point = [["lift", "n", "gru_rmse_kg", "gru_mae_kg", "mean_error_kg"]]
    for i, lift in enumerate(LIFTS):
        point.append(
            [
                lift,
                str(cohort.n),
                _fmt(float(np.sqrt(np.mean(error[:, i] ** 2)))),
                _fmt(float(np.mean(np.abs(error[:, i])))),
                _fmt(float(np.mean(error[:, i]))),
            ]
        )
    strata_rows = [["arm", "plan_horizon", "lift", "n", "crps_kg", "coverage_90", "width_90_kg"]]
    for arm in ("H", "H_GT"):
        for group in range(STRATA):
            rows = cohort.stratum == group
            for i, lift in enumerate(LIFTS):
                strata_rows.append(
                    [
                        arm,
                        stratum_label(group),
                        lift,
                        str(int(rows.sum())),
                        _fmt(float(scores[arm].crps[rows, i].mean())),
                        _fmt(float(scores[arm].hit[0.9][rows, i].mean())),
                        _fmt(float(scores[arm].width[0.9][rows, i].mean())),
                    ]
                )
    support = [
        [
            "horizon_days",
            "n_cessation",
            "truth_nonpositive_fraction",
            "mean_gaussian_positive_mass_B1",
            "mean_gaussian_positive_mass_H",
            "truncated_positive_mass",
        ]
    ]
    for horizon in HORIZONS:
        rows = cohort.stratum == stratum_index("cessation", horizon)
        support.append(
            [
                str(horizon),
                str(int(rows.sum())),
                _fmt(float(np.mean(y[rows] <= 0))),
                _fmt(float(scoring.positive_mass(cohort.mu[rows], arms["B1"][0][rows]).mean())),
                _fmt(float(scoring.positive_mass(cohort.mu[rows], arms["H"][0][rows]).mean())),
                _fmt(
                    float(
                        1.0
                        - scoring.truncated_cdf(
                            cohort.mu[rows], arms["H_T"][0][rows], np.zeros_like(cohort.mu[rows])
                        ).max()
                    )
                ),
            ]
        )
    return {
        "scores": score_rows,
        "point_forecast": point,
        "stratum_diagnostics": strata_rows,
        "cessation_support": support,
    }


def formula_selfcheck(
    cohort: Cohort, arms: dict[str, tuple[FloatArray, npt.NDArray[np.bool_]]], y: FloatArray
) -> dict[str, float]:
    """Compare closed-form CRPS with direct numerical integration of the predictive CDF."""
    worst = 0.0
    picks = np.linspace(0, cohort.n - 1, 48).astype(int)
    for arm in ("H", "H_GT"):
        sigma, trunc = arms[arm]
        for i in picks:
            for lift in range(len(LIFTS)):
                m, s, o = cohort.mu[i, lift], sigma[i, lift], y[i, lift]
                cut = bool(trunc[i])
                cdf = scoring.truncated_cdf if cut else scoring.gaussian_cdf
                hi = 0.0 if cut else m + 14 * s
                lo = min(m - 14 * s, o - 1.0)
                left = np.linspace(lo, o, 20001)
                right = np.linspace(o, max(hi, o), 20001)
                integral = np.trapezoid(cdf(m, s, left) ** 2, left) + np.trapezoid(
                    (1 - cdf(m, s, right)) ** 2, right
                )
                closed = (scoring.truncated_crps if cut else scoring.gaussian_crps)(m, s, o)
                worst = max(worst, abs(float(closed) - float(integral)))
    if worst > TOLERANCES["formula_reference_abs"] * 1e4:
        raise ValueError(f"closed-form CRPS disagrees with numerical integration: {worst}")
    return {"max_abs_crps_vs_integral_kg": worst, "rows_checked": float(len(picks) * 2 * 3)}


def alignment_checks(
    cohort: Cohort, arms: dict[str, tuple[FloatArray, npt.NDArray[np.bool_]]], y: FloatArray
) -> None:
    n = cohort.n
    if not (cohort.mu.shape == y.shape == (n, 3) and cohort.features.shape[0] == n):
        raise ValueError("cohort arrays are misaligned")
    for sigma, mask in arms.values():
        if sigma.shape != (n, 3) or mask.shape != (n,) or not np.isfinite(sigma).all():
            raise ValueError("predictive arms are misaligned or non-finite")
        if sigma.min() < 0.25 or sigma.max() > 100.0:
            raise ValueError("predictive scale left the frozen [0.25, 100] kg bounds")
    cessation = cohort.plan == CESSATION
    if (y[cessation] > 0).any():
        raise ValueError("cessation truth is positive; the truncation support rule is invalid")
    parsed = [rid.split("-", 1)[0] for rid in cohort.row_ids]
    if set(parsed) != {"TEST"}:
        raise ValueError("TEST row ids carry the wrong role prefix")


# ----------------------------------------------------------------------------- outputs


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_digest(*arrays: FloatArray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.ascontiguousarray(np.round(array, 9), dtype="<f8").tobytes())
    return digest.hexdigest()


def csv_bytes(rows: list[list[str]]) -> bytes:
    import io

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode("utf-8")


def parameters_document(fit: Fitted) -> dict[str, Any]:
    return {
        "note": "Parameters of this NEW public reference only; not the historical private ones.",
        "b1_residual_rms_kg_by_plan_horizon_lift": {
            stratum_label(g): [round(float(v), 9) for v in fit.b1_raw[g]] for g in range(STRATA)
        },
        "scale_c": {
            "B1": [round(float(v), 9) for v in fit.c_b1],
            "H": [round(float(v), 9) for v in fit.c_h],
        },
        "group_factors_G": {
            stratum_label(g): [round(float(v), 9) for v in fit.g[g]] for g in range(STRATA)
        },
        "h_head": {
            lift: {
                "intercept": round(float(fit.head.intercept[i]), 9),
                "beta_l2_norm": round(float(np.linalg.norm(fit.head.beta[i])), 9),
                "beta_sha256": array_digest(fit.head.beta[i]),
            }
            for i, lift in enumerate(LIFTS)
        },
    }


# ----------------------------------------------------------------------------- figures


def _svg(width: int, height: int, body: str, title: str) -> bytes:
    style = (
        ":root{--s:#fcfcfb;--t:#0b0b0b;--m:#52514e;--g:#d9d8d3;--a:#2a78d6;--b:#eb6834;}"
        "@media (prefers-color-scheme:dark){:root{--s:#1a1a19;--t:#f0efec;--m:#c3c2b7;"
        "--g:#3a3a38;--a:#3987e5;--b:#d95926;}}"
        "text{font:12px system-ui,sans-serif;fill:var(--t)}.m{fill:var(--m)}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{title}"><title>{title}</title><style>{style}</style>'
        f'<rect width="{width}" height="{height}" fill="var(--s)"/>{body}</svg>\n'
    ).encode()


def _panel(
    x0: int,
    y0: int,
    w: int,
    h: int,
    title: str,
    labels: Sequence[str],
    values: Sequence[float],
    colors: Sequence[str],
    vmax: float,
    unit: str,
    reference: float | None = None,
) -> str:
    out = [f'<text x="{x0}" y="{y0 - 12}">{title}</text>']
    out.append(f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="var(--g)"/>')
    slot = w / len(values)
    for i, (label, value, color) in enumerate(zip(labels, values, colors, strict=True)):
        bar = max(value, 0.0) / vmax * h
        x = x0 + i * slot + slot * 0.2
        out.append(
            f'<rect x="{x:.1f}" y="{y0 + h - bar:.1f}" width="{slot * 0.6:.1f}" '
            f'height="{bar:.1f}" rx="3" fill="var(--{color})"/>'
        )
        out.append(
            f'<text class="m" x="{x + slot * 0.3:.1f}" y="{y0 + h - bar - 5:.1f}" '
            f'text-anchor="middle">{value:.3f}{unit}</text>'
        )
        out.append(
            f'<text class="m" x="{x + slot * 0.3:.1f}" y="{y0 + h + 16}" '
            f'text-anchor="middle">{label}</text>'
        )
    if reference is not None:
        ry = y0 + h - reference / vmax * h
        out.append(
            f'<line x1="{x0}" y1="{ry:.1f}" x2="{x0 + w}" y2="{ry:.1f}" stroke="var(--t)" '
            'stroke-dasharray="4 3"/>'
            f'<text class="m" x="{x0 + w}" y="{ry - 4:.1f}" text-anchor="end">'
            f"nominal {reference}</text>"
        )
    return "".join(out)


def figures(tables: dict[str, list[list[str]]]) -> dict[str, bytes]:
    header = tables["scores"][0]
    macro = {r[0]: r for r in tables["scores"][1:] if r[1] == "macro"}
    col = {name: i for i, name in enumerate(header)}
    colors = ["b" if arm in TRUNCATED_ARMS or arm == "H_G" else "a" for arm in ARMS]
    f1 = _panel(
        50,
        50,
        330,
        220,
        "Macro CRPS (kg), lower is better",
        ARMS,
        [float(macro[a][col["crps_kg"]]) for a in ARMS],
        colors,
        max(float(macro[a][col["crps_kg"]]) for a in ARMS) * 1.15,
        "",
    )
    f1 += _panel(
        430,
        50,
        330,
        220,
        "Macro NLL (nats), lower is better",
        ARMS,
        [
            float(macro[a][col["nll_nats"]])
            - min(float(macro[b][col["nll_nats"]]) for b in ARMS)
            + 0.0
            for a in ARMS
        ],
        colors,
        max(
            max(float(macro[a][col["nll_nats"]]) for a in ARMS)
            - min(float(macro[a][col["nll_nats"]]) for a in ARMS),
            1e-6,
        )
        * 1.15,
        "",
    )
    f1 += (
        '<text class="m" x="430" y="310">NLL relative to the best arm; '
        "orange = truncated or group-calibrated.</text>"
    )
    fig1 = _svg(800, 330, f1, "Macro CRPS and relative NLL by arm")

    f2 = ""
    for k, level in enumerate(INTERVAL_LEVELS):
        f2 += _panel(
            40 + k * 250,
            50,
            220,
            200,
            f"Central {int(100 * level)}% empirical coverage",
            ARMS,
            [float(macro[a][col[f"coverage_{int(100 * level)}"]]) for a in ARMS],
            colors,
            1.0,
            "",
            reference=level,
        )
    fig2 = _svg(800, 300, f2, "Nominal versus empirical central interval coverage by arm")

    sup = tables["cessation_support"][1:]
    labels = [f"{r[0]} d" for r in sup]
    f3 = _panel(
        50,
        50,
        330,
        200,
        "Cessation: Gaussian mass above zero, B1",
        labels,
        [float(r[3]) for r in sup],
        ["a"] * len(sup),
        max(float(r[3]) for r in sup) * 1.15 + 1e-9,
        "",
    )
    f3 += _panel(
        430,
        50,
        330,
        200,
        "Cessation: Gaussian mass above zero, H",
        labels,
        [float(r[4]) for r in sup],
        ["a"] * len(sup),
        max(float(r[4]) for r in sup) * 1.15 + 1e-9,
        "",
    )
    f3 += '<text class="m" x="50" y="290">Truncated arms place exactly zero mass above zero.</text>'
    fig3 = _svg(800, 310, f3, "Gaussian predictive mass above zero under cessation")
    return {
        "figure-1-macro-scores.svg": fig1,
        "figure-2-interval-coverage.svg": fig2,
        "figure-3-cessation-support.svg": fig3,
    }


# ----------------------------------------------------------------------------- orchestration


def _peak_rss_bytes() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _check_budget(started_cpu: float) -> None:
    if _peak_rss_bytes() > MAX_RSS_BYTES:
        raise ResourceLimitReached("peak resident memory exceeded the 2 GiB ceiling")
    if time.process_time() - started_cpu > MAX_CPU_SECONDS:
        raise ResourceLimitReached("charged CPU time exceeded the 30 minute ceiling")


def require_pinned_threads() -> None:
    torch.set_num_threads(1)
    if torch.get_num_threads() != 1 or any(os.environ.get(v) != "1" for v in THREAD_VARIABLES):
        raise RuntimeError(
            "one BLAS/PyTorch thread is required; set OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "
            "MKL_NUM_THREADS=1 (the command line entry point does this automatically)"
        )


def run(profile: str, out_dir: Path, repo_root: Path = ROOT) -> dict[str, Any]:
    """Execute the whole reference once and write deterministic outputs plus a receipt."""
    if profile not in ("smoke", "full"):
        raise ValueError("profile must be 'smoke' or 'full'")
    require_pinned_threads()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to write into a non-empty directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    roles = SMOKE_COHORTS if profile == "smoke" else COHORTS
    started, wall = time.process_time(), time.time()
    phases: dict[str, float] = {}
    models, stats, asset_hashes = load_gru(repo_root)

    def build(role: str) -> Cohort:
        t = time.process_time()
        cohort = build_cohort(role, roles[role], models, stats)
        phases[role] = round(time.process_time() - t, 3)
        _check_budget(started)
        return cohort

    fit_cohort, cal_c, cal_g = build("FIT"), build("CAL_C"), build("CAL_G")
    fit = calibrate(fit_cohort, cal_c, cal_g)
    test = build("TEST")
    arms = predictive_arms(fit, test)
    seal = array_digest(test.mu, *[arms[a][0] for a in ARMS])
    if test.truth.opened:
        raise RuntimeError("TEST truth was opened before predictions were sealed")
    y = test.truth.open()
    alignment_checks(test, arms, y)
    check = formula_selfcheck(test, arms, y)
    tables = build_tables(test, arms, y)
    outputs: dict[str, bytes] = {f"{name}.csv": csv_bytes(rows) for name, rows in tables.items()}
    outputs.update(figures(tables))
    outputs["fitted-parameters.json"] = canonical_json_bytes(parameters_document(fit)) + b"\n"
    manifest = {
        "reference_id": REFERENCE_ID,
        "protocol_digest": PROTOCOL_DIGEST,
        "rights_register_digest": RIGHTS_DIGEST,
        "profile": profile,
        "route": PROTOCOL["route"],
        "target": PROTOCOL["target"]["kind"],
        "released_asset_sha256": asset_hashes,
        "cohorts": {
            role: {
                "rows": cohort.n,
                "seeds": roles[role]["seeds"],
                "row_id_sha256": _sha("\n".join(cohort.row_ids).encode()),
                "feature_sha256": array_digest(cohort.features),
                "truth_opened_for": "scoring" if role == "TEST" else "fitting",
            }
            for role, cohort in (
                ("FIT", fit_cohort),
                ("CAL_C", cal_c),
                ("CAL_G", cal_g),
                ("TEST", test),
            )
        },
        "test_prediction_seal_sha256": seal,
        "test_truth_sha256": array_digest(y),
        "formula_selfcheck": check,
        "output_sha256": {name: _sha(data) for name, data in sorted(outputs.items())},
        "nonclaims": PROTOCOL["nonclaims"],
    }
    outputs["manifest.json"] = canonical_json_bytes(manifest) + b"\n"
    for name, data in outputs.items():
        (out_dir / name).write_bytes(data)
    receipt = {
        "reference_id": REFERENCE_ID,
        "manifest_sha256": _sha(outputs["manifest.json"]),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "platform": f"{platform.system()} {platform.machine()}",
            "threads": {v: os.environ.get(v) for v in THREAD_VARIABLES},
            "torch_threads": torch.get_num_threads(),
            "device": "cpu",
        },
        "resources": {
            "cpu_seconds": round(time.process_time() - started, 3),
            "wall_seconds": round(time.time() - wall, 3),
            "peak_rss_bytes": _peak_rss_bytes(),
            "phase_cpu_seconds": phases,
            "ceilings": RESOURCE_LIMITS,
        },
    }
    _check_budget(started)
    (out_dir / "execution-receipt.json").write_bytes(canonical_json_bytes(receipt) + b"\n")
    return {"manifest": manifest, "receipt": receipt}


def compare_to_expected(
    out_dir: Path, expected_dir: Path, *, same_environment: bool
) -> dict[str, float]:
    """Check a fresh run against committed expected outputs; never edits the expected files."""
    mine = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    theirs = json.loads((expected_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in mine["output_sha256"].items():
        if _sha((out_dir / name).read_bytes()) != digest:
            raise ValueError(f"output file does not match its manifest hash: {name}")
    for key in (
        "reference_id",
        "protocol_digest",
        "rights_register_digest",
        "profile",
        "released_asset_sha256",
        "target",
    ):
        if mine[key] != theirs[key]:
            raise ValueError(f"manifest identity differs: {key}")
    for role, item in mine["cohorts"].items():
        for key in ("rows", "seeds", "row_id_sha256", "feature_sha256"):
            if item[key] != theirs["cohorts"][role][key]:
                raise ValueError(f"cohort {role} differs: {key}")
    if mine["test_truth_sha256"] != theirs["test_truth_sha256"]:
        raise ValueError("TEST truth differs from the expected generation")
    if same_environment:
        if mine["output_sha256"] != theirs["output_sha256"]:
            raise ValueError("same-environment run is not byte-identical")
        if mine["test_prediction_seal_sha256"] != theirs["test_prediction_seal_sha256"]:
            raise ValueError("same-environment prediction seal differs")
    limits = {
        "crps_kg": TOLERANCES["cross_environment_crps_kg_abs"],
        "nll_nats": TOLERANCES["cross_environment_nll_abs"],
        "pit_mean": TOLERANCES["cross_environment_coverage_abs"],
    }
    worst = {"crps_kg": 0.0, "nll_nats": 0.0, "coverage": 0.0, "width_kg": 0.0}
    with (
        (out_dir / "scores.csv").open(newline="") as a,
        (expected_dir / "scores.csv").open(newline="") as b,
    ):
        for r1, r2 in zip(csv.DictReader(a), csv.DictReader(b), strict=True):
            if (r1["arm"], r1["lift"]) != (r2["arm"], r2["lift"]):
                raise ValueError("score rows are not aligned")
            for column, value in r1.items():
                if column in ("arm", "lift"):
                    continue
                diff = abs(float(value) - float(r2[column]))
                kind = (
                    "coverage"
                    if column.startswith("coverage") or column == "pit_mean"
                    else "width_kg"
                    if column.startswith("width")
                    else column
                )
                worst[kind] = max(worst[kind], diff)
    bounds = {
        "crps_kg": limits["crps_kg"],
        "nll_nats": limits["nll_nats"],
        "coverage": TOLERANCES["cross_environment_coverage_abs"],
        "width_kg": TOLERANCES["cross_environment_width_kg_abs"],
    }
    for kind, value in worst.items():
        if value > bounds[kind]:
            raise ValueError(f"{kind} differs from expected by {value} (tolerance {bounds[kind]})")
    return worst


# ----------------------------------------------------------------------------- command line


def _stop(signum: int, frame: Any) -> NoReturn:
    raise ResourceLimitReached("CPU time limit signal received (30 minute ceiling)")


def main(argv: Sequence[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    if any(os.environ.get(v) != "1" for v in THREAD_VARIABLES):
        env = {**os.environ, **{v: "1" for v in THREAD_VARIABLES}}
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "powerlifting_state_research.probabilistic", *args_in],
            env,
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--out", type=Path, required=True, help="new empty output directory")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--expected", type=Path, help="compare with committed expected outputs")
    parser.add_argument(
        "--cross-environment",
        action="store_true",
        help="use cross-environment tolerances instead of byte identity",
    )
    args = parser.parse_args(args_in)
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (MAX_CPU_SECONDS, MAX_CPU_SECONDS + 30),
    )
    signal.signal(signal.SIGXCPU, _stop)
    try:
        result = run(args.profile, args.out, args.repo_root)
    except ResourceLimitReached as error:
        print(json.dumps({"status": "LIMITATION", "reason": str(error)}))
        return 3
    status: dict[str, Any] = {
        "status": "PASS",
        "reference_id": REFERENCE_ID,
        "resources": result["receipt"]["resources"],
    }
    expected = args.expected or (
        args.repo_root / EXPECTED_RELATIVE / ("full" if args.profile == "full" else "smoke")
    )
    if expected.is_dir():
        status["max_differences_from_expected"] = compare_to_expected(
            args.out, expected, same_environment=not args.cross_environment
        )
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
