"""Seeded public dataset generation, causal validation, and realization manifests."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from ...artifacts.manifests import RightsMetadata
from ...contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    ObservationAvailability,
    SplitIdentity,
    SupportSummary,
    TemporalCoverage,
)
from ...contracts.serialization import canonical_json_bytes, sha256_record
from .dynamics import (
    LiftTrajectory,
    TrainingSession,
    latent_capacity_change,
    simulate_lift,
)
from .interventions import (
    DOSE_INTENSITY_PAIRS,
    HISTORY_TEMPLATES,
    HORIZONS_DAYS,
    ORIGIN_DAY,
    PLAN_END_DAY,
    PLAN_IDS,
    STRATA,
    DeclaredFuturePlan,
    HistorySegment,
    declared_plan,
    history_segments,
    sample_history_template_combinations,
    training_sessions,
)
from .observations import (
    ASSESSMENT_CV,
    HISTORY_OBSERVATION_DAYS,
    LOAD_FRACTION_RANGE,
    RELATIVE_LOAD_DOMAIN,
    VELOCITY_CONSTANTS,
    VELOCITY_SD_MPS,
    PerformanceObservation,
    sample_performance_history,
)
from .population import (
    ADAPTATION_RETENTION_28D_RANGE,
    ADAPTATION_UTILIZATION_RANGE,
    BASELINE_SCALE_KG_RANGE,
    BENCH_RATIO_RANGE,
    COORDINATE_ORDER,
    DEADLIFT_RATIO_RANGE,
    LIFTS,
    REFERENCE_DOSE_PRODUCT,
    REFERENCE_STIMULUS_RANGE,
    SUPPRESSION_RETENTION_RANGE,
    SUPPRESSION_UTILIZATION_RANGE,
    AthleteProfile,
    sample_athlete,
)
from .spec import PUBLIC_NATIVE_DATASET_SPEC_ID

PRODUCTION_ROWS = {"train": 12_288, "validation": 3_072}
SCHEMA_IDENTITY = "latent-capacity-transient-participant-row-v2"
GENERATOR_IDENTITY = (
    "powerlifting_state_research.benchmarks."
    "latent_capacity_change_with_transient_expression_forecasting.dataset:iid-public-production"
)
REALIZATION_ID = "latent-capacity-transient-iid-production"
DATASET_SPEC_ID = PUBLIC_NATIVE_DATASET_SPEC_ID
SOURCE_IDENTITY = (
    "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md"
)


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    train_rows: int = PRODUCTION_ROWS["train"]
    validation_rows: int = PRODUCTION_ROWS["validation"]
    population_seed: int = 26_901
    intervention_seed: int = 26_902
    observation_seed: int = 26_903
    split_seed: int = 26_904
    serialization_seed: int = 26_905

    def __post_init__(self) -> None:
        if min(self.train_rows, self.validation_rows) < len(STRATA):
            raise ValueError("each split must have at least one row per plan/horizon stratum")
        if any(count % len(STRATA) for count in (self.train_rows, self.validation_rows)):
            raise ValueError("split row counts must divide evenly across all plan/horizon strata")
        if (
            min(
                self.population_seed,
                self.intervention_seed,
                self.observation_seed,
                self.split_seed,
                self.serialization_seed,
            )
            < 0
        ):
            raise ValueError("generation seeds cannot be negative")


DEFAULT_CONFIG = GenerationConfig()


@dataclass(frozen=True, slots=True)
class LiftInputs:
    history: tuple[PerformanceObservation, ...]
    history_schedule: tuple[HistorySegment, ...]


@dataclass(frozen=True, slots=True)
class ForecastInputs:
    entity_id: str
    origin_day: int
    horizon_days: int
    declared_future_plan: DeclaredFuturePlan
    lifts: dict[str, LiftInputs]


@dataclass(frozen=True, slots=True)
class PublicForecastRow:
    row_id: str
    inputs: ForecastInputs
    targets: dict[str, float]


@dataclass(frozen=True, slots=True)
class PublicRealization:
    output_directory: Path
    manifest: DatasetRealizationManifest

    @property
    def train_sha256(self) -> str:
        return self.manifest.artifact_hashes[0].sha256

    @property
    def validation_sha256(self) -> str:
        return self.manifest.artifact_hashes[1].sha256


PUBLIC_GENERATION_CONFIGURATION: dict[str, object] = {
    "world": {
        "stimulus": "dose*intensity/(dose*intensity+stimulus_reference)",
        "adaptation": "A[t]=exp(-1/tau_a)*A[t-1]+(1-exp(-1/tau_a))*S[t]",
        "capacity": "baseline*(1+adaptation_gain*adaptation)",
        "suppression": "R[t]=exp(-1/tau_r)*R[t-1]+(1-exp(-1/tau_r))*S[t]",
        "expression": "capacity*(1-suppression_gain*suppression)",
        "adaptation_retention_days": ADAPTATION_RETENTION_28D_RANGE,
        "suppression_retention": SUPPRESSION_RETENTION_RANGE,
        "process_disturbances": "none",
        "cross_lift_edges": "none",
    },
    "population": {
        "coordinates": COORDINATE_ORDER,
        "measure": "independent Uniform(0,1) coordinates",
        "sampling_algorithm": ("IID pseudorandom draws from random.Random(population_seed).random"),
        "sampling_order": "one complete coordinate vector per entity in increasing entity index",
        "baseline_scale_kg": BASELINE_SCALE_KG_RANGE,
        "bench_ratio": BENCH_RATIO_RANGE,
        "deadlift_ratio": DEADLIFT_RATIO_RANGE,
        "reference_dose_product": REFERENCE_DOSE_PRODUCT,
        "reference_stimulus": REFERENCE_STIMULUS_RANGE,
        "adaptation_utilization": ADAPTATION_UTILIZATION_RANGE,
        "adaptation_retention_28_days": ADAPTATION_RETENTION_28D_RANGE,
        "suppression_utilization": SUPPRESSION_UTILIZATION_RANGE,
        "suppression_retention": SUPPRESSION_RETENTION_RANGE,
        "transforms": {
            "baseline_scale": "log-linear coordinate map",
            "ratios_and_utilizations": "linear coordinate map",
            "adaptation_gain": "adaptation_utilization/reference_stimulus",
            "adaptation_time_days": "-28/log(1-adaptation_retention_28d)",
            "suppression_gain": "suppression_utilization/reference_stimulus",
            "suppression_time_days": "-1/log(suppression_retention)",
            "stimulus_reference": "reference_product*(1-reference_stimulus)/reference_stimulus",
        },
    },
    "intervention": {
        "dose_intensity_pairs": DOSE_INTENSITY_PAIRS,
        "history_templates": HISTORY_TEMPLATES,
        "history_template_combinations_balanced_per_split_and_stratum": True,
        "history_days": ORIGIN_DAY,
        "future_plan_days": (ORIGIN_DAY, PLAN_END_DAY),
        "balanced_strata": STRATA,
    },
    "observation": {
        "days": HISTORY_OBSERVATION_DAYS,
        "assessment_cv": ASSESSMENT_CV,
        "velocity_sd_mps": VELOCITY_SD_MPS,
        "velocity_relation": VELOCITY_CONSTANTS,
        "load_fraction": LOAD_FRACTION_RANGE,
        "relative_load_domain": RELATIVE_LOAD_DOMAIN,
        "assessment": "P*(1+Normal(0,cv_lift))",
        "prescribed_load": "Uniform(load_fraction)*assessment",
        "velocity": "endpoint+span*((1-relative_load)/0.60)^exponent+Normal(0,sigma_lift)",
    },
    "task": {
        "origin_day": ORIGIN_DAY,
        "horizons_days": HORIZONS_DAYS,
        "target": "C[origin+horizon-1]-C[origin-1]",
        "row_unit": "one entity, one declared plan, one horizon, all lifts",
    },
    "production_rows": PRODUCTION_ROWS,
    "schema": SCHEMA_IDENTITY,
    "serialization": "seeded permutation after row completion; compact sorted-key UTF-8 JSONL; LF",
    "rng_ownership": (
        "population",
        "intervention/history-template and plan-horizon stratum order",
        "split labels within fixed history-template groups",
        "observation noise",
        "serialization order over complete rows",
    ),
}
PUBLIC_GENERATION_CONFIGURATION_SHA256 = sha256_record(PUBLIC_GENERATION_CONFIGURATION)


def _row_records(config: GenerationConfig) -> list[tuple[str, int, str, int, tuple[int, ...]]]:
    records: list[tuple[str, int, str, int, tuple[int, ...]]] = []
    intervention_rng = random.Random(config.intervention_seed)
    split_rng = random.Random(config.split_seed)
    stratum_order = list(STRATA)
    intervention_rng.shuffle(stratum_order)
    next_entity = 0
    train_per_stratum = config.train_rows // len(STRATA)
    validation_per_stratum = config.validation_rows // len(STRATA)
    for plan_id, horizon in stratum_order:
        templates_by_split = {
            "train": sample_history_template_combinations(intervention_rng, train_per_stratum),
            "validation": sample_history_template_combinations(
                intervention_rng, validation_per_stratum
            ),
        }
        template_order = dict.fromkeys(
            (*templates_by_split["train"], *templates_by_split["validation"])
        )
        # ponytail: scans at most 64 template groups per stratum; pre-count if dimensions grow.
        for templates in template_order:
            split_labels = [
                split
                for split, assignments in templates_by_split.items()
                for assignment in assignments
                if assignment == templates
            ]
            split_rng.shuffle(split_labels)
            for split in split_labels:
                records.append((split, next_entity, plan_id, horizon, templates))
                next_entity += 1
    return records


def simulate_athlete(
    athlete: AthleteProfile,
    sessions_by_lift: Mapping[str, Mapping[int, TrainingSession]],
) -> dict[str, LiftTrajectory]:
    if set(sessions_by_lift) != set(LIFTS):
        raise ValueError("world schedule must contain exactly the three lifts")
    return {
        lift: simulate_lift(
            athlete.parameters.lifts[lift],
            sessions_by_lift[lift],
            athlete.parameters.stimulus_reference,
            PLAN_END_DAY,
        )
        for lift in LIFTS
    }


def validate_public_row(row: PublicForecastRow) -> None:
    """Enforce row identities, task times, and participant-visible field bounds."""
    if not row.row_id or row.row_id != row.inputs.entity_id:
        raise ValueError("row and entity identities must be the same non-empty key")
    if row.inputs.origin_day != ORIGIN_DAY or row.inputs.horizon_days not in HORIZONS_DAYS:
        raise ValueError("row does not use a frozen origin and horizon")
    plan = row.inputs.declared_future_plan
    if plan.plan_id not in DOSE_INTENSITY_PAIRS:
        raise ValueError("row has an undeclared future plan")
    if (plan.start_day, plan.end_day, plan.dose, plan.intensity) != (
        ORIGIN_DAY,
        PLAN_END_DAY,
        *DOSE_INTENSITY_PAIRS[plan.plan_id],
    ):
        raise ValueError("declared plan does not match its permitted support")
    if set(row.inputs.lifts) != set(LIFTS):
        raise ValueError("row must contain all three lifts")
    expected_days = HISTORY_OBSERVATION_DAYS
    for lift in LIFTS:
        lift_inputs = row.inputs.lifts[lift]
        if tuple(item.day for item in lift_inputs.history) != expected_days:
            raise ValueError(f"{lift} history must contain the 32 weekly observations")
        if not lift_inputs.history_schedule or lift_inputs.history_schedule[0].start_day != 0:
            raise ValueError(f"{lift} history schedule must start on day 0")
        if lift_inputs.history_schedule[-1].end_day != ORIGIN_DAY - 1:
            raise ValueError(f"{lift} history schedule must end on day 223")
        next_day = 0
        for segment in lift_inputs.history_schedule:
            if segment.start_day != next_day or segment.end_day < segment.start_day:
                raise ValueError(f"{lift} history schedule has a gap or overlap")
            if segment.end_day > ORIGIN_DAY - 1:
                raise ValueError("learner-visible realized training extends beyond day 223")
            if (segment.dose, segment.intensity) not in DOSE_INTENSITY_PAIRS.values():
                raise ValueError("history schedule contains off-support training")
            next_day = segment.end_day + 1
        for observation in lift_inputs.history:
            if observation.day > ORIGIN_DAY:
                raise ValueError("learner-visible observation exceeds inclusive cutoff")
            if observation.day > ORIGIN_DAY - 1:
                raise ValueError("historical observation occurs after day 223")
            if any(
                not math.isfinite(value)
                for value in (
                    observation.assessment_kg,
                    observation.prescribed_load_kg,
                    observation.velocity_mps,
                )
            ):
                raise ValueError("learner-visible observation must be finite")
    expected_targets = {f"{lift}_delta_capacity_kg" for lift in LIFTS}
    if set(row.targets) != expected_targets or any(
        not math.isfinite(value) for value in row.targets.values()
    ):
        raise ValueError("row targets must contain finite latent-capacity changes for all lifts")


def iter_public_rows(
    config: GenerationConfig = DEFAULT_CONFIG,
) -> Iterator[tuple[str, PublicForecastRow]]:
    records = _row_records(config)
    population_rng = random.Random(config.population_seed)
    observation_rng = random.Random(config.observation_seed)
    for split, index, plan_id, horizon, templates in records:
        athlete = sample_athlete(index, population_rng)
        plan = declared_plan(plan_id)
        sessions_by_lift = {
            lift: training_sessions(templates[lift_index], plan)
            for lift_index, lift in enumerate(LIFTS)
        }
        trajectories = simulate_athlete(athlete, sessions_by_lift)
        lifts: dict[str, LiftInputs] = {}
        for lift_index, lift in enumerate(LIFTS):
            segments = history_segments(templates[lift_index])
            history = sample_performance_history(
                trajectories[lift].expressed_performance_kg,
                lift,
                observation_rng,
            )
            lifts[lift] = LiftInputs(history, segments)
        row = PublicForecastRow(
            row_id=athlete.entity_id,
            inputs=ForecastInputs(athlete.entity_id, ORIGIN_DAY, horizon, plan, lifts),
            targets={
                f"{lift}_delta_capacity_kg": latent_capacity_change(
                    trajectories[lift], ORIGIN_DAY, horizon
                )
                for lift in LIFTS
            },
        )
        validate_public_row(row)
        yield split, row


def _manifest_json(manifest: DatasetRealizationManifest) -> bytes:
    payload = json.loads(manifest.canonical_serialization)
    payload["identity_id"] = manifest.identity_id
    payload["realization_digest"] = manifest.realization_digest
    payload["manifest_digest"] = manifest.manifest_digest
    return canonical_json_bytes(payload) + b"\n"


def write_manifest_copy(manifest: DatasetRealizationManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temp_name = file.name
            file.write(_manifest_json(manifest))
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def write_public_realization(
    output_directory: Path, config: GenerationConfig = DEFAULT_CONFIG
) -> PublicRealization:
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".latent-capacity-realization-", dir=output_directory.parent)
    )
    try:
        digests = {split: hashlib.sha256() for split in ("train", "validation")}
        entity_ids: dict[str, set[str]] = {split: set() for split in ("train", "validation")}
        row_ids: set[str] = set()
        row_counts = {split: 0 for split in ("train", "validation")}
        serialized_rows = [
            (split, row.row_id, canonical_json_bytes(row) + b"\n")
            for split, row in iter_public_rows(config)
        ]
        random.Random(config.serialization_seed).shuffle(serialized_rows)
        with (
            (staging / "train.jsonl").open("wb") as train_file,
            (staging / "validation.jsonl").open("wb") as validation_file,
        ):
            sinks = {"train": train_file, "validation": validation_file}
            for split, row_id, payload in serialized_rows:
                if row_id in row_ids or row_id in entity_ids[split]:
                    raise ValueError("generated row/entity identities are not unique")
                row_ids.add(row_id)
                entity_ids[split].add(row_id)
                sinks[split].write(payload)
                digests[split].update(payload)
                row_counts[split] += 1

        if row_counts != {
            "train": config.train_rows,
            "validation": config.validation_rows,
        }:
            raise ValueError("generated split row counts do not match configuration")
        if entity_ids["train"] & entity_ids["validation"]:
            raise ValueError("train and validation entities overlap")

        train_digest = digests["train"].hexdigest()
        validation_digest = digests["validation"].hexdigest()
        manifest = DatasetRealizationManifest(
            dataset_spec_id=DATASET_SPEC_ID,
            realization_id=REALIZATION_ID,
            generator_identity=(
                f"{GENERATOR_IDENTITY};config-sha256="
                f"{PUBLIC_GENERATION_CONFIGURATION_SHA256.removeprefix('sha256:')}"
            ),
            source_identity=SOURCE_IDENTITY,
            seeds=(
                ("population", config.population_seed),
                ("intervention_plan", config.intervention_seed),
                ("observation_noise", config.observation_seed),
                ("split_allocation", config.split_seed),
                ("serialization_order", config.serialization_seed),
            ),
            replicate_ids=("iid-public-production",),
            entity_count=config.train_rows + config.validation_rows,
            row_count=config.train_rows + config.validation_rows,
            split_identities=(
                SplitIdentity("train", "model fitting", config.train_rows, config.train_rows),
                SplitIdentity(
                    "validation",
                    "same-law held-out validation",
                    config.validation_rows,
                    config.validation_rows,
                ),
            ),
            artifact_hashes=(
                ArtifactHash("train", train_digest, "application/x-ndjson"),
                ArtifactHash("validation", validation_digest, "application/x-ndjson"),
            ),
            schema_identity=SCHEMA_IDENTITY,
            temporal_coverage=TemporalCoverage("day", 0, PLAN_END_DAY),
            realized_intervention_support=tuple(
                SupportSummary(
                    f"plan:{plan_id}",
                    f"daily dose {DOSE_INTENSITY_PAIRS[plan_id][0]:g}, intensity "
                    f"{DOSE_INTENSITY_PAIRS[plan_id][1]:g} over days 224–279",
                )
                for plan_id in PLAN_IDS
            ),
            observation_availability=tuple(
                ObservationAvailability(
                    field,
                    (config.train_rows + config.validation_rows)
                    * len(LIFTS)
                    * len(HISTORY_OBSERVATION_DAYS),
                    0,
                )
                for field in (
                    "assessment_kg",
                    "prescribed_load_kg",
                    "velocity_mps",
                )
            ),
            provenance=(
                "Generated by the independently authored public-native IID benchmark. Its "
                "sampling design is DatasetSpec-bearing and differs from the historical scrambled "
                "Sobol design. Historical source and data bytes are not runtime inputs. Public "
                "configuration SHA-256: "
                f"{PUBLIC_GENERATION_CONFIGURATION_SHA256.removeprefix('sha256:')}."
            ),
            rights=RightsMetadata(
                "CC-BY-4.0",
                "Powerlifting State Research contributors",
                "Public redistribution permitted with attribution",
            ),
        )
        (staging / "manifest.json").write_bytes(_manifest_json(manifest))
        os.replace(staging, output_directory)
        return PublicRealization(output_directory, manifest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
