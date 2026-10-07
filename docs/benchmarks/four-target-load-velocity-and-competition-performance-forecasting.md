# Four-Target Load–Velocity and Competition Performance Forecasting

## Research question

From point-in-time completed histories, how accurately can models forecast target-load velocity, load at a reference velocity, next-set velocity loss, and competition-day capacity over 25 days? This does not establish causal training effects, real-athlete accuracy, or state/parameter recovery.

This question is classified as **RETROSPECTIVE_TECHNICAL_CHARACTERIZATION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Characterize four powerlifting performance targets in a longitudinal synthetic system.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: FOUR_TARGET_25_DAY_PERFORMANCE_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Point-in-time histories; temporal features end at the current completed event. No future-plan field in the recovered interface.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | four_target_longitudinal_performance_state | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | athlete_state_training_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | four_target_load_velocity_and_competition_performance_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | four_target_load_velocity_and_competition_performance_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | four_load_velocity_and_competition_performance_targets | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | four_target_temporal_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | four_target_weighted_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Reconstructed synthetic four-output specimen with source-bound checkpoint/public scalar.
- Four target meanings and the historical weighted evaluation identity are recoverable.

## Claim limits

- Qualification/performance claim from checkpoint/scalar alone.
- Real-athlete, biological, causal, parameter-identification, or OOD claims.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.four_target_load_velocity_and_competition_performance_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
