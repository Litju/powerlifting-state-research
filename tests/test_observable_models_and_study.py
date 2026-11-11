"""RES-616 models, calibration chain, statistics, firewall and fail-closed behavior."""

import json
import math
import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from powerlifting_state_research.models import temporal_expert as te
from powerlifting_state_research.observable import contract as C
from powerlifting_state_research.observable import data as D
from powerlifting_state_research.observable import models as M
from powerlifting_state_research.observable import study as S
from powerlifting_state_research.probabilistic import reference as ref
from powerlifting_state_research.probabilistic import scoring

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SMOKE = ROOT / S.EXPECTED_RELATIVE / "smoke"
BASES = C.SMOKE_ROLE_BASE
ROWS = C.SMOKE_ROLE_ROWS


@pytest.fixture(autouse=True)
def pinned(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ref.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


@pytest.fixture(scope="module")
def roles() -> dict[str, D.ObsCohort]:
    return {
        r: D.build_cohorts(r, ROWS[r], BASES[r])["CONTROL"]
        for r in ("FIT", "DEV", "CAL_C", "CAL_G")
    }


@pytest.fixture(scope="module")
def frozen(roles: dict[str, D.ObsCohort]) -> M.Frozen:
    torch.set_num_threads(1)
    fit, dev, cal_c, cal_g = (roles[r] for r in ("FIT", "DEV", "CAL_C", "CAL_G"))
    ridge, scores = M.fit_ridge(fit, dev)
    stats = M.gru_stats(fit)
    train = M.train_gru(
        M.make_batch(fit, stats),
        M.target_z(fit, stats),
        M.make_batch(dev, stats),
        M.target_z(dev, stats),
        seed=C.SMOKE_MODEL_SEED,
        max_epochs=2,
    )
    partial = M.Frozen(ridge, scores, train.model, stats, {}, train)
    chains = {m: M.fit_chain(m, partial, dev, cal_c, cal_g) for m in C.MODELS}
    return M.Frozen(ridge, scores, train.model, stats, chains, train)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    torch.set_num_threads(1)
    for name in ref.THREAD_VARIABLES:
        os.environ[name] = "1"
    first = tmp_path_factory.mktemp("a") / "out"
    second = tmp_path_factory.mktemp("b") / "out"
    S.run("smoke", first)
    S.run("smoke", second)
    return {"first": first, "second": second}


# ------------------------------------------------------------------ scoring and statistics


def test_score_arm_matches_manual_formulas() -> None:
    mu = np.array([[100.0, 80.0, 150.0], [101.0, 79.0, 149.0]])
    sigma = np.array([[4.0, 3.0, 6.0], [4.0, 3.0, 6.0]])
    y = np.array([[103.0, 80.0, 140.0], [95.0, 85.0, 152.0]])
    result = S.score_arm(mu, sigma, y)
    z = (y - mu) / sigma
    cdf = np.vectorize(lambda v: 0.5 * (1 + math.erf(v / math.sqrt(2))))
    pdf = np.exp(-0.5 * z**2) / math.sqrt(2 * math.pi)
    assert np.allclose(
        result["crps"],
        sigma * (z * (2 * cdf(z) - 1) + 2 * pdf - 1 / math.sqrt(math.pi)),
        atol=1e-12,
    )
    assert np.allclose(result["nll"], np.log(sigma) + 0.5 * math.log(2 * math.pi) + z**2 / 2)
    assert np.array_equal(result["abs_error"], np.abs(mu - y))
    assert np.allclose(result["negative_mass"], cdf(-mu / sigma))
    half = {0.8: 1.2815515655446004, 0.9: 1.6448536269514722}
    for level, q in half.items():
        key = int(level * 100)
        assert np.array_equal(result[f"cov{key}"], (np.abs(z) <= q + 1e-12).astype(float))
        assert np.allclose(result[f"width{key}"], 2 * q * sigma)


def test_crps_agrees_with_numerical_integration_for_assessments() -> None:
    mu, sigma, y = 142.3, 5.1, 150.2
    grid_left = np.linspace(mu - 14 * sigma, y, 40001)
    grid_right = np.linspace(y, mu + 14 * sigma, 40001)
    cdf = lambda t: scoring.gaussian_cdf(mu, sigma, t)  # noqa: E731
    integral = np.trapezoid(cdf(grid_left) ** 2, grid_left) + np.trapezoid(
        (1 - cdf(grid_right)) ** 2, grid_right
    )
    assert float(
        S.score_arm(np.array([[mu]]), np.array([[sigma]]), np.array([[y]]))["crps"][0, 0]
    ) == pytest.approx(integral, abs=1e-6)


def test_no_truncation_path_exists_for_the_observed_target() -> None:
    source = (ROOT / "src/powerlifting_state_research/observable/study.py").read_text()
    models = (ROOT / "src/powerlifting_state_research/observable/models.py").read_text()
    for text in (source, models):
        assert "truncated_" not in text and "truncated_ppf" not in text
    mu = np.array([[-50.0, 10.0, 10.0]])  # large negative mass is reported, never transformed
    out = S.score_arm(mu, np.ones((1, 3)) * 20, np.array([[1.0, 2.0, 3.0]]))
    assert out["negative_mass"][0, 0] > 0.99 and np.isfinite(out["crps"]).all()


def test_bootstrap_indices_are_deterministic_stratified_and_seeded_from_the_protocol() -> None:
    seed = C.role_seeds(C.ROLE_BASE["TEST_A"])["bootstrap"]
    assert seed == 616508
    a = S.bootstrap_indices(seed, 256, 1000)
    assert a.shape == (1000, 12, 256) and a.min() >= 0 and a.max() < 256
    assert np.array_equal(a, S.bootstrap_indices(seed, 256, 1000))
    assert not np.array_equal(a, S.bootstrap_indices(seed + 1000, 256, 1000))
    assert C.BOOTSTRAP_REPLICATES == 1000


def test_bootstrap_means_are_paired_exact_and_cover_the_truth() -> None:
    rng = np.random.default_rng(3)
    n, per = 12 * 40, 40
    stratum = np.repeat(np.arange(12), per)
    rng.shuffle(stratum)
    strata = S.stratum_matrix(stratum)
    assert strata.shape == (12, per) and (stratum[strata] == np.arange(12)[:, None]).all()
    a = rng.normal(5.0, 1.0, n)
    b = a + rng.normal(0.3, 0.2, n)  # strongly paired
    idx = S.bootstrap_indices(11, per, 1000)
    identity = np.broadcast_to(np.arange(per), (1, 12, per))
    assert S.bootstrap_means(a, strata, identity)[0] == pytest.approx(a.mean(), abs=1e-12)
    diff = S.bootstrap_means(b, strata, idx) - S.bootstrap_means(a, strata, idx)
    assert np.allclose(diff, S.bootstrap_means(b - a, strata, idx), atol=1e-12)  # pairing preserved
    lo, hi = S.percentile_interval(diff)
    assert lo < float((b - a).mean()) < hi and lo > 0
    assert (hi - lo) < 0.15  # pairing shrinks the interval relative to unpaired variability
    assert (lo, hi) == tuple(float(v) for v in np.percentile(diff, [2.5, 97.5]))
    with pytest.raises(ValueError, match="unbalanced"):
        S.stratum_matrix(np.array([0] * 13 + list(range(1, 12))))


# ------------------------------------------------------------------ models and fitting


def test_ridge_design_uses_only_visible_features_and_solves_the_normal_equations(
    roles: dict[str, D.ObsCohort],
) -> None:
    fit = roles["FIT"]
    for lift in range(3):
        design = M.ridge_design(fit.base_features, fit.stratum, lift)
        assert design.shape == (fit.n, 163)
        assert np.array_equal(design[:, :127], fit.base_features)
    design = M.ridge_design(fit.base_features, fit.stratum, 0)
    target = (fit.truth.open().y - fit.last_assessment)[:, 0]
    alpha = 0.1
    mean, sd, intercept, beta = M._ridge_one(design, target, alpha)
    z = (design - mean) / sd
    gradient = z.T @ (target - intercept - z @ beta) / fit.n - alpha * beta
    assert np.abs(gradient).max() < 1e-9 and intercept == pytest.approx(target.mean(), abs=1e-12)


def test_alpha_is_selected_from_the_frozen_set_using_dev_only(
    roles: dict[str, D.ObsCohort], frozen: M.Frozen
) -> None:
    assert M.ALPHAS == tuple(float(a) for a in C.PROTOCOL["models"]["M1"]["alpha_candidates"])
    assert frozen.ridge.alpha in M.ALPHAS and set(frozen.ridge_alpha_scores) == {
        str(a) for a in M.ALPHAS
    }
    best = min(frozen.ridge_alpha_scores, key=lambda k: frozen.ridge_alpha_scores[k])
    assert float(best) == frozen.ridge.alpha


def test_frozen_training_constants_match_the_protocol() -> None:
    spec = C.PROTOCOL["models"]["M2"]
    assert spec["max_epochs"] == 20 and spec["attempts"] == 1 and spec["seed"] == C.MODEL_SEED
    assert (M.LR, M.WEIGHT_DECAY, M.BATCH_SIZE, M.CLIP_NORM) == (1e-3, 1e-4, 256, 1.0)
    assert (M.PATIENCE, M.MIN_IMPROVEMENT) == (4, 1e-4)
    assert S.MAX_GRU_CPU == 2400.0 and S.MAX_CPU == 5400 and S.MAX_WALL == 7200
    assert S.MAX_RSS == 2 * 1024**3 and spec["training_seed_stability"] == "NOT TESTED"


def test_gru_batch_matches_the_released_preprocessing(roles: dict[str, D.ObsCohort]) -> None:
    config = D.generation_config(60, BASES["DEV"])
    rows = [
        r
        for r in D.iter_raw_rows(config, C.role_seeds(BASES["DEV"])["future_assessment"])
        if r.split == "train"
    ][:20]
    inputs = [
        te.TemporalModelInput.from_forecast_inputs(f"x{i}", r.inputs) for i, r in enumerate(rows)
    ]
    cohort = D._assemble("DEV", "CONTROL", rows, [r.inputs for r in rows])
    stats = M.gru_stats(roles["FIT"])
    expected = te.prepare_batch(inputs, stats).tensors
    got = M.make_batch(cohort, stats)
    assert torch.equal(got.history, expected.history) and torch.equal(
        got.plan_index, expected.plan_index
    )
    assert torch.equal(got.plan_numeric, expected.plan_numeric)


def test_gru_statistics_are_fit_only(roles: dict[str, D.ObsCohort]) -> None:
    stats = M.gru_stats(roles["FIT"])
    delta = roles["FIT"].truth.open().y - roles["FIT"].last_assessment
    assert np.allclose(stats.target_mean, delta.mean(axis=0)) and np.allclose(
        stats.target_scale, delta.std(axis=0)
    )
    shifted = replace(roles["DEV"], raw_history=roles["DEV"].raw_history * 2)
    assert (
        M.gru_stats(roles["FIT"]) == stats
        and shifted.raw_history.shape == roles["DEV"].raw_history.shape
    )


def test_gru_training_is_deterministic_budgeted_and_restores_the_best_state(
    roles: dict[str, D.ObsCohort], frozen: M.Frozen
) -> None:
    fit, dev = roles["FIT"], roles["DEV"]
    stats = frozen.stats
    args = (
        M.make_batch(fit, stats),
        M.target_z(fit, stats),
        M.make_batch(dev, stats),
        M.target_z(dev, stats),
    )
    again = M.train_gru(*args, seed=C.SMOKE_MODEL_SEED, max_epochs=2)
    assert M.state_digest(again.model) == M.state_digest(frozen.gru)
    train = frozen.train
    assert (
        train is not None
        and train.epochs_run <= 2
        and train.stop_reason in {"max_epochs", "early_stopping"}
    )
    best = min(train.history, key=lambda h: h["dev_mse"])
    assert train.best_epoch == int(best["epoch"])
    dev_mse = float(torch.mean((M._forward(frozen.gru, args[2]) - args[3]) ** 2))
    assert dev_mse == pytest.approx(best["dev_mse"], rel=1e-5)
    stopped = M.train_gru(*args, seed=C.SMOKE_MODEL_SEED, max_epochs=5, cpu_budget_seconds=0.0)
    assert stopped.stop_reason == "cpu_budget_exhausted" and stopped.epochs_run == 1


def test_early_stopping_uses_patience_four(
    monkeypatch: pytest.MonkeyPatch, roles: dict[str, D.ObsCohort]
) -> None:
    fit, dev = roles["FIT"], roles["DEV"]
    stats = M.gru_stats(fit)
    values = iter([1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    real_mean = torch.mean
    state = {"calls": 0}

    def fake_mean(x: torch.Tensor, *a: object, **k: object) -> torch.Tensor:
        # the dev MSE is the only mean() taken under inference_mode; train mean needs grad
        if not x.requires_grad and x.ndim == 2:
            state["calls"] += 1
            return torch.tensor(next(values))
        return real_mean(x, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(torch, "mean", fake_mean)
    result = M.train_gru(
        M.make_batch(fit, stats),
        M.target_z(fit, stats),
        M.make_batch(dev, stats),
        M.target_z(dev, stats),
        seed=1,
        max_epochs=20,
    )
    # epoch 2 is the last improvement (0.5); epochs 3..6 add four non-improving epochs -> stop at 6
    assert (
        result.best_epoch == 2 and result.epochs_run == 6 and result.stop_reason == "early_stopping"
    )


# ------------------------------------------------------------------ calibration chain


def test_sigma_chain_follows_the_frozen_formulas(
    roles: dict[str, D.ObsCohort], frozen: M.Frozen
) -> None:
    dev, cal_c, cal_g = roles["DEV"], roles["CAL_C"], roles["CAL_G"]
    for model in C.MODELS:
        chain = frozen.chains[model]
        res_dev = dev.truth.open().y - M.predict_mu(model, frozen, dev)
        for g in range(12):
            take = dev.stratum == g
            assert np.allclose(
                chain.raw[g], np.clip(np.sqrt(np.mean(res_dev[take] ** 2, axis=0)), 0.25, 100)
            )
        res_c = cal_c.truth.open().y - M.predict_mu(model, frozen, cal_c)
        expected_c = np.clip(
            np.sqrt(np.mean(res_c**2 / chain.raw[cal_c.stratum] ** 2, axis=0)), 0.25, 4
        )
        assert np.allclose(chain.c, expected_c)
        res_g = cal_g.truth.open().y - M.predict_mu(model, frozen, cal_g)
        sig = np.clip(chain.c * chain.raw[cal_g.stratum], 0.25, 100)
        for g in range(12):
            take = cal_g.stratum == g
            n = take.sum()
            r = np.mean(res_g[take] ** 2 / sig[take] ** 2, axis=0)
            assert np.allclose(chain.g[g], np.clip(np.sqrt((n * r + 256) / (n + 256)), 0.7, 1.4))
        assert (chain.g >= 0.7).all() and (chain.g <= 1.4).all()


def test_each_calibration_stage_depends_only_on_its_own_role(
    roles: dict[str, D.ObsCohort], frozen: M.Frozen
) -> None:
    dev, cal_c, cal_g = roles["DEV"], roles["CAL_C"], roles["CAL_G"]

    def shifted(cohort: D.ObsCohort, amount: float) -> D.ObsCohort:
        t = cohort.truth.open()
        return replace(cohort, truth=D.Sealed(replace(t, y=t.y + amount)))

    base = M.fit_chain("M2", frozen, dev, cal_c, cal_g)
    moved_g = M.fit_chain("M2", frozen, dev, cal_c, shifted(cal_g, 4.0))
    assert np.array_equal(moved_g.raw, base.raw) and np.array_equal(moved_g.c, base.c)
    assert not np.array_equal(moved_g.g, base.g)
    moved_c = M.fit_chain("M2", frozen, dev, shifted(cal_c, 4.0), cal_g)
    assert np.array_equal(moved_c.raw, base.raw) and not np.array_equal(moved_c.c, base.c)
    moved_dev = M.fit_chain("M2", frozen, shifted(dev, 4.0), cal_c, cal_g)
    assert not np.array_equal(moved_dev.raw, base.raw)


def test_predictive_arms_are_frozen_gaussian_and_untruncated(
    roles: dict[str, D.ObsCohort], frozen: M.Frozen
) -> None:
    test = D.build_cohorts("TEST_A", 60, BASES["TEST_A"], C.SCENARIOS)
    control = test["CONTROL"]
    arms = M.predictive_arms(frozen, control)
    assert set(arms) == set(C.ARMS)
    assert np.array_equal(arms["M0_C"][0], control.last_assessment)  # persistence
    assert np.array_equal(arms["M1_C"][0], arms["M1_G"][0]) and np.array_equal(
        arms["M2_C"][0], arms["M2_G"][0]
    )
    for mu, sigma in arms.values():
        assert mu.shape == sigma.shape == (60, 3) and np.isfinite(mu).all()
        assert sigma.min() >= 0.25 and sigma.max() <= 100
    # predictions never touch the sealed truth
    assert not any(c.truth.opened for c in test.values())
    # perturbing hidden truth cannot change predictions
    tampered = replace(
        control, truth=D.Sealed(replace(control.truth.open(), y=control.truth.open().y + 99))
    )
    again = M.predictive_arms(frozen, tampered)
    for arm in C.ARMS:
        assert np.array_equal(arms[arm][0], again[arm][0]) and np.array_equal(
            arms[arm][1], again[arm][1]
        )
    # predictions differ across models (a latent-capacity output is not reused)
    assert not np.array_equal(arms["M1_C"][0], arms["M2_C"][0])


# ------------------------------------------------------------------ end-to-end smoke


def test_fresh_executions_are_byte_identical_except_the_receipt(smoke_run: dict[str, Path]) -> None:
    names = sorted(p.name for p in smoke_run["first"].iterdir())
    for required in (
        "manifest.json",
        "prediction-seal.json",
        "freeze-seal.json",
        "scores.csv",
        "paired_contrasts.csv",
        "summary.json",
        "execution-receipt.json",
    ):
        assert required in names
    for name in names:
        if name != "execution-receipt.json":
            assert (smoke_run["first"] / name).read_bytes() == (
                smoke_run["second"] / name
            ).read_bytes()


def test_committed_smoke_expectation_reproduces(smoke_run: dict[str, Path]) -> None:
    assert EXPECTED_SMOKE.is_dir()
    worst = S.compare_to_expected(smoke_run["first"], EXPECTED_SMOKE, same_environment=False)
    assert max(worst.values()) <= max(S.CROSS_ENVIRONMENT_TOLERANCE.values())


def test_comparison_detects_tampering(smoke_run: dict[str, Path], tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    copy.mkdir()
    for p in smoke_run["first"].iterdir():
        (copy / p.name).write_bytes(p.read_bytes())
    lines = (copy / "scores.csv").read_text().splitlines()
    cells = lines[1].split(",")
    cells[5] = f"{float(cells[5]) + 1.0:.9f}"
    lines[1] = ",".join(cells)
    (copy / "scores.csv").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="manifest hash"):
        S.compare_to_expected(copy, smoke_run["first"], same_environment=False)


def test_truth_order_and_records(smoke_run: dict[str, Path]) -> None:
    out = smoke_run["first"]
    freeze = json.loads((out / "freeze-seal.json").read_text())
    seal = json.loads((out / "prediction-seal.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    assert freeze["test_cohorts_generated"] is False and seal["test_truth_opened"] is False
    assert seal["frozen_parameters_sha256"] == freeze["frozen_parameters_sha256"]
    assert manifest["prediction_seal_sha256"] == seal["prediction_seal_sha256"]
    assert manifest["study_id"] == C.STUDY_ID and manifest["identities"] == C.PROTOCOL["identities"]
    assert len(manifest["cohorts"]) == 6 and manifest["disposition"] in C.DISPOSITION_RULES
    receipt = json.loads((out / "execution-receipt.json").read_text())
    assert (
        receipt["environment"]["device"] == "cpu" and receipt["environment"]["torch_threads"] == 1
    )
    assert receipt["resources"]["peak_rss_bytes"] < S.MAX_RSS
    assert receipt["resources"]["gru_forward_backward_calls"] >= 1
    text = json.dumps(receipt) + json.dumps(manifest)
    assert "/home/" not in text and "/tmp/" not in text
    frozen_doc = json.loads((out / "frozen-parameters.json").read_text())
    assert frozen_doc["gru"]["training_seed_stability"] == "NOT TESTED"


def test_tables_have_complete_denominators_and_paired_structure(smoke_run: dict[str, Path]) -> None:
    import csv

    out = smoke_run["first"]
    with (out / "scores.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 * 3 * len(C.ARMS) * 4 and all(r["n"] == "60" for r in rows)
    assert all(
        math.isfinite(float(v))
        for r in rows
        for k, v in r.items()
        if k not in ("parent", "scenario", "arm", "lift")
    )
    with (out / "integrity.csv").open() as handle:
        for r in csv.DictReader(handle):
            assert (
                r["rows_expected"] == r["rows_scored"] == "60" and r["nonfinite_predictions"] == "0"
            )
    with (out / "paired_contrasts.csv").open() as handle:
        contrasts = list(csv.DictReader(handle))
    primary = [r for r in contrasts if r["status"] == "PRIMARY"]
    assert [r["parent"] for r in primary] == ["TEST_A", "TEST_B"] and all(
        r["scenario"] == "CONTROL" for r in primary
    )
    assert all(
        float(r["ci_lo"]) <= float(r["diff_crps_kg"]) <= float(r["ci_hi"]) for r in contrasts
    )
    with (out / "cessation_audit.csv").open() as handle:
        audit = list(csv.DictReader(handle))
    assert all(float(r["capacity_change_nonpositive_frac"]) == 1.0 for r in audit)


# ------------------------------------------------------------------ fail-closed behavior


def test_existing_output_and_bad_profile_fail_before_work(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("evidence")
    with pytest.raises(FileExistsError):
        S.run("smoke", tmp_path)
    assert (tmp_path / "keep.txt").read_text() == "evidence"
    with pytest.raises(ValueError, match="profile"):
        S.run("huge", tmp_path / "x")


def test_thread_pinning_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    with pytest.raises(RuntimeError, match="one BLAS/PyTorch thread"):
        S.run("smoke", tmp_path / "out")


def test_ceilings_stop_the_campaign(monkeypatch: pytest.MonkeyPatch) -> None:
    budget = S.Budget()
    budget.check()
    budget.cpu0 -= S.MAX_CPU + 1
    with pytest.raises(S.CeilingReached, match="CPU"):
        budget.check()
    wall = S.Budget()
    wall.wall0 -= S.MAX_WALL + 1
    with pytest.raises(S.CeilingReached, match="wall"):
        wall.check()
    monkeypatch.setattr(S, "MAX_RSS", 1)
    with pytest.raises(S.CeilingReached, match="memory"):
        S.Budget().check()


def test_failure_after_truth_opened_is_preserved_and_not_rescored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated scoring failure")

    monkeypatch.setattr(S, "score_arm", boom)
    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="simulated"):
        S.run("smoke", out)
    failed = json.loads((out / "FAILED-AFTER-TEST-TRUTH.json").read_text())
    assert "never adjust and rescore" in failed["note"]
    assert not (out / "manifest.json").exists() and (out / "prediction-seal.json").exists()


def test_study_does_not_use_restricted_or_historical_artifacts() -> None:
    root = ROOT / "src/powerlifting_state_research/observable"
    text = "".join(p.read_text() for p in root.glob("*.py"))
    for forbidden in (
        "verify_released_assets",
        "seed-383001",
        "load_weights",
        "torch.load",
        "psr-res5",
    ):
        assert forbidden not in text
    assert C.PROTOCOL["rights"]["historical_checkpoints"].startswith("not loaded")


@pytest.mark.skipif(
    os.environ.get("PSR_RUN_FULL_OBSERVABLE") != "1",
    reason="opt-in ~8 CPU-minute reproduction; set PSR_RUN_FULL_OBSERVABLE=1",
)
def test_full_study_reproduces_committed_values(tmp_path: Path) -> None:
    result = S.run("full", tmp_path / "out")
    assert result["receipt"]["resources"]["peak_rss_bytes"] < S.MAX_RSS
    S.compare_to_expected(
        tmp_path / "out", ROOT / S.EXPECTED_RELATIVE / "full", same_environment=False
    )


def test_committed_full_results_are_complete_and_internally_consistent() -> None:
    import csv
    import hashlib

    full = ROOT / S.EXPECTED_RELATIVE / "full"
    manifest = json.loads((full / "manifest.json").read_text())
    for name, digest in manifest["output_sha256"].items():
        assert hashlib.sha256((full / name).read_bytes()).hexdigest() == digest
    assert manifest["study_id"] == C.STUDY_ID and manifest["profile"] == "full"
    assert manifest["disposition"] == "OBSERVABLE_FORECASTING_NOT_QUALIFIED"
    assert (
        all(v["rows"] == 3072 for v in manifest["cohorts"].values())
        and len(manifest["cohorts"]) == 6
    )
    with (full / "scores.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 * 3 * 5 * 4 and all(r["n"] == "3072" for r in rows)
    summary = json.loads((full / "summary.json").read_text())
    assert summary["criteria"]["nonfinite_predictions"] == 0
    assert not any(p["screen"] for p in summary["primary"].values())
    receipt = json.loads((full / "execution-receipt.json").read_text())["resources"]
    assert receipt["cpu_seconds"] < 5400 and receipt["wall_seconds"] < 7200
    assert receipt["gru_fit_cpu_seconds"] < 2400 and receipt["peak_rss_bytes"] < 2 * 1024**3
