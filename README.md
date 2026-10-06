# Powerlifting State Research

Open research on latent powerlifting capacity, performance expression, and forecast evaluation in synthetic dynamical systems.

This repository starts with a public-safe research registry and typed package skeleton. It contains eight reconstructed historical benchmark specimens across six shared worlds. **No independent public benchmark mechanics are implemented at bootstrap.** Every specimen remains marked PUBLIC_IMPLEMENTATION_PENDING.

The first independent public mechanics work is planned for the parsimonious latent capacity-change formulation in the next research phase. This repository does not implement that world at bootstrap.

## Scientific object

The program separates latent capacity and its change from transient performance expression, observation noise, training exposure, population construction, and forecast targets. A benchmark declaration composes shared scientific components with a task, information boundary, dataset specification, and evaluation.

## Historical benchmark registry

| Scientific formulation | Canonical package slug | Historical status | Completeness | Public implementation |
|---|---|---|---|---|
| [Seasonal Capacity–Fatigue Forecasting with Five Performance Targets](docs/benchmarks/seasonal-capacity-fatigue-five-target-forecasting.md) | seasonal_capacity_fatigue_five_target_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Class-Normalized Cross-Lift Capacity–Fatigue Forecasting with Five Targets](docs/benchmarks/class-normalized-cross-lift-capacity-fatigue-forecasting.md) | class_normalized_cross_lift_capacity_fatigue_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Final-Origin Target-Domain Evaluation of Seasonal Performance Forecasts](docs/benchmarks/final-origin-target-domain-evaluation.md) | final_origin_target_domain_evaluation | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Stable-Slope/Tilt Four-Target Athlete-State Forecasting](docs/benchmarks/stable-slope-tilt-four-target-forecasting.md) | stable_slope_tilt_four_target_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Schedule/Exposure Heterogeneity Four-Target Forecasting](docs/benchmarks/schedule-exposure-heterogeneity-forecasting.md) | schedule_exposure_heterogeneity_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Observed-Origin Performance-Change Forecasting](docs/benchmarks/observed-origin-performance-change-forecasting.md) | observed_origin_performance_change_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Latent-Origin Capacity-Change Forecasting](docs/benchmarks/latent-origin-capacity-change-forecasting.md) | latent_origin_capacity_change_forecasting | PARTIALLY_RECONSTRUCTED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Parsimonious Latent Capacity-Change Forecasting with Transient Performance Expression](docs/benchmarks/parsimonious-latent-capacity-change-forecasting.md) | parsimonious_latent_capacity_change_forecasting | REPRODUCIBLE_SPEC | FULL_FROM_EXISTING_EVIDENCE | PUBLIC_IMPLEMENTATION_PENDING |

Historical aliases and source identity strings are provenance metadata in the package registry. Public paths, module names, tests, and documentation use the scientific formulations above.

## What results can say

Results from a synthetic benchmark characterize prediction under that declared synthetic system and data realization. They do not establish real-athlete validity, causal training effects, biological parameter identification, or broad out-of-domain performance. Comparisons require aligned targets, information boundaries, support, and evaluation rules.

## Repository map

- **src/powerlifting_state_research/** — typed declarations, shared components, and explicit benchmark registry.
- **docs/** — public scientific overview, contract, benchmark cards, claim boundaries, and reproducibility guidance.
- **data/** — dataset specifications and public realization-manifest homes; no historical data bytes.
- **models/** — model-family, training, comparator, and checkpoint-manifest homes; no historical weights.
- **studies/** and **audits/** — distinct study and cross-benchmark analysis homes.
- **results/** and **artifacts/** — identified generated outputs and publication bundles.
- **tests/** — registry, component-reuse, provenance, and descriptor smoke checks.

## Reproducibility

Benchmark semantics are represented in typed Python. Dataset realizations, model records, predictions, and evaluations have separate identities. A semantic benchmark ID is not minted until its complete contract is validated. The initial package version 0.1.0 is independent of benchmark identities.

## Licensing

Source code is MIT-licensed under [LICENSE](LICENSE). Project-authored Markdown documentation is CC BY 4.0 under [LICENSE-DOCS](LICENSE-DOCS). Data and model artifacts carry rights per artifact; this repository does not license historical private material.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the frozen research homes and implementation boundaries.
