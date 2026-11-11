"""Independent read-only Ridge preflight (RES-616 historical roles only; no RES-639 data)."""

import json
import time

import numpy as np

from powerlifting_state_research.history_uncertainty import contract as K
from powerlifting_state_research.history_uncertainty import replay as R
from powerlifting_state_research.observable import contract as C
from powerlifting_state_research.observable import data as D
from powerlifting_state_research.observable import models as M
from powerlifting_state_research.probabilistic import reference as ref
from powerlifting_state_research.probabilistic import scoring

t0 = time.process_time()
fit = D.build_cohorts("FIT", C.ROLE_ROWS["FIT"], C.ROLE_BASE["FIT"])["CONTROL"]
dev = D.build_cohorts("DEV", C.ROLE_ROWS["DEV"], C.ROLE_BASE["DEV"])["CONTROL"]
ridge, scores = M.fit_ridge(fit, dev)
out = {"cpu_generate_fit": round(time.process_time() - t0, 2)}
ref_ = K.RIDGE_REFERENCE
out["alpha"] = ridge.alpha
out["beta_sha256"] = ref.array_digest(ridge.beta)
out["tier1_exact_digest_match"] = out["beta_sha256"] == ref_["beta_sha256"]
out["sign_normalized"] = R.sign_normalized_digest(ridge.beta)
out["dev_rmse_max_abs_diff"] = max(
    abs(scores[a] - ref_["dev_rmse_by_alpha"][a]) for a in ref_["dev_rmse_by_alpha"]
)
out["row_id_match"] = {
    r: R.hashlib.sha256("\n".join(c.row_ids).encode()).hexdigest()
    == ref_["cohort_row_id_sha256"][r]
    for r, c in (("FIT", fit), ("DEV", dev))
}
# independent solve: normal equations on the same standardized design
y = fit.truth.open().y - fit.last_assessment
worst_beta = 0
worst_pred = 0
zero_cols = []
for lift in range(3):
    X = M.ridge_design(fit.base_features, fit.stratum, lift)
    n = len(X)
    mean = X.mean(0)
    sd = np.maximum(X.std(0), 1e-6)
    Z = (X - mean) / sd
    assert np.allclose(mean, ridge.mean[lift]) and np.allclose(
        sd, ridge.sd[lift]
    )  # feature alignment
    t = y[:, lift] - y[:, lift].mean()
    b = np.linalg.solve(Z.T @ Z / n + ridge.alpha * np.eye(Z.shape[1]), Z.T @ t / n)
    worst_beta = max(worst_beta, float(np.abs(b - ridge.beta[lift]).max()))
    Zd = (M.ridge_design(dev.base_features, dev.stratum, lift) - mean) / sd
    p1 = ridge.intercept[lift] + Zd @ ridge.beta[lift]
    p2 = y[:, lift].mean() + Zd @ b
    worst_pred = max(worst_pred, float(np.abs(p1 - p2).max()))
    zero_cols.append(int((sd <= 1e-6 + 1e-12).sum()))
out["max_abs_beta_diff_lstsq_vs_normal_eq"] = worst_beta
out["max_abs_dev_prediction_diff_kg"] = worst_pred
out["degenerate_columns_per_lift"] = zero_cols
out["n_beta_abs_lt_1e-12"] = int((np.abs(ridge.beta) < 1e-12).sum())
# prediction-level aggregate check against published RES-616 M1_C TEST_A CONTROL macro CRPS
cal = D.build_cohorts("CAL_C", C.ROLE_ROWS["CAL_C"], C.ROLE_BASE["CAL_C"])["CONTROL"]
ta = D.build_cohorts("TEST_A", C.ROLE_ROWS["TEST_A"], C.ROLE_BASE["TEST_A"])["CONTROL"]
mu = lambda c: c.last_assessment + M.ridge_predict_delta(ridge, c)
raw = ref.fit_b1(dev.stratum, mu(dev), dev.truth.open().y)
cc = ref.fit_scale_c(raw[cal.stratum], mu(cal), cal.truth.open().y)
sig = scoring.clip_sigma(cc * raw[ta.stratum])
yt = ta.truth.open().y
crps = float(scoring.gaussian_crps(mu(ta), sig, yt).mean())
out["replayed_M1_C_TEST_A_CONTROL_macro_crps"] = round(crps, 9)
import csv

pub = [
    r
    for r in csv.DictReader(open("results/studies/observable_strength_forecasting/full/scores.csv"))
    if (r["parent"], r["scenario"], r["arm"], r["lift"]) == ("TEST_A", "CONTROL", "M1_C", "macro")
][0]
out["published_M1_C_TEST_A_CONTROL_macro_crps"] = float(pub["crps"])
out["abs_diff_vs_published"] = abs(round(crps, 9) - float(pub["crps"]))
out["cpu_total"] = round(time.process_time() - t0, 2)
print(json.dumps(out, indent=1))
