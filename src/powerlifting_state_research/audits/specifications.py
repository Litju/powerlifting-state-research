"""Frozen cross-benchmark audit-axis declarations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditAxis:
    slug: str
    purpose: str


AUDIT_AXES: tuple[AuditAxis, ...] = (
    AuditAxis("reproducibility", "Exact regeneration and identity agreement."),
    AuditAxis("information_leakage", "Information-boundary and target leakage."),
    AuditAxis("observability", "Latent-state and target observability."),
    AuditAxis("structural_reconstructability", "Structural target/world reconstruction."),
    AuditAxis(
        "public_surrogate_reconstructability", "Reconstruction from participant-public inputs."
    ),
    AuditAxis("simple_model_frontier", "Strong simple/reference comparator frontier."),
    AuditAxis("representation_dependence", "Representation and input-transform dependence."),
    AuditAxis(
        "machine_learning_load_bearing",
        "Learned-method contribution under controlled alternatives.",
    ),
    AuditAxis("history_cadence_sensitivity", "History length and observation-cadence sensitivity."),
    AuditAxis("intervention_robustness", "Target-domain and intervention-regime robustness."),
    AuditAxis("model_ranking_stability", "Model ranking stability across benchmark formulations."),
)
