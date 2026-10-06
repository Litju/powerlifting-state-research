"""
Shared evaluation component declarations.

Canonical evaluation-protocol references.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

evaluation_references: dict[str, ComponentReference] = {
    "class_normalized_five_output_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "class_normalized_five_output_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "final_origin_target_domain_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "final_origin_target_domain_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "four_target_weighted_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "four_target_weighted_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_change_canonical_sre_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "latent_capacity_change_canonical_sre_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "latent_capacity_change_diagnostic_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "latent_capacity_change_diagnostic_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "observed_origin_public_sre_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "observed_origin_public_sre_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
    "seasonal_five_output_consistency_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "seasonal_five_output_consistency_evaluation",
        ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
    ),
}
