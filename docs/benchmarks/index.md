# Historical benchmark registry

The registry contains eight reconstructed historical specimens and one independent public-native benchmark variant. The historical projection and the executable native variant have separate BenchmarkSpec identities.

Registry enumeration is lexicographic by canonical scientific slug.

| Scientific formulation | Package slug | Historical state | Qualification | Completeness | Public implementation |
|---|---|---|---|---|---|
| [Class-Normalized Cross-Lift Five-Target Performance Forecasting](class-normalized-cross-lift-five-target-performance-forecasting.md) | class_normalized_cross_lift_five_target_performance_forecasting | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Four-Target Load–Velocity and Competition Performance Forecasting](four-target-load-velocity-and-competition-performance-forecasting.md) | four_target_load_velocity_and_competition_performance_forecasting | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Held-Out Final-Origin Evaluation of Five Performance Targets](held-out-final-origin-five-target-performance-evaluation.md) | held_out_final_origin_five_target_performance_evaluation | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Latent Capacity-Change Forecasting with Transient Performance Expression](latent-capacity-change-with-transient-expression-forecasting.md) | latent_capacity_change_with_transient_expression_forecasting | REPRODUCIBLE_SPEC | QUALIFIED_HISTORICAL | FULL_FROM_EXISTING_EVIDENCE | PUBLIC_IMPLEMENTATION_PENDING |
| [Latent-Origin Capacity-Change Forecasting](latent-origin-capacity-change-forecasting.md) | latent_origin_capacity_change_forecasting | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Observed-Origin-Referenced Capacity-Change Forecasting](observed-origin-referenced-capacity-change-forecasting.md) | observed_origin_referenced_capacity_change_forecasting | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Seasonal Five-Target Load–Velocity and Performance Forecasting](seasonal-five-target-load-velocity-performance-forecasting.md) | seasonal_five_target_load_velocity_performance_forecasting | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |
| [Performance Forecasting Under Schedule, Exposure, and Reporting Heterogeneity](performance-forecasting-under-schedule-exposure-reporting-heterogeneity.md) | performance_forecasting_under_schedule_exposure_reporting_heterogeneity | PARTIALLY_RECONSTRUCTED | NOT_QUALIFIED_OR_UNRESOLVED | PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS | PUBLIC_IMPLEMENTATION_PENDING |

Seven historical specimens are partially reconstructed. The latent-capacity and transient-expression historical projection has a reproducible specification with an unresolved readiness-receipt caveat, but its historical scrambled-Sobol DatasetSpec is not implemented by the public IID generator.

## Public-native variants

| Scientific formulation | Canonical slug | Identity authority | DatasetSpec | Public implementation |
|---|---|---|---|---|
| [IID-Sampled Latent Capacity-Change Forecasting with Transient Performance Expression](iid-latent-capacity-change-with-transient-expression-forecasting.md) | iid_latent_capacity_change_with_transient_expression_forecasting | PUBLIC_NATIVE | IID pseudorandom Uniform(0,1) | PUBLIC_IMPLEMENTED |

The public-native variant shares WORLD mechanics, task, QOI, and representation with the historical projection. It has direct public-native population, intervention, observation, DatasetSpec, and four-metric evaluation identities. Its sampling design differs from historical scrambled Sobol, so its semantic digest is distinct. The other seven historical records remain PUBLIC_IMPLEMENTATION_PENDING.

Each row links to a public research card. Historical aliases are available only in the centralized provenance metadata.
