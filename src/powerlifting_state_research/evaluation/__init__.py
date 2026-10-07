"""Target-wise metrics and typed evaluation/result records."""

from .metrics import (
    MetricName,
    MetricResult,
    MetricStatus,
    NonFiniteMetricInputPolicy,
    TargetMetrics,
    canonical_target_metrics,
)
from .protocols import (
    AggregationRecord,
    EvaluationResult,
    ExclusionRecord,
    MetricEvidenceStatus,
    MetricIdentity,
    PredictionArtifactReference,
    ResultStatus,
    StratificationRecord,
    UncertaintyRecord,
)

__all__ = [
    "AggregationRecord",
    "EvaluationResult",
    "ExclusionRecord",
    "MetricEvidenceStatus",
    "MetricIdentity",
    "MetricName",
    "MetricResult",
    "MetricStatus",
    "NonFiniteMetricInputPolicy",
    "PredictionArtifactReference",
    "ResultStatus",
    "StratificationRecord",
    "TargetMetrics",
    "UncertaintyRecord",
    "canonical_target_metrics",
]
