# Public surrogate reconstruction: RES-290

Study identity: psr:study:public-surrogate-reconstruction-public-native@1.0.0~e71ab192551c
Protocol SHA-256: sha256:e71ab192551cb8c80ad28402a11441546a94672bd72375f9f41b29dd86c5480e
Study realization: psr:dataset-realization:public-surrogate-reconstruction-public-native@sha256:d6543d9fe0143d1fbb0134d6bb841b5e7c72cc01bc4a9e9901c632d574ac56ac
Realization digest: sha256:d6543d9fe0143d1fbb0134d6bb841b5e7c72cc01bc4a9e9901c632d574ac56ac
Evaluation: res290-public-surrogate-evaluation-v1

This is a new public-native experiment, not a historical G3 reproduction. Historical G3 survives only as metadata and aliases; no original G3 method, data, fitted model, or score is recovered. See [historical lineage](../../../studies/public_surrogate_reconstruction/historical-lineage.md).

## Historical and scientific claim boundary

G3 / ALI-543 and pl_study_g3_public_surrogate identify a retrospective study home. The original study question, protocol, participant rows, model, evaluation, and quantitative results are unsupported by surviving public evidence. RES-287 and RES-289 are independent public-native studies with their own identities and results. Their scores and historical G3 are not compared here.

Predictive utility, observable-record distribution fidelity, matched conditional-response fidelity, finite-sample coverage, memorization, structural equivalence, and system identification are separate claims. Agreement on a finite predictive or distributional metric does not establish source-generator recovery, latent-state identification, causal equivalence, or transfer to real athletes.

## Frozen design and firewall

The protocol was frozen at starting main 31ad65bdd4e19ef80243fbdbf507097d70f1776b before any RES-290 realization was generated. It binds the public-native world, participant row contract, and M4/M5 references in [frozen evidence](../../../studies/public_surrogate_reconstruction/frozen-evidence.json).

Fitting has 384 rows, development 192, and each factual test population 384, balanced across 12 plan-by-horizon cells. Test A and test B use independent population and observation draws. A paired noise realization reuses test-A population and schedules with an independent observation seed. The matched set has 64 authority-only entities across four declared plans and three horizons.

The learner receives only public fields and train/development target labels. Test rows have no target fields in the learner payload. Fitting runs in an isolated Python subprocess from a staged learner module; imports outside NumPy and the Python standard library are rejected, and file, network, repository-import, and subprocess events are blocked. The authority keeps truth and matched-entity keys outside the payload, seals prediction bytes, then scores. The [payload audit](learner-input-audit.json) records the exact request digest, source, split counts, and firewall outcome.

## Methods and fitted identities

The empirical baseline resamples complete participant-visible fitting records with replacement within plan-by-horizon cells and predicts the cell mean. Summary Ridge uses predeclared visible summaries. Sequence RFF Ridge uses ordered observation and schedule fields with 128 generic random Fourier features and a fixed nine-configuration development search. Both conditional models return means only. Neither generates observable records. No source equation, latent coordinate, hidden state, exact population bound, historical artifact, or canonical M3/M4 fitted state enters learner fitting.

| Family | Fitted instance | Selected alpha | Selected gamma | Fit-state scalars |
|---|---|---:|---:|---:|
| empirical_finite_support_resampler_v1 | psr:fitted-instance:res290-empirical-finite-support-resampler@1.0.0~8c8ef9a13f8b | not tuned | not tuned | 0 |
| sequence_rff_ridge_v1 | psr:fitted-instance:res290-sequence-rff-ridge@1.0.0~fc1e80894960 | 10.0 | 0.01 | 62848 |
| summary_ridge_v1 | psr:fitted-instance:res290-summary-ridge@1.0.0~19d8f6aae2aa | 100.0 | not tuned | 174 |

The exact fit states and input hashes are in [fitted models](fitted-models.json) and [fitted identities](fitted-model-identities.json). Every failed tuning configuration and any family-level fit failure is in [method-failures.json] and [development-selection.json]. The empirical generator is intentionally a row-copy baseline.

## Predictive utility

The table pools the three horizons with equal row counts, separately by population, method, and lift. Per-horizon RMSE, MAE, signed bias, and entity-bootstrap intervals for all three metrics remain in [predictive-metrics.csv](predictive-metrics.csv); paired method uncertainty is in [paired-model-comparisons.csv](paired-model-comparisons.csv). No target or lift is collapsed into a universal score.

| Population | Method | Lift | n | Pooled RMSE (kg) | Mean MAE (kg) | Mean bias (kg) |
|---|---|---|---:|---:|---:|---:|
| test_a | empirical_finite_support_resampler_v1 | bench_press | 384 | 3.0432 | 1.9434 | -0.1752 |
| test_a | empirical_finite_support_resampler_v1 | deadlift | 384 | 5.0498 | 3.2189 | -0.2490 |
| test_a | empirical_finite_support_resampler_v1 | squat | 384 | 3.9626 | 2.4950 | 0.2013 |
| test_a | sequence_rff_ridge_v1 | bench_press | 384 | 6.2221 | 4.7307 | 0.0003 |
| test_a | sequence_rff_ridge_v1 | deadlift | 384 | 10.1724 | 7.8247 | -0.3855 |
| test_a | sequence_rff_ridge_v1 | squat | 384 | 7.9342 | 5.9270 | 0.1633 |
| test_a | summary_ridge_v1 | bench_press | 384 | 3.3688 | 2.2998 | -0.2698 |
| test_a | summary_ridge_v1 | deadlift | 384 | 5.2512 | 3.4842 | -0.3179 |
| test_a | summary_ridge_v1 | squat | 384 | 4.5354 | 2.8281 | 0.1140 |
| test_a_noise_replicate | empirical_finite_support_resampler_v1 | bench_press | 384 | 3.0432 | 1.9434 | -0.1752 |
| test_a_noise_replicate | empirical_finite_support_resampler_v1 | deadlift | 384 | 5.0498 | 3.2189 | -0.2490 |
| test_a_noise_replicate | empirical_finite_support_resampler_v1 | squat | 384 | 3.9626 | 2.4950 | 0.2013 |
| test_a_noise_replicate | sequence_rff_ridge_v1 | bench_press | 384 | 6.1748 | 4.5921 | 0.1555 |
| test_a_noise_replicate | sequence_rff_ridge_v1 | deadlift | 384 | 10.4514 | 7.9924 | 0.0223 |
| test_a_noise_replicate | sequence_rff_ridge_v1 | squat | 384 | 8.3506 | 6.1715 | 0.5550 |
| test_a_noise_replicate | summary_ridge_v1 | bench_press | 384 | 3.3033 | 2.2575 | -0.3382 |
| test_a_noise_replicate | summary_ridge_v1 | deadlift | 384 | 5.2176 | 3.4745 | -0.4294 |
| test_a_noise_replicate | summary_ridge_v1 | squat | 384 | 4.4523 | 2.7503 | 0.0943 |
| test_b | empirical_finite_support_resampler_v1 | bench_press | 384 | 3.3054 | 2.1167 | -0.2436 |
| test_b | empirical_finite_support_resampler_v1 | deadlift | 384 | 5.5096 | 3.5026 | -0.3579 |
| test_b | empirical_finite_support_resampler_v1 | squat | 384 | 4.4582 | 2.8928 | -0.2243 |
| test_b | sequence_rff_ridge_v1 | bench_press | 384 | 6.5342 | 4.7439 | -0.0035 |
| test_b | sequence_rff_ridge_v1 | deadlift | 384 | 10.8175 | 8.0486 | 0.0173 |
| test_b | sequence_rff_ridge_v1 | squat | 384 | 8.4215 | 6.3195 | -0.1233 |
| test_b | summary_ridge_v1 | bench_press | 384 | 3.8253 | 2.5879 | -0.3029 |
| test_b | summary_ridge_v1 | deadlift | 384 | 6.0648 | 3.9152 | -0.3563 |
| test_b | summary_ridge_v1 | squat | 384 | 4.6613 | 2.9792 | -0.2430 |

Across 54 conditional-model/lift/horizon/population cells, 1 had lower point RMSE than the empirical plan-by-horizon mean. This point count does not establish an inferential improvement; the paired bootstrap contrasts below keep resolved and inconclusive cells separate.

Figure: [predictive fidelity](predictive-fidelity.svg); the machine-readable table is the source alternative.

## Observable-record distribution and memorization

Only the empirical resampler generates complete observable records. Its output is compared with test-A inputs using field-wise 1-Wasserstein distance normalized by each fitting-sample standard deviation. Correlation discrepancy uses the 58 predeclared visible summary features. Plan and horizon frequencies are measured separately.

| Lift | Channel | W1 / training SD | 95% entity-bootstrap interval |
|---|---|---:|---:|
| squat | assessment_kg | 0.0753 | [0.0596, 0.1359] |
| squat | prescribed_load_kg | 0.0757 | [0.0602, 0.1367] |
| squat | velocity_mps | 0.1084 | [0.1153, 0.1367] |
| bench_press | assessment_kg | 0.0507 | [0.0523, 0.1380] |
| bench_press | prescribed_load_kg | 0.0506 | [0.0528, 0.1380] |
| bench_press | velocity_mps | 0.1155 | [0.1220, 0.1433] |
| deadlift | assessment_kg | 0.0908 | [0.0671, 0.1552] |
| deadlift | prescribed_load_kg | 0.0909 | [0.0678, 0.1550] |
| deadlift | velocity_mps | 0.1050 | [0.1121, 0.1337] |

| Statistic | Value | 95% entity-bootstrap interval |
|---|---:|---:|
| history_schedule_combination_total_variation | 0.2370 | [0.2370, 0.3178] |
| plan_horizon_total_variation | 0.0000 | [0.0000, 0.0000] |
| visible_summary_correlation_frobenius | 3.2744 | [3.5131, 4.2036] |

The empirical generator produced 384 records from 245 unique fitting donors. Exact donor-copy fraction was 1.000; duplicate draw fraction was 0.362. Exact fitting/test-A visible-record overlap was 0 of 384. These measurements quantify finite-sample reuse; they do not recover a generating world.

Figure: [observable-distribution fidelity](observable-distribution.svg), with uncertainty by held-out entity.

## Support coverage, sampling geometry, and noise

Within test A's plan-by-horizon cells, the mean fraction of observed history-schedule combinations also present in fitting was 0.427. Cell counts for fitting, development, each test population, the paired noise draw, and matched support are in [support-coverage.csv](support-coverage.csv).

The [sampling-geometry table](sampling-geometry.csv) reports held-out rows outside fitting-sample extrema and nearest fitting-row distances using the frozen 58 visible summary features. These diagnose this finite sample only; they do not estimate population bounds. The protocol scores no unsupported extrapolation state.

| Set | Rows outside training sample extrema | Fraction | Median nearest training distance | 95th percentile |
|---|---:|---:|---:|---:|
| development | 13.0000000000 | 0.068 | 5.153 | 6.267 |
| test_a | 23.0000000000 | 0.060 | 5.156 | 6.288 |
| test_b | 32.0000000000 | 0.083 | 5.249 | 6.563 |
| test_a_noise_replicate | 27.0000000000 | 0.070 | 5.181 | 6.478 |
| matched | 84.0000000000 | 0.109 | 5.193 | 6.406 |

Observation-noise sensitivity uses the test-A population and schedules with a new native observation seed. 0 of 27 method/lift/horizon paired RMSE contrasts were resolved by their 95% entity-bootstrap intervals. Full results are in [noise-sensitivity.csv](noise-sensitivity.csv). This is not a different noise-scale test.

## Matched response and structural non-identification

The Evaluation Authority generated 81 matched response metric cells across supported plan contrasts, lifts, horizons, and methods. Each contrast holds synthetic entity, history, historical schedule, and observation noise fixed while varying one declared future plan. The learner sees each public query but not the matching key or truth. Results and entity-level uncertainty are in [matched-response.csv](matched-response.csv).

| Method | Lift | Matched-effect RMSE range across 9 plan/horizon cells (kg) |
|---|---|---:|
| empirical_finite_support_resampler_v1 | squat | [1.248, 8.464] |
| empirical_finite_support_resampler_v1 | bench_press | [1.436, 8.929] |
| empirical_finite_support_resampler_v1 | deadlift | [2.551, 12.546] |
| sequence_rff_ridge_v1 | squat | [2.836, 18.013] |
| sequence_rff_ridge_v1 | bench_press | [2.174, 15.897] |
| sequence_rff_ridge_v1 | deadlift | [3.888, 23.279] |
| summary_ridge_v1 | squat | [1.305, 10.001] |
| summary_ridge_v1 | bench_press | [1.378, 10.203] |
| summary_ridge_v1 | deadlift | [2.152, 13.555] |

The predeclared paired prediction contrasts found sequence RFF Ridge higher than Summary Ridge in 27 of 27 cells, with 27 resolved by the entity-bootstrap intervals. Summary Ridge had higher RMSE than the empirical plan-by-horizon baseline in 9 of 27 cells; 18 cells were inconclusive.

The experiment did not demonstrate a pair of observationally similar conditional surrogates with different matched response surfaces. The two conditional model families were distinguishable on held-out prediction error; no practical equivalence margin was frozen. The structural non-identification question therefore remains inconclusive. Their different internals and finite public-statistic agreement do not identify or reproduce the source mechanism.

## Negative and inconclusive findings

See [negative-results.csv](negative-results.csv) for the claim register and [method-failures.json](method-failures.json) for failed methods/configurations. Historical G3 outcomes remain unsupported. Finite empirical resampling copies its donor support by construction. Predictive, marginal, or conditional agreement does not establish system identification. Off-support extrapolation and real-athlete or causal transfer were not evaluated. Intervals spanning zero remain inconclusive.

## Reproduction and provenance

Replay from the repository root with:

    uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction

Verify source hashes, output identities, learner isolation, and deterministic regeneration with:

    uv run --locked python -m powerlifting_state_research.studies.public_surrogate_reconstruction --check

The [study manifest](manifest.json), [artifact manifest](artifact-manifest.json), and [SHA-256 index](SHA256SUMS.txt) bind the report, tables, figures, realizations, fitted states, predictions, and truth to the protocol, realization, fitted models, evaluation, source, and redistribution rights. No private historical artifact was used.

RES-287 lineage and results: [study report](../observation_inversion/report.md), [RES-289 handoff](../observation_inversion/RES-289-handoff.md). RES-289 lineage and results: [study report](../target_sufficient_structural_reconstruction/report.md), [RES-290 handoff](../target_sufficient_structural_reconstruction/RES-290-handoff.md). Historical scores are not compared.
