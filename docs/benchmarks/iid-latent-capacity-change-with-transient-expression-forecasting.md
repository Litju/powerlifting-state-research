# IID-Sampled Latent Capacity-Change Forecasting with Transient Performance Expression

## Identity and relation to the historical projection

This is the independently executable public-native benchmark variant. It shares the specified world, task, QOI, representation, and evaluation with the historical projection, and uses newly minted direct public-native population, intervention, observation, and dataset identities.

The definitive data, participant-visible row, generation, rights, and limitations contract is the [IID public-native dataset card](../../artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md). This benchmark page retains the historical comparison record.

| Record | Identity authority | Benchmark ID | Semantic digest | Public implementation |
|---|---|---|---|---|
| [Historical projection](latent-capacity-change-with-transient-expression-forecasting.md) | HISTORICAL_PROJECTION | `psr:benchmark-spec:latent-capacity-change-with-transient-expression-forecasting@1.0.0~fbfbe59eb0a8` | `sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472` | PUBLIC_IMPLEMENTATION_PENDING for this exact DatasetSpec |
| IID public-native variant | PUBLIC_NATIVE | `psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting@1.0.0~49b4994f7df4` | `sha256:49b4994f7df4443c6f8d80c968d456d611b5e7886c32659727e8c351dfed9de3` | PUBLIC_IMPLEMENTED |

The historical benchmark digest remains frozen. The public-native digest differs because the sampling algorithm is part of DATASET_SPEC under the RES-267 taxonomy. Historical production used scrambled Sobol sampling; this public variant uses IID pseudorandom Uniform(0,1) coordinates. Its equal coordinate support does not make the two sampling designs identical. The historical Sobol scramble, seed, skip/index convention, and coordinate ordering are not sufficiently specified to implement Path A without guessing, so this is Path B.

The public-native semantic identity uses these direct component IDs:

| Component | Identity |
|---|---|
| WORLD (shared) | `psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e` |
| POPULATION | `psr:population:latent-capacity-transient-uniform-coordinate-population@1.0.0~1aaf9be508dc` |
| INTERVENTION_REGIME | `psr:intervention-regime:latent-capacity-transient-balanced-plan-history-regime@1.0.0~a1ca0adb3ef3` |
| OBSERVATION_MODEL | `psr:observation-model:latent-capacity-transient-performance-observation@1.0.0~9147ed8f5372` |
| DATASET_SPEC | `psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed` |

Task, QOI, representation, and evaluation reuse the historical projection’s direct identities. The world identity is also shared because its specified mechanics are unchanged. The native component IDs are derived from canonical public semantic payloads; the public DatasetSpec separates sampling algorithm/order from coordinate support and transforms.

## Public IID sampling and RNG ownership

The population vector has 16 coordinates in `population.COORDINATE_ORDER`. Each coordinate is a separate `random.Random(population_seed).random()` draw in `[0,1)`. The generator consumes one complete vector for each entity in increasing entity index, after deterministic intervention and split allocation. No Sobol sequence or scrambling is used.

Within each plan/horizon stratum, the intervention seed determines a shuffled stratum and history-template-group order. The split seed shuffles train/validation labels only within fixed template groups, preserving balanced template counts in both splits. Thus changing `split_seed` changes entity membership but not `row_id -> scientific row content`. Population and observation streams consume draws in canonical entity order. Serialization applies its own seeded permutation only after every row is complete.

The production configuration contains 12,288 train rows and 3,072 validation rows, with 1,024 and 256 rows respectively in each of the 12 plan/horizon strata. Train and validation use disjoint entities and the same population, intervention, and observation laws.

Run a production generation into a new directory:

```sh
uv run --locked python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting \
  --output data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production \
  --manifest data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json
```

The full release verifier generates into a fresh temporary directory, computes both file hashes and the manifest digests, and can compare the generated manifest against the checked-in expected manifest:

```sh
uv run --locked python scripts/verify_public_iid_production.py --check
```

Pass `--output-dir PATH` to retain the generated files. Full production repeatability is an opt-in release gate (`PSR_FULL_PRODUCTION=1 uv run --locked pytest tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py`); it is not part of ordinary PR CI.

## Historical equivalence matrix

The classifications below retain the RES-269 private qualification results as evidence only. RES-396 changes RNG allocation and DatasetSpec identity; it does not change world equations, public transforms, observation formulas, task, QOI, or the information boundary. No historical source or data bytes are public runtime inputs.

| Axis | Classification | Qualification result |
|---|---|---|
| WORLD mechanics | NUMERICALLY_EQUIVALENT_SERIALIZATION_DIFFERENT | Two fixed-coordinate cases matched stimulus, adaptation, capacity, suppression, expression, and latent-capacity change exactly. |
| Population transforms/support | NUMERICALLY_EQUIVALENT_SERIALIZATION_DIFFERENT | Fixed-coordinate transformations matched exactly; coordinate ranges and parameter transforms are shared. |
| Population sampling design | DATASET_SPEC_DIFFERENT | Historical scrambled Sobol versus public IID pseudorandom Uniform(0,1). |
| INTERVENTION_REGIME | SCIENTIFICALLY_EQUIVALENT_REALIZATION_DIFFERENT | Declared plans, schedule support, origin/horizons, and history-template family match; row allocation and sampled realization differ. |
| OBSERVATION_MODEL | NUMERICALLY_EQUIVALENT_SERIALIZATION_DIFFERENT | The deterministic zero-noise mapping differed by at most `2.9e-14`; absolute tolerance was `1e-12`. Random draws differ across realizations. |
| TASK and QOI | EXACT_BYTE_EQUIVALENT | Same task and latent-capacity-change identities and target definition. |
| Representation and information boundary | EXACT_BYTE_EQUIVALENT | Same visible fields, day-224 cutoff, history through day 223, and declared-plan visibility. |
| DATASET_SPEC | DATASET_SPEC_DIFFERENT | IID sampling is an identity-bearing dataset design change from scrambled Sobol. |
| Selected-row numeric behavior | SCIENTIFICALLY_EQUIVALENT_REALIZATION_DIFFERENT | A selected pair shared plan, horizon, history schedule, observation days/channels, and field meanings; independent population/noise draws produced different numeric values. |
| Complete train realization | DATASET_SPEC_DIFFERENT | Different sampling design, RNG ownership repair, and JSONL output; no exact historical bytes claimed. |
| Complete validation realization | DATASET_SPEC_DIFFERENT | Different sampling design, RNG ownership repair, and JSONL output; no exact historical bytes claimed. |
| Serialization | NOT_EQUIVALENT | Historical Parquet and public canonical JSONL use different serialization formats and ordering codecs. |

Historical full train/validation hashes remain qualification authorities only. Path B does not attempt to reproduce them because their scrambled Sobol realization is not the public-native DatasetSpec. The previous RES-269 report’s public validation SHA was not authoritative; the repaired production verifier and checked-in manifest are the sole authorities for the public-native realization.

## Public realization

The checked-in manifest is `data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json`. The authoritative production outputs are:

- Train SHA-256: `914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550`
- Validation SHA-256: `0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a`
- Realization ID: `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad`
- Realization digest: `sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad`
- Manifest digest: `sha256:2655965129f99fa98857f6c9363aa28a0dd964c2d7d8554156c17073e0277e35`
- Generator-source SHA-256: `sha256:284266740cdaebdbe7108a5abe1acf4a2eeb3c055852b6ebc3c439ec164d1ad3`
- Generation-config SHA-256: `sha256:979aad4cea7be05ec8c4861ac9025f282c45903e0db0cab72c22d1fcdd87d850`

The RES-396 realization is preserved as superseded provenance: realization digest `sha256:bbb19dee8cb843c7156e23d0c1d20d00c06fcc7c1c58326f59c22c23a80b5119`, manifest digest `sha256:2334a2e954f8f82536db0f35dc39272db2972cc2af2acb3abf23a9500db6b5a9`. Its train and validation hashes are unchanged because the source/configuration identity hardening changes manifest identity, not generated row content. It is not a second current manifest. Generated JSONL is not checked into Git.

The opt-in full-production repeatability gate passed: two complete runs produced byte-identical train and validation JSONL, and both manifests matched the canonical manifest above.
