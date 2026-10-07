"""Shared population component references for historical and public-native records."""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

population_references: dict[str, ComponentReference] = {
    "latent_capacity_transient_public_uniform_coordinates": ComponentReference(
        ComponentClass.POPULATION,
        "latent_capacity_transient_public_uniform_coordinates",
        ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
    )
}
