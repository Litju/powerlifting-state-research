"""
Shared dataset spec component declarations.

Dataset-spec references; each future realization has a separate identity.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

dataset_spec_references: dict[str, ComponentReference] = {
    "class_normalized_cross_lift_capacity_fatigue_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "class_normalized_cross_lift_capacity_fatigue_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "final_origin_target_domain_evaluation_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "final_origin_target_domain_evaluation_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_origin_capacity_change_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "latent_origin_capacity_change_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "observed_origin_performance_change_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "observed_origin_performance_change_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "parsimonious_latent_capacity_change_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "parsimonious_latent_capacity_change_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "schedule_exposure_heterogeneity_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "schedule_exposure_heterogeneity_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_capacity_fatigue_five_target_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "seasonal_capacity_fatigue_five_target_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "stable_slope_tilt_four_target_forecasting_sampling_design": ComponentReference(
        ComponentClass.DATASET_SPEC,
        "stable_slope_tilt_four_target_forecasting_sampling_design",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
