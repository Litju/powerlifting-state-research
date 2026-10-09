# PUBLIC_NATIVE IID Comparator Suite

This suite records six new standardized comparators for the frozen PUBLIC_NATIVE IID latent-capacity benchmark. Each method is `NEW_STANDARDIZED_COMPARATOR`; none is claimed as a recovered historical model. The RES-274 temporal expert is included as a separately identified, immutable reference.

## Frozen identities and protocol

| Record | Identity |
| --- | --- |
| Training protocol | `psr:training-protocol:public-native-comparator-suite@1.0.0~fdb64939b9e3` |
| BenchmarkSpec | `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~f99463d55ba0` |
| DatasetSpec | `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` |
| DatasetRealization | `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| Canonical evaluation | `psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8` |
| Prediction schema | `psr:prediction-schema:iid-latent-capacity-change-jsonl-row@1.0.0~cad5c74acd66` |

The protocol is exported from typed Python in [`training.py`](../../src/powerlifting_state_research/models/training.py) as [`public-native-comparator-suite.json`](../training-protocols/public-native-comparator-suite.json). It binds the 12,288-row TRAIN bytes (`914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550`), the 3,072-row validation bytes (`0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a`), the M3 participant-visible inputs, three run seeds (`383001`, `383002`, `383003`), one fixed configuration per method, and target-wise RMSE, MAE, R², and SRE (`ddof=0`). It creates no universal scalar score.

All new methods use the same entity-disjoint, support-preserving split of TRAIN: 9,984 fit rows and 2,304 internal selection rows. Its identity is `psr:internal-selection-split:public-native-temporal-expert@sha256:9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25`. Normalization statistics are fit on the fit rows only. The internal selection rows choose only the predeclared stopping step for the boosted stumps and neural model. The other new methods use fixed fits and do not select on those rows.

All fitted states and a fit seal were written and hashed before the runner opened canonical validation. The runner then evaluated all new predictions with RES-271. The fit seal records `canonical_validation_accessed=false`; the run manifest records that evaluation followed the seal. Integrity checks verify both records, every fitted-state hash, prediction hash, and EvaluationResult identity.

## Models

The common source is the M3 `TemporalModelInput`: origin day 224, observations through day 223, each lift's historical schedule, and the declared future plan. Predictions are the three latent capacity changes in kilograms. No method receives row IDs as features, target values as features, latent coordinates, or future realized information.

The dense feature vector has 127 values: five summaries (first, last, mean, population SD, and slope per seven-day observation step) for six standardized observation channels on each lift; three summaries for each of three schedule channels on each lift; and the six M3 plan/timing values plus a four-category plan one-hot. The channel statistics are fit on the 9,984 fit rows. Context and mechanistic methods use the same permitted input record but use their narrower declared features directly.

| Method | Model ID | Fixed rule | Fitted scalar parameters | Median fit seconds per seed |
| --- | --- | --- | ---: | ---: |
| Context mean | `psr:model:public-native-context-mean@1.0.0~0b76d1c62dae` | Fit target means for 12 declared-plan × horizon groups | 36 | 0.021 |
| Ridge | `psr:model:public-native-ridge@1.0.0~35f69cbae323` | Closed-form multi-output Ridge, α=1 | 384 | 0.013 |
| Boosted stumps | `psr:model:public-native-histogram-boosted-stumps@1.0.0~dbec1ea66506` | NumPy squared-error boosting; depth-one trees; 15 fit-row quantile cuts per feature; learning rate 0.05; all seeds used 40 rounds | 363 | 0.939 |
| Mechanistic midpoint | `psr:model:public-native-mechanistic-midpoint@1.0.0~9b52973798f4` | Published adaptation/suppression recurrence with six fixed population-midpoint constants and a day-223 baseline estimate | 0 | 0.006 |
| Compact neural | `psr:model:public-native-compact-neural@1.0.0~e0317f3b36a1` | 127 → 32 ReLU → 3; AdamW; learning rate 0.003; weight decay 0.0001; batch 256; selected epochs 13, 15, 21 | 4,195 | 0.763 |
| Mechanistic + Ridge residual | `psr:model:public-native-mechanistic-ridge-residual@1.0.0~e153e20558e2` | Mechanistic midpoint plus fit-only Ridge residual, α=1 | 384 | 3.488 |

The midpoint constants are reference stimulus 0.485, reference dose product 0.6, adaptation utilization 0.11, 28-day adaptation retention 0.525, suppression utilization 0.04, and suppression retention 0.625. This is a fixed-parameter mechanistic comparator; it is not a historical MAP reconstruction. The hybrid's small error changes do not establish a general benefit from residual correction.

The boosted-stump parameter count is 363 learned numeric values; its 120 split-feature selectors are reported separately as structure. All three seeds reached the predeclared 40-round maximum. The compact neural model selected epochs 13, 15, and 21 on internal selection data.

## Target-wise results

The following new-comparator values are arithmetic means over their three declared runs. Every per-seed result remains separately identified in the CSV and registry below; deterministic methods produce the same prediction bytes across run seeds. No standard errors or confidence intervals are claimed.

| Method | Target | RMSE (kg) | MAE (kg) | R² | SRE (`ddof=0`) |
| --- | --- | ---: | ---: | ---: | ---: |
| Context mean | Squat | 4.095616 | 2.632207 | 0.682828 | 0.563181 |
| Context mean | Bench press | 2.927671 | 1.901911 | 0.674223 | 0.570769 |
| Context mean | Deadlift | 5.106667 | 3.275178 | 0.668083 | 0.576122 |
| Ridge | Squat | 4.437993 | 2.941466 | 0.627582 | 0.610260 |
| Ridge | Bench press | 3.185413 | 2.121076 | 0.614338 | 0.621017 |
| Ridge | Deadlift | 5.527782 | 3.658255 | 0.611084 | 0.623632 |
| Boosted stumps | Squat | 4.661339 | 2.791983 | 0.589155 | 0.640972 |
| Boosted stumps | Bench press | 3.307625 | 1.994049 | 0.584177 | 0.644843 |
| Boosted stumps | Deadlift | 5.776726 | 3.405304 | 0.575265 | 0.651717 |
| Mechanistic midpoint | Squat | 3.623429 | 2.319977 | 0.751746 | 0.498251 |
| Mechanistic midpoint | Bench press | 2.537177 | 1.630308 | 0.755332 | 0.494639 |
| Mechanistic midpoint | Deadlift | 4.324416 | 2.760074 | 0.761982 | 0.487871 |
| Compact neural | Squat | 3.316625 | 2.219914 | 0.792003 | 0.456063 |
| Compact neural | Bench press | 2.319099 | 1.547669 | 0.795584 | 0.452123 |
| Compact neural | Deadlift | 4.084293 | 2.686785 | 0.787681 | 0.460780 |
| Mechanistic + Ridge residual | Squat | 3.587940 | 2.339115 | 0.756585 | 0.493371 |
| Mechanistic + Ridge residual | Bench press | 2.510873 | 1.657118 | 0.760379 | 0.489511 |
| Mechanistic + Ridge residual | Deadlift | 4.277962 | 2.768965 | 0.767069 | 0.482630 |

For context, the mean of the three immutable RES-274 seed results is RMSE 2.969516 / MAE 1.877696 / R² 0.833242 / SRE 0.408333 for squat; 1.915522 / 1.216180 / 0.860533 / 0.373444 for bench press; and 3.737979 / 2.358107 / 0.822155 / 0.421710 for deadlift. Its already-sealed ensemble result is RMSE 2.900956 / MAE 1.834434 / R² 0.840875 / SRE 0.398905 for squat; 1.870287 / 1.187341 / 0.867049 / 0.364625 for bench press; and 3.668192 / 2.316805 / 0.828739 / 0.413837 for deadlift. These values were read from existing RES-274 EvaluationResults; no expert predictions or metrics were regenerated.

Among the six new methods, the compact neural model has the lowest mean RMSE and SRE and highest mean R² on all three targets in this run. The context baseline beats Ridge and the fixed boosted-stump configuration on all four metrics for each target. The residual hybrid improves RMSE, R², and SRE over the mechanistic midpoint, while its MAE is slightly higher on each target. These are results for this frozen synthetic IID population, not a universal ranking.

## Complexity and compute

| Method | Fitted parameters | Fixed constants | Median validation prediction seconds per seed |
| --- | ---: | ---: | ---: |
| Context mean | 36 | 0 | 0.003 |
| Ridge | 384 | 0 | 0.002 |
| Boosted stumps | 363 | 0 | 0.004 |
| Mechanistic midpoint | 0 | 6 | 1.089 |
| Compact neural | 4,195 | 0 | 0.004 |
| Mechanistic + Ridge residual | 384 | 6 | 1.116 |

Training used CPU execution on Linux 6.18 WSL2, x86_64, with 8 logical CPUs, Python 3.12.13, NumPy 2.4.4, and PyTorch 2.9.1+cpu. Shared fit preprocessing took 7.937 seconds once; shared validation feature construction took 1.651 seconds once. Per-model fit and prediction medians above exclude those two shared steps. The exact CPU model was unavailable. RES-274 was trained under its sealed RTX A6000/CUDA environment; fit/inference durations are not present in the ingested expert results, so they are not filled in here.

## Artifact and claim boundaries

- [Machine-readable comparator registry](../registries/public-native-comparator-registry.json) binds all six model IDs, three fitted-instance IDs, prediction artifact identities, EvaluationResult identities, and immutable RES-274 references.
- [Per-seed target metrics](../../results/tables/public-native-comparator-frontier.csv) preserves all 66 method/seed/target rows, four metrics, parameter counts, and measured runtimes.
- [Run manifest](../../results/manifests/public-native-comparator-suite.json), [checksum index](../../results/manifests/public-native-comparator-suite-checksums.json), [fit seal](../../results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-comparator-suite/training-seal.json), and [internal split identity](../../results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-comparator-suite/internal-selection-split.json) support independent integrity checks.
- The RES-274 expert predictions, fitted/checkpoint identities, and EvaluationResults remain in their original paths and are verified byte-for-byte by the integrity suite.
- The [historical lineage table](historical-model-evidence-lineage.md) records the only supported historical family and the families that remain unsubstantiated.
- The historical temporal expert is bound to a scrambled-Sobol DatasetRealization and historical SRE evaluation. This suite is bound to the IID DatasetRealization and four-metric evaluation. Their raw scores are not directly comparable.
- All results are conditional on the public synthetic world's finite support and observation law. They do not establish real-athlete validity, causal training effects, latent-state identification, or broad distribution shift performance.
