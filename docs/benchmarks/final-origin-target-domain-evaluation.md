# Final-Origin Target-Domain Evaluation of Seasonal Performance Forecasts

## Research question

Using the class-normalized synthetic world, can predictors trained on four 25-day origins predict the five performance outputs for an independent held-out final-origin draw at days 340–365? This evaluates transfer within the synthetic target domain, not human or general-domain transfer.

This question is classified as **CONTEMPORANEOUS_RESEARCH_QUESTION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Evaluate the five targets at an independent held-out final origin within the class-normalized synthetic target domain.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: FINAL_ORIGIN_TARGET_DOMAIN_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Past/completed observations only. Training origins 200/260/315/340; validation/hidden at 340→365; no declared future-plan input.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | class_normalized_cross_lift_capacity_fatigue | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | field_velocity_and_load_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | final_origin_target_domain_evaluation_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | final_origin_seasonal_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | seasonal_five_performance_outputs | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | class_normalized_table_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | final_origin_target_domain_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Held-out public final-origin validation exists within refined synthetic world.
- Five shared legacy target meanings can support matched canonical reevaluation.

## Claim limits

- Human transfer, broad OOD generalization, causal effects.
- Prediction improvement, qualification, or raw-score superiority inferred from split design.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.final_origin_target_domain_evaluation. The canonical alias and provenance record is kept in the centralized provenance module.
