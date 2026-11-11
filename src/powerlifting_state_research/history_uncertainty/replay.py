"""Bounded Ridge-only replay of the RES-616 location model, verified against published identities.

Only the Ridge (M1) is reconstructed, from the public RES-616 FIT and DEV seeds. The GRU is neither
trained nor loaded. A mismatch is a blocker; no substitute Ridge is ever returned.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..observable import contract as base
from ..observable import data as observable_data
from ..observable import models as ridge_models
from ..probabilistic import reference as ref
from . import contract as K


class RidgeIdentityError(RuntimeError):
    """The replayed Ridge does not match the published RES-616 identity."""


@dataclass(frozen=True)
class RidgeReplay:
    ridge: ridge_models.RidgeFit
    beta_sha256: str
    beta_sign_normalized_sha256: str
    dev_rmse_by_alpha: dict[str, float]
    row_id_sha256: dict[str, str]
    profile: str


def reference_for(profile: str, root: Path) -> dict[str, Any]:
    """Published identity: the full RES-616 reference, or the committed RES-616 smoke record."""
    if profile == "full":
        return dict(K.RIDGE_REFERENCE)
    record = json.loads((root / K.SMOKE_RIDGE_REFERENCE_PATH).read_text(encoding="utf-8"))
    return {
        "alpha": record["ridge"]["alpha"],
        "beta_sha256": record["ridge"]["beta_sha256"],
        "dev_rmse_by_alpha": record["ridge"]["dev_rmse_by_alpha"],
        "cohort_row_id_sha256": {r: record["cohort_row_id_sha256"][r] for r in ("FIT", "DEV")},
        "dev_rmse_cross_environment_tolerance_kg": K.RIDGE_REFERENCE[
            "dev_rmse_cross_environment_tolerance_kg"
        ],
    }


def sign_normalized_digest(beta: Any) -> str:
    """Digest that ignores the sign of coefficients that round to zero at 9 decimals.

    The published digest hashes ``round(beta, 9)`` bytes, so the sign of the many (exactly
    degenerate-column) near-zero coefficients changes it when BLAS thread settings change. This
    companion digest is invariant to that and is recorded alongside the published one.
    """
    rounded = np.round(np.asarray(beta, dtype=np.float64), 9)
    return ref.array_digest(np.where(rounded == 0.0, 0.0, rounded))


def replay_ridge(profile: str) -> RidgeReplay:
    """Regenerate RES-616 FIT and DEV with their published seeds and refit the Ridge."""
    smoke = profile == "smoke"
    rows = base.SMOKE_ROLE_ROWS if smoke else base.ROLE_ROWS
    bases = base.SMOKE_ROLE_BASE if smoke else base.ROLE_BASE
    cohorts = {
        r: observable_data.build_cohorts(r, rows[r], bases[r])["CONTROL"] for r in ("FIT", "DEV")
    }
    ridge, scores = ridge_models.fit_ridge(cohorts["FIT"], cohorts["DEV"])
    return RidgeReplay(
        ridge,
        ref.array_digest(ridge.beta),
        sign_normalized_digest(ridge.beta),
        scores,
        {r: hashlib.sha256("\n".join(c.row_ids).encode()).hexdigest() for r, c in cohorts.items()},
        profile,
    )


def verify_replay(
    replay: RidgeReplay, reference: dict[str, Any], *, cross_environment: bool = False
) -> dict[str, Any]:
    """Raise ``RidgeIdentityError`` unless the replay matches the published identity.

    Strict mode (default) demands the exact beta SHA-256. ``cross_environment`` additionally
    accepts a matching alpha and DEV RMSE for every alpha within the declared tolerance, and
    records that the digest was not matched.
    """
    if replay.row_id_sha256 != reference["cohort_row_id_sha256"]:
        raise RidgeIdentityError("replayed FIT/DEV row identifiers differ from RES-616")
    if replay.ridge.alpha != reference["alpha"]:
        raise RidgeIdentityError(f"selected alpha {replay.ridge.alpha} != {reference['alpha']}")
    tolerance = reference["dev_rmse_cross_environment_tolerance_kg"]
    worst = max(
        abs(replay.dev_rmse_by_alpha[a] - reference["dev_rmse_by_alpha"][a])
        for a in reference["dev_rmse_by_alpha"]
    )
    digest_matched = replay.beta_sha256 == reference["beta_sha256"]
    if not digest_matched and not (
        cross_environment and bool(np.isfinite(worst)) and worst <= tolerance
    ):
        raise RidgeIdentityError(
            "ridge coefficient digest differs from the published RES-616 identity "
            f"(max DEV RMSE difference {worst:.3e} kg); no substitute Ridge is permitted"
        )
    return {
        "beta_digest_matched": digest_matched,
        "max_dev_rmse_abs_difference_kg": worst,
        "alpha": replay.ridge.alpha,
        "beta_sha256": replay.beta_sha256,
        "beta_sign_normalized_sha256": replay.beta_sign_normalized_sha256,
        "cross_environment_path_used": bool(cross_environment and not digest_matched),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": f"{platform.system()} {platform.machine()}",
        },
    }
