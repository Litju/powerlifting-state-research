# Held-Out Final-Origin Evaluation of Five Performance Targets

## Research question

Using the refined class-normalized synthetic cross-lift system, can predictors trained on four earlier 25-day origins predict the same five outputs for an independent final-origin draw at days 340–365? This evaluates transfer within synthetic support, not human or general-domain transfer.

This question is classified as **CONTEMPORANEOUS_RESEARCH_QUESTION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Evaluate five performance targets on an independent held-out final origin within the class-normalized synthetic system.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: HELD_OUT_FINAL_ORIGIN_FIVE_TARGET_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Past/completed observations only. Training origins 200/260/315/340; validation/hidden at 340→365; no declared future-plan input.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | athlete_latent_state_dynamics | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | field_velocity_and_load_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | held_out_final_origin_five_target_performance_evaluation_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | held_out_final_origin_five_target_performance_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | seasonal_five_target_performance_outputs | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | class_normalized_table_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | held_out_final_origin_five_target_performance_evaluation | DIRECT_HISTORICAL_IDENTITY |

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

The scientific declaration is available as powerlifting_state_research.benchmarks.held_out_final_origin_five_target_performance_evaluation. The canonical alias and provenance record is kept in the centralized provenance module.
