"""RES-639 estimators, information firewall, fail-closed gates and statistics (smoke fixtures)."""

import copy
import inspect
import json
import math
import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from powerlifting_state_research.history_uncertainty import contract as K
from powerlifting_state_research.history_uncertainty import heads as H
from powerlifting_state_research.history_uncertainty import replay as R
from powerlifting_state_research.history_uncertainty import study as S
from powerlifting_state_research.observable import contract as base
from powerlifting_state_research.observable import data as D
from powerlifting_state_research.observable import models as ridge_models
from powerlifting_state_research.probabilistic import reference as ref
from powerlifting_state_research.probabilistic import scoring

ROOT = Path(__file__).resolve().parents[1]
ROWS = K.SMOKE_ROLE_ROWS
BASES = K.SMOKE_ROLE_BASE
SMOKE_RIDGE_BETA = "d885aa2011738922567c896e282c7ae11f484b5d9971e619e363376b6b6a2534"
SMOKE_RIDGE_BETA_SIGN_NORMALIZED = (
    "3c5688bf4be4abd1e2b12c352620bf3f3d1d5678edc96d3128a43cbadadcf7d0"
)


@pytest.fixture(autouse=True)
def pinned(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ref.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


@pytest.fixture(scope="module")
def replay() -> R.RidgeReplay:
    torch.set_num_threads(1)
    return R.replay_ridge("smoke")


@pytest.fixture(scope="module")
def populations() -> dict[str, D.ObsCohort]:
    return {
        r: D.build_cohorts(r, ROWS[r], BASES[r])["CONTROL"]
        for r in ("SCALE_FIT", "SCALE_CAL", "TEST_A")
    }


@pytest.fixture(scope="module")
def frozen(replay: R.RidgeReplay, populations: dict[str, D.ObsCohort]) -> H.FrozenScale:
    return H.fit_scale_models(replay.ridge, populations["SCALE_FIT"], populations["SCALE_CAL"])


# ------------------------------------------------------------------ Ridge replay


def test_smoke_replay_matches_the_committed_res616_smoke_identity() -> None:
    """Exact published digest needs the pinned single-thread BLAS the study CLI sets up."""
    import subprocess
    import sys

    code = (
        "import json;from pathlib import Path;"
        "from powerlifting_state_research.history_uncertainty import replay as R;"
        "r=R.replay_ridge('smoke');"
        f"v=R.verify_replay(r,R.reference_for('smoke',Path({str(ROOT)!r})));"
        "print(json.dumps([v['beta_digest_matched'],r.beta_sha256]))"
    )
    env = {**os.environ, **{v: "1" for v in ref.THREAD_VARIABLES}}
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    matched, digest = json.loads(done.stdout.strip().splitlines()[-1])
    assert matched is True and digest == SMOKE_RIDGE_BETA


def test_sign_normalized_digest_is_thread_invariant_and_pinned(replay: R.RidgeReplay) -> None:
    """The published digest is sensitive to the sign of near-zero coefficients; this is not."""
    assert replay.beta_sign_normalized_sha256 == SMOKE_RIDGE_BETA_SIGN_NORMALIZED
    flipped = np.where(np.round(replay.ridge.beta, 9) == 0.0, -0.0, replay.ridge.beta)
    assert R.sign_normalized_digest(flipped) == SMOKE_RIDGE_BETA_SIGN_NORMALIZED
    assert ref.array_digest(flipped) != ref.array_digest(np.abs(flipped) * 0 + replay.ridge.beta)


def test_replay_rejects_changed_ridge_coefficients(replay: R.RidgeReplay) -> None:
    reference = R.reference_for("smoke", ROOT)
    tampered = replace(replay, ridge=replace(replay.ridge, beta=replay.ridge.beta + 1e-6))
    object.__setattr__(tampered, "beta_sha256", ref.array_digest(tampered.ridge.beta))
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(tampered, reference)
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(replace(replay, beta_sha256="0" * 64), reference)


def test_replay_rejects_wrong_alpha_or_row_identity(replay: R.RidgeReplay) -> None:
    reference = R.reference_for("smoke", ROOT)
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(replace(replay, ridge=replace(replay.ridge, alpha=0.01)), reference)
    bad_ids = {**replay.row_id_sha256, "FIT": "f" * 64}
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(replace(replay, row_id_sha256=bad_ids), reference)


def test_cross_environment_path_is_explicit_and_tolerance_bounded(replay: R.RidgeReplay) -> None:
    reference = R.reference_for("smoke", ROOT)
    drift = replace(
        replay,
        beta_sha256="1" * 64,
        dev_rmse_by_alpha={a: v + 1e-9 for a, v in replay.dev_rmse_by_alpha.items()},
    )
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(drift, reference)  # strict by default
    accepted = R.verify_replay(drift, reference, cross_environment=True)
    assert accepted["cross_environment_path_used"] is True
    too_far = replace(
        drift, dev_rmse_by_alpha={a: v + 1e-3 for a, v in replay.dev_rmse_by_alpha.items()}
    )
    with pytest.raises(R.RidgeIdentityError):
        R.verify_replay(too_far, reference, cross_environment=True)


def test_full_reference_is_the_published_res616_identity() -> None:
    reference = R.reference_for("full", ROOT)
    assert reference["alpha"] == 0.01
    assert reference["beta_sha256"].startswith("e360665d7c568dff")
    assert reference["dev_rmse_by_alpha"]["0.01"] == pytest.approx(12.110506034691115)


def test_replay_never_trains_or_loads_the_gru() -> None:
    source = inspect.getsource(R) + inspect.getsource(H) + inspect.getsource(S)
    for forbidden in ("train_gru", "load_gru", "load_weights", "LiftSharedTemporalExpert("):
        assert forbidden not in source


# ------------------------------------------------------------------ designs and firewall


def test_designs_have_the_frozen_widths_and_h_extends_b_mag(
    populations: dict[str, D.ObsCohort], replay: R.RidgeReplay
) -> None:
    cohort = populations["SCALE_FIT"]
    mu = H.ridge_mu(replay.ridge, cohort)[:, 0]
    mag = H.mag_design(mu, cohort.stratum)
    hist = H.history_design(cohort.base_features, mu, cohort.stratum)
    assert mag.shape[1] == 14 and hist.shape[1] == 141
    np.testing.assert_array_equal(hist[:, :14], mag)
    np.testing.assert_array_equal(hist[:, 14:], cohort.base_features)
    np.testing.assert_allclose(mag[:, 1], np.log(np.maximum(mu, 1.0)))
    assert (mag[:, 2:].sum(axis=1) == 1).all()


def test_features_do_not_depend_on_future_observations_or_truth(
    populations: dict[str, D.ObsCohort],
) -> None:
    """Changing only the future-assessment stream changes Y but never any model input."""
    seeds = K.role_seeds(BASES["SCALE_FIT"])
    config = D.generation_config(ROWS["SCALE_FIT"], BASES["SCALE_FIT"])
    other = [r for r in D.iter_raw_rows(config, seeds["future_assessment"] + 1000)]
    other_train = [r for r in other if r.split == "train"]
    rebuilt = D._assemble("SCALE_FIT", "CONTROL", other_train, [r.inputs for r in other_train])
    original = populations["SCALE_FIT"]
    np.testing.assert_array_equal(rebuilt.base_features, original.base_features)
    np.testing.assert_array_equal(rebuilt.raw_history, original.raw_history)
    assert not np.array_equal(rebuilt.truth.open().y, original.truth.open().y)


def test_design_functions_take_only_visible_arrays_and_no_hidden_quantities() -> None:
    for fn in (H.mag_design, H.history_design, H.design_for):
        names = set(inspect.signature(fn).parameters)
        assert names <= {"base", "mu_lift", "stratum", "model"}
        source = inspect.getsource(fn)
        for forbidden in ("truth", ".e.", ".c.", "parameters", "row_ids", "last_e", "last_c"):
            assert forbidden not in source


def test_scale_models_contain_no_entity_or_hidden_state(frozen: H.FrozenScale) -> None:
    for model in frozen.models.values():
        assert set(vars(model)) == {"name", "head", "group", "c", "c_clipped"}
        if model.head is not None:
            assert model.head.beta.shape[1] in (14, 141)


def test_mu_is_the_unchanged_ridge_forecast(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    cohort = populations["TEST_A"]
    arms = H.predict_arms(frozen, cohort)
    expected = cohort.last_assessment + ridge_models.ridge_predict_delta(frozen.ridge, cohort)
    for mu, _ in arms.values():
        np.testing.assert_array_equal(mu, expected)
    assert set(arms) == set(K.MODELS)


# ------------------------------------------------------------------ fitting separation


def test_scale_fitting_and_calibration_reject_test_populations(
    populations: dict[str, D.ObsCohort], replay: R.RidgeReplay
) -> None:
    test = populations["TEST_A"]
    with pytest.raises(H.RoleViolation):
        H.fit_scale_models(replay.ridge, test, populations["SCALE_CAL"])
    with pytest.raises(H.RoleViolation):
        H.fit_scale_models(replay.ridge, populations["SCALE_FIT"], test)
    with pytest.raises(H.RoleViolation):
        H.fit_scale_models(replay.ridge, populations["SCALE_CAL"], populations["SCALE_FIT"])
    forged = replace(test, role="SCALE_FIT")
    with pytest.raises(H.RoleViolation):
        H.fit_scale_models(replay.ridge, forged, populations["SCALE_CAL"])


def test_fitting_never_opens_test_truth(replay: R.RidgeReplay) -> None:
    fit = D.build_cohorts("SCALE_FIT", ROWS["SCALE_FIT"], BASES["SCALE_FIT"])["CONTROL"]
    cal = D.build_cohorts("SCALE_CAL", ROWS["SCALE_CAL"], BASES["SCALE_CAL"])["CONTROL"]
    test = D.build_cohorts("TEST_A", ROWS["TEST_A"], BASES["TEST_A"])["CONTROL"]
    frozen = H.fit_scale_models(replay.ridge, fit, cal)
    H.predict_arms(frozen, test)
    assert fit.truth.opened and cal.truth.opened
    assert not test.truth.opened


def test_populations_are_independent_of_res616_and_each_other(
    populations: dict[str, D.ObsCohort],
) -> None:
    res616 = D.build_cohorts("FIT", base.SMOKE_ROLE_ROWS["FIT"], base.SMOKE_ROLE_BASE["FIT"])
    ids = [set(c.row_ids) for c in populations.values()]
    assert sum(len(i) for i in ids) == len(set().union(*ids))
    other = res616["CONTROL"]
    mine = populations["SCALE_FIT"]
    assert mine.raw_history.shape[1:] == other.raw_history.shape[1:]
    assert not np.array_equal(mine.raw_history[:60], other.raw_history[:60])
    assert not np.array_equal(mine.base_features[:60], other.base_features[:60])


# ------------------------------------------------------------------ estimator mathematics


def test_head_matches_an_independent_normal_equation_solution() -> None:
    rng = np.random.default_rng(3)
    n = 400
    stratum = np.tile(np.arange(12), n // 12 + 1)[:n]
    mu = 150 + 40 * rng.random((n, 3))
    y = mu + rng.normal(0, 8, (n, 3))
    head = H.fit_head("B_MAG", np.zeros((n, 127)), stratum, mu, y)
    for lift in range(3):
        x = H.mag_design(mu[:, lift], stratum)
        mean, sd = x.mean(axis=0), np.maximum(x.std(axis=0), 1e-6)
        z = (x - mean) / sd
        t = np.log((y[:, lift] - mu[:, lift]) ** 2 + 0.25**2)
        t0 = t - t.mean()
        beta = np.linalg.solve(z.T @ z / n + 0.05 * np.eye(14), z.T @ t0 / n)
        np.testing.assert_allclose(head.beta[lift], beta, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(head.intercept[lift], t.mean())
        np.testing.assert_allclose(head.mean[lift], mean)


def test_calibration_scale_formula_and_clipping() -> None:
    mu = np.zeros((4, 3))
    y = np.array([[2.0, 4.0, 1.0]] * 4)
    sigma_raw = np.ones((4, 3))
    np.testing.assert_allclose(H.fit_scale_c(sigma_raw, mu, y), [2.0, 4.0, 1.0])
    np.testing.assert_allclose(H.fit_scale_c(sigma_raw, mu, y * 10), [4.0, 4.0, 4.0])
    np.testing.assert_allclose(H.fit_scale_c(sigma_raw, mu, y * 0.0), [0.25, 0.25, 0.25])
    assert H.clip_sigma([0.0, 1.0, 500.0]).tolist() == [0.25, 1.0, 100.0]


def test_constant_log_shift_is_absorbed_by_calibration(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    """exp((zhat + k)/2) rescales sigma_raw by a constant that c removes exactly."""
    model = frozen.models["B_MAG"]
    cal = populations["SCALE_CAL"]
    mu, y = H.ridge_mu(frozen.ridge, cal), cal.truth.open().y
    outputs = []
    for shift in (0.0, 1.2704):
        raw = H.clip_sigma(
            np.exp(
                H.head_log_variance("B_MAG", model.head, cal.base_features, cal.stratum, mu, shift)
                / 2
            )
        )
        c = H.fit_scale_c(raw, mu, y)
        outputs.append(H.clip_sigma(c * raw))
    np.testing.assert_allclose(outputs[0], outputs[1], rtol=1e-10)


def test_log_squared_residual_is_biased_low_by_the_known_constant() -> None:
    rng = np.random.default_rng(0)
    z = np.log(rng.normal(size=2_000_000) ** 2)
    assert z.mean() == pytest.approx(-(np.euler_gamma + math.log(2)), abs=2e-3)


def test_b_group_is_the_stratum_rms_and_b_mag_h_share_family(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    fit = populations["SCALE_FIT"]
    mu, y = H.ridge_mu(frozen.ridge, fit), fit.truth.open().y
    group = frozen.models["B_GROUP"].group
    assert group is not None
    for g in range(12):
        rows = fit.stratum == g
        np.testing.assert_allclose(
            group[g], np.clip(np.sqrt(np.mean((y[rows] - mu[rows]) ** 2, axis=0)), 0.25, 100)
        )
    a, b = frozen.models["B_MAG"], frozen.models["H_HISTORY"]
    assert a.head is not None and b.head is not None
    assert a.head.beta.shape == (3, 14) and b.head.beta.shape == (3, 141)
    for model in (a, b):
        assert (model.c >= 0.25).all() and (model.c <= 4.0).all()


def test_sigma_is_finite_positive_and_within_bounds(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    for mu, sigma in H.predict_arms(frozen, populations["TEST_A"]).values():
        assert np.isfinite(mu).all() and np.isfinite(sigma).all()
        assert (sigma >= 0.25).all() and (sigma <= 100.0).all()


# ------------------------------------------------------------------ truncation and identities


def test_no_truncation_anywhere_in_the_study_modules() -> None:
    for module in (H, R, S):
        source = inspect.getsource(module)
        for forbidden in ("truncated_crps", "truncated_nll", "truncated_cdf", "truncated_ppf"):
            assert forbidden not in source
    with pytest.raises(ValueError):
        base.check_target_compatibility(base.LATENT_TARGET_KIND, "cessation")


def test_cessation_rows_use_the_plain_gaussian_score() -> None:
    mu = np.array([[5.0, 5.0, 5.0]])
    sigma = np.array([[10.0, 10.0, 10.0]])
    y = np.array([[-3.0, 4.0, 40.0]])
    out = S.score_arm(mu, sigma, y)
    np.testing.assert_allclose(out["crps"], scoring.gaussian_crps(mu, sigma, y))
    assert (out["negative_mass"] > 0).all()  # P(Y<0) reported, never imposed


def test_prediction_target_identity_and_validity_checks(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    cohort = populations["TEST_A"]
    arms = H.predict_arms(frozen, cohort)
    y = np.zeros((cohort.n, 3))
    S.check_identity(cohort, arms, y)
    with pytest.raises(ValueError):
        S.check_identity(cohort, arms, y[:-1])
    short = {k: (mu[:-1], sg[:-1]) for k, (mu, sg) in arms.items()}
    with pytest.raises(ValueError):
        S.check_identity(cohort, short, y)
    bad = copy.deepcopy(arms)
    bad["H_HISTORY"][1][0, 0] = 0.0
    with pytest.raises(ValueError):
        S.check_identity(cohort, bad, y)
    nonfinite = copy.deepcopy(arms)
    nonfinite["B_MAG"][0][0, 0] = np.nan
    with pytest.raises(ValueError):
        S.check_identity(cohort, nonfinite, y)
    with pytest.raises(ValueError):
        scoring.gaussian_crps([1.0], [-1.0], [0.0])
    with pytest.raises(ValueError):
        scoring.gaussian_crps([1.0], [1.0], [np.inf])


def test_sealed_truth_requires_matching_predictions(
    populations: dict[str, D.ObsCohort], frozen: H.FrozenScale
) -> None:
    cohort = D.build_cohorts("TEST_A", ROWS["TEST_A"], BASES["TEST_A"], K.SCENARIOS)
    predictions: dict[str, Any] = {
        "TEST_A": {s: H.predict_arms(frozen, c) for s, c in cohort.items()}
    }
    predictions["TEST_B"] = predictions["TEST_A"]
    seal = S.prediction_digest(predictions)
    assert not cohort["CONTROL"].truth.opened
    with pytest.raises(S.SealViolation):
        S.open_sealed_truth(cohort["CONTROL"], predictions, "0" * 64)
    assert not cohort["CONTROL"].truth.opened
    mutated = copy.deepcopy(predictions)
    mutated["TEST_A"]["CONTROL"]["H_HISTORY"][1][0, 0] += 1.0
    with pytest.raises(S.SealViolation):
        S.open_sealed_truth(cohort["CONTROL"], mutated, seal)
    assert not cohort["CONTROL"].truth.opened
    S.open_sealed_truth(cohort["CONTROL"], predictions, seal)
    assert cohort["CONTROL"].truth.opened


# ------------------------------------------------------------------ statistics


def test_scale_bins_are_equal_count_quintiles_ordered_by_scale() -> None:
    sigma = np.random.default_rng(1).random(103) + 1
    bins = S.scale_bins(sigma)
    assert len(bins) == 5 and sum(len(b) for b in bins) == 103
    assert len({int(i) for b in bins for i in b}) == 103
    means = [sigma[b].mean() for b in bins]
    assert means == sorted(means)


def test_pit_of_a_calibrated_gaussian_is_uniform_and_misfit_is_visible() -> None:
    rng = np.random.default_rng(2)
    mu, sigma = np.zeros((20000, 3)), np.full((20000, 3), 3.0)
    good = S.pit_counts(S.pit_values(mu, sigma, rng.normal(0, 3, mu.shape)))
    assert good.sum() == 60000 and (np.abs(good / 6000 - 1) < 0.06).all()
    narrow = S.pit_counts(S.pit_values(mu, sigma / 2, rng.normal(0, 3, mu.shape)))
    assert narrow[0] > 2 * narrow[4] and narrow[9] > 2 * narrow[4]


def test_interval_coverage_and_width_match_gaussian_quantiles() -> None:
    rng = np.random.default_rng(4)
    mu, sigma = np.zeros((50000, 3)), np.full((50000, 3), 2.0)
    out = S.score_arm(mu, sigma, rng.normal(0, 2, mu.shape))
    for level, key in ((0.5, "50"), (0.8, "80"), (0.9, "90")):
        assert out[f"cov{key}"].mean() == pytest.approx(level, abs=0.01)
        z = float(scoring.gaussian_ppf(0.0, 1.0, 0.5 + level / 2))
        assert out[f"width{key}"].mean() == pytest.approx(4.0 * z, rel=1e-6)


def test_paired_bootstrap_is_deterministic_and_preserves_pairing() -> None:
    from powerlifting_state_research.observable import study as obs

    stratum = np.repeat(np.arange(12), 8)
    matrix = obs.stratum_matrix(stratum)
    idx = obs.bootstrap_indices(K.role_seeds(K.ROLE_BASE["TEST_A"])["bootstrap"], 8, 25)
    np.testing.assert_array_equal(
        idx, obs.bootstrap_indices(K.role_seeds(K.ROLE_BASE["TEST_A"])["bootstrap"], 8, 25)
    )
    a = np.random.default_rng(5).random(96)
    diff = obs.bootstrap_means(a, matrix, idx) - obs.bootstrap_means(a, matrix, idx)
    assert np.all(diff == 0)  # identical paired scores have a degenerate difference


# ------------------------------------------------------------------ authorization and resources


def test_full_profile_is_refused_without_valid_authorization(tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(S.NotAuthorized):
        S.run("full", out)
    assert not out.exists()
    record = tmp_path / "auth.json"
    for body in (
        "not json",
        json.dumps({"protocol_digest": "sha256:" + "0" * 64, "owner_authorized_full_run": True}),
        json.dumps({"protocol_digest": K.PROTOCOL_DIGEST, "owner_authorized_full_run": "yes"}),
        json.dumps({"protocol_digest": K.PROTOCOL_DIGEST}),
    ):
        record.write_text(body)
        with pytest.raises(S.NotAuthorized):
            S.run("full", out, authorization=record)
        assert not out.exists()
    record.write_text(
        json.dumps({"protocol_digest": K.PROTOCOL_DIGEST, "owner_authorized_full_run": True})
    )
    assert len(S.check_authorization(record)) == 64


def test_cli_returns_blocked_exit_code_without_authorization(tmp_path: Path) -> None:
    code = S.main(["--profile", "full", "--out", str(tmp_path / "o")])
    assert code == 4 and not (tmp_path / "o").exists()


def test_budget_stops_on_each_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (S.MAX_CPU, S.MAX_WALL, S.MAX_RSS) == (2400, 3600, 2 * 1024**3)
    budget = S.Budget()
    budget.check()
    monkeypatch.setattr(S, "MAX_CPU", -1)
    with pytest.raises(S.CeilingReached):
        budget.check()
    monkeypatch.setattr(S, "MAX_CPU", 2400)
    monkeypatch.setattr(S, "MAX_WALL", -1)
    with pytest.raises(S.CeilingReached):
        budget.check()
    monkeypatch.setattr(S, "MAX_WALL", 3600)
    monkeypatch.setattr(S, "MAX_RSS", 1)
    with pytest.raises(S.CeilingReached):
        budget.check()


def test_run_refuses_a_non_empty_output_directory(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(FileExistsError):
        S.run("smoke", tmp_path, cross_environment_ridge=True)


def test_unpinned_threads_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "4")
    with pytest.raises(RuntimeError):
        S.require_pinned_threads()


# ------------------------------------------------------------------ chronology (end to end)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[tuple[str, bool]]]:
    out = tmp_path_factory.mktemp("smoke") / "out"
    calls: list[tuple[str, bool]] = []
    original_open = D.Sealed.open
    original_build = D.build_cohorts

    def tagged_build(role: str, rows: int, base_seed: int, scenarios: Any = ("CONTROL",)) -> Any:
        built = original_build(role, rows, base_seed, scenarios)
        for cohort in built.values():
            cohort.truth.role = role  # type: ignore[attr-defined]
        return built

    def spy(self: D.Sealed) -> Any:
        calls.append((getattr(self, "role", "?"), (out / "prediction-seal.json").exists()))
        return original_open(self)

    D.build_cohorts = tagged_build  # type: ignore[assignment]
    D.Sealed.open = spy  # type: ignore[method-assign]
    os.environ.update({v: "1" for v in ref.THREAD_VARIABLES})
    try:
        S.run("smoke", out, cross_environment_ridge=True)
    finally:
        D.build_cohorts = original_build  # type: ignore[assignment]
        D.Sealed.open = original_open  # type: ignore[method-assign]
    return out, calls


def test_test_truth_is_opened_only_after_the_prediction_seal(
    smoke_run: tuple[Path, list[tuple[str, bool]]],
) -> None:
    _, calls = smoke_run
    test_calls = [sealed for role, sealed in calls if role.startswith("TEST")]
    other_calls = [sealed for role, sealed in calls if not role.startswith("TEST")]
    assert test_calls and all(test_calls)
    assert other_calls and not any(other_calls)
    assert {role for role, _ in calls} == {
        "FIT",
        "DEV",
        "SCALE_FIT",
        "SCALE_CAL",
        "TEST_A",
        "TEST_B",
    }


def test_smoke_outputs_are_complete_hashed_and_free_of_cohort_rows(
    smoke_run: tuple[Path, list[tuple[str, bool]]],
) -> None:
    out, _ = smoke_run
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["study_id"] == K.STUDY_ID and manifest["protocol_digest"] == K.PROTOCOL_DIGEST
    assert manifest["disposition"] in K.DISPOSITIONS
    assert manifest["authorization_record_sha256"] is None
    for name, digest in manifest["output_sha256"].items():
        assert S._sha((out / name).read_bytes()) == digest
    frozen = json.loads((out / "frozen-parameters.json").read_text())
    replayed = frozen["ridge_replay"]
    assert replayed["beta_sign_normalized_sha256"] == SMOKE_RIDGE_BETA_SIGN_NORMALIZED
    assert replayed["beta_digest_matched"] or replayed["cross_environment_path_used"]
    text = (out / "frozen-parameters.json").read_text()
    assert "TEST_A-" not in text and "entity-" not in text
    seal = json.loads((out / "prediction-seal.json").read_text())
    assert seal["test_truth_opened"] is False
    assert seal["frozen_parameters_sha256"] == manifest["frozen_parameters_sha256"]


def test_smoke_scores_have_exact_denominators_and_all_models(
    smoke_run: tuple[Path, list[tuple[str, bool]]],
) -> None:
    import csv

    out, _ = smoke_run
    rows = list(csv.DictReader((out / "scores.csv").open()))
    assert {r["model"] for r in rows} == set(K.MODELS)
    assert {r["scenario"] for r in rows} == set(K.SCENARIOS)
    assert {r["n"] for r in rows} == {str(ROWS["TEST_A"])}
    assert len(rows) == 2 * 3 * 3 * 4
    integrity = list(csv.DictReader((out / "integrity.csv").open()))
    assert all(r["rows_expected"] == r["rows_scored"] == str(ROWS["TEST_A"]) for r in integrity)
    assert all(r["nonfinite_predictions"] == "0" for r in integrity)
    pit = list(csv.DictReader((out / "pit.csv").open()))
    assert (
        sum(
            int(r["count"])
            for r in pit
            if r["model"] == "B_MAG" and r["parent"] == "TEST_A" and r["scenario"] == "CONTROL"
        )
        == 3 * ROWS["TEST_A"]
    )


def test_primary_contrast_is_labelled_once_per_parent(
    smoke_run: tuple[Path, list[tuple[str, bool]]],
) -> None:
    import csv

    out, _ = smoke_run
    primary = [
        r for r in csv.DictReader((out / "paired_contrasts.csv").open()) if r["status"] == "PRIMARY"
    ]
    assert sorted(r["parent"] for r in primary) == ["TEST_A", "TEST_B"]
    assert all(r["contrast"] == "H_HISTORY-B_MAG" and r["scenario"] == "CONTROL" for r in primary)


def test_smoke_run_is_deterministic(
    smoke_run: tuple[Path, list[tuple[str, bool]]], tmp_path: Path
) -> None:
    out, _ = smoke_run
    again = tmp_path / "again"
    S.run("smoke", again, cross_environment_ridge=True)
    first = json.loads((out / "manifest.json").read_text())
    second = json.loads((again / "manifest.json").read_text())
    assert first["output_sha256"] == second["output_sha256"]
    S.compare_to_expected(again, out, same_environment=True)


def test_failure_after_truth_is_preserved_not_rescored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected failure")

    monkeypatch.setattr(S, "figures", boom)
    out = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="injected"):
        S.run("smoke", out, cross_environment_ridge=True)
    marker = json.loads((out / "FAILED-AFTER-TEST-TRUTH.json").read_text())
    assert "never adjust and rescore" in marker["note"]
    assert not (out / "manifest.json").exists()


EXPECTED_SMOKE = ROOT / S.EXPECTED_RELATIVE / "smoke"


def test_smoke_matches_the_committed_expectation(tmp_path: Path) -> None:
    out = tmp_path / "fresh"
    S.run("smoke", out, cross_environment_ridge=True)
    worst = S.compare_to_expected(out, EXPECTED_SMOKE, same_environment=False)
    assert max(worst.values()) <= max(S.CROSS_ENVIRONMENT_TOLERANCE.values())
    expected = json.loads((EXPECTED_SMOKE / "manifest.json").read_text())
    assert expected["profile"] == "smoke" and expected["authorization_record_sha256"] is None
    assert expected["protocol_digest"] == K.PROTOCOL_DIGEST


def test_committed_smoke_directory_contains_no_scientific_claims() -> None:
    names = {p.name for p in EXPECTED_SMOKE.iterdir()}
    assert "execution-receipt.json" not in names  # nondeterministic timing is not committed
    assert not (ROOT / S.EXPECTED_RELATIVE / "full").exists()  # no scientific result exists yet


@pytest.mark.skipif(
    "PSR_RUN_FULL_HISTORY_UNCERTAINTY" not in os.environ,
    reason="owner-authorized one-shot run; set PSR_RUN_FULL_HISTORY_UNCERTAINTY=<record path>",
)
def test_full_profile_is_only_runnable_with_the_owner_record(tmp_path: Path) -> None:
    record = Path(os.environ["PSR_RUN_FULL_HISTORY_UNCERTAINTY"])
    result = S.run("full", tmp_path / "full", authorization=record)
    assert result["summary"]["disposition"] in K.DISPOSITIONS
