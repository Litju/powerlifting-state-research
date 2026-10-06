# Seasonal Capacity–Fatigue Forecasting with Five Performance Targets

## Research question

Within the seasonal capacity-fatigue and load-velocity synthetic world, how well can a model forecast target-load velocity, reference-velocity load, session shift, next-set velocity loss, and competition-day capacity from records available at each query time? This characterizes the synthetic task and does not establish real-athlete validity or latent-state identification.

This question is classified as **RETROSPECTIVE_TECHNICAL_CHARACTERIZATION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Characterize five source-defined synthetic performance targets within a seasonal capacity-fatigue world.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: MULTI_OUTPUT_SEASONAL_PERFORMANCE_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Use past/completed records available at each query time; future meet outcomes and future/in-session records are excluded. No declared future-plan input.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | seasonal_capacity_fatigue | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | seasonal_multi_channel_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | seasonal_capacity_fatigue_five_target_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | seasonal_five_performance_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | seasonal_five_performance_outputs | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | seasonal_public_table_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | seasonal_five_output_consistency_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Source-bound historical specimen and five synthetic target definitions.
- Common canonical reevaluation after target/support alignment.

## Claim limits

- Human/biological/coaching/digital-twin/intervention/identification/OOD claims.
- Raw score ranking or claims that early equals later legacy worlds.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.seasonal_capacity_fatigue_five_target_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
