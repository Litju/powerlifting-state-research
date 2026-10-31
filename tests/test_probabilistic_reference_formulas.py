"""Reference mathematics only: these tests do not import private study implementations."""

import math

import pytest
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm, truncnorm


@pytest.mark.parametrize("mu", [-5.0, 0.0, 4.0])
@pytest.mark.parametrize("sigma", [0.25, 1.0, 3.0])
@pytest.mark.parametrize("truncated", [False, True])
def test_reference_scores_against_cdf_integrals(mu: float, sigma: float, truncated: bool) -> None:
    y = min(mu - sigma / 2, -0.1) if truncated else mu - sigma / 2
    z = (y - mu) / sigma
    a = -mu / sigma
    distribution = truncnorm(-math.inf, a, loc=mu, scale=sigma) if truncated else norm(mu, sigma)
    if truncated:
        log_z = float(log_ndtr(a))
        crps = sigma * (
            z * (2 * math.exp(float(log_ndtr(z)) - log_z) - 1)
            + 2 * math.exp(float(norm.logpdf(z)) - log_z)
            - math.exp(float(log_ndtr(math.sqrt(2) * a)) - 2 * log_z) / math.sqrt(math.pi)
        )
        nll = math.log(sigma) + math.log(2 * math.pi) / 2 + z * z / 2 + log_z
        assert distribution.sf(0) == 0
        assert distribution.mean() == pytest.approx(
            mu - sigma * math.exp(float(norm.logpdf(a)) - log_z)
        )
    else:
        crps = sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi))
        nll = math.log(sigma) + math.log(2 * math.pi) / 2 + z * z / 2
    integral = quad(lambda t: distribution.cdf(t) ** 2, -math.inf, y)[0]
    integral += quad(lambda t: distribution.sf(t) ** 2, y, 0 if truncated else math.inf)[0]
    assert crps == pytest.approx(integral, abs=1e-10)
    assert nll == pytest.approx(-distribution.logpdf(y), abs=1e-10)
