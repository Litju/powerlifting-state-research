"""Numerical checks of the Gaussian and upper-truncated predictive scores against scipy."""

import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import norm, truncnorm

from powerlifting_state_research.probabilistic import scoring as S

MUS = [-12.0, -5.0, -0.3, 0.0, 0.7, 4.0]
SIGMAS = [0.25, 1.0, 3.0, 20.0]


def _law(mu: float, sigma: float, truncated: bool):  # type: ignore[no-untyped-def]
    return truncnorm(-math.inf, -mu / sigma, loc=mu, scale=sigma) if truncated else norm(mu, sigma)


def test_hand_computed_constants() -> None:
    assert S.gaussian_crps(0.0, 1.0, 0.0) == pytest.approx(0.2336949773, abs=1e-10)
    assert S.gaussian_nll(0.0, 1.0, 0.0) == pytest.approx(0.9189385332, abs=1e-10)
    # a = 0 gives Z = 1/2: CRPS = 4 phi(0) - 4 Phi(0)/sqrt(pi) at y = 0, NLL = Gaussian + log(1/2)
    assert S.truncated_crps(0.0, 1.0, 0.0) == pytest.approx(0.4673899545, abs=1e-10)
    assert S.truncated_nll(0.0, 1.0, 0.0) == pytest.approx(0.9189385332 + math.log(0.5), abs=1e-9)


@pytest.mark.parametrize("truncated", [False, True])
@pytest.mark.parametrize("mu", MUS)
@pytest.mark.parametrize("sigma", SIGMAS)
def test_scores_match_cdf_integral_and_logpdf(mu: float, sigma: float, truncated: bool) -> None:
    law = _law(mu, sigma, truncated)
    y = min(mu - sigma / 2, -0.05)
    upper = 0.0 if truncated else math.inf
    integral = quad(lambda t: law.cdf(t) ** 2, -math.inf, y, limit=200)[0]
    integral += quad(lambda t: law.sf(t) ** 2, y, upper, limit=200)[0]
    crps = (S.truncated_crps if truncated else S.gaussian_crps)(mu, sigma, y)
    nll = (S.truncated_nll if truncated else S.gaussian_nll)(mu, sigma, y)
    assert float(crps) == pytest.approx(integral, abs=1e-9)
    assert float(nll) == pytest.approx(-law.logpdf(y), abs=1e-9)


@pytest.mark.parametrize("truncated", [False, True])
def test_cdf_ppf_round_trip_and_reference(truncated: bool) -> None:
    mu = np.array(MUS * 2)
    sigma = np.array([0.25, 1.0, 3.0] * 4)
    for p in (0.025, 0.05, 0.25, 0.5, 0.75, 0.95, 0.975):
        ours = (S.truncated_ppf if truncated else S.gaussian_ppf)(mu, sigma, p)
        ref = np.array([_law(m, s, truncated).ppf(p) for m, s in zip(mu, sigma, strict=True)])
        assert np.abs(ours - ref).max() < 1e-10
        cdf = (S.truncated_cdf if truncated else S.gaussian_cdf)(mu, sigma, ours)
        assert np.abs(cdf - p).max() < 1e-10


def test_truncated_support_mass_and_mean() -> None:
    mu = np.array([-5.0, 0.0, 3.0, 40.0])
    sigma = np.array([1.0, 0.5, 2.0, 1.0])
    # exactly no mass above zero; Gaussian places positive mass there
    assert S.truncated_cdf(mu, sigma, np.zeros(4)).tolist() == [1.0] * 4
    assert S.truncated_cdf(mu, sigma, np.array([0.1, 1, 5, 50])).tolist() == [1.0] * 4
    assert (S.positive_mass(mu, sigma) > 0).all()
    ref = np.array(
        [
            truncnorm(-math.inf, -m / s, loc=m, scale=s).mean()
            for m, s in zip(mu, sigma, strict=True)
        ]
    )
    assert np.abs(S.truncated_mean(mu, sigma) - ref).max() < 1e-9
    assert (S.truncated_mean(mu, sigma) < np.minimum(mu, 0.0) + 1e-12).all()
    assert (S.truncated_ppf(mu, sigma, 0.9999) <= 0).all()


def test_extreme_tails_are_finite_and_correct() -> None:
    # mu/sigma = 1600: Phi(-1600) underflows to 0 in float64; the log-space solver must not
    q = S.truncated_ppf(400.0, 0.25, 0.05)
    assert math.isfinite(float(q)) and float(q) < 0
    # exponential-tail limit with rate mu/sigma^2
    assert float(q) == pytest.approx(math.log(0.05) / (400.0 / 0.25**2), rel=1e-3)
    assert math.isfinite(float(S.truncated_crps(400.0, 0.25, -0.001)))
    assert math.isfinite(float(S.truncated_nll(400.0, 0.25, -0.001)))
    assert math.isfinite(float(S.gaussian_crps(0.0, 0.25, 1e4)))


def test_truncation_converges_to_gaussian_far_from_boundary() -> None:
    y = np.array([-9.0, -10.0])
    g = S.gaussian_crps(-10.0, 1.0, y)
    t = S.truncated_crps(-10.0, 1.0, y)
    assert np.abs(g - t).max() < 1e-12


def test_invalid_inputs_fail_safely() -> None:
    for bad_sigma in (0.0, -1.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            S.gaussian_crps(0.0, bad_sigma, 0.0)
    with pytest.raises(ValueError):
        S.gaussian_nll(math.nan, 1.0, 0.0)
    with pytest.raises(ValueError):
        S.gaussian_nll(0.0, 1.0, math.inf)
    with pytest.raises(ValueError, match="support"):
        S.truncated_crps(-1.0, 1.0, 0.5)
    with pytest.raises(ValueError, match="support"):
        S.truncated_nll(-1.0, 1.0, 1e-9)
    with pytest.raises(ValueError):
        S.truncated_ppf(-1.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        S.central_interval(0.0, 1.0, 1.0, truncated=False)


def test_support_rule_only_for_latent_capacity_change_under_cessation() -> None:
    kind = S.LATENT_CAPACITY_CHANGE
    assert S.require_support_target(kind, "cessation") is True
    for plan in ("continue", "step_down", "step_up"):
        assert S.require_support_target(kind, plan) is False
    for incompatible in ("observed_performance_kg", "observed_1rm_kg", ""):
        with pytest.raises(ValueError, match="latent capacity change"):
            S.require_support_target(incompatible, "cessation")


def test_intervals_have_nominal_frequency_under_the_true_law() -> None:
    rng = np.random.default_rng(615)
    n = 40_000
    mu = rng.uniform(-6, 3, n)
    sigma = rng.uniform(0.5, 4, n)
    for truncated in (False, True):
        if truncated:
            y = truncnorm.rvs(-np.inf, -mu / sigma, loc=mu, scale=sigma, random_state=615)
        else:
            y = rng.normal(mu, sigma)
        mask = np.full(n, truncated)
        result = S.central_coverage_and_width(mu, sigma, y, mask, [0.5, 0.8, 0.9])
        for level, (hit, width) in result.items():
            assert abs(hit.mean() - level) < 4 * math.sqrt(level * (1 - level) / n)
            assert (width > 0).all()
    # truncated central intervals are never wider than Gaussian ones and never exceed zero
    lo, hi = S.central_interval(mu, sigma, 0.9, truncated=True)
    glo, ghi = S.central_interval(mu, sigma, 0.9, truncated=False)
    assert (hi <= 0).all() and ((hi - lo) <= (ghi - glo) + 1e-12).all()


def test_proper_score_prefers_the_true_distribution() -> None:
    rng = np.random.default_rng(7)
    y = rng.normal(0.0, 2.0, 50_000)
    true = S.gaussian_crps(0.0, 2.0, y).mean()
    assert true < S.gaussian_crps(0.0, 1.0, y).mean()
    assert true < S.gaussian_crps(0.0, 4.0, y).mean()
    assert S.gaussian_nll(0.0, 2.0, y).mean() < S.gaussian_nll(0.0, 1.0, y).mean()
