"""
Shared observation model component declarations.

Shared observation-model references used by the benchmark compositions.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

observation_model_references: dict[str, ComponentReference] = {
    "athlete_state_training_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "athlete_state_training_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "field_velocity_and_load_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "field_velocity_and_load_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "performance_assessment_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "performance_assessment_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "performance_expression_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "performance_expression_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_transient_public_performance_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "latent_capacity_transient_public_performance_observation",
        ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
    ),
    "schedule_reporting_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "schedule_reporting_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_multi_channel_observation": ComponentReference(
        ComponentClass.OBSERVATION_MODEL,
        "seasonal_multi_channel_observation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
