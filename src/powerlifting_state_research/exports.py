"""Generate checked-in JSON interchange files from authoritative Python records."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from importlib import import_module
from pathlib import Path
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from . import __version__
from .artifacts.manifests import ArtifactManifest, RightsMetadata
from .components.source_identity_provenance import (
    SOURCE_COMPONENT_ALIASES,
    SOURCE_COMPONENT_IDENTITIES,
)
from .components.worlds import WORLD_DECLARATIONS
from .contracts.benchmark import (
    BenchmarkIdentityAuthority,
    BenchmarkSemanticIdentity,
    BenchmarkSpec,
    ComponentIdentity,
)
from .contracts.datasets import DatasetRealizationManifest
from .contracts.prediction import PredictionContract
from .contracts.serialization import canonical_json
from .contracts.shifts import ShiftDeclaration
from .evaluation.protocols import EvaluationResult, PredictionArtifactReference
from .provenance import HISTORICAL_SOURCES
from .registry import BENCHMARKS

GENERATOR = {"name": "powerlifting-state-research-python", "version": __version__}
EXPORT_ROOT = Path(__file__).resolve().parents[2] / "artifacts"


def _document(value: Any) -> str:
    plain = json.loads(canonical_json(value))
    return json.dumps(plain, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def registry_document() -> dict[str, object]:
    benchmarks: list[dict[str, object]] = []
    for spec in BENCHMARKS:
        research_module = (
            ".public_native_research"
            if spec.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
            else ".research"
        )
        research = import_module(spec.python_namespace + research_module).RESEARCH
        benchmarks.append(
            {
                "slug": spec.slug,
                "display_name": spec.display_name,
                "contract_schema_version": spec.contract_schema_version,
                "version": spec.version,
                "benchmark_id": spec.benchmark_id,
                "semantic_digest": spec.semantic_digest,
                "identity_mintable": spec.identity_mintable,
                "historical_specimen_status": spec.historical_specimen_status,
                "historical_qualification_state": spec.historical_qualification_state,
                "completeness_status": spec.completeness_status,
                "public_implementation_status": spec.public_implementation_status,
                "identity_authority": spec.identity_authority,
                "related_benchmark_slugs": spec.related_benchmark_slugs,
                "target_ontology": spec.target_ontology,
                "task_type": spec.task_type,
                "component_references": spec.component_references,
                "semantic_identity_payload": spec.identity_payload,
                "research": research,
                "historical_provenance": HISTORICAL_SOURCES.get(spec.slug),
            }
        )
    worlds = [
        {
            "slug": world.slug,
            "display_name": world.display_name,
            "component_identity_id": world.component_identity_id,
            "historical_aliases": world.historical_aliases,
            "scientific_summary": world.scientific_summary,
        }
        for world in WORLD_DECLARATIONS
    ]
    return {
        "generator": GENERATOR,
        "benchmarks": benchmarks,
        "worlds": worlds,
        "component_provenance": {
            "historical_aliases": SOURCE_COMPONENT_ALIASES,
            "identity_mapping": SOURCE_COMPONENT_IDENTITIES,
        },
    }


def _type_schema(annotation: Any, definitions: dict[str, Any]) -> dict[str, Any]:
    if annotation is Any or annotation is object:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return {"type": "string", "enum": [member.value for member in annotation]}
    if isinstance(annotation, type) and is_dataclass(annotation):
        name = annotation.__name__
        if name not in definitions:
            definitions[name] = {}
            hints = get_type_hints(annotation)
            props: dict[str, Any] = {}
            required: list[str] = []
            for field in fields(annotation):
                props[field.name] = _type_schema(hints[field.name], definitions)
                if field.default is MISSING and field.default_factory is MISSING:
                    required.append(field.name)
            definitions[name] = {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False,
            }
        return {"$ref": f"#/$defs/{name}"}
    if isinstance(annotation, type) and hasattr(annotation, "__required_keys__"):
        hints = get_type_hints(annotation)
        return {
            "type": "object",
            "properties": {name: _type_schema(value, definitions) for name, value in hints.items()},
            "required": sorted(annotation.__required_keys__),
            "additionalProperties": False,
        }
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, UnionType):
        variants = [_type_schema(arg, definitions) for arg in args]
        return {"oneOf": variants}
    if origin is Literal:
        return {"enum": list(args)}
    if origin in (tuple, list, set, frozenset):
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": _type_schema(args[0], definitions)}
        if not args:
            return {"type": "array"}
        return {
            "type": "array",
            "prefixItems": [_type_schema(arg, definitions) for arg in args],
            "minItems": len(args),
            "maxItems": len(args),
        }
    if origin is dict:
        return {"type": "object", "additionalProperties": _type_schema(args[1], definitions)}
    primitive = {str: "string", int: "integer", float: "number", bool: "boolean"}
    if annotation in primitive:
        return {"type": primitive[annotation]}
    return {}


def schema_document(model: type[Any]) -> dict[str, object]:
    definitions: dict[str, Any] = {}
    _type_schema(model, definitions)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/$defs/{model.__name__}",
        "$defs": definitions,
        "x-generator": GENERATOR,
        "x-semantic-validation": (
            "JSON Schema describes record structure only; semantic and cross-field invariants "
            "require the authoritative Python contract validator."
        ),
    }


SCHEMAS: tuple[tuple[str, type[Any]], ...] = (
    ("benchmark-spec.schema.json", BenchmarkSpec),
    ("benchmark-semantic-identity.schema.json", BenchmarkSemanticIdentity),
    ("dataset-realization-manifest.schema.json", DatasetRealizationManifest),
    ("prediction-contract.schema.json", PredictionContract),
    ("shift-declaration.schema.json", ShiftDeclaration),
    ("evaluation-result.schema.json", EvaluationResult),
    ("prediction-artifact-reference.schema.json", PredictionArtifactReference),
    ("artifact-manifest.schema.json", ArtifactManifest),
    ("rights-metadata.schema.json", RightsMetadata),
    ("component-identity.schema.json", ComponentIdentity),
)


def generated_files() -> dict[Path, str]:
    from .benchmarks.latent_capacity_change_with_transient_expression_forecasting.dataset import (
        PublicForecastRow,
    )

    schemas: tuple[tuple[str, type[Any]], ...] = (
        *SCHEMAS,
        ("public-forecast-row.schema.json", PublicForecastRow),
    )
    files = {Path("registries/benchmark-registry.json"): _document(registry_document())}
    files.update(
        {
            Path("schemas") / filename: _document(schema_document(model))
            for filename, model in schemas
        }
    )
    return files


def write_exports(output_dir: Path = EXPORT_ROOT) -> None:
    for relative, content in generated_files().items():
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def check_exports(output_dir: Path = EXPORT_ROOT) -> tuple[str, ...]:
    drift = []
    for relative, content in generated_files().items():
        path = output_dir / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            drift.append(relative.as_posix())
    return tuple(drift)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if checked-in exports drift")
    parser.add_argument("--output-dir", type=Path, default=EXPORT_ROOT)
    args = parser.parse_args()
    if args.check:
        drift = check_exports(args.output_dir)
        if drift:
            print("generated export drift: " + ", ".join(drift), file=sys.stderr)
            return 1
        print(f"PASS: {len(generated_files())} generated exports are current")
        return 0
    write_exports(args.output_dir)
    print(f"wrote {len(generated_files())} generated exports under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
