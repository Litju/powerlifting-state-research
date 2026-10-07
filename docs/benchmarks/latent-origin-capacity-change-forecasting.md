# Latent-Origin Capacity-Change Forecasting

## Research question

At the forecast origin, using noisy pre-origin observations and the participant-visible declared dose/intensity plan, how accurately can a model forecast latent capacity change for three lifts at horizons 14, 28, and 56 days while keeping measurement noise in the inputs and out of target truth? This is conditional synthetic prediction, not a causal effect, latent-coordinate recovery, or human validity.

This question is classified as **CONTEMPORANEOUS_RESEARCH_QUESTION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Forecast latent capacity change while retaining noisy origin assessment as an input rather than target truth.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: LATENT_CAPACITY_CHANGE_FORECAST
- Target ontology: LATENT_CAPACITY_CHANGE
- Information setting: DECLARED_FUTURE_PLAN_VISIBLE
- Historical prediction boundary: Origin 224; dose-history observations through origin and complete declared future dose/intensity plan; future realized outcomes unavailable.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | training_dose_history_capacity_dynamics | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | performance_assessment_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | latent_origin_capacity_change_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | latent_capacity_change_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | latent_capacity_change | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | dose_history_and_assessment_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | latent_capacity_change_diagnostic_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- Target migration isolates latent capacity-change QOI on same 2,048 dose-history inputs.
- Public diagnostics support claims only about this task/folds.

## Claim limits

- Individual causal treatment effect or responder classification.
- Human validity, biological parameter ID, broad OOD, hidden/final qualification.
- Raw score ranking against observed-origin performance change or latent capacity change with transient performance expression.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.latent_origin_capacity_change_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
