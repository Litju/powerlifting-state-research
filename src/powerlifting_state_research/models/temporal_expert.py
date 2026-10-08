"""Clean-room PUBLIC_NATIVE temporal capacity-change model."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import torch
from torch import Tensor, nn

from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset,
    interventions,
    observations,
    prediction,
    spec,
)
from ..contracts.serialization import sha256_record
from ..evaluation.identity import TARGETS
from ..evaluation.prediction import PredictionRow

DOSE_INTENSITY_PAIRS = interventions.DOSE_INTENSITY_PAIRS
HISTORY_OBSERVATION_DAYS = observations.HISTORY_OBSERVATION_DAYS
ORIGIN_DAY = interventions.ORIGIN_DAY
PLAN_END_DAY = interventions.PLAN_END_DAY
PLAN_IDS = interventions.PLAN_IDS
PLAN_START_DAY = interventions.PLAN_START_DAY
PREDICTION_CONTRACT = prediction.PREDICTION_CONTRACT
PUBLIC_NATIVE_SPEC = spec.PUBLIC_NATIVE_SPEC

LIFT_KEYS = ("squat", "bench_press", "deadlift")
HISTORY_STEPS = len(HISTORY_OBSERVATION_DAYS)
OBSERVATION_CHANNELS = (
    "assessment_kg",
    "prescribed_load_kg",
    "velocity_mps",
    "relative_prescribed_load",
    "assessment_delta_kg",
    "velocity_delta_mps",
)
HISTORY_CHANNELS = (
    *OBSERVATION_CHANNELS,
    "schedule_dose_div_1.2",
    "schedule_intensity_div_1.0",
    "schedule_dose_x_intensity_div_1.2",
    "observation_age_fraction",
)
PLAN_ORDER = ("cessation", "continue", "step_down", "step_up")
NORMALIZATION_SCHEMA_ID = "public-native-temporal-expert-normalization-v1"
NORMALIZATION_EPSILON = 1e-6
DROPOUT = 0.10
FILM_SCALE = 0.25

MODEL_SPEC_SEMANTICS: dict[str, object] = {
    "architecture_family": "shared_lift_temporal_gru_plan_conditioned_cross_lift_fusion",
    "architecture_version": "1.0.0",
    "benchmark_spec_id": PUBLIC_NATIVE_SPEC.benchmark_id,
    "input_representation": {
        "participant_components": (
            "history observations through day 223",
            "per-lift history schedule through day 223",
            "declared future plan",
            "origin day",
            "horizon days",
        ),
        "lift_order": LIFT_KEYS,
        "observation_days": HISTORY_OBSERVATION_DAYS,
        "sequence_order": "oldest_to_newest",
        "history_shape": ("N", 3, 32, 10),
        "history_channels": HISTORY_CHANNELS,
        "history_mask_shape": ("N", 3, 32),
        "history_mask": "all ones; 32 complete public observations; no padding",
        "plan_numeric_shape": ("N", 6),
        "plan_numeric_order": (
            "origin_day_div_224",
            "horizon_days_div_56",
            "future_dose_div_1.2",
            "future_intensity_div_1.0",
            "future_dose_x_intensity_div_1.2",
            "future_plan_duration_days_div_56",
        ),
        "plan_category_order": PLAN_ORDER,
        "plan_index_dtype": "int64",
        "numeric_dtype": "float32",
    },
    "temporal_architecture": {
        "history_projection": (10, 64),
        "lift_code_projection": (3, 8),
        "temporal_input_normalization": "LayerNorm(72)",
        "temporal_encoder": "GRU(input=72, hidden=64, layers=2, batch_first=true)",
        "recurrent_dropout": "0",
        "shared_across_lifts": True,
    },
    "context_architecture": {
        "structural_summary_order": (
            "recent_mean_first_6_channels_last_4",
            "early_mean_first_6_channels_first_4",
            "endpoint_delta_first_6_channels",
            "recent_mean_schedule_channels_last_4",
            "all_history_mean_schedule_channels",
        ),
        "structural_summary_shape": ("N", 3, 24),
        "structural_encoder": (24, 32, "GELU", "LayerNorm", "Dropout(0.10)"),
        "plan_embedding": (4, 16),
        "plan_encoder": (22, 32, "GELU", "LayerNorm"),
        "plan_film": "Linear(32,128); gamma,beta; bounded scale=0.25",
        "cross_lift_gate": "Linear(160,64); sigmoid; other_lift_mean",
        "cross_lift_fusion": (192, 64, "GELU", "LayerNorm", "Dropout(0.10)"),
    },
    "output_head": (224, 128, 64, 3),
    "output_activations": ("GELU", "GELU", "identity"),
    "output_order": TARGETS,
    "output_semantics": "latent capacity change in kg; one joint three-output head",
    "network_output_space": "standardized_train_targets_z",
    "preprocessing": {
        "input_standardization": (
            "first six history channels; per lift; train split only; population "
            "standard deviation; scale floor 1e-6"
        ),
        "fixed_history_scales": ("dose/1.2", "intensity/1.0", "dose_x_intensity/1.2"),
        "history_age": "(224-observation_day)/224",
        "plan_scales": (
            "origin/224",
            "horizon/56",
            "dose/1.2",
            "intensity/1.0",
            "dose_x_intensity/1.2",
            "duration_days/56",
        ),
        "target_standardization": (
            "per target; train split only; population standard deviation; scale floor 1e-6"
        ),
        "inverse_transform": "standardized output * target scale + target mean, once",
        "statistics_are_model_weights": False,
    },
    "dropout_probability": "0.10",
    "prediction_contract_outputs": PREDICTION_CONTRACT.outputs,
}
_MODEL_DIGEST = sha256_record(
    {
        "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
        "component_class": "model",
        "slug": "public-native-lift-shared-temporal-gru-capacity-change",
        "version": "1.0.0",
        "semantics": MODEL_SPEC_SEMANTICS,
    },
    reject_floats=True,
)
MODEL_SPEC_ID = (
    f"psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~{_MODEL_DIGEST[7:19]}"
)


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


@dataclass(frozen=True, slots=True)
class TemporalModelInput:
    """Prediction-time fields only; row ID is alignment metadata, never a feature."""

    row_id: str
    origin_day: int
    horizon_days: int
    declared_future_plan: interventions.DeclaredFuturePlan
    squat: dataset.LiftInputs
    bench_press: dataset.LiftInputs
    deadlift: dataset.LiftInputs

    def __post_init__(self) -> None:
        if not isinstance(self.row_id, str) or not self.row_id.strip():
            raise ValueError("row_id must be non-empty")
        if type(self.origin_day) is not int or self.origin_day != ORIGIN_DAY:
            raise ValueError("origin_day must be the frozen public origin day")
        if type(self.horizon_days) is not int or self.horizon_days not in (14, 28, 56):
            raise ValueError("horizon_days is outside public support")
        plan = self.declared_future_plan
        if (
            plan.plan_id not in PLAN_IDS
            or (plan.start_day, plan.end_day) != (PLAN_START_DAY, PLAN_END_DAY)
            or (plan.dose, plan.intensity) != DOSE_INTENSITY_PAIRS[plan.plan_id]
        ):
            raise ValueError("declared future plan is outside public support")
        for lift_name, lift in zip(LIFT_KEYS, self.lifts, strict=True):
            if (
                any(type(item.day) is not int for item in lift.history)
                or tuple(item.day for item in lift.history) != HISTORY_OBSERVATION_DAYS
            ):
                raise ValueError(f"{lift_name} history must contain all 32 ordered observations")
            previous_day = -1
            for segment in lift.history_schedule:
                if (
                    type(segment.start_day) is not int
                    or type(segment.end_day) is not int
                    or segment.start_day != previous_day + 1
                    or segment.end_day < segment.start_day
                    or segment.end_day > ORIGIN_DAY - 1
                ):
                    raise ValueError(f"{lift_name} schedule has a gap, overlap, or invalid day")
                pair = (
                    _finite(segment.dose, "schedule dose"),
                    _finite(segment.intensity, "schedule intensity"),
                )
                if pair not in DOSE_INTENSITY_PAIRS.values():
                    raise ValueError(f"{lift_name} schedule is outside public support")
                previous_day = segment.end_day
            if previous_day != ORIGIN_DAY - 1:
                raise ValueError(f"{lift_name} schedule must end on day 223")
            for observation in lift.history:
                assessment = _finite(observation.assessment_kg, "assessment_kg")
                prescribed = _finite(observation.prescribed_load_kg, "prescribed_load_kg")
                _finite(observation.velocity_mps, "velocity_mps")
                if assessment <= 0.0 or prescribed < 0.0 or prescribed > assessment:
                    raise ValueError(f"{lift_name} observation is outside public support")

    @property
    def lifts(self) -> tuple[dataset.LiftInputs, dataset.LiftInputs, dataset.LiftInputs]:
        return (self.squat, self.bench_press, self.deadlift)

    @classmethod
    def from_forecast_inputs(
        cls, row_id: str, inputs: dataset.ForecastInputs
    ) -> TemporalModelInput:
        return cls(
            row_id,
            inputs.origin_day,
            inputs.horizon_days,
            inputs.declared_future_plan,
            inputs.lifts["squat"],
            inputs.lifts["bench_press"],
            inputs.lifts["deadlift"],
        )


def _raw_history(row: TemporalModelInput) -> Tensor:
    lifts: list[list[list[float]]] = []
    for lift in row.lifts:
        channels: list[list[float]] = []
        previous: observations.PerformanceObservation | None = None
        segment_index = 0
        for observation in lift.history:
            while lift.history_schedule[segment_index].end_day < observation.day:
                segment_index += 1
            segment: interventions.HistorySegment = lift.history_schedule[segment_index]
            assessment = float(observation.assessment_kg)
            prescribed = float(observation.prescribed_load_kg)
            velocity = float(observation.velocity_mps)
            channels.append(
                [
                    assessment,
                    prescribed,
                    velocity,
                    prescribed / assessment,
                    0.0 if previous is None else assessment - previous.assessment_kg,
                    0.0 if previous is None else velocity - previous.velocity_mps,
                    float(segment.dose),
                    float(segment.intensity),
                    float(segment.dose * segment.intensity),
                    (row.origin_day - observation.day) / ORIGIN_DAY,
                ]
            )
            previous = observation
        lifts.append(channels)
    return torch.tensor(lifts, dtype=torch.float64)


def _plan_numeric(row: TemporalModelInput) -> tuple[float, ...]:
    plan = row.declared_future_plan
    return (
        row.origin_day / ORIGIN_DAY,
        row.horizon_days / 56.0,
        plan.dose / 1.2,
        plan.intensity,
        (plan.dose * plan.intensity) / 1.2,
        (plan.end_day - plan.start_day + 1) / 56.0,
    )


def _matrix_tuple(values: Tensor) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(item) for item in row) for row in values.tolist())


@dataclass(frozen=True, slots=True)
class NormalizationStats:
    """Train-fitted input and target statistics, stored outside model weights."""

    input_mean: tuple[tuple[float, ...], ...]
    input_scale: tuple[tuple[float, ...], ...]
    target_mean: tuple[float, float, float]
    target_scale: tuple[float, float, float]

    def __post_init__(self) -> None:
        if len(self.input_mean) != 3 or len(self.input_scale) != 3:
            raise ValueError("input statistics must be [3,6]")
        for mean, scale in zip(self.input_mean, self.input_scale, strict=True):
            if len(mean) != 6 or len(scale) != 6:
                raise ValueError("input statistics must be [3,6]")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in mean
            ):
                raise ValueError("input means must be finite")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < NORMALIZATION_EPSILON
                for value in scale
            ):
                raise ValueError("input scales must be finite and at least 1e-6")
        if len(self.target_mean) != 3 or len(self.target_scale) != 3:
            raise ValueError("target statistics must be [3]")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in self.target_mean
        ):
            raise ValueError("target means must be finite")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < NORMALIZATION_EPSILON
            for value in self.target_scale
        ):
            raise ValueError("target scales must be finite and at least 1e-6")

    @classmethod
    def fit_train(
        cls,
        train_inputs: Sequence[TemporalModelInput],
        train_targets: Sequence[tuple[float, float, float]],
    ) -> NormalizationStats:
        if not train_inputs or len(train_inputs) != len(train_targets):
            raise ValueError("train inputs and targets must be non-empty and row-aligned")
        history = torch.stack([_raw_history(item) for item in train_inputs])
        observed = history[:, :, :, : len(OBSERVATION_CHANNELS)]
        input_mean = observed.mean(dim=(0, 2))
        input_scale = observed.std(dim=(0, 2), unbiased=False).clamp_min(NORMALIZATION_EPSILON)
        target_values = torch.tensor(
            [[_finite(value, "training target") for value in row] for row in train_targets],
            dtype=torch.float64,
        )
        if target_values.shape != (len(train_inputs), 3):
            raise ValueError("training targets must be [N,3] in squat, bench, deadlift order")
        target_mean = target_values.mean(dim=0)
        target_scale = target_values.std(dim=0, unbiased=False).clamp_min(NORMALIZATION_EPSILON)
        return cls(
            _matrix_tuple(input_mean),
            _matrix_tuple(input_scale),
            tuple(float(item) for item in target_mean.tolist()),  # type: ignore[arg-type]
            tuple(float(item) for item in target_scale.tolist()),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": NORMALIZATION_SCHEMA_ID,
            "input_mean": self.input_mean,
            "input_scale": self.input_scale,
            "target_mean": self.target_mean,
            "target_scale": self.target_scale,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> NormalizationStats:
        required = {"schema_id", "input_mean", "input_scale", "target_mean", "target_scale"}
        if set(value) != required or value["schema_id"] != NORMALIZATION_SCHEMA_ID:
            raise ValueError("normalization schema mismatch")
        input_mean = cast(Sequence[Sequence[object]], value["input_mean"])
        input_scale = cast(Sequence[Sequence[object]], value["input_scale"])
        target_mean = cast(Sequence[object], value["target_mean"])
        target_scale = cast(Sequence[object], value["target_scale"])
        return cls(
            tuple(tuple(_finite(item, "input mean") for item in row) for row in input_mean),
            tuple(tuple(_finite(item, "input scale") for item in row) for row in input_scale),
            cast(
                tuple[float, float, float],
                tuple(_finite(item, "target mean") for item in target_mean),
            ),
            cast(
                tuple[float, float, float],
                tuple(_finite(item, "target scale") for item in target_scale),
            ),
        )


@dataclass(frozen=True, slots=True)
class TemporalModelBatch:
    """Only tensors consumed by the architecture; no IDs, labels, or latent state."""

    history: Tensor
    history_mask: Tensor
    plan_numeric: Tensor
    plan_index: Tensor

    def validate(self) -> None:
        batch = self.history.shape[0] if self.history.ndim == 4 else -1
        if batch < 1 or self.history.shape != (batch, 3, 32, 10):
            raise ValueError("history tensor must be [N,3,32,10]")
        if self.history_mask.shape != (batch, 3, 32):
            raise ValueError("history mask must be [N,3,32]")
        if self.plan_numeric.shape != (batch, 6) or self.plan_index.shape != (batch,):
            raise ValueError("plan tensors must be [N,6] and [N]")
        if self.history.dtype is not torch.float32 or self.history_mask.dtype is not torch.float32:
            raise ValueError("history tensors must be float32")
        if self.plan_numeric.dtype is not torch.float32 or self.plan_index.dtype is not torch.int64:
            raise ValueError("plan tensors must be float32 and int64")
        if not all(
            bool(torch.isfinite(value).all())
            for value in (self.history, self.history_mask, self.plan_numeric)
        ):
            raise ValueError("model input tensors must be finite")
        if not bool(torch.all(self.history_mask == 1.0)):
            raise ValueError("the public representation requires all 32 history points")
        if not bool(torch.all((self.plan_index >= 0) & (self.plan_index < len(PLAN_ORDER)))):
            raise ValueError("plan index is outside public support")

    def to(self, device: torch.device) -> TemporalModelBatch:
        return TemporalModelBatch(
            self.history.to(device),
            self.history_mask.to(device),
            self.plan_numeric.to(device),
            self.plan_index.to(device),
        )


@dataclass(frozen=True, slots=True)
class PreparedBatch:
    row_ids: tuple[str, ...]
    tensors: TemporalModelBatch


def prepare_batch(inputs: Sequence[TemporalModelInput], stats: NormalizationStats) -> PreparedBatch:
    if not inputs:
        raise ValueError("cannot prepare an empty model batch")
    row_ids = tuple(row.row_id for row in inputs)
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("model input row IDs must be unique")
    history = torch.stack([_raw_history(row) for row in inputs])
    mean = torch.tensor(stats.input_mean, dtype=torch.float64).view(1, 3, 1, 6)
    scale = torch.tensor(stats.input_scale, dtype=torch.float64).view(1, 3, 1, 6)
    history[:, :, :, :6] = (history[:, :, :, :6] - mean) / scale
    history[:, :, :, 6] /= 1.2
    history[:, :, :, 7] /= 1.0
    history[:, :, :, 8] /= 1.2
    plan_numeric = torch.tensor([_plan_numeric(row) for row in inputs], dtype=torch.float32)
    plan_index = torch.tensor(
        [PLAN_ORDER.index(row.declared_future_plan.plan_id) for row in inputs],
        dtype=torch.int64,
    )
    tensors = TemporalModelBatch(
        history.to(torch.float32),
        torch.ones((len(inputs), 3, 32), dtype=torch.float32),
        plan_numeric,
        plan_index,
    )
    tensors.validate()
    return PreparedBatch(row_ids, tensors)


def _masked_mean(values: Tensor, mask: Tensor, dim: int) -> Tensor:
    weights = mask.to(dtype=values.dtype)
    while weights.ndim < values.ndim:
        weights = weights.unsqueeze(-1)
    return (values * weights).sum(dim=dim) / weights.sum(dim=dim).clamp_min(1.0)


class LiftSharedTemporalExpert(nn.Module):
    """Two-layer shared GRU, plan FiLM, gated cross-lift fusion, joint head."""

    model_spec_id = MODEL_SPEC_ID

    def __init__(self) -> None:
        super().__init__()
        self.history_projection = nn.Linear(10, 64)
        self.lift_projection = nn.Linear(3, 8, bias=False)
        self.temporal_input_norm = nn.LayerNorm(72)
        self.temporal_encoder = nn.GRU(
            input_size=72, hidden_size=64, num_layers=2, batch_first=True, dropout=0.0
        )
        self.structural_encoder = nn.Sequential(
            nn.Linear(24, 32),
            nn.GELU(),
            nn.LayerNorm(32),
            nn.Dropout(DROPOUT),
        )
        self.plan_embedding = nn.Embedding(4, 16)
        self.plan_encoder = nn.Sequential(nn.Linear(22, 32), nn.GELU(), nn.LayerNorm(32))
        self.plan_film = nn.Linear(32, 128)
        nn.init.zeros_(self.plan_film.weight)
        nn.init.zeros_(self.plan_film.bias)
        self.cross_gate = nn.Linear(160, 64)
        self.fusion = nn.Sequential(
            nn.Linear(192, 64),
            nn.GELU(),
            nn.LayerNorm(64),
            nn.Dropout(DROPOUT),
        )
        self.output_head = nn.Sequential(
            nn.Linear(224, 128),
            nn.GELU(),
            nn.LayerNorm(128),
            nn.Dropout(DROPOUT),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Dropout(DROPOUT),
            nn.Linear(64, 3),
        )
        self.register_buffer("lift_one_hot", torch.eye(3, dtype=torch.float32))

    def _structural_summary(self, history: Tensor, mask: Tensor) -> Tensor:
        recent = _masked_mean(history[:, :, -4:, :6], mask[:, :, -4:], dim=2)
        early = _masked_mean(history[:, :, :4, :6], mask[:, :, :4], dim=2)
        endpoint_delta = history[:, :, -1, :6] - history[:, :, 0, :6]
        recent_schedule = _masked_mean(history[:, :, -4:, 6:9], mask[:, :, -4:], dim=2)
        mean_schedule = _masked_mean(history[:, :, :, 6:9], mask, dim=2)
        return torch.cat((recent, early, endpoint_delta, recent_schedule, mean_schedule), dim=-1)

    def forward(self, batch: TemporalModelBatch) -> Tensor:
        batch.validate()
        history, mask = batch.history, batch.history_mask
        count = history.shape[0]
        lift_codes = self.lift_projection(self.lift_one_hot.to(dtype=history.dtype))
        lift_codes = lift_codes[None, :, None, :].expand(count, -1, 32, -1)
        sequence = torch.cat((self.history_projection(history), lift_codes), dim=-1)
        sequence = self.temporal_input_norm(sequence) * mask.unsqueeze(-1)
        _, hidden = self.temporal_encoder(sequence.reshape(count * 3, 32, 72))
        state = hidden[-1].reshape(count, 3, 64)

        plan_embedding = self.plan_embedding(batch.plan_index)
        plan_context = self.plan_encoder(torch.cat((batch.plan_numeric, plan_embedding), dim=-1))
        gamma, beta = self.plan_film(plan_context).chunk(2, dim=-1)
        state = state * (1.0 + FILM_SCALE * torch.tanh(gamma).unsqueeze(1))
        state = state + FILM_SCALE * torch.tanh(beta).unsqueeze(1)

        structural = self.structural_encoder(self._structural_summary(history, mask))
        other_lifts = (state.sum(dim=1, keepdim=True) - state) / 2.0
        plan = plan_context.unsqueeze(1).expand(-1, 3, -1)
        gate = torch.sigmoid(self.cross_gate(torch.cat((state, other_lifts, plan), dim=-1)))
        fused = self.fusion(torch.cat((state, structural, gate * other_lifts, plan), dim=-1))
        return cast(
            Tensor,
            self.output_head(torch.cat((fused.reshape(count, 192), plan_context), dim=-1)),
        )


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def _target_tensors(stats: NormalizationStats, device: torch.device) -> tuple[Tensor, Tensor]:
    return (
        torch.tensor(stats.target_mean, dtype=torch.float32, device=device),
        torch.tensor(stats.target_scale, dtype=torch.float32, device=device),
    )


def _rows_from_standardized(
    row_ids: tuple[str, ...], standardized: Tensor, stats: NormalizationStats
) -> tuple[PredictionRow, ...]:
    mean, scale = _target_tensors(stats, standardized.device)
    values = standardized * scale + mean
    if not bool(torch.isfinite(values).all()):
        raise ValueError("model output is non-finite")
    return tuple(
        PredictionRow(row_id, *(float(value) for value in row))
        for row_id, row in zip(row_ids, values.detach().cpu().tolist(), strict=True)
    )


def predict(
    model: LiftSharedTemporalExpert,
    inputs: Sequence[TemporalModelInput],
    stats: NormalizationStats,
) -> tuple[PredictionRow, ...]:
    prepared = prepare_batch(inputs, stats)
    model.eval()
    device = next(model.parameters()).device
    with torch.inference_mode():
        standardized = model(prepared.tensors.to(device))
    return _rows_from_standardized(prepared.row_ids, standardized, stats)


def predict_three_seed_ensemble(
    models: Sequence[LiftSharedTemporalExpert],
    inputs: Sequence[TemporalModelInput],
    stats: NormalizationStats,
) -> tuple[PredictionRow, ...]:
    if len(models) != 3:
        raise ValueError("the temporal expert ensemble requires exactly three seed models")
    prepared = prepare_batch(inputs, stats)
    devices = {next(model.parameters()).device for model in models}
    if len(devices) != 1:
        raise ValueError("all ensemble models must use the same device")
    device = next(iter(devices))
    with torch.inference_mode():
        standardized = []
        for model in models:
            model.eval()
            standardized.append(model(prepared.tensors.to(device)))
        ensemble = torch.stack(standardized).mean(dim=0)
    return _rows_from_standardized(prepared.row_ids, ensemble, stats)


def save_weights(path: Path, model: LiftSharedTemporalExpert) -> None:
    """Save learned tensors bound to their model spec; normalization stays separate."""

    torch.save({"model_spec_id": model.model_spec_id, "state_dict": model.state_dict()}, path)


def load_weights(path: Path, model: LiftSharedTemporalExpert) -> LiftSharedTemporalExpert:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, Mapping) or set(checkpoint) != {"model_spec_id", "state_dict"}:
        raise ValueError("weight file must contain a model spec and state dictionary")
    if checkpoint["model_spec_id"] != model.model_spec_id:
        raise ValueError("checkpoint model specification mismatch")
    state = checkpoint["state_dict"]
    if not isinstance(state, Mapping):
        raise ValueError("weight file state_dict must be a mapping")
    model.load_state_dict(state, strict=True)
    return model
