"""M0 persistence, M1 ridge, M2 GRU and the sigma calibration chain for observed assessments.

Targets are absolute assessments Y; M1 and M2 learn the deviation from the latest assessment, so
every model's forecast is ``last + correction``. No latent-capacity model output is used anywhere.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import torch
from torch import nn

from ..models import temporal_expert as te
from ..probabilistic import reference as ref
from ..probabilistic import scoring
from . import contract as C
from .data import ObsCohort

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
ALPHAS = (0.01, 0.1, 1.0, 10.0)
STRATA = 12
N_RIDGE_FEATURES = 163
LR = 1e-3
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 256
CLIP_NORM = 1.0
PATIENCE = 4
MIN_IMPROVEMENT = 1e-4
_TE_PLAN = {plan: te.PLAN_ORDER.index(plan) for plan in C.PLANS}


# ------------------------------------------------------------------------------ M1 ridge


def ridge_design(cohort_features: FloatArray, stratum: IntArray, lift: int) -> FloatArray:
    """163 columns: 127 visible + 12 strata + 12 strata x (last assessment, assessment slope)."""
    one_hot = np.eye(STRATA)[stratum]
    last = cohort_features[:, lift * 30 + 1][:, None]
    slope = cohort_features[:, lift * 30 + 4][:, None]
    out: FloatArray = np.hstack([cohort_features, one_hot, one_hot * last, one_hot * slope])
    if out.shape[1] != N_RIDGE_FEATURES:
        raise ValueError("unexpected ridge design width")
    return out


@dataclass(frozen=True)
class RidgeFit:
    alpha: float
    mean: FloatArray  # (3,163)
    sd: FloatArray
    intercept: FloatArray  # (3,)
    beta: FloatArray  # (3,163)


def _ridge_one(design: FloatArray, target: FloatArray, alpha: float) -> tuple[Any, ...]:
    n = design.shape[0]
    mean = design.mean(axis=0)
    sd = np.maximum(design.std(axis=0), 1e-6)
    z = (design - mean) / sd
    intercept = float(target.mean())
    augmented = np.vstack([z / math.sqrt(n), math.sqrt(alpha) * np.eye(design.shape[1])])
    rhs = np.concatenate([(target - intercept) / math.sqrt(n), np.zeros(design.shape[1])])
    beta = np.linalg.lstsq(augmented, rhs, rcond=None)[0]
    return mean, sd, intercept, beta


def ridge_predict_delta(fit: RidgeFit, cohort: ObsCohort) -> FloatArray:
    out = np.zeros((cohort.n, 3))
    for lift in range(3):
        z = (ridge_design(cohort.base_features, cohort.stratum, lift) - fit.mean[lift]) / fit.sd[
            lift
        ]
        out[:, lift] = fit.intercept[lift] + z @ fit.beta[lift]
    return out


def fit_ridge(fit: ObsCohort, dev: ObsCohort) -> tuple[RidgeFit, dict[str, float]]:
    """Fit per lift on FIT for each fixed alpha; choose alpha by DEV RMSE only."""
    y_fit = fit.truth.open().y - fit.last_assessment
    y_dev = dev.truth.open().y - dev.last_assessment
    scores: dict[str, float] = {}
    best: RidgeFit | None = None
    best_score = math.inf
    for alpha in ALPHAS:
        parts = [
            _ridge_one(ridge_design(fit.base_features, fit.stratum, lift), y_fit[:, lift], alpha)
            for lift in range(3)
        ]
        candidate = RidgeFit(
            alpha,
            np.vstack([p[0] for p in parts]),
            np.vstack([p[1] for p in parts]),
            np.asarray([p[2] for p in parts]),
            np.vstack([p[3] for p in parts]),
        )
        rmse = np.sqrt(np.mean((ridge_predict_delta(candidate, dev) - y_dev) ** 2, axis=0))
        scores[str(alpha)] = float(rmse.mean())
        if scores[str(alpha)] < best_score:
            best, best_score = candidate, scores[str(alpha)]
    assert best is not None
    return best, scores


# ------------------------------------------------------------------------------ M2 GRU


def gru_stats(fit: ObsCohort) -> te.NormalizationStats:
    """FIT-only input statistics (first six channels) and FIT-only delta-target statistics."""
    observed = torch.from_numpy(fit.raw_history[:, :, :, :6])
    delta = fit.truth.open().y - fit.last_assessment
    target = torch.from_numpy(delta)
    scale = target.std(dim=0, unbiased=False).clamp_min(te.NORMALIZATION_EPSILON)
    return te.NormalizationStats(
        te._matrix_tuple(observed.mean(dim=(0, 2))),
        te._matrix_tuple(observed.std(dim=(0, 2), unbiased=False).clamp_min(1e-6)),
        tuple(float(v) for v in target.mean(dim=0).tolist()),  # type: ignore[arg-type]
        tuple(float(v) for v in scale.tolist()),  # type: ignore[arg-type]
    )


def make_batch(cohort: ObsCohort, stats: te.NormalizationStats) -> te.TemporalModelBatch:
    """Same preprocessing as ``te.prepare_batch`` computed from stored raw history."""
    history = torch.from_numpy(cohort.raw_history.copy())
    mean = torch.tensor(stats.input_mean, dtype=torch.float64).view(1, 3, 1, 6)
    scale = torch.tensor(stats.input_scale, dtype=torch.float64).view(1, 3, 1, 6)
    history[:, :, :, :6] = (history[:, :, :, :6] - mean) / scale
    history[:, :, :, 6] /= 1.2
    history[:, :, :, 7] /= 1.0
    history[:, :, :, 8] /= 1.2
    plan_index = torch.tensor([_TE_PLAN[C.PLANS[p]] for p in cohort.plan], dtype=torch.int64)
    batch = te.TemporalModelBatch(
        history.to(torch.float32),
        torch.ones((cohort.n, 3, 32), dtype=torch.float32),
        torch.from_numpy(cohort.plan_numeric).to(torch.float32),
        plan_index,
    )
    batch.validate()
    return batch


def _slice(batch: te.TemporalModelBatch, index: torch.Tensor) -> te.TemporalModelBatch:
    return te.TemporalModelBatch(
        batch.history[index],
        batch.history_mask[index],
        batch.plan_numeric[index],
        batch.plan_index[index],
    )


def target_z(cohort: ObsCohort, stats: te.NormalizationStats) -> torch.Tensor:
    delta = cohort.truth.open().y - cohort.last_assessment
    mean = np.asarray(stats.target_mean)
    scale = np.asarray(stats.target_scale)
    return torch.from_numpy(((delta - mean) / scale).astype(np.float32))


@dataclass
class TrainResult:
    model: te.LiftSharedTemporalExpert
    history: list[dict[str, float]]
    best_epoch: int
    stop_reason: str
    cpu_seconds: float
    epochs_run: int
    forward_backward_calls: int


def train_gru(
    fit_batch: te.TemporalModelBatch,
    fit_z: torch.Tensor,
    dev_batch: te.TemporalModelBatch,
    dev_z: torch.Tensor,
    *,
    seed: int,
    max_epochs: int = 20,
    cpu_budget_seconds: float = 2400.0,
) -> TrainResult:
    """One training attempt: AdamW, DEV-only early stopping (patience 4), best-state restore."""
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    model = te.LiftSharedTemporalExpert()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY, betas=(0.9, 0.999)
    )
    started = time.process_time()
    n = fit_z.shape[0]
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    best_mse, best_epoch, waited, calls = math.inf, 0, 0, 0
    history: list[dict[str, float]] = []
    reason = "max_epochs"
    for epoch in range(1, max_epochs + 1):
        model.train()
        order = torch.randperm(n, generator=generator)
        total = 0.0
        for start in range(0, n, BATCH_SIZE):
            index = order[start : start + BATCH_SIZE]
            loss = torch.mean((model(_slice(fit_batch, index)) - fit_z[index]) ** 2)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()  # type: ignore[no-untyped-call]
            nn.utils.clip_grad_norm_(model.parameters(), CLIP_NORM)
            optimizer.step()
            total += float(loss.detach()) * len(index)
            calls += 1
            if time.process_time() - started > cpu_budget_seconds:
                reason = "cpu_budget_exhausted"
                break
        dev_mse = float(torch.mean((_forward(model, dev_batch) - dev_z) ** 2))
        history.append(
            {
                "epoch": epoch,
                "train_mse": total / n,
                "dev_mse": dev_mse,
                "cpu_seconds": time.process_time() - started,
            }
        )
        if dev_mse < best_mse - MIN_IMPROVEMENT:
            best_mse, best_epoch, waited = dev_mse, epoch, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            waited += 1
        if reason == "cpu_budget_exhausted":
            break
        if waited >= PATIENCE:
            reason = "early_stopping"
            break
    model.load_state_dict(best_state)
    model.eval()
    return TrainResult(
        model, history, best_epoch, reason, time.process_time() - started, len(history), calls
    )


def _forward(model: te.LiftSharedTemporalExpert, batch: te.TemporalModelBatch) -> torch.Tensor:
    model.eval()
    outputs = []
    with torch.inference_mode():
        for start in range(0, batch.history.shape[0], 1024):
            index = torch.arange(start, min(start + 1024, batch.history.shape[0]))
            outputs.append(model(_slice(batch, index)))
    return torch.cat(outputs)


def gru_predict_delta(
    model: te.LiftSharedTemporalExpert, cohort: ObsCohort, stats: te.NormalizationStats
) -> FloatArray:
    z = _forward(model, make_batch(cohort, stats)).numpy().astype(np.float64)
    out: FloatArray = z * np.asarray(stats.target_scale) + np.asarray(stats.target_mean)
    return out


def state_digest(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().numpy().astype("<f4").tobytes())
    return digest.hexdigest()


# ------------------------------------------------------------------------------ calibration


@dataclass(frozen=True)
class SigmaChain:
    raw: FloatArray  # (12,3) DEV group RMS
    c: FloatArray  # (3,) CAL_C
    g: FloatArray  # (12,3) CAL_G


@dataclass(frozen=True)
class Frozen:
    ridge: RidgeFit
    ridge_alpha_scores: dict[str, float]
    gru: te.LiftSharedTemporalExpert
    stats: te.NormalizationStats
    chains: dict[str, SigmaChain]
    train: TrainResult | None


def predict_mu(model: str, frozen: Frozen, cohort: ObsCohort) -> FloatArray:
    last = cohort.last_assessment
    if model == "M0":
        return last.copy()
    if model == "M1":
        return last + ridge_predict_delta(frozen.ridge, cohort)
    if model == "M2":
        return last + gru_predict_delta(frozen.gru, cohort, frozen.stats)
    raise ValueError(f"unknown model {model!r}")


def sigma_c(chain: SigmaChain, stratum: IntArray) -> FloatArray:
    return scoring.clip_sigma(chain.c * chain.raw[stratum])


def sigma_g(chain: SigmaChain, stratum: IntArray) -> FloatArray:
    return scoring.clip_sigma(sigma_c(chain, stratum) * chain.g[stratum])


def fit_chain(
    model: str,
    frozen_partial: Frozen,
    dev: ObsCohort,
    cal_c: ObsCohort,
    cal_g: ObsCohort,
) -> SigmaChain:
    """sigma_raw from DEV group RMS, c from CAL_C, shrinkage group factors from CAL_G."""
    raw = ref.fit_b1(dev.stratum, predict_mu(model, frozen_partial, dev), dev.truth.open().y)
    mu_c = predict_mu(model, frozen_partial, cal_c)
    y_c = cal_c.truth.open().y
    c = ref.fit_scale_c(raw[cal_c.stratum], mu_c, y_c)
    partial = SigmaChain(raw, c, np.ones((STRATA, 3)))
    mu_g = predict_mu(model, frozen_partial, cal_g)
    g = ref.fit_group_factors(
        sigma_c(partial, cal_g.stratum), cal_g.stratum, mu_g, cal_g.truth.open().y
    )
    return SigmaChain(raw, c, g)


def predictive_arms(frozen: Frozen, cohort: ObsCohort) -> dict[str, tuple[FloatArray, FloatArray]]:
    """arm -> (mu, sigma). No truncation exists in this path (see contract)."""
    C.check_target_compatibility(C.OBSERVED_TARGET_KIND, "cessation")
    mu = {m: predict_mu(m, frozen, cohort) for m in C.MODELS}
    return {
        "M0_C": (mu["M0"], sigma_c(frozen.chains["M0"], cohort.stratum)),
        "M1_C": (mu["M1"], sigma_c(frozen.chains["M1"], cohort.stratum)),
        "M1_G": (mu["M1"], sigma_g(frozen.chains["M1"], cohort.stratum)),
        "M2_C": (mu["M2"], sigma_c(frozen.chains["M2"], cohort.stratum)),
        "M2_G": (mu["M2"], sigma_g(frozen.chains["M2"], cohort.stratum)),
    }
