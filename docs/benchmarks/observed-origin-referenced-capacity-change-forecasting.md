# Observed-Origin-Referenced Capacity-Change Forecasting

## Research question

At the forecast origin, can a model using noisy performance observations through that origin and the participant-visible declared dose/intensity plan predict future modeled capacity relative to the noisy observed-origin assessment for squat, bench, and deadlift at horizons 14, 28, and 56 days? This is not a difference between two observed performance assessments, a causal effect, or the same estimand as latent-origin capacity change.

This question is classified as **RETROSPECTIVE_TECHNICAL_CHARACTERIZATION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Forecast future capacity relative to a noisy observed-origin assessment under a declared future plan in a synthetic dose-history world.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE_FORECAST
- Target ontology: OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE
- Information setting: DECLARED_FUTURE_PLAN_VISIBLE
- Historical prediction boundary: Origin 224; use observations through origin and complete declared future dose/intensity plan. Future realized outcomes are unavailable.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | training_dose_history_capacity_dynamics | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | performance_assessment_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | observed_origin_referenced_capacity_change_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | observed_origin_referenced_capacity_change_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | observed_origin_referenced_capacity_change | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | dose_history_and_assessment_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | observed_origin_public_sre_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- The target is future modeled capacity relative to a noisy observed-origin assessment, not observed-to-observed performance change.
- dose-history interface exposes future dose/intensity plan and measurements through origin.

## Claim limits

- Pure latent-capacity-change, causal effect, responder classification, real-athlete validity, biological parameter ID.
- Do not rank raw scores across the observed-origin target, latent-origin target, or different dynamical systems.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.observed_origin_referenced_capacity_change_forecasting. The historical alias and provenance record is kept in the centralized provenance module.
