"""Historical component identifiers mapped once to canonical scientific references.

This metadata preserves traceability; identifiers do not name public packages or mechanics.
"""

from __future__ import annotations

SOURCE_COMPONENT_IDENTITIES: dict[str, tuple[tuple[str, str], ...]] = {
    "psr:dataset-spec:pl-c21-stable-slope-tilt-sampling-design@1.0.0~30f3942a0a2b": (
        ("DATASET_SPEC", "stable_slope_tilt_four_target_forecasting_sampling_design"),
    ),
    "psr:dataset-spec:pl-c22-schedule-exposure-sampling-design@1.0.0~6fcc1c11df19": (
        ("DATASET_SPEC", "schedule_exposure_heterogeneity_forecasting_sampling_design"),
    ),
    "psr:dataset-spec:pl-legacy-capacity-early-sampling-design@1.0.0~200b45f1c717": (
        ("DATASET_SPEC", "seasonal_capacity_fatigue_five_target_forecasting_sampling_design"),
    ),
    "psr:dataset-spec:pl-legacy-capacity-refined-sampling-design@1.0.0~66448b8642d5": (
        (
            "DATASET_SPEC",
            "class_normalized_cross_lift_capacity_fatigue_forecasting_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-legacy-target-domain-split-sampling-design@1.0.0~fd842c9e9b0c": (
        ("DATASET_SPEC", "final_origin_target_domain_evaluation_sampling_design"),
    ),
    "psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@1.0.0~7098655518cd": (
        ("DATASET_SPEC", "parsimonious_latent_capacity_change_forecasting_sampling_design"),
    ),
    "psr:dataset-spec:v1-response-shared-sampling-inputs@1.0.0~23bb079da836": (
        ("DATASET_SPEC", "latent_origin_capacity_change_forecasting_sampling_design"),
        ("DATASET_SPEC", "observed_origin_performance_change_forecasting_sampling_design"),
    ),
    "psr:evaluation:c21-c22-four-target-release-contract@1.0.0~a17c43781876": (
        ("EVALUATION", "four_target_weighted_evaluation"),
    ),
    "psr:evaluation:legacy-prediction-physical-consistency-blend@1.0.0~a67b640c37ae": (
        ("EVALUATION", "seasonal_five_output_consistency_evaluation"),
    ),
    "psr:evaluation:refined-prediction-physical-consistency-blend@1.0.0~dceb437baad4": (
        ("EVALUATION", "class_normalized_five_output_evaluation"),
    ),
    "psr:evaluation:target-domain-public-validation@1.0.0~31076d7ca05d": (
        ("EVALUATION", "final_origin_target_domain_evaluation"),
    ),
    "psr:evaluation:v1-t0-public-only-sre@1.0.0~2181dbc99f16": (
        ("EVALUATION", "observed_origin_public_sre_evaluation"),
    ),
    "psr:evaluation:v1-t1-public-only-diagnostics@1.0.0~60c57c4744de": (
        ("EVALUATION", "latent_capacity_change_diagnostic_evaluation"),
    ),
    "psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f": (
        ("EVALUATION", "latent_capacity_change_canonical_sre_evaluation"),
    ),
    "psr:observation-model:c21-field-velocity-rpe-rir-readiness@1.0.0~bab5eaa0e137": (
        ("OBSERVATION_MODEL", "athlete_state_training_observation"),
    ),
    "psr:observation-model:c22-schedule-reporting-observation@1.0.0~c624f7e4e737": (
        ("OBSERVATION_MODEL", "schedule_reporting_observation"),
    ),
    "psr:observation-model:legacy-multi-channel-field-observation@1.0.0~4c95cbb9d46a": (
        ("OBSERVATION_MODEL", "seasonal_multi_channel_observation"),
    ),
    "psr:observation-model:refined-field-velocity-and-lpt@1.0.0~141fae096dc7": (
        ("OBSERVATION_MODEL", "field_velocity_and_load_observation"),
    ),
    "psr:observation-model:v1-performance-assessment-load-velocity@1.0.0~ac2781dad306": (
        ("OBSERVATION_MODEL", "performance_assessment_observation"),
    ),
    "psr:observation-model:world-v2-performance-expression-observation@1.0.0~c8a52272a9cd": (
        ("OBSERVATION_MODEL", "performance_expression_observation"),
    ),
    "psr:qoi:four-target-p1-p2-p4-p5@1.0.0~1ded2f48e4a3": (("QOI", "four_performance_targets"),),
    "psr:qoi:future-capacity-minus-noisy-origin-assessment@1.0.0~b7e407fe2b81": (
        ("QOI", "observed_origin_performance_change"),
    ),
    "psr:qoi:latent-capacity-change@1.0.0~675491124046": (("QOI", "latent_capacity_change"),),
    "psr:qoi:legacy-five-target-set@1.0.0~d0a410b2edfc": (
        ("QOI", "seasonal_five_performance_outputs"),
    ),
    "psr:representation:c21-c22-temporal-interface@1.0.0~ee6b1d7aace1": (
        ("REPRESENTATION", "four_target_temporal_inputs"),
    ),
    "psr:representation:published-legacy-tables@1.0.0~467ad9987e65": (
        ("REPRESENTATION", "seasonal_public_table_inputs"),
    ),
    "psr:representation:refined-legacy-tables@1.0.0~94f112f44552": (
        ("REPRESENTATION", "class_normalized_table_inputs"),
    ),
    "psr:representation:v1-response-feature-schema-v2@1.0.0~e9db564d4b3b": (
        ("REPRESENTATION", "dose_history_and_assessment_inputs"),
    ),
    "psr:representation:world-v2-participant-inputs-json-v2@1.0.0~2c2c7f0222c6": (
        ("REPRESENTATION", "weekly_performance_history_and_plan_inputs"),
    ),
    "psr:task:five-outputs-with-mixed-origin-25-day-labels@1.0.0~36e65b57cb2e": (
        ("TASK", "final_origin_seasonal_forecast"),
    ),
    "psr:task:five-seasonal-powerlifting-outputs@1.0.0~cc696be87ed4": (
        ("TASK", "seasonal_five_performance_forecast"),
    ),
    "psr:task:four-25-day-athlete-state-outputs@1.0.0~9a575a70b41e": (
        ("TASK", "four_performance_target_forecast"),
    ),
    "psr:task:latent-capacity-change@1.0.0~44fc77353e7a": (
        ("TASK", "latent_capacity_change_forecast"),
    ),
    "psr:task:v1-t0-observed-origin-performance-change@1.0.0~6fedfb6051bb": (
        ("TASK", "observed_origin_performance_change_forecast"),
    ),
    "psr:world:c21-athlete-state-stable-slope-tilt-world@1.0.0~8956f2327a14": (
        ("WORLD", "stable_slope_tilt_athlete_state"),
    ),
    "psr:world:c22-heterogeneous-schedule-exposure-world@1.0.0~55a292e3b1c6": (
        ("WORLD", "schedule_exposure_heterogeneity"),
    ),
    "psr:world:early-seasonal-capacity-load-velocity-world@1.0.0~168dadf66c15": (
        ("WORLD", "seasonal_capacity_fatigue"),
    ),
    "psr:world:refined-class-normalized-seasonal-cross-lift-world@1.0.0~c7dcec83d1f8": (
        ("WORLD", "class_normalized_cross_lift_capacity_fatigue"),
    ),
    "psr:world:v1-dose-memory-response-world@1.0.0~11b6f0033502": (
        ("WORLD", "dose_history_capacity_dynamics"),
    ),
    "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e": (
        ("WORLD", "parsimonious_capacity_expression"),
    ),
}
