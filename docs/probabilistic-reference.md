# Public probabilistic reference (RES-615)

A one-command, CPU-only reference experiment for **probabilistic forecasts of simulated latent capacity change**. It is a **new** public reference (Route B), **not** a reproduction of the historical M10–M12 studies. It makes no claim about observed performance, real athletes or distribution shift.

- Target: change in simulated latent capacity, `C[223+h]−C[223]` in kg, for squat, bench press and deadlift at horizons 14, 28 and 56 days under four declared plans. It is not an observed one-repetition maximum. The observable-performance benchmark is a separate task.
- Identity: `psr:reference-experiment:public-probabilistic-latent-capacity-change-reference@1.0.0~18f54a184fc9`, minted from the [frozen protocol](../results/references/public-probabilistic-latent-capacity-change-v1/protocol.json) before any scientific run.
- Rights: [per-artifact audit](../provenance/RES-615-probabilistic-reference-rights-audit.md). Only the three released GRU checkpoints, their normalization statistics and the public generator are reused. The original fitted H/H_GT parameters, calibration factors, scoring adapters, cohorts and predictions have no recorded redistribution grant and are excluded.

## Run it

From a full clone, with the locked environment:

```sh
uv sync --locked
uv run --locked python -m powerlifting_state_research.probabilistic --profile smoke --out psr-smoke-out
uv run --locked python -m powerlifting_state_research.probabilistic --profile full --out psr-full-out
```

`--out` must be a new or empty directory; the command never overwrites evidence. The command pins one BLAS/PyTorch thread itself. Each run compares its tables with the committed expected values (`--cross-environment` switches from byte identity to the tolerances below).

| Profile | Rows | CPU time | Peak memory | Where it runs |
| --- | --- | --- | --- | --- |
| `smoke` | 240 FIT + 3 × 60 | about 3 s | about 0.3 GB | ordinary pytest and CI |
| `full` | 12,288 FIT + 3 × 3,072 | about 133 s | about 0.37 GB | opt-in only (`PSR_RUN_FULL_REFERENCE=1 pytest -k full_reference`, or the command above) |

Ceilings enforced by the code: one worker, one thread, no GPU, no network, 2 GiB peak memory, 30 minutes of charged CPU time, no retries. A breach stops the run with a `LIMITATION` status instead of expanding scope.

## Procedure

1. Verify the released GRU checkpoints and normalization bytes against the MIT release manifest and pinned SHA-256 values; refuse anything else.
2. Generate four disjoint cohorts with the public generator and frozen new seeds (none from the canonical realization): `FIT`, `CAL_C`, `CAL_G`, `TEST`. Rows are regenerated, never committed.
3. The location is the unchanged three-seed GRU ensemble (point forecast).
4. `FIT` alone fits B1 (plan/horizon/lift residual RMS) and the H ridge head for the log squared error (140 features). `CAL_C` alone fits the per-lift scale `c`. `CAL_G` alone fits 36 group factors `G`.
5. All `TEST` predictive parameters are computed and hashed (a seal) before `TEST` truth is opened once for scoring.
6. Six arms: B1, B1_T, H, H_T, H_G, H_GT. `_T` arms upper-truncate the Gaussian at zero **only on cessation rows**, which is valid because zero training dose makes simulated adaptation decay and the latent change nonpositive. The rule is rejected for any other target kind.
7. CRPS (kg), NLL (nats), PIT mean, central 50/80/90% coverage and width, and GRU point errors are written, with a runtime check of closed-form CRPS against numerical integration of the predictive CDF.

The firewall is an in-process organizational barrier recorded by hashes, not adversarial isolation.

## Outputs

[`results/references/public-probabilistic-latent-capacity-change-v1/`](../results/references/public-probabilistic-latent-capacity-change-v1/) holds the protocol, `smoke/` and `full/` expected outputs: `scores.csv`, `point_forecast.csv`, `stratum_diagnostics.csv`, `cessation_support.csv`, `fitted-parameters.json` (parameters of this new reference only), three SVG figures, `manifest.json` (identities, cohort digests, seal, output hashes) and, for `full/`, `execution-receipt.json` (environment and resources).

## Reproducibility tolerances

Same machine and locked environment: all tables, figures and the manifest are byte-identical (verified with two independent fresh executions). Across machines, the committed values are checked to: CRPS ±1e-3 kg, NLL ±2e-3 nats, coverage and PIT ±4e-3, width ±5e-3 kg. The released RES-274 record bounds CPU GRU location differences by 0.0167 kg per prediction, and CRPS is 1-Lipschitz in the location, so 0.0167 kg is a hard bound on any mean CRPS change. Cohort identities and truth are checked exactly. A violation is reported, not widened.

## Results and how to read them

The single `TEST` cohort has 3,072 rows (9,216 lift observations, not independent). There is no confidence interval and no claim that any arm beats another beyond this cohort. Differences between arms are small. Pooled central 90% coverage is 91.6–91.9% for every arm (central 50% coverage is 54–62%, so the intervals overcover at lower levels). For H_GT, 90% coverage by plan/horizon/lift group (256 rows each) ranges from 87.1% (step_up/28 deadlift) to 96.1% (step_down/14 bench press) in `stratum_diagnostics.csv`, so pooled coverage is not conditional calibration. Gaussian arms place positive mass on impossible increases under cessation; truncated arms place exactly zero.

## Restrictions and nonclaims

- Not a reproduction of historical M11/M12 numbers, parameters or conclusions. Cohorts, seeds and implementation are new; B0, the controlled-shift scenarios and the paired bootstrap are not run.
- Simulated data only. No real-athlete, physiological or observed-performance validity.
- Joint three-lift calibration, distribution-shift robustness and conditional reliability are untested.
- Not an independent external scientific review.
- CPU GRU outputs may differ slightly from the original GPU outputs; the checkpoints are used unchanged.
- The canonical generated dataset is CC-BY-4.0 with attribution. Published aggregate outputs here are derived from the project's generator and are released under MIT.
