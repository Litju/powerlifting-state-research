"""Historical component identifiers mapped once to canonical scientific references.

This metadata preserves traceability; identifiers do not name public packages or mechanics.
"""

from __future__ import annotations

SOURCE_COMPONENT_IDENTITIES: dict[str, tuple[tuple[str, str], ...]] = {
    "psr:dataset-spec:pl-c21-stable-slope-tilt-sampling-design@1.0.0~30f3942a0a2b": (
        (
            "DATASET_SPEC",
            "four_target_load_velocity_and_competition_performance_forecasting_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-c22-schedule-exposure-sampling-design@1.0.0~6fcc1c11df19": (
        (
            "DATASET_SPEC",
            "performance_forecasting_under_schedule_exposure_reporting_heterogeneity_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-legacy-capacity-early-sampling-design@1.0.0~200b45f1c717": (
        (
            "DATASET_SPEC",
            "seasonal_five_target_load_velocity_performance_forecasting_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-legacy-capacity-refined-sampling-design@1.0.0~66448b8642d5": (
        (
            "DATASET_SPEC",
            "class_normalized_cross_lift_five_target_performance_forecasting_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-legacy-target-domain-split-sampling-design@1.0.0~fd842c9e9b0c": (
        (
            "DATASET_SPEC",
            "held_out_final_origin_five_target_performance_evaluation_sampling_design",
        ),
    ),
    "psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@1.0.0~7098655518cd": (
        (
            "DATASET_SPEC",
            "latent_capacity_change_with_transient_expression_forecasting_sampling_design",
        ),
    ),
    "psr:dataset-spec:v1-response-shared-sampling-inputs@1.0.0~23bb079da836": (
        ("DATASET_SPEC", "latent_origin_capacity_change_forecasting_sampling_design"),
        ("DATASET_SPEC", "observed_origin_referenced_capacity_change_sampling_design"),
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
        ("EVALUATION", "held_out_final_origin_five_target_performance_evaluation"),
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
    "psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8": (
        ("EVALUATION", "iid_latent_capacity_change_four_metric_validation"),
    ),
    "psr:metric:rmse@1.0.0~0a9b0918a7aa": (("METRIC", "iid_public_rmse"),),
    "psr:metric:mae@1.0.0~7319598a8a18": (("METRIC", "iid_public_mae"),),
    "psr:metric:r-squared@1.0.0~00bad728358d": (("METRIC", "iid_public_r_squared"),),
    "psr:metric:sre-population-sd-ddof-0@1.0.0~f3341587fd14": (
        ("METRIC", "iid_public_sre_ddof_0"),
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
    "psr:qoi:four-target-p1-p2-p4-p5@1.0.0~1ded2f48e4a3": (
        ("QOI", "four_load_velocity_and_competition_performance_targets"),
    ),
    "psr:qoi:future-capacity-minus-noisy-origin-assessment@1.0.0~b7e407fe2b81": (
        ("QOI", "observed_origin_referenced_capacity_change"),
    ),
    "psr:qoi:latent-capacity-change@1.0.0~675491124046": (("QOI", "latent_capacity_change"),),
    "psr:qoi:legacy-five-target-set@1.0.0~d0a410b2edfc": (
        ("QOI", "seasonal_five_target_performance_outputs"),
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
        ("TASK", "held_out_final_origin_five_target_performance_forecast"),
    ),
    "psr:task:five-seasonal-powerlifting-outputs@1.0.0~cc696be87ed4": (
        ("TASK", "seasonal_five_target_performance_forecast"),
    ),
    "psr:task:four-25-day-athlete-state-outputs@1.0.0~9a575a70b41e": (
        ("TASK", "four_target_load_velocity_and_competition_performance_forecast"),
    ),
    "psr:task:latent-capacity-change@1.0.0~44fc77353e7a": (
        ("TASK", "latent_capacity_change_forecast"),
    ),
    "psr:task:v1-t0-observed-origin-performance-change@1.0.0~6fedfb6051bb": (
        ("TASK", "observed_origin_referenced_capacity_change_forecast"),
    ),
    "psr:world:c21-athlete-state-stable-slope-tilt-world@1.0.0~8956f2327a14": (
        ("WORLD", "longitudinal_athlete_state_dynamics"),
    ),
    "psr:world:c22-heterogeneous-schedule-exposure-world@1.0.0~55a292e3b1c6": (
        ("WORLD", "athlete_state_transition_dynamics"),
    ),
    "psr:world:early-seasonal-capacity-load-velocity-world@1.0.0~168dadf66c15": (
        ("WORLD", "latent_state_transition_dynamics"),
    ),
    "psr:world:refined-class-normalized-seasonal-cross-lift-world@1.0.0~c7dcec83d1f8": (
        ("WORLD", "athlete_latent_state_dynamics"),
    ),
    "psr:world:v1-dose-memory-response-world@1.0.0~11b6f0033502": (
        ("WORLD", "training_dose_history_capacity_dynamics"),
    ),
    "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e": (
        ("WORLD", "latent_capacity_transient_performance_expression_dynamics"),
    ),
}

# Old bootstrap keys are lookup metadata only; component registries contain only new names.
SOURCE_COMPONENT_ALIASES: dict[str, str] = {
    "seasonal_capacity_fatigue": "latent_state_transition_dynamics",
    "seasonal_load_velocity_and_performance": "latent_state_transition_dynamics",
    "class_normalized_cross_lift_capacity_fatigue": "athlete_latent_state_dynamics",
    "class_normalized_cross_lift_performance": "athlete_latent_state_dynamics",
    "stable_slope_tilt_athlete_state": "longitudinal_athlete_state_dynamics",
    "four_target_longitudinal_performance_state": "longitudinal_athlete_state_dynamics",
    "schedule_exposure_heterogeneity": "athlete_state_transition_dynamics",
    "heterogeneous_training_schedule_exposure_and_reporting": "athlete_state_transition_dynamics",
    "dose_history_capacity_dynamics": "training_dose_history_capacity_dynamics",
    "parsimonious_capacity_expression": "latent_capacity_transient_performance_expression_dynamics",
    "seasonal_capacity_fatigue_five_target_forecasting_sampling_design": (
        "seasonal_five_target_load_velocity_performance_forecasting_sampling_design"
    ),
    "class_normalized_cross_lift_capacity_fatigue_forecasting_sampling_design": (
        "class_normalized_cross_lift_five_target_performance_forecasting_sampling_design"
    ),
    "final_origin_target_domain_evaluation_sampling_design": (
        "held_out_final_origin_five_target_performance_evaluation_sampling_design"
    ),
    "stable_slope_tilt_four_target_forecasting_sampling_design": (
        "four_target_load_velocity_and_competition_performance_forecasting_sampling_design"
    ),
    "schedule_exposure_heterogeneity_forecasting_sampling_design": (
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity_sampling_design"
    ),
    "training_schedule_exposure_heterogeneity_forecasting_sampling_design": (
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity_sampling_design"
    ),
    "observed_origin_performance_change_forecasting_sampling_design": (
        "observed_origin_referenced_capacity_change_sampling_design"
    ),
    "parsimonious_latent_capacity_change_forecasting_sampling_design": (
        "latent_capacity_change_with_transient_expression_forecasting_sampling_design"
    ),
    "final_origin_target_domain_evaluation": (
        "held_out_final_origin_five_target_performance_evaluation"
    ),
    "four_performance_target_forecast": (
        "four_target_load_velocity_and_competition_performance_forecast"
    ),
    "final_origin_seasonal_forecast": "held_out_final_origin_five_target_performance_forecast",
    "seasonal_five_performance_forecast": "seasonal_five_target_performance_forecast",
    "four_performance_targets": "four_load_velocity_and_competition_performance_targets",
    "seasonal_five_performance_outputs": "seasonal_five_target_performance_outputs",
    "observed_origin_performance_change": "observed_origin_referenced_capacity_change",
    "observed_origin_performance_change_forecast": (
        "observed_origin_referenced_capacity_change_forecast"
    ),
}
