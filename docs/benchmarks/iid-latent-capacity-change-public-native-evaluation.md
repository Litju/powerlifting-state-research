# PUBLIC_NATIVE IID evaluation card

## Identity

| Record | Identity |
|---|---|
| BenchmarkSpec | `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~f99463d55ba0` |
| BenchmarkSpec digest | `sha256:f99463d55ba0902595a1866032ba94b803ac97d9b4985a89e208293da9c7fed0` |
| DatasetSpec | `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` |
| DatasetRealization | `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| DatasetRealization digest | `sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad` |
| EVALUATION | `psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8` |

The previous PUBLIC_NATIVE BenchmarkSpec `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~49b4994f7df4` (`sha256:49b4994f7df4443c6f8d80c968d456d611b5e7886c32659727e8c351dfed9de3`) is superseded because it reused the historical SRE evaluation identity. The historical projection and its evaluation identity are unchanged. DatasetSpec, DatasetRealization, manifest digest, and train/validation bytes are unchanged.

The public taxonomy maps the historical identity to `latent_capacity_change_canonical_sre_evaluation`. Frozen provenance records the SRE family with `ddof=0`, equal-lift averaging, and an evaluation identity change while retaining that SRE family; it does not establish the complete public RMSE/MAE/R²/target-wise protocol. Therefore this benchmark has a separate EVALUATION identity. See the [component taxonomy](../science/component-taxonomy.md), [benchmark registry](../../artifacts/registries/benchmark-registry.json), and [historical provenance declaration](../../src/powerlifting_state_research/provenance/historical_sources.py).

## Prediction contract

- Task: `psr:task:latent-capacity-change@1.0.0~44fc77353e7a`.
- QOI: `psr:qoi:latent-capacity-change@1.0.0~675491124046`.
- Forecast origin: day 224; realized history ends on day 223.
- The declared future plan is visible. Future realized performance, future observations, future disturbances, unknown intervention deviations, target-derived information, and evaluation truth are forbidden.
- Output fields, each in kg: `squat_delta_capacity_kg`, `bench_press_delta_capacity_kg`, `deadlift_delta_capacity_kg`.
- `row_id` is the canonical alignment key. Dataset rows guarantee `row_id == entity_id`, so a separate `entity_id` field would be redundant.
- Missing prediction and non-finite prediction: REJECT. Align by declared keys; prediction serialization order is irrelevant.

The typed row is `PredictionRow`. Its generated schema is [`artifacts/schemas/iid-latent-capacity-change-prediction-row.schema.json`](../../artifacts/schemas/iid-latent-capacity-change-prediction-row.schema.json), identity `psr:prediction-schema:iid-latent-capacity-change-jsonl-row@1.0.0~cad5c74acd66`. Each UTF-8 JSONL line is one canonical compact JSON object containing only `row_id` and the three predicted values. Malformed JSON, duplicate JSON fields, duplicate row IDs, missing or extra row IDs, missing targets, unknown fields, wrong primitive types, and non-finite values are rejected. Artifact SHA-256 hashes the original bytes and may vary with line order; aligned metrics do not.

## Canonical metrics

Each target is scored over every row in the complete 3,072-row validation split. The result reports target-wise metrics only:

| Metric | Identity | Definition | Unit / undefined case |
|---|---|---|---|
| RMSE | `psr:metric:rmse@1.0.0~0a9b0918a7aa` | `sqrt(mean((prediction - truth)^2))` | kg |
| MAE | `psr:metric:mae@1.0.0~7319598a8a18` | `mean(abs(prediction - truth))` | kg |
| R² | `psr:metric:r-squared@1.0.0~00bad728358d` | `1 - SSE/SST` | dimensionless; `UNDEFINED / CONSTANT_TRUTH` |
| SRE(ddof=0) | `psr:metric:sre-population-sd-ddof-0@1.0.0~f3341587fd14` | `RMSE / sqrt(mean((truth - mean(truth))^2))` | dimensionless; `UNDEFINED / ZERO_TRUTH_POPULATION_SD` |

SRE uses population standard deviation (`ddof=0`). Empty truth is undefined as `EMPTY_TRUTH`; malformed or incomplete prediction inputs reject before scoring. There is no universal scalar aggregate. Canonical stratification and uncertainty are empty; optional plan/horizon diagnostics are non-canonical and do not alter result identity.

## Result and command

The typed `EvaluationResult` schema is [`artifacts/schemas/evaluation-result.schema.json`](../../artifacts/schemas/evaluation-result.schema.json). Its digest covers the benchmark and dataset identities, model ID, training protocol applicability, prediction artifact hash and schema identity, evaluation and metric identities, target-wise metrics, environment/dependency metadata, RNG/determinism status, and rights/provenance. Precomputed predictions use `TrainingProtocolReference(training_protocol_id=None, not_applicable_reason=...)`; no fitted-instance or checkpoint identity is invented.

After producing the frozen validation file with the [RES-270 regeneration command](../../artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md), run:

```sh
python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.evaluate \
  --validation data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production/validation.jsonl \
  --predictions predictions.jsonl \
  --model-id psr:model:your-model@1.0.0~000000000000
```

The evaluator verifies the checked-in realization manifest and validation SHA before scoring. It fails clearly when the canonical validation JSONL is absent and never regenerates it implicitly.

Claims are limited to conditional prediction within this synthetic world, finite support, observation law, and same-law IID validation design. Results do not establish real-athlete validity, causal intervention effects, biological parameter identification, or broad out-of-distribution performance.
