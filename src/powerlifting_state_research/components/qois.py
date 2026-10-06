"""
Shared qoi component declarations.

Canonical quantity-of-interest references shared across related tasks.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

qoi_references: dict[str, ComponentReference] = {
    "four_performance_targets": ComponentReference(
        ComponentClass.QOI,
        "four_performance_targets",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_change": ComponentReference(
        ComponentClass.QOI, "latent_capacity_change", ComponentResolution.DIRECT_HISTORICAL_IDENTITY
    ),
    "observed_origin_performance_change": ComponentReference(
        ComponentClass.QOI,
        "observed_origin_performance_change",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_five_performance_outputs": ComponentReference(
        ComponentClass.QOI,
        "seasonal_five_performance_outputs",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
