# Schedule/Exposure Heterogeneity Four-Target Forecasting

## Research question

Within a synthetic world with heterogeneous training schedules, exposure, and reporting, can models forecast target-load velocity, reference-velocity load, next-set velocity loss, and competition-day capacity over 25 days from completed histories? The available evidence does not establish that added heterogeneity improves prediction.

This question is classified as **RETROSPECTIVE_TECHNICAL_CHARACTERIZATION**. It characterizes the recorded task where retrospective; it does not assert that the same wording was the original historical motivation.

## Scientific objective

Characterize the same four targets when training schedule, exposure, and reporting vary in a synthetic world.

## Specimen and completeness

Historical specimen status: PARTIALLY_RECONSTRUCTED. Historical qualification: NOT_QUALIFIED_OR_UNRESOLVED. Completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS. Public implementation: PUBLIC_IMPLEMENTATION_PENDING.

A reproducible historical specification is not the same as an independent public implementation or a qualification result.

## Task and information boundary

- Task type: FOUR_OUTPUT_25_DAY_FORECAST
- Target ontology: MULTI_OUTPUT_OTHER
- Information setting: HISTORY_ONLY
- Historical prediction boundary: Point-in-time completed histories for 25-day forecast; no declared future-plan input in recovered interface.

## Bound scientific components

| Component | Canonical reference | Resolution |
|---|---|---|
| WORLD | schedule_exposure_heterogeneity | DIRECT_HISTORICAL_IDENTITY |
| POPULATION | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| INTERVENTION_REGIME | unresolved direct identity | UNRESOLVED_DIRECT_ID |
| OBSERVATION_MODEL | schedule_reporting_observation | DIRECT_HISTORICAL_IDENTITY |
| DATASET_SPEC | schedule_exposure_heterogeneity_forecasting_sampling_design | DIRECT_HISTORICAL_IDENTITY |
| TASK | four_performance_target_forecast | DIRECT_HISTORICAL_IDENTITY |
| QOI | four_performance_targets | DIRECT_HISTORICAL_IDENTITY |
| REPRESENTATION | four_target_temporal_inputs | DIRECT_HISTORICAL_IDENTITY |
| EVALUATION | four_target_weighted_evaluation | DIRECT_HISTORICAL_IDENTITY |

Repeated canonical references are declared once in the shared component modules. Unresolved component identities remain explicitly unresolved.

## Supported interpretation

- the schedule/exposure formulation adds schedule/exposure and reporting heterogeneity over stable-slope/tilt state core.
- schedule/exposure formulation has separate data identity and shared four-target task contract.

## Claim limits

- schedule/exposure formulation qualification/performance inferred from stable-slope/tilt formulation checkpoint.
- Human, biological, intervention-effect, parameter-ID, or OOD claims.
- Do not claim unresolved intermediate variants or treat a branch/version discrepancy as settled.

These records describe synthetic benchmark formulations. They do not establish real-athlete validity, causal training effects, biological parameter recovery, or general-domain transfer.

## Data and implementation

No historical dataset, checkpoint, or benchmark mechanics are bundled at bootstrap. Public data realizations, model weights, and results require their own identity, provenance, and rights records.

The scientific declaration is available as powerlifting_state_research.benchmarks.schedule_exposure_heterogeneity_forecasting. The canonical alias and provenance record is kept in the centralized provenance module.
