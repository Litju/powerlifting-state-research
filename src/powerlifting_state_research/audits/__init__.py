"""Cross-benchmark validity contracts and evidence-state profiles."""

from .profiles import VERSION_VALIDITY_PROFILES
from .specifications import (
    ATTACK_SPECS,
    AUDIT_AXES,
    BENCHMARK_VERSIONS,
    VALIDITY_AXES,
    AttackSpec,
    AuditAxis,
    AuditResult,
    AuditSpec,
    AuditStatus,
    ValidityAxis,
    VersionValidityProfile,
)

__all__ = [
    "ATTACK_SPECS",
    "AUDIT_AXES",
    "BENCHMARK_VERSIONS",
    "VERSION_VALIDITY_PROFILES",
    "VALIDITY_AXES",
    "AttackSpec",
    "AuditAxis",
    "AuditResult",
    "AuditSpec",
    "AuditStatus",
    "ValidityAxis",
    "VersionValidityProfile",
]
