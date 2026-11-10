"""Smoke-profile workflow checks: determinism, leakage barriers, fitting formulas, failures."""

import copy
import csv
import json
import math
import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import torch

from powerlifting_state_research.probabilistic import contract as C
from powerlifting_state_research.probabilistic import reference as R
from powerlifting_state_research.probabilistic import scoring as S

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SMOKE = ROOT / R.EXPECTED_RELATIVE / "smoke"


@pytest.fixture(autouse=True)
def pinned_threads(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in R.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")
    previous = torch.get_num_threads()
    yield
    torch.set_num_threads(previous)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    torch.set_num_threads(1)
    import os

    for name in R.THREAD_VARIABLES:
        os.environ[name] = "1"
    first = tmp_path_factory.mktemp("first") / "out"
    second = tmp_path_factory.mktemp("second") / "out"
    R.run("smoke", first)
    R.run("smoke", second)
    return {"first": first, "second": second}


@pytest.fixture(scope="module")
def cohorts() -> dict[str, R.Cohort]:
    torch.set_num_threads(1)
    models, stats, _ = R.load_gru(ROOT)
    return {
        role: R.build_cohort(role, spec, models, stats) for role, spec in C.SMOKE_COHORTS.items()
    }


# ------------------------------------------------------------------ reproducibility


def test_fresh_executions_are_byte_identical(smoke_run: dict[str, Path]) -> None:
    names = sorted(path.name for path in smoke_run["first"].iterdir())
    assert "execution-receipt.json" in names and "manifest.json" in names
    for name in names:
        if name == "execution-receipt.json":  # timings and peak memory differ by design
            continue
        assert (smoke_run["first"] / name).read_bytes() == (smoke_run["second"] / name).read_bytes()


def test_committed_smoke_values_reproduce_within_cross_environment_tolerance(
    smoke_run: dict[str, Path],
) -> None:
    assert EXPECTED_SMOKE.is_dir(), "committed smoke expectation is missing"
    worst = R.compare_to_expected(smoke_run["first"], EXPECTED_SMOKE, same_environment=False)
    assert max(worst.values()) < 5e-3


def test_comparison_rejects_perturbed_scores_and_changed_identity(
    smoke_run: dict[str, Path], tmp_path: Path
) -> None:
    mutated = tmp_path / "mutated"
    mutated.mkdir()
    for path in smoke_run["first"].iterdir():
        (mutated / path.name).write_bytes(path.read_bytes())
    lines = (mutated / "scores.csv").read_text().splitlines()
    cells = lines[1].split(",")
    cells[2] = f"{float(cells[2]) + 0.01:.9f}"
    lines[1] = ",".join(cells)
    (mutated / "scores.csv").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="does not match its manifest hash"):
        R.compare_to_expected(mutated, smoke_run["first"], same_environment=True)
    # a consistent re-hash is still caught by the numerical tolerance
    import hashlib

    manifest = json.loads((mutated / "manifest.json").read_text())
    manifest["output_sha256"]["scores.csv"] = hashlib.sha256(
        (mutated / "scores.csv").read_bytes()
    ).hexdigest()
    (mutated / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="crps_kg differs"):
        R.compare_to_expected(mutated, smoke_run["first"], same_environment=False)
    manifest = json.loads((mutated / "manifest.json").read_text())
    manifest["protocol_digest"] = "sha256:" + "0" * 64
    (mutated / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest identity differs"):
        R.compare_to_expected(mutated, smoke_run["first"], same_environment=False)


def test_outputs_state_identity_target_and_nonclaims(smoke_run: dict[str, Path]) -> None:
    manifest = json.loads((smoke_run["first"] / "manifest.json").read_text())
    assert manifest["reference_id"] == C.REFERENCE_ID
    assert manifest["target"] == S.LATENT_CAPACITY_CHANGE
    assert "NOT a reproduction" in manifest["route"]
    assert (
        manifest["released_asset_sha256"]["seed-383001.pt"]
        == C.GRU_CHECKPOINT_SHA256["seed-383001"]
    )
    assert manifest["cohorts"]["TEST"]["truth_opened_for"] == "scoring"
    assert all(
        manifest["cohorts"][r]["truth_opened_for"] == "fitting" for r in ("FIT", "CAL_C", "CAL_G")
    )
    assert any("historical" in claim for claim in manifest["nonclaims"])
    # the manifest binds every published output byte
    import hashlib

    for name, digest in manifest["output_sha256"].items():
        assert hashlib.sha256((smoke_run["first"] / name).read_bytes()).hexdigest() == digest
    receipt = json.loads((smoke_run["first"] / "execution-receipt.json").read_text())
    assert (
        receipt["environment"]["device"] == "cpu" and receipt["environment"]["torch_threads"] == 1
    )
    assert receipt["resources"]["peak_rss_bytes"] < 2 * 1024**3
    text = json.dumps(receipt) + json.dumps(manifest)
    assert "/home/" not in text and "/tmp/" not in text, "no absolute paths in outputs"


def test_score_tables_are_finite_complete_and_support_exact(smoke_run: dict[str, Path]) -> None:
    with (smoke_run["first"] / "scores.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(C.ARMS) * 4
    for row in rows:
        values = [float(v) for k, v in row.items() if k not in ("arm", "lift")]
        assert all(math.isfinite(v) for v in values)
        assert 0 < float(row["coverage_50"]) <= 1 and float(row["crps_kg"]) > 0
        assert float(row["width_50_kg"]) < float(row["width_80_kg"]) < float(row["width_90_kg"])
    with (smoke_run["first"] / "cessation_support.csv").open() as handle:
        support = list(csv.DictReader(handle))
    assert [r["truncated_positive_mass"] for r in support] == ["0.000000000"] * 3
    assert all(float(r["truth_nonpositive_fraction"]) == 1.0 for r in support)
    assert all(float(r["mean_gaussian_positive_mass_H"]) > 0 for r in support)


# ------------------------------------------------------------------ leakage and alignment


def test_cohorts_are_disjoint_in_ids_and_content(cohorts: dict[str, R.Cohort]) -> None:
    ids = [set(c.row_ids) for c in cohorts.values()]
    assert sum(len(i) for i in ids) == len(set().union(*ids))
    for role, cohort in cohorts.items():
        assert all(rid.startswith(role + "-") for rid in cohort.row_ids)
    pairs = [(a, b) for a in cohorts for b in cohorts if a < b]
    for a, b in pairs:
        left = {tuple(np.round(row, 6)) for row in cohorts[a].features[:, :32]}
        right = {tuple(np.round(row, 6)) for row in cohorts[b].features[:, :32]}
        assert not left & right, f"{a} and {b} share a participant history"


def test_test_truth_stays_sealed_while_predictions_are_made(cohorts: dict[str, R.Cohort]) -> None:
    fit_cohort, cal_c, cal_g, test = (cohorts[k] for k in ("FIT", "CAL_C", "CAL_G", "TEST"))
    assert not test.truth.opened
    fitted = R.calibrate(fit_cohort, cal_c, cal_g)
    R.predictive_arms(fitted, test)
    assert not test.truth.opened
    assert fit_cohort.truth.opened and cal_c.truth.opened and cal_g.truth.opened


def test_each_parameter_depends_only_on_its_own_cohort_truth(cohorts: dict[str, R.Cohort]) -> None:
    fit_cohort, cal_c, cal_g, test = (cohorts[k] for k in ("FIT", "CAL_C", "CAL_G", "TEST"))
    base = R.calibrate(fit_cohort, cal_c, cal_g)

    def altered(cohort: R.Cohort, shift: float) -> R.Cohort:
        y = cohort.truth.open() + shift
        return R.Cohort(
            cohort.role,
            cohort.row_ids,
            cohort.stratum,
            cohort.features,
            cohort.mu,
            R.SealedTruth(y),
        )

    # TEST truth is never an input to fitting: altering it cannot change any parameter
    again = R.calibrate(fit_cohort, cal_c, cal_g)
    assert np.array_equal(again.g, base.g) and np.array_equal(again.c_h, base.c_h)
    shifted_test = altered(test, 5.0)
    first = R.predictive_arms(base, test)["H_GT"][0]
    second = R.predictive_arms(base, shifted_test)["H_GT"][0]
    assert np.array_equal(first, second)
    # CAL_G truth moves only G
    moved = R.calibrate(fit_cohort, cal_c, altered(cal_g, 3.0))
    assert np.array_equal(moved.head.beta, base.head.beta)
    assert np.array_equal(moved.c_b1, base.c_b1) and np.array_equal(moved.c_h, base.c_h)
    assert not np.array_equal(moved.g, base.g)
    # CAL_C truth moves c (and G through the calibrated H scale) but never the FIT head or B1 table
    moved = R.calibrate(fit_cohort, altered(cal_c, 3.0), cal_g)
    assert np.array_equal(moved.head.beta, base.head.beta)
    assert np.array_equal(moved.b1_raw, base.b1_raw)
    assert not np.array_equal(moved.c_h, base.c_h)


def test_truncation_mask_is_cessation_only_and_leaves_other_plans_unchanged(
    cohorts: dict[str, R.Cohort],
) -> None:
    fit_cohort, cal_c, cal_g, test = (cohorts[k] for k in ("FIT", "CAL_C", "CAL_G", "TEST"))
    arms = R.predictive_arms(R.calibrate(fit_cohort, cal_c, cal_g), test)
    cessation = test.plan == R.CESSATION
    assert cessation.sum() == 15
    for arm in C.ARMS:
        mask = arms[arm][1]
        assert np.array_equal(mask, cessation) if arm in R.TRUNCATED_ARMS else not mask.any()
    y = test.truth.open()
    gaussian = (
        R.score_arm(test.mu, *(arms["H"][0], arms["H"][1]), y)
        if False
        else R.score_arm(test.mu, arms["H"][0], y, arms["H"][1])
    )
    truncated = R.score_arm(test.mu, arms["H_T"][0], y, arms["H_T"][1])
    assert np.array_equal(arms["H"][0], arms["H_T"][0])
    assert np.array_equal(gaussian.crps[~cessation], truncated.crps[~cessation])
    assert not np.array_equal(gaussian.crps[cessation], truncated.crps[cessation])
    assert R.TRUNCATED_ARMS == {"B1_T", "H_T", "H_GT"}
    # the group-calibrated pair differs exactly (and only) on cessation rows
    hg = R.score_arm(test.mu, arms["H_G"][0], y, arms["H_G"][1])
    hgt = R.score_arm(test.mu, arms["H_GT"][0], y, arms["H_GT"][1])
    assert np.array_equal(hg.crps[~cessation], hgt.crps[~cessation])
    assert not np.array_equal(hg.crps[cessation], hgt.crps[cessation])
    assert (y[cessation] <= 0).all()


def test_alignment_checks_reject_misaligned_or_unsupported_inputs(
    cohorts: dict[str, R.Cohort],
) -> None:
    fit_cohort, cal_c, cal_g, test = (cohorts[k] for k in ("FIT", "CAL_C", "CAL_G", "TEST"))
    arms = R.predictive_arms(R.calibrate(fit_cohort, cal_c, cal_g), test)
    y = test.truth.open()
    R.alignment_checks(test, arms, y)
    with pytest.raises(ValueError, match="misaligned"):
        R.alignment_checks(test, arms, y[:-1])
    bad = y.copy()
    bad[test.plan == R.CESSATION, 0] = 0.5
    with pytest.raises(ValueError, match="cessation truth is positive"):
        R.alignment_checks(test, arms, bad)
    wrong_role = R.Cohort("TEST", cal_c.row_ids, test.stratum, test.features, test.mu, test.truth)
    with pytest.raises(ValueError, match="role prefix"):
        R.alignment_checks(wrong_role, arms, y)
    # misaligned truth scores far worse than aligned truth: alignment is observable in the score
    aligned = R.score_arm(test.mu, arms["H"][0], y, arms["H"][1]).crps.mean()
    shuffled = R.score_arm(test.mu, arms["H"][0], y[::-1], arms["H"][1]).crps.mean()
    assert shuffled > 1.2 * aligned


# ------------------------------------------------------------------ fitting formulas


def test_visible_features_match_hand_computation() -> None:
    n = 2
    history = np.zeros((n, 3, 32, 10))
    history[:, :, :, 0] = np.arange(32) * 2.0 + 10  # linear ramp: slope exactly 2
    history[:, :, :, 6] = 0.8
    history[:, :, -1, 6] = 1.2
    numeric = np.arange(12, dtype=float).reshape(n, 6)
    plan = np.array([0, 3])
    features = R.visible_features(history, numeric, plan)
    assert features.shape == (n, 127)
    block = features[0, :5]  # lift 0, channel 0: first, last, mean, population SD, slope
    assert block.tolist() == pytest.approx(
        [10.0, 72.0, 41.0, float(np.std(np.arange(32) * 2.0)), 2.0]
    )
    sched = features[0, 90:99].reshape(3, 3)[0]  # lift 0, dose: mean, last-4 mean, last
    assert sched.tolist() == pytest.approx([0.8 + 0.4 / 32, 0.8 + 0.4 / 4, 1.2])
    assert features[:, -4:].tolist() == [[1, 0, 0, 0], [0, 0, 0, 1]]
    assert features[1, 117:123].tolist() == numeric[1].tolist()


def test_b1_table_is_groupwise_rms_clipped() -> None:
    stratum = np.repeat(np.arange(12), 4)
    mu = np.zeros((48, 3))
    y = np.ones((48, 3)) * np.arange(12).repeat(4)[:, None]
    table = R.fit_b1(stratum, mu, y)
    assert table[5].tolist() == [5.0, 5.0, 5.0]
    assert table[0].tolist() == [0.25] * 3  # lower clip
    assert table[11].tolist() == [11.0] * 3
    assert R.fit_b1(stratum, mu, y * 20)[11].tolist() == [100.0] * 3  # upper clip


def test_ridge_head_satisfies_its_normal_equations_and_recovers_a_scale_law() -> None:
    rng = np.random.default_rng(615)
    n = 3000
    base = rng.normal(size=(n, 127))
    stratum = np.arange(n) % 12
    mu = rng.normal(size=(n, 3))
    scale = np.exp(0.6 * base[:, 0] / 2 + 0.3)
    y = mu + rng.normal(size=(n, 3)) * scale[:, None]
    head = R.fit_h(base, stratum, mu, y)
    for lift in range(3):
        design = R.head_design(base, mu[:, lift], stratum)
        z = (design - head.mean[lift]) / head.sd[lift]
        t = np.log((y[:, lift] - mu[:, lift]) ** 2 + 0.25**2)
        residual = t - head.intercept[lift] - z @ head.beta[lift]
        gradient = z.T @ residual / n - 0.05 * head.beta[lift]
        assert np.abs(gradient).max() < 1e-9
        assert head.intercept[lift] == pytest.approx(t.mean(), abs=1e-12)
    sigma = R.h_sigma_raw(head, base, stratum, mu)
    assert np.corrcoef(np.log(sigma[:, 0]), np.log(scale))[0, 1] > 0.8
    assert sigma.min() >= 0.25 and sigma.max() <= 100


def test_scale_and_group_calibration_formulas() -> None:
    y = np.array([[2.0, -1.0, 0.5]] * 100)
    mu = np.zeros((100, 3))
    c = R.fit_scale_c(np.ones((100, 3)), mu, y)
    assert c.tolist() == pytest.approx([2.0, 1.0, 0.5])
    assert R.fit_scale_c(np.ones((100, 3)), mu, y * 10).tolist() == [4.0] * 3  # upper clip
    assert R.fit_scale_c(np.ones((100, 3)), mu, y / 10).tolist() == [0.25] * 3  # lower clip
    stratum = np.repeat(np.arange(12), 256)
    mu = np.zeros((3072, 3))
    sigma = np.ones((3072, 3))
    same = R.fit_group_factors(sigma, stratum, mu, np.ones((3072, 3)))
    assert np.allclose(same, 1.0)  # R = 1 -> g = 1
    bigger = R.fit_group_factors(sigma, stratum, mu, 2 * np.ones((3072, 3)))
    assert math.sqrt((256 * 4 + 256) / 512) > 1.4  # unclipped sqrt(2.5) = 1.58
    assert np.allclose(bigger, 1.4)  # upper clip
    smaller = R.fit_group_factors(sigma, stratum, mu, 0.1 * np.ones((3072, 3)))
    assert np.allclose(smaller, math.sqrt((256 * 0.01 + 256) / 512))


def test_support_rule_cannot_be_applied_to_observed_performance(
    cohorts: dict[str, R.Cohort],
) -> None:
    for incompatible in ("observed_performance_kg", "assessment_kg"):
        with pytest.raises(ValueError, match="latent capacity change"):
            S.require_support_target(incompatible, "cessation")
    assert C.PROTOCOL["target"]["kind"] == S.LATENT_CAPACITY_CHANGE
    assert "never applied to any other plan or target" in C.PROTOCOL["target"]["truncation_rule"]


def test_formula_selfcheck_matches_numerical_integration(cohorts: dict[str, R.Cohort]) -> None:
    fit_cohort, cal_c, cal_g, test = (cohorts[k] for k in ("FIT", "CAL_C", "CAL_G", "TEST"))
    arms = R.predictive_arms(R.calibrate(fit_cohort, cal_c, cal_g), test)
    report = R.formula_selfcheck(test, arms, test.truth.open())
    assert report["max_abs_crps_vs_integral_kg"] < 1e-6


# ------------------------------------------------------------------ safe failure and limits


def test_missing_or_incompatible_assets_fail_before_any_work(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        R.run("smoke", tmp_path / "out", repo_root=tmp_path)
    assert not (tmp_path / "out" / "manifest.json").exists()


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("evidence")
    with pytest.raises(FileExistsError):
        R.run("smoke", tmp_path)
    assert (tmp_path / "keep.txt").read_text() == "evidence"
    with pytest.raises(ValueError, match="profile"):
        R.run("huge", tmp_path / "x")


def test_thread_pinning_is_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    with pytest.raises(RuntimeError, match="one BLAS/PyTorch thread"):
        R.run("smoke", tmp_path / "out")


def test_resource_ceilings_stop_the_run_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    assert (R.MAX_RSS_BYTES, R.MAX_CPU_SECONDS) == (
        C.RESOURCE_LIMITS["max_process_memory_bytes"],
        C.RESOURCE_LIMITS["max_cpu_seconds"],
    )
    R._check_budget(time.process_time())
    with pytest.raises(R.ResourceLimitReached, match="CPU"):
        R._check_budget(time.process_time() - R.MAX_CPU_SECONDS - 1)
    monkeypatch.setattr(R, "MAX_RSS_BYTES", 1)
    with pytest.raises(R.ResourceLimitReached, match="memory"):
        R._check_budget(time.process_time())


def test_changed_protocol_content_cannot_reuse_the_identity() -> None:
    changed = copy.deepcopy(C.PROTOCOL)
    changed["methods"]["H"]["ridge"] = "different"
    assert C.sha256_record(changed) != C.PROTOCOL_DIGEST


@pytest.mark.skipif(
    os.environ.get("PSR_RUN_FULL_REFERENCE") != "1",
    reason="opt-in ~2 minute CPU reproduction; set PSR_RUN_FULL_REFERENCE=1",
)
def test_full_reference_reproduces_committed_values(tmp_path: Path) -> None:
    result = R.run("full", tmp_path / "out")
    assert result["receipt"]["resources"]["peak_rss_bytes"] < 2 * 1024**3
    expected = ROOT / R.EXPECTED_RELATIVE / "full"
    worst = R.compare_to_expected(tmp_path / "out", expected, same_environment=False)
    assert max(worst.values()) < 5e-3
