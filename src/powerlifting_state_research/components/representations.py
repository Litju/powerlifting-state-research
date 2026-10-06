"""
Shared representation component declarations.

Canonical input-representation references.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

representation_references: dict[str, ComponentReference] = {
    "class_normalized_table_inputs": ComponentReference(
        ComponentClass.REPRESENTATION,
        "class_normalized_table_inputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "dose_history_and_assessment_inputs": ComponentReference(
        ComponentClass.REPRESENTATION,
        "dose_history_and_assessment_inputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "four_target_temporal_inputs": ComponentReference(
        ComponentClass.REPRESENTATION,
        "four_target_temporal_inputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_public_table_inputs": ComponentReference(
        ComponentClass.REPRESENTATION,
        "seasonal_public_table_inputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "weekly_performance_history_and_plan_inputs": ComponentReference(
        ComponentClass.REPRESENTATION,
        "weekly_performance_history_and_plan_inputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
