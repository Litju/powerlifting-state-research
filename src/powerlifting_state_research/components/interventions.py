"""
Shared intervention regime component declarations.

Intervention-regime identities and unresolved historical direct IDs.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

intervention_regime_references: dict[str, ComponentReference] = {
    "latent_capacity_transient_public_training_regime": ComponentReference(
        ComponentClass.INTERVENTION_REGIME,
        "latent_capacity_transient_public_training_regime",
        ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
    )
}
