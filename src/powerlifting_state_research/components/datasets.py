"""
Shared dataset spec component declarations.

Dataset-spec references; each future realization has a separate identity.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

dataset_spec_references: dict[str, ComponentReference] = {
    (
        "class_normalized_cross_lift_five_target_performance_forecasting_sampling_design"
    ): ComponentReference(
        ComponentClass.DATASET_SPEC,
        "class_normalized_cross_lift_five_target_performance_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "held_out_final_origin_five_target_performance_evaluation_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "held_out_final_origin_five_target_performance_evaluation_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_origin_capacity_change_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "latent_origin_capacity_change_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "observed_origin_referenced_capacity_change_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "observed_origin_referenced_capacity_change_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    (
        "latent_capacity_change_with_transient_expression_forecasting_sampling_design"
    ): ComponentReference(
        ComponentClass.DATASET_SPEC,
        "latent_capacity_change_with_transient_expression_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "iid_latent_capacity_change_with_transient_expression_forecasting_sampling_design": (
        ComponentReference(
            ComponentClass.DATASET_SPEC,
            "iid_latent_capacity_change_with_transient_expression_forecasting_sampling_design",
            ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
        )
    ),
    (
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity_sampling_design"
    ): ComponentReference(
        ComponentClass.DATASET_SPEC,
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    (
        "seasonal_five_target_load_velocity_performance_forecasting_sampling_design"
    ): ComponentReference(
        ComponentClass.DATASET_SPEC,
        "seasonal_five_target_load_velocity_performance_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    (
        "four_target_load_velocity_and_competition_performance_forecasting_sampling_design"
    ): ComponentReference(
        ComponentClass.DATASET_SPEC,
        "four_target_load_velocity_and_competition_performance_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
