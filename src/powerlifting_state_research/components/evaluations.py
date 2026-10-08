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
    "held_out_final_origin_five_target_performance_evaluation": ComponentReference(
        ComponentClass.EVALUATION,
        "held_out_final_origin_five_target_performance_evaluation",
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
    "iid_latent_capacity_change_four_metric_validation": ComponentReference(
        ComponentClass.EVALUATION,
        "iid_latent_capacity_change_four_metric_validation",
        ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
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
