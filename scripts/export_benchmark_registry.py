"""Export typed benchmark declarations and generated JSON Schemas."""

from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Literal, TypedDict, Union, get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerlifting_state_research.artifacts.manifests import ArtifactManifest  # noqa: E402
from powerlifting_state_research.contracts.benchmark import BenchmarkSpec  # noqa: E402
from powerlifting_state_research.exports import write_exports  # noqa: E402


class DatasetFile(TypedDict):
    path: str
    sha256: str
    bytes: int


class GenerationProvenance(TypedDict):
    generator: str
    generator_version: str
    configuration_sha256: str
    seeds_or_replicates: list[str]
    source: str


class DatasetRealizationManifest(TypedDict):
    dataset_spec_id: str
    realization_id: str
    schema_id: str
    generation: GenerationProvenance
    split_ids: list[str]
    temporal_coverage: str
    entity_count: int
    row_counts: dict[str, int]
    files: list[DatasetFile]
    license_expression: str
    origin_class: str
    redistribution_status: str


class PredictionRow(TypedDict):
    entity_id: str
    query_id: str
    qoi_id: str
    horizon: str
    value: float


class PredictionArtifact(TypedDict):
    benchmark_id: str
    dataset_realization_id: str
    model_id: str
    created_at: str
    predictions: list[PredictionRow]


class MetricResult(TypedDict):
    metric_id: str
    value: float
    support: int
    uncertainty: float | None


class EvaluationResult(TypedDict):
    benchmark_id: str
    dataset_realization_id: str
    evaluation_id: str
    prediction_artifact_id: str
    metrics: list[MetricResult]
    claim_scope: list[str]
    created_at: str


def schema_for(annotation: Any) -> dict[str, Any]:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        values = list(args)
        types = {type(value).__name__ for value in values}
        schema: dict[str, Any] = {"enum": values}
        if len(types) == 1:
            schema["type"] = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
            }.get(next(iter(types)))
        return schema
    if origin in (Union, UnionType):
        return {"anyOf": [schema_for(arg) for arg in args]}
    if origin in (list, tuple):
        item_type = args[0] if args else Any
        return {"type": "array", "items": schema_for(item_type)}
    if origin is dict:
        value_type = args[1] if len(args) > 1 else Any
        return {"type": "object", "additionalProperties": schema_for(value_type)}
    if annotation is Any or annotation is object:
        return {}
    if annotation is type(None):
        return {"type": "null"}
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        values = [member.value for member in annotation]
        return {"type": "string", "enum": values}
    if isinstance(annotation, type) and hasattr(annotation, "__required_keys__"):
        hints = get_type_hints(annotation)
        return {
            "type": "object",
            "properties": {name: schema_for(value) for name, value in hints.items()},
            "required": sorted(annotation.__required_keys__),
            "additionalProperties": False,
        }
    if isinstance(annotation, type) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        return {
            "type": "object",
            "properties": {
                field.name: schema_for(hints[field.name]) for field in fields(annotation)
            },
            "required": [field.name for field in fields(annotation)],
            "additionalProperties": False,
        }
    primitive = {str: "string", int: "integer", float: "number", bool: "boolean"}
    return {"type": primitive[annotation]} if annotation in primitive else {}


def document_schema(title: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "$comment": (
            "JSON Schema describes record structure only. Semantic and cross-field invariants "
            "are enforced by the authoritative Python contract validator; no execution engine "
            "is implied."
        ),
        **body,
    }


def export() -> None:
    write_exports()
    schemas = {
        "artifact-manifest.schema.json": (ArtifactManifest, "Public artifact rights manifest"),
        "benchmark-spec.schema.json": (BenchmarkSpec, "Public benchmark specification"),
        "dataset-realization.schema.json": (
            DatasetRealizationManifest,
            "Dataset realization manifest",
        ),
        "evaluation-result.schema.json": (EvaluationResult, "Evaluation result"),
        "prediction.schema.json": (PredictionArtifact, "Prediction artifact"),
    }
    for filename, (record_type, title) in schemas.items():
        output = document_schema(title, schema_for(record_type))
        (ROOT / "schemas" / filename).write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    export()
