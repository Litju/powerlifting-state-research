# Latent Capacity-Change Forecasting with Transient Performance Expression

## Research question

At day 224, given 32 weekly performance observations per lift through day 223, the declared future plan, and task-allowed context, can a model predict latent capacity change for three lifts at horizons 14, 28, and 56 days in a synthetic system that separates latent capacity from transient performance expression? This is conditional synthetic prediction, not human response, biological identification, intervention efficacy, or broad out-of-domain generalization.

This question is classified as **CONTEMPORANEOUS_RESEARCH_QUESTION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Evaluate latent capacity-change forecasting in a synthetic system separating chronic adaptation, latent capacity, transient performance expression, and recorded observations.

## Specimen and completeness

Historical specimen status: REPRODUCIBLE_SPEC. Historical qualification: QUALIFIED_HISTORICAL. Completeness: FULL_FROM_EXISTING_EVIDENCE. Public implementation of this exact historical BenchmarkSpec: PUBLIC_IMPLEMENTATION_PENDING.

The executable public IID variant is a separate PUBLIC_NATIVE BenchmarkSpec: [IID-Sampled Latent Capacity-Change Forecasting with Transient Performance Expression](iid-latent-capacity-change-with-transient-expression-forecasting.md). Its DatasetSpec differs because historical production used scrambled Sobol sampling and the public-native generator uses IID pseudorandom Uniform(0,1). The historical benchmark digest below remains unchanged.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: LATENT_CAPACITY_CHANGE_FORECAST
- Target ontology: LATENT_CAPACITY_CHANGE
- Information setting: DECLARED_FUTURE_PLAN_VISIBLE
- Historical prediction boundary: Cutoff day 224; 32 weekly observations/lift through day223 plus declared plan/context visible; latent coordinates, targets, future realized outcomes/observations hidden.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | latent_capacity_transient_performance_expression_dynamics | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | COMMITTED_BY_SYSTEM_CONFIG |
| INTERVENTION_REGIME | unresolved direct identity | COMMITTED_BY_SYSTEM_CONFIG |
| OBSERVATION_MODEL | performance_expression_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | latent_capacity_change_with_transient_expression_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | latent_capacity_change_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | latent_capacity_change | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | weekly_performance_history_and_plan_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | latent_capacity_change_canonical_sre_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Qualified conditional synthetic prediction within the named latent-capacity and transient-expression system, support, and evaluation, subject to a missing readiness receipt.
- Later audit studies support only their named findings and tested protocols.

## Claim limits

- Real athlete/biological/coaching/digital twin, causal intervention effect, broad OOD.
- Biological parameter/full-coordinate identification.
- Bayes ceiling, exact hidden-model recovery, replayed sealed result, unsupported G4 load-bearing claim.
- Treating audits/model branches as benchmarks.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

The independently authored mechanics are in `src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/` and execute the separate public-native variant. They use the shared world mechanics and separate chronic adaptation `A`, latent capacity `C`, transient suppression `R`, expressed performance `P`, and recorded observations. Public implementation status belongs to that native BenchmarkSpec, not this historical projection.

For each lift `l` and day `t`, dose `d` and intensity `i` produce bounded stimulus `s`:

```text
x_l(t) = d_l(t) * i_l(t)
s_l(t) = x_l(t) / (x_l(t) + X_REF)
alpha_A,l = exp(-1 / TAU_A,l)
alpha_R,l = exp(-1 / TAU_R,l)
A_l(t) = alpha_A,l * A_l(t-1) + (1-alpha_A,l) * s_l(t)
C_l(t) = B_l * (1 + G_A,l * A_l(t))
R_l(t) = alpha_R,l * R_l(t-1) + (1-alpha_R,l) * s_l(t)
P_l(t) = C_l(t) * (1 - G_R,l * R_l(t))
```

Both dynamic states start at zero on the day before the simulated history. Each lift has a baseline, adaptation gain and time scale, and suppression gain and time scale. The baseline scale is log-linear in its normalized coordinate; the other parameter maps are linear. For reference stimulus `S_REF`, `X_REF = 0.6 * (1-S_REF)/S_REF`; the adaptation and suppression gains equal their reference-use values divided by `S_REF`. The adaptation time scale is `-28/log(1-adaptation_retention_over_28d)` days, and the suppression time scale is `-1/log(daily_suppression_retention)` days. Each lift evolves from only its own parameters and training schedule; there are no cross-lift dynamic edges. The transition has no process shocks.

The synthetic population draws 16 independent uniform coordinates in `[0,1)`. These are coverage coordinates, not a human prior. The shared baseline scale is log-uniform over 120–360 kg; bench and deadlift baseline ratios are uniform over 0.5–0.9 and 1.0–1.4. A reference dose product of 0.6 and reference stimulus coordinate determine `X_REF`. Per lift, adaptation utilization, 28-day adaptation retention, suppression utilization, and daily suppression retention are uniform over `[0.04,0.18]`, `[0.15,0.90]`, `[0.01,0.07]`, and `[0.30,0.95]`. The code applies the documented transforms to obtain the time constants and gains. No latent coordinate is participant-visible.

Historical dose/intensity support is finite: `(0.0,0.75)`, `(0.4,0.75)`, `(0.8,0.75)`, and `(1.2,0.75)`. Each lift receives one of four fixed 32-week piecewise-constant histories, with at least one zero-dose recovery block. The four profiles are specified as run-length sequences in `interventions.py`; all 64 three-lift profile combinations are balanced within every plan/horizon stratum of each split. The future plan is one of four constant 56-day declarations: cessation, step-down, continue, or step-up. A row is one entity, one plan, and one horizon, with all three lift targets. Plan/horizon combinations are balanced: each of the 12 strata contributes 1,024 train rows and 256 validation rows. The splits contain 12,288 and 3,072 distinct entities and use the same population, history, plan, and observation laws.

The origin and inclusive decision cutoff are day 224. Per lift, inputs contain the past training schedule and 32 observations on days 6, 13, …, 223. Each observation contains a noisy assessment, prescribed load, and velocity. The declared future plan covers days 224–279 and is exposed as a plan only; future realized observations or deviations are not generated into inputs. Assessment noise is multiplicative with lift-specific coefficients of variation (squat 0.05, bench 0.04, deadlift 0.05). Prescribed load is a uniform fraction in `[0.68,0.71)` of that noisy assessment. Velocity uses a monotone lift-specific relation of relative load plus independent additive noise (standard deviations 0.04, 0.03, and 0.05 m/s for squat, bench, and deadlift). Observation noise never changes `A`, `C`, `R`, `P`, or target truth.

Each row has `row_id`, `inputs`, and `targets`. Inputs contain the entity key, origin, one horizon, one declared plan, per-lift historical schedule segments, and per-lift observations. Targets contain only the three latent-capacity changes for that row's horizon. For every lift:

```text
Delta C_l(h) = C_l(224 + h - 1) - C_l(223)
```

The validator enforces the observation dates, the inclusive cutoff, history ending on day 223, declared plan bounds, dose support, target fields, entity uniqueness, and train/validation disjointness. JSONL uses compact canonical UTF-8 JSON with sorted keys and one record per line. The `DatasetRealizationManifest` records the schema, counts, split identities, RNG seeds, support, and train/validation hashes. Regenerate from the repository root with:

```sh
python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting
```

Generated JSONL is left under `data/synthetic/` and is not checked in. The manifest is tracked under `data/manifests/realizations/`; realization identity does not alter the frozen benchmark digest.

Historical qualification identified the state equations, population transform/support, observation law, and declared future-plan set as **SCIENTIFICALLY_IDENTITY_BEARING**. The historical DatasetSpec includes scrambled Sobol sampling. Public IID sampling is therefore **DATASET_SPEC_BEARING**, not realization-only. The public-native record preserves the fully specified IID design without changing this historical projection's digest. Canonical JSONL instead of Parquet and output ordering are **SERIALIZATION_ONLY**. No historical dataset or checkpoint is bundled or used at runtime. These synthetic benchmarks claim no real-athlete validity, biological parameter recovery, or intervention efficacy.

The scientific declaration is available as powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
