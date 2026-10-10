# RES-283 model-ranking stability and comparability

Analysis identity: `psr:analysis:res283-public-native-model-ranking-stability-v1@sha256:313e781f2a7454c1e9068c9de7982f63cd088ea52db1c8d687f1c2016f44a010`.

## Admissible scope

One within-version comparison is admissible: the saved public-native IID model panel under one DatasetRealization and one canonical RES-271 evaluation. It contains 22 fitted-instance or ensemble candidates, three target QOIs, and 3072 unique prediction row keys. The three public-native fit seeds remain separate. No model was trained and no prediction was regenerated.

The other eight benchmark versions have no public historical fitted-model panel, row-level predictions, and matching evaluation results. Their within-version rankings are `UNSUPPORTED_BY_EVIDENCE`. All 36 cross-version pairs retain the RES-281 decision `REJECTED_FOR_NUMERICAL_COMPARISON`; no historical rank statistic is calculated.

The candidate unit is a fitted instance. Temporal-expert seed instances and the separately identified ensemble are distinct candidates. Seed labels on deterministic comparator families are repeated deterministic executions, not independent training replications.

## Frozen IID target-wise rankings

Ranks are per target and metric, rank 1 is best, and exact ties receive average ranks. RMSE, MAE, and SRE(ddof=0) minimize; R² maximizes. No scalar or cross-target aggregate ranking is formed.

### squat_delta_capacity_kg

- **RMSE** — rank 1: public-native-temporal-expert:ensemble (2.90096); full ordering is in the target-wise ranking CSV.
- **MAE** — rank 1: public-native-temporal-expert:383003 (1.83388); full ordering is in the target-wise ranking CSV.
- **R²** — rank 1: public-native-temporal-expert:ensemble (0.840875); full ordering is in the target-wise ranking CSV.
- **SRE(ddof=0)** — rank 1: public-native-temporal-expert:ensemble (0.398905); full ordering is in the target-wise ranking CSV.

### bench_press_delta_capacity_kg

- **RMSE** — rank 1: public-native-temporal-expert:ensemble (1.87029); full ordering is in the target-wise ranking CSV.
- **MAE** — rank 1: public-native-temporal-expert:ensemble (1.18734); full ordering is in the target-wise ranking CSV.
- **R²** — rank 1: public-native-temporal-expert:ensemble (0.867049); full ordering is in the target-wise ranking CSV.
- **SRE(ddof=0)** — rank 1: public-native-temporal-expert:ensemble (0.364625); full ordering is in the target-wise ranking CSV.

### deadlift_delta_capacity_kg

- **RMSE** — rank 1: public-native-temporal-expert:ensemble (3.66819); full ordering is in the target-wise ranking CSV.
- **MAE** — rank 1: public-native-temporal-expert:ensemble (2.3168); full ordering is in the target-wise ranking CSV.
- **R²** — rank 1: public-native-temporal-expert:ensemble (0.828739); full ordering is in the target-wise ranking CSV.
- **SRE(ddof=0)** — rank 1: public-native-temporal-expert:ensemble (0.413837); full ordering is in the target-wise ranking CSV.

## Fit-seed stability

RES-281's original public-native model-ranking-instability result remains `INCONCLUSIVE` (`psr:audit-result:iid_latent_capacity_change_with_transient_expression_forecasting-model_ranking_instability@1.0.0~1fc848142265`): Existing per-seed EvaluationResults yield target-wise RMSE ranks, but three seeds and no predeclared rank-stability margin do not resolve stability.
RES-281's original public-native baseline-domination result also remains `INCONCLUSIVE` (`psr:audit-result:iid_latent_capacity_change_with_transient_expression_forecasting-baseline_domination@1.0.0~b98e2eb0b9d3`): The existing M4 comparator and immutable expert results support a target-wise descriptive Pareto frontier, but no practical margin or paired uncertainty method resolves domination.

Fit-seed ranks compare the same seven model families within each fit-seed panel; the separately identified expert ensemble is excluded from seed panels. The three temporal-expert and compact-neural fit seeds are distinct saved fits. Their seed-wise rank ranges are descriptive with n=3. Context mean, Ridge, boosted stumps, mechanistic midpoint, and mechanistic-plus-Ridge predictions are exact repeats across seed labels; their zero rank range is not evidence from independent fit replications. Dataset-seed, split-seed, and distribution-shift stability were not estimated.

- `compact_neural`: observed rank range spans 0–0 positions across target/metric cells; THREE_DISTINCT_FIT_SEEDS_DESCRIPTIVE_ONLY (12 cells).
- `context_mean`: observed rank range spans 0–0 positions across target/metric cells; DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS (12 cells).
- `histogram_boosted_stumps`: observed rank range spans 0–0 positions across target/metric cells; DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS (12 cells).
- `mechanistic_midpoint`: observed rank range spans 0–0 positions across target/metric cells; DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS (12 cells).
- `mechanistic_ridge_residual`: observed rank range spans 0–0 positions across target/metric cells; DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS (12 cells).
- `public-native-temporal-expert`: observed rank range spans 0–0 positions across target/metric cells; THREE_DISTINCT_FIT_SEEDS_DESCRIPTIVE_ONLY (12 cells).
- `ridge`: observed rank range spans 0–0 positions across target/metric cells; DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS (12 cells).

- `squat_delta_capacity_kg` RMSE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `squat_delta_capacity_kg` MAE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `squat_delta_capacity_kg` R²: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `squat_delta_capacity_kg` SRE(ddof=0): 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `bench_press_delta_capacity_kg` RMSE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `bench_press_delta_capacity_kg` MAE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `bench_press_delta_capacity_kg` R²: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `bench_press_delta_capacity_kg` SRE(ddof=0): 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `deadlift_delta_capacity_kg` RMSE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `deadlift_delta_capacity_kg` MAE: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `deadlift_delta_capacity_kg` R²: 0 pairwise order reversals across 63 non-tied seed-pair comparisons.
- `deadlift_delta_capacity_kg` SRE(ddof=0): 0 pairwise order reversals across 63 non-tied seed-pair comparisons.

## Metric-dependent rank changes

The metric-pair summary gives exact pairwise rank reversals and ties by target. For a fixed target and sample, canonical R² and SRE(ddof=0) are monotone transforms of RMSE, so their model rankings should coincide. RMSE-versus-MAE reversals reflect different error weighting; they do not establish a universal best model.

- `squat_delta_capacity_kg` RMSE vs MAE: 20 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `squat_delta_capacity_kg` RMSE vs R²: 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `squat_delta_capacity_kg` RMSE vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `squat_delta_capacity_kg` MAE vs R²: 20 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `squat_delta_capacity_kg` MAE vs SRE(ddof=0): 20 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `squat_delta_capacity_kg` R² vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` RMSE vs MAE: 18 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` RMSE vs R²: 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` RMSE vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` MAE vs R²: 18 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` MAE vs SRE(ddof=0): 18 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `bench_press_delta_capacity_kg` R² vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` RMSE vs MAE: 19 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` RMSE vs R²: 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` RMSE vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` MAE vs R²: 19 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` MAE vs SRE(ddof=0): 19 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).
- `deadlift_delta_capacity_kg` R² vs SRE(ddof=0): 0 reversals among 216 pairs ordered on both metrics (ties: 15 / 15).

## Pareto trade-offs

- `squat_delta_capacity_kg`: 2 Pareto-front candidates (public-native-temporal-expert:383003, public-native-temporal-expert:ensemble); families: public-native-temporal-expert.
- `bench_press_delta_capacity_kg`: 1 Pareto-front candidates (public-native-temporal-expert:ensemble); families: public-native-temporal-expert.
- `deadlift_delta_capacity_kg`: 1 Pareto-front candidates (public-native-temporal-expert:ensemble); families: public-native-temporal-expert.

Dominance uses RMSE↓, MAE↓, and SRE(ddof=0)↓ with R²↑ and exact values. Seed instances are listed separately in the Pareto CSV. R² and SRE do not add independent objectives beyond RMSE for a fixed target population.
The point-estimate Pareto frontier is descriptive; RES-281's baseline-domination state remains INCONCLUSIVE because no practical margin or paired uncertainty method was predeclared.

## Paired uncertainty evidence

All candidate prediction artifacts share 3072 row IDs and the canonical EvaluationResults bind 3072 samples, but tracked public inputs do not contain validation target truth rows or the row-to-entity mapping. The predeclared 2000-replicate entity bootstrap was not run. All 264 target/candidate/metric uncertainty cells are `UNSUPPORTED_BY_EVIDENCE`, with inference `INCONCLUSIVE`; no rows were regenerated.


## Historical evidence-gap result

Cross-version matrix: 36 rejected, 0 admissible, 0 numerically analyzed. Every pair lacks verified common support and paired scores; the failed semantic conditions and source decisions are retained in the matrix. This is unavailable evidence, not demonstrated ranking instability.

No chronology-based ranking improvement or regression can be inferred. Scrambled-Sobol historical values are not combined with public-native IID values.

## Uncertainty and limitations

- Three stochastic fit seeds provide only a small descriptive sample; deterministic repeats add no independent training variation.
- Paired residual and entity-cluster uncertainty could not be estimated: the tracked repository has neither validation truth rows nor the row-to-entity mapping. Prediction row keys alone do not identify athletes.
- No practical decision threshold was frozen for meaningful rank differences. Fit-seed rank dispersion and point rankings are descriptive; the existing RES-281 stability and domination statuses remain `INCONCLUSIVE`.
- Historical evaluation identities, paired populations, and fitted-model outputs are missing for the eight historical versions. Their rankings are unsupported, not unstable.
- Results do not establish correspondence to real-athlete outcomes or any model's external validity.

## RES-284 handoff boundary

RES-284 may prepare publication from the public-native within-version descriptive results and the negative historical-comparability finding. It must not report historical rankings, cross-version stability coefficients, model improvement over benchmark chronology, or raw historical comparisons. Keep source-level expert prediction rights marked NOASSERTION and do not publish private historical data, checkpoints, or outputs. Resolving the historical claims requires rights-cleared matched rows, executable native adapters, the same fitted model panel, and a common evaluation/support contract.

Runnable companion notebook: `analysis-notebook.ipynb`.
