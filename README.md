# Powerlifting State Research

Open research on latent powerlifting capacity, performance expression, and forecast evaluation in synthetic dynamical systems.

This repository contains eight reconstructed historical benchmark specimens across six shared worlds. The latent-capacity-change benchmark with transient performance expression now has an independently authored public mechanics and deterministic data generator. The other seven specimens remain registry records marked PUBLIC_IMPLEMENTATION_PENDING.

## Scientific object

The program separates latent capacity and its change from transient performance expression, observation noise, training exposure, population construction, and forecast targets. A benchmark declaration composes shared scientific components with a task, information boundary, dataset specification, and evaluation.

## Historical benchmark registry

See [scientific naming decisions](docs/provenance/scientific-naming-decisions.md) for the audited benchmark and world names, terminology rationale, citations, and retained provenance aliases.

| Scientific formulation | Canonical package slug | Historical status | Completeness | Public implementation |
|---|---|---|---|---|
| [Class-Normalized Cross-Lift Five-Target Performance Forecasting](docs/benchmarks/class-normalized-cross-lift-five-target-performance-forecasting.md) | class_normalized_cross_lift_five_target_performance_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Four-Target Load–Velocity and Competition Performance Forecasting](docs/benchmarks/four-target-load-velocity-and-competition-performance-forecasting.md) | four_target_load_velocity_and_competition_performance_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Held-Out Final-Origin Evaluation of Five Performance Targets](docs/benchmarks/held-out-final-origin-five-target-performance-evaluation.md) | held_out_final_origin_five_target_performance_evaluation | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Latent Capacity-Change Forecasting with Transient Performance Expression](docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md) | latent_capacity_change_with_transient_expression_forecasting | REPRODUCIBLE_SPEC | FULL_FROM_EXISTING_EVIDENCE | PUBLIC_IMPLEMENTED |
| [Latent-Origin Capacity-Change Forecasting](docs/benchmarks/latent-origin-capacity-change-forecasting.md) | latent_origin_capacity_change_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Observed-Origin-Referenced Capacity-Change Forecasting](docs/benchmarks/observed-origin-referenced-capacity-change-forecasting.md) | observed_origin_referenced_capacity_change_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Seasonal Five-Target Load–Velocity and Performance Forecasting](docs/benchmarks/seasonal-five-target-load-velocity-performance-forecasting.md) | seasonal_five_target_load_velocity_performance_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Performance Forecasting Under Schedule, Exposure, and Reporting Heterogeneity](docs/benchmarks/performance-forecasting-under-schedule-exposure-reporting-heterogeneity.md) | performance_forecasting_under_schedule_exposure_reporting_heterogeneity | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |

Historical aliases and frozen component identity strings are provenance or identity references. Public paths, module names, tests, and descriptions use the scientific formulations above.

## What results can say

Results from a synthetic benchmark characterize prediction under that declared synthetic system and data realization. They do not establish real-athlete validity, causal training effects, biological parameter identification, or broad out-of-domain performance. Comparisons require aligned targets, information boundaries, support, and evaluation rules.

## Repository map

- **src/powerlifting_state_research/** — typed declarations, shared components, and explicit benchmark registry.
- **docs/** — public scientific overview, contract, benchmark cards, claim boundaries, and reproducibility guidance.
- **data/** — dataset specifications and public realization-manifest homes; no historical data bytes.
- **models/** — model-family, training, comparator, and checkpoint-manifest homes; no historical weights.
- **studies/** and **audits/** — distinct study and cross-benchmark analysis homes.
- **results/** and **artifacts/** — identified generated outputs and publication bundles.
- **tests/** — registry, component-reuse, provenance, descriptor, and public-mechanics checks.

## Reproducibility

Benchmark semantics are represented in typed Python. Dataset realizations, model records, predictions, and evaluations have separate identities. A semantic benchmark ID is not minted until its complete contract is validated. The initial package version 0.1.0 is independent of benchmark identities.

## Licensing

Source code is MIT-licensed under [LICENSE](LICENSE). Project-authored Markdown documentation is CC BY 4.0 under [LICENSE-DOCS](LICENSE-DOCS). Data and model artifacts carry rights per artifact; this repository does not license historical private material.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the frozen research homes and implementation boundaries.
