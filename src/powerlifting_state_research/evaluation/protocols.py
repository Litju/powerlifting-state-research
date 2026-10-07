"""Typed evaluation and result records; metric calculation remains target-wise."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ..artifacts.manifests import RightsMetadata
from ..contracts.serialization import require_scientific_id, sha256_record
from ..models.references import (
    CheckpointReference,
    EnvironmentProvenance,
    FittedInstanceReference,
    ModelReference,
    RNGProvenance,
    TrainingProtocolReference,
)
from .metrics import MetricName, TargetMetrics


class ResultStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class MetricEvidenceStatus(StrEnum):
    HISTORICAL_REPORTED = "HISTORICAL_REPORTED"
    CANONICAL_RESEARCH = "CANONICAL_RESEARCH"
    RECOMPUTED_CANONICAL = "RECOMPUTED_CANONICAL"
    NOT_COMPARABLE = "NOT_COMPARABLE"


@dataclass(frozen=True, slots=True)
class MetricIdentity:
    metric_id: str
    metric: MetricName
    definition: str
    evidence_status: MetricEvidenceStatus

    def __post_init__(self) -> None:
        if any(not item.strip() for item in (self.metric_id, self.definition)):
            raise ValueError("metric identity and definition must be explicit")
        require_scientific_id(self.metric_id, "metric ID")


@dataclass(frozen=True, slots=True)
class AggregationRecord:
    aggregation_id: str
    metric_id: str
    value: float
    unit: str
    target_order: tuple[str, ...]
    weights: tuple[float, ...] = ()
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.aggregation_id.strip() or not self.metric_id.strip() or not self.unit.strip():
            raise ValueError("aggregation identities and units must be explicit")
        if self.weights and len(self.weights) != len(self.target_order):
            raise ValueError("aggregation weights must align with the declared target order")
        if self.weights and (self.rationale is None or not self.rationale.strip()):
            raise ValueError("weighted aggregation needs a rationale")


@dataclass(frozen=True, slots=True)
class StratificationRecord:
    axis: str
    levels: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.axis.strip() or not self.levels or not self.rationale.strip():
            raise ValueError("stratification needs an axis, levels, and rationale")


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    row_identity: str
    target: str
    reason: str

    def __post_init__(self) -> None:
        if any(not item.strip() for item in (self.row_identity, self.target, self.reason)):
            raise ValueError("exclusions need a row, target, and reason")


@dataclass(frozen=True, slots=True)
class UncertaintyRecord:
    target: str
    method: str
    estimate: float
    lower: float
    upper: float
    resampling_unit: str

    def __post_init__(self) -> None:
        if not all(item.strip() for item in (self.target, self.method, self.resampling_unit)):
            raise ValueError("uncertainty records need target, method, and resampling unit")
        if self.lower > self.upper:
            raise ValueError("uncertainty lower bound cannot exceed the upper bound")


@dataclass(frozen=True, slots=True)
class PredictionArtifactReference:
    artifact_id: str
    benchmark_id: str
    benchmark_spec_digest: str
    dataset_realization_id: str
    dataset_realization_digest: str
    model_id: str
    output_schema_identity: str
    row_count: int
    content_sha256: str
    rights: RightsMetadata

    def __post_init__(self) -> None:
        if any(
            not item.strip()
            for item in (
                self.artifact_id,
                self.benchmark_id,
                self.dataset_realization_id,
                self.model_id,
                self.output_schema_identity,
            )
        ):
            raise ValueError(
                "prediction artifact references must identify their content and context"
            )
        if not re.fullmatch(
            r"psr:benchmark-spec:[a-z0-9][a-z0-9-]*@[0-9]+\.[0-9]+\.[0-9]+~[a-f0-9]{12}",
            self.benchmark_id,
        ):
            raise ValueError("prediction artifact must reference a minted benchmark ID")
        if not re.fullmatch(
            r"psr:dataset-realization:[a-z0-9][a-z0-9-]*@sha256:[a-f0-9]{64}",
            self.dataset_realization_id,
        ):
            raise ValueError("prediction artifact must reference a dataset realization ID")
        require_scientific_id(self.model_id, "model ID")
        if self.row_count < 0:
            raise ValueError("prediction artifact row count cannot be negative")
        for value in (
            self.benchmark_spec_digest,
            self.dataset_realization_digest,
            self.content_sha256,
        ):
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
                raise ValueError("prediction artifact hashes must be full prefixed SHA-256 digests")

    def identity_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "benchmark_id": self.benchmark_id,
            "benchmark_spec_digest": self.benchmark_spec_digest,
            "dataset_realization_id": self.dataset_realization_id,
            "dataset_realization_digest": self.dataset_realization_digest,
            "model_id": self.model_id,
            "output_schema_identity": self.output_schema_identity,
            "row_count": self.row_count,
            "content_sha256": self.content_sha256,
            "rights": self.rights,
        }

    @property
    def digest(self) -> str:
        return sha256_record(self.identity_payload())

    @property
    def identity_id(self) -> str:
        return f"psr:prediction-artifact:{self.artifact_id}@{self.digest}"


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    benchmark_id: str
    benchmark_spec_digest: str
    dataset_realization_id: str
    dataset_realization_digest: str
    model: ModelReference
    training_protocol: TrainingProtocolReference
    fitted_instance: FittedInstanceReference | None
    checkpoint: CheckpointReference | None
    environment: EnvironmentProvenance
    rng: RNGProvenance
    prediction_artifact: PredictionArtifactReference
    evaluation_id: str
    metric_identities: tuple[MetricIdentity, ...]
    targets: tuple[TargetMetrics, ...]
    aggregations: tuple[AggregationRecord, ...]
    stratifications: tuple[StratificationRecord, ...]
    exclusions: tuple[ExclusionRecord, ...]
    uncertainty: tuple[UncertaintyRecord, ...]
    status: ResultStatus
    rights: RightsMetadata

    def __post_init__(self) -> None:
        ids = (
            self.benchmark_id,
            self.dataset_realization_id,
            self.evaluation_id,
        )
        if any(not item.strip() for item in ids):
            raise ValueError("result must bind benchmark, data realization, and evaluation IDs")
        if not re.fullmatch(
            r"psr:benchmark-spec:[a-z0-9][a-z0-9-]*@[0-9]+\.[0-9]+\.[0-9]+~[a-f0-9]{12}",
            self.benchmark_id,
        ):
            raise ValueError("evaluation result must reference a minted benchmark ID")
        if not re.fullmatch(
            r"psr:dataset-realization:[a-z0-9][a-z0-9-]*@sha256:[a-f0-9]{64}",
            self.dataset_realization_id,
        ):
            raise ValueError("evaluation result must reference a dataset realization ID")
        require_scientific_id(self.evaluation_id, "evaluation ID")
        for value, label in (
            (self.benchmark_spec_digest, "benchmark_spec_digest"),
            (self.dataset_realization_digest, "dataset_realization_digest"),
        ):
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
                raise ValueError(f"{label} must be a full prefixed SHA-256 digest")
        if (
            self.prediction_artifact.benchmark_id != self.benchmark_id
            or self.prediction_artifact.benchmark_spec_digest != self.benchmark_spec_digest
            or self.prediction_artifact.dataset_realization_id != self.dataset_realization_id
            or self.prediction_artifact.dataset_realization_digest
            != self.dataset_realization_digest
            or self.prediction_artifact.model_id != self.model.model_id
        ):
            raise ValueError("prediction artifact must bind the same benchmark, data, and model")
        expected = {item.metric for item in self.metric_identities}
        if any({metric.metric for metric in target.metrics} != expected for target in self.targets):
            raise ValueError("every target must report the declared metric identities")

    def identity_payload(self) -> dict[str, object]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_spec_digest": self.benchmark_spec_digest,
            "dataset_realization_id": self.dataset_realization_id,
            "dataset_realization_digest": self.dataset_realization_digest,
            "model": self.model,
            "training_protocol": self.training_protocol,
            "fitted_instance": self.fitted_instance,
            "checkpoint": self.checkpoint,
            "environment": self.environment,
            "rng": self.rng,
            "prediction_artifact": self.prediction_artifact,
            "evaluation_id": self.evaluation_id,
            "metric_identities": self.metric_identities,
            "targets": self.targets,
            "aggregations": self.aggregations,
            "stratifications": self.stratifications,
            "exclusions": self.exclusions,
            "uncertainty": self.uncertainty,
            "status": self.status.value,
            "rights": self.rights,
        }

    @property
    def digest(self) -> str:
        return sha256_record(self.identity_payload())

    @property
    def result_id(self) -> str:
        return f"psr:evaluation-result@{self.digest}"
