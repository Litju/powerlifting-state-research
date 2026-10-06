# Class-Normalized Cross-Lift Capacity–Fatigue Forecasting with Five Targets

## Research question

Within a class-normalized synthetic cross-lift capacity-fatigue world, how well can a model forecast five performance outputs from past or completed records? The result is conditional on the synthetic generator and does not establish real-athlete validity or latent-state recovery.

This question is classified as **RETROSPECTIVE_TECHNICAL_CHARACTERIZATION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Characterize the same five target meanings in a class-normalized cross-lift synthetic world with changed observation and population generation.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: MULTI_OUTPUT_SEASONAL_PERFORMANCE_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Past/completed context at each query; future outcomes excluded; no declared future-plan input.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | class_normalized_cross_lift_capacity_fatigue | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | field_velocity_and_load_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | class_normalized_cross_lift_capacity_fatigue_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | seasonal_five_performance_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | seasonal_five_performance_outputs | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | class_normalized_table_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | class_normalized_five_output_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Five source-defined synthetic outputs can be evaluated after scorer is fixed.
- Common canonical comparison with other normalized legacy specimens.

## Claim limits

- Human/biological/coaching/digital-twin/intervention/identification/OOD claims.
- Raw historical ranking or undocumented claim the rewrite fixed a known defect.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.class_normalized_cross_lift_capacity_fatigue_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
