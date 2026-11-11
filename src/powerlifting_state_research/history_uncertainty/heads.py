"""B_GROUP, B_MAG and H_HISTORY predictive-scale models around the frozen RES-616 Ridge.

All three share one estimator family, residual floor, penalty, standardization, calibration and
clipping; only the design columns differ. The location mu is never modified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from ..observable import models as ridge_models
from ..observable.data import ObsCohort
from ..probabilistic import reference as ref
from . import contract as K

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
FIT_ROLE = "SCALE_FIT"
CAL_ROLE = "SCALE_CAL"


class RoleViolation(ValueError):
    """A cohort with the wrong role was offered to a fitting or calibration routine."""


def require_role(cohort: ObsCohort, expected: str) -> None:
    """Scale fitting uses SCALE_FIT only and calibration SCALE_CAL only; never TEST data."""
    if cohort.role != expected:
        raise RoleViolation(f"expected a {expected} cohort, received {cohort.role!r}")
    if any(not identifier.startswith(f"{expected}-") for identifier in cohort.row_ids):
        raise RoleViolation(f"row identifiers do not carry the {expected} prefix")


def ridge_mu(ridge: ridge_models.RidgeFit, cohort: ObsCohort) -> FloatArray:
    """Frozen location forecast: latest assessment plus the Ridge correction (kg)."""
    out: FloatArray = cohort.last_assessment + ridge_models.ridge_predict_delta(ridge, cohort)
    return out


# ------------------------------------------------------------------ designs


def mag_design(mu_lift: FloatArray, stratum: IntArray) -> FloatArray:
    """mu, log(max(mu, 1 kg)) and 12 plan x horizon indicators: 14 columns."""
    log_mu = np.log(np.maximum(mu_lift, K.LOG_MU_FLOOR_KG))
    out: FloatArray = np.hstack([mu_lift[:, None], log_mu[:, None], np.eye(K.STRATA)[stratum]])
    if out.shape[1] != K.N_MAG_FEATURES:
        raise ValueError("unexpected magnitude design width")
    return out


def history_design(base: FloatArray, mu_lift: FloatArray, stratum: IntArray) -> FloatArray:
    """The magnitude columns plus the 127 RES-616 participant-visible summaries: 141 columns."""
    if base.shape[1] != K.N_BASE_FEATURES:
        raise ValueError("unexpected visible-feature width")
    out: FloatArray = np.hstack([mag_design(mu_lift, stratum), base])
    if out.shape[1] != K.N_HISTORY_FEATURES:
        raise ValueError("unexpected history design width")
    return out


def design_for(model: str, base: FloatArray, mu_lift: FloatArray, stratum: IntArray) -> FloatArray:
    if model == "B_MAG":
        return mag_design(mu_lift, stratum)
    if model == "H_HISTORY":
        return history_design(base, mu_lift, stratum)
    raise ValueError(f"model {model!r} has no regression design")


# ------------------------------------------------------------------ fitting


@dataclass(frozen=True)
class ScaleHead:
    mean: FloatArray  # (3, p)
    sd: FloatArray
    intercept: FloatArray  # (3,)
    beta: FloatArray  # (3, p)


def log_squared_residual(y: FloatArray, mu: FloatArray) -> FloatArray:
    out: FloatArray = np.log((y - mu) ** 2 + K.ERROR_FLOOR_KG**2)
    return out


def fit_head(
    model: str, base: FloatArray, stratum: IntArray, mu: FloatArray, y: FloatArray
) -> ScaleHead:
    """Per-lift ridge on z = log((Y-mu)^2 + eps^2); unpenalized intercept; fixed penalty."""
    means, sds, intercepts, betas = [], [], [], []
    n = base.shape[0]
    for lift in range(len(K.LIFTS)):
        design = design_for(model, base, mu[:, lift], stratum)
        p = design.shape[1]
        mean = design.mean(axis=0)
        sd = np.maximum(design.std(axis=0), 1e-6)
        z = (design - mean) / sd
        target = log_squared_residual(y[:, lift], mu[:, lift])
        intercept = float(target.mean())
        augmented = np.vstack([z / math.sqrt(n), math.sqrt(K.RIDGE_PENALTY) * np.eye(p)])
        rhs = np.concatenate([(target - intercept) / math.sqrt(n), np.zeros(p)])
        beta = np.linalg.lstsq(augmented, rhs, rcond=None)[0]
        means.append(mean)
        sds.append(sd)
        intercepts.append(intercept)
        betas.append(beta)
    return ScaleHead(np.vstack(means), np.vstack(sds), np.asarray(intercepts), np.vstack(betas))


def head_log_variance(
    model: str,
    head: ScaleHead,
    base: FloatArray,
    stratum: IntArray,
    mu: FloatArray,
    shift: float = 0.0,
) -> FloatArray:
    """zhat per row and lift. ``shift`` is a test hook for the c-invariance property."""
    out: FloatArray = np.zeros_like(mu)
    for lift in range(len(K.LIFTS)):
        design = design_for(model, base, mu[:, lift], stratum)
        z = (design - head.mean[lift]) / head.sd[lift]
        out[:, lift] = head.intercept[lift] + z @ head.beta[lift] + shift
    return out


def clip_sigma(sigma: npt.ArrayLike) -> FloatArray:
    return np.clip(np.asarray(sigma, dtype=np.float64), K.SIGMA_MIN_KG, K.SIGMA_MAX_KG)


def group_rms(stratum: IntArray, mu: FloatArray, y: FloatArray) -> FloatArray:
    """B_GROUP raw scale: per stratum and lift RMS residual, shape (12, 3), clipped."""
    table = np.zeros((K.STRATA, len(K.LIFTS)))
    for group in range(K.STRATA):
        rows = stratum == group
        if not rows.any():
            raise ValueError(f"stratum {group} is empty")
        table[group] = np.sqrt(np.mean((y[rows] - mu[rows]) ** 2, axis=0))
    return clip_sigma(table)


def fit_scale_c(sigma_raw: FloatArray, mu: FloatArray, y: FloatArray) -> FloatArray:
    """Per-lift RMS-scale calibration: sqrt(mean((Y-mu)^2/sigma_raw^2)) clipped to [0.25, 4]."""
    out: FloatArray = np.clip(
        np.sqrt(np.mean((y - mu) ** 2 / sigma_raw**2, axis=0)), K.SCALE_C_MIN, K.SCALE_C_MAX
    )
    return out


@dataclass(frozen=True)
class ScaleModel:
    name: str
    head: ScaleHead | None
    group: FloatArray | None  # (12, 3) for B_GROUP
    c: FloatArray  # (3,)
    c_clipped: int

    def sigma_raw(self, base: FloatArray, stratum: IntArray, mu: FloatArray) -> FloatArray:
        if self.name == "B_GROUP":
            assert self.group is not None
            return np.asarray(self.group[stratum], dtype=np.float64)
        assert self.head is not None
        return clip_sigma(np.exp(head_log_variance(self.name, self.head, base, stratum, mu) / 2.0))

    def sigma(self, base: FloatArray, stratum: IntArray, mu: FloatArray) -> FloatArray:
        return clip_sigma(self.c * self.sigma_raw(base, stratum, mu))


@dataclass(frozen=True)
class FrozenScale:
    ridge: ridge_models.RidgeFit
    models: dict[str, ScaleModel]


def _c_clip_count(c: FloatArray) -> int:
    return int(((c <= K.SCALE_C_MIN + 1e-12) | (c >= K.SCALE_C_MAX - 1e-12)).sum())


def fit_scale_models(
    ridge: ridge_models.RidgeFit, scale_fit: ObsCohort, scale_cal: ObsCohort
) -> FrozenScale:
    """Fit all three models on SCALE_FIT; calibrate one RMS scale per lift on SCALE_CAL."""
    require_role(scale_fit, FIT_ROLE)
    require_role(scale_cal, CAL_ROLE)
    if set(scale_fit.row_ids) & set(scale_cal.row_ids):
        raise ValueError("SCALE_FIT and SCALE_CAL share row identifiers")
    mu_fit, y_fit = ridge_mu(ridge, scale_fit), scale_fit.truth.open().y
    mu_cal, y_cal = ridge_mu(ridge, scale_cal), scale_cal.truth.open().y
    models: dict[str, ScaleModel] = {}
    for name in K.MODELS:
        if name == "B_GROUP":
            group = group_rms(scale_fit.stratum, mu_fit, y_fit)
            raw_cal = group[scale_cal.stratum]
            c = fit_scale_c(raw_cal, mu_cal, y_cal)
            models[name] = ScaleModel(name, None, group, c, _c_clip_count(c))
        else:
            head = fit_head(name, scale_fit.base_features, scale_fit.stratum, mu_fit, y_fit)
            partial = ScaleModel(name, head, None, np.ones(3), 0)
            raw_cal = partial.sigma_raw(scale_cal.base_features, scale_cal.stratum, mu_cal)
            c = fit_scale_c(raw_cal, mu_cal, y_cal)
            models[name] = ScaleModel(name, head, None, c, _c_clip_count(c))
    return FrozenScale(ridge, models)


def predict_arms(
    frozen: FrozenScale, cohort: ObsCohort
) -> dict[str, tuple[FloatArray, FloatArray]]:
    """model -> (mu, sigma_final). No truncation exists on this path."""
    from ..observable import contract as observable_contract

    observable_contract.check_target_compatibility(K.OBSERVED_TARGET_KIND, "cessation")
    mu = ridge_mu(frozen.ridge, cohort)
    return {
        name: (mu, m.sigma(cohort.base_features, cohort.stratum, mu))
        for name, m in frozen.models.items()
    }


def array_digest(*arrays: FloatArray) -> str:
    return ref.array_digest(*arrays)
