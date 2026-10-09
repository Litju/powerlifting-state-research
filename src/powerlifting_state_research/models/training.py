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
from ..evaluation.identity import EVALUATION_ID, METRIC_IDENTITIES
from ..evaluation.prediction import PREDICTION_SCHEMA_ID
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


@dataclass(frozen=True, slots=True)
class StandardizedComparatorProtocol:
    format: str
    benchmark_id: str
    benchmark_digest: str
    dataset_spec_id: str
    dataset_realization_id: str
    dataset_realization_digest: str
    train_sha256: str
    validation_sha256: str
    train_row_count: int
    validation_row_count: int
    evaluation_id: str
    metric_ids: tuple[str, ...]
    prediction_schema_id: str
    participant_visible_input: tuple[str, ...]
    feature_representation: tuple[tuple[str, object], ...]
    training_partition: tuple[tuple[str, object], ...]
    selection_rule: tuple[tuple[str, object], ...]
    tuning_budget: tuple[tuple[str, object], ...]
    seeds: tuple[int, int, int]
    determinism: tuple[tuple[str, object], ...]
    model_selection: tuple[tuple[str, object], ...]
    comparator_methods: tuple[tuple[str, tuple[tuple[str, object], ...]], ...]
    parameter_and_compute_reporting: tuple[tuple[str, object], ...]
    identity_rules: tuple[tuple[str, object], ...]
    validation_isolation: tuple[tuple[str, object], ...]
    reused_immutable_result: tuple[tuple[str, object], ...]
    rights: tuple[tuple[str, object], ...]

    def identity_payload(self) -> dict[str, object]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_record(self.identity_payload())

    @property
    def training_protocol_id(self) -> str:
        return f"psr:training-protocol:public-native-comparator-suite@1.0.0~{self.digest[7:19]}"


PUBLIC_NATIVE_COMPARATOR_PROTOCOL = StandardizedComparatorProtocol(
    format="PSR_STANDARDIZED_COMPARATOR_PROTOCOL_V1",
    benchmark_id=evaluate.CANONICAL_BENCHMARK_ID,
    benchmark_digest=evaluate.CANONICAL_BENCHMARK_DIGEST,
    dataset_spec_id=spec.PUBLIC_NATIVE_DATASET_SPEC_ID,
    dataset_realization_id=evaluate.CANONICAL_VALIDATION.realization_id,
    dataset_realization_digest=evaluate.CANONICAL_VALIDATION.realization_digest,
    train_sha256="914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550",
    validation_sha256=evaluate.CANONICAL_VALIDATION.validation_sha256,
    train_row_count=12_288,
    validation_row_count=evaluate.CANONICAL_VALIDATION.validation_rows,
    evaluation_id=EVALUATION_ID,
    metric_ids=tuple(item.metric_id for item in METRIC_IDENTITIES),
    prediction_schema_id=PREDICTION_SCHEMA_ID,
    participant_visible_input=(
        "origin_day",
        "horizon_days",
        "declared_future_plan",
        "three ordered lift histories through day 223",
        "history schedule through day 223",
    ),
    feature_representation=(
        ("source", "M3 TemporalModelInput; only participant-visible fields"),
        ("lift_order", ("squat", "bench_press", "deadlift")),
        (
            "observation_channels",
            (
                "assessment_kg",
                "prescribed_load_kg",
                "velocity_mps",
                "relative_prescribed_load",
                "assessment_delta_kg",
                "velocity_delta_mps",
            ),
        ),
        (
            "channel_normalization",
            "per lift/channel; fitting rows only; population ddof=0; floor 1e-6",
        ),
        (
            "history_summaries_per_channel",
            ("first", "last", "mean", "population_sd", "linear_slope"),
        ),
        ("slope_coordinate", "ordinary least-squares slope per seven-day observation step"),
        ("schedule_channels", ("dose/1.2", "intensity", "dose*intensity/1.2")),
        ("schedule_summaries_per_channel", ("mean", "mean_last_four", "last")),
        ("plan_features", "M3 six numeric plan/timing fields plus four-category one-hot"),
        ("plan_category_order", ("cessation", "continue", "step_down", "step_up")),
        ("feature_count", 127),
        ("forbidden", ("IDs", "targets", "latent coordinates", "future realized information")),
    ),
    training_partition=(
        ("training_source", "canonical train split only"),
        ("fit_row_count", 9_984),
        ("selection_row_count", 2_304),
        (
            "split_id",
            "psr:internal-selection-split:public-native-temporal-expert@sha256:9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25",
        ),
        ("split_digest", "sha256:9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"),
        (
            "split_rule",
            "RES-274 plan × horizon × three-lift schedule-template hash-ranked 80/20 split",
        ),
        ("entity_disjoint", True),
        ("support_preserved", True),
        ("normalization", "fitting rows only; selection rows excluded"),
    ),
    selection_rule=(
        ("metric", "equal-target mean squared error in fit-standardized target space"),
        (
            "selection_rows_use",
            "only declared stopping/model-selection rules; never gradient fitting or normalization",
        ),
        (
            "tree_stopping",
            "best selection loss; earliest tie; 8-round patience; min improvement 1e-4; "
            "max 40 rounds",
        ),
        (
            "neural_stopping",
            "best selection loss; earliest tie; 10-epoch patience; min improvement 1e-4; "
            "max 60 epochs",
        ),
        ("fixed_methods", "no selection-based fitting or hyperparameter choice"),
    ),
    tuning_budget=(
        ("configurations_per_method", 1),
        ("hyperparameter_tournament", False),
        ("canonical_validation_tuning", False),
        ("validation_feature_engineering", False),
        ("validation_protocol_revision", False),
    ),
    seeds=(383_001, 383_002, 383_003),
    determinism=(
        ("python_numpy_torch_seeds", "the per-fit declared seed"),
        ("torch_deterministic_algorithms", True),
        ("dataloader_workers", 0),
        ("feature_order_and_ties", "declared order; earliest feature/threshold on exact ties"),
        (
            "deterministic_methods",
            "same fitted-state bytes across run seeds are expected and reported",
        ),
        ("cross_hardware_bitwise_guarantee", False),
    ),
    model_selection=(
        ("training_loss", "equal-target MSE in fitting-row standardized target space"),
        ("output", "three latent capacity changes in kg; squat, bench press, deadlift order"),
        (
            "validation",
            "RES-271 complete 3,072-row canonical validation; report all four target-wise metrics",
        ),
        ("universal_scalar", False),
    ),
    comparator_methods=(
        (
            "context_mean",
            (("groups", "declared plan × horizon"), ("fit_rule", "fit-row target mean")),
        ),
        ("ridge", (("alpha", 1.0), ("solver", "closed-form multi-output ridge with intercept"))),
        (
            "histogram_boosted_stumps",
            (
                ("algorithm", "squared-error gradient boosting of depth-one regression trees"),
                (
                    "thresholds",
                    "15 empirical fitting-row quantiles at k/16; duplicate thresholds removed",
                ),
                ("learning_rate", 0.05),
                ("maximum_rounds", 40),
            ),
        ),
        (
            "mechanistic_midpoint",
            (
                ("reference_stimulus", 0.485),
                ("reference_dose_product", 0.6),
                ("adaptation_utilization", 0.11),
                ("adaptation_retention_28d", 0.525),
                ("suppression_utilization", 0.04),
                ("suppression_retention", 0.625),
                (
                    "baseline_estimator",
                    "last assessment divided by midpoint model expression fraction at day 223",
                ),
                (
                    "target",
                    "baseline × adaptation_gain × (adaptation_end − adaptation_day_223)",
                ),
                ("fit_parameters", False),
            ),
        ),
        (
            "compact_neural",
            (
                ("architecture", "127 → 32 ReLU → 3"),
                ("optimizer", "AdamW"),
                ("learning_rate", 0.003),
                ("weight_decay", 0.0001),
                ("batch_size", 256),
                ("maximum_epochs", 60),
            ),
        ),
        (
            "mechanistic_ridge_residual",
            (("base", "mechanistic_midpoint"), ("residual_model", "ridge"), ("alpha", 1.0)),
        ),
    ),
    parameter_and_compute_reporting=(
        (
            "parameter_count",
            "count fitted scalar parameters; separately list fixed mechanistic constants",
        ),
        ("compute", "measured fit and prediction wall seconds per seed"),
        ("hardware", "CPU model when available; platform and Python/NumPy/PyTorch versions"),
        ("validation_compute", "measured separately from fitting"),
    ),
    identity_rules=(
        ("new_model_classification", "NEW_STANDARDIZED_COMPARATOR"),
        ("model_id", "hash model semantics and fixed comparator configuration"),
        (
            "fitted_instance_id",
            "hash canonical fitted-state artifact, fit/selection split, seed, and training "
            "protocol",
        ),
        ("prediction_artifact", "RES-271 canonical JSONL schema and byte SHA-256"),
        (
            "evaluation_result",
            "RES-271 deterministic EvaluationResult digest with model, fitted instance, "
            "protocol, environment, RNG, and rights",
        ),
        ("checkpoint", "none; final selected fitted state is stored as a fitted-instance artifact"),
    ),
    validation_isolation=(
        ("training_loader", "opens and validates canonical train.jsonl only"),
        ("validation_access", "after all fit state and training receipts are sealed"),
        ("validation_purpose", "one canonical RES-271 evaluation; no tuning or revisions"),
    ),
    reused_immutable_result=(
        (
            "model_id",
            "psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f",
        ),
        (
            "training_protocol_id",
            "psr:training-protocol:public-native-temporal-expert@1.0.0~dc47230f3465",
        ),
        (
            "policy",
            "reuse sealed RES-274 seed predictions/results; do not retrain, regenerate, "
            "rescore, or relabel",
        ),
    ),
    rights=(
        ("new_model_artifacts", "repository-generated JSON; project-authored MIT"),
        ("new_predictions_and_results", "repository-generated; project-authored MIT"),
        ("RES-274 expert predictions", "retain original rights and immutable bytes"),
        (
            "historical_private_evidence",
            "metadata summaries only; no private source, data, or weights copied",
        ),
    ),
)

COMPARATOR_TRAINING_PROTOCOL_DIGEST = PUBLIC_NATIVE_COMPARATOR_PROTOCOL.digest
COMPARATOR_TRAINING_PROTOCOL_ID = PUBLIC_NATIVE_COMPARATOR_PROTOCOL.training_protocol_id


def comparator_training_protocol_manifest() -> dict[str, object]:
    return {
        "format": PUBLIC_NATIVE_COMPARATOR_PROTOCOL.format,
        "training_protocol_id": COMPARATOR_TRAINING_PROTOCOL_ID,
        "protocol_digest": COMPARATOR_TRAINING_PROTOCOL_DIGEST,
        "protocol": PUBLIC_NATIVE_COMPARATOR_PROTOCOL.identity_payload(),
    }


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
