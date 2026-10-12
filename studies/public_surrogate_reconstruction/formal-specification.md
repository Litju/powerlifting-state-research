# Public-surrogate study specification

## Research question and claim scope

Can a learner fit a useful conditional predictor and a finite empirical generator from public-native benchmark rows while receiving no source equations, exact population support, latent state, population coordinates, generator implementation, or evaluation truth?

The scope is the named public-native synthetic benchmark, participant-visible row schema, declared plan/history support, independently generated study populations, and this protocol. Predictive utility, observable-record distribution fidelity, conditional response fidelity, structural equivalence, and system identification are distinct estimands. This study does not identify the original generator, establish causal equivalence, or transfer to real athletes.

## Frozen M2–M5 boundary

M2 supplies the public synthetic world and its population and observation declarations to the Evaluation Authority only. M3 supplies the PUBLIC_NATIVE BenchmarkSpec, IID DatasetSpec, public row semantics, units, and declared intervention/history fields. M4 comparator and training artifacts are provenance references only; no existing fitted state or canonical training result is reused. M5 evaluation contracts inform record handling, but this study uses a separate evaluation identity, metrics, realization, and truth. Historical and public-native scores are not combined.

The exact frozen source artifacts, their SHA-256 values, and the RES-287/289 lineage and handoff artifacts are recorded in frozen-evidence.json. The public/private firewall and file-origin ledger govern every new artifact.

## Roles and enforced dataflow

### SURROGATE_LEARNER

The learner is a separate Python subprocess running a staged copy of the learner module with isolated Python mode. Its standard input is a strict JSON allow-list containing:

- fitting rows with only the public inputs and the training target columns;
- development rows with only the same public inputs and target columns;
- evaluation query rows with public inputs and no target columns;
- the frozen model budget and random seed.

The learner may use the field descriptions and units in protocol.json and the installed NumPy dependency. It does not import repository benchmark, generator, provenance, evaluation, or result modules. It performs no file, network, or subprocess access. It cannot read the authority's realization files because the subprocess runs from a fresh temporary directory and receives bytes only on standard input. The harness rejects unknown keys, target fields in evaluation queries, and overlapping fitting/development/evaluation entity identities before launch.

The learner never receives truth rows, source implementation files, exact support bounds, hidden states, source parameters, or population coordinates. Entity keys are alignment fields and are excluded from features.

### EVALUATION_AUTHORITY

The authority alone calls the frozen public-native generator to make independent training, development, factual test, noise-replicate, independent-population, and matched-plan realizations. It keeps target truth and matched-entity groupings outside the learner payload. It validates protocol, schema, units, splits, source hashes, and permitted support, then launches the learner. Only after prediction and fitted-state bytes are sealed does it score against evaluation truth.

Authority code, truth, source calls, matched groups, and score functions are never imported by the learner subprocess. A static import-boundary test, strict payload validator, runtime file/network/subprocess guard, disjointness assertions, and deterministic replay test exercise these boundaries.

## Participant-visible fields and units

| Field | Meaning available to the learner | Unit |
|---|---|---|
| row_id and inputs.entity_id | Opaque synthetic row/entity keys for alignment; not features | none |
| inputs.origin_day | Forecast origin | day |
| inputs.horizon_days | Declared prediction horizon | days |
| inputs.declared_future_plan | Plan name, inclusive dates, dose and intensity values | days; dose/intensity dimensionless |
| inputs.lifts.<lift>.history_schedule | Piecewise-constant historical dose and intensity segments | days; dose/intensity dimensionless |
| inputs.lifts.<lift>.history | Ordered observations at the declared days through the cutoff | day; assessment and prescribed load in kg; velocity in m/s |
| targets.<lift>_delta_capacity_kg | Supervised outcome in fitting/development only | kg |

No latent-state, capacity-level, parameter, population-coordinate, generator, or evaluation-only field is part of the learner schema. The learner's feature builders consume only the visible fields above.

The visible plan categories are cessation (dose 0.0), step_down (0.4), continue (0.8), and step_up (1.2), each with intensity 0.75 over days 224–279. The forecast origin is day 224 and horizons are 14, 28, and 56 days. Historical dose/intensity pairs use those same four declared categories over inclusive segments from day 0 through day 223. The public observation dates are days 6, 13, …, 223. These are participant-visible intervention and timing fields; they are not the hidden population-coordinate bounds.

## Estimands

1. Predictive utility: conditional mean prediction error for each lift and horizon on independent public-native entities, separately for test population A, test population B, and the paired observation-noise replicate.
2. Observable-distribution fidelity: discrepancy between an empirical with-replacement sample of complete participant-visible training inputs and held-out participant-visible records, stratified by declared plan and horizon. This resampler reproduces finite training records; it is not a learned conditional response model.
3. Conditional response fidelity: error in predicted capacity-change contrasts across declared future plans for the same authority-matched synthetic entity, historical schedule, history, horizon, and observation noise. The matched entity and truth are withheld from the learner.
4. Finite-sample coverage: counts of declared plan/history cells represented in training, development and evaluation; exact public-record hash novelty; sample-extrema exceedance and nearest-training distance on standardized visible fields. Finite observed extrema are not treated as population support.
5. Memorization: the fraction of generated empirical records that are exact copies of a training participant-visible record, their unique donor count, and the exact train/test visible-record overlap.
6. Structural non-identification: compare fitted model families on predeclared predictive and matched-response metrics. Similar predictive errors or public statistics do not establish common internal structure, generator recovery, or system identification.

All intervention queries use the benchmark's declared plans. Inputs outside declared schema or intervention support are UNSUPPORTED_BY_PROTOCOL and are not scored. No extrapolation result is implied.

## Frozen method families and budgets

1. Empirical finite-support resampling: resample training visible records with replacement within plan-by-horizon strata; use the stratum mean as its target-conditional point-prediction baseline. Generate one 384-record sample with fixed seed 290180. It has no fitted parameters and is explicitly a memorization baseline.
2. Summary Ridge: closed-form multi-output Ridge on the latest, mean, and linear trend of each visible observation channel; fixed summaries of visible historical schedule; declared plan and horizon one-hot fields. Fit rows only; choose alpha from [0.1, 1, 10, 100] by mean target-standardized development MSE. No refit after selection.
3. Sequence RFF Ridge: generic random Fourier feature Ridge on the ordered 32-step observation and schedule sequences, declared plan, and horizon. The 128 Fourier features use fixed seed 290190. Choose gamma from [0.01, 0.05, 0.2] and alpha from [0.1, 1, 10] by mean target-standardized development MSE. This one family is both the predeclared nonlinear and sequence-aware candidate; it uses no mechanistic equations.

Both conditional methods return conditional means only. Neither is used to generate observable records or to impute evaluation truth. The small fixed family avoids a neural architecture tournament and adds no dependency beyond NumPy.

## Splits, seeds, and sampling

Each generated row is one entity-plan-horizon query. Fitting has 384 rows, development has 192, and each factual test population has 384 rows. Counts divide evenly across the 12 declared plan-by-horizon strata. Fitting, development, test A, test B, and the matched counterfactual entities use independent population draws and independent observation draws. A second noise realization reuses test-A population and schedules with a new observation seed to isolate measurement-noise variation. Train, development, test-A, test-B, and matched evaluation entities are disjoint. The paired noise replicate is deliberately linked only to test A in the authority-side key map.

The exact population, intervention, observation, split, bootstrap, resampling, and RFF seeds are fixed in protocol.json. Each new realization has its own content-bound identity. No canonical M3/M4 data or RES-287/289 outcome bytes are fitted or scored.

## Metrics, uncertainty, and failure rules

Predictive and matched-response tables report RMSE, MAE, signed bias, and 95% entity-level percentile-bootstrap intervals with 1,000 replicates. Paired method contrasts resample the same entity clusters. Observable fidelity reports field-wise 1-Wasserstein distance normalized by the training scale for each unit-bearing channel, absolute correlation-matrix discrepancy for the predeclared visible summaries, and plan/history frequency discrepancies. All metrics retain their units or normalization rule and denominators.

The empirical generator reports exact donor-copy fraction and unique donor counts. Coverage reports exact categorical-cell coverage and observed sample extrema; the latter is a diagnostic only. The study does not infer unobserved population bounds from a finite sample. Invalid schema or non-finite fields fail realization validation. Failed model fits, unsupported queries, empty or degenerate metric cells, and intervals spanning zero remain explicit in the negative-results register. If any learner/evaluation firewall assertion fails, the run fails before scoring. If a method fails, other methods remain reportable and the failed method is not silently dropped.

## Identity and publication

The protocol digest binds this complete specification, the frozen evidence digest, starting main 31ad65bdd4e19ef80243fbdbf507097d70f1776b, all seeds, splits, model families, budgets, estimands, evaluation authority, support rules, uncertainty, and failure criteria. The study ID derives from that digest. Independent realization digests bind generated visible and truth bytes separately. Fitted-model IDs bind the study/protocol, training and development input hashes, selected configuration, learner source hash, fitted-state hash, and exact model family.

Results are reported only as NEW_PUBLIC_NATIVE_EXPERIMENT. Predictive utility is not distributional fidelity; distributional fidelity is not conditional response fidelity; conditional response fidelity is not structural equivalence; none establishes system identification. No comparison uses incompatible historical scores.
