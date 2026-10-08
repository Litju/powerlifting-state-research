import hashlib
import json
from dataclasses import replace
from importlib import import_module
from pathlib import Path

import pytest

from powerlifting_state_research.artifacts.manifests import RightsMetadata
from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as iid_benchmark,
)
from powerlifting_state_research.contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    SplitIdentity,
    TemporalCoverage,
)
from powerlifting_state_research.contracts.prediction import (
    InformationKind,
    InputField,
)
from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.evaluation.identity import TARGETS
from powerlifting_state_research.evaluation.metrics import (
    MetricName,
    MetricStatus,
    NonFiniteMetricInputPolicy,
    canonical_target_metrics,
)
from powerlifting_state_research.evaluation.prediction import (
    PREDICTION_FIELDS,
    PredictionRow,
    canonical_prediction_jsonl,
    parse_prediction_jsonl,
)
from powerlifting_state_research.models.references import EnvironmentProvenance

evaluator = import_module(f"{iid_benchmark.__name__}.evaluate")
prediction_contract = import_module(f"{iid_benchmark.__name__}.prediction")
GenerationConfig = iid_benchmark.GenerationConfig
PublicForecastRow = iid_benchmark.PublicForecastRow
iter_public_rows = iid_benchmark.iter_public_rows
PUBLIC_NATIVE_SPEC = iid_benchmark.PUBLIC_NATIVE_SPEC

MODEL_ID = "psr:model:test-prediction-fixture@1.0.0~000000000000"
METRIC_ORDER = (MetricName.RMSE, MetricName.MAE, MetricName.R2, MetricName.SRE)


@pytest.fixture
def evaluation_files(
    tmp_path: Path,
) -> tuple[Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]]:
    config = GenerationConfig(train_rows=12, validation_rows=12)
    truth_rows = tuple(row for split, row in iter_public_rows(config) if split == "validation")
    validation_bytes = b"".join(canonical_json_bytes(row) + b"\n" for row in truth_rows)
    validation_path = tmp_path / "validation.jsonl"
    validation_path.write_bytes(validation_bytes)
    validation_sha = hashlib.sha256(validation_bytes).hexdigest()
    manifest = DatasetRealizationManifest(
        dataset_spec_id=evaluator.DATASET_SPEC_ID,
        realization_id="iid-test-evaluation-fixture",
        generator_identity="test-only-fixture-generator",
        source_identity=None,
        seeds=(),
        replicate_ids=("test-fixture",),
        entity_count=len(truth_rows),
        row_count=len(truth_rows),
        split_identities=(
            SplitIdentity("validation", "test-only fixture", len(truth_rows), len(truth_rows)),
        ),
        artifact_hashes=(ArtifactHash("validation", validation_sha, "application/x-ndjson"),),
        schema_identity="latent-capacity-transient-participant-row-v2",
        temporal_coverage=TemporalCoverage("day", 0, 279),
        realized_intervention_support=(),
        observation_availability=(),
        provenance="Test-only evaluator fixture; not model or benchmark evidence.",
        rights=RightsMetadata("CC0-1.0", "Test authors", "Test fixture only."),
    )
    manifest_value = {
        **manifest.manifest_payload(),
        "identity_id": manifest.identity_id,
        "realization_digest": manifest.realization_digest,
        "manifest_digest": manifest.manifest_digest,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest_value) + b"\n")
    binding = evaluator.ValidationBinding(
        manifest.dataset_spec_id,
        manifest.identity_id,
        manifest.realization_digest,
        manifest.manifest_digest,
        validation_sha,
        len(truth_rows),
        len(truth_rows),
    )
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_bytes(
        canonical_prediction_jsonl(
            tuple(
                PredictionRow(
                    row.row_id,
                    *(float(row.targets[target]) for target in TARGETS),
                )
                for row in truth_rows
            )
        )
    )
    return validation_path, predictions_path, manifest_path, binding, truth_rows


def _evaluate(
    files: tuple[Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]],
    *,
    predictions_path: Path | None = None,
    binding: evaluator.ValidationBinding | None = None,
    benchmark_spec=PUBLIC_NATIVE_SPEC,
):
    validation_path, default_predictions, manifest_path, default_binding, _ = files
    return evaluator.evaluate_files(
        validation_path,
        predictions_path or default_predictions,
        MODEL_ID,
        manifest_path=manifest_path,
        validation_binding=binding or default_binding,
        benchmark_spec=benchmark_spec,
        environment=EnvironmentProvenance("test-eval-env", "3.12", "test", "deps:none"),
    )


def test_hand_computable_canonical_metrics_and_undefined_cases() -> None:
    ordinary = canonical_target_metrics("target", (1.0, 2.0, 3.0), (1.0, 2.0, 4.0), unit="kg")
    values = {item.metric: item for item in ordinary.metrics}
    assert values[MetricName.RMSE].value == pytest.approx((1 / 3) ** 0.5)
    assert values[MetricName.MAE].value == pytest.approx(1 / 3)
    assert values[MetricName.R2].value == pytest.approx(0.5)
    assert values[MetricName.SRE].value == pytest.approx(0.5**0.5)
    assert values[MetricName.RMSE].unit == values[MetricName.MAE].unit == "kg"
    assert values[MetricName.R2].unit == values[MetricName.SRE].unit == "1"

    constant = canonical_target_metrics("target", (2.0, 2.0), (2.0, 3.0), unit="kg")
    constant_values = {item.metric: item for item in constant.metrics}
    assert constant_values[MetricName.R2].status is MetricStatus.UNDEFINED
    assert constant_values[MetricName.R2].reason == "CONSTANT_TRUTH"
    assert constant_values[MetricName.SRE].reason == "ZERO_TRUTH_POPULATION_SD"

    empty = canonical_target_metrics("target", (), (), unit="kg")
    assert {item.reason for item in empty.metrics} == {"EMPTY_TRUTH"}
    with pytest.raises(ValueError, match="missing predictions"):
        canonical_target_metrics("target", (1.0,), (None,), unit="kg")
    with pytest.raises(ValueError, match="non-finite"):
        canonical_target_metrics("target", (1.0,), (float("inf"),), unit="kg")
    with pytest.raises(ValueError, match="non-finite"):
        canonical_target_metrics(
            "target",
            (1.0,),
            (float("nan"),),
            unit="kg",
            non_finite_policy=NonFiniteMetricInputPolicy.REJECT,
        )


def test_prediction_contract_freezes_cutoff_outputs_alignment_and_firewall() -> None:
    contract = prediction_contract.PREDICTION_CONTRACT
    contract.validate()
    assert contract.decision_cutoff.value == 224
    assert contract.cutoff_inclusive
    assert contract.history_observation_last_day == 223
    assert contract.information_boundary.history_observation_last_day == 223
    assert contract.row_identity_fields == ("row_id",)
    assert contract.ordering_alignment_policy.value == "ALIGN_BY_DECLARED_KEYS"
    assert tuple(output.name for output in contract.outputs) == TARGETS
    assert all(output.unit == "kg" for output in contract.outputs)
    assert any(item.kind is InformationKind.DECLARED_FUTURE_PLAN for item in contract.inputs)
    with pytest.raises(ValueError, match="history observations must end"):
        replace(contract, history_observation_last_day=225).validate()

    for kind in (
        InformationKind.FUTURE_REALIZED_PERFORMANCE,
        InformationKind.FUTURE_OBSERVATION,
        InformationKind.FUTURE_PROCESS_DISTURBANCE,
        InformationKind.UNKNOWN_FUTURE_INTERVENTION_DEVIATION,
        InformationKind.TARGET_DERIVED,
        InformationKind.EVALUATION_TRUTH,
    ):
        blocked = replace(contract, inputs=(InputField("forbidden", kind),))
        with pytest.raises(ValueError, match="forbidden prediction input"):
            blocked.validate()


def test_prediction_schema_is_generated_from_the_typed_row() -> None:
    from powerlifting_state_research.exports import generated_files

    schema = json.loads(
        generated_files()[Path("schemas/iid-latent-capacity-change-prediction-row.schema.json")]
    )
    row_schema = schema["$defs"]["PredictionRow"]
    assert set(row_schema["properties"]) == PREDICTION_FIELDS
    assert set(row_schema["required"]) == PREDICTION_FIELDS
    assert row_schema["additionalProperties"] is False


def test_prediction_jsonl_rejects_invalid_rows_and_canonicalizes() -> None:
    row = PredictionRow("row-1", 1.0, 2.0, 3.0)
    assert set(json.loads(canonical_prediction_jsonl((row,)).decode())) == PREDICTION_FIELDS
    assert parse_prediction_jsonl(canonical_prediction_jsonl((row,))) == (row,)

    duplicate = canonical_json_bytes(row) + b"\n" + canonical_json_bytes(row) + b"\n"
    with pytest.raises(ValueError, match="duplicate prediction row_id"):
        parse_prediction_jsonl(duplicate)
    with pytest.raises(ValueError, match="malformed"):
        parse_prediction_jsonl(b"{bad json}\n")

    missing = {
        key: value
        for key, value in json.loads(canonical_json_bytes(row)).items()
        if key != "deadlift_delta_capacity_kg"
    }
    with pytest.raises(ValueError, match="missing=.*deadlift_delta_capacity_kg"):
        parse_prediction_jsonl(canonical_json_bytes(missing) + b"\n")
    extra = {**json.loads(canonical_json_bytes(row)), "unknown": 1}
    with pytest.raises(ValueError, match="extra=.*unknown"):
        parse_prediction_jsonl(canonical_json_bytes(extra) + b"\n")
    wrong_primitive = {**json.loads(canonical_json_bytes(row)), "squat_delta_capacity_kg": True}
    with pytest.raises(ValueError, match="finite JSON numbers"):
        parse_prediction_jsonl(canonical_json_bytes(wrong_primitive) + b"\n")
    with pytest.raises(ValueError, match="finite JSON numbers"):
        parse_prediction_jsonl(
            b'{"bench_press_delta_capacity_kg":2.0,"deadlift_delta_capacity_kg":3.0,'
            b'"row_id":"row-1","squat_delta_capacity_kg":1e999}\n'
        )
    with pytest.raises(ValueError, match="non-standard JSON"):
        parse_prediction_jsonl(
            b'{"bench_press_delta_capacity_kg":2.0,"deadlift_delta_capacity_kg":3.0,'
            b'"row_id":"row-1","squat_delta_capacity_kg":NaN}\n'
        )


def test_small_end_to_end_perfect_predictions_and_result_determinism(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
) -> None:
    first = _evaluate(evaluation_files)
    second = _evaluate(evaluation_files)
    assert first.digest == second.digest
    assert first.result_id == second.result_id
    assert evaluator.result_json_bytes(first) == evaluator.result_json_bytes(second)
    assert first.aggregations == first.stratifications == first.uncertainty == ()
    assert first.prediction_artifact.output_schema_identity == evaluator.PREDICTION_SCHEMA_ID
    assert first.training_protocol.training_protocol_id is None
    assert first.fitted_instance is first.checkpoint is None

    for target in first.targets:
        assert tuple(metric.metric for metric in target.metrics) == METRIC_ORDER
        assert tuple(metric.value for metric in target.metrics) == (0.0, 0.0, 1.0, 0.0)


def test_prediction_row_permutation_preserves_scientific_metrics(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
    tmp_path: Path,
) -> None:
    rows = tuple(
        PredictionRow(row.row_id, *(float(row.targets[target]) for target in TARGETS))
        for row in evaluation_files[4]
    )
    permuted_path = tmp_path / "permuted.jsonl"
    permuted_path.write_bytes(canonical_prediction_jsonl(tuple(reversed(rows))))
    canonical = _evaluate(evaluation_files)
    permuted = _evaluate(evaluation_files, predictions_path=permuted_path)
    assert canonical.targets == permuted.targets
    assert (
        canonical.prediction_artifact.content_sha256 != permuted.prediction_artifact.content_sha256
    )
    assert canonical.digest != permuted.digest


@pytest.mark.parametrize("alignment", ("missing", "extra"))
def test_prediction_row_ids_must_match_exactly(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
    tmp_path: Path,
    alignment: str,
) -> None:
    rows = tuple(
        PredictionRow(row.row_id, *(float(row.targets[target]) for target in TARGETS))
        for row in evaluation_files[4]
    )
    if alignment == "missing":
        rows = rows[1:]
    else:
        rows = (*rows, PredictionRow("unexpected-row", 0.0, 0.0, 0.0))
    predictions_path = tmp_path / f"{alignment}.jsonl"
    predictions_path.write_bytes(canonical_prediction_jsonl(rows))
    expected = "missing=.*entity-" if alignment == "missing" else "extra=.*unexpected-row"
    with pytest.raises(ValueError, match=expected):
        _evaluate(evaluation_files, predictions_path=predictions_path)


@pytest.mark.parametrize(
    ("binding_change", "message"),
    (
        ("realization_digest", "dataset realization identity/digest"),
        ("validation_sha256", "validation artifact SHA"),
        ("validation_rows", "validation split row count"),
    ),
)
def test_dataset_binding_rejects_wrong_digest_sha_and_row_count(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
    binding_change: str,
    message: str,
) -> None:
    _, _, _, binding, _ = evaluation_files
    value = getattr(binding, binding_change)
    if binding_change == "realization_digest":
        changed = replace(binding, realization_digest="sha256:" + "0" * 64)
    elif binding_change == "validation_sha256":
        changed = replace(binding, validation_sha256="0" * 64)
    else:
        changed = replace(binding, validation_rows=value + 1)
    with pytest.raises(ValueError, match=message):
        _evaluate(evaluation_files, binding=changed)


def test_benchmark_binding_rejects_wrong_digest(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
) -> None:
    assert PUBLIC_NATIVE_SPEC.semantic_identity is not None
    wrong_spec = replace(
        PUBLIC_NATIVE_SPEC,
        semantic_identity=replace(
            PUBLIC_NATIVE_SPEC.semantic_identity,
            evaluation_id="psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f",
        ),
    )
    with pytest.raises(ValueError, match="BenchmarkSpec identity/digest"):
        _evaluate(evaluation_files, benchmark_spec=wrong_spec)


def test_cli_emits_canonical_result_and_metric_table_for_small_fixture(
    evaluation_files: tuple[
        Path, Path, Path, evaluator.ValidationBinding, tuple[PublicForecastRow, ...]
    ],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    validation_path, predictions_path, manifest_path, binding, _ = evaluation_files
    monkeypatch.setattr(evaluator, "CANONICAL_VALIDATION", binding)
    monkeypatch.setattr(evaluator, "MANIFEST_PATH", manifest_path)
    assert (
        evaluator.main(
            [
                "--validation",
                str(validation_path),
                "--predictions",
                str(predictions_path),
                "--model-id",
                MODEL_ID,
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert value["evaluation_id"] == evaluator.EVALUATION_ID
    assert "RMSE (kg)" in captured.err
    assert "SRE(ddof=0)" in captured.err


def test_missing_canonical_validation_points_to_res_270_regeneration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="RES-270.*uv run --locked python -m"):
        evaluator._load_truth(
            tmp_path / "absent-validation.jsonl",
            tmp_path / "manifest.json",
            evaluator.CANONICAL_VALIDATION,
        )
