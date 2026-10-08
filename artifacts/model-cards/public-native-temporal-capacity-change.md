# Public-Native Temporal Capacity-Change Model

## Model taxonomy

| Object | Identity |
| --- | --- |
| Historical model family | Three-lift shared temporal GRU with plan conditioning and cross-lift fusion |
| Historical fitted instance, seed 383001 | `psr:fitted-instance:historical-temporal-capacity-change-seed-383001@sha256:b41fd12298fffb44d86087198fbfec1151acef4f34d6446a8f40e249da1984fb` |
| Historical fitted instance, seed 383002 | `psr:fitted-instance:historical-temporal-capacity-change-seed-383002@sha256:6169d437ff152ecb75c5d3d9f2bc7b84d522d059e191faf10798bba8c81899a5` |
| Historical fitted instance, seed 383003 | `psr:fitted-instance:historical-temporal-capacity-change-seed-383003@sha256:7d2994106ae0ee33a44973f8550836ac099fdbf59c253d533da4f3c0424ad0c0` |
| Historical ensemble | `psr:ensemble:historical-three-seed-temporal-capacity-expert-mean@1.0.0~79afba062509` |
| Clean-room PUBLIC_NATIVE model specification | `psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f` |

The three historical fitted-instance IDs are RES-272 metadata handles bound to the preserved checkpoint hashes. Their checkpoint IDs are `CHECKPOINT:sha256:<same hash>`. The model family, fitted instances, checkpoints, ensemble, and PUBLIC_NATIVE model specification are separate objects.

The prior clean-room model ID `psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~47f177b3d989` is superseded. Its semantic payload incorrectly included the complete PUBLIC_NATIVE BenchmarkSpec identity; this was corrected before any production PUBLIC_NATIVE fitted instance, checkpoint, or training result existed. MODEL identity binds direct task/QOI and model-facing input/output semantics and is independent of BenchmarkSpec, EVALUATION, and DatasetRealization.

## Historical reconstruction

Evidence classes: the preserved M0 qualification/checkpoint metadata, M1 model and dataset identity maps, and the frozen architecture/training contracts. The preserved source-file hashes and checkpoint hashes were checked locally; no evidence files were copied into the public implementation.

The preserved detailed architecture contract and implementation establish a shared two-layer GRU family. A brief M1 identity label called it a temporal MLP; the detailed contract resolves that shorthand to a GRU with plan-conditioned state and gated cross-lift fusion.

Historical input sequences use the lift order **squat, bench, deadlift**, and 32 observations at days 6, 13, …, 223 in oldest-to-newest order. Each observation contains assessment kg, prescribed load kg, and velocity m/s. The model derives relative prescribed load (`prescribed_load / assessment`), assessment change, and velocity change; the first change in each sequence is zero. It reads the per-lift schedule segment covering each observation day.

The normalized history tensor is `[N, 3, 32, 10]`, float32, with these channels in order:

1. assessment kg, train-standardized per lift;
2. prescribed load kg, train-standardized per lift;
3. velocity m/s, train-standardized per lift;
4. relative prescribed load, train-standardized per lift;
5. assessment change kg, train-standardized per lift;
6. velocity change m/s, train-standardized per lift;
7. schedule dose divided by 1.2;
8. schedule intensity divided by 1.0;
9. dose × intensity divided by 1.2;
10. observation age `(224 - observation_day) / 224`.

All 32 history-mask entries are one. The supported representation has no padding. The plan category order is **CESSATION, CONTINUE, STEP_DOWN, STEP_UP**. Six plan/timing features are ordered as origin/224, horizon/56, dose/1.2, intensity/1.0, dose × intensity/1.2, and plan duration/56. The origin is day 224; supported horizons are 14, 28, and 56 days; the declared plan spans days 224–279.

The historical joint output order is squat, bench, deadlift latent capacity change in kg. The clean-room implementation maps those positions to the final M3 output names below.

The active inference path has these dimensions:

- history projection `10 → 64`, lift one-hot projection `3 → 8`, then LayerNorm(72);
- a two-layer batch-first GRU, input 72 and hidden size 64, shared across lifts, recurrent dropout 0;
- a per-lift 24-value structural summary encoded `24 → 32` with GELU, LayerNorm, and dropout 0.10;
- a four-category, 16-wide plan embedding plus six numeric features encoded `22 → 32`;
- bounded plan FiLM from 32 to 128 values, split into scale and offset with `0.25 × tanh`;
- a gated mean of the other two lift states, followed by shared cross-lift fusion `192 → 64`;
- one joint output head `224 → 128 → 64 → 3`, with GELU and dropout 0.10.

Activations are the GRU's sigmoid/tanh gates, GELU in the context and head blocks, sigmoid in cross-lift gates, tanh in bounded FiLM, and an unbounded identity output. Inference uses evaluation mode, so the 0.10 dropout modules are inactive.

The historical full training object has 135,470 trainable parameters. It also instantiates inactive ablation-only summary/control branches. The public implementation contains the active full-expert inference path and has 118,571 trainable parameters; the omitted inactive branches account for the difference. All 39 active public state-dict tensor names and shapes match historical checkpoint entries.

Historical input means and population standard deviations were fitted per lift over the six observation-derived channels on training rows only; standard-deviation floors are `1e-6`. Target means and population standard deviations were fitted per target on the same training split, with the same floor. The network predicts standardized target z values. The ensemble averages in that space and applies the per-target inverse transform once. The fitted numeric statistics remain in private historical evidence and are not copied into this public card or implementation.

### Historical training and runtime evidence

- Train split: 12,288 rows. Validation split: 3,072 rows; validation was used for checkpoint selection and qualification, not gradient fitting or normalization.
- Loss: equal-target mean squared error in train-standardized target space.
- Optimizer: AdamW, learning rate `3e-4`, weight decay `1e-4`, betas `(0.9, 0.999)`, epsilon `1e-8`; batch size 256.
- Batches shuffled, `drop_last=false`, no gradient accumulation, and zero data-loader workers. Schedule: five warmup epochs/240 steps, then cosine decay to `1e-5`, maximum 120 epochs/5,760 steps; global gradient norm clipped at 1.0.
- Checkpoint selection: lowest aggregate public-validation raw SRE; early stopping after a 20-epoch minimum, 20-epoch patience, and `1e-4` minimum improvement.
- Historical seeds and selected epochs: 383001/36, 383002/39, 383003/38.
- Recorded runtime: Ubuntu 22.04.5, CPython 3.13.15, PyTorch 2.9.1+cu128 (build `5811a8d7da873dd699ff6687092c225caffcf1bb`), NumPy 2.4.4, PyArrow 24.0.0, NVIDIA driver 580.126.09, CUDA 12.8, and cuDNN version 91002. Training used one NVIDIA RTX A6000 48 GB; BF16 was supported and used for eligible autocast operations, with FP32 target scaling, loss checks, clipping, validation predictions, and inverse transforms. Deterministic algorithms and cuDNN determinism were enabled; cuDNN benchmarking was disabled.
- Checkpoints are private PyTorch `.pt` serialized mappings containing `model_state`, input and target normalization, architecture/output-space metadata, and target order; optimizer state is excluded.
- The preserved final manifest reports qualification and aggregate SRE 0.3826914846 against its historical benchmark. RES-272 did not recompute that validation result.

### Historical benchmark and data binding

| Component | Historical identity |
| --- | --- |
| BenchmarkSpec mapping recorded by M1 | `psr:benchmark-spec:pl-response-v2-parsimonious-production-historical-mapping@1.0.0~548604c18ac7` |
| Current repository historical projection | `psr:benchmark-spec:latent-capacity-change-with-transient-expression-forecasting@1.0.0~fbfbe59eb0a8` |
| DatasetSpec | `psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@1.0.0~7098655518cd` |
| DatasetRealization | `psr:dataset-realization:pl-response-v2-parsimonious-production@sha256:1c986ed3dc23ab6202a7840e7e569099ec3d9eeef7ccf4643c4d07d9e0af56d5` |
| Evaluation | `psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f` (`EVAL_SRE_DDOF0_EQUAL_LIFT_MEAN_V2`) |

The preserved train and validation Parquet SHA-256 values are `8d5dff0b1c51030669ab5e6e8a54e42de2998d7cbecd3a185756df3d3f203b20` and `a23603a874673904a6338f79de780d2fba3d26caee5849198c363a31afc9c536`.

### Qualification state

| Dimension | Classification | Evidence |
| --- | --- | --- |
| Historical active architecture and tensor dimensions | EXACTLY_RECONSTRUCTED | Frozen architecture contract, preserved source hashes, and checkpoint tensor shapes |
| Input transforms and normalization rules | EXACTLY_RECONSTRUCTED | Preserved preprocessing source, normalization record, and fixed-input comparison |
| Historical training protocol and recorded software versions | EXACTLY_RECONSTRUCTED | Frozen training protocol and final runtime fingerprint |
| Historical BenchmarkSpec, DatasetSpec, DatasetRealization, and Evaluation binding | EXACTLY_RECONSTRUCTED | M1 identity map and preserved data-hash manifest |
| Three checkpoint identities and SHA-256 values | EXACTLY_RECONSTRUCTED | Direct file hashes match preserved manifest and M1 identity evidence |
| Clean-room per-seed forward behavior | FUNCTIONALLY_EQUIVALENT | CPU comparison on one fixed synthetic input; max absolute z-output differences were `1.49e-8`, `4.47e-8`, and `2.98e-8` |
| Ensemble operation | EXACTLY_RECONSTRUCTED | Equal mean of exactly three standardized predictions, followed by one inverse transform; synthetic comparison passed |
| Full historical object versus public active-path parameter count | PARTIALLY_RECONSTRUCTED | Public inference omits inactive historical ablation-only branches |
| Readiness receipt and independent readiness re-adjudication | UNRESOLVED | The receipt is absent from preserved evidence; the final manifest's readiness status is retained with this caveat |
| Checkpoint redistribution rights | UNRESOLVED | No separate rights clearance is recorded; checkpoint bytes remain private |

The fixed-input comparison used PyTorch 2.9.1+cpu against preserved checkpoints originally recorded with PyTorch 2.9.1+cu128. It used `rtol=1e-5`, `atol=1e-6`; the maximum observed difference was below `5e-8`. It did not evaluate historical checkpoints on the IID benchmark.

### Provenance aliases

These historical identifiers are aliases/provenance only; the scientific family name above is used in public descriptions.

- Historical model alias: `MODEL:pl_model_v2_temporal_expert_ensemble`.
- Historical architecture alias: `powerlifting.big3.expert.world_v2.lift_shared_temporal_state_plan_fusion.v1`.

| Seed | Checkpoint identity | SHA-256 |
| --- | --- | --- |
| 383001 | `CHECKPOINT:sha256:b41fd12298fffb44d86087198fbfec1151acef4f34d6446a8f40e249da1984fb` | `b41fd12298fffb44d86087198fbfec1151acef4f34d6446a8f40e249da1984fb` |
| 383002 | `CHECKPOINT:sha256:6169d437ff152ecb75c5d3d9f2bc7b84d522d059e191faf10798bba8c81899a5` | `6169d437ff152ecb75c5d3d9f2bc7b84d522d059e191faf10798bba8c81899a5` |
| 383003 | `CHECKPOINT:sha256:7d2994106ae0ee33a44973f8550836ac099fdbf59c253d533da4f3c0424ad0c0` | `7d2994106ae0ee33a44973f8550836ac099fdbf59c253d533da4f3c0424ad0c0` |

Each checkpoint SHA-256 was recomputed directly from its preserved file and matched both the preserved final manifest and M1 identity evidence.

## Clean-room PUBLIC_NATIVE specification

`MODEL_SPEC_ID` is computed from `MODEL_SPEC_SEMANTICS` in `src/powerlifting_state_research/models/temporal_expert.py`. It binds the task and QOI IDs, prediction-time input/output contract, participant-input representation, lift and observation order, channels, temporal topology, dimensions, plan/horizon encoding, preprocessing rules, and output semantics. It is independent of BenchmarkSpec, EVALUATION, and DatasetRealization. It does not bind fitted statistics, weights, seed, hardware, or result metrics.

`TemporalModelInput.from_forecast_inputs(row_id, inputs)` copies only origin, horizon, declared plan, and the ordered per-lift observation histories/schedules. `row_id` is retained only to construct the prediction artifact. Entity identifiers and target fields are not fields on `TemporalModelInput` or `TemporalModelBatch`.

The public input tensors are:

- `history`: `[N,3,32,10]`, float32, lift order squat/bench_press/deadlift, observation order day 6 through day 223;
- `history_mask`: `[N,3,32]`, float32, all ones;
- `plan_numeric`: `[N,6]`, float32, with the six plan/timing fields listed above;
- `plan_index`: `[N]`, int64, categories cessation/continue/step_down/step_up.

The model accepts no validation targets, latent coordinates or trajectories, future observations, transient state, future realized intervention deviations, athlete ID, or row ID as a tensor feature. Inputs must be complete and finite; malformed schedules, missing observations, unsupported plans/horizons, and padded histories are rejected.

`NormalizationStats` stores input and target means/scales separately from model weights. `fit_train` uses train rows only; inference receives the frozen stats object and never receives target rows. The public spec requires deterministic evaluation mode and inference mode under fixed weights and environment. Dropout is disabled during inference. The API emits `PredictionRow` values in kg, ordered exactly as:

1. `squat_delta_capacity_kg`
2. `bench_press_delta_capacity_kg`
3. `deadlift_delta_capacity_kg`

The public `predict_three_seed_ensemble` averages exactly three standardized outputs and performs one inverse transform after averaging.

Public fixture weight files bind `MODEL_SPEC_ID` to a strict state dictionary. Normalization statistics are stored separately; the load path rejects a model-spec mismatch.

The locked runtime uses PyTorch 2.9.1 with its CPU wheel for public CI and NumPy 2.4.4. Model-spec and inference code require no private runtime, experiment-management package, or network access.

## Firewall

- Historical source bytes are not public implementation source.
- Historical checkpoint bytes are not redistributed; only approved identity and hash metadata appears here.
- No public weights exist in RES-272.
- RES-274 will train PUBLIC_NATIVE weights from scratch.
- Public runtime has no historical checkpoint path or private adapter dependency. The one-off local equivalence adapter used for RES-272 was not committed.
- No historical checkpoint was evaluated on the PUBLIC_NATIVE IID benchmark.

## RES-274 Gate A historical evidence replay

This local-only reconstruction used the preserved historical checkpoint files, training/data manifests, original inference implementation, the 3,072-row historical validation truth, and the preserved ensemble prediction array. The checkpoint bytes, source bytes, normalization values, validation rows, and prediction arrays remain private and are not part of this repository.

| Historical binding | Verified identity |
| --- | --- |
| M1 historical BenchmarkSpec mapping | `psr:benchmark-spec:pl-response-v2-parsimonious-production-historical-mapping@1.0.0~548604c18ac7` |
| Current historical projection BenchmarkSpec | `psr:benchmark-spec:latent-capacity-change-with-transient-expression-forecasting@1.0.0~fbfbe59eb0a8` |
| Historical DatasetSpec | `psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@1.0.0~7098655518cd` |
| Historical DatasetRealization | `psr:dataset-realization:pl-response-v2-parsimonious-production@sha256:1c986ed3dc23ab6202a7840e7e569099ec3d9eeef7ccf4643c4d07d9e0af56d5` |
| Historical EVALUATION | `psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f` (`EVAL_SRE_DDOF0_EQUAL_LIFT_MEAN_V2`) |
| Historical train Parquet SHA-256 | `8d5dff0b1c51030669ab5e6e8a54e42de2998d7cbecd3a185756df3d3f203b20` |
| Historical validation Parquet SHA-256 | `a23603a874673904a6338f79de780d2fba3d26caee5849198c363a31afc9c536` |

The three checkpoint files were hashed directly and match the identities above. The frozen original inference source files also match all eight source hashes in the preserved execution protocol. For each checkpoint, the input and target normalization arrays match the preserved normalization record exactly; normalization was fitted on historical TRAIN only. The recorded preprocessing remains the historical six observation-derived channels standardized per lift, four fixed schedule/age channels, and target-wise train-standardized output.

### HISTORICAL_REPORTED

The preserved final manifest reports ensemble aggregate SRE `0.38269148458554314`. It also records these per-seed results and prediction hashes:

| Seed | Selected epoch | Reported aggregate SRE | Recorded prediction SHA-256 |
| --- | ---: | ---: | --- |
| 383001 | 36 | 0.38905997037453116 | `fd9809235009e5bbd2bc3ccc8a3cef2631ddf506b57a6d062026d851cf179da1` |
| 383002 | 39 | 0.39165193195993514 | `ea59ab47647642bde35ed9b8e2ef613a47da2318c883ff04ecd26756de6106ec` |
| 383003 | 38 | 0.38408848994213046 | `6e11d7441e5d03aa837a7eaab6834799c2ef39d795e25c5f2437f9b6f5bda809` |

The individual seed prediction files did not survive in the preserved copy, so those hashes could not be checked against their original bytes. Each seed was replayed locally from its preserved checkpoint on the same historical validation rows. The CPU replay mean-target SREs were `0.389059918725785`, `0.391655430836215`, and `0.384091694067965`; differences from the reported values were `-5.16e-8`, `+3.50e-6`, and `+3.20e-6`. This replay is not byte-identical evidence for the original recorded GPU/BF16 predictions.

The following `RECOMPUTED_CANONICAL` metrics are from those CPU checkpoint replays, not from surviving per-seed prediction bytes:

| Seed | Target | RMSE (kg) | MAE (kg) | R² | SRE (`ddof=0`) |
| --- | --- | ---: | ---: | ---: | ---: |
| 383001 | Squat | 2.9588125077 | 1.8668266188 | 0.8384681366 | 0.4019102678 |
| 383001 | Bench | 1.9288516710 | 1.2015760827 | 0.8631842971 | 0.3698860674 |
| 383001 | Deadlift | 3.5668154853 | 2.2745875634 | 0.8436719504 | 0.3953834210 |
| 383002 | Squat | 2.9623534106 | 1.8893058679 | 0.8380812849 | 0.4023912463 |
| 383002 | Bench | 1.9714665359 | 1.2215561057 | 0.8570720707 | 0.3780581031 |
| 383002 | Deadlift | 3.5589988528 | 2.2879186901 | 0.8443563817 | 0.3945169430 |
| 383003 | Squat | 2.9006113271 | 1.8572810523 | 0.8447604453 | 0.3940045110 |
| 383003 | Bench | 1.9121338774 | 1.2002500861 | 0.8655456447 | 0.3666801812 |
| 383003 | Deadlift | 3.5325979611 | 2.2894070143 | 0.8466569665 | 0.3915903900 |

### RECOMPUTED_CANONICAL

Canonical target-wise RMSE, MAE, R², and SRE (`ddof=0`) were recomputed from the preserved original three-seed ensemble prediction array and the same historical target truth. Its SHA-256 `5caf4d31d0c54dd198e1f7d0b277adfc6eb88f81385fb8091b2df8b1f58b6854` matches the preserved final manifest.

| Target | RMSE (kg) | MAE (kg) | R² | SRE (`ddof=0`) |
| --- | ---: | ---: | ---: | ---: |
| Squat | 2.8982321850 | 1.8475730713 | 0.8450150023 | 0.3936813403 |
| Bench | 1.9072639643 | 1.1893457368 | 0.8662296420 | 0.3657463028 |
| Deadlift | 3.5060434500 | 2.2558997246 | 0.8489536586 | 0.3886468081 |

The canonical arithmetic mean of these three target SREs is `0.382691483706746`, `8.79e-10` below `HISTORICAL_REPORTED`. The reported value is retained unchanged. A separate arithmetic mean of the three CPU-replayed checkpoint predictions had SRE `0.382692798577011` and differed from the preserved original ensemble predictions by at most `0.00692378575` kg per target element; the recorded GPU/BF16 runtime is a plausible source of this replay difference. No historical metric or checkpoint was tuned to remove it.
