"""Reproduce the RES-283 public-native ranking and historical evidence analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..artifacts.hashes import sha256_record
from ..contracts.comparability import (
    ComparisonProfile,
    EstimandKind,
    SupportAlignment,
    assess_comparability,
)

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = Path("results/audits/res283-analysis/analysis-config.json")
OUTPUT_DIR = Path("results/audits/res283-analysis")
IID_SLUG = "iid_latent_capacity_change_with_transient_expression_forecasting"
TARGETS = (
    "squat_delta_capacity_kg",
    "bench_press_delta_capacity_kg",
    "deadlift_delta_capacity_kg",
)
METRICS = ("RMSE", "MAE", "R²", "SRE(ddof=0)")
METRIC_FIELDS = {
    "RMSE": "rmse_kg",
    "MAE": "mae_kg",
    "R²": "r2",
    "SRE(ddof=0)": "sre_ddof0",
}
METRIC_DIRECTIONS = {"RMSE": "lower", "MAE": "lower", "R²": "higher", "SRE(ddof=0)": "lower"}


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    family: str
    seed: str
    role: str
    model_id: str
    fitted_instance_id: str
    evaluation_result_id: str
    evaluation_sample_count: int
    prediction_artifact_identity: str
    evaluation_path: str
    prediction_path: str
    fitted_instance_path: str
    evaluation_sha256: str
    prediction_sha256: str
    fitted_instance_sha256: str
    metrics: dict[str, dict[str, float]]
    benchmark_id: str
    dataset_realization_id: str
    evaluation_id: str
    metric_ids: tuple[str, ...]
    rights: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _csv_bytes(fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _read_json(root: Path, relative_path: str) -> dict[str, Any]:
    value = json.loads((root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {relative_path}")
    return value


def _verify_references(root: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    for entry in entries:
        path = str(entry["path"])
        expected = str(entry["sha256"]).removeprefix("sha256:")
        actual = _sha256(root / path)
        if actual != expected:
            raise ValueError(f"checksum mismatch for {path}: expected {expected}, got {actual}")


def rank_values(values: Sequence[float], direction: str) -> tuple[float, ...]:
    """Return average ranks, with rank one best and exact-value ties preserved."""
    if not values or direction not in {"lower", "higher"}:
        raise ValueError("ranking needs finite values and a declared direction")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("ranking rejects non-finite metric values")
    ordered = sorted(enumerate(values), key=lambda pair: pair[1], reverse=direction == "higher")
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for index, _ in ordered[start:end]:
            ranks[index] = average_rank
        start = end
    return tuple(ranks)


def numerical_comparison_status(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[str, tuple[str, ...]]:
    """Classify two candidate populations before calculating a comparison."""
    semantic_fields = (
        "benchmark_id",
        "world_id",
        "dataset_spec_id",
        "dataset_realization_id",
        "evaluation_id",
        "task_id",
        "qoi_id",
        "metric_ids",
        "information_boundary",
    )
    missing = [
        field
        for field in (*semantic_fields, "row_ids")
        if field not in left or field not in right or left[field] is None or right[field] is None
    ]
    if missing:
        return "UNSUPPORTED_BY_EVIDENCE", tuple(missing)
    failed = [field for field in semantic_fields if left[field] != right[field]]
    if left["row_ids"] != right["row_ids"]:
        failed.append("matched_prediction_row_support")
    if failed:
        return "REJECTED_FOR_NUMERICAL_COMPARISON", tuple(failed)
    return "ADMISSIBLE", ()


def validate_model_identity(
    result: Mapping[str, Any],
    table_row: Mapping[str, Any],
    *,
    result_id: str,
    prediction_identity: str,
) -> None:
    """Keep the result, fitted model, prediction, and frozen frontier row bound together."""
    fitted = result.get("fitted_instance")
    prediction = result.get("prediction_artifact")
    model = result.get("model")
    if not all(isinstance(item, Mapping) for item in (fitted, prediction, model)):
        raise ValueError(
            "EvaluationResult is missing model, fitted-instance, or prediction identity"
        )
    fitted_record = cast(Mapping[str, Any], fitted)
    model_record = cast(Mapping[str, Any], model)
    expected = {
        "evaluation_result_id": result_id,
        "model_id": model_record["model_id"],
        "fitted_instance_id": fitted_record["fitted_instance_id"],
        "prediction_artifact_identity": prediction_identity,
    }
    for field, value in expected.items():
        if str(table_row.get(field)) != str(value):
            raise ValueError(f"frontier {field} does not match its EvaluationResult")


def validate_fitted_artifact(
    result: Mapping[str, Any],
    fitted_artifact: Mapping[str, Any],
    *,
    file_sha256: str,
    seed: str,
) -> None:
    """Verify the saved fit or ensemble manifest against the EvaluationResult identity."""
    fitted = result.get("fitted_instance")
    model = result.get("model")
    protocol = result.get("training_protocol")
    prediction = result.get("prediction_artifact")
    if not all(isinstance(item, Mapping) for item in (fitted, model, protocol, prediction)):
        raise ValueError("EvaluationResult lacks a fitted, model, protocol, or prediction identity")
    fitted_record = cast(Mapping[str, Any], fitted)
    model_record = cast(Mapping[str, Any], model)
    protocol_record = cast(Mapping[str, Any], protocol)
    if fitted_artifact.get("model_id") != model_record["model_id"]:
        raise ValueError("fitted artifact model ID does not match the EvaluationResult")
    if fitted_artifact.get("dataset_realization_id") != result["dataset_realization_id"]:
        raise ValueError("fitted artifact DatasetRealization does not match the EvaluationResult")
    protocol_id = str(protocol_record["training_protocol_id"])
    actual_protocol_id = str(fitted_artifact.get("training_protocol_id", ""))
    if protocol_id != actual_protocol_id:
        raise ValueError("fitted artifact training protocol does not match the EvaluationResult")

    expected_id = str(fitted_record["fitted_instance_id"])
    expected_digest = str(fitted_record["content_sha256"])
    is_ensemble = "ensemble_fitted_instance_id" in fitted_artifact
    if is_ensemble:
        if seed != "ensemble":
            raise ValueError("ensemble fitted identity is attached to a non-ensemble candidate")
        actual_id = str(fitted_artifact["ensemble_fitted_instance_id"])
        actual_digest = str(fitted_artifact["ensemble_fitted_instance_digest"])
        if actual_id != expected_id or actual_digest != expected_digest:
            raise ValueError(
                "ensemble fitted identity or digest does not match the EvaluationResult"
            )
    elif "fitted_instance_id" in fitted_artifact:
        actual_id = str(fitted_artifact["fitted_instance_id"])
        actual_digest = str(fitted_artifact["fitted_instance_digest"])
        if actual_id != expected_id or actual_digest != expected_digest:
            raise ValueError(
                "fitted instance identity or digest does not match the EvaluationResult"
            )
        if str(fitted_artifact.get("training_seed", "")) != seed:
            raise ValueError("fitted instance training seed does not match its candidate label")
    else:
        if expected_digest != f"sha256:{file_sha256}" or not expected_id.endswith(
            "@" + expected_digest
        ):
            raise ValueError(
                "standardized fitted-instance identity does not match its saved artifact hash"
            )
        if str(fitted_artifact.get("seed", "")) != seed:
            raise ValueError("standardized fitted-instance seed does not match its candidate label")


def align_rows(
    validation_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
    *,
    target_names: Sequence[str] = TARGETS,
) -> tuple[list[str], list[str], dict[str, list[float]], dict[str, list[float]]]:
    """Pair rows by row ID, and return entity keys so resampling keeps all rows together."""
    truth_by_id: dict[str, Mapping[str, Any]] = {}
    entity_by_id: dict[str, str] = {}
    for row in validation_rows:
        row_id = str(row.get("row_id", ""))
        inputs = row.get("inputs")
        if not row_id or row_id in truth_by_id or not isinstance(inputs, Mapping):
            raise ValueError("validation rows need unique row IDs and participant inputs")
        entity_id = str(inputs.get("entity_id", ""))
        targets = row.get("targets")
        if not entity_id or not isinstance(targets, Mapping):
            raise ValueError("validation rows need an entity ID and target values")
        if any(target not in targets for target in target_names):
            raise ValueError("validation row is missing a declared target")
        truth_by_id[row_id] = row
        entity_by_id[row_id] = entity_id

    prediction_by_id: dict[str, Mapping[str, Any]] = {}
    for row in prediction_rows:
        row_id = str(row.get("row_id", ""))
        if not row_id or row_id in prediction_by_id:
            raise ValueError("prediction rows need unique row IDs")
        if any(target not in row for target in target_names):
            raise ValueError("prediction row is missing a declared target")
        prediction_by_id[row_id] = row
    if set(prediction_by_id) != set(truth_by_id):
        raise ValueError("prediction and validation row IDs do not have exact paired support")

    row_ids = sorted(truth_by_id)
    entity_ids = [entity_by_id[row_id] for row_id in row_ids]
    truth = {
        target: [float(truth_by_id[row_id]["targets"][target]) for row_id in row_ids]
        for target in target_names
    }
    predictions = {
        target: [float(prediction_by_id[row_id][target]) for row_id in row_ids]
        for target in target_names
    }
    values = [*truth.values(), *predictions.values()]
    if any(not math.isfinite(value) for vector in values for value in vector):
        raise ValueError("paired rows contain a non-finite target or prediction")
    return row_ids, entity_ids, truth, predictions


def seed_interpretation(
    family: str,
    prediction_digests: Sequence[str],
    stochastic_families: Sequence[str],
    deterministic_families: Sequence[str],
) -> str:
    if len(prediction_digests) != 3:
        raise ValueError("fit-seed diagnostics require the three frozen seed labels")
    distinct = len(set(prediction_digests))
    if family in deterministic_families:
        if distinct != 1:
            raise ValueError(
                f"deterministic family {family} changed predictions across seed labels"
            )
        return "DETERMINISTIC_REPEATS_NOT_INDEPENDENT_FIT_REPLICATIONS"
    if family in stochastic_families:
        if distinct != 3:
            raise ValueError(f"stochastic family {family} does not have three distinct predictions")
        return "THREE_DISTINCT_FIT_SEEDS_DESCRIPTIVE_ONLY"
    raise ValueError(f"no predeclared seed interpretation for {family}")


def _target_metrics(result: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for target_record in result["targets"]:
        target = str(target_record["target"])
        output[target] = {}
        for metric in target_record["metrics"]:
            if metric["status"] != "COMPUTED" or metric["value"] is None:
                raise ValueError(f"missing computed metric {metric['metric']} for {target}")
            output[target][str(metric["metric"])] = float(metric["value"])
    return output


def _family_map(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    comparator = _read_json(root, "artifacts/registries/public-native-comparator-registry.json")
    model_to_family = {
        str(item["model_id"]): str(item["method"]) for item in comparator["comparators"]
    }
    model_to_slug = {str(item["model_id"]): str(item["slug"]) for item in comparator["comparators"]}
    expert = _read_json(root, "results/manifests/public-native-temporal-expert.json")
    model_id = str(expert["scientific_identity"]["model_id"])
    model_to_family[model_id] = "public-native-temporal-expert"
    model_to_slug[model_id] = "public-native-temporal-expert"
    return model_to_family, model_to_slug


def _native_panel_contract(root: Path) -> dict[str, Any]:
    registry = _read_json(root, "artifacts/registries/benchmark-registry.json")
    benchmark = next(
        item
        for item in registry["benchmarks"]
        if item["slug"] == IID_SLUG and item["version"] == "1.0.0"
    )
    semantic = benchmark["semantic_identity_payload"]
    evaluation = registry["public_native_evaluation"]
    realization = _read_json(
        root,
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
    )
    m4_manifest = _read_json(root, "results/manifests/public-native-comparator-suite.json")
    validation_split = next(
        item
        for item in realization["split_identities"]
        if item["purpose"] == "same-law held-out validation"
    )
    metric_ids = tuple(str(item["metric_id"]) for item in evaluation["metric_identities"])
    metric_names = {str(item["metric"]) for item in evaluation["metric_identities"]}
    if (
        semantic["dataset_spec_id"] != realization["dataset_spec_id"]
        or semantic["evaluation_id"] != evaluation["evaluation_id"]
        or set(metric_names) != set(METRICS)
    ):
        raise ValueError(
            "benchmark registry, DatasetRealization, and public evaluation identities disagree"
        )
    return {
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_spec_digest": benchmark["semantic_digest"],
        "dataset_spec_id": semantic["dataset_spec_id"],
        "dataset_realization_id": realization["identity_id"],
        "dataset_realization_digest": realization["realization_digest"],
        "evaluation_id": evaluation["evaluation_id"],
        "world_id": semantic["world_id"]["id"],
        "task_id": semantic["task_id"],
        "qoi_ids": tuple(semantic["qoi_ids"]),
        "metric_ids": metric_ids,
        "information_boundary": semantic["prediction_information_boundary"],
        "validation_split_id": validation_split["split_id"],
        "validation_row_count": validation_split["row_count"],
        "validation_entity_count": validation_split["entity_count"],
        "model_selection_split_id": m4_manifest["fit_selection_split"]["split_id"],
    }


def require_comparable_native_panel(
    contract: Mapping[str, Any], target_records: Sequence[Mapping[str, Any]]
) -> None:
    profile = ComparisonProfile(
        world_id=str(contract["world_id"]),
        qoi_ids=tuple(str(item) for item in contract["qoi_ids"]),
        output_fields=tuple(
            (str(item["target"]), str(item["target_unit"])) for item in target_records
        ),
        metric_ids=tuple(str(item) for item in contract["metric_ids"]),
        evaluation_id=str(contract["evaluation_id"]),
        estimand=EstimandKind.LATENT_CAPACITY_CHANGE,
    )
    decision = assess_comparability(profile, profile, support_alignment=SupportAlignment.MATCHED)
    if not decision.direct_performance_comparable:
        raise ValueError(
            f"existing comparability contract rejects the IID model panel: {decision.rationale}"
        )


def _load_candidates(root: Path, contract: Mapping[str, Any]) -> list[Candidate]:
    table_path = root / "results/tables/public-native-comparator-frontier.csv"
    with table_path.open(newline="", encoding="utf-8") as stream:
        table_rows = list(csv.DictReader(stream))
    table_by_result_target = {
        (row["evaluation_result_id"], row["target"]): row for row in table_rows
    }
    if len(table_rows) != 66 or len(table_by_result_target) != len(table_rows):
        raise ValueError("the frozen comparator frontier must contain 66 unique result-target rows")

    model_to_family, model_to_slug = _family_map(root)
    eval_root = root / "results/benchmarks" / IID_SLUG
    eval_paths = sorted(
        eval_root.glob("public-native-comparator-suite/**/*.evaluation-result.json")
    )
    eval_paths += sorted(eval_root.glob("public-native-temporal-expert/*.evaluation-result.json"))
    candidates: list[Candidate] = []
    seen_result_ids: set[str] = set()
    for path in eval_paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        result = document.get("result", document)
        for field in (
            "benchmark_id",
            "benchmark_spec_digest",
            "dataset_realization_id",
            "dataset_realization_digest",
            "evaluation_id",
        ):
            if result[field] != contract[field]:
                raise ValueError(
                    f"EvaluationResult {field} differs from the frozen native contract"
                )
        result_metric_ids = tuple(str(item["metric_id"]) for item in result["metric_identities"])
        if set(result_metric_ids) != set(contract["metric_ids"]):
            raise ValueError(
                "EvaluationResult metric identities differ from the canonical evaluation"
            )
        sample_counts = {
            int(metric["sample_count"])
            for target_record in result["targets"]
            for metric in target_record["metrics"]
        }
        if sample_counts != {int(result["prediction_artifact"].get("row_count", -1))}:
            raise ValueError("EvaluationResult sample count differs from its prediction artifact")
        result_id = f"psr:evaluation-result@{sha256_record(result)}"
        if document.get("result_id") and document["result_id"] != result_id:
            raise ValueError(f"EvaluationResult identity mismatch: {path.relative_to(root)}")
        if result_id in seen_result_ids:
            raise ValueError(f"duplicate EvaluationResult identity: {result_id}")
        seen_result_ids.add(result_id)

        model = result["model"]
        model_id = str(model["model_id"])
        family = model_to_family.get(model_id)
        if family is None:
            raise ValueError(f"unregistered model family for {model_id}")
        prediction = result["prediction_artifact"]
        prediction_identity = (
            f"psr:prediction-artifact:{prediction['artifact_id']}@{sha256_record(prediction)}"
        )
        seed_match = re.search(r"(?:seed-)?(\d{6})|ensemble", path.name)
        if seed_match is None:
            raise ValueError(f"cannot read fit seed from {path.name}")
        seed = "ensemble" if seed_match.group(0) == "ensemble" else seed_match.group(1)
        role = "ensemble" if seed == "ensemble" else "fit_seed"
        candidate_id = f"{family}:{seed}"
        fitted_instance = result["fitted_instance"]
        fitted_instance_id = str(fitted_instance["fitted_instance_id"])
        pred_path = path.with_name(
            path.name.replace(".evaluation-result.json", ".predictions.jsonl")
        )
        if not pred_path.is_file():
            raise ValueError(f"missing paired prediction artifact for {path.name}")
        if prediction.get("content_sha256") != f"sha256:{_sha256(pred_path)}":
            raise ValueError(f"prediction content hash mismatch: {pred_path.relative_to(root)}")
        if prediction.get("row_count") != 3072:
            raise ValueError("frozen public-native prediction row count is not 3072")
        for field in (
            "benchmark_id",
            "benchmark_spec_digest",
            "dataset_realization_id",
            "dataset_realization_digest",
        ):
            if prediction.get(field) != result.get(field):
                raise ValueError(f"prediction {field} does not match its EvaluationResult")
        if prediction.get("model_id") != model_id:
            raise ValueError("prediction model ID does not match its EvaluationResult")

        fitted_stub = "ensemble" if seed == "ensemble" else f"seed-{seed}"
        if family == "public-native-temporal-expert":
            fit_name = (
                "ensemble-manifest.json"
                if seed == "ensemble"
                else f"{fitted_stub}.fitted-instance.json"
            )
            fit_path = root / "models/checkpoint-manifests/public-native-temporal-expert" / fit_name
        else:
            fit_name = f"{fitted_stub}.fitted-instance.json"
            fit_path = (
                root
                / "models/fitted-instances/public-native-comparator-suite"
                / model_to_slug[model_id]
                / fit_name
            )
        rights_metadata = prediction.get("rights", {})
        rights = (
            "; ".join(
                str(rights_metadata.get(key) or "")
                for key in ("license_expression", "redistribution_status")
                if rights_metadata.get(key)
            )
            or "Rights metadata not stated in prediction artifact."
        )
        if not fit_path.is_file():
            raise ValueError(f"missing fitted-instance artifact: {fit_path.relative_to(root)}")
        fitted_sha256 = _sha256(fit_path)
        validate_fitted_artifact(
            result,
            json.loads(fit_path.read_text(encoding="utf-8")),
            file_sha256=fitted_sha256,
            seed=seed,
        )

        target_metrics = _target_metrics(result)
        if set(target_metrics) != set(TARGETS):
            raise ValueError(f"unexpected target set in {path.relative_to(root)}")
        for target in TARGETS:
            table_row = table_by_result_target.get((result_id, target))
            if table_row is None:
                raise ValueError(f"frontier is missing {result_id} / {target}")
            validate_model_identity(
                result,
                table_row,
                result_id=result_id,
                prediction_identity=prediction_identity,
            )
            if table_row["model_id"] != model_id or table_row["seed"] != seed:
                raise ValueError("frontier family or seed does not match the EvaluationResult")
            for metric, field in METRIC_FIELDS.items():
                if not math.isclose(
                    float(table_row[field]),
                    target_metrics[target][metric],
                    rel_tol=0,
                    abs_tol=1e-12,
                ):
                    raise ValueError(f"frontier metric differs from canonical result: {metric}")

        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                family=family,
                seed=seed,
                role=role,
                model_id=model_id,
                fitted_instance_id=fitted_instance_id,
                evaluation_result_id=result_id,
                evaluation_sample_count=next(iter(sample_counts)),
                prediction_artifact_identity=prediction_identity,
                evaluation_path=path.relative_to(root).as_posix(),
                prediction_path=pred_path.relative_to(root).as_posix(),
                fitted_instance_path=fit_path.relative_to(root).as_posix(),
                evaluation_sha256=_sha256(path),
                prediction_sha256=_sha256(pred_path),
                fitted_instance_sha256=fitted_sha256,
                metrics=target_metrics,
                benchmark_id=str(result["benchmark_id"]),
                dataset_realization_id=str(result["dataset_realization_id"]),
                evaluation_id=str(result["evaluation_id"]),
                metric_ids=tuple(str(item["metric_id"]) for item in result["metric_identities"]),
                rights=rights,
            )
        )
    if len(candidates) != 22:
        raise ValueError(f"expected 22 saved candidates, found {len(candidates)}")
    require_complete_result_targets(
        [
            (candidate.evaluation_result_id, target)
            for candidate in candidates
            for target in TARGETS
        ],
        set(table_by_result_target),
    )
    return sorted(candidates, key=lambda item: (item.family, item.seed))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _load_prediction_row_ids(root: Path, candidates: Sequence[Candidate]) -> list[str]:
    shared_row_ids: list[str] | None = None
    for candidate in candidates:
        row_ids: list[str] = []
        seen: set[str] = set()
        for row in _read_jsonl(root / candidate.prediction_path):
            row_id = str(row.get("row_id", ""))
            if not row_id or row_id in seen:
                raise ValueError(
                    f"prediction row IDs are missing or duplicated in {candidate.prediction_path}"
                )
            if any(target not in row for target in TARGETS):
                raise ValueError(f"prediction target is missing in {candidate.prediction_path}")
            values = [float(row[target]) for target in TARGETS]
            if any(not math.isfinite(value) for value in values):
                raise ValueError(
                    f"prediction contains a non-finite value in {candidate.prediction_path}"
                )
            seen.add(row_id)
            row_ids.append(row_id)
        current_row_ids = sorted(row_ids)
        if len(current_row_ids) != candidate.evaluation_sample_count:
            raise ValueError(
                "prediction row count differs from its canonical EvaluationResult sample count"
            )
        if shared_row_ids is None:
            shared_row_ids = current_row_ids
        elif current_row_ids != shared_row_ids:
            raise ValueError("candidate predictions do not share exact paired row-ID support")
    if shared_row_ids is None:
        raise ValueError("the frozen IID prediction panel is missing")
    return shared_row_ids


def _point_ranks(candidates: Sequence[Candidate]) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for target in TARGETS:
        output[target] = {}
        for metric in METRICS:
            ranks = rank_values(
                [candidate.metrics[target][metric] for candidate in candidates],
                METRIC_DIRECTIONS[metric],
            )
            output[target][metric] = {
                candidate.candidate_id: rank
                for candidate, rank in zip(candidates, ranks, strict=True)
            }
    return output


def _ranking_rows(
    candidates: Sequence[Candidate], row_ids: Sequence[str], ranks: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                ranks[target]["RMSE"][candidate.candidate_id],
                candidate.candidate_id,
            ),
        )
        for candidate in ordered:
            row: dict[str, Any] = {
                "target": target,
                "prediction_row_keys": len(row_ids),
                "canonical_evaluation_sample_count": candidate.evaluation_sample_count,
                "candidate_id": candidate.candidate_id,
                "model_family": candidate.family,
                "candidate_role": candidate.role,
                "fit_seed": candidate.seed,
                "model_id": candidate.model_id,
                "fitted_instance_id": candidate.fitted_instance_id,
                "evaluation_result_id": candidate.evaluation_result_id,
                "prediction_artifact_identity": candidate.prediction_artifact_identity,
                "evaluation_result_sha256": f"sha256:{candidate.evaluation_sha256}",
                "prediction_artifact_sha256": f"sha256:{candidate.prediction_sha256}",
                "fitted_identity_artifact_sha256": f"sha256:{candidate.fitted_instance_sha256}",
                "within_version_comparison_status": "ADMISSIBLE",
            }
            for metric in METRICS:
                row[metric] = candidate.metrics[target][metric]
                row[f"{metric}_rank"] = ranks[target][metric][candidate.candidate_id]
            rows.append(row)
    return rows


def _seed_panel_ranks(
    candidates: Sequence[Candidate],
) -> tuple[tuple[str, ...], tuple[str, ...], dict[tuple[str, str, str], dict[str, float]]]:
    seed_candidates: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.role == "fit_seed":
            seed_candidates[candidate.seed].append(candidate)
    seeds = tuple(sorted(seed_candidates))
    families = tuple(
        sorted({candidate.family for values in seed_candidates.values() for candidate in values})
    )
    if len(seeds) != 3 or not families:
        raise ValueError("fit-seed ranking requires three saved seed panels")
    output: dict[tuple[str, str, str], dict[str, float]] = {}
    for seed in seeds:
        panel = seed_candidates[seed]
        by_family = {candidate.family: candidate for candidate in panel}
        if len(by_family) != len(panel) or set(by_family) != set(families):
            raise ValueError("every fit seed must contain exactly one result per model family")
        for target in TARGETS:
            for metric in METRICS:
                ranks = rank_values(
                    [by_family[family].metrics[target][metric] for family in families],
                    METRIC_DIRECTIONS[metric],
                )
                output[(target, metric, seed)] = dict(zip(families, ranks, strict=True))
    return seeds, families, output


def _fit_seed_rows(
    candidates: Sequence[Candidate], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    seeds, families, panel_ranks = _seed_panel_ranks(candidates)
    expected_families = set(config["candidate_policy"]["families"])
    if set(families) != expected_families:
        raise ValueError("fit-seed panel families differ from the frozen analysis configuration")
    seed_config = config["candidate_policy"]["seed_design"]
    stochastic = seed_config["stochastic_fit_families"]
    deterministic = seed_config["deterministic_fit_families"]
    by_family: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.role == "fit_seed":
            by_family[candidate.family].append(candidate)
    rows: list[dict[str, Any]] = []
    for family, members in sorted(by_family.items()):
        members.sort(key=lambda item: item.seed)
        interpretation = seed_interpretation(
            family,
            [candidate.prediction_sha256 for candidate in members],
            stochastic,
            deterministic,
        )
        for target in TARGETS:
            for metric in METRICS:
                seed_ranks = [panel_ranks[(target, metric, seed)][family] for seed in seeds]
                rows.append(
                    {
                        "model_family": family,
                        "target": target,
                        "metric": metric,
                        "fit_seed_count": len(members),
                        "comparison_panel_family_count": len(families),
                        "seed_candidate_ids": json.dumps(
                            {candidate.seed: candidate.candidate_id for candidate in members},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "seed_ranks": json.dumps(
                            dict(zip(seeds, seed_ranks, strict=True)),
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "rank_min": min(seed_ranks),
                        "rank_max": max(seed_ranks),
                        "rank_range": max(seed_ranks) - min(seed_ranks),
                        "rank_sd_ddof0": math.sqrt(
                            sum(
                                (rank - sum(seed_ranks) / len(seed_ranks)) ** 2
                                for rank in seed_ranks
                            )
                            / len(seed_ranks)
                        ),
                        "distinct_ranks": len(set(seed_ranks)),
                        "distinct_prediction_artifacts": len(
                            {candidate.prediction_artifact_identity for candidate in members}
                        ),
                        "seed_interpretation": interpretation,
                        "inference_status": "INCONCLUSIVE_NO_PREDECLARED_PRACTICAL_THRESHOLD",
                    }
                )
    return rows


def _fit_seed_pairwise_rows(candidates: Sequence[Candidate]) -> list[dict[str, Any]]:
    seeds, families, panel_ranks = _seed_panel_ranks(candidates)
    rows: list[dict[str, Any]] = []
    by_seed_family = {
        (candidate.seed, candidate.family): candidate.candidate_id
        for candidate in candidates
        if candidate.role == "fit_seed"
    }
    for target in TARGETS:
        for metric in METRICS:
            for family_a, family_b in itertools.combinations(families, 2):
                relations = [
                    _relation(
                        panel_ranks[(target, metric, seed)][family_a],
                        panel_ranks[(target, metric, seed)][family_b],
                    )
                    for seed in seeds
                ]
                pair_comparisons = [
                    (left, right)
                    for left, right in itertools.combinations(relations, 2)
                    if left != 0 and right != 0
                ]
                rows.append(
                    {
                        "target": target,
                        "metric": metric,
                        "model_family_a": family_a,
                        "model_family_b": family_b,
                        "candidate_ids_a": json.dumps(
                            {seed: by_seed_family[(seed, family_a)] for seed in seeds},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "candidate_ids_b": json.dumps(
                            {seed: by_seed_family[(seed, family_b)] for seed in seeds},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "family_a_ranks_by_seed": json.dumps(
                            {seed: panel_ranks[(target, metric, seed)][family_a] for seed in seeds},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "family_b_ranks_by_seed": json.dumps(
                            {seed: panel_ranks[(target, metric, seed)][family_b] for seed in seeds},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "ordered_seed_pairs": len(pair_comparisons),
                        "pairwise_seed_rank_reversals": sum(
                            relation_a != relation_b for relation_a, relation_b in pair_comparisons
                        ),
                        "tied_seed_labels": ",".join(
                            seed
                            for seed, relation in zip(seeds, relations, strict=True)
                            if relation == 0
                        ),
                        "inference_status": "INCONCLUSIVE_NO_PREDECLARED_PRACTICAL_THRESHOLD",
                    }
                )
    return rows


def _pairwise_ranking_rows(
    candidates: Sequence[Candidate], ranks: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    details: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    metric_pairs = list(itertools.combinations(METRICS, 2))
    for target in TARGETS:
        for left, right in itertools.combinations(candidates, 2):
            row: dict[str, Any] = {
                "target": target,
                "candidate_a": left.candidate_id,
                "candidate_b": right.candidate_id,
            }
            reversed_pairs: list[str] = []
            for metric in METRICS:
                row[f"{metric}_rank_a"] = ranks[target][metric][left.candidate_id]
                row[f"{metric}_rank_b"] = ranks[target][metric][right.candidate_id]
            for metric_a, metric_b in metric_pairs:
                rank_a = ranks[target][metric_a]
                rank_b = ranks[target][metric_b]
                a_relation = _relation(rank_a[left.candidate_id], rank_a[right.candidate_id])
                b_relation = _relation(rank_b[left.candidate_id], rank_b[right.candidate_id])
                row[f"{metric_a}_vs_{metric_b}_relation"] = (
                    "TIE"
                    if a_relation == 0 or b_relation == 0
                    else "SAME_ORDER"
                    if a_relation == b_relation
                    else "REVERSAL"
                )
                if a_relation != 0 and b_relation != 0 and a_relation != b_relation:
                    reversed_pairs.append(f"{metric_a} vs {metric_b}")
            row["reversed_metric_pairs"] = json.dumps(reversed_pairs, separators=(",", ":"))
            details.append(row)
        for metric_a, metric_b in metric_pairs:
            pair_count = reversal_count = tie_a = tie_b = 0
            for left, right in itertools.combinations(candidates, 2):
                a = _relation(
                    ranks[target][metric_a][left.candidate_id],
                    ranks[target][metric_a][right.candidate_id],
                )
                b = _relation(
                    ranks[target][metric_b][left.candidate_id],
                    ranks[target][metric_b][right.candidate_id],
                )
                tie_a += a == 0
                tie_b += b == 0
                if a != 0 and b != 0:
                    pair_count += 1
                    reversal_count += a != b
            summary.append(
                {
                    "target": target,
                    "metric_a": metric_a,
                    "metric_b": metric_b,
                    "candidate_pairs": math.comb(len(candidates), 2),
                    "pairs_ordered_on_both_metrics": pair_count,
                    "rank_reversals": reversal_count,
                    "ties_on_metric_a": tie_a,
                    "ties_on_metric_b": tie_b,
                    "interpretation": "Descriptive; R² and SRE are monotone transforms of RMSE within a fixed target population.",
                }
            )
    return details, summary


def _relation(rank_a: float, rank_b: float) -> int:
    return (rank_a > rank_b) - (rank_a < rank_b)


def require_complete_result_targets(
    actual: Sequence[tuple[str, str]], expected: set[tuple[str, str]]
) -> None:
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        unexpected = sorted(set(actual) - expected)
        raise ValueError(
            f"missing or unexpected model results: missing={missing}, unexpected={unexpected}"
        )


def _pareto_rows(candidates: Sequence[Candidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        for candidate in candidates:
            dominated_by: list[str] = []
            for other in candidates:
                if candidate == other:
                    continue
                better_or_equal = all(
                    other.metrics[target][metric] <= candidate.metrics[target][metric]
                    if METRIC_DIRECTIONS[metric] == "lower"
                    else other.metrics[target][metric] >= candidate.metrics[target][metric]
                    for metric in METRICS
                )
                strictly_better = any(
                    other.metrics[target][metric] < candidate.metrics[target][metric]
                    if METRIC_DIRECTIONS[metric] == "lower"
                    else other.metrics[target][metric] > candidate.metrics[target][metric]
                    for metric in METRICS
                )
                if better_or_equal and strictly_better:
                    dominated_by.append(other.candidate_id)
            rows.append(
                {
                    "target": target,
                    "candidate_id": candidate.candidate_id,
                    "model_family": candidate.family,
                    "pareto_front": not dominated_by,
                    "dominated_by_count": len(dominated_by),
                    "dominated_by_candidate_ids": json.dumps(dominated_by, separators=(",", ":")),
                    "rmse_kg": candidate.metrics[target]["RMSE"],
                    "mae_kg": candidate.metrics[target]["MAE"],
                    "r2": candidate.metrics[target]["R²"],
                    "sre_ddof0": candidate.metrics[target]["SRE(ddof=0)"],
                }
            )
    return rows


def _uncertainty_evidence_rows(
    candidates: Sequence[Candidate], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    uncertainty = config["paired_uncertainty"]
    reason = (
        "Tracked public evidence contains paired prediction row IDs and aggregate EvaluationResults, "
        "but not the validation target truth rows or row-to-entity mapping required for paired residuals "
        "and entity-cluster resampling. No data or predictions were regenerated."
    )
    return [
        {
            "target": target,
            "metric": metric,
            "candidate_id": candidate.candidate_id,
            "planned_method": uncertainty["method"],
            "planned_resamples": int(uncertainty["resamples"]),
            "planned_seed": int(uncertainty["seed"]),
            "completed_resamples": 0,
            "status": "UNSUPPORTED_BY_EVIDENCE",
            "inference_status": "INCONCLUSIVE",
            "reason": reason,
        }
        for target in TARGETS
        for metric in METRICS
        for candidate in candidates
    ]


def _version_rows(
    root: Path,
    candidates: Sequence[Candidate],
    row_ids: Sequence[str],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    registry = _read_json(root, "artifacts/registries/benchmark-registry.json")
    worlds = {str(world["slug"]): world for world in registry["worlds"]}
    iid_metric_ids = [
        str(item["metric_id"]) for item in registry["public_native_evaluation"]["metric_identities"]
    ]
    component_ids: dict[tuple[str, str], str] = {}
    for identity, references in registry["component_provenance"]["identity_mapping"].items():
        for component_class, canonical_key in references:
            component_ids[(str(component_class), str(canonical_key))] = str(identity)
    by_family: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_family[candidate.family].append(candidate)
    realization = _read_json(
        root,
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
    )
    m4_manifest = _read_json(root, "results/manifests/public-native-comparator-suite.json")
    selection_split = m4_manifest["fit_selection_split"]
    seed_design = config["candidate_policy"]["seed_design"]
    stochastic_families = seed_design["stochastic_fit_families"]
    deterministic_families = seed_design["deterministic_fit_families"]
    dataset_seeds = "; ".join(f"{item[0]}={item[1]}" for item in realization["seeds"])
    rows: list[dict[str, Any]] = []
    for benchmark in sorted(registry["benchmarks"], key=lambda item: item["slug"]):
        version = f"{benchmark['slug']}@{benchmark['version']}"
        references = {item["component_class"]: item for item in benchmark["component_references"]}
        world_ref = references["WORLD"]
        world = worlds.get(str(world_ref["canonical_key"]), {})
        semantic = benchmark.get("semantic_identity_payload") or {}
        iid = benchmark["slug"] == IID_SLUG
        spec = references["DATASET_SPEC"]
        evaluation = references["EVALUATION"]
        qoi = references["QOI"]
        representation = references["REPRESENTATION"]
        population = references["POPULATION"]
        intervention = references["INTERVENTION_REGIME"]
        observation = references["OBSERVATION_MODEL"]
        semantic_qoi = semantic.get("qoi_ids")
        qoi_identity = (
            semantic_qoi[0]
            if semantic_qoi
            else component_ids.get(("QOI", str(qoi["canonical_key"])), qoi["canonical_key"])
        )
        task_identity = semantic.get("task_id") or component_ids.get(
            ("TASK", str(references["TASK"]["canonical_key"])),
            references["TASK"]["canonical_key"],
        )
        dataset_spec_identity = semantic.get("dataset_spec_id") or component_ids.get(
            ("DATASET_SPEC", str(spec["canonical_key"])), spec["canonical_key"]
        )
        evaluation_identity = semantic.get("evaluation_id") or component_ids.get(
            ("EVALUATION", str(evaluation["canonical_key"])),
            f"Historical reference: {evaluation['canonical_key']}",
        )
        representation_identity = component_ids.get(
            ("REPRESENTATION", str(representation["canonical_key"])),
            representation["canonical_key"],
        )
        observation_identity = component_ids.get(
            ("OBSERVATION_MODEL", str(observation["canonical_key"])),
            observation["canonical_key"] or "UNRESOLVED_BY_EVIDENCE",
        )

        def declared_component(
            semantic_field: str,
            reference: Mapping[str, Any],
            component_class: str,
            semantic_payload: Mapping[str, Any] = semantic,
        ) -> tuple[str, str]:
            value = semantic_payload.get(semantic_field)
            if isinstance(value, Mapping):
                direct_id = value.get("id") or value.get("direct_component_id")
                if direct_id:
                    return str(direct_id), str(value.get("resolution", "DIRECT"))
                system_config_id = value.get("system_config_id")
                if system_config_id:
                    return (
                        f"COMMITTED_BY_SYSTEM_CONFIG:{system_config_id}",
                        "COMMITTED_BY_SYSTEM_CONFIG",
                    )
            canonical_key = reference.get("canonical_key")
            if canonical_key:
                return (
                    component_ids.get((component_class, str(canonical_key)), str(canonical_key)),
                    str(reference["resolution"]),
                )
            return "UNRESOLVED_BY_EVIDENCE", str(reference.get("resolution", "UNRESOLVED"))

        population_identity, population_resolution = declared_component(
            "population_id", population, "POPULATION"
        )
        intervention_identity, intervention_resolution = declared_component(
            "intervention_regime_id", intervention, "INTERVENTION_REGIME"
        )
        visible = (
            json.dumps(semantic.get("prediction_information_boundary"), sort_keys=True)
            if iid
            else f"Declared input family {representation['canonical_key']}; exact historical information boundary unavailable."
        )
        evaluation_description = str(evaluation_identity)
        metric_description = (
            "RMSE↓, MAE↓, R²↑, SRE(ddof=0)↓; all four canonical RES-271 metrics"
            if iid
            else (
                "SRE↓ only; other metric directions and structured EvaluationResults unavailable"
                if "sre" in str(evaluation["canonical_key"]).lower()
                else "Native metric directions and structured EvaluationResults unavailable"
            )
        )
        family_names = (
            list(by_family)
            if iid
            else [
                "public-native-temporal-expert",
                "compact_neural",
                "mechanistic_midpoint",
                "mechanistic_ridge_residual",
                "context_mean",
                "ridge",
                "histogram_boosted_stumps",
            ]
        )
        for family in family_names:
            members = by_family[family] if iid else []
            native_status = "ADMISSIBLE" if iid else "UNSUPPORTED_BY_EVIDENCE"
            if not iid:
                seed_summary = "Historical fit/data/split seed values and seed types are not publicly available."
            elif family in stochastic_families:
                seed_summary = f"3 stochastic fit seeds (383001, 383002, 383003); IID generator seeds: {dataset_seeds}."
            else:
                assert family in deterministic_families
                seed_summary = f"3 deterministic seed-labeled repeats (not independent fits); IID generator seeds: {dataset_seeds}."
            if iid and family == "public-native-temporal-expert":
                seed_summary += (
                    " The ensemble is a separate derived candidate, not a fourth fit seed."
                )
            if iid:
                dataset_split_summary = (
                    "; ".join(
                        f"{item['split_id']}={item['entity_count']} entities/{item['row_count']} rows"
                        for item in realization["split_identities"]
                    )
                    + f"; allocation seed={dict(realization['seeds'])['split_allocation']}"
                )
                model_selection_summary = (
                    f"{selection_split['split_id']} ({selection_split['fit_row_count']} fit rows, "
                    f"{selection_split['selection_row_count']} selection rows, "
                    f"entity_disjoint={selection_split['entity_disjoint']})"
                )
            else:
                dataset_split_summary = "Historical train/selection/evaluation split identities and seeds are not publicly available."
                model_selection_summary = "Historical internal model-selection split identity and grain are not publicly available."
            rows.append(
                {
                    "benchmark_version": version,
                    "benchmark_id": benchmark.get("benchmark_id") or "UNRESOLVED",
                    "task_type": benchmark.get("task_type", "UNRESOLVED"),
                    "task_identity": task_identity,
                    "qoi_identity": qoi_identity,
                    "qoi_reference": qoi["canonical_key"],
                    "target_ontology": benchmark.get("target_ontology", "UNRESOLVED"),
                    "world_identity": world.get(
                        "component_identity_id", world_ref["canonical_key"]
                    ),
                    "world_summary_dgp": world.get(
                        "scientific_summary", "Historical generation details unavailable."
                    ),
                    "data_generating_process": (
                        realization["generator_identity"]
                        if iid
                        else "Historical world description is registry-backed; exact executable DGP and generated rows unavailable."
                    ),
                    "population_identity": population_identity,
                    "population_resolution": population_resolution,
                    "intervention_regime_identity": intervention_identity,
                    "intervention_regime_resolution": intervention_resolution,
                    "observation_model_identity": observation_identity,
                    "representation_identity": representation_identity,
                    "dataset_spec_identity": dataset_spec_identity,
                    "dataset_spec_resolution": spec["resolution"],
                    "dataset_realization_identity": realization["identity_id"]
                    if iid
                    else "UNSUPPORTED_BY_EVIDENCE",
                    "dataset_realization_digest": realization["realization_digest"] if iid else "",
                    "participant_visible_information": visible,
                    "evaluation_identity": evaluation_description,
                    "metric_identity_ids": json.dumps(iid_metric_ids, separators=(",", ":"))
                    if iid
                    else "UNSUPPORTED_BY_EVIDENCE",
                    "metric_direction": metric_description,
                    "model_family": family,
                    "model_family_evidence_status": (
                        "AVAILABLE_PUBLIC_FIT" if iid else "UNSUPPORTED_BY_EVIDENCE"
                    ),
                    "model_id": members[0].model_id if members else "UNSUPPORTED_BY_EVIDENCE",
                    "fitted_instance_ids": json.dumps(
                        [candidate.fitted_instance_id for candidate in members],
                        separators=(",", ":"),
                    ),
                    "prediction_artifact_identities": json.dumps(
                        [candidate.prediction_artifact_identity for candidate in members],
                        separators=(",", ":"),
                    ),
                    "evaluation_result_ids": json.dumps(
                        [candidate.evaluation_result_id for candidate in members],
                        separators=(",", ":"),
                    ),
                    "fit_seed_labels": ",".join(
                        candidate.seed for candidate in members if candidate.role == "fit_seed"
                    ),
                    "seed_role_summary": seed_summary,
                    "dataset_split_design": dataset_split_summary,
                    "model_selection_split": model_selection_summary,
                    "ensemble_present": any(candidate.role == "ensemble" for candidate in members),
                    "candidate_count": len(members),
                    "row_level_matched_evidence": (
                        f"All candidate predictions share {len(row_ids)} unique row_id keys and each canonical EvaluationResult binds {members[0].evaluation_sample_count} rows; "
                        "tracked target truth and row-to-entity mapping are unavailable for paired residual or entity-cluster uncertainty"
                        if iid
                        else "UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions"
                    ),
                    "rights_access_constraints": (
                        "IID data CC-BY-4.0; model prediction rights: "
                        + "; ".join(sorted({candidate.rights for candidate in members}))
                        if iid
                        else "Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable"
                    ),
                    "native_ranking_status": native_status,
                }
            )
    return rows


def _cross_version_rows(root: Path) -> list[dict[str, Any]]:
    path = root / "results/audits/res281-analysis/cross-version-comparability.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        source = list(csv.DictReader(stream))
    registry = _read_json(root, "artifacts/registries/benchmark-registry.json")
    versions = {f"{item['slug']}@{item['version']}" for item in registry["benchmarks"]}
    expected_pairs = {tuple(sorted(pair)) for pair in itertools.combinations(versions, 2)}
    actual_pairs: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for item in source:
        left = item["left_benchmark_version"]
        right = item["right_benchmark_version"]
        left_version, right_version = str(left), str(right)
        actual_pairs.add(
            (left_version, right_version)
            if left_version <= right_version
            else (right_version, left_version)
        )
        decision = item["numerical_comparison_decision"]
        if decision not in {
            "ADMISSIBLE",
            "REJECTED_FOR_NUMERICAL_COMPARISON",
            "UNSUPPORTED_BY_EVIDENCE",
        }:
            raise ValueError(f"unknown RES-281 comparison decision: {decision}")
        checks = json.loads(item["declared_semantic_checks"])
        failed = sorted(name for name, passed in checks.items() if not passed)
        if item["matched_support_and_paired_scores_verified"].lower() != "true":
            missing = [
                "no matched cross-version prediction/evaluation rows establish common support",
                "no paired scores exist for a shared evaluation population",
            ]
            historical_versions = [
                version for version in (left, right) if not version.startswith(IID_SLUG + "@")
            ]
            if historical_versions:
                missing.append(
                    "no public fitted-model/prediction/evaluation panel for: "
                    + ", ".join(historical_versions)
                )
        else:
            missing = []
        if decision != "ADMISSIBLE" and not failed and not missing:
            raise ValueError(
                "rejected RES-281 comparison has no documented semantic or evidence gap"
            )
        output.append(
            {
                "left_benchmark_version": left,
                "right_benchmark_version": right,
                "original_res281_decision": decision,
                "admissibility_classification": decision,
                "declared_semantic_checks": json.dumps(
                    checks, sort_keys=True, separators=(",", ":")
                ),
                "failed_semantic_conditions": ";".join(failed),
                "matched_support_and_paired_scores_verified": item[
                    "matched_support_and_paired_scores_verified"
                ],
                "missing_matched_evidence": "; ".join(missing),
                "rankings_scientifically_identifiable": decision == "ADMISSIBLE",
                "rejection_reasons": item["rejection_reasons"],
            }
        )
    if len(source) != 36 or actual_pairs != expected_pairs:
        raise ValueError("RES-281 matrix is not the complete 36-pair census of nine versions")
    if any(
        row["original_res281_decision"] != "REJECTED_FOR_NUMERICAL_COMPARISON" for row in output
    ):
        raise ValueError("RES-281 is binding: this analysis may not relax a cross-version decision")
    return sorted(
        output, key=lambda item: (item["left_benchmark_version"], item["right_benchmark_version"])
    )


def _source_files(
    root: Path, config: Mapping[str, Any], candidates: Sequence[Candidate]
) -> dict[str, str]:
    paths = {str(path) for path in config["source_artifacts"]}
    paths.add(CONFIG_PATH.as_posix())
    for candidate in candidates:
        paths.update(
            {
                candidate.evaluation_path,
                candidate.prediction_path,
                candidate.fitted_instance_path,
            }
        )
    registered_realization = _read_json(
        root,
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
    )
    if len(registered_realization["artifact_hashes"]) != 2:
        raise ValueError("IID realization manifest does not bind train and validation inputs")
    declared_data_ids = {
        str(item["artifact_id"]) for item in registered_realization["artifact_hashes"]
    }
    if declared_data_ids != {"train", "validation"}:
        raise ValueError("IID DatasetRealization must declare its train and validation artifacts")

    res281_manifest = _read_json(root, "results/audits/res281/audit-results.manifest.json")
    _verify_references(root, res281_manifest["files"])
    analysis_manifest = _read_json(
        root, "results/audits/res281-analysis/analysis-results.manifest.json"
    )
    _verify_references(root, [*analysis_manifest["files"], *analysis_manifest["source_files"]])
    m4_checksums = _read_json(
        root, "results/manifests/public-native-comparator-suite-checksums.json"
    )
    _verify_references(root, m4_checksums["entries"])
    m4_manifest = _read_json(root, "results/manifests/public-native-comparator-suite.json")
    if (
        m4_checksums["run_manifest_sha256"]
        != f"sha256:{_sha256(root / 'results/manifests/public-native-comparator-suite.json')}"
    ):
        raise ValueError("M4 comparator checksum index does not bind its run manifest")
    if m4_manifest["status"] != "PASS":
        raise ValueError("M4 comparator run manifest is not PASS")
    expert_checksums = _read_json(
        root, "results/manifests/public-native-temporal-expert-checksums.json"
    )
    for section in (
        "checkpoint_metadata",
        "copied_artifacts",
        "checkpoint_publication_index",
        "run_manifest",
        "source_inventory",
        "verification_receipt",
    ):
        values = expert_checksums.get(section, [])
        entries = values if isinstance(values, list) else [values]
        _verify_references(
            root, [entry for entry in entries if isinstance(entry, Mapping) and "path" in entry]
        )
    if expert_checksums.get("verification_receipt", {}).get("status") != "PASS":
        raise ValueError("temporal-expert evidence verification receipt is not PASS")
    return {path: _sha256(root / path) for path in sorted(paths)}


def _report_markdown(
    candidates: Sequence[Candidate],
    ranks: Mapping[str, Any],
    fit_rows: Sequence[Mapping[str, Any]],
    fit_seed_pairwise_rows: Sequence[Mapping[str, Any]],
    reversal_summary: Sequence[Mapping[str, Any]],
    pareto_rows: Sequence[Mapping[str, Any]],
    cross_rows: Sequence[Mapping[str, Any]],
    uncertainty_rows: Sequence[Mapping[str, Any]],
    row_ids: Sequence[str],
    analysis_identity: str,
    res281_record: Mapping[str, Any],
    res281_baseline_record: Mapping[str, Any],
) -> str:
    lines = [
        "# RES-283 model-ranking stability and comparability",
        "",
        f"Analysis identity: `{analysis_identity}`.",
        "",
        "## Admissible scope",
        "",
        f"One within-version comparison is admissible: the saved public-native IID model panel under one DatasetRealization and one canonical RES-271 evaluation. It contains {len(candidates)} fitted-instance or ensemble candidates, three target QOIs, and {len(row_ids)} unique prediction row keys. The three public-native fit seeds remain separate. No model was trained and no prediction was regenerated.",
        "",
        "The other eight benchmark versions have no public historical fitted-model panel, row-level predictions, and matching evaluation results. Their within-version rankings are `UNSUPPORTED_BY_EVIDENCE`. All 36 cross-version pairs retain the RES-281 decision `REJECTED_FOR_NUMERICAL_COMPARISON`; no historical rank statistic is calculated.",
        "",
        "The candidate unit is a fitted instance. Temporal-expert seed instances and the separately identified ensemble are distinct candidates. Seed labels on deterministic comparator families are repeated deterministic executions, not independent training replications.",
        "",
        "## Frozen IID target-wise rankings",
        "",
        "Ranks are per target and metric, rank 1 is best, and exact ties receive average ranks. RMSE, MAE, and SRE(ddof=0) minimize; R² maximizes. No scalar or cross-target aggregate ranking is formed.",
        "",
    ]
    for target in TARGETS:
        lines.extend([f"### {target}", ""])
        for metric in METRICS:
            ordered = sorted(
                candidates,
                key=lambda candidate: (
                    ranks[target][metric][candidate.candidate_id],
                    candidate.candidate_id,
                ),
            )
            leaders = ", ".join(
                f"{item.candidate_id} ({item.metrics[target][metric]:.6g})"
                for item in ordered
                if ranks[target][metric][item.candidate_id] == 1
            )
            lines.append(
                f"- **{metric}** — rank 1: {leaders}; full ordering is in the target-wise ranking CSV."
            )
        lines.append("")

    lines.extend(
        [
            "## Fit-seed stability",
            "",
            f"RES-281's original public-native model-ranking-instability result remains `{res281_record['status']}` (`{res281_record['result_artifact_identity']}`): {res281_record['status_reason']}",
            f"RES-281's original public-native baseline-domination result also remains `{res281_baseline_record['status']}` (`{res281_baseline_record['result_artifact_identity']}`): {res281_baseline_record['status_reason']}",
            "",
            "Fit-seed ranks compare the same seven model families within each fit-seed panel; the separately identified expert ensemble is excluded from seed panels. The three temporal-expert and compact-neural fit seeds are distinct saved fits. Their seed-wise rank ranges are descriptive with n=3. Context mean, Ridge, boosted stumps, mechanistic midpoint, and mechanistic-plus-Ridge predictions are exact repeats across seed labels; their zero rank range is not evidence from independent fit replications. Dataset-seed, split-seed, and distribution-shift stability were not estimated.",
            "",
        ]
    )
    for family in sorted({str(row["model_family"]) for row in fit_rows}):
        family_rows = [row for row in fit_rows if row["model_family"] == family]
        ranges = [float(row["rank_range"]) for row in family_rows]
        interpretations = sorted({str(row["seed_interpretation"]) for row in family_rows})
        lines.append(
            f"- `{family}`: observed rank range spans {min(ranges):g}–{max(ranges):g} positions across target/metric cells; {interpretations[0]} ({len(family_rows)} cells)."
        )
    lines.append("")
    for target in TARGETS:
        for metric in METRICS:
            panel = [
                row
                for row in fit_seed_pairwise_rows
                if row["target"] == target and row["metric"] == metric
            ]
            lines.append(
                f"- `{target}` {metric}: {sum(int(row['pairwise_seed_rank_reversals']) for row in panel)} pairwise order reversals across {sum(int(row['ordered_seed_pairs']) for row in panel)} non-tied seed-pair comparisons."
            )
    lines.extend(
        [
            "",
            "## Metric-dependent rank changes",
            "",
            "The metric-pair summary gives exact pairwise rank reversals and ties by target. For a fixed target and sample, canonical R² and SRE(ddof=0) are monotone transforms of RMSE, so their model rankings should coincide. RMSE-versus-MAE reversals reflect different error weighting; they do not establish a universal best model.",
            "",
        ]
    )
    for row in reversal_summary:
        lines.append(
            f"- `{row['target']}` {row['metric_a']} vs {row['metric_b']}: {row['rank_reversals']} reversals among {row['pairs_ordered_on_both_metrics']} pairs ordered on both metrics (ties: {row['ties_on_metric_a']} / {row['ties_on_metric_b']})."
        )
    front_by_target: dict[str, set[str]] = defaultdict(set)
    front_candidates_by_target: dict[str, list[str]] = defaultdict(list)
    for row in pareto_rows:
        if row["pareto_front"]:
            front_by_target[str(row["target"])].add(str(row["model_family"]))
            front_candidates_by_target[str(row["target"])].append(str(row["candidate_id"]))
    lines.extend(["", "## Pareto trade-offs", ""])
    for target in TARGETS:
        lines.append(
            f"- `{target}`: {len(front_candidates_by_target[target])} Pareto-front candidates "
            f"({', '.join(front_candidates_by_target[target])}); families: "
            f"{', '.join(sorted(front_by_target[target]))}."
        )
    lines.extend(
        [
            "",
            "Dominance uses RMSE↓, MAE↓, and SRE(ddof=0)↓ with R²↑ and exact values. Seed instances are listed separately in the Pareto CSV. R² and SRE do not add independent objectives beyond RMSE for a fixed target population.",
            "The point-estimate Pareto frontier is descriptive; RES-281's baseline-domination state remains INCONCLUSIVE because no practical margin or paired uncertainty method was predeclared.",
            "",
            "## Paired uncertainty evidence",
            "",
            f"All candidate prediction artifacts share {len(row_ids)} row IDs and the canonical EvaluationResults bind {candidates[0].evaluation_sample_count} samples, but tracked public inputs do not contain validation target truth rows or the row-to-entity mapping. The predeclared {int(uncertainty_rows[0]['planned_resamples'])}-replicate entity bootstrap was not run. All {len(uncertainty_rows)} target/candidate/metric uncertainty cells are `UNSUPPORTED_BY_EVIDENCE`, with inference `INCONCLUSIVE`; no rows were regenerated.",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "## Historical evidence-gap result",
            "",
            f"Cross-version matrix: {len(cross_rows)} rejected, 0 admissible, 0 numerically analyzed. Every pair lacks verified common support and paired scores; the failed semantic conditions and source decisions are retained in the matrix. This is unavailable evidence, not demonstrated ranking instability.",
            "",
            "No chronology-based ranking improvement or regression can be inferred. Scrambled-Sobol historical values are not combined with public-native IID values.",
            "",
            "## Uncertainty and limitations",
            "",
            "- Three stochastic fit seeds provide only a small descriptive sample; deterministic repeats add no independent training variation.",
            "- Paired residual and entity-cluster uncertainty could not be estimated: the tracked repository has neither validation truth rows nor the row-to-entity mapping. Prediction row keys alone do not identify athletes.",
            "- No practical decision threshold was frozen for meaningful rank differences. Fit-seed rank dispersion and point rankings are descriptive; the existing RES-281 stability and domination statuses remain `INCONCLUSIVE`.",
            "- Historical evaluation identities, paired populations, and fitted-model outputs are missing for the eight historical versions. Their rankings are unsupported, not unstable.",
            "- Results do not establish correspondence to real-athlete outcomes or any model's external validity.",
            "",
            "## RES-284 handoff boundary",
            "",
            "RES-284 may prepare publication from the public-native within-version descriptive results and the negative historical-comparability finding. It must not report historical rankings, cross-version stability coefficients, model improvement over benchmark chronology, or raw historical comparisons. Keep source-level expert prediction rights marked NOASSERTION and do not publish private historical data, checkpoints, or outputs. Resolving the historical claims requires rights-cleared matched rows, executable native adapters, the same fitted model panel, and a common evaluation/support contract.",
            "",
            "Runnable companion notebook: `analysis-notebook.ipynb`.",
            "",
        ]
    )
    return "\n".join(lines)


def _historical_gap_report(cross_rows: Sequence[Mapping[str, Any]]) -> str:
    versions = sorted(
        {
            str(row[key])
            for row in cross_rows
            for key in ("left_benchmark_version", "right_benchmark_version")
        }
    )
    historical = [version for version in versions if not version.startswith(IID_SLUG + "@")]
    return "\n".join(
        [
            "# RES-283 historical ranking evidence gaps",
            "",
            "The RES-281 cross-version comparability matrix is binding. All 36 version pairs remain `REJECTED_FOR_NUMERICAL_COMPARISON`; zero cross-version ranking statistics are admissible. The public-native IID result is not substituted for missing historical fitted-model evaluations, and scrambled-Sobol historical values are not treated as IID scores.",
            "",
            "## Missing evidence by historical version",
            "",
            *[
                f"- `{version}`: no public rights-cleared native evaluation rows, no matched fitted-model/prediction panel, no row-level paired scores under a common evaluation, and insufficient access metadata to reconstruct the historical panel. Within-version model ranking is `UNSUPPORTED_BY_EVIDENCE`."
                for version in historical
            ],
            "",
            "## Pairwise conclusion",
            "",
            "The original decision, eight semantic check flags, failed conditions, missing matched evidence, and ranking-identifiability status are preserved for every pair in `cross-version-ranking-admissibility.csv`. Missing historical evidence indicates that ranking stability cannot be identified; it does not demonstrate that rankings changed or remained stable.",
            "",
            "No private historical datasets, checkpoints, or outputs were added.",
            "",
        ]
    )


def _rmse_candidate_rank_svg(ranking_rows: Sequence[Mapping[str, Any]]) -> str:
    values = {
        (str(row["candidate_id"]), str(row["target"])): float(row["RMSE_rank"])
        for row in ranking_rows
    }
    candidates = sorted({candidate for candidate, _ in values})
    targets = (
        "squat_delta_capacity_kg",
        "bench_press_delta_capacity_kg",
        "deadlift_delta_capacity_kg",
    )
    label_width, panel_width, row_height = 200, 108, 20
    top, legend_height = 78, 48
    width = label_width + len(targets) * panel_width + 24
    height = top + len(candidates) * row_height + legend_height
    rank_max = max(values.values())
    family_labels = {
        "public-native-temporal-expert": "Expert",
        "compact_neural": "Compact NN",
        "mechanistic_midpoint": "Mechanistic",
        "mechanistic_ridge_residual": "Mech + Ridge",
        "context_mean": "Context mean",
        "ridge": "Ridge",
        "histogram_boosted_stumps": "Boosted stumps",
    }
    short_targets = {
        "squat_delta_capacity_kg": "Squat",
        "bench_press_delta_capacity_kg": "Bench",
        "deadlift_delta_capacity_kg": "Deadlift",
    }
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-description">',
        '<title id="chart-title">Candidate RMSE rank by target</title>',
        '<desc id="chart-description">A heatmap of exact candidate ranks from the canonical IID EvaluationResults. Rank one is best; exact metric ties use average ranks. Each target has a separate column and each cell prints its rank.</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="8" y="20" font-family="sans-serif" font-size="14" font-weight="600" fill="#1f2937">Candidate RMSE rank by target</text>',
        '<text x="8" y="39" font-family="sans-serif" font-size="11" fill="#4b5563">Canonical IID evaluation · rank 1 is best · exact ties receive average ranks</text>',
    ]
    for column, target in enumerate(targets):
        x = label_width + column * panel_width
        out.append(
            f'<text x="{x + panel_width / 2}" y="62" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="600" fill="#1f2937">{short_targets[target]}</text>'
        )
    for row_index, candidate_id in enumerate(candidates):
        y = top + row_index * row_height
        family, seed = candidate_id.rsplit(":", 1)
        seed_label = "ensemble" if seed == "ensemble" else f"seed {seed[-1]}"
        label = f"{family_labels.get(family, family)} · {seed_label}"
        out.append(
            f'<text x="{label_width - 8}" y="{y + 14}" text-anchor="end" font-family="sans-serif" font-size="10.5" fill="#374151">{label}</text>'
        )
        for column, target in enumerate(targets):
            rank = values[(candidate_id, target)]
            intensity = 1.0 if rank_max == 1 else (rank_max - rank) / (rank_max - 1)
            # A single blue sequential scale; cell values make the encoding readable without color.
            low = (239, 246, 255)
            high = (29, 78, 216)
            color = tuple(round(a + (b - a) * intensity) for a, b in zip(low, high, strict=True))
            fill = "#" + "".join(f"{channel:02x}" for channel in color)
            x = label_width + column * panel_width + 4
            text_color = "#ffffff" if intensity >= 0.48 else "#1f2937"
            out.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{panel_width - 8}" height="{row_height - 2}" rx="2" fill="{fill}" stroke="#d1d5db" stroke-width="0.5"/>',
                    f'<text x="{x + (panel_width - 8) / 2}" y="{y + 13}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="{text_color}">{rank:g}</text>',
                ]
            )
    legend_y = top + len(candidates) * row_height + 13
    out.append(
        f'<text x="8" y="{legend_y + 3}" font-family="sans-serif" font-size="10" fill="#4b5563">Candidate RMSE rank</text>'
    )
    legend_x = label_width
    for index in range(11):
        rank = 1.0 + index / 10 * (rank_max - 1.0)
        intensity = 1.0 if rank_max == 1 else (rank_max - rank) / (rank_max - 1)
        low = (239, 246, 255)
        high = (29, 78, 216)
        color = tuple(round(a + (b - a) * intensity) for a, b in zip(low, high, strict=True))
        fill = "#" + "".join(f"{channel:02x}" for channel in color)
        x = legend_x + index * 14
        out.append(f'<rect x="{x}" y="{legend_y - 8}" width="14" height="10" fill="{fill}"/>')
    out.extend(
        [
            f'<text x="{legend_x}" y="{legend_y + 14}" font-family="sans-serif" font-size="9" fill="#4b5563">1 best</text>',
            f'<text x="{legend_x + 140}" y="{legend_y + 14}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#4b5563">{rank_max:g}</text>',
            "</svg>",
        ]
    )
    return "\n".join(out)


def _notebook_bytes(
    analysis_identity: str,
    candidates: Sequence[Candidate],
    ranking_rows: Sequence[Mapping[str, Any]],
    uncertainty_rows: Sequence[Mapping[str, Any]],
    fit_rows: Sequence[Mapping[str, Any]],
    fit_seed_pairwise_rows: Sequence[Mapping[str, Any]],
    reversal_summary: Sequence[Mapping[str, Any]],
    cross_rows: Sequence[Mapping[str, Any]],
    row_ids: Sequence[str],
    res281_record: Mapping[str, Any],
    res281_baseline_record: Mapping[str, Any],
) -> bytes:
    if len(uncertainty_rows) != len(candidates) * len(TARGETS) * len(METRICS):
        raise ValueError(
            "uncertainty evidence matrix must cover every candidate, target, and metric"
        )
    unsupported_uncertainty_count = sum(
        row["status"] == "UNSUPPORTED_BY_EVIDENCE" for row in uncertainty_rows
    )
    winners: list[str] = []
    for target in TARGETS:
        for metric in METRICS:
            metric_rows = [
                row
                for row in ranking_rows
                if row["target"] == target and row[f"{metric}_rank"] == 1
            ]
            labels = ", ".join(str(row["candidate_id"]) for row in metric_rows)
            winners.append(f"- `{target}` · {metric}: {labels}.")
    fit_summary = []
    for family in sorted({str(row["model_family"]) for row in fit_rows}):
        rows = [row for row in fit_rows if row["model_family"] == family]
        fit_summary.append(
            f"- `{family}`: rank range {min(float(row['rank_range']) for row in rows):g}–{max(float(row['rank_range']) for row in rows):g}; {rows[0]['seed_interpretation']}."
        )
    fit_seed_reversal_lines = []
    for target in TARGETS:
        for metric in METRICS:
            panel = [
                row
                for row in fit_seed_pairwise_rows
                if row["target"] == target and row["metric"] == metric
            ]
            fit_seed_reversal_lines.append(
                f"- `{target}` {metric}: {sum(int(row['pairwise_seed_rank_reversals']) for row in panel)} fit-seed order reversals across {sum(int(row['ordered_seed_pairs']) for row in panel)} non-tied comparisons."
            )
    reversal_lines = [
        f"- `{row['target']}` {row['metric_a']} vs {row['metric_b']}: {row['rank_reversals']} reversals among {row['pairs_ordered_on_both_metrics']} non-tied pairs."
        for row in reversal_summary
    ]
    rejected = sum(
        row["original_res281_decision"] == "REJECTED_FOR_NUMERICAL_COMPARISON" for row in cross_rows
    )
    markdown_cells = [
        "# RES-283 model-ranking stability and comparability\n\n"
        "## tl;dr\n\n"
        f"The only admissible model panel is the public-native IID evaluation: {len(candidates)} fitted-instance/ensemble candidates across three target QOIs. The temporal-expert ensemble ranks first on all four metrics for bench and deadlift, and on RMSE, R², and SRE for squat; expert seed 383003 has the lowest squat MAE. All {rejected} historical cross-version pairs remain rejected, with no historical ranking statistic. RES-281's original ranking-instability and baseline-domination states remain `{res281_record['status']}` and `{res281_baseline_record['status']}`.\n\n"
        "## Context & Methods\n\n"
        "The frozen candidate unit is one fitted instance. Three temporal-expert seeds are kept separate, and their equal-mean ensemble is a separate candidate. Compact-neural seed runs are separate. Fit-seed ranks compare the same seven families within each seed panel; the ensemble is excluded from those panels. Repeated deterministic comparator outputs are shown as separate saved identities but are not independent fit replications. RMSE, MAE, and SRE(ddof=0) minimize; R² maximizes. Exact ties receive average ranks. No universal scalar score or cross-target ranking is computed.\n\n"
        "Canonical result metrics support point rankings and candidate prediction files share their row keys. The tracked repository does not include validation truth rows or the row-to-entity map, so no entity-cluster bootstrap or paired residual uncertainty was computed. The uncertainty evidence table marks those estimates `UNSUPPORTED_BY_EVIDENCE`; inference remains `INCONCLUSIVE`.\n\n"
        "## Data\n\n"
        "Sources are the RES-274 temporal-expert EvaluationResults and ensemble, RES-275 standardized comparator EvaluationResults and fitted instances, the canonical RES-271 IID EvaluationResults, the public IID DatasetRealization manifests, and the binding RES-281 comparability matrix. The raw IID validation JSONL is not checked in; its declared hashes remain in the manifests. The analysis verifies EvaluationResult and prediction-artifact identities, target metrics, and shared prediction row keys. Historical row-level predictions or model panels are not substituted from IID evidence.\n\n"
        "## Results\n\n"
        "### Target-wise rank-one candidates\n\n"
        + "\n".join(winners)
        + "\n\n### Fit-seed rank ranges\n\n"
        + "\n".join(fit_summary)
        + "\n\n### Pairwise order changes across fit seeds\n\n"
        + "\n".join(fit_seed_reversal_lines)
        + "\n\n### Metric-dependent pairwise reversals\n\n"
        + "\n".join(reversal_lines)
        + "\n\n### Historical comparisons\n\n"
        + f"{rejected} of {len(cross_rows)} cross-version pairs are `REJECTED_FOR_NUMERICAL_COMPARISON`; zero are admissible. This is missing evidence, not demonstrated ranking instability.\n\n"
        "## Takeaways\n\n"
        "The public-native ranking is specific to the synthetic IID realization and its evaluation. Fit-seed variation, data-seed variation, split-seed variation, and distribution-shift variation are distinct. Only the observed fit-seed ordering is measured; held-out-population uncertainty is unavailable without the tracked validation truth and entity map. No chronology-based improvement or real-athlete validity is established. See the report, evidence matrix, pairwise reversal table, and cross-version admissibility matrix for the complete evidence.\n"
    ]
    verify_code = """import json

from powerlifting_state_research.audits.res283_analysis import (
    build_analysis_artifacts,
    verify_output_index,
)

artifacts = build_analysis_artifacts()
verify_output_index(artifacts)
run_manifest = json.loads(artifacts["results/audits/res283-analysis/run-manifest.json"])
print(f\"PASS · {run_manifest['run_id']}\")
print(run_manifest["analysis_identity"])
print(f\"{run_manifest['candidate_count']} candidates\")
row_key_count = run_manifest["prediction_row_key_count"]
sample_count = run_manifest["canonical_evaluation_sample_count"]
entity_map_available = run_manifest["row_to_entity_mapping_available"]
print(f\"{row_key_count} prediction row keys · {sample_count} canonical evaluation samples\")
print(f\"row-to-entity mapping available: {entity_map_available}\")
"""
    winners_code = """import csv
from io import StringIO

ranking_csv = artifacts[
    "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv"
].decode()
ranking_rows = list(csv.DictReader(StringIO(ranking_csv)))
targets = ("squat_delta_capacity_kg", "bench_press_delta_capacity_kg", "deadlift_delta_capacity_kg")
for target in targets:
    for metric in ("RMSE", "MAE", "R²", "SRE(ddof=0)"):
        leaders = [
            row
            for row in ranking_rows
            if row["target"] == target and float(row[f"{metric}_rank"]) == 1
        ]
        leader_names = ", ".join(row["candidate_id"] for row in leaders)
        print(f\"{target} · {metric}: {leader_names}.\")
"""
    figure_code = """from IPython.display import SVG, display

from powerlifting_state_research.audits.res283_analysis import _rmse_candidate_rank_svg

display(SVG(_rmse_candidate_rank_svg(ranking_rows)))
"""
    cross_code = """import csv
from collections import Counter
from io import StringIO

cross_csv = artifacts[
    "results/audits/res283-analysis/cross-version-ranking-admissibility.csv"
].decode()
cross_rows = list(csv.DictReader(StringIO(cross_csv)))
print(dict(Counter(row["original_res281_decision"] for row in cross_rows)))
uncertainty_csv = artifacts[
    "results/audits/res283-analysis/paired-uncertainty-evidence.csv"
].decode()
uncertainty_rows = list(csv.DictReader(StringIO(uncertainty_csv)))
print(dict(Counter(row["status"] for row in uncertainty_rows)))
ranking_status = run_manifest["res281_public_native_model_ranking_status"]
result_identity = run_manifest["res281_public_native_model_ranking_result_identity"]
print(f\"RES-281 model-ranking-instability status: {ranking_status}\")
print(result_identity)
baseline_status = run_manifest["res281_public_native_baseline_domination_status"]
baseline_identity = run_manifest["res281_public_native_baseline_domination_result_identity"]
print(f\"RES-281 baseline-domination status: {baseline_status}\")
print(baseline_identity)
"""

    def cell(
        cell_type: str,
        cell_id: str,
        source: str,
        *,
        execution_count: int | None = None,
        outputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source_lines = source.splitlines(keepends=True)
        if source_lines and source_lines[-1].endswith("\n"):
            source_lines[-1] = source_lines[-1][:-1]
        result: dict[str, Any] = {
            "cell_type": cell_type,
            "id": cell_id,
            "metadata": {},
            "source": source_lines,
        }
        if cell_type == "code":
            result["execution_count"] = execution_count
            result["outputs"] = outputs or []
        return result

    def stdout(text: str) -> dict[str, Any]:
        return {"output_type": "stream", "name": "stdout", "text": text.splitlines(keepends=True)}

    svg = _rmse_candidate_rank_svg(ranking_rows)
    notebook = {
        "cells": [
            cell("markdown", "res283-summary", markdown_cells[0]),
            cell(
                "markdown",
                "res283-run",
                "### 1. Rebuild and verify the artifacts\n\nThis cell replays the frozen configuration, checks source identities and exact row pairing, and verifies the output checksum index.",
            ),
            cell(
                "code",
                "res283-verify",
                verify_code,
                execution_count=1,
                outputs=[
                    stdout(
                        f"PASS · res283-ranking-{analysis_identity.rsplit('sha256:', 1)[1][:12]}\n"
                        f"{analysis_identity}\n"
                        f"{len(candidates)} candidates\n"
                        f"{len(row_ids)} prediction row keys · {candidates[0].evaluation_sample_count} canonical evaluation samples\n"
                        "row-to-entity mapping available: False\n"
                    )
                ],
            ),
            cell(
                "markdown",
                "res283-winners-heading",
                "### 2. Target-wise rank leaders\n\nEach metric and target remains separate; ties are preserved.",
            ),
            cell(
                "code",
                "res283-winners",
                winners_code,
                execution_count=2,
                outputs=[
                    stdout(
                        "\n".join(winners)
                        .replace("- `", "")
                        .replace("` · ", " · ")
                        .replace("`.", "")
                        + "\n"
                    )
                ],
            ),
            cell(
                "markdown",
                "res283-heatmap-heading",
                "### 3. Candidate-level RMSE rank by target\n\nThe heatmap shows exact ranks from the canonical EvaluationResults. Rank one is best; exact ties receive average ranks.",
            ),
            cell(
                "code",
                "res283-heatmap",
                figure_code,
                execution_count=3,
                outputs=[
                    {
                        "output_type": "display_data",
                        "data": {
                            "image/svg+xml": svg,
                            "text/plain": "<svg RES-283 candidate RMSE rank heatmap>",
                        },
                        "metadata": {},
                    }
                ],
            ),
            cell(
                "markdown",
                "res283-cross-heading",
                "### 4. Cross-version admissibility and original status",
            ),
            cell(
                "code",
                "res283-cross",
                cross_code,
                execution_count=4,
                outputs=[
                    stdout(
                        "{'REJECTED_FOR_NUMERICAL_COMPARISON': 36}\n"
                        f"{{'UNSUPPORTED_BY_EVIDENCE': {unsupported_uncertainty_count}}}\n"
                        f"RES-281 model-ranking-instability status: {res281_record['status']}\n"
                        f"{res281_record['result_artifact_identity']}\n"
                        f"RES-281 baseline-domination status: {res281_baseline_record['status']}\n"
                        f"{res281_baseline_record['result_artifact_identity']}\n"
                    )
                ],
            ),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return (json.dumps(notebook, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode(
        "utf-8"
    )


def _res281_public_native_record(root: Path, attack_slug: str) -> dict[str, Any]:
    audit = _read_json(root, "results/audits/res281/audit-results.json")
    matching = [
        record
        for record in audit["records"]
        if record.get("benchmark_version") == f"{IID_SLUG}@1.0.0"
        and record.get("attack_spec_ref") == f"{attack_slug}@1.0.0"
    ]
    if len(matching) != 1:
        raise ValueError(f"RES-281 must have one public-native {attack_slug} record")
    result = matching[0]
    if result["status"] != "INCONCLUSIVE":
        raise ValueError(f"RES-281 {attack_slug} status must remain INCONCLUSIVE")
    return cast(dict[str, Any], result)


def build_analysis_artifacts(root: Path = ROOT) -> dict[str, bytes]:
    """Build every deterministic RES-283 output without writing to source artifacts."""
    config = _read_json(root, CONFIG_PATH.as_posix())
    if config.get("format") != "PSR_RES283_ANALYSIS_CONFIG_V1":
        raise ValueError("unexpected RES-283 analysis configuration")
    contract = _native_panel_contract(root)
    candidates = _load_candidates(root, contract)
    first_result_document = json.loads(
        (root / candidates[0].evaluation_path).read_text(encoding="utf-8")
    )
    first_result = first_result_document.get("result", first_result_document)
    require_comparable_native_panel(contract, first_result["targets"])
    row_ids = _load_prediction_row_ids(root, candidates)
    if len(row_ids) != contract["validation_row_count"]:
        raise ValueError(
            "paired prediction row keys differ from the canonical IID EvaluationResult sample count"
        )

    base_identity = {
        candidate.candidate_id: {
            "benchmark_id": candidate.benchmark_id,
            "world_id": contract["world_id"],
            "dataset_spec_id": contract["dataset_spec_id"],
            "dataset_realization_id": candidate.dataset_realization_id,
            "evaluation_id": candidate.evaluation_id,
            "task_id": contract["task_id"],
            "qoi_id": contract["qoi_ids"],
            "metric_ids": contract["metric_ids"],
            "information_boundary": contract["information_boundary"],
            "row_ids": tuple(row_ids),
        }
        for candidate in candidates
    }
    first_identity = base_identity[candidates[0].candidate_id]
    for candidate in candidates[1:]:
        status, failed = numerical_comparison_status(
            first_identity, base_identity[candidate.candidate_id]
        )
        if status != "ADMISSIBLE" or failed:
            raise ValueError(
                f"within-version model comparison failed admissibility: {status}/{failed}"
            )

    ranks = _point_ranks(candidates)
    ranking_rows = _ranking_rows(candidates, row_ids, ranks)
    fit_rows = _fit_seed_rows(candidates, config)
    fit_seed_pairwise_rows = _fit_seed_pairwise_rows(candidates)
    pairwise_rows, reversal_summary = _pairwise_ranking_rows(candidates, ranks)
    pareto_rows = _pareto_rows(candidates)
    uncertainty_rows = _uncertainty_evidence_rows(candidates, config)
    version_rows = _version_rows(root, candidates, row_ids, config)
    cross_rows = _cross_version_rows(root)
    res281_record = _res281_public_native_record(root, "model_ranking_instability")
    res281_baseline_record = _res281_public_native_record(root, "baseline_domination")
    input_hashes = _source_files(root, config, candidates)
    config_hash = _sha256(root / CONFIG_PATH)
    analysis_fingerprint = sha256_record(
        {
            "analysis_id": config["analysis_id"],
            "source_commit": config["source_commit"],
            "analysis_config_sha256": f"sha256:{config_hash}",
            "input_artifacts": input_hashes,
        }
    ).removeprefix("sha256:")
    analysis_identity = f"psr:analysis:{config['analysis_id']}@sha256:{analysis_fingerprint}"

    outputs: dict[str, bytes] = {
        "version-by-model-evidence.csv": _csv_bytes(
            (
                "benchmark_version",
                "benchmark_id",
                "task_type",
                "task_identity",
                "qoi_identity",
                "qoi_reference",
                "target_ontology",
                "world_identity",
                "world_summary_dgp",
                "data_generating_process",
                "population_identity",
                "population_resolution",
                "intervention_regime_identity",
                "intervention_regime_resolution",
                "observation_model_identity",
                "representation_identity",
                "dataset_spec_identity",
                "dataset_spec_resolution",
                "dataset_realization_identity",
                "dataset_realization_digest",
                "participant_visible_information",
                "evaluation_identity",
                "metric_identity_ids",
                "metric_direction",
                "model_family",
                "model_family_evidence_status",
                "model_id",
                "fitted_instance_ids",
                "prediction_artifact_identities",
                "evaluation_result_ids",
                "fit_seed_labels",
                "seed_role_summary",
                "dataset_split_design",
                "model_selection_split",
                "ensemble_present",
                "candidate_count",
                "row_level_matched_evidence",
                "rights_access_constraints",
                "native_ranking_status",
            ),
            version_rows,
        ),
        "frozen-iid-target-wise-rankings.csv": _csv_bytes(
            (
                "target",
                "prediction_row_keys",
                "canonical_evaluation_sample_count",
                "candidate_id",
                "model_family",
                "candidate_role",
                "fit_seed",
                "model_id",
                "fitted_instance_id",
                "evaluation_result_id",
                "prediction_artifact_identity",
                "evaluation_result_sha256",
                "prediction_artifact_sha256",
                "fitted_identity_artifact_sha256",
                "within_version_comparison_status",
                *METRICS,
                *(f"{metric}_rank" for metric in METRICS),
            ),
            ranking_rows,
        ),
        "fit-seed-rank-stability.csv": _csv_bytes(
            (
                "model_family",
                "target",
                "metric",
                "fit_seed_count",
                "comparison_panel_family_count",
                "seed_candidate_ids",
                "seed_ranks",
                "rank_min",
                "rank_max",
                "rank_range",
                "rank_sd_ddof0",
                "distinct_ranks",
                "distinct_prediction_artifacts",
                "seed_interpretation",
                "inference_status",
            ),
            fit_rows,
        ),
        "fit-seed-pairwise-reversals.csv": _csv_bytes(
            (
                "target",
                "metric",
                "model_family_a",
                "model_family_b",
                "candidate_ids_a",
                "candidate_ids_b",
                "family_a_ranks_by_seed",
                "family_b_ranks_by_seed",
                "ordered_seed_pairs",
                "pairwise_seed_rank_reversals",
                "tied_seed_labels",
                "inference_status",
            ),
            fit_seed_pairwise_rows,
        ),
        "pairwise-ranking-reversals.csv": _csv_bytes(
            (
                "target",
                "candidate_a",
                "candidate_b",
                *(f"{metric}_rank_a" for metric in METRICS),
                *(f"{metric}_rank_b" for metric in METRICS),
                *(f"{a}_vs_{b}_relation" for a, b in itertools.combinations(METRICS, 2)),
                "reversed_metric_pairs",
            ),
            pairwise_rows,
        ),
        "metric-dependent-ranking-summary.csv": _csv_bytes(
            (
                "target",
                "metric_a",
                "metric_b",
                "candidate_pairs",
                "pairs_ordered_on_both_metrics",
                "rank_reversals",
                "ties_on_metric_a",
                "ties_on_metric_b",
                "interpretation",
            ),
            reversal_summary,
        ),
        "pareto-comparison-summary.csv": _csv_bytes(
            (
                "target",
                "candidate_id",
                "model_family",
                "pareto_front",
                "dominated_by_count",
                "dominated_by_candidate_ids",
                "rmse_kg",
                "mae_kg",
                "r2",
                "sre_ddof0",
            ),
            pareto_rows,
        ),
        "paired-uncertainty-evidence.csv": _csv_bytes(
            (
                "target",
                "metric",
                "candidate_id",
                "planned_method",
                "planned_resamples",
                "planned_seed",
                "completed_resamples",
                "status",
                "inference_status",
                "reason",
            ),
            uncertainty_rows,
        ),
        "cross-version-ranking-admissibility.csv": _csv_bytes(
            (
                "left_benchmark_version",
                "right_benchmark_version",
                "original_res281_decision",
                "admissibility_classification",
                "declared_semantic_checks",
                "failed_semantic_conditions",
                "matched_support_and_paired_scores_verified",
                "missing_matched_evidence",
                "rankings_scientifically_identifiable",
                "rejection_reasons",
            ),
            cross_rows,
        ),
        "historical-evidence-gap-report.md": _historical_gap_report(cross_rows).encode("utf-8"),
        "res283-model-ranking-stability.md": _report_markdown(
            candidates,
            ranks,
            fit_rows,
            fit_seed_pairwise_rows,
            reversal_summary,
            pareto_rows,
            cross_rows,
            uncertainty_rows,
            row_ids,
            analysis_identity,
            res281_record,
            res281_baseline_record,
        ).encode("utf-8"),
        "RES-284-handoff.md": (
            "# RES-284 handoff\n\n"
            f"RES-283 analysis identity: `{analysis_identity}`.\n\n"
            "RES-284 may prepare a publication using the public-native IID target-wise rankings, matched-seed diagnostics, metric reversals, Pareto findings, and the negative historical-comparability result. Preserve `INCONCLUSIVE` uncertainty statuses and the paired-evidence gap. Do not report any historical model ranking, cross-version stability coefficient, improvement over benchmark chronology, direct comparison of scrambled-Sobol and IID raw scores, or bootstrap estimate. The historical result is an evidence gap: eight versions lack public matched rows, fitted panels, and common-evaluation results. Keep temporal-expert prediction rights marked NOASSERTION and exclude private historical datasets, checkpoints, and outputs.\n\n"
            "Publication boundary: the report may describe public-native synthetic evidence and the fact that historical rankings are not identifiable. It may not imply real-athlete validity or cross-version superiority. Any new historical claim requires rights-cleared matched evidence and a common native evaluation before RES-284 analysis.\n"
        ).encode(),
    }
    outputs["analysis-notebook.ipynb"] = _notebook_bytes(
        analysis_identity,
        candidates,
        ranking_rows,
        uncertainty_rows,
        fit_rows,
        fit_seed_pairwise_rows,
        reversal_summary,
        cross_rows,
        row_ids,
        res281_record,
        res281_baseline_record,
    )
    artifact_records = [
        {
            "path": f"{OUTPUT_DIR.as_posix()}/{name}",
            "sha256": f"sha256:{hashlib.sha256(content).hexdigest()}",
        }
        for name, content in sorted(outputs.items())
    ]
    run_manifest = {
        "format": "PSR_RES283_ANALYSIS_RUN_V1",
        "run_id": f"res283-ranking-{analysis_fingerprint[:12]}",
        "analysis_identity": analysis_identity,
        "source_commit": config["source_commit"],
        "analysis_config": {"path": CONFIG_PATH.as_posix(), "sha256": f"sha256:{config_hash}"},
        "analysis_implementation": {
            "path": "src/powerlifting_state_research/audits/res283_analysis.py",
            "sha256": f"sha256:{input_hashes['src/powerlifting_state_research/audits/res283_analysis.py']}",
        },
        "input_artifacts": [
            {"path": path, "sha256": f"sha256:{digest}"}
            for path, digest in sorted(input_hashes.items())
        ],
        "source_model_ids": sorted({candidate.model_id for candidate in candidates}),
        "fitted_instance_ids": sorted({candidate.fitted_instance_id for candidate in candidates}),
        "evaluation_result_ids": sorted(
            {candidate.evaluation_result_id for candidate in candidates}
        ),
        "prediction_artifact_identities": sorted(
            {candidate.prediction_artifact_identity for candidate in candidates}
        ),
        "candidate_identity_bindings": [
            {
                "candidate_id": candidate.candidate_id,
                "model_family": candidate.family,
                "candidate_role": candidate.role,
                "fit_seed": candidate.seed,
                "model_id": candidate.model_id,
                "fitted_instance_id": candidate.fitted_instance_id,
                "fitted_identity_artifact": {
                    "path": candidate.fitted_instance_path,
                    "sha256": f"sha256:{candidate.fitted_instance_sha256}",
                },
                "evaluation_result_id": candidate.evaluation_result_id,
                "evaluation_result": {
                    "path": candidate.evaluation_path,
                    "sha256": f"sha256:{candidate.evaluation_sha256}",
                },
                "prediction_artifact_identity": candidate.prediction_artifact_identity,
                "prediction_artifact": {
                    "path": candidate.prediction_path,
                    "sha256": f"sha256:{candidate.prediction_sha256}",
                },
            }
            for candidate in candidates
        ],
        "benchmark_id": contract["benchmark_id"],
        "dataset_spec_id": contract["dataset_spec_id"],
        "dataset_realization_id": contract["dataset_realization_id"],
        "evaluation_id": contract["evaluation_id"],
        "task_id": contract["task_id"],
        "qoi_ids": contract["qoi_ids"],
        "metric_ids": contract["metric_ids"],
        "validation_split_id": contract["validation_split_id"],
        "model_selection_split_id": contract["model_selection_split_id"],
        "target_count": len(TARGETS),
        "candidate_count": len(candidates),
        "prediction_row_key_count": len(row_ids),
        "canonical_evaluation_sample_count": candidates[0].evaluation_sample_count,
        "validation_target_truth_available": False,
        "row_to_entity_mapping_available": False,
        "planned_entity_bootstrap_resamples": int(config["paired_uncertainty"]["resamples"]),
        "completed_entity_bootstrap_resamples": 0,
        "cross_version_pair_count": len(cross_rows),
        "admissible_cross_version_pair_count": sum(
            row["admissibility_classification"] == "ADMISSIBLE" for row in cross_rows
        ),
        "res281_public_native_model_ranking_status": res281_record["status"],
        "res281_public_native_model_ranking_result_identity": res281_record[
            "result_artifact_identity"
        ],
        "res281_public_native_baseline_domination_status": res281_baseline_record["status"],
        "res281_public_native_baseline_domination_result_identity": res281_baseline_record[
            "result_artifact_identity"
        ],
        "artifacts": artifact_records,
    }
    manifest_bytes = _json_bytes(run_manifest)
    outputs["run-manifest.json"] = manifest_bytes
    index_files = [
        {
            "path": f"{OUTPUT_DIR.as_posix()}/{name}",
            "sha256": f"sha256:{hashlib.sha256(content).hexdigest()}",
            "size_bytes": len(content),
        }
        for name, content in sorted(
            {**outputs, "analysis-config.json": (root / CONFIG_PATH).read_bytes()}.items()
        )
    ]
    outputs["checksum-index.json"] = _json_bytes(
        {
            "format": "PSR_SHA256_INDEX_V1",
            "algorithm": "SHA-256",
            "run_manifest_sha256": f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}",
            "files": index_files,
        }
    )
    return {
        **{f"{OUTPUT_DIR.as_posix()}/{name}": content for name, content in outputs.items()},
        CONFIG_PATH.as_posix(): (root / CONFIG_PATH).read_bytes(),
    }


def verify_output_index(artifacts: Mapping[str, bytes]) -> None:
    index_path = f"{OUTPUT_DIR.as_posix()}/checksum-index.json"
    index = json.loads(artifacts[index_path])
    indexed_paths: set[str] = set()
    for entry in index["files"]:
        path = str(entry["path"])
        indexed_paths.add(path)
        if path not in artifacts:
            raise ValueError(f"checksum index references missing artifact {path}")
        if int(entry["size_bytes"]) != len(artifacts[path]):
            raise ValueError(f"analysis size mismatch for {path}")
        actual = hashlib.sha256(artifacts[path]).hexdigest()
        if actual != str(entry["sha256"]).removeprefix("sha256:"):
            raise ValueError(f"analysis checksum mismatch for {path}")
    manifest = artifacts[f"{OUTPUT_DIR.as_posix()}/run-manifest.json"]
    if index["run_manifest_sha256"] != f"sha256:{hashlib.sha256(manifest).hexdigest()}":
        raise ValueError("analysis checksum index does not bind its run manifest")
    run_manifest = json.loads(manifest)
    config_path = str(run_manifest["analysis_config"]["path"])
    config_sha256 = str(run_manifest["analysis_config"]["sha256"])
    if config_path not in indexed_paths or config_path not in artifacts:
        raise ValueError("analysis checksum index omits its declared configuration")
    if config_sha256 != f"sha256:{hashlib.sha256(artifacts[config_path]).hexdigest()}":
        raise ValueError("run manifest configuration hash does not match its input artifact")
    for entry in run_manifest["artifacts"]:
        path = str(entry["path"])
        expected = str(entry["sha256"])
        if path not in indexed_paths or path not in artifacts:
            raise ValueError(f"analysis output is missing from the checksum index: {path}")
        if expected != f"sha256:{hashlib.sha256(artifacts[path]).hexdigest()}":
            raise ValueError(f"run manifest output hash mismatch for {path}")


def write_analysis(artifacts: Mapping[str, bytes], root: Path = ROOT) -> None:
    verify_output_index(artifacts)
    index_path = f"{OUTPUT_DIR.as_posix()}/checksum-index.json"
    ordered_paths = sorted(path for path in artifacts if path != index_path) + [index_path]
    for relative_path in ordered_paths:
        content = artifacts[relative_path]
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def check_analysis(root: Path = ROOT) -> None:
    expected = build_analysis_artifacts(root)
    verify_output_index(expected)
    for relative_path, content in expected.items():
        actual_path = root / relative_path
        if not actual_path.is_file() or actual_path.read_bytes() != content:
            raise ValueError(f"analysis replay differs at {relative_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify a deterministic replay")
    args = parser.parse_args()
    if args.check:
        check_analysis()
        print("RES-283 deterministic replay and checksum verification: PASS")
    else:
        artifacts = build_analysis_artifacts()
        write_analysis(artifacts)
        print(f"RES-283 analysis written to {OUTPUT_DIR.as_posix()}")


if __name__ == "__main__":
    main()
