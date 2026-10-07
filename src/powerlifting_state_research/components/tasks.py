"""
Shared task component declarations.

Canonical task references shared across related benchmark compositions.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

task_references: dict[str, ComponentReference] = {
    "held_out_final_origin_five_target_performance_forecast": ComponentReference(
        ComponentClass.TASK,
        "held_out_final_origin_five_target_performance_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "four_target_load_velocity_and_competition_performance_forecast": ComponentReference(
        ComponentClass.TASK,
        "four_target_load_velocity_and_competition_performance_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_change_forecast": ComponentReference(
        ComponentClass.TASK,
        "latent_capacity_change_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "observed_origin_referenced_capacity_change_forecast": ComponentReference(
        ComponentClass.TASK,
        "observed_origin_referenced_capacity_change_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_five_target_performance_forecast": ComponentReference(
        ComponentClass.TASK,
        "seasonal_five_target_performance_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
