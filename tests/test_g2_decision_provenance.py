"""RES-617: the G2 decision memo, provenance record and public-evidence citations must agree."""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMO = (ROOT / "docs/studies/g2-identifiability-decision.md").read_text(encoding="utf-8")
PROVENANCE = (ROOT / "provenance/RES-617-g2-evidence-provenance.md").read_text(encoding="utf-8")
RES289 = ROOT / "results/studies/target_sufficient_structural_reconstruction"
FULL = "5f5d3fefc21aae9fb362b2d0fc3b1df441ed8ca69160fcd88745aa07fd678c67"
SHORT = "5f5d3fefc21aae9fb362b2d0fc3b1df441ed8ca69160fcd88745aa07cdc7"
DISPOSITIONS = (
    "REDUCED_QUANTITIES_SUPPORTED",
    "SET_VALUED_SENSITIVITY_ONLY",
    "FULL_G2_IDENTIFICATION_UNSUPPORTED",
)


def test_exactly_one_disposition_is_selected_and_it_is_the_negative_one() -> None:
    assert "**`FULL_G2_IDENTIFICATION_UNSUPPORTED`**" in MEMO
    headline = MEMO.split("## 1. Definitions used")[0]
    assert [d for d in DISPOSITIONS if f"`{d}`" in headline] == [
        "FULL_G2_IDENTIFICATION_UNSUPPORTED"
    ]
    section = MEMO.split("## 6. Final disposition")[1].split("## 7.")[0]
    assert "`REDUCED_QUANTITIES_SUPPORTED` is not chosen" in section
    assert "`SET_VALUED_SENSITIVITY_ONLY` is not chosen" in section


def test_pointer_discrepancy_is_recorded_with_the_full_verified_digest() -> None:
    assert re.fullmatch(r"[0-9a-f]{64}", FULL) and re.fullmatch(r"[0-9a-f]{60}", SHORT)
    assert FULL[:56] == SHORT[:56] and FULL[56:] == "fd678c67" and SHORT[56:] == "cdc7"
    for text in (PROVENANCE,):
        assert FULL in text and SHORT in text
    assert FULL in PROVENANCE.split("## Linear pointer discrepancy")[0]
    assert "left unedited" in PROVENANCE and "60 hexadecimal characters" in PROVENANCE
    for digest in re.findall(r"`([0-9a-f]{64})`", PROVENANCE):
        assert len(digest) == 64


def test_all_cited_evidence_identities_are_present() -> None:
    for token in (
        "334 members, 0 mismatches",
        "36 members, 0 mismatches",
        "674 members, 0 mismatches",
        "90fd1b3549f20799d6fb1fc2176cb5472026b19458cb86dd26d737e296c13232",
        "82503f22e9d9aa7069b40a7bb5ce91180ecbbfc9810aba5bdfc76f0dab1b3bb5",
        "ce80188fc908e3d715a1996c0064520133d32913aa449dd3a5243e4cb1dffb63",
        "psr:study:target-sufficient-structural-reconstruction-public-native@1.0.0~12aafcbac716",
    ):
        assert token in PROVENANCE
    assert "No optimizer, fit, profile, simulation, cohort or model call was run" in PROVENANCE
    assert "/home/" not in MEMO + PROVENANCE and "/tmp/" not in MEMO + PROVENANCE


def test_target_table_covers_every_requested_target_with_a_class() -> None:
    table = MEMO.split("## 3. Target-by-target assessment")[1].split("## 4.")[0]
    rows = [line for line in table.splitlines() if line.startswith("| ") and "---" not in line][1:]
    assert len(rows) == 7
    labels = [row.split("|")[1].strip() for row in rows]
    for needle in (
        "adaptation",
        "suppression",
        "time constants",
        "expressed-performance",
        "forecasts",
        "Reduced",
        "Set-valued",
    ):
        assert any(needle in label for label in labels), needle
    classes = [re.search(r"\*\*([SPLU])\*\*", row.split("|")[-2]) for row in rows]
    assert all(classes) and [m.group(1) for m in classes if m] == [
        "U",
        "U",
        "U",
        "P",
        "U",
        "U",
        "U",
    ]
    assert "Optimizer success is not identifiability" in MEMO


def test_public_res289_numbers_cited_in_the_memo_match_the_repository_results() -> None:
    identifiability = json.loads((RES289 / "identifiability.json").read_text())
    conditions = [
        r["condition_number_full_rank_only"]
        for r in identifiability["canonical_template_rank_summary"]
    ]
    assert all(r["rank"] == 16 for r in identifiability["canonical_template_rank_summary"])
    assert (round(min(conditions)), round(max(conditions))) == (952, 1119)
    report = (RES289 / "report.md").read_text()
    assert "| full_bounded_native_mle_v1 | none | 1.0 | 7 | 249 |" in report
    assert "| full_bounded_native_mle_v1 | none | 2.0 | 22 | 234 |" in report
    assert "EXACT_COUNTEREXAMPLE_OUTSIDE_CANONICAL_TEMPLATES" in report and "INCONCLUSIVE" in report
    with (RES289 / "parameter-results.csv").open(newline="") as handle:
        params = {
            (r["estimator_id"][:13], r["prior"], r["parameter"]): float(r["rmse"])
            for r in csv.DictReader(handle)
            if r["noise_scale"] == "1.0" and r["n_scored"] == "32"
        }
    mle = "full_bounded_"
    assert round(params[(mle, "none", "coordinate.squat_adaptation_utilization")], 2) == 0.34
    assert round(params[(mle, "none", "coordinate.squat_adaptation_retention_28d")], 2) == 0.30
    assert round(params[(mle, "none", "coordinate.squat_suppression_utilization")], 2) == 0.39
    assert round(params[(mle, "none", "coordinate.squat_suppression_retention")], 2) == 0.40
    assert round(params[(mle, "none", "squat.adaptation_time_days")], 1) == 48.9
    assert round(params[("bayesian_nati", "beta8", "squat.adaptation_time_days")], 1) == 29.0
    with (RES289 / "target-results.csv").open(newline="") as handle:
        targets = {
            (r["estimator_id"][:13], r["target"]): float(r["rmse"])
            for r in csv.DictReader(handle)
            if r["noise_scale"] == "1.0"
            and r["lift"] == "squat"
            and r["prior"] in ("none", "beta8")
            and r["n_scored"] == "32"
        }
    assert (
        round(targets[(mle, "P_223_kg")], 1) == 2.9
        and round(targets[("bayesian_nati", "P_223_kg")], 1) == 4.0
    )
    reduced = next(
        float(r["rmse"])
        for r in csv.DictReader((RES289 / "target-results.csv").open(newline=""))
        if r["estimator_id"].startswith("reduced")
        and r["target"] == "P_223_kg"
        and r["noise_scale"] == "1.0"
        and r["lift"] == "squat"
    )
    assert round(reduced, 1) == 11.5
    assert abs((1 / 12) ** 0.5 - 0.289) < 5e-4  # standard deviation of Uniform[0,1]
    assert (
        round(-28 / __import__("math").log(0.85)) == 172
        and round(-28 / __import__("math").log(0.10)) == 12
    )
