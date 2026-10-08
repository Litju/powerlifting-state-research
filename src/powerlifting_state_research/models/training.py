"""Typed, frozen authority for PUBLIC_NATIVE temporal-expert training."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TypeAlias

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    evaluate,
    prediction,
    spec,
)
from ..contracts.serialization import sha256_record
from ..evaluation.identity import EVALUATION_ID
from .references import TrainingProtocolReference
from .temporal_expert import MODEL_SPEC_ID


@dataclass(frozen=True, slots=True)
class TemporalExpertTrainingProtocol:
    model_id: str
    benchmark_id: str
    benchmark_digest: str
    dataset_spec_id: str
    dataset_realization_id: str
    dataset_realization_digest: str
    dataset_train_sha256: str
    dataset_validation_sha256: str
    train_row_count: int
    validation_row_count: int
    evaluation_id: str
    prediction_contract_digest: str
    loss: str
    optimizer: str
    learning_rate: float
    weight_decay: float
    betas: tuple[float, float]
    epsilon: float
    batch_size: int
    warmup_epochs: int
    scheduler: str
    minimum_learning_rate: float
    maximum_epochs: int
    gradient_clip_norm: float
    normalization: tuple[tuple[str, object], ...]
    internal_split: tuple[tuple[str, object], ...]
    internal_selection_split_id: str
    internal_selection_split_digest: str
    internal_fit_row_count: int
    internal_selection_row_count: int
    seeds: tuple[int, int, int]
    checkpoint_selection: tuple[tuple[str, object], ...]
    determinism: tuple[tuple[str, object], ...]
    ensemble: tuple[tuple[str, object], ...]
    artifact_schemas: tuple[tuple[str, str], ...]
    runtime_receipt_fields: tuple[str, ...]

    def identity_payload(self) -> dict[str, object]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_record(self.identity_payload())

    @property
    def training_protocol_id(self) -> str:
        return f"psr:training-protocol:public-native-temporal-expert@1.0.0~{self.digest[7:19]}"


PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL = TemporalExpertTrainingProtocol(
    model_id=MODEL_SPEC_ID,
    benchmark_id=evaluate.CANONICAL_BENCHMARK_ID,
    benchmark_digest=evaluate.CANONICAL_BENCHMARK_DIGEST,
    dataset_spec_id=spec.PUBLIC_NATIVE_DATASET_SPEC_ID,
    dataset_realization_id=evaluate.CANONICAL_VALIDATION.realization_id,
    dataset_realization_digest=evaluate.CANONICAL_VALIDATION.realization_digest,
    dataset_train_sha256="914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550",
    dataset_validation_sha256=evaluate.CANONICAL_VALIDATION.validation_sha256,
    train_row_count=12_288,
    validation_row_count=evaluate.CANONICAL_VALIDATION.validation_rows,
    evaluation_id=EVALUATION_ID,
    prediction_contract_digest=sha256_record(prediction.PREDICTION_CONTRACT),
    loss="equal-target mean squared error in fit-standardized target space",
    optimizer="AdamW",
    learning_rate=3e-4,
    weight_decay=1e-4,
    betas=(0.9, 0.999),
    epsilon=1e-8,
    batch_size=256,
    warmup_epochs=5,
    scheduler="linear warmup by optimizer step, then cosine to minimum_learning_rate",
    minimum_learning_rate=1e-5,
    maximum_epochs=120,
    gradient_clip_norm=1.0,
    normalization=(
        ("fitting_rows_only", True),
        (
            "input_channels",
            (
                "assessment_kg",
                "prescribed_load_kg",
                "velocity_mps",
                "relative_prescribed_load",
                "assessment_delta_kg",
                "velocity_delta_mps",
            ),
        ),
        ("input_axes", "all fit rows and 32 observations; separate statistic per lift/channel"),
        ("target_axes", "fit rows; separate statistic per target"),
        ("standard_deviation", "population ddof=0"),
        ("minimum_scale", 1e-6),
        ("shared_across_seeds", True),
    ),
    internal_split=(
        ("source_split", "canonical TRAIN only"),
        (
            "strata",
            (
                "future plan",
                "horizon",
                "squat history schedule template",
                "bench history schedule template",
                "deadlift history schedule template",
            ),
        ),
        ("selection_rows_per_stratum", "max(1, min(n - 1, floor(n / 5)))"),
        (
            "selection_order",
            "ascending SHA-256 of UTF-8 row_id, then row_id; no RNG",
        ),
        ("entity_disjoint", True),
        ("support_requirement", "each stratum must contain at least two rows"),
        ("identity", "hash sorted fit and selection row IDs plus DatasetRealization"),
    ),
    internal_selection_split_id=(
        "psr:internal-selection-split:public-native-temporal-expert@sha256:"
        "9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"
    ),
    internal_selection_split_digest=(
        "sha256:9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"
    ),
    internal_fit_row_count=9_984,
    internal_selection_row_count=2_304,
    seeds=(383001, 383002, 383003),
    checkpoint_selection=(
        ("metric", "equal-target standardized MSE"),
        ("minimum_epochs", 20),
        ("patience", 20),
        ("minimum_improvement", 1e-4),
        ("maximum_epochs", 120),
        (
            "tie_break",
            "earliest epoch; require improvement strictly greater than minimum_improvement",
        ),
        ("validation_use", "internal selection rows only"),
    ),
    determinism=(
        ("python_seed", "training seed"),
        ("numpy_seed", "training seed"),
        ("torch_cpu_seed", "training seed"),
        ("torch_cuda_seeds", "training seed on every visible device"),
        ("torch_deterministic_algorithms", True),
        ("cudnn_deterministic", True),
        ("cudnn_benchmark", False),
        ("float32_matmul_precision", "highest"),
        ("cuda_matmul_allow_tf32", False),
        ("cublas_workspace_config", ":4096:8"),
        (
            "dataloader_order",
            "torch.randperm each epoch using a CPU generator seeded with the training seed",
        ),
        ("dataloader_workers", 0),
        ("cross_gpu_bitwise_guarantee", False),
    ),
    ensemble=(
        ("seed_count", 3),
        ("rule", "equal arithmetic mean of standardized outputs"),
        ("inverse_transform_count", 1),
        ("seed_dropping_or_reweighting", False),
    ),
    artifact_schemas=(
        ("TRAINING_PROTOCOL", "PSR_TRAINING_PROTOCOL_V1"),
        ("INTERNAL_SELECTION_SPLIT", "PSR_INTERNAL_SELECTION_SPLIT_V1"),
        ("NORMALIZATION_STATS", "PSR_NORMALIZATION_STATS_V1"),
        ("FITTED_INSTANCE", "PSR_FITTED_INSTANCE_V1"),
        ("CHECKPOINT", "PSR_CHECKPOINT_MANIFEST_V1"),
        ("TRAINING_HISTORY", "PSR_TRAINING_HISTORY_V1"),
        ("TRAINING_RUN", "PSR_TRAINING_RUN_V1"),
        ("RUN_RECEIPT", "PSR_RUN_RECEIPT_V1"),
        ("PREDICTION", "PSR_IID_CAPACITY_CHANGE_PREDICTION_JSONL_V1"),
        ("EVALUATION_RESULT", "PSR_EVALUATION_RESULT_V1"),
    ),
    runtime_receipt_fields=(
        "code_sha",
        "git_tree_status",
        "python",
        "package_version",
        "torch_version",
        "torch_build",
        "torch_cuda_version",
        "cudnn_version",
        "nvidia_driver",
        "gpu_name",
        "gpu_memory_bytes",
        "platform",
        "dependency_fingerprint",
        "determinism_controls",
    ),
)

TRAINING_PROTOCOL_ID = PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.training_protocol_id
TRAINING_PROTOCOL_DIGEST = PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.digest
TRAINING_PROTOCOLS: TypeAlias = tuple[TrainingProtocolReference, ...]
TRAINING_PROTOCOL_REFERENCES: TRAINING_PROTOCOLS = (
    TrainingProtocolReference(TRAINING_PROTOCOL_ID),
)


def training_protocol_manifest() -> dict[str, object]:
    return {
        "format": "PSR_TRAINING_PROTOCOL_V1",
        "training_protocol_id": TRAINING_PROTOCOL_ID,
        "protocol_digest": TRAINING_PROTOCOL_DIGEST,
        "protocol": PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL.identity_payload(),
    }
