# Observable strength-assessment forecasting (RES-616)

**Disposition: `OBSERVABLE_FORECASTING_NOT_QUALIFIED`.** In this synthetic world a newly fitted GRU forecasts the future noisy strength assessment better than persistence, but it does **not** beat a regularized ridge baseline. On both independent TEST parents the GRU is slightly *worse* than ridge, and the paired intervals exclude zero in the unfavorable direction. This is a valid negative finding, not a failed run.

All results are for **simulated assessments**. They say nothing about real athletes, physiology or competition one-repetition maxima.

## Task and what is measured

- Forecast origin day 224; histories end on day 223. Horizons 14, 28 and 56 days; assessment days 237, 251 and 279 (`origin + horizon − 1`).
- Lifts: squat, bench press, deadlift. Declared plans: continue, step-up, step-down, cessation.
- **Target `Y`:** the absolute noisy synthetic assessment on the assessment day, in kg, drawn with the simulator's declared assessment law (`E × (1 + Normal(0, cv))`) from a separate future-noise stream. It is distinct from latent capacity `C` and from expressed performance `E`, neither of which a model sees.
- **No cessation truncation.** Under cessation the modeled capacity change is nonpositive in 100% of 768 test rows per scenario, yet expressed performance rises in about 21–33% and the assessment exceeds the last observed assessment in about 34–42%. The RES-615 `y ≤ 0` rule would be wrong for this target, and code and tests reject it.
- Identities: study `psr:study:observable-strength-assessment-forecasting@1.0.0~de8b63092417`; task `psr:task:future-observed-strength-assessment-forecasting@1.0.0~847efe3c965f`; the QOI, observation protocol and evaluation identities are in the [frozen protocol](../../results/studies/observable_strength_forecasting/protocol.json).

## Design (frozen before fitting)

| Role | Rows | Use |
| --- | ---: | --- |
| FIT | 12,288 | fit ridge and GRU |
| DEV | 3,072 | ridge alpha, GRU early stopping, group RMS scale |
| CAL_C | 3,072 | per-lift scale `c` |
| CAL_G | 3,072 | shrinkage group factors (lift × plan × horizon) |
| TEST_A, TEST_B | 3,072 each | two independent parents, each with control and two shifts |

Three predictors: **M0** persistence (latest assessment), **M1** ridge on 163 visible features (alpha from a fixed four-value set chosen on DEV; 0.01 was chosen), **M2** the existing GRU architecture with new weights trained once on the new target (seed 616701, at most 20 epochs, DEV early stopping with patience 4; it stopped at epoch 17 with the best DEV epoch 13). Gaussian scales: DEV group RMS, then global per-lift `c` from CAL_C (arms `*_C`). The one calibration contender is the CAL_G shrinkage group adjustment (arms `*_G`). Training-seed stability is **not tested**: only one GRU was fitted.

## Primary endpoint

Paired macro CRPS (kg, lower is better), M2_C − M1_C, control scenario, 1,000 stratified entity-cluster bootstrap replicates per parent.

| Parent | M1_C | M2_C | Difference | 95% interval | Relative |
| --- | ---: | ---: | ---: | --- | ---: |
| TEST_A | 6.6378 | 6.7481 | +0.1103 | [+0.0679, +0.1487] | +1.66% (worse) |
| TEST_B | 6.6281 | 6.7197 | +0.0916 | [+0.0524, +0.1333] | +1.38% (worse) |

The superiority screen (≥1% improvement and an interval below zero on each parent) is **not** met; the GRU is worse by a statistically distinguishable but small margin. The 1% threshold is an exploratory criterion, not a clinically established change.

## Secondary findings (descriptive, unadjusted, overlapping metrics)

- **Ranking (control CRPS):** M1_C < M2_G ≈ M2_C < M0_C on both parents. M1_G ties M1_C. The GRU beats persistence by about 25–26% (M2_C − M0_C ≈ −2.28 / −2.35 kg, intervals well below zero).
- **Point error (MAE, kg):** M0 12.36 / 12.46, M1 9.11 / 9.11, M2 9.26 / 9.24 (TEST_A / TEST_B).
- **Calibration contender:** M2_G − M2_C is −0.0031 kg [−0.0054, −0.0009] on TEST_A and −0.0009 kg [−0.0032, +0.0012] on TEST_B. The group adjustment is statistically distinguishable from zero on one parent and negligible in size on both. It improves CRPS in about half the 36 lift × plan × horizon groups and worsens it in the rest.
- **Pooled coverage:** central 90% coverage of every arm is 90.3–90.7% and central 80% coverage is 82.6–83.3%, so intervals are slightly conservative at 80% and near nominal at 90%. M2_C pooled 90% coverage: 90.40% (A) and 90.39% (B). Predicted probability mass below zero is 0 to nine decimals.
- **Subgroup reliability:** M2_C 90% coverage by lift × plan × horizon group (256 rows each) ranges 85.5–96.9% (A control) and 85.5–95.7% (B control); one group is outside 85–95% on each control parent. M2_C has higher CRPS than M1_C in 29 of 36 groups on both parents and higher NLL in 27 and 29 of 36. Pooled agreement is not subgroup calibration.
- **Interval widths** depend only on lift × plan × horizon (the scale model is group-constant), so they are identical across parents; the intervals do not adapt to individual histories. This is a limitation of the frozen calibration design.

## Distribution shifts (relative ranking separated from absolute degradation)

Frozen models and calibration parameters were evaluated unchanged. These are two parents × three scenarios = six dependent sets, not six independent populations.

| Macro CRPS (kg) | A control | A velocity noise | A adaptation shift | B control | B velocity noise | B adaptation shift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M0_C | 9.023 | 9.023 | 9.123 | 9.074 | 9.074 | 9.192 |
| M1_C | 6.638 | 6.678 | 6.645 | 6.628 | 6.670 | 6.654 |
| M2_C | 6.748 | 6.820 | 6.751 | 6.720 | 6.804 | 6.746 |

- **Ranking is unchanged** in all six scenarios (M1 < M2 < M0). M2_C minus M1_C is +0.142 / +0.106 kg (A velocity / adaptation) and +0.134 / +0.092 kg (B), all intervals above zero.
- **Absolute degradation:** velocity noise raises M1 CRPS 0.60–0.63% and M2 1.06–1.25% (the GRU relies more on velocity histories). The adaptation shift raises M0 by 1.1–1.3% and M1/M2 by 0.04–0.39%. Persistence is unaffected by velocity noise by construction (it uses assessments only). Pooled 90% coverage stays within 90.1–90.6%.
- No claim of robustness to arbitrary shifts is made.

## Resources, identities and reproducibility

One CPU worker and thread. The full campaign used 488 charged CPU-s (ceiling 5,400) and 488 s wall (ceiling 7,200), peak 0.98 GB RSS (ceiling 2 GiB). GRU fitting used 324 CPU-s (ceiling 2,400) with 17 epochs and 816 forward/backward calls. Frozen-parameter, prediction-seal and output hashes are in the manifest. The GRU weights are identified by SHA-256 (`5e3857554296d8f41f6ed55ce553462c4a343f59c63431c5593fda832cd82108`) but not committed. Reproduce with:

```sh
uv run --locked python -m powerlifting_state_research.observable --profile smoke --out OUTDIR
uv run --locked python -m powerlifting_state_research.observable --profile full --out OUTDIR   # about 8 CPU minutes
```

Sealed-then-opened order: parameters frozen and hashed; all TEST predictions computed and hashed; truth opened once; no refitting or rescoring.

## What this does and does not show

- Latent capacity is not measured performance: the RES-615 latent reference and this observable task are separate, with separate fitted parameters.
- Same-law accuracy and shift robustness are separate results above; so are pooled and subgroup calibration, and statistical versus practical significance (the GRU deficit is real but about 1.5%).
- One GRU initialization was fitted; any seed-to-seed spread is unknown, so a different seed could change the sign of the small primary difference. Not tested.
- Synthetic system only. No real-athlete validity, physiological identification or causal training advice is established.
