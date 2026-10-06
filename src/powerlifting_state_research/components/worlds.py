"""
Shared world component declarations.

Six canonical latent-system references shared across the eight historical specimens.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

world_references: dict[str, ComponentReference] = {
    "class_normalized_cross_lift_capacity_fatigue": ComponentReference(
        ComponentClass.WORLD,
        "class_normalized_cross_lift_capacity_fatigue",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "dose_history_capacity_dynamics": ComponentReference(
        ComponentClass.WORLD,
        "dose_history_capacity_dynamics",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "parsimonious_capacity_expression": ComponentReference(
        ComponentClass.WORLD,
        "parsimonious_capacity_expression",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "schedule_exposure_heterogeneity": ComponentReference(
        ComponentClass.WORLD,
        "schedule_exposure_heterogeneity",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_capacity_fatigue": ComponentReference(
        ComponentClass.WORLD,
        "seasonal_capacity_fatigue",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "stable_slope_tilt_athlete_state": ComponentReference(
        ComponentClass.WORLD,
        "stable_slope_tilt_athlete_state",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
