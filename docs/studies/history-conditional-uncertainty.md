# History-conditioned predictive uncertainty (RES-639)

**Status: COMPLETED (one authorized run). Disposition: `MIXED_OR_NOT_QUALIFIED`.** Participant-visible histories did **not** improve the predictive scale of the frozen Ridge forecast beyond forecast magnitude; `H_HISTORY` was slightly *worse* than `B_MAG` on both independent TEST parents. This is a controlled synthetic result with a negative primary finding. The design sections below are the pre-execution record; [Results](#results-single-authorized-run) follows them.

- Mission: `PSR_OBSERVABLE_HISTORY_CONDITIONAL_UNCERTAINTY_ONE_SHOT`
- Frozen protocol: [`protocol.json`](../../results/studies/history_conditional_uncertainty/protocol.json), study id `psr:study:history-conditioned-assessment-uncertainty@1.0.0~3402d80af3db`, digest `sha256:3402d80af3db1ecf79682a6683a1f603f288010fe1dc486513f28ee587129c52`
- Baseline mainline: `6696bebe61adbc57abf406445acfe92e008d2fcf`
- Unchanged prior dispositions: RES-616 `OBSERVABLE_FORECASTING_NOT_QUALIFIED`; RES-617 `FULL_G2_IDENTIFICATION_UNSUPPORTED`. G2 fitting, identification and mechanistic reconstruction are not reopened.

## Question

Does participant-visible training history give incremental information about the uncertainty of a future noisy synthetic strength assessment, beyond the forecast magnitude and the lift × plan × horizon stratum? The location forecast μ is the unchanged RES-616 Ridge (M1). Because μ is itself history-dependent, the answer is **incremental to the frozen point forecast**, not the total influence of history.

The target is `Y_t = E_t(1 + ε_t)`, the future noisy assessment, not latent capacity. Origin day 224, history through day 223, horizons 14/28/56 days (assessment days 237/251/279), three lifts, four plans. No truncation is applied anywhere.

## Baseline audit (verified at design time)

| Check | Result |
| --- | --- |
| `origin/main` | `6696beb` (matches the stated mainline) |
| Study id / protocol digest (RES-616) | code, `protocol.json`, `manifest.json`, `frozen-parameters.json` all agree (`…~de8b63092417`) |
| `frozen-parameters.json` SHA-256 | `18caaf9c…` equals `freeze-seal.json` and the manifest output hash |
| Ridge α, β identity | α = 0.01; `beta_sha256 = e360665d…f9d9` (recorded; **coefficients themselves are not published**) |
| Replay-relevant source drift since RES-616 evaluation commit `978fa53` | none (empty `git diff` over generator, feature, ridge, scoring modules, `pyproject.toml`, `uv.lock`); 12 files byte-pinned in tests |
| RES-616 CONTROL macro CRPS (TEST_A / TEST_B) | Ridge 6.6378 / 6.6281 kg; GRU 6.7481 / 6.7197 kg (read from committed `scores.csv`) |

**Source-level identity** (above) was verified at design time. The numerical replay (regenerating RES-616 FIT 12,288 and DEV 3,072 rows) was deferred to the execution gate and then performed; see Results.

### Reproducibility assessment

- Ridge depends only on public MIT code, the public synthetic generator and published FIT/DEV seeds (616101, 616201). No private bytes, uncommitted checkpoint or nondeterministic training is involved. The GRU is neither retrained nor loaded.
- The fit is a deterministic least-squares solve (`numpy.linalg.lstsq`) after SD-floored standardization. Its recorded digest rounds to 9 decimals, but BLAS differences across machines can in principle alter low-order bits. Recorded RES-616 environment: Python 3.12.13, NumPy 2.4.4, PyTorch 2.9.1+cpu, Linux x86_64, one thread.
- **Undocumented-runtime risk:** only the β digest, not the coefficients, is published. A mismatch cannot be localized. The replay therefore requires an exact β digest in the recorded environment. Outside it, the explicit tier-2 path accepts α = 0.01 and DEV RMSE for every α within 1e-6 kg and records that the digest was not matched. If neither holds the run is `BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE`. A newly optimized Ridge is never substituted.
- Expected replay cost, from RES-616 receipts: about 60 s generation plus 3 s fit, charged to the same 2,400 s campaign.

## Frozen design

**Populations** (new seeds, disjoint from RES-615/616 and each other, checked against the historical registries; each balanced over the 12 plan × horizon strata):

| Role | Rows | Seed base |
| --- | ---: | ---: |
| SCALE_FIT | 6,144 | 639101 |
| SCALE_CAL | 3,072 | 639201 |
| TEST_A | 3,072 | 639301 |
| TEST_B | 3,072 | 639401 |

Each TEST parent has CONTROL, VELOCITY_NOISE_SHIFT and ADAPTATION_TIMESCALE_SHIFT. These are six dependent scenario sets from two independent parents.

**Uncertainty models** (location always μ = frozen Ridge forecast; Gaussian predictive law):

- **B_GROUP**: σ_raw = per lift × stratum RMS of SCALE_FIT residuals.
- **B_MAG** (primary comparator): per-lift ridge on `z = log((Y−μ)² + ε²)` with columns μ, log max(μ, 1 kg) and 12 stratum indicators.
- **H_HISTORY**: the same columns plus the 127 RES-616 participant-visible summaries. Family, ε, λ, standardization, calibration and clipping are identical, so the contrast isolates the added information.

With ε = 0.25 kg, λ = 0.05 (penalty on the mean squared error scale, intercept unpenalized, design standardized with SCALE_FIT statistics):

σ_raw = clip(exp(ẑ/2), 0.25, 100); c_l = clip(√mean_SCALE_CAL[(Y−μ)²/σ_raw²], 0.25, 4); σ_final = clip(c_l σ_raw, 0.25, 100).

This calibrates a **per-lift RMS scale only**; it does not prove conditional distributional calibration.

**Primary endpoint:** paired macro CRPS difference ΔCRPS = CRPS(H_HISTORY) − CRPS(B_MAG) on CONTROL for each parent, 1,000 stratified entity-cluster bootstrap replicates per parent. Screen: relative improvement ≥ 1% and 95% interval upper bound < 0 on **both** parents. The 1% value is a pragmatic screen, not a validated meaningful difference.

**Dispositions** (exact rules in `history_uncertainty.contract.decide`):

- `HISTORY_UNCERTAINTY_QUALIFIED_WITHIN_SYNTHETIC_WORLD`: screen met on both parents, H_HISTORY CRPS below B_GROUP, and every guardrail passes.
- `SCORE_GAIN_ONLY_CONDITIONAL_RELIABILITY_UNSUPPORTED`: screen met but a guardrail failed.
- `MIXED_OR_NOT_QUALIFIED`: every other completed outcome.
- `BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE`: Ridge unverifiable, a ceiling or rights failure, nonfinite values or an identity/denominator mismatch.

Guardrails (CONTROL, both parents unless stated; none are tunable after results): NLL deterioration vs B_MAG ≤ 0.005 nats; pooled and per-lift 90% coverage within [0.85, 0.95]; no lift × stratum cell with 90% coverage outside [0.80, 0.97]; 90% coverage within [0.84, 0.96] in each per-lift predicted-scale quintile; mean 90% width ≤ 1.10 × B_MAG; on all four shifted parent × scenario sets no CRPS reversal against B_MAG and pooled 90% coverage within [0.80, 0.97]; zero nonfinite values.

**Resources (hard, one shot):** one worker and thread, CPU only, ≤ 2,400 charged CPU s, ≤ 3,600 wall s, ≤ 2 GiB, zero retries, no automatic increase. Estimated about 250 CPU s (estimate, not a bound).

## Scientific review before execution

This is a self-review by the implementing agent against the cited sources; **no independent human peer review has occurred.**

1. **Ridge as fixed location.** It is the best RES-616 forecaster on CONTROL (6.64 vs 6.75 GRU, 9.02 persistence) and is deterministic, public and cheap. This is a design choice, not a claim that Ridge is optimal. A history effect on σ may differ under another μ.
2. **Magnitude control (repair applied).** Because `Y = E(1+ε)`, measurement SD is proportional to E, i.e. log σ is linear in log μ. A linear-in-μ term alone would understate the comparator and inflate any H_HISTORY benefit, so `log max(μ, 1 kg)` was added to B_MAG before freeze. This reason is design-based; no TEST data informed it.
3. **Interpretability.** H_HISTORY and B_MAG share one code path; only columns differ. The 127 summaries add 127 parameters per lift, so some gain may reflect capacity rather than "history"; the single λ and the independent calibration limit but do not remove that.
4. **Sample size and a sensitivity ceiling.** Gaussian oracle calculation: if the true log-scale heterogeneity left after magnitude has SD 0.10 / 0.15 / 0.20 / 0.25, even a perfect scale model improves CRPS by only about 0.25 / 0.56 / 0.99 / 1.54%. The 1% screen therefore demands large unexplained heterogeneity and near-perfect recovery. For scale, RES-616's Ridge-vs-GRU paired CRPS difference had a bootstrap half-width of about 0.04 kg on 3,072 entities. Uncertainty-model differences are expected to be smaller, so power is plausible but a negative result is likely and informative. Per-cell subgroup diagnostics (256 entities, coverage SE about 0.019) are exploratory.
5. **Gaussian approximation.** Conditional on E the noise is Gaussian with CV 4–5%; given x the predictive law is a convolution with a forecast error of unknown shape. PIT histograms and scale-conditional coverage are reported to expose misfit. P(Y<0) is reported, not imposed.
6. **Leakage.** Inputs are μ, log μ, plan indicators and the RES-616 visible summaries of days ≤ 223. Entity ids, E, C, parameters and future draws are excluded; tests perturb the future stream and assert identical features.
7. **Shifts.** The velocity shift changes only history velocity (targets identical); the adaptation shift changes the population distribution within the simulator's support. Neither refits anything.
8. **Decision statistics.** The intersection of two independent parent tests is conservative (each parent: 95% two-sided percentile interval upper bound below zero) and needs no multiplicity correction for the primary. Guardrails are descriptive and unadjusted.
9. **Resource enforcement.** CPU is limited by `RLIMIT_CPU`, a SIGXCPU handler, in-process budget checks (CPU, wall, peak RSS) and an independent `/usr/bin/time -v` wrapper command.
10. **Claims.** All conclusions are confined to this synthetic generator and these two parents.

**Statistical estimator note.** `E[log χ²₁] = −1.2704`, so exp(ẑ/2) is biased low for Gaussian errors. A constant shift in ẑ is absorbed exactly by c (unless c hits a clip, which is recorded), so no explicit correction is applied.

**Literature support.** Crossref confirmed the bibliographic records (title, journal, volume, pages, authors) of both references; the full texts were **not** re-read in this session, so the statements below rest on the author's prior knowledge of these papers. Strict propriety of the CRPS and logarithmic score: Gneiting & Raftery (2007), JASA 102, 359–378, DOI 10.1198/016214506000001437. Probabilistic calibration versus sharpness and PIT diagnostics: Gneiting, Balabdaoui & Raftery (2007), JRSS B 69, 243–268, DOI 10.1111/j.1467-9868.2007.00587.x. The ε, λ, guardrail and 1% values are **implementation assumptions**, not literature results. The CRPS closed form is checked numerically by the existing scoring tests.

## Results (single authorized run)

**Execution.** Owner-authorized, one campaign, clean checkout of `f6af0be73108a969214dd8f2577916493f6c45d1`, Python 3.12.13, NumPy 2.4.4, PyTorch 2.9.1+cpu (CPU only), Linux x86_64 under WSL2, one thread, authorization-record SHA-256 `18957b6e14b13fd78bbf873c86d1daa45c4e72332b4284426754aa40240bfce0` (record not committed). Exit status 0. `/usr/bin/time -v`: 135.02 s user + 5.11 s system = **140.13 CPU s**, **141.1 s wall**, **679,444 kB peak** (ceilings 2,400 s, 3,600 s, 2 GiB). A separate Ridge preflight used 87.6 CPU s (not part of the campaign). No retries.

**Ridge verification: Tier 1, exact published coefficient digest** (`e360665d…f9d9`, α = 0.01, FIT/DEV row-id hashes and all four DEV RMSE values identical). This establishes digest identity of the replayed fit **on this machine**. It is not independent replication on another machine: the same exact digest was not reproducible for the smoke fit on the GitHub runner. Further independent checks (preflight): the least-squares solution agrees with a normal-equation solve to 8.0e-13 in β and 3.9e-13 kg in DEV predictions; design standardization matches; the replayed RES-616 M1_C TEST_A CONTROL macro CRPS equals the published 6.637830247 exactly at nine decimals. No original per-row predictions exist to compare.

**Primary endpoint (CONTROL, macro CRPS, kg; lower is better).**

| Parent | B_GROUP | B_MAG | H_HISTORY | H − B_MAG | Relative | 95% paired bootstrap interval | Screen |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| TEST_A | 6.6943 | 6.5125 | 6.5367 | **+0.0242** | **+0.37%** (worse) | [+0.0180, +0.0308] | not met |
| TEST_B | 6.6288 | 6.4675 | 6.4859 | **+0.0185** | **+0.29%** (worse) | [+0.0119, +0.0249] | not met |

The frozen screen needs at least 1% *improvement* with the upper bound below zero on both parents; both bounds are above zero. The interval excludes zero in the harmful direction, so the machine label `distinguishable_below_screen` in `summary.json` means distinguishable from zero, **not** a small gain. Magnitude matters: B_MAG beats B_GROUP by 2.7% / 2.4%, and H_HISTORY beats B_GROUP by 2.4% / 2.2%.

**Reliability (CONTROL).**

| Parent | Model | NLL | 50% cov | 80% cov | 90% cov | 90% width (kg) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TEST_A | B_GROUP | 3.8685 | 0.554 | 0.823 | 0.899 | 39.79 |
| TEST_A | B_MAG | 3.7598 | 0.506 | 0.800 | 0.901 | 38.07 |
| TEST_A | H_HISTORY | 3.7719 | 0.511 | 0.804 | 0.902 | 38.87 |
| TEST_B | B_GROUP | 3.8602 | 0.559 | 0.826 | 0.903 | 39.79 |
| TEST_B | B_MAG | 3.7601 | 0.502 | 0.797 | 0.898 | 37.80 |
| TEST_B | H_HISTORY | 3.7699 | 0.508 | 0.799 | 0.901 | 38.59 |

- H_HISTORY NLL is worse than B_MAG by +0.0121 / +0.0098 nats, above the 0.005 guardrail on both parents (bootstrap intervals exclude zero).
- Pooled and per-lift 90% coverage are within the guardrail bands. This is **pooled** calibration; the model is not shown to be individually calibrated.
- Plan × horizon × lift cells (36 per parent, 256 entities each, unadjusted and exploratory): H_HISTORY 90% coverage ranges 0.844 to 0.945 (TEST_A) and 0.836 to 0.941 (TEST_B); one cell per parent is below 0.85 (squat, continue/28 and step_down/28); none falls outside the severe band [0.80, 0.97].
- Coverage by lift-specific predicted-scale quintile (across groups only): 0.879 to 0.932 (TEST_A), 0.867 to 0.940 (TEST_B); all inside [0.84, 0.96].
- PIT bin fractions for H_HISTORY lie between 0.090 and 0.105 (uniform = 0.100).
- Predicted-scale variation within a stratum and lift (SD of log σ) averages 0.32 for B_MAG and 0.35 for H_HISTORY, so the added variation is not accompanied by better scores.
- Counts: 3,072 rows scored in every one of 6 parent/scenario sets, 0 nonfinite values, no σ at either clip bound, no scale-calibration constant clipped (fitted c: B_MAG 1.80/1.77/1.84, H_HISTORY 1.83/1.79/1.86, near the log-χ² bias of about 1.89).

**Controlled shifts (no refit; dependent scenarios of each parent).**

| Parent | Scenario | B_GROUP | B_MAG | H_HISTORY | H − B_MAG | H_HISTORY 90% cov |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TEST_A | CONTROL | 6.6943 | 6.5125 | 6.5367 | +0.0242 | 0.902 |
| TEST_A | VELOCITY_NOISE | 6.7413 | 6.5673 | 6.5952 | +0.0279 | 0.886 |
| TEST_A | ADAPTATION_TIMESCALE | 6.7136 | 6.5337 | 6.5607 | +0.0269 | 0.906 |
| TEST_B | CONTROL | 6.6288 | 6.4675 | 6.4859 | +0.0185 | 0.901 |
| TEST_B | VELOCITY_NOISE | 6.6927 | 6.5401 | 6.5626 | +0.0225 | 0.879 |
| TEST_B | ADAPTATION_TIMESCALE | 6.6158 | 6.4562 | 6.4763 | +0.0201 | 0.902 |

- **Relative:** the ranking B_MAG < H_HISTORY < B_GROUP is identical in all six sets, and H − B_MAG is positive (worse for histories) in all six, widening somewhat under the velocity-noise shift.
- **Absolute:** B_MAG CRPS rises 0.84% / 1.12% under velocity noise and 0.33% / −0.17% under the adaptation shift (TEST_A / TEST_B); H_HISTORY rises 0.90% / 1.18% and 0.37% / −0.15%. TEST_B improves slightly under the adaptation shift, so shift effects are not uniformly harmful.
- H_HISTORY loses to B_MAG in all four shifted sets, failing the no-reversal guardrail. No claim of general out-of-distribution robustness is made.

**Disposition rule trace.** The primary screen failed on both parents, so the frozen rule returns `MIXED_OR_NOT_QUALIFIED`. Guardrails that also failed (irrelevant to the label here but recorded): NLL (both parents) and no-reversal under both shifts (both parents). All other guardrails passed.

### Interpretation

Within this synthetic world, forecast magnitude carries real scale information (the measurement SD is proportional to expressed performance), and a log-μ term captures it. Adding the 127 visible history summaries to that regression produced no incremental benefit under the frozen estimator and slightly degraded both CRPS and NLL, consistent with variance from extra parameters and a noisy log-squared-residual target. This does **not** prove histories carry no scale information; it shows this estimator, penalty and sample size could not extract any beyond magnitude. Good pooled coverage here is not evidence of individualized reliability, and no score gain exists to be separated from reliability. The 1% screen was demanding (see sensitivity note) and was not reinterpreted.

### Independent verification and limits

- `scripts/audit_history_uncertainty_results.py` reads only the saved aggregate outputs and reimplements the frozen rules from `protocol.json`: **135 checks, 0 failed** (output hashes, freeze and prediction seal chain, protocol digest, denominators, macro-versus-lift identities, every contrast recomputed from `scores.csv`, all guardrails and the final disposition). Result: [`evidence-audit.json`](../../results/studies/history_conditional_uncertainty/full/independent-audit/evidence-audit.json).
- Not independently recomputable: bootstrap intervals and PIT values, because per-entity scores are not published (rights boundary) and re-executing the scoring is forbidden by the one-shot rule. Their consistency was checked only against the point estimates (each interval brackets its estimate).
- The audit was written and run by the same agent that implemented the study; it is not independent human peer review.
- Levels of evidence kept distinct: exact coefficient digest identity (this machine), numerical equivalence of the least-squares solution (normal equations), deterministic source replay (pinned source hashes), and independent empirical replication (not performed).
- Limitations accepted by the owner: Tier 1/Tier 2 policy (Tier 2 was not needed), Ridge-only reconstruction, scale-conditional coverage across groups only, and a demanding exploratory 1% threshold.

## Implementation (verified with non-scientific fixtures only)

`src/powerlifting_state_research/history_uncertainty/` reuses the RES-616 cohort generator, Ridge code and shift transforms and the RES-615 scoring library without modifying them (their SHA-256 values are pinned in tests).

| Module | Role |
| --- | --- |
| `contract.py` | Frozen protocol, identities, seeds, Ridge reference, resource limits, guardrails and the pure `decide()` disposition |
| `replay.py` | Ridge-only replay of RES-616 FIT/DEV and identity verification (no GRU) |
| `heads.py` | B_GROUP, B_MAG, H_HISTORY on one estimator path; role guards; RMS-scale calibration |
| `study.py` | Authorization gate, freeze and prediction seals, single truth opening, scoring, paired bootstrap, diagnostics, resource budget, CLI |

The smoke profile (240/120/60/60 rows, seeds 639811 to 639841, 50 bootstrap replicates) is **non-scientific**. It verifies the machinery, including that the replayed smoke Ridge reproduces the committed RES-616 smoke digest. Its smoke "disposition" has no scientific meaning. Committed expected outputs: [`smoke/`](../../results/studies/history_conditional_uncertainty/smoke).

### Findings made during implementation

- **Digest fragility (confirmed on CI).** The published `beta_sha256` hashes `round(beta, 9)` bytes. Many coefficients belong to degenerate (constant) columns and are numerically zero; their sign depends on the BLAS kernel. The same smoke fit gave different digests with one versus several BLAS threads on the development machine, and the exact published smoke digest did **not** reproduce on the GitHub runner even with one thread, while the sign-normalized digest did. The exact digest is therefore machine-dependent evidence, not a universal test. The protocol states two tiers: tier 1 demands the exact published digest; tier 2 (explicit `--cross-environment` only) accepts matching α, row-id hashes and DEV RMSE for every α within 1e-6 kg, and the tier used is recorded in all outputs. A sign-normalized companion digest is always recorded; it cannot be compared with the published value because only the raw digest was published.
- **Protocol revision before authorization.** The protocol digest changed from `…18650c7858f4` (first commit) to `…3402d80af3db` solely to state these two tiers, after CI evidence and with no TEST information. Only the current digest can be authorized.
- **Constant-offset invariance.** A constant shift of the log-variance prediction is removed exactly by the calibration constant (tested), so the known log-χ² bias needs no explicit correction. Expect fitted c near 1.9 for B_MAG and H_HISTORY; that is the bias, not a defect, and a clipped c would be reported.

## Rights and provenance audit

All new code, tests and documents are project-authored (MIT, docs CC-BY-4.0) and registered in `provenance/PUBLIC_FILE_ORIGINS.csv`. Inputs are only the public generator, new seeds and public RES-616 reference identities. No athlete data, private bytes, checkpoints or historical parameters are read. Outputs committed are aggregate tables, SVG figures and hashes; cohort rows, Ridge coefficients and scale-head coefficients are not written (only SHA-256 digests). Reuse of RES-615/616 code is within the same repository and licence.

## Implementation self-review

Checked by the implementing agent, not independent human review: heads match an independent normal-equation solution; H_HISTORY columns extend the B_MAG columns exactly; features are unchanged under a different future-assessment stream; fitting/calibration reject TEST and forged roles; TEST truth is opened only after the prediction seal (spy test) and a mutated prediction cannot open it; a failure after truth opening is preserved and never rescored; every guardrail boundary is exercised; the full profile is refused without an owner record naming the digest; each CPU, wall and memory ceiling stops the run.

## Execution procedure (executed once)

1. The owner creates an authorization record, for example `authorization.json`: `{"protocol_digest": "sha256:3402d80af3db1ecf79682a6683a1f603f288010fe1dc486513f28ee587129c52", "owner_authorized_full_run": true}`.
2. From a clean locked checkout of the authorized commit: `uv sync --locked --all-groups --python 3.12`.
3. Run once, with independent resource observation:

   ```bash
   /usr/bin/time -v uv run --locked --no-sync python -m powerlifting_state_research.history_uncertainty \
     --profile full --authorization-record authorization.json \
     --out results/studies/history_conditional_uncertainty/full
   ```

4. The run verifies the Ridge replay first (blocking on mismatch), then fits and calibrates, writes the freeze and prediction seals, opens truth once, scores and writes the manifest. On any ceiling the run exits 3 with `BLOCKED_TECHNICAL_RIGHTS_OR_RESOURCE` and is not retried or extended. Compare `/usr/bin/time -v` maximum resident size and CPU times with the in-process `execution-receipt.json`.

Expected cost was about 250 CPU s (generation of roughly 30,000 entity-scenarios plus a 1,000-replicate bootstrap) against hard limits of 2,400 CPU s, 3,600 wall s and 2 GiB; the measured run used 140.1 CPU s.

## Limits

Synthetic assessment measurements only; no real-athlete validity, causation, physiological identification or G2 claim; no general robustness claim; statistical distinguishability is not practical significance.
