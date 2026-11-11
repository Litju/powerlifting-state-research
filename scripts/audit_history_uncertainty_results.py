"""Independent read-only audit of RES-639 saved outputs (reimplements the frozen rules)."""

import csv
import hashlib
import json
import sys
from collections import defaultdict

D = sys.argv[1]
P = json.load(open(sys.argv[2]))["protocol"]
G = P["guardrails"]
rd = lambda n: list(csv.DictReader(open(f"{D}/{n}")))
out = {}
fails = []


def chk(name, ok):
    out[name] = bool(ok)
    if not ok:
        fails.append(name)


# 1 hashes / seal chain
man = json.load(open(f"{D}/manifest.json"))
for n, h in man["output_sha256"].items():
    chk("sha:" + n, hashlib.sha256(open(f"{D}/{n}", "rb").read()).hexdigest() == h)
fz = hashlib.sha256(open(f"{D}/frozen-parameters.json", "rb").read()).hexdigest()
chk(
    "freeze_seal",
    json.load(open(f"{D}/freeze-seal.json"))["frozen_parameters_sha256"]
    == fz
    == man["frozen_parameters_sha256"],
)
ps = json.load(open(f"{D}/prediction-seal.json"))
chk(
    "pred_seal",
    ps["prediction_seal_sha256"] == man["prediction_seal_sha256"]
    and ps["frozen_parameters_sha256"] == fz
    and ps["test_truth_opened"] is False,
)
chk("protocol_digest", man["protocol_digest"] == json.load(open(sys.argv[2]))["protocol_digest"])
# 2 denominators / integrity
for r in rd("integrity.csv"):
    chk(
        f"integ:{r['parent']}:{r['scenario']}",
        r["rows_expected"] == r["rows_scored"] == "3072" and r["nonfinite_predictions"] == "0",
    )
sc = defaultdict(dict)
for r in rd("scores.csv"):
    sc[(r["parent"], r["scenario"], r["model"])][r["lift"]] = r
chk(
    "scores_rows",
    len(rd("scores.csv")) == 2 * 3 * 3 * 4 and all(r["n"] == "3072" for r in rd("scores.csv")),
)
for k, v in sc.items():  # macro = mean of lifts
    for m in ("crps", "nll", "cov90", "width90"):
        chk(
            f"macro:{k}:{m}",
            abs(
                sum(float(v[l][m]) for l in ("squat", "bench_press", "deadlift")) / 3
                - float(v["macro"][m])
            )
            < 2e-9,
        )
for r in rd("pit.csv"):
    pass
pit = defaultdict(int)
for r in rd("pit.csv"):
    pit[(r["parent"], r["scenario"], r["model"])] += int(r["count"])
chk("pit_denominators", all(v == 3 * 3072 for v in pit.values()) and len(pit) == 18)
# 3 primary + contrasts recomputed from scores.csv
M = lambda p, s, m, k: float(sc[(p, s, m)]["macro"][k])
con = {}
for r in rd("paired_contrasts.csv"):
    a, b = r["contrast"].split("-")
    d = M(r["parent"], r["scenario"], a, r["metric"]) - M(
        r["parent"], r["scenario"], b, r["metric"]
    )
    chk(
        f"contrast:{r['parent']}:{r['scenario']}:{r['contrast']}:{r['metric']}",
        abs(d - float(r["diff"])) < 3e-9
        and abs(100 * d / M(r["parent"], r["scenario"], b, r["metric"]) - float(r["rel_pct"]))
        < 1e-6
        and float(r["ci_lo"]) <= float(r["diff"]) <= float(r["ci_hi"]),
    )
    con[(r["parent"], r["scenario"], r["contrast"], r["metric"])] = r
# 4 independent decision
gc = defaultdict(dict)
sev = defaultdict(int)
lo, hi = G["severe_subgroup_coverage90_band"]
for r in rd("group_calibration.csv"):
    if (
        r["model"] == "H_HISTORY"
        and r["scenario"] == "CONTROL"
        and not (lo <= float(r["cov90"]) <= hi)
    ):
        sev[r["parent"]] += 1
bins = defaultdict(list)
for r in rd("conditional_coverage.csv"):
    if r["model"] == "H_HISTORY" and r["scenario"] == "CONTROL":
        bins[r["parent"]].append(float(r["cov90"]))
inb = lambda v, b: b[0] <= v <= b[1]
checks = {}
screen = {}
for p in ("TEST_A", "TEST_B"):
    pr = con[(p, "CONTROL", "H_HISTORY-B_MAG", "crps")]
    screen[p] = (
        float(pr["rel_pct"]) <= -G["primary_relative_improvement_pct"]
        and float(pr["ci_hi"]) < G["primary_ci_upper_bound"]
    )
    h, b, g = (lambda m: m)("H_HISTORY"), "B_MAG", "B_GROUP"
    checks[f"{p}:beats_B_GROUP"] = M(p, "CONTROL", h, "crps") < M(p, "CONTROL", g, "crps")
    checks[f"{p}:nll"] = (
        M(p, "CONTROL", h, "nll") - M(p, "CONTROL", b, "nll") <= G["nll_deterioration_max_nats"]
    )
    checks[f"{p}:coverage90"] = inb(M(p, "CONTROL", h, "cov90"), G["coverage90_band"])
    checks[f"{p}:coverage90_per_lift"] = all(
        inb(float(sc[(p, "CONTROL", h)][l]["cov90"]), G["coverage90_per_lift_band"])
        for l in ("squat", "bench_press", "deadlift")
    )
    checks[f"{p}:severe_subgroup"] = sev[p] <= G["severe_subgroup_cells_allowed"]
    checks[f"{p}:scale_conditional"] = len(bins[p]) == 15 and all(
        inb(v, G["conditional_scale_bin_coverage90_band"]) for v in bins[p]
    )
    checks[f"{p}:width"] = M(p, "CONTROL", h, "width90") <= G[
        "width90_ratio_max_vs_comparator"
    ] * M(p, "CONTROL", b, "width90")
    for s in ("VELOCITY_NOISE_SHIFT", "ADAPTATION_TIMESCALE_SHIFT"):
        checks[f"{p}:{s}:no_crps_reversal"] = M(p, s, h, "crps") <= M(p, s, b, "crps")
        checks[f"{p}:{s}:coverage90"] = inb(M(p, s, h, "cov90"), G["shift_pooled_coverage90_band"])
disp = (
    "MIXED_OR_NOT_QUALIFIED"
    if not all(screen.values())
    else "HISTORY_UNCERTAINTY_QUALIFIED_WITHIN_SYNTHETIC_WORLD"
    if all(checks.values())
    else "SCORE_GAIN_ONLY_CONDITIONAL_RELIABILITY_UNSUPPORTED"
)
summ = json.load(open(f"{D}/summary.json"))
chk("disposition_agrees", disp == summ["disposition"] == man["disposition"])
chk(
    "guardrails_agree",
    checks == summ["criteria"]["guardrails"] and screen == summ["criteria"]["screen"],
)
out["independent_disposition"] = disp
out["independent_screen"] = screen
out["independent_guardrails_failed"] = [k for k, v in checks.items() if not v]
out["severe_cells_H_control"] = dict(sev)
out["failed_audit_checks"] = fails
out["n_checks"] = len([k for k in out if isinstance(out[k], bool)])
print(json.dumps(out, indent=1))
