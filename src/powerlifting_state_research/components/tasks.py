"""
Shared task component declarations.

Canonical task references shared across related benchmark compositions.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

task_references: dict[str, ComponentReference] = {
    "final_origin_seasonal_forecast": ComponentReference(
        ComponentClass.TASK,
        "final_origin_seasonal_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "four_performance_target_forecast": ComponentReference(
        ComponentClass.TASK,
        "four_performance_target_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_change_forecast": ComponentReference(
        ComponentClass.TASK,
        "latent_capacity_change_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "observed_origin_performance_change_forecast": ComponentReference(
        ComponentClass.TASK,
        "observed_origin_performance_change_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_five_performance_forecast": ComponentReference(
        ComponentClass.TASK,
        "seasonal_five_performance_forecast",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
