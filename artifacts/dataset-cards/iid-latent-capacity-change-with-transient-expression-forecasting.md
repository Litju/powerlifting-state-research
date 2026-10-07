# IID Latent Capacity-Change Forecasting with Transient Performance Expression

## Scientific purpose and claim boundary

This is a synthetic benchmark for conditional forecasting of latent capacity change in a specified three-lift system. At origin day 224, a learner receives a declared future plan and the generated history through day 223, then predicts future latent-capacity change for squat, bench press, and deadlift.

This benchmark is **not** real-athlete validation, causal intervention-efficacy evidence, biological-parameter identification, or broad out-of-distribution evidence. It describes behavior inside the named synthetic system and finite support only.

## Benchmark identity

| Field | Identity |
|---|---|
| PUBLIC_NATIVE BenchmarkSpec | `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~49b4994f7df4` |
| BenchmarkSpec digest | `sha256:49b4994f7df4443c6f8d80c968d456d611b5e7886c32659727e8c351dfed9de3` |
| DatasetSpec | `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` |
| WORLD | `psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e` |
| TASK | `psr:task:latent-capacity-change@1.0.0~44fc77353e7a` |
| QOI | `psr:qoi:latent-capacity-change@1.0.0~675491124046` |

The separate historical projection is `latent_capacity_change_with_transient_expression_forecasting`, with BenchmarkSpec digest `sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472`. It remains `HISTORICAL_PROJECTION`; this benchmark is `PUBLIC_NATIVE` and explicitly non-historical. The two records share specified world mechanics, task, QOI, representation, and evaluation. Their population sampling designs and DatasetSpecs differ.

## Population

Each entity receives 16 independent pseudorandom coordinates from `random.Random(population_seed).random()`, each in **`[0,1)`**. The order below is the generator order. The ranges are transform ranges, not a human population prior. This is a synthetic coverage measure.

| # | Coordinate | Transform range | Mapping |
|---:|---|---:|---|
| 1 | `baseline_scale` | 120–360 kg | Log-linear; becomes squat baseline capacity. |
| 2 | `bench_baseline_ratio` | 0.50–0.90 | Linear; multiplied by baseline scale. |
| 3 | `deadlift_baseline_ratio` | 1.00–1.40 | Linear; multiplied by baseline scale. |
| 4 | `squat_adaptation_utilization` | 0.04–0.18 | Linear; divided by reference stimulus for adaptation gain. |
| 5 | `squat_adaptation_retention_28d` | 0.15–0.90 | Linear; adaptation time is `-28 / log(1 - retention)`. |
| 6 | `squat_suppression_utilization` | 0.01–0.07 | Linear; divided by reference stimulus for suppression gain. |
| 7 | `squat_suppression_retention` | 0.30–0.95 | Linear; suppression time is `-1 / log(retention)`. |
| 8 | `bench_adaptation_utilization` | 0.04–0.18 | Same adaptation transform as squat. |
| 9 | `bench_adaptation_retention_28d` | 0.15–0.90 | Same adaptation-time transform as squat. |
| 10 | `bench_suppression_utilization` | 0.01–0.07 | Same suppression-gain transform as squat. |
| 11 | `bench_suppression_retention` | 0.30–0.95 | Same suppression-time transform as squat. |
| 12 | `deadlift_adaptation_utilization` | 0.04–0.18 | Same adaptation transform as squat. |
| 13 | `deadlift_adaptation_retention_28d` | 0.15–0.90 | Same adaptation-time transform as squat. |
| 14 | `deadlift_suppression_utilization` | 0.01–0.07 | Same suppression-gain transform as squat. |
| 15 | `deadlift_suppression_retention` | 0.30–0.95 | Same suppression-time transform as squat. |
| 16 | `reference_stimulus` | 0.12–0.85 | Linear; stimulus reference is `0.6 * (1 - value) / value`. |

The population transforms use normalized, dimensionless coordinates. The baseline and target measures use kilograms; training dose, intensity, utilization, and retention are dimensionless. Coordinate 0 and values immediately below 1 are valid; 1, negative values, NaN, and infinities are invalid.

## World and intervention support

The world evolves capacity adaptation and transient suppression separately for each lift, with no cross-lift edges and no process disturbances. Expressed performance is the observed latent capacity after transient suppression. See [the world description](../../docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md) for the equations.

Each lift uses one of four piecewise-constant 32-week history templates. Week-blocks use dose keys `cessation=0.0`, `step_down=0.4`, `continue=0.8`, and `step_up=1.2`; intensity is 0.75 for every key.

| Template | Consecutive week blocks, oldest to newest |
|---:|---|
| 0 | `4 step_down, 4 continue, 4 step_up, 1 cessation, 4 step_down, 4 continue, 4 step_up, 1 cessation, 4 continue, 2 step_down` |
| 1 | `4 step_up, 4 continue, 4 step_down, 1 cessation, 4 step_up, 4 step_down, 4 continue, 1 cessation, 2 step_up, 2 continue, 2 step_down` |
| 2 | `8 continue, 4 step_up, 2 cessation, 4 step_down, 4 step_up, 2 cessation, 4 continue, 4 step_down` |
| 3 | `8 step_down, 2 cessation, 8 step_up, 4 continue, 2 cessation, 4 step_up, 4 step_down` |

There are `4³ = 64` three-lift history-template combinations. The four declared future plans use the same dose keys and intensity, cover days 224–279, and begin at origin day 224. The three prediction horizons are 14, 28, and 56 days. All 4 plan × 3 horizon strata are balanced in each split.

## Observation model

Each lift has 32 observations on days `6, 13, …, 223`. All observations are present; no field is nullable. Day is an integer day index. Assessment and prescribed load are kilograms, and velocity is metres per second.

Assessment is expressed performance multiplied by `1 + Normal(0, CV)`, with CV 0.05 for squat, 0.04 for bench press, and 0.05 for deadlift. Prescribed load is a fraction from `[0.68, 0.71)` of the noisy assessment. Its ratio to expressed performance must be in `[0.40, 1.00]`.

Velocity is `endpoint + span * ((1 - relative_load) / 0.60)^exponent + Normal(0, sigma)`. The `(endpoint, span, exponent, sigma)` values are `(0.25, 0.60, 1.0, 0.04 m/s)` for squat, `(0.18, 0.74, 1.0, 0.03 m/s)` for bench press, and `(0.20, 0.60, 1.0, 0.05 m/s)` for deadlift.

## Public row and visibility

The Python `PublicForecastRow` type generates [`artifacts/schemas/public-forecast-row.schema.json`](../schemas/public-forecast-row.schema.json). Its manifest schema identity is `latent-capacity-transient-participant-row-v2`. JSON Schema freezes structure and primitive types only; Python validation remains authoritative for exact observation dates, the day-223 cutoff, contiguous history-plan boundaries, target-field consistency, and causal leakage.

| Field | Type and units | Meaning and visibility |
|---|---|---|
| `row_id` | string | Row key; exactly equals `inputs.entity_id`. |
| `inputs.entity_id` | string | Synthetic entity key. |
| `inputs.origin_day` | integer day | Always 224. |
| `inputs.horizon_days` | integer days | One of 14, 28, or 56. |
| `inputs.declared_future_plan` | object | `plan_id`, inclusive `start_day` and `end_day`, normalized `dose`, and `intensity`; visible as a declaration, not a delivery claim. |
| `inputs.lifts.{squat,bench_press,deadlift}.history_schedule` | array of segments | Ordered contiguous historical day segments, inclusive, from day 0 through 223; each has `start_day`, `end_day`, normalized `dose`, and `intensity`. |
| `inputs.lifts.{lift}.history` | array of observations | Ordered by `day`; each observation has `day`, `assessment_kg`, `prescribed_load_kg`, and `velocity_mps`. Exactly 32 per lift. |
| `targets.squat_delta_capacity_kg` | number, kg | Squat latent-capacity difference `C[origin + horizon - 1] - C[origin - 1]`. |
| `targets.bench_press_delta_capacity_kg` | number, kg | Bench-press latent-capacity difference with the same temporal definition. |
| `targets.deadlift_delta_capacity_kg` | number, kg | Deadlift latent-capacity difference with the same temporal definition. |

One row aligns one entity, one declared plan, one horizon, and all three lifts. `row_id` and `entity_id` provide the row/entity join key; split membership is declared by the realization manifest, not by a row field. Input fields are learner-visible at forecast time. Targets are supervised outputs, not model inputs; validation targets are evaluation truth and must be withheld from participant/model inputs. The generated row includes every required field, with no null or omitted values.

## Splits and RNG ownership

| Split | Rows/entities | Rows per plan/horizon stratum | Rows per history combination within each stratum |
|---|---:|---:|---:|
| Train | 12,288 | 1,024 | 16 |
| Validation | 3,072 | 256 | 4 |

Train and validation entity IDs are disjoint. Validation is a same-law IID holdout, not an OOD test. Every plan/horizon stratum contains all 64 history combinations with the counts above.

| RNG role | Seed | Ownership |
|---|---:|---|
| Population | 26901 | Coordinate vectors, one vector per entity in entity-index order. |
| Intervention/history | 26902 | Stratum order and history-template allocation/order. |
| Split | 26904 | Train/validation labels within fixed history-template groups. |
| Observation | 26903 | Assessment, prescribed-load, and velocity draws. |
| Serialization | 26905 | Permutation of fully generated rows within serialized output order. |

The serialization seed cannot alter scientific row content or split membership; it only changes row order after generation.

## Causal and information boundary

Historical schedules and realized observations end on day 223. The forecast decision origin is day 224. The declared plan is visible from day 224 through day 279. Future realized outcomes, future observations, and deviations from the declared plan are hidden from the learner. Targets are separate from `inputs` and unavailable to participant/model inputs. Python row validation enforces the temporal and causal boundaries; the schema does not.

## Canonical realization and regeneration

The canonical public production realization uses DatasetSpec `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` and realization ID `latent-capacity-transient-iid-production`.

| Provenance value | Canonical value |
|---|---|
| Package version | `0.1.0` |
| Generator-source SHA-256 | `sha256:284266740cdaebdbe7108a5abe1acf4a2eeb3c055852b6ebc3c439ec164d1ad3` |
| Generation-config SHA-256 | `sha256:979aad4cea7be05ec8c4861ac9025f282c45903e0db0cab72c22d1fcdd87d850` |
| Realization ID | `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| Realization digest | `sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| Manifest digest | `sha256:2655965129f99fa98857f6c9363aa28a0dd964c2d7d8554156c17073e0277e35` |
| Train SHA-256 | `914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550` |
| Validation SHA-256 | `0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a` |

The source digest hashes these exact UTF-8 source files in the listed package-relative POSIX order: `benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py`, `benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py`, `benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py`, `benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py`, `benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py`, and `contracts/serialization.py`. CRLF is normalized to LF; no other source bytes are rewritten. SHA-256 input begins with `PSR_PUBLIC_GENERATOR_SOURCE_V1\0`. Each path contributes its 4-byte big-endian UTF-8 byte length and bytes, followed by the normalized source's 8-byte big-endian length and bytes. The working-tree root, absolute paths, `.git`, documentation, tests, and private workspace state are excluded.

From a fresh public clone, install the locked dependencies and run the canonical verifier:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked python scripts/verify_public_iid_production.py --check
```

The verifier regenerates train and validation JSONL into a fresh temporary destination and fails unless the generated manifest bytes match the checked-in canonical manifest. Full-production repeatability remains an opt-in release gate:

```sh
PSR_FULL_PRODUCTION=1 uv run --locked pytest tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py
```

That gate performs two complete generations and requires byte-identical train and validation files and manifests matching the checked-in canonical manifest. Generated JSONL remains Git-ignored; Git tracks the generator, this card, the generated row schema, the canonical realization manifest, the verifier, and these regeneration instructions. M7/M8 own downloadable release packaging.

## Historical relationship

| Axis | Historical projection | PUBLIC_NATIVE IID benchmark | Classification |
|---|---|---|---|
| Population sampling | Scrambled Sobol | IID pseudorandom Uniform `[0,1)` | `DATASET_SPEC_DIFFERENT` |
| DatasetSpec | Historical sampling specification | IID sampling specification | `DATASET_SPEC_DIFFERENT` |
| World mechanics | Same specified world | Same specified world | Shared identity |
| Task and QOI | Latent capacity-change forecast | Same task and QOI | Shared identity |
| Train/validation bytes | Historical artifacts | New public-native JSONL | Not interchangeable; historical bytes are not realizations of this IID DatasetSpec. |

The public implementation is independently authored. Historical source code, private data, and historical artifacts are not runtime inputs and are not redistributed or relicensed by this card.

## Rights and provenance

| Artifact | License | Copyright | Provenance |
|---|---|---|---|
| Source code | MIT | Powerlifting State Research contributors, 2026 | Public implementation source. |
| Generated row schema and canonical manifest files | MIT | Powerlifting State Research contributors | Machine-readable contracts generated from or used by the typed Python implementation. |
| Generated IID dataset | CC-BY-4.0 | Powerlifting State Research contributors | Provenance class `GENERATED_PUBLIC_ARTIFACT`; newly generated public synthetic data; public redistribution with attribution. |
| Repository-authored documentation, including this card | CC-BY-4.0 | Powerlifting State Research contributors, 2026 | Public documentation. |

These terms apply to their named artifacts only. They do not relicense historical private or third-party artifacts.

## Limitations

- The data come from a synthetic abstraction, not real athletes.
- Only squat, bench press, and deadlift are modeled.
- Schedule and declared-plan support is finite and fixed.
- The observation law and noise parameters are fixed.
- IID finite-sample geometry may affect realized coverage.
- Validation uses the same law as training and provides no broad OOD evidence.
- No real-athlete external validity or causal-effect interpretation is supported.
