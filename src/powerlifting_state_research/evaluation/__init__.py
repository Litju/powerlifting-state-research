"""Target-wise metrics and typed evaluation/result records."""

from .identity import EVALUATION_ID, METRIC_IDENTITIES
from .metrics import (
    MetricName,
    MetricResult,
    MetricStatus,
    NonFiniteMetricInputPolicy,
    TargetMetrics,
    canonical_target_metrics,
)
from .prediction import PREDICTION_SCHEMA_ID, PredictionRow, canonical_prediction_jsonl
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
    "EVALUATION_ID",
    "ExclusionRecord",
    "MetricEvidenceStatus",
    "MetricIdentity",
    "METRIC_IDENTITIES",
    "MetricName",
    "MetricResult",
    "MetricStatus",
    "NonFiniteMetricInputPolicy",
    "PredictionArtifactReference",
    "PREDICTION_SCHEMA_ID",
    "PredictionRow",
    "ResultStatus",
    "StratificationRecord",
    "TargetMetrics",
    "UncertaintyRecord",
    "canonical_target_metrics",
    "canonical_prediction_jsonl",
]
