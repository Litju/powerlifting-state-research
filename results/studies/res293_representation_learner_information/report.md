# RES-293 representation, learner, and information study

**Status: executed once; all 30 final states and prediction sets sealed; exploratory analysis complete.** This is a new public-native experiment under [RES-293 v0.2](../../../studies/res293_representation_learner_information/protocol.json), not a reconstruction of historical G1–G4 or an independent confirmation study.

## Scientific identity and scope

| Record | Identity |
|---|---|
| Protocol | `psr:study-protocol:res293-representation-learner-information@1.0.0~333eccbc9029` |
| Protocol digest | `sha256:333eccbc9029cd3f3f822fabab66d8515ee083eae99b322739723217cb81256b` |
| Freeze commit | [`f8caac59f316e46df7700ba453913be79a47119e`](https://github.com/Litju/powerlifting-state-research/commit/f8caac59f316e46df7700ba453913be79a47119e), directly after audited baseline `9f928748909f0d49860808c592c567e0e33bf021` |
| BenchmarkSpec / DatasetSpec | `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~f99463d55ba0` / `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` |
| Evaluation / analysis | `psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8` / `sha256:88a0eae1855fa2dc92c9046166e847500b3e02ad7c5428d2c414fe2cb43542dd` |
| Realization digest | `sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| TRAIN / validation SHA-256 | `914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550` / `0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a` |
| Fit / development split digest | `9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25` |

The canonical public IID bytes were reused. The receipt verifies the original manifest, schema, row and split membership, rights, and all 768 evaluation strata (four validation rows per stratum); no new population, split, seed, or dataset was introduced. The protocol records that this validation panel had been inspected before this study was selected, so all results are post-hoc and exploratory.

## Fixed procedures and execution

| Configuration | Input | Learner |
|---|---|---|
| C1 | S summary | L affine `874→3` |
| C2 | O ordered | L affine `874→3` |
| C3 | S summary, fixed reference | N `874→32→3`, ReLU |
| C4 | O ordered | N `874→32→3`, ReLU |
| C5 | S context only | N |
| C6 | S with assessment/load feature group omitted | N |

Five paired initialization seeds (`293201–293205`) and separate batch-order seeds (`293301–293305`) produced **30 CPU fits**. Every fit used 9,984 fit rows, batch size 256, 60 epochs, 2,340 updates, the frozen zero-bias initialization, fit-only scaling, and its final checkpoint. There was no best-checkpoint selection, development selection, tuning, GPU, or paid compute.

The process sealed all 30 final states and all development/validation predictions before the authority joined evaluation truth. The fitter's payload had no development or validation labels, and the worker never opened evaluation truth. The analysis opened truth only after the complete seal passed. The 30 states remain local and ignored; their hashes are preserved, and checkpoint weights are not distributed.

The campaign used 76.61 wall seconds and 76.25 CPU seconds; the slowest fit took 3.64 seconds. Maximum recorded worker RSS was 469,774,336 bytes (0.44 GiB), under the 16 GiB hard process ceiling. The outcome-blind F projection was 1,391,239,168 bytes (1.30 GiB), under the 12 GiB gate. At F, available RAM was 16,594,087,936 bytes (15.45 GiB), and the required projection-plus-reserve was 3,538,722,816 bytes (3.30 GiB). At launch, available RAM was 17,879,220,224 bytes (16.66 GiB). WSL guest memory was 20,973,219,840 bytes (19.54 GiB); cgroup memory and CPU quotas were unlimited. The required 2 GiB operating-system reserve and all runtime checks passed.

### Memory-gate amendment

The original attempt-5 bug was in the then-uncommitted `scripts/run_res293.py:148`: `MemAvailable_bytes >= 16 * 1024**3`. It treated the 16 GiB hard process RSS ceiling as a requirement for 16 GiB of free RAM. Attempt 5 recorded 17,154,805,760 bytes available (about 15.98 GiB) and failed E before F. This was an arbitrary admission threshold, **not an OOM or observed workload failure**. The single recorded engineering amendment separates the gates: E records memory and leaves admission pending; after F, projected peak must be at most 12 GiB, current `MemAvailable` and effective WSL/cgroup headroom must each cover projection plus a 2 GiB host reserve, and actual worker RSS remains subject to the distinct 16 GiB cap. Admission is rechecked immediately before launch and runtime memory is monitored. Regression tests cover the 15.98 GiB boundary, missing projection, projection above 12 GiB, insufficient available RAM, and insufficient effective container headroom.

## Canonical validation metrics

The table gives mean seed-wise validation RMSE in kg for each fixed procedure. It is a descriptive summary of this fit panel, not a universal leaderboard.

| Target | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---:|---:|---:|---:|---:|---:|
| Squat ΔC | 4.462 | 4.734 | 3.298 | 3.950 | 4.100 | 4.128 |
| Bench press ΔC | 3.202 | 3.340 | 2.334 | 2.762 | 2.930 | 2.979 |
| Deadlift ΔC | 5.548 | 5.792 | 4.129 | 4.872 | 5.117 | 5.200 |

The complete canonical RMSE, MAE, R², and SRE (`ddof=0`) values are in [canonical-metrics.csv](canonical-metrics.csv); the matching development diagnostics are in [development-metrics.csv](development-metrics.csv). No secondary metric is treated as independent confirmation.

## All 21 primary target-wise contrasts

Each point estimate is the mean of the five paired seed-specific RMSE differences, in kg. The five-seed range is descriptive. The final column is the shared first-order multiplier envelope using 20,000 shared-entity draws, PCG64 seed 293901, and the `higher` quantile. Its common half-width is 0.243057 kg. **Sampling coverage is not qualified**; the envelope is not a confidence interval and does not support significance, equivalence, materiality, harm, or superiority classifications.

| Target | Contrast | Estimate kg | Five-seed range kg | Descriptive envelope kg |
|---|---|---:|---:|---:|
| Squat | `C2_minus_C1` | 0.272 | [0.210, 0.386] | [0.029, 0.515] |
| Squat | `C4_minus_C3` | 0.653 | [0.598, 0.779] | [0.409, 0.896] |
| Squat | `C3_minus_C1` | -1.164 | [-1.216, -1.114] | [-1.407, -0.921] |
| Squat | `C4_minus_C2` | -0.784 | [-0.902, -0.622] | [-1.027, -0.541] |
| Squat | `encoding_by_learner_interaction` | 0.381 | [0.246, 0.546] | [0.137, 0.624] |
| Squat | `C3_minus_C5` | -0.802 | [-0.837, -0.758] | [-1.045, -0.559] |
| Squat | `C3_minus_C6` | -0.830 | [-0.854, -0.790] | [-1.073, -0.587] |
| Bench press | `C2_minus_C1` | 0.138 | [0.116, 0.163] | [-0.105, 0.381] |
| Bench press | `C4_minus_C3` | 0.428 | [0.330, 0.489] | [0.185, 0.671] |
| Bench press | `C3_minus_C1` | -0.868 | [-0.882, -0.826] | [-1.111, -0.625] |
| Bench press | `C4_minus_C2` | -0.578 | [-0.612, -0.502] | [-0.821, -0.335] |
| Bench press | `encoding_by_learner_interaction` | 0.289 | [0.214, 0.372] | [0.046, 0.532] |
| Bench press | `C3_minus_C5` | -0.596 | [-0.612, -0.550] | [-0.839, -0.353] |
| Bench press | `C3_minus_C6` | -0.645 | [-0.660, -0.601] | [-0.888, -0.402] |
| Deadlift | `C2_minus_C1` | 0.243 | [0.161, 0.348] | [0.0002, 0.4863] |
| Deadlift | `C4_minus_C3` | 0.742 | [0.655, 0.798] | [0.499, 0.985] |
| Deadlift | `C3_minus_C1` | -1.419 | [-1.436, -1.392] | [-1.662, -1.176] |
| Deadlift | `C4_minus_C2` | -0.920 | [-1.017, -0.824] | [-1.163, -0.677] |
| Deadlift | `encoding_by_learner_interaction` | 0.499 | [0.404, 0.568] | [0.256, 0.742] |
| Deadlift | `C3_minus_C5` | -0.988 | [-0.994, -0.977] | [-1.231, -0.745] |
| Deadlift | `C3_minus_C6` | -1.070 | [-1.094, -1.041] | [-1.313, -0.827] |

The exact rows and definitions are in [primary-contrasts.csv](primary-contrasts.csv); all **105 per-seed** contrast values are in [per-seed-primary-contrasts.csv](per-seed-primary-contrasts.csv). Training trajectories, influence diagnostics, and all 20,000 multiplier maxima are preserved in [training-loss.csv](training-loss.csv), [contrast-influence-diagnostics.csv](contrast-influence-diagnostics.csv), and [multiplier-maxima.csv](multiplier-maxima.csv).

On point estimates, ordered input had higher RMSE than summary input in all six lift-by-learner comparisons; N had lower RMSE than L in all six lift-by-encoding comparisons; and full S had lower RMSE than context-only and assessment/load-omitted controls for each lift. These are differences between the named finite-budget procedures. L is not an optimized linear frontier, so these findings do not establish that nonlinear architecture is necessary. C5 and C6 also do not establish information-theoretic necessity or an independent sensor mechanism.

## Interpretation and limits

- The primary target is the existing `ΔC` forecast in kg at origin day 224. Results condition on one fixed synthetic IID realization, its inspected evaluation panel, one fixed internal split, and the five analyzed fits.
- The design is not retrospectively preregistered; it is exploratory and does not establish independent confirmation, population-of-seeds coverage, or fresh-data/split uncertainty.
- The multiplier envelope is an uncalibrated descriptive diagnostic. No p-values, calibrated coverage, equivalence margins, material-benefit labels, or confirmatory superiority claims are reported.
- Equal rows/updates do not equalize optimization adequacy, effective capacity, FLOPs, or convergence. The study does not establish an optimal simple-model frontier, nonlinear necessity, causal information necessity, global identification, human-athlete validity, or coaching efficacy.
- Negative, null, and inconclusive findings are retained. A point estimate or envelope position is not itself a decision classification.

## Evidence and reproducibility

[Protocol freeze](../../../studies/res293_representation_learner_information/protocol-freeze.json), [D/E/Q/F receipts](../../../studies/res293_representation_learner_information/qualification/pre-fit-qualification.json), [execution receipt](execution-receipt.json), [analysis receipt](analysis-receipt.json), [seal manifest](seal-manifest.json), and [prediction seal index](prediction-seal-index.csv) bind the run. All ten analysis-output hashes were rechecked; the sealed run verified 30 state artifacts and 122 sealed artifacts, and the recorded point contrasts recomputed consistently from the canonical RMSE rows. The 21 contrast rows, 105 seed rows, and 90 target-metric rows passed structural checks.

Attempts 1–5 remain preserved. During publication-path cleanup, one requalification stopped at E because the required one-thread environment variables were absent from the invocation; another stopped at F because Bubblewrap could not create the nonexistent `/sandbox` mountpoint. Neither failure launched a fit. The final implementation uses an existing isolated `/run` mountpoint, and the final recorded D/E/Q/F pass was made against that source. These receipts are retained in the preservation bundle. The public copies redact only machine-specific absolute paths and carry the original receipt SHA-256 values; byte-identical originals remain in the local ignored preservation area.

These checks are **hash verification and result-consistency checks**, not a new numerical replay of the scientific campaign and not independent scientific approval. The exact private state bytes are withheld; their hashes and fit receipts remain. Fresh execution requires the frozen locked environment, the exact canonical bytes or deterministic reconstruction of that same realization, and the one-shot D/E/Q/F workflow. See [repository reproduction instructions](../../../docs/reproducibility.md) and [protocol](../../../studies/res293_representation_learner_information/protocol.json). The final D/E/Q/F PASS is recorded in [pre-fit-qualification.json](../../../studies/res293_representation_learner_information/qualification/pre-fit-qualification.json); the earlier attempts and path-redacted public copies are indexed in [preserved-receipts.json](../../../studies/res293_representation_learner_information/qualification/preserved-receipts.json).
