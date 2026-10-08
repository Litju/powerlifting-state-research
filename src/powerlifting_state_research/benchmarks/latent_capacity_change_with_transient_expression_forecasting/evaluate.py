"""Canonical evaluator for PUBLIC_NATIVE IID latent-capacity predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ... import __version__
from ...artifacts.manifests import RightsMetadata
from ...contracts.benchmark import (
    BenchmarkSpec,
)
from ...contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    ObservationAvailability,
    SplitIdentity,
    SupportSummary,
    TemporalCoverage,
)
from ...contracts.serialization import canonical_json_bytes, sha256_record
from ...evaluation.identity import (
    DATASET_SPEC_ID,
    EVALUATION_ID,
    METRIC_IDENTITIES,
    TARGETS,
)
from ...evaluation.metrics import (
    MetricName,
)
from ...evaluation.prediction import (
    PREDICTION_SCHEMA_ID,
    _object,
    _reject_constant,
    parse_prediction_jsonl,
)
from ...evaluation.protocols import (
    EvaluationResult,
    PredictionArtifactReference,
    ResultStatus,
)
from ...models.references import (
    DeterminismStatus,
    EnvironmentProvenance,
    ModelReference,
    RNGProvenance,
    TrainingProtocolReference,
)
from .alignment import align_and_score
from .dataset import (
    ForecastInputs,
    LiftInputs,
    PublicCapacityTargets,
    PublicForecastRow,
    PublicLiftInputs,
    validate_public_row,
)
from .interventions import HORIZONS_DAYS, DeclaredFuturePlan, HistorySegment
from .observations import HISTORY_OBSERVATION_DAYS, PerformanceObservation
from .spec import PUBLIC_NATIVE_SPEC

CANONICAL_BENCHMARK_ID = (
    "psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting"
    "@1.0.0~f99463d55ba0"
)
CANONICAL_BENCHMARK_DIGEST = (
    "sha256:f99463d55ba0902595a1866032ba94b803ac97d9b4985a89e208293da9c7fed0"
)
REALIZATION_ID = (
    "psr:dataset-realization:latent-capacity-transient-iid-production"
    "@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
)
REALIZATION_DIGEST = "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
MANIFEST_DIGEST = "sha256:2655965129f99fa98857f6c9363aa28a0dd964c2d7d8554156c17073e0277e35"
VALIDATION_SHA256 = "0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a"
VALIDATION_ROWS = 3_072
REALIZATION_ROWS = 15_360
MANIFEST_PATH = (
    Path.cwd().resolve()
    / "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting"
    / "iid-production.json"
)
VALIDATION_REGENERATION_COMMAND = (
    "uv run --locked python -m "
    "powerlifting_state_research.benchmarks."
    "latent_capacity_change_with_transient_expression_forecasting "
    "--output data/synthetic/latent_capacity_change_with_transient_expression_forecasting/"
    "iid-production "
    "--manifest data/manifests/realizations/"
    "latent_capacity_change_with_transient_expression_forecasting/iid-production.json"
)


@dataclass(frozen=True, slots=True)
class ValidationBinding:
    dataset_spec_id: str
    realization_id: str
    realization_digest: str
    manifest_digest: str
    validation_sha256: str
    validation_rows: int
    realization_rows: int


CANONICAL_VALIDATION = ValidationBinding(
    DATASET_SPEC_ID,
    REALIZATION_ID,
    REALIZATION_DIGEST,
    MANIFEST_DIGEST,
    VALIDATION_SHA256,
    VALIDATION_ROWS,
    REALIZATION_ROWS,
)


def _mapping(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        actual = set(value) if isinstance(value, dict) else set()
        raise ValueError(
            f"{label} fields invalid; expected={sorted(fields)}, "
            f"missing={sorted(fields - actual)}, extra={sorted(actual - fields)}"
        )
    return cast(dict[str, object], value)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a JSON number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _parse_truth_row(value: object) -> PublicForecastRow:
    row = _mapping(value, {"row_id", "inputs", "targets"}, "truth row")
    inputs = _mapping(
        row["inputs"],
        {"entity_id", "origin_day", "horizon_days", "declared_future_plan", "lifts"},
        "truth inputs",
    )
    plan = _mapping(
        inputs["declared_future_plan"],
        {"plan_id", "start_day", "end_day", "dose", "intensity"},
        "declared future plan",
    )
    declared_plan = DeclaredFuturePlan(
        _string(plan["plan_id"], "plan_id"),
        _integer(plan["start_day"], "plan start_day"),
        _integer(plan["end_day"], "plan end_day"),
        _number(plan["dose"], "plan dose"),
        _number(plan["intensity"], "plan intensity"),
    )
    lift_values = _mapping(inputs["lifts"], {"squat", "bench_press", "deadlift"}, "lifts")
    lifts: dict[str, LiftInputs] = {}
    for lift, item in lift_values.items():
        lift_row = _mapping(item, {"history", "history_schedule"}, f"{lift} input")
        raw_history = lift_row["history"]
        raw_schedule = lift_row["history_schedule"]
        if not isinstance(raw_history, list) or not isinstance(raw_schedule, list):
            raise ValueError(f"{lift} history and history_schedule must be arrays")
        history = tuple(
            PerformanceObservation(
                _integer(observation["day"], f"{lift} observation day"),
                _number(observation["assessment_kg"], f"{lift} assessment_kg"),
                _number(observation["prescribed_load_kg"], f"{lift} prescribed_load_kg"),
                _number(observation["velocity_mps"], f"{lift} velocity_mps"),
            )
            for observation in (
                _mapping(
                    item,
                    {"day", "assessment_kg", "prescribed_load_kg", "velocity_mps"},
                    f"{lift} observation",
                )
                for item in raw_history
            )
        )
        schedule = tuple(
            HistorySegment(
                _integer(segment["start_day"], f"{lift} schedule start_day"),
                _integer(segment["end_day"], f"{lift} schedule end_day"),
                _number(segment["dose"], f"{lift} schedule dose"),
                _number(segment["intensity"], f"{lift} schedule intensity"),
            )
            for segment in (
                _mapping(
                    item,
                    {"start_day", "end_day", "dose", "intensity"},
                    f"{lift} history segment",
                )
                for item in raw_schedule
            )
        )
        lifts[lift] = LiftInputs(history, schedule)
    targets = _mapping(row["targets"], set(TARGETS), "truth targets")
    parsed = PublicForecastRow(
        _string(row["row_id"], "truth row_id"),
        ForecastInputs(
            _string(inputs["entity_id"], "truth entity_id"),
            _integer(inputs["origin_day"], "truth origin_day"),
            _integer(inputs["horizon_days"], "truth horizon_days"),
            declared_plan,
            cast(PublicLiftInputs, lifts),
        ),
        cast(
            PublicCapacityTargets,
            {target: _number(targets[target], f"truth {target}") for target in TARGETS},
        ),
    )
    validate_public_row(parsed)
    if parsed.inputs.origin_day != 224 or parsed.inputs.horizon_days not in HORIZONS_DAYS:
        raise ValueError("truth row is outside the frozen origin/horizon contract")
    if tuple(item.day for item in parsed.inputs.lifts["squat"].history) != HISTORY_OBSERVATION_DAYS:
        raise ValueError("truth history does not match the frozen weekly observation schedule")
    return parsed


def _parse_manifest(path: Path, binding: ValidationBinding) -> DatasetRealizationManifest:
    raw_bytes = path.read_bytes()
    if not raw_bytes.endswith(b"\n"):
        raise ValueError("dataset manifest must be canonical JSON followed by a newline")
    try:
        raw_value = json.loads(
            raw_bytes[:-1], object_pairs_hook=_object, parse_constant=_reject_constant
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"invalid dataset realization manifest: {error}") from error
    if not isinstance(raw_value, dict) or canonical_json_bytes(raw_value) + b"\n" != raw_bytes:
        raise ValueError("dataset realization manifest is not canonical JSON")
    raw = cast(dict[str, object], raw_value)
    envelope = _mapping(
        raw,
        {
            "dataset_spec_id",
            "realization_id",
            "generator_identity",
            "source_identity",
            "seeds",
            "replicate_ids",
            "entity_count",
            "row_count",
            "split_identities",
            "artifact_hashes",
            "schema_identity",
            "temporal_coverage",
            "realized_intervention_support",
            "observation_availability",
            "provenance",
            "rights",
            "identity_id",
            "realization_digest",
            "manifest_digest",
        },
        "dataset manifest",
    )
    try:
        splits = tuple(
            SplitIdentity(
                _string(item["split_id"], "split_id"),
                _string(item["purpose"], "split purpose"),
                _integer(item["entity_count"], "split entity_count"),
                _integer(item["row_count"], "split row_count"),
            )
            for item in (
                _mapping(
                    value,
                    {"split_id", "purpose", "entity_count", "row_count"},
                    "split identity",
                )
                for value in cast(list[object], envelope["split_identities"])
            )
        )
        artifacts = tuple(
            ArtifactHash(
                _string(item["artifact_id"], "artifact_id"),
                _string(item["sha256"], "artifact sha256"),
                _string(item["media_type"], "artifact media_type"),
            )
            for item in (
                _mapping(value, {"artifact_id", "sha256", "media_type"}, "artifact hash")
                for value in cast(list[object], envelope["artifact_hashes"])
            )
        )
        coverage = _mapping(
            envelope["temporal_coverage"], {"event_index", "start", "end"}, "temporal coverage"
        )
        support = tuple(
            SupportSummary(
                _string(item["axis"], "support axis"),
                _string(item["description"], "support description"),
            )
            for item in (
                _mapping(value, {"axis", "description"}, "support summary")
                for value in cast(list[object], envelope["realized_intervention_support"])
            )
        )
        availability = tuple(
            ObservationAvailability(
                _string(item["field"], "observation field"),
                _integer(item["available_count"], "available_count"),
                _integer(item["missing_count"], "missing_count"),
            )
            for item in (
                _mapping(
                    value,
                    {"field", "available_count", "missing_count"},
                    "observation availability",
                )
                for value in cast(list[object], envelope["observation_availability"])
            )
        )
        rights_value = _mapping(
            envelope["rights"],
            {
                "license_expression",
                "copyright_holder",
                "redistribution_status",
                "access_conditions",
            },
            "rights",
        )
        access_conditions = rights_value["access_conditions"]
        if access_conditions is not None and not isinstance(access_conditions, str):
            raise ValueError("manifest access_conditions must be a string or null")
        rights = RightsMetadata(
            _string(rights_value["license_expression"], "license_expression"),
            _string(rights_value["copyright_holder"], "copyright_holder"),
            _string(rights_value["redistribution_status"], "redistribution_status"),
            access_conditions,
        )
        seed_values = cast(list[object], envelope["seeds"])
        seeds = tuple(
            (_string(pair[0], "seed name"), _integer(pair[1], "seed value"))
            for pair in (cast(list[object], value) for value in seed_values)
            if len(pair) == 2
        )
        if len(seeds) != len(seed_values):
            raise ValueError("manifest RNG seeds must be name/value pairs")
        time_start = coverage["start"]
        time_end = coverage["end"]
        if type(time_start) not in {int, str} or type(time_end) not in {int, str}:
            raise ValueError("manifest temporal coverage bounds must be integers or strings")
        manifest = DatasetRealizationManifest(
            _string(envelope["dataset_spec_id"], "dataset_spec_id"),
            _string(envelope["realization_id"], "realization_id"),
            cast(str | None, envelope["generator_identity"]),
            cast(str | None, envelope["source_identity"]),
            seeds,
            tuple(
                _string(value, "replicate ID")
                for value in cast(list[object], envelope["replicate_ids"])
            ),
            _integer(envelope["entity_count"], "entity_count"),
            _integer(envelope["row_count"], "row_count"),
            splits,
            artifacts,
            _string(envelope["schema_identity"], "schema_identity"),
            TemporalCoverage(
                _string(coverage["event_index"], "event_index"),
                cast(int | str, time_start),
                cast(int | str, time_end),
            ),
            support,
            availability,
            _string(envelope["provenance"], "provenance"),
            rights,
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(f"invalid dataset realization manifest fields: {error}") from error
    if envelope["identity_id"] != binding.realization_id:
        raise ValueError("dataset realization ID does not match the canonical evaluation binding")
    if (
        manifest.dataset_spec_id != binding.dataset_spec_id
        or manifest.identity_id != binding.realization_id
        or manifest.realization_digest != binding.realization_digest
        or manifest.manifest_digest != binding.manifest_digest
        or envelope["realization_digest"] != binding.realization_digest
        or envelope["manifest_digest"] != binding.manifest_digest
    ):
        raise ValueError(
            "dataset realization identity/digest does not match the evaluation binding"
        )
    if manifest.row_count != binding.realization_rows:
        raise ValueError("dataset realization row count does not match the evaluation binding")
    split = next(
        (item for item in manifest.split_identities if item.split_id == "validation"), None
    )
    artifact = next(
        (item for item in manifest.artifact_hashes if item.artifact_id == "validation"), None
    )
    if split is None or split.row_count != binding.validation_rows:
        raise ValueError("validation split row count does not match the evaluation binding")
    if artifact is None or artifact.sha256 != binding.validation_sha256:
        raise ValueError("validation artifact SHA does not match the evaluation binding")
    return manifest


def _load_truth(
    validation_path: Path,
    manifest_path: Path,
    binding: ValidationBinding,
) -> tuple[PublicForecastRow, ...]:
    if not validation_path.is_file():
        raise ValueError(
            f"canonical validation JSONL not found at {validation_path}; "
            "regenerate it with RES-270: "
            f"{VALIDATION_REGENERATION_COMMAND}"
        )
    if not manifest_path.is_file():
        raise ValueError(
            f"canonical dataset manifest not found at {manifest_path}; use the RES-270 "
            f"regeneration command: {VALIDATION_REGENERATION_COMMAND}"
        )
    _parse_manifest(manifest_path, binding)
    content = validation_path.read_bytes()
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != binding.validation_sha256:
        raise ValueError(
            f"validation SHA-256 mismatch: expected {binding.validation_sha256}, got {actual_sha}"
        )
    if not content or not content.endswith(b"\n"):
        raise ValueError("validation JSONL must be non-empty and newline-terminated")
    try:
        lines = content.decode("utf-8", errors="strict").splitlines(keepends=True)
    except UnicodeDecodeError as error:
        raise ValueError("validation JSONL must be UTF-8") from error
    if len(lines) != binding.validation_rows:
        raise ValueError(
            f"validation row count mismatch: expected {binding.validation_rows}, got {len(lines)}"
        )
    rows: list[PublicForecastRow] = []
    seen: set[str] = set()
    for index, line in enumerate(lines, start=1):
        raw_line = line.removesuffix("\n").encode("utf-8")
        try:
            value = json.loads(
                raw_line,
                object_pairs_hook=_object,
                parse_constant=_reject_constant,
            )
            if canonical_json_bytes(value) != raw_line:
                raise ValueError("row is not canonical compact JSON")
            row = _parse_truth_row(value)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as error:
            raise ValueError(f"invalid validation row {index}: {error}") from error
        if row.row_id in seen:
            raise ValueError(f"duplicate validation row_id {row.row_id!r}")
        seen.add(row.row_id)
        rows.append(row)
    return tuple(rows)


def _check_benchmark(spec: BenchmarkSpec) -> None:
    if (
        spec.benchmark_id != CANONICAL_BENCHMARK_ID
        or spec.semantic_digest != CANONICAL_BENCHMARK_DIGEST
    ):
        raise ValueError(
            "BenchmarkSpec identity/digest does not match the canonical PUBLIC_NATIVE evaluator"
        )
    if spec.semantic_identity is None or spec.semantic_identity.evaluation_id != EVALUATION_ID:
        raise ValueError(
            "PUBLIC_NATIVE BenchmarkSpec does not bind the canonical evaluation identity"
        )


def _environment() -> EnvironmentProvenance:
    facts = {
        "package": f"powerlifting-state-research=={__version__}",
        "runtime_dependencies": "none",
        "python": platform.python_version(),
        "platform": f"{platform.system()}-{platform.machine()}",
    }
    identity = sha256_record(facts)
    return EnvironmentProvenance(
        environment_id=f"psr:evaluator-environment@{identity}",
        python_version=platform.python_version(),
        platform=facts["platform"],
        dependency_identity=f"{facts['package']};runtime-dependencies=none",
    )


def evaluate_files(
    validation_path: Path,
    predictions_path: Path,
    model_id: str,
    *,
    manifest_path: Path = MANIFEST_PATH,
    validation_binding: ValidationBinding = CANONICAL_VALIDATION,
    benchmark_spec: BenchmarkSpec = PUBLIC_NATIVE_SPEC,
    environment: EnvironmentProvenance | None = None,
) -> EvaluationResult:
    """Validate frozen truth/predictions, align by row_id, and bind a result."""
    _check_benchmark(benchmark_spec)
    truth_rows = _load_truth(validation_path, manifest_path, validation_binding)
    prediction_bytes = predictions_path.read_bytes()
    predictions = parse_prediction_jsonl(prediction_bytes)
    target_metrics = align_and_score(truth_rows, predictions)
    prediction_sha = hashlib.sha256(prediction_bytes).hexdigest()
    return EvaluationResult(
        benchmark_id=benchmark_spec.benchmark_id or "",
        benchmark_spec_digest=benchmark_spec.semantic_digest or "",
        dataset_realization_id=validation_binding.realization_id,
        dataset_realization_digest=validation_binding.realization_digest,
        model=ModelReference(model_id),
        training_protocol=TrainingProtocolReference(
            training_protocol_id=None,
            not_applicable_reason=(
                "Predictions were supplied as a precomputed artifact; "
                "this evaluator does not train."
            ),
        ),
        fitted_instance=None,
        checkpoint=None,
        environment=environment or _environment(),
        rng=RNGProvenance(
            DeterminismStatus.NOT_APPLICABLE,
            explanation="Evaluation uses fixed prediction bytes and performs no random sampling.",
        ),
        prediction_artifact=PredictionArtifactReference(
            artifact_id=f"prediction-jsonl-{prediction_sha[:12]}",
            benchmark_id=benchmark_spec.benchmark_id or "",
            benchmark_spec_digest=benchmark_spec.semantic_digest or "",
            dataset_realization_id=validation_binding.realization_id,
            dataset_realization_digest=validation_binding.realization_digest,
            model_id=model_id,
            output_schema_identity=PREDICTION_SCHEMA_ID,
            row_count=len(predictions),
            content_sha256=f"sha256:{prediction_sha}",
            rights=RightsMetadata(
                license_expression="NOASSERTION",
                copyright_holder="Not asserted",
                redistribution_status=(
                    "External prediction rights are not claimed; "
                    "only evaluation metadata is retained."
                ),
            ),
        ),
        evaluation_id=EVALUATION_ID,
        metric_identities=METRIC_IDENTITIES,
        targets=tuple(target_metrics),
        aggregations=(),
        stratifications=(),
        exclusions=(),
        uncertainty=(),
        status=ResultStatus.COMPLETE,
        rights=RightsMetadata(
            license_expression="MIT",
            copyright_holder="Powerlifting State Research contributors",
            redistribution_status=(
                "Repository-generated evaluation metadata; "
                "redistribution permitted with attribution."
            ),
        ),
    )


def result_json_bytes(result: EvaluationResult) -> bytes:
    return canonical_json_bytes(result) + b"\n"


def _print_metrics(result: EvaluationResult) -> None:
    print(
        "target                         RMSE (kg)   MAE (kg)         R²   SRE(ddof=0)",
        file=sys.stderr,
    )
    for target in result.targets:
        values = {item.metric: item for item in target.metrics}
        formatted = [
            "UNDEFINED" if values[metric].value is None else f"{values[metric].value:.6g}"
            for metric in (MetricName.RMSE, MetricName.MAE, MetricName.R2, MetricName.SRE)
        ]
        print(
            f"{target.target:30} {formatted[0]:>10} {formatted[1]:>10} "
            f"{formatted[2]:>10} {formatted[3]:>12}",
            file=sys.stderr,
        )
    print(result.result_id, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = evaluate_files(
            args.validation,
            args.predictions,
            args.model_id,
            manifest_path=args.manifest,
            validation_binding=CANONICAL_VALIDATION,
        )
        serialized = result_json_bytes(result)
        if args.output is None:
            sys.stdout.buffer.write(serialized)
        else:
            args.output.write_bytes(serialized)
        _print_metrics(result)
    except (OSError, ValueError) as error:
        print(f"evaluation failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
