"""Gaussian and upper-truncated Gaussian predictive distributions for latent capacity change.

All functions take float64 arrays of location ``mu``, scale ``sigma`` and observation ``y`` in kg.
Truncation conditions a Gaussian on ``y <= 0``. It is valid only for the simulated latent
capacity *change* under a zero-dose (cessation) plan, where the source law makes adaptation decay
monotonically (``C`` cannot increase). It is not valid for observed performance.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
import torch

FloatArray = npt.NDArray[np.float64]
LATENT_CAPACITY_CHANGE = "latent_capacity_change_kg"
SIGMA_MIN_KG = 0.25
SIGMA_MAX_KG = 100.0
_HALF_LOG_2PI = 0.5 * math.log(2.0 * math.pi)
_INV_SQRT_PI = 1.0 / math.sqrt(math.pi)


def _t(value: npt.ArrayLike) -> torch.Tensor:
    return torch.as_tensor(np.array(value, dtype=np.float64))


def _check(mu: torch.Tensor, sigma: torch.Tensor, y: torch.Tensor | None = None) -> None:
    if not bool(torch.isfinite(mu).all()) or not bool(torch.isfinite(sigma).all()):
        raise ValueError("location and scale must be finite")
    if bool((sigma <= 0).any()):
        raise ValueError("scale must be positive")
    if y is not None and not bool(torch.isfinite(y).all()):
        raise ValueError("observations must be finite")


def require_support_target(target_kind: str, plan_id: str) -> bool:
    """Return whether truncation applies; reject any target other than latent capacity change."""
    if target_kind != LATENT_CAPACITY_CHANGE:
        raise ValueError(
            "upper truncation at zero is defined only for simulated latent capacity change, "
            f"not {target_kind!r}"
        )
    return plan_id == "cessation"


def clip_sigma(sigma: npt.ArrayLike) -> FloatArray:
    return np.clip(np.asarray(sigma, dtype=np.float64), SIGMA_MIN_KG, SIGMA_MAX_KG)


def gaussian_crps(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    z = (o - m) / s
    out = s * (z * (2 * torch.special.ndtr(z) - 1) + 2 * _pdf(z) - _INV_SQRT_PI)
    return np.asarray(out.numpy(), dtype=np.float64)


def gaussian_nll(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    z = (o - m) / s
    return np.asarray((torch.log(s) + _HALF_LOG_2PI + 0.5 * z * z).numpy(), dtype=np.float64)


def _pdf(z: torch.Tensor) -> torch.Tensor:
    return torch.exp(-0.5 * z * z - _HALF_LOG_2PI)


def _log_pdf(z: torch.Tensor) -> torch.Tensor:
    return -0.5 * z * z - _HALF_LOG_2PI


def _require_nonpositive(o: torch.Tensor) -> None:
    if bool((o > 0).any()):
        raise ValueError("observation violates the upper-truncated support y <= 0")


def truncated_crps(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    """CRPS of N(mu, sigma^2) conditioned on y <= 0, computed with log-CDF terms."""
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    _require_nonpositive(o)
    z = (o - m) / s
    a = -m / s
    log_z = torch.special.log_ndtr(a)
    cdf = torch.exp(torch.special.log_ndtr(z) - log_z)
    tail = torch.exp(torch.special.log_ndtr(math.sqrt(2.0) * a) - 2.0 * log_z) * _INV_SQRT_PI
    out = s * (z * (2 * cdf - 1) + 2 * torch.exp(_log_pdf(z) - log_z) - tail)
    return np.asarray(out.numpy(), dtype=np.float64)


def truncated_nll(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    _require_nonpositive(o)
    z = (o - m) / s
    log_z = torch.special.log_ndtr(-m / s)
    return np.asarray(
        (torch.log(s) + _HALF_LOG_2PI + 0.5 * z * z + log_z).numpy(), dtype=np.float64
    )


def truncated_mean(mu: npt.ArrayLike, sigma: npt.ArrayLike) -> FloatArray:
    """Mean of the truncated law; the location ``mu`` is not this mean."""
    m, s = _t(mu), _t(sigma)
    _check(m, s)
    a = -m / s
    return np.asarray(
        (m - s * torch.exp(_log_pdf(a) - torch.special.log_ndtr(a))).numpy(), dtype=np.float64
    )


def gaussian_cdf(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    return np.asarray(torch.special.ndtr((o - m) / s).numpy(), dtype=np.float64)


def truncated_cdf(mu: npt.ArrayLike, sigma: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    """F(y) = Phi((y-mu)/sigma) / Phi(-mu/sigma) for y <= 0 and exactly 1 above zero."""
    m, s, o = _t(mu), _t(sigma), _t(y)
    _check(m, s, o)
    z = (o - m) / s
    value = torch.exp(torch.special.log_ndtr(z) - torch.special.log_ndtr(-m / s))
    return np.asarray(torch.where(o > 0, torch.ones_like(value), value).numpy(), dtype=np.float64)


def gaussian_ppf(mu: npt.ArrayLike, sigma: npt.ArrayLike, p: npt.ArrayLike) -> FloatArray:
    m, s, q = _t(mu), _t(sigma), _t(p)
    _check(m, s)
    return np.asarray((m + s * torch.special.ndtri(q)).numpy(), dtype=np.float64)


def truncated_ppf(mu: npt.ArrayLike, sigma: npt.ArrayLike, p: npt.ArrayLike) -> FloatArray:
    """Quantile mu + sigma * Phi^-1(p * Phi(-mu/sigma)), solved in log space for stability.

    Newton iterations on ``log Phi(x) = log p + log Phi(a)`` avoid underflow when Phi(a) is tiny.
    """
    m, s, q = torch.broadcast_tensors(_t(mu), _t(sigma), _t(p))  # type: ignore[no-untyped-call]
    _check(m, s)
    if bool(((q <= 0) | (q >= 1)).any()):
        raise ValueError("probabilities must lie strictly between 0 and 1")
    a = -m / s
    target = torch.log(q) + torch.special.log_ndtr(a)
    x = torch.minimum(a, torch.special.ndtri(torch.exp(target).clamp_min(1e-300)))
    for _ in range(100):
        log_cdf = torch.special.log_ndtr(x)
        step = (log_cdf - target) / torch.exp(_log_pdf(x) - log_cdf)
        x = x - step
        if float(step.abs().max()) < 1e-13:
            break
    return np.asarray((m + s * x).numpy(), dtype=np.float64)


def central_interval(
    mu: npt.ArrayLike, sigma: npt.ArrayLike, level: float, *, truncated: npt.ArrayLike
) -> tuple[FloatArray, FloatArray]:
    """Central ``level`` interval; ``truncated`` may be a bool or a per-row boolean mask."""
    if not 0.0 < level < 1.0:
        raise ValueError("interval level must lie strictly between 0 and 1")
    lo_p, hi_p = (1.0 - level) / 2.0, 1.0 - (1.0 - level) / 2.0
    m = np.asarray(mu, dtype=np.float64)
    s = np.asarray(sigma, dtype=np.float64)
    mask = np.broadcast_to(np.asarray(truncated, dtype=bool), m.shape)
    lo = gaussian_ppf(m, s, lo_p)
    hi = gaussian_ppf(m, s, hi_p)
    if mask.any():
        lo = np.where(mask, truncated_ppf(m, s, lo_p), lo)
        hi = np.where(mask, truncated_ppf(m, s, hi_p), hi)
    return lo, hi


def positive_mass(mu: npt.ArrayLike, sigma: npt.ArrayLike) -> FloatArray:
    """Gaussian probability of y > 0; zero by construction for the truncated law."""
    m, s = _t(mu), _t(sigma)
    _check(m, s)
    return np.asarray(torch.special.ndtr(m / s).numpy(), dtype=np.float64)


def central_coverage_and_width(
    mu: FloatArray,
    sigma: FloatArray,
    y: FloatArray,
    truncated: npt.ArrayLike,
    levels: Sequence[float],
) -> dict[float, tuple[FloatArray, FloatArray]]:
    """Per-row inclusion (0/1) and width for every central level."""
    out: dict[float, tuple[FloatArray, FloatArray]] = {}
    for level in levels:
        lo, hi = central_interval(mu, sigma, level, truncated=truncated)
        out[level] = (((y >= lo) & (y <= hi)).astype(np.float64), hi - lo)
    return out
