"""Read-only evidence reconciliation and deterministic RES-277 audit execution."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, fields, replace
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from ..artifacts.hashes import sha256_file, sha256_file_content
from ..artifacts.manifests import RightsMetadata
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dataset as native_dataset,
)
from ..benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    dynamics,
    interventions,
    observations,
    population,
)
from ..contracts.benchmark import BenchmarkIdentityAuthority
from ..contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    ObservationAvailability,
    SplitIdentity,
    SupportSummary,
    TemporalCoverage,
)
from ..contracts.serialization import (
    canonical_json_bytes,
    require_benchmark_digest_match,
    require_dataset_realization_digest_match,
    sha256_record,
)
from ..evaluation.identity import EVALUATION_ID, METRIC_IDENTITIES, TARGETS
from ..evaluation.metrics import MetricName, canonical_target_metrics
from ..evaluation.prediction import PREDICTION_SCHEMA_ID, PredictionRow, parse_prediction_jsonl
from ..provenance import HISTORICAL_SOURCES
from ..registry import BENCHMARKS
from .profiles import VERSION_VALIDITY_PROFILES
from .specifications import (
    ATTACK_SPECS,
    VALIDITY_AXES,
    AuditStatus,
    DiagnosticValue,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = Path("results/audits/res278")
RESULT_FORMAT = "PSR_AUDIT_EXECUTIONS_V1"
_NATIVE_ATTACK_SEEDS = {
    "participant_input_leakage": 281_101,
    "target_identity_contamination": 281_102,
    "temporal_history_disruption": 281_103,
    "training_plan_counterfactual_sensitivity": 281_104,
    "observation_noise_perturbation": 281_105,
}
_RUN_NAMESPACE = "res281"
AUDIT_ROW_COUNT = 96
MODEL_SEEDS = (383_001, 383_002, 383_003)
_SHA256 = "sha256:"
_EXECUTED = {AuditStatus.PASS, AuditStatus.FAIL, AuditStatus.INCONCLUSIVE}
_PUBLIC_RIGHTS = RightsMetadata(
    "CC-BY-4.0",
    "Powerlifting State Research contributors",
    "Public redistribution permitted with attribution.",
)
_RESULT_RIGHTS = RightsMetadata(
    "MIT",
    "Powerlifting State Research contributors",
    "RES-281 audit execution metadata under the repository license.",
)
_ATTACKS = {item.reference: item for item in ATTACK_SPECS}
_AXES = {item.slug: item for item in VALIDITY_AXES}
_BENCHMARKS = {f"{item.slug}@{item.version}": item for item in BENCHMARKS}
_NATIVE_VERSION = "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0"
_NATIVE_DATASET_REALIZATION_ID = (
    "psr:dataset-realization:latent-capacity-transient-iid-production@"
    "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
)
_NATIVE_DATASET_REALIZATION_DIGEST = (
    "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
)
_IID_MANIFEST = Path(
    "data/manifests/realizations/"
    "latent_capacity_change_with_transient_expression_forecasting/iid-production.json"
)
_COMPARATOR_REGISTRY = Path("artifacts/registries/public-native-comparator-registry.json")
_COMPARATOR_MANIFEST = Path("results/manifests/public-native-comparator-suite.json")
_COMPARATOR_CHECKSUMS = Path("results/manifests/public-native-comparator-suite-checksums.json")
_TRAINING_SEAL = Path(
    "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/"
    "public-native-comparator-suite/training-seal.json"
)
_EXPERT_MANIFEST = Path("results/manifests/public-native-temporal-expert.json")
_EXPERT_CHECKSUMS = Path("results/manifests/public-native-temporal-expert-checksums.json")


@dataclass(frozen=True, slots=True)
class EvidenceArtifactReference:
    path: str
    sha256: str
    media_type: str
    rights: RightsMetadata

    def __post_init__(self) -> None:
        relative = PurePosixPath(self.path)
        if (
            not self.path
            or relative.is_absolute()
            or ".." in relative.parts
            or not self.media_type.strip()
        ):
            raise ValueError(
                "evidence artifact needs a safe repository-relative path and media type"
            )
        if not self.sha256.startswith(_SHA256) or len(self.sha256) != 71:
            raise ValueError("evidence artifact needs a full SHA-256 digest")


@dataclass(frozen=True, slots=True)
class AuditExecutionRecord:
    """One version-scoped result state with a detached, non-recursive record identity."""

    attack_spec_ref: str
    benchmark_version: str
    axis_slug: str
    audit_spec_version: str
    execution_format: Literal["PSR_AUDIT_EXECUTION_V1"]
    result_schema: Literal["PSR_AUDIT_RESULT_V1"]
    benchmark_id: str | None
    semantic_digest: str | None
    dataset_spec_id: str | None
    dataset_realization_id: str | None
    dataset_realization_digest: str | None
    task_id: str | None
    qoi_ids: tuple[str, ...]
    evaluation_id: str | None
    configuration: dict[str, DiagnosticValue]
    input_artifacts: tuple[EvidenceArtifactReference, ...]
    permitted_intervention: str | None
    audit_realization_kind: Literal["PUBLIC_DATASET", "INPUT_SELECTION"] | None
    audit_realization_id: str | None
    audit_realization_digest: str | None
    audit_realization_manifest_path: str | None
    run_id: str | None
    source_commit: str | None
    status: AuditStatus
    status_reason: str
    diagnostics: dict[str, DiagnosticValue]
    evidence_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    decision_criteria: tuple[str, ...]
    limitations: tuple[str, ...]
    result_rights: RightsMetadata
    result_artifact_identity: str
    result_artifact_sha256: str

    @classmethod
    def create(cls, **values: Any) -> AuditExecutionRecord:
        values = {
            "execution_format": "PSR_AUDIT_EXECUTION_V1",
            "result_schema": "PSR_AUDIT_RESULT_V1",
            "result_rights": _RESULT_RIGHTS,
            **values,
        }
        identity_payload = {name: value for name, value in values.items()}
        digest = sha256_record(identity_payload)
        attack_slug, attack_version = cast(str, values["attack_spec_ref"]).rsplit("@", 1)
        benchmark_slug = cast(str, values["benchmark_version"]).rsplit("@", 1)[0]
        identity = (
            f"psr:audit-result:{benchmark_slug}-{attack_slug}@{attack_version}~{digest[7:19]}"
        )
        return cls(
            **values,
            result_artifact_identity=identity,
            result_artifact_sha256=digest,
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name not in {"result_artifact_identity", "result_artifact_sha256"}
        }

    def __post_init__(self) -> None:
        attack = _ATTACKS.get(self.attack_spec_ref)
        if attack is None:
            raise ValueError(f"unknown attack specification: {self.attack_spec_ref}")
        benchmark = _BENCHMARKS.get(self.benchmark_version)
        if benchmark is None:
            raise ValueError(f"unknown benchmark version: {self.benchmark_version}")
        axis = _AXES.get(self.axis_slug)
        if (
            axis is None
            or attack.axis_slug != self.axis_slug
            or axis.version != self.audit_spec_version
        ):
            raise ValueError("audit result axis or AuditSpec version conflicts with its attack")
        if (
            self.execution_format != "PSR_AUDIT_EXECUTION_V1"
            or self.result_schema != attack.expected_output_schema
        ):
            raise ValueError("execution record does not emit the registered result schema")
        if self.result_rights.license_expression != "MIT":
            raise ValueError("audit result metadata must use its declared repository license")
        expected_version = self.benchmark_version in attack.applicable_benchmark_versions
        no_hidden_claim = (
            attack.slug == "hidden_test_fairness" and self.benchmark_version == _NATIVE_VERSION
        )
        if self.status is AuditStatus.NOT_APPLICABLE:
            if expected_version and not no_hidden_claim:
                raise ValueError(
                    "NOT_APPLICABLE conflicts with the attack's declared applicability"
                )
        elif not expected_version:
            raise ValueError("result references an attack that is inapplicable to this version")
        if (
            self.status in _EXECUTED
            and benchmark.identity_authority is BenchmarkIdentityAuthority.HISTORICAL_PROJECTION
            and attack.slug != "audit_coverage_accounting"
        ):
            raise ValueError(
                "historical attack execution is blocked without a "
                "version-specific rights-cleared adapter"
            )

        identity = benchmark.semantic_identity
        if identity is None:
            historical = HISTORICAL_SOURCES.get(benchmark.slug)
            components = {} if historical is None else historical.source_component_ids
            expected_dataset = components.get("dataset_spec_id")
            expected_task = components.get("task_id")
            expected_qoi = components.get("qoi_id")
            expected_eval = components.get("evaluation_id")
            expected_qois: tuple[str, ...] = () if expected_qoi is None else (expected_qoi,)
        else:
            expected_dataset = identity.dataset_spec_id
            expected_task = identity.task_id
            expected_qois = identity.qoi_ids
            expected_eval = identity.evaluation_id
        if (
            (self.benchmark_id, self.semantic_digest)
            != (benchmark.benchmark_id, benchmark.semantic_digest)
            or self.dataset_spec_id != expected_dataset
            or self.task_id != expected_task
            or self.qoi_ids != expected_qois
            or self.evaluation_id != expected_eval
        ):
            raise ValueError("audit result contains conflicting scientific identities")
        if self.benchmark_id is not None and self.semantic_digest is not None:
            require_benchmark_digest_match(
                self.benchmark_id, self.semantic_digest, "audit execution benchmark"
            )
        if (self.dataset_realization_id is None) != (self.dataset_realization_digest is None):
            raise ValueError("canonical dataset realization ID and digest must appear together")
        if self.dataset_realization_id is not None and self.dataset_realization_digest is not None:
            require_dataset_realization_digest_match(
                self.dataset_realization_id,
                self.dataset_realization_digest,
                "audit execution dataset realization",
            )
        if self.benchmark_version == _NATIVE_VERSION:
            if (self.dataset_realization_id, self.dataset_realization_digest) != (
                _NATIVE_DATASET_REALIZATION_ID,
                _NATIVE_DATASET_REALIZATION_DIGEST,
            ):
                raise ValueError(
                    "public-native result must use its registered IID DatasetRealization"
                )
        elif self.dataset_realization_id is not None:
            raise ValueError("historical profiles do not mint an executable DatasetRealization")
        if (self.audit_realization_id is None) != (self.audit_realization_digest is None):
            raise ValueError("audit realization ID and digest must appear together")
        if (self.audit_realization_id is None) != (self.audit_realization_kind is None):
            raise ValueError("audit realization identity needs an explicit kind")
        if self.audit_realization_kind == "PUBLIC_DATASET":
            if self.audit_realization_manifest_path is None:
                raise ValueError("generated audit DatasetRealization needs its manifest path")
            if self.audit_realization_id is None or self.audit_realization_digest is None:
                raise ValueError("generated audit DatasetRealization needs an ID and digest")
            require_dataset_realization_digest_match(
                self.audit_realization_id,
                self.audit_realization_digest,
                "independent audit realization",
            )
        elif self.audit_realization_kind == "INPUT_SELECTION":
            if self.audit_realization_manifest_path is not None:
                raise ValueError("input-selection realization is embedded in its execution record")
            expected_digest = sha256_record(
                {
                    "format": "PSR_AUDIT_REALIZATION_V1",
                    "attack_spec_ref": self.attack_spec_ref,
                    "benchmark_version": self.benchmark_version,
                    "dataset_spec_id": self.dataset_spec_id,
                    "dataset_realization_id": self.dataset_realization_id,
                    "dataset_realization_digest": self.dataset_realization_digest,
                    "configuration": self.configuration,
                    "input_artifacts": self.input_artifacts,
                    "permitted_intervention": self.permitted_intervention,
                    "run_id": self.run_id,
                    "source_commit": self.source_commit,
                }
            )
            benchmark_slug = self.benchmark_version.rsplit("@", 1)[0]
            attack_slug = self.attack_spec_ref.rsplit("@", 1)[0]
            expected_id = f"psr:audit-realization:{benchmark_slug}-{attack_slug}@{expected_digest}"
            if (self.audit_realization_digest, self.audit_realization_id) != (
                expected_digest,
                expected_id,
            ):
                raise ValueError("input-selection audit realization identity/hash mismatch")
        if not all((self.status_reason.strip(), self.attack_spec_ref, self.benchmark_version)):
            raise ValueError("audit execution is missing required identity or status text")
        if not isinstance(self.status, AuditStatus):
            raise ValueError("audit execution uses an unknown state")
        paths = {item.path for item in self.input_artifacts}
        if len(paths) != len(self.input_artifacts):
            raise ValueError("audit input artifact paths must be unique")
        if not set(self.evidence_refs) <= paths:
            raise ValueError("evidence references must resolve to hashed input artifacts")
        if any(not key for key in self.diagnostics):
            raise ValueError("diagnostic names must be non-empty")
        if any(
            isinstance(value, float) and not math.isfinite(value)
            for value in self.diagnostics.values()
        ):
            raise ValueError("audit diagnostics must be finite")

        if self.status in _EXECUTED:
            if (
                not self.run_id
                or self.source_commit is None
                or len(self.source_commit) != 40
                or any(char not in "0123456789abcdef" for char in self.source_commit)
                or not self.configuration
                or not isinstance(self.configuration.get("seed"), int)
                or not self.input_artifacts
                or not self.evidence_refs
                or not self.diagnostics
                or not self.permitted_intervention
                or self.permitted_intervention not in attack.permitted_interventions
                or not self.decision_criteria
                or self.audit_realization_id is None
                or self.audit_realization_digest is None
                or self.audit_realization_kind is None
            ):
                raise ValueError(
                    "executed audit results need run provenance, evidence, and criteria"
                )
            if self.missing_evidence:
                raise ValueError("executed results cannot claim missing evidence")
            if self.status is AuditStatus.PASS and all(
                "schema" in item.lower() for item in self.decision_criteria
            ):
                raise ValueError("schema validation alone cannot support PASS")
        else:
            if self.run_id is not None or self.source_commit is not None:
                raise ValueError("non-execution states cannot claim run provenance")
            if self.configuration or self.diagnostics or self.permitted_intervention:
                raise ValueError(
                    "non-execution states cannot carry execution configuration or diagnostics"
                )
            if self.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE:
                if not self.missing_evidence or not self.evidence_refs:
                    raise ValueError("unsupported results need evidence references and named gaps")
            elif self.missing_evidence:
                raise ValueError("only UNSUPPORTED_BY_EVIDENCE may name missing evidence")
            if self.status is AuditStatus.NOT_APPLICABLE and not self.evidence_refs:
                raise ValueError("NOT_APPLICABLE must cite its semantic condition")
            if self.status is not AuditStatus.UNSUPPORTED_BY_EVIDENCE and self.decision_criteria:
                raise ValueError("non-execution states cannot carry measured decision criteria")
            if self.audit_realization_kind is not None:
                raise ValueError("non-execution states cannot claim an audit realization")

        digest = sha256_record(self.identity_payload())
        attack_slug, attack_version = self.attack_spec_ref.rsplit("@", 1)
        benchmark_slug = self.benchmark_version.rsplit("@", 1)[0]
        expected_identity = (
            f"psr:audit-result:{benchmark_slug}-{attack_slug}@{attack_version}~{digest[7:19]}"
        )
        if (
            self.result_artifact_sha256 != digest
            or self.result_artifact_identity != expected_identity
        ):
            raise ValueError("audit result identity or content hash does not match its record")


def read_audit_execution_record(document: dict[str, Any]) -> AuditExecutionRecord:
    """Read an exported execution with the same cross-field checks used at creation."""
    values = dict(document)
    values["status"] = AuditStatus(values["status"])
    for name in (
        "qoi_ids",
        "evidence_refs",
        "missing_evidence",
        "decision_criteria",
        "limitations",
    ):
        values[name] = tuple(values[name])
    values["input_artifacts"] = tuple(
        EvidenceArtifactReference(
            path=item["path"],
            sha256=item["sha256"],
            media_type=item["media_type"],
            rights=RightsMetadata(**item["rights"]),
        )
        for item in values["input_artifacts"]
    )
    values["result_rights"] = RightsMetadata(**values["result_rights"])
    return AuditExecutionRecord(**values)


@dataclass(frozen=True, slots=True)
class _ComparatorRun:
    method: str
    model_id: str
    seed: int
    state: dict[str, Any]
    evaluation: dict[str, Any]
    prediction_rows: tuple[PredictionRow, ...]
    metrics: dict[str, dict[str, float]]


@dataclass(frozen=True, slots=True)
class _M4Evidence:
    artifact_refs: tuple[EvidenceArtifactReference, ...]
    comparator_registry: dict[str, Any]
    run_manifest: dict[str, Any]
    training_seal: dict[str, Any]
    comparator_runs: tuple[_ComparatorRun, ...]
    expert_metrics: dict[tuple[str, int], dict[str, dict[str, float]]]
    expert_predictions: dict[tuple[str, int], tuple[PredictionRow, ...]]
    expert_ensemble_metrics: dict[str, dict[str, float]]


def _rights_for_path(root: Path, path: str) -> RightsMetadata:
    ledger = root / "provenance/PUBLIC_FILE_ORIGINS.csv"
    with ledger.open(newline="", encoding="utf-8") as file:
        row = next((item for item in csv.DictReader(file) if item["path"] == path), None)
    if row is None:
        raise ValueError(f"public-file-origin ledger has no rights entry for {path}")
    return RightsMetadata(
        row["license_expression"],
        row["owner"],
        f"{row['origin_class']}: {row['purpose']}",
    )


def _media_type(path: str) -> str:
    if path.endswith(".jsonl"):
        return "application/x-ndjson"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".csv"):
        return "text/csv"
    return "text/plain"


def evidence_artifact(
    root: Path,
    path: str,
    *,
    expected_sha256: str | None = None,
    rights: RightsMetadata | None = None,
    source_path: Path | None = None,
) -> EvidenceArtifactReference:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("evidence paths must stay inside the repository")
    file_path = root.joinpath(*relative.parts) if source_path is None else source_path
    resolved_root = root.resolve()
    resolved_file = file_path.resolve(strict=True)
    try:
        resolved_file.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("evidence artifact resolves outside the repository") from error
    if not resolved_file.is_file():
        raise ValueError(f"evidence artifact is not a file: {path}")
    digest = sha256_file_content(resolved_file)
    if expected_sha256 is not None:
        expected = (
            expected_sha256 if expected_sha256.startswith(_SHA256) else _SHA256 + expected_sha256
        )
        if digest != expected:
            raise ValueError(f"artifact SHA-256 mismatch: {path}")
    return EvidenceArtifactReference(
        path,
        digest,
        _media_type(path),
        rights if rights is not None else _rights_for_path(root, path),
    )


def reconcile_registry_evidence(root: Path = ROOT) -> tuple[EvidenceArtifactReference, ...]:
    """Verify exported registries, profiles, applicability and all cited public evidence."""
    from ..exports import check_exports

    drift = check_exports(root / "artifacts")
    if drift:
        raise ValueError("generated audit registries or schemas are stale: " + ", ".join(drift))
    axes_path = "artifacts/registries/validity-axis-registry.json"
    attacks_path = "artifacts/registries/attack-contract-registry.json"
    profiles_path = "artifacts/registries/version-validity-profiles.json"
    axis_doc = json.loads((root / axes_path).read_text(encoding="utf-8"))
    attack_doc = json.loads((root / attacks_path).read_text(encoding="utf-8"))
    profile_doc = json.loads((root / profiles_path).read_text(encoding="utf-8"))
    if [item["slug"] for item in axis_doc["axes"]] != [item.slug for item in VALIDITY_AXES]:
        raise ValueError("validity-axis registry differs from typed contracts")
    if [item["slug"] for item in attack_doc["attacks"]] != [item.slug for item in ATTACK_SPECS]:
        raise ValueError("attack registry differs from typed contracts")
    if profile_doc.get("profile_version") != "1.0.0":
        raise ValueError("profile registry version differs from typed contracts")
    expected_profiles = {
        f"{item.benchmark_slug}@{item.benchmark_version}": item
        for item in VERSION_VALIDITY_PROFILES
    }
    exported_profiles = {
        f"{item['benchmark_slug']}@{item['benchmark_version']}": item
        for item in profile_doc["profiles"]
    }
    if set(exported_profiles) != set(expected_profiles):
        raise ValueError("version-validity profile selectors differ from typed contracts")
    refs: dict[str, EvidenceArtifactReference] = {}
    for path in (
        axes_path,
        attacks_path,
        profiles_path,
        "artifacts/registries/benchmark-registry.json",
    ):
        refs[path] = evidence_artifact(root, path)
    for selector, profile in expected_profiles.items():
        if selector not in _BENCHMARKS:
            raise ValueError(f"profile references an unregistered benchmark version: {selector}")
        attacks = {result.attack_spec_refs[0]: result for result in profile.attack_results}
        expected = {attack.reference for attack in ATTACK_SPECS}
        if set(attacks) != expected or len(attacks) != len(profile.attack_results):
            raise ValueError(f"profile attack ledger is incomplete or duplicated: {selector}")
        for attack in ATTACK_SPECS:
            result = attacks[attack.reference]
            applies = selector in attack.applicable_benchmark_versions
            if not applies and result.status is not AuditStatus.NOT_APPLICABLE:
                raise ValueError(
                    f"profile status conflicts with attack scope: {selector}/{attack.slug}"
                )
        for result in (*profile.axis_results, *profile.attack_results):
            for path in result.evidence_refs:
                refs.setdefault(path, evidence_artifact(root, path))
    return tuple(refs[path] for path in sorted(refs))


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    value = json.loads((root / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.as_posix()}")
    return value


def _metrics_from_evaluation(document: dict[str, Any]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    if document.get("evaluation_id") != EVALUATION_ID:
        raise ValueError("M4 EvaluationResult does not use the canonical RES-271 evaluation")
    if document.get("status") != "COMPLETE":
        raise ValueError("M4 EvaluationResult is not complete")
    metric_identities = {
        item["metric_id"]: item["metric"] for item in document.get("metric_identities", [])
    }
    expected_metric_identities = {item.metric_id: item.metric.value for item in METRIC_IDENTITIES}
    if metric_identities != expected_metric_identities:
        raise ValueError("M4 EvaluationResult metric identities differ from RES-271")
    for target in document.get("targets", []):
        values: dict[str, float] = {}
        for metric in target.get("metrics", []):
            if metric.get("status") != "COMPUTED" or metric.get("value") is None:
                raise ValueError("M4 EvaluationResult has a non-computed target metric")
            values[metric["metric"]] = float(metric["value"])
        if set(values) != {item.metric.value for item in METRIC_IDENTITIES}:
            raise ValueError("M4 EvaluationResult metric set differs from RES-271")
        output[target["target"]] = values
    if set(output) != set(TARGETS):
        raise ValueError("M4 EvaluationResult target set differs from the benchmark")
    return output


def _dataset_manifest(root: Path) -> tuple[dict[str, Any], DatasetRealizationManifest]:
    path = root / _IID_MANIFEST
    raw = json.loads(path.read_text(encoding="utf-8"))
    identity = {
        key: value
        for key, value in raw.items()
        if key not in {"identity_id", "realization_digest", "manifest_digest"}
    }
    identity_payload = {
        key: value for key, value in identity.items() if key not in {"provenance", "rights"}
    }
    realization_digest = sha256_record(identity_payload)
    manifest_digest = sha256_record(identity)
    realization_id = raw["realization_id"]
    identity_id = f"psr:dataset-realization:{realization_id}@{realization_digest}"
    if (
        raw.get("realization_digest") != realization_digest
        or raw.get("manifest_digest") != manifest_digest
        or raw.get("identity_id") != identity_id
    ):
        raise ValueError("public IID DatasetRealization manifest identity is inconsistent")
    manifest = DatasetRealizationManifest(
        dataset_spec_id=raw["dataset_spec_id"],
        realization_id=realization_id,
        generator_identity=raw["generator_identity"],
        source_identity=raw["source_identity"],
        seeds=tuple((item[0], item[1]) for item in raw["seeds"]),
        replicate_ids=tuple(raw["replicate_ids"]),
        entity_count=raw["entity_count"],
        row_count=raw["row_count"],
        split_identities=tuple(SplitIdentity(**item) for item in raw["split_identities"]),
        artifact_hashes=tuple(ArtifactHash(**item) for item in raw["artifact_hashes"]),
        schema_identity=raw["schema_identity"],
        temporal_coverage=TemporalCoverage(**raw["temporal_coverage"]),
        realized_intervention_support=tuple(
            SupportSummary(**item) for item in raw["realized_intervention_support"]
        ),
        observation_availability=tuple(
            ObservationAvailability(**item) for item in raw["observation_availability"]
        ),
        provenance=raw["provenance"],
        rights=RightsMetadata(**raw["rights"]),
    )
    if (
        manifest.realization_digest != realization_digest
        or manifest.manifest_digest != manifest_digest
    ):
        raise ValueError("typed public IID DatasetRealization does not match its manifest")
    return raw, manifest


def _load_m4_evidence(root: Path) -> _M4Evidence:
    from ..models.comparators import MODEL_SPECS

    registry = _read_json(root, _COMPARATOR_REGISTRY)
    manifest = _read_json(root, _COMPARATOR_MANIFEST)
    checksum_index = _read_json(root, _COMPARATOR_CHECKSUMS)
    seal = _read_json(root, _TRAINING_SEAL)
    iid_raw, iid_manifest = _dataset_manifest(root)
    expert = _read_json(root, _EXPERT_MANIFEST)
    expert_checksums = _read_json(root, _EXPERT_CHECKSUMS)
    if checksum_index.get("run_manifest_sha256") != sha256_file_content(
        root / _COMPARATOR_MANIFEST
    ):
        raise ValueError("M4 checksum index does not bind its run manifest")
    entries: dict[str, dict[str, Any]] = {}
    refs: dict[str, EvidenceArtifactReference] = {}
    for entry in checksum_index.get("entries", []):
        path = entry["path"]
        if path in entries:
            raise ValueError(f"M4 checksum index duplicates {path}")
        artifact = evidence_artifact(
            root,
            path,
            expected_sha256=entry["sha256"],
        )
        if (root / path).stat().st_size != entry["size_bytes"]:
            raise ValueError(f"M4 artifact size mismatch: {path}")
        entries[path] = entry
        refs[path] = artifact
    if not entries or len(entries) != len(checksum_index.get("entries", [])):
        raise ValueError("M4 checksum index is empty or malformed")
    for path in (_COMPARATOR_REGISTRY.as_posix(), _COMPARATOR_MANIFEST.as_posix()):
        if path not in entries:
            raise ValueError(f"M4 checksum index omits {path}")
    refs[_COMPARATOR_CHECKSUMS.as_posix()] = evidence_artifact(
        root, _COMPARATOR_CHECKSUMS.as_posix()
    )
    refs[_IID_MANIFEST.as_posix()] = evidence_artifact(root, _IID_MANIFEST.as_posix())
    for ref in (
        expert_checksums["run_manifest"],
        expert_checksums["checkpoint_publication_index"],
        expert_checksums["source_inventory"],
        expert_checksums["verification_receipt"],
    ):
        artifact = evidence_artifact(root, ref["path"], expected_sha256=ref["sha256"])
        refs[ref["path"]] = artifact
    refs[_EXPERT_MANIFEST.as_posix()] = evidence_artifact(root, _EXPERT_MANIFEST.as_posix())
    for item in expert_checksums.get("copied_artifacts", []):
        if item["path"] in entries:
            if entries[item["path"]]["sha256"] != item["sha256"]:
                raise ValueError(f"M4 expert checksum indexes conflict: {item['path']}")
        else:
            refs[item["path"]] = evidence_artifact(
                root, item["path"], expected_sha256=item["sha256"]
            )
    if (
        manifest.get("registry", {}).get("sha256", "").removeprefix(_SHA256)
        != entries[_COMPARATOR_REGISTRY.as_posix()]["sha256"]
    ):
        raise ValueError("M4 run manifest and comparator registry hashes conflict")
    if (
        manifest.get("registry", {}).get("path") != _COMPARATOR_REGISTRY.as_posix()
        or registry.get("training_protocol_id") != manifest.get("protocol_id")
        or registry.get("training_protocol_path") != manifest.get("protocol_path")
        or registry.get("target_metrics_path") != manifest.get("target_metrics_path")
    ):
        raise ValueError("M4 registry and run-manifest protocol/metric references conflict")
    declared_data_hashes = {
        item["artifact_id"]: item["sha256"] for item in iid_raw["artifact_hashes"]
    }
    if (
        set(declared_data_hashes) != {"train", "validation"}
        or manifest.get("train_sha256") != declared_data_hashes["train"]
        or manifest.get("validation_sha256") != declared_data_hashes["validation"]
    ):
        raise ValueError("M4 run manifest train/validation hashes conflict with the realization")
    seal_metadata = manifest.get("validation_isolation", {})
    if seal_metadata.get("seal_path") != _TRAINING_SEAL.as_posix() or seal_metadata.get(
        "seal_sha256"
    ) != sha256_file_content(root / _TRAINING_SEAL):
        raise ValueError("M4 run manifest does not bind the checked fit-seal artifact")

    native = _BENCHMARKS[_NATIVE_VERSION]
    identity = native.semantic_identity
    if identity is None:
        raise ValueError("public-native benchmark identity is missing")
    protocol_path = Path(registry["training_protocol_path"])
    if protocol_path.as_posix() not in entries:
        raise ValueError("M4 checksum index omits the comparator training protocol")
    protocol_document = _read_json(root, protocol_path)
    protocol = protocol_document.get("protocol", {})
    if (
        protocol_document.get("training_protocol_id") != registry.get("training_protocol_id")
        or protocol_document.get("training_protocol_id") != manifest.get("protocol_id")
        or protocol_document.get("protocol_digest") != sha256_record(protocol)
        or protocol.get("benchmark_id") != native.benchmark_id
        or protocol.get("benchmark_digest") != native.semantic_digest
        or protocol.get("dataset_spec_id") != identity.dataset_spec_id
        or protocol.get("dataset_realization_id") != iid_manifest.identity_id
        or protocol.get("dataset_realization_digest") != iid_manifest.realization_digest
        or protocol.get("evaluation_id") != EVALUATION_ID
        or tuple(protocol.get("seeds", ())) != MODEL_SEEDS
    ):
        raise ValueError("M4 comparator training protocol conflicts with the frozen identities")
    for source, key in (
        (registry, "benchmark_id"),
        (manifest, "benchmark_id"),
        (seal, "dataset_realization_id"),
    ):
        expected = native.benchmark_id if key == "benchmark_id" else iid_manifest.identity_id
        if source.get(key) != expected:
            raise ValueError(f"M4 scientific identity mismatch for {key}")
    if (
        registry.get("benchmark_digest") != native.semantic_digest
        or manifest.get("benchmark_digest") != native.semantic_digest
    ):
        raise ValueError("M4 benchmark semantic digest conflicts with the typed registry")
    for source in (registry, manifest, seal):
        if (
            source.get("dataset_realization_id") != iid_manifest.identity_id
            or source.get("dataset_realization_digest") != iid_manifest.realization_digest
        ):
            raise ValueError("M4 DatasetRealization identity conflicts with its manifest")
    for source in (registry, manifest):
        if (
            source.get("dataset_spec_id") != identity.dataset_spec_id
            or source.get("evaluation_id") != EVALUATION_ID
        ):
            raise ValueError("M4 DatasetSpec or Evaluation identity conflicts with the benchmark")
    if (
        seal.get("canonical_validation_accessed") is not False
        or manifest.get("validation_isolation", {}).get(
            "fit_artifacts_sealed_before_validation_access"
        )
        is not True
    ):
        raise ValueError("M4 training seal does not establish validation isolation")
    if manifest.get("validation_isolation", {}).get("evaluation_after_seal") is not True:
        raise ValueError("M4 evaluation did not follow the fit seal")

    specs = {item.method: item.model_id for item in MODEL_SPECS}
    comparator_runs: list[_ComparatorRun] = []
    row_ids: tuple[str, ...] | None = None
    receipts = {(item["method"], item["seed"]): item for item in seal.get("fitted_instances", [])}
    for comparator in registry.get("comparators", []):
        method = comparator["semantics"]["method"]
        model_id = comparator["model_id"]
        if method not in specs or specs[method] != model_id:
            raise ValueError(f"M4 comparator identity is not registered: {method}")
        if (
            comparator["semantics"].get("task_id") != identity.task_id
            or comparator["semantics"].get("qoi_id") not in identity.qoi_ids
        ):
            raise ValueError(f"M4 comparator task/QOI identity mismatch: {method}")
        for run in comparator.get("runs", []):
            seed = run["seed"]
            for key, hash_key in (
                ("prediction_path", "prediction_sha256"),
                ("evaluation_result_path", "evaluation_result_sha256"),
                ("fitted_instance_path", "fitted_instance_sha256"),
            ):
                path = run[key]
                if path not in entries or entries[path]["sha256"] != run[hash_key].removeprefix(
                    _SHA256
                ):
                    raise ValueError(
                        f"M4 run artifact reference conflicts with checksum index: {path}"
                    )
            fitted_path = root / run["fitted_instance_path"]
            state = json.loads(fitted_path.read_text(encoding="utf-8"))
            state_hash = sha256_file_content(fitted_path)
            if (
                state_hash != run["fitted_instance_sha256"]
                or state.get("model_id") != model_id
                or state.get("seed") != seed
                or state.get("training_protocol_id") != registry.get("training_protocol_id")
                or state.get("dataset_realization_id") != iid_manifest.identity_id
                or state.get("dataset_realization_digest") != iid_manifest.realization_digest
            ):
                raise ValueError(
                    f"M4 fitted-instance metadata mismatch: {run['fitted_instance_path']}"
                )
            fit_id = (
                f"psr:fitted-instance:{Path(run['fitted_instance_path']).parent.name}-seed-{seed}"
                f"@{state_hash}"
            )
            # Registry IDs are authoritative; compare their digest and the EvaluationResult binding.
            if state_hash not in run["fitted_instance_id"] or run["fitted_instance_id"] != fit_id:
                raise ValueError(
                    f"M4 fitted-instance identity mismatch: {run['fitted_instance_path']}"
                )
            receipt = receipts.get((method, seed))
            if receipt is None or (
                receipt.get("fitted_instance_id") != run["fitted_instance_id"]
                or receipt.get("fitted_instance_sha256") != run["fitted_instance_sha256"]
                or receipt.get("training_validation_accessed") is not False
            ):
                raise ValueError(f"M4 fit seal omits or conflicts with {method}/{seed}")
            evaluation = json.loads(
                (root / run["evaluation_result_path"]).read_text(encoding="utf-8")
            )
            if (
                f"psr:evaluation-result@{sha256_record(evaluation)}" != run["evaluation_result_id"]
                or evaluation.get("benchmark_id") != native.benchmark_id
                or evaluation.get("benchmark_spec_digest") != native.semantic_digest
                or evaluation.get("dataset_realization_id") != iid_manifest.identity_id
                or evaluation.get("dataset_realization_digest") != iid_manifest.realization_digest
                or evaluation.get("evaluation_id") != EVALUATION_ID
                or evaluation.get("model", {}).get("model_id") != model_id
                or evaluation.get("training_protocol", {}).get("training_protocol_id")
                != registry.get("training_protocol_id")
                or evaluation.get("prediction_artifact", {}).get("content_sha256")
                != run["prediction_sha256"]
                or evaluation.get("prediction_artifact", {}).get("benchmark_id")
                != native.benchmark_id
                or evaluation.get("prediction_artifact", {}).get("benchmark_spec_digest")
                != native.semantic_digest
                or evaluation.get("prediction_artifact", {}).get("dataset_realization_id")
                != iid_manifest.identity_id
                or evaluation.get("prediction_artifact", {}).get("dataset_realization_digest")
                != iid_manifest.realization_digest
                or evaluation.get("prediction_artifact", {}).get("model_id") != model_id
                or evaluation.get("prediction_artifact", {}).get("output_schema_identity")
                != PREDICTION_SCHEMA_ID
                or evaluation.get("prediction_artifact", {})
                .get("rights", {})
                .get("license_expression")
                != "MIT"
                or evaluation.get("fitted_instance", {}).get("fitted_instance_id")
                != run["fitted_instance_id"]
                or evaluation.get("rights", {}).get("license_expression") != "MIT"
            ):
                raise ValueError(
                    f"M4 EvaluationResult identity mismatch: {run['evaluation_result_path']}"
                )
            prediction = parse_prediction_jsonl((root / run["prediction_path"]).read_bytes())
            if len(prediction) != evaluation["prediction_artifact"]["row_count"]:
                raise ValueError(f"M4 prediction row count mismatch: {run['prediction_path']}")
            if row_ids is None:
                row_ids = tuple(item.row_id for item in prediction)
            elif tuple(item.row_id for item in prediction) != row_ids:
                raise ValueError("M4 predictions are not aligned to the same canonical rows")
            metrics = _metrics_from_evaluation(evaluation)
            for target in TARGETS:
                registry_values = {
                    item["metric"]: item["value"]
                    for item in next(
                        item for item in run["target_metrics"] if item["target"] == target
                    )["metrics"]
                }
                if metrics[target] != registry_values:
                    raise ValueError(
                        f"M4 metric registry differs from EvaluationResult: {method}/{seed}"
                    )
            comparator_runs.append(
                _ComparatorRun(method, model_id, seed, state, evaluation, prediction, metrics)
            )
    if len(comparator_runs) != 18 or set(receipts) != {
        (run.method, run.seed) for run in comparator_runs
    }:
        raise ValueError("M4 registry or fit seal does not contain the frozen 18 comparator runs")

    scientific = expert.get("scientific_identity", {})
    if any(
        scientific.get(key) != expected
        for key, expected in (
            ("benchmark_spec_id", native.benchmark_id),
            ("benchmark_spec_digest", native.semantic_digest),
            ("dataset_spec_id", identity.dataset_spec_id),
            ("dataset_realization_id", iid_manifest.identity_id),
            ("dataset_realization_digest", iid_manifest.realization_digest),
            ("evaluation_id", EVALUATION_ID),
        )
    ):
        raise ValueError("immutable temporal-expert evidence has conflicting M4 identities")
    expert_metrics: dict[tuple[str, int], dict[str, dict[str, float]]] = {}
    expert_predictions: dict[tuple[str, int], tuple[PredictionRow, ...]] = {}
    expert_model = scientific["model_id"]
    for run in expert.get("checkpoints", []):
        seed = run["seed"]
        result_ref = run["evaluation_result"]
        prediction_ref = run["prediction"]
        for ref in (result_ref, prediction_ref, run["fitted_instance_manifest"]):
            if ref["path"] not in entries or entries[ref["path"]]["sha256"] != ref["sha256"]:
                raise ValueError(f"immutable temporal-expert artifact hash mismatch: {ref['path']}")
        result_envelope = json.loads((root / result_ref["path"]).read_text(encoding="utf-8"))
        evaluation = result_envelope.get("result")
        if not isinstance(evaluation, dict):
            raise ValueError(
                f"immutable temporal-expert result envelope is invalid: {result_ref['path']}"
            )
        if (
            result_envelope.get("result_id") != result_ref["result_id"]
            or f"psr:evaluation-result@{sha256_record(evaluation)}" != result_ref["result_id"]
            or evaluation.get("model", {}).get("model_id") != expert_model
            or evaluation.get("evaluation_id") != EVALUATION_ID
            or evaluation.get("benchmark_id") != native.benchmark_id
            or evaluation.get("dataset_realization_id") != iid_manifest.identity_id
        ):
            raise ValueError(
                f"immutable temporal-expert EvaluationResult mismatch: {result_ref['path']}"
            )
        prediction = parse_prediction_jsonl((root / prediction_ref["path"]).read_bytes())
        if row_ids is not None and tuple(item.row_id for item in prediction) != row_ids:
            raise ValueError("temporal-expert predictions do not align with comparator rows")
        expert_metrics[("public-native-temporal-expert", seed)] = _metrics_from_evaluation(
            evaluation
        )
        expert_predictions[("public-native-temporal-expert", seed)] = prediction
    ensemble = expert["ensemble"]
    result_ref = ensemble["evaluation_result"]
    if (
        result_ref["path"] not in entries
        or entries[result_ref["path"]]["sha256"] != result_ref["sha256"]
    ):
        raise ValueError(
            "immutable temporal-expert ensemble result is absent from M4 checksum index"
        )
    ensemble_envelope = json.loads((root / result_ref["path"]).read_text(encoding="utf-8"))
    ensemble_result = ensemble_envelope.get("result")
    if not isinstance(ensemble_result, dict):
        raise ValueError("immutable temporal-expert ensemble result envelope is invalid")
    if (
        ensemble_envelope.get("result_id") != result_ref["result_id"]
        or f"psr:evaluation-result@{sha256_record(ensemble_result)}" != result_ref["result_id"]
        or ensemble_result.get("model", {}).get("model_id") != expert_model
        or ensemble_result.get("evaluation_id") != EVALUATION_ID
    ):
        raise ValueError("immutable temporal-expert ensemble EvaluationResult identity mismatch")

    return _M4Evidence(
        tuple(refs[path] for path in sorted(refs)),
        registry,
        manifest,
        seal,
        tuple(comparator_runs),
        expert_metrics,
        expert_predictions,
        _metrics_from_evaluation(ensemble_result),
    )


def _version_identities(
    benchmark_version: str,
) -> tuple[str | None, str | None, tuple[str, ...], str | None]:
    benchmark = _BENCHMARKS[benchmark_version]
    identity = benchmark.semantic_identity
    if identity is not None:
        return identity.dataset_spec_id, identity.task_id, identity.qoi_ids, identity.evaluation_id
    historical = HISTORICAL_SOURCES.get(benchmark.slug)
    source_ids = {} if historical is None else historical.source_component_ids
    qoi_id = source_ids.get("qoi_id")
    return (
        source_ids.get("dataset_spec_id"),
        source_ids.get("task_id"),
        () if qoi_id is None else (qoi_id,),
        source_ids.get("evaluation_id"),
    )


def _refs_for_profile(root: Path, profile: Any) -> tuple[EvidenceArtifactReference, ...]:
    paths = {
        path
        for item in (*profile.axis_results, *profile.attack_results)
        for path in item.evidence_refs
    }
    return tuple(evidence_artifact(root, path) for path in sorted(paths))


def _git_commit(root: Path) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise ValueError("audit execution requires a clean source worktree")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run_id(
    attack_ref: str,
    benchmark_version: str,
    source_commit: str,
    configuration: dict[str, DiagnosticValue],
    artifacts: tuple[EvidenceArtifactReference, ...],
    audit_realization_digest: str | None,
) -> str:
    attack_slug = attack_ref.split("@", 1)[0]
    digest = sha256_record(
        {
            "attack_spec_ref": attack_ref,
            "benchmark_version": benchmark_version,
            "source_commit": source_commit,
            "configuration": configuration,
            "inputs": tuple((item.path, item.sha256) for item in artifacts),
            "audit_realization_digest": audit_realization_digest,
        }
    )
    return f"{_RUN_NAMESPACE}-{attack_slug}-{digest[7:19]}"


def _record(
    *,
    benchmark_version: str,
    attack_slug: str,
    status: AuditStatus,
    reason: str,
    input_artifacts: tuple[EvidenceArtifactReference, ...],
    missing: tuple[str, ...] = (),
    diagnostics: dict[str, DiagnosticValue] | None = None,
    source_commit: str | None = None,
    seed: int | None = None,
    intervention: str | None = None,
    audit_realization: DatasetRealizationManifest | None = None,
    audit_manifest_path: str | None = None,
    decision_criteria: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
    extra_configuration: dict[str, DiagnosticValue] | None = None,
) -> AuditExecutionRecord:
    attack_ref = f"{attack_slug}@1.0.0"
    if attack_ref not in _ATTACKS:
        raise ValueError(f"unknown attack specification: {attack_ref}")
    benchmark = _BENCHMARKS[benchmark_version]
    axis = next(item for item in VALIDITY_AXES if item.slug == _ATTACKS[attack_ref].axis_slug)
    dataset_spec, task_id, qoi_ids, evaluation_id = _version_identities(benchmark_version)
    evidence_refs = tuple(item.path for item in input_artifacts)
    configuration: dict[str, DiagnosticValue] = {}
    run_id = None
    commit = None
    audit_realization_kind: Literal["PUBLIC_DATASET", "INPUT_SELECTION"] | None = None
    audit_realization_id = None
    audit_realization_digest = None
    realization_manifest_path = None
    if status in _EXECUTED:
        if source_commit is None or seed is None or intervention is None:
            raise ValueError(
                "executed audit builder needs source commit, deterministic seed, and intervention"
            )
        configuration = {"seed": seed, **(extra_configuration or {})}
        commit = source_commit
        audit_digest = None if audit_realization is None else audit_realization.realization_digest
        run_id = _run_id(
            attack_ref, benchmark_version, commit, configuration, input_artifacts, audit_digest
        )
        if audit_realization is not None:
            audit_realization_kind = "PUBLIC_DATASET"
            audit_realization_id = audit_realization.identity_id
            audit_realization_digest = audit_realization.realization_digest
            realization_manifest_path = audit_manifest_path
        else:
            audit_realization_kind = "INPUT_SELECTION"
            audit_realization_payload = {
                "format": "PSR_AUDIT_REALIZATION_V1",
                "attack_spec_ref": attack_ref,
                "benchmark_version": benchmark_version,
                "dataset_spec_id": dataset_spec,
                "dataset_realization_id": (
                    _NATIVE_DATASET_REALIZATION_ID if benchmark_version == _NATIVE_VERSION else None
                ),
                "dataset_realization_digest": (
                    _NATIVE_DATASET_REALIZATION_DIGEST
                    if benchmark_version == _NATIVE_VERSION
                    else None
                ),
                "configuration": configuration,
                "input_artifacts": input_artifacts,
                "permitted_intervention": intervention,
                "run_id": run_id,
                "source_commit": commit,
            }
            audit_realization_digest = sha256_record(audit_realization_payload)
            audit_realization_id = (
                f"psr:audit-realization:{benchmark_version.rsplit('@', 1)[0]}-{attack_slug}"
                f"@{audit_realization_digest}"
            )
    return AuditExecutionRecord.create(
        attack_spec_ref=attack_ref,
        benchmark_version=benchmark_version,
        axis_slug=axis.slug,
        audit_spec_version=axis.audit_spec.version,
        benchmark_id=benchmark.benchmark_id,
        semantic_digest=benchmark.semantic_digest,
        dataset_spec_id=dataset_spec,
        dataset_realization_id=(
            _NATIVE_DATASET_REALIZATION_ID if benchmark_version == _NATIVE_VERSION else None
        ),
        dataset_realization_digest=(
            _NATIVE_DATASET_REALIZATION_DIGEST if benchmark_version == _NATIVE_VERSION else None
        ),
        task_id=task_id,
        qoi_ids=qoi_ids,
        evaluation_id=evaluation_id,
        configuration=configuration,
        input_artifacts=input_artifacts,
        permitted_intervention=intervention if status in _EXECUTED else None,
        audit_realization_kind=audit_realization_kind,
        audit_realization_id=audit_realization_id,
        audit_realization_digest=audit_realization_digest,
        audit_realization_manifest_path=realization_manifest_path,
        run_id=run_id,
        source_commit=commit,
        status=status,
        status_reason=reason,
        diagnostics={} if diagnostics is None else diagnostics,
        evidence_refs=evidence_refs,
        missing_evidence=missing,
        decision_criteria=decision_criteria,
        limitations=limitations,
    )


def _manifest_bytes(manifest: DatasetRealizationManifest) -> bytes:
    value = json.loads(manifest.canonical_serialization)
    value["identity_id"] = manifest.identity_id
    value["realization_digest"] = manifest.realization_digest
    value["manifest_digest"] = manifest.manifest_digest
    return canonical_json_bytes(value) + b"\n"


def _row_bytes(rows: tuple[native_dataset.PublicForecastRow, ...]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _audit_rows(
    seed: int, realization_id: str
) -> tuple[
    native_dataset.GenerationConfig,
    tuple[native_dataset.PublicForecastRow, ...],
    dict[str, population.AthleteProfile],
]:
    config = native_dataset.GenerationConfig(
        train_rows=12,
        validation_rows=AUDIT_ROW_COUNT,
        population_seed=seed,
        intervention_seed=seed + 1,
        observation_seed=seed + 2,
        split_seed=seed + 3,
        serialization_seed=seed + 4,
    )
    raw_rows = tuple(
        row for split, row in native_dataset.iter_public_rows(config) if split == "validation"
    )
    if len(raw_rows) != AUDIT_ROW_COUNT:
        raise ValueError("native generator did not produce the declared audit sample size")
    population_rng = random.Random(config.population_seed)
    population_by_id = {
        f"entity-{index:06d}": population.sample_athlete(index, population_rng)
        for index in range(config.train_rows + config.validation_rows)
    }
    rows = tuple(
        replace(
            row,
            row_id=f"{realization_id}-{row.row_id}",
            inputs=replace(row.inputs, entity_id=f"{realization_id}-{row.inputs.entity_id}"),
        )
        for row in raw_rows
    )
    return config, rows, population_by_id


def _artifact_from_staging(
    root: Path,
    staging: Path,
    final_path: str,
    temporary_path: Path,
) -> EvidenceArtifactReference:
    return EvidenceArtifactReference(
        final_path,
        sha256_file_content(temporary_path),
        _media_type(final_path),
        _PUBLIC_RIGHTS,
    )


def _write_audit_realization(
    root: Path,
    staging: Path,
    output_rel: Path,
    attack_slug: str,
    seed: int,
    config: native_dataset.GenerationConfig,
    baseline: tuple[native_dataset.PublicForecastRow, ...],
    conditions: tuple[tuple[str, tuple[native_dataset.PublicForecastRow, ...]], ...],
    intervention_description: str,
    source_commit: str,
    extra_seeds: tuple[tuple[str, int], ...] = (),
) -> tuple[DatasetRealizationManifest, str, tuple[EvidenceArtifactReference, ...]]:
    realization_id = f"{_RUN_NAMESPACE}-{attack_slug.replace('_', '-')}-seed-{seed}"
    folder = staging / "realizations" / realization_id
    folder.mkdir(parents=True)
    final_folder = (output_rel / "realizations" / realization_id).as_posix()
    artifacts: list[ArtifactHash] = []
    refs: list[EvidenceArtifactReference] = []
    conditions_all = (("baseline", baseline), *conditions)
    for name, rows in conditions_all:
        path = folder / f"{name}.jsonl"
        content = _row_bytes(rows)
        path.write_bytes(content)
        digest = sha256_file(path)
        artifacts.append(ArtifactHash(name, digest, "application/x-ndjson"))
        refs.append(_artifact_from_staging(root, staging, f"{final_folder}/{name}.jsonl", path))
    total_rows = sum(len(rows) for _, rows in conditions_all)
    manifest = DatasetRealizationManifest(
        dataset_spec_id=native_dataset.DATASET_SPEC_ID,
        realization_id=realization_id,
        generator_identity=(
            f"{native_dataset.GENERATOR_IDENTITY};audit-source-commit={source_commit};"
            f"audit-configuration-sha256={sha256_record(config)}"
        ),
        source_identity=f"PSR_AUDIT_HARNESS_V1:{attack_slug}",
        seeds=(
            ("population", config.population_seed),
            ("intervention_plan", config.intervention_seed),
            ("observation_noise", config.observation_seed),
            ("split_allocation", config.split_seed),
            ("serialization", config.serialization_seed),
            ("audit", seed),
            *extra_seeds,
        ),
        replicate_ids=tuple(name for name, _ in conditions_all),
        entity_count=AUDIT_ROW_COUNT,
        row_count=total_rows,
        split_identities=tuple(
            SplitIdentity(name, "independent audit realization condition", len(rows), len(rows))
            for name, rows in conditions_all
        ),
        artifact_hashes=tuple(artifacts),
        schema_identity=native_dataset.SCHEMA_IDENTITY,
        temporal_coverage=TemporalCoverage("day", 0, 279),
        realized_intervention_support=(
            SupportSummary("audit_intervention", intervention_description),
        ),
        observation_availability=tuple(
            ObservationAvailability(
                field,
                total_rows * len(observations.HISTORY_OBSERVATION_DAYS) * len(population.LIFTS),
                0,
            )
            for field in ("assessment_kg", "prescribed_load_kg", "velocity_mps")
        ),
        provenance=(
            "Independent rows generated by the public-native IID generator with audit-only seeds; "
            "no canonical TRAIN, validation, prediction, or EvaluationResult was modified."
        ),
        rights=_PUBLIC_RIGHTS,
    )
    manifest_path = folder / "manifest.json"
    manifest_path.write_bytes(_manifest_bytes(manifest))
    manifest_rel = f"{final_folder}/manifest.json"
    refs.append(_artifact_from_staging(root, staging, manifest_rel, manifest_path))
    return manifest, manifest_rel, tuple(refs)


def _targets(rows: tuple[native_dataset.PublicForecastRow, ...]) -> Any:
    import numpy as np

    return np.asarray(
        [[cast(dict[str, float], row.targets)[name] for name in TARGETS] for row in rows],
        dtype=np.float64,
    )


def _relabel(
    rows: tuple[native_dataset.PublicForecastRow, ...], seed: int
) -> tuple[native_dataset.PublicForecastRow, ...]:
    labels = [row.row_id for row in rows]
    shuffled = labels.copy()
    random.Random(seed).shuffle(shuffled)
    if shuffled == labels:
        shuffled = labels[1:] + labels[:1]
    return tuple(
        replace(row, row_id=key, inputs=replace(row.inputs, entity_id=key))
        for row, key in zip(rows, shuffled, strict=True)
    )


def _target_canary(
    rows: tuple[native_dataset.PublicForecastRow, ...], value: float = 1_000_000.0
) -> tuple[native_dataset.PublicForecastRow, ...]:
    return tuple(
        replace(
            row, targets=cast(native_dataset.PublicCapacityTargets, {key: value for key in TARGETS})
        )
        for row in rows
    )


def _disrupt_history(
    rows: tuple[native_dataset.PublicForecastRow, ...],
) -> tuple[native_dataset.PublicForecastRow, ...]:
    output = []
    for row in rows:
        lifts: dict[str, native_dataset.LiftInputs] = {}
        for lift in population.LIFTS:
            values = cast(dict[str, native_dataset.LiftInputs], row.inputs.lifts)[lift]
            reversed_history = tuple(reversed(values.history))
            history = tuple(
                replace(
                    original,
                    assessment_kg=shuffled.assessment_kg,
                    prescribed_load_kg=shuffled.prescribed_load_kg,
                    velocity_mps=shuffled.velocity_mps,
                )
                for original, shuffled in zip(values.history, reversed_history, strict=True)
            )
            lifts[lift] = replace(values, history=history)
        output.append(
            replace(
                row, inputs=replace(row.inputs, lifts=cast(native_dataset.PublicLiftInputs, lifts))
            )
        )
    return tuple(output)


def _simulate_targets(
    row: native_dataset.PublicForecastRow,
    athlete: population.AthleteProfile,
    plan: interventions.DeclaredFuturePlan,
) -> native_dataset.PublicCapacityTargets:
    targets: dict[str, float] = {}
    row_lifts = cast(dict[str, native_dataset.LiftInputs], row.inputs.lifts)
    for lift in population.LIFTS:
        inputs = row_lifts[lift]
        sessions: dict[int, dynamics.TrainingSession] = {}
        for segment in inputs.history_schedule:
            for day in range(segment.start_day, segment.end_day + 1):
                sessions[day] = dynamics.TrainingSession(day, segment.dose, segment.intensity)
        for day in range(plan.start_day, plan.end_day + 1):
            sessions[day] = dynamics.TrainingSession(day, plan.dose, plan.intensity)
        trajectory = dynamics.simulate_lift(
            athlete.parameters.lifts[lift],
            sessions,
            athlete.parameters.stimulus_reference,
            interventions.PLAN_END_DAY,
        )
        targets[f"{lift}_delta_capacity_kg"] = dynamics.latent_capacity_change(
            trajectory, row.inputs.origin_day, row.inputs.horizon_days
        )
    return cast(native_dataset.PublicCapacityTargets, targets)


def _counterfactual_plans(
    rows: tuple[native_dataset.PublicForecastRow, ...],
    profiles: dict[str, population.AthleteProfile],
) -> tuple[native_dataset.PublicForecastRow, ...]:
    swap = {
        "continue": "cessation",
        "cessation": "continue",
        "step_up": "step_down",
        "step_down": "step_up",
    }
    output = []
    for row in rows:
        old = row.inputs.declared_future_plan
        changed = interventions.declared_plan(swap[old.plan_id])
        changed_input = replace(row.inputs, declared_future_plan=changed)
        athlete_key = f"entity-{row.row_id.rsplit('entity-', 1)[1]}"
        changed_row = replace(
            row,
            inputs=changed_input,
            targets=_simulate_targets(row, profiles[athlete_key], changed),
        )
        output.append(changed_row)
    return tuple(output)


def _fresh_observation_rows(
    rows: tuple[native_dataset.PublicForecastRow, ...],
    profiles: dict[str, population.AthleteProfile],
    seed: int,
) -> tuple[native_dataset.PublicForecastRow, ...]:
    rng = random.Random(seed)
    output = []
    for row in rows:
        athlete_key = row.row_id.rsplit("-", 1)[-1]
        profile = profiles[f"entity-{athlete_key}"]
        trajectories: dict[str, dynamics.LiftTrajectory] = {}
        row_lifts = cast(dict[str, native_dataset.LiftInputs], row.inputs.lifts)
        for lift in population.LIFTS:
            inputs = row_lifts[lift]
            sessions: dict[int, dynamics.TrainingSession] = {}
            for segment in inputs.history_schedule:
                for day in range(segment.start_day, segment.end_day + 1):
                    sessions[day] = dynamics.TrainingSession(day, segment.dose, segment.intensity)
            plan = row.inputs.declared_future_plan
            for day in range(plan.start_day, plan.end_day + 1):
                sessions[day] = dynamics.TrainingSession(day, plan.dose, plan.intensity)
            trajectories[lift] = dynamics.simulate_lift(
                profile.parameters.lifts[lift],
                sessions,
                profile.parameters.stimulus_reference,
                interventions.PLAN_END_DAY,
            )
        lifts = {
            lift: replace(
                row_lifts[lift],
                history=observations.sample_performance_history(
                    trajectories[lift].expressed_performance_kg, lift, rng
                ),
            )
            for lift in population.LIFTS
        }
        output.append(
            replace(
                row, inputs=replace(row.inputs, lifts=cast(native_dataset.PublicLiftInputs, lifts))
            )
        )
    return tuple(output)


def _prediction_matrix(
    m4: _M4Evidence,
    rows: tuple[native_dataset.PublicForecastRow, ...],
) -> dict[tuple[str, int], Any]:

    from ..models.comparators import feature_matrix, predict_comparator
    from ..models.temporal_expert import NormalizationStats

    reference = m4.comparator_runs[0].state["input_normalization"]
    if any(run.state["input_normalization"] != reference for run in m4.comparator_runs):
        raise ValueError("M4 comparator fit states do not share declared input normalization")
    stats = NormalizationStats.from_dict(reference)
    features = feature_matrix(rows, stats)
    return {
        (run.method, run.seed): predict_comparator(run.method, run.state, rows, features)
        for run in m4.comparator_runs
    }


def _paired_diagnostics(
    baseline: tuple[native_dataset.PublicForecastRow, ...],
    changed: tuple[native_dataset.PublicForecastRow, ...],
    first: dict[tuple[str, int], Any],
    second: dict[tuple[str, int], Any],
    prefix: str,
) -> dict[str, DiagnosticValue]:
    import numpy as np

    output: dict[str, DiagnosticValue] = {}
    for (method, seed), before in first.items():
        after = second[(method, seed)]
        output[f"max_abs_prediction_delta::{prefix}::{method}::{seed}"] = float(
            np.max(np.abs(after - before))
        )
        for index, target in enumerate(TARGETS):
            before_metrics = canonical_target_metrics(
                target,
                _targets(baseline)[:, index].tolist(),
                before[:, index].tolist(),
                unit="kg",
            )
            after_metrics = canonical_target_metrics(
                target,
                _targets(changed)[:, index].tolist(),
                after[:, index].tolist(),
                unit="kg",
            )
            rmse_before = next(
                item.value for item in before_metrics.metrics if item.metric is MetricName.RMSE
            )
            rmse_after = next(
                item.value for item in after_metrics.metrics if item.metric is MetricName.RMSE
            )
            if rmse_before is None or rmse_after is None:
                raise ValueError("canonical RMSE unexpectedly has no value")
            output[f"rmse_delta::{prefix}::{method}::{seed}::{target}"] = float(
                rmse_after - rmse_before
            )
    return output


def _native_data_artifacts(
    root: Path, iid_raw: dict[str, Any]
) -> tuple[tuple[EvidenceArtifactReference, ...], tuple[str, ...], int]:
    data_root = Path(
        "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production"
    )
    rights = RightsMetadata(**iid_raw["rights"])
    output = []
    missing: list[str] = []
    mismatches = 0
    for item in iid_raw["artifact_hashes"]:
        name = "train.jsonl" if item["artifact_id"] == "train" else "validation.jsonl"
        path = (data_root / name).as_posix()
        if not (root / path).is_file():
            missing.append(path)
            continue
        artifact = evidence_artifact(root, path, rights=rights)
        if artifact.sha256.removeprefix(_SHA256) != item["sha256"]:
            mismatches += 1
        output.append(artifact)
    return tuple(output), tuple(missing), mismatches


def _is_origin_shift_predeclared(benchmark_version: str) -> bool:
    identity = _BENCHMARKS[benchmark_version].semantic_identity
    return identity is not None and bool(identity.declared_shift_relations)


def _nonexecuted_record(
    root: Path,
    benchmark_version: str,
    attack_slug: str,
    status: AuditStatus,
    reason: str,
    paths: tuple[str, ...],
    missing: tuple[str, ...] = (),
) -> AuditExecutionRecord:
    available: list[EvidenceArtifactReference] = []
    unavailable: list[str] = []
    for path in paths:
        try:
            available.append(evidence_artifact(root, path))
        except FileNotFoundError:
            unavailable.append(path)
    if not available:
        raise ValueError("non-execution state has no available evidence to cite")
    if unavailable and status in {AuditStatus.NOT_RUN, AuditStatus.UNSUPPORTED_BY_EVIDENCE}:
        missing = (
            *missing,
            *(f"Public evidence artifact is unavailable: {path}" for path in unavailable),
        )
    if unavailable and status is AuditStatus.NOT_RUN:
        status = AuditStatus.UNSUPPORTED_BY_EVIDENCE
        reason = f"{reason} Required public evidence is missing."
    refs = tuple(available)
    return _record(
        benchmark_version=benchmark_version,
        attack_slug=attack_slug,
        status=status,
        reason=reason,
        input_artifacts=refs,
        missing=missing,
    )


def _native_intervention_record(
    root: Path,
    staging: Path,
    output_rel: Path,
    m4: _M4Evidence,
    benchmark_version: str,
    attack_slug: str,
    source_commit: str,
    seed: int,
) -> AuditExecutionRecord:
    import numpy as np

    realization_id = f"{_RUN_NAMESPACE}-{attack_slug.replace('_', '-')}-seed-{seed}"
    config, baseline, profiles = _audit_rows(seed, realization_id)
    intervention = _ATTACKS[f"{attack_slug}@1.0.0"].permitted_interventions[0]
    model_inputs = m4.artifact_refs
    diagnostics: dict[str, DiagnosticValue]
    criteria: tuple[str, ...]
    extra_configuration: dict[str, DiagnosticValue] = {}
    extra_seeds: tuple[tuple[str, int], ...] = ()
    data_conditions: tuple[tuple[str, tuple[native_dataset.PublicForecastRow, ...]], ...]
    if attack_slug == "participant_input_leakage":
        key_seed = seed + 90
        changed = _relabel(baseline, key_seed)
        extra_seeds = (("key_permutation", key_seed),)
        extra_configuration = {"key_permutation_seed": key_seed}
        before = _prediction_matrix(m4, baseline)
        after = _prediction_matrix(m4, changed)
        mismatch = sum(not np.array_equal(before[key], after[key]) for key in before)
        max_delta = max(float(np.max(np.abs(before[key] - after[key]))) for key in before)
        diagnostics = {
            "audit_row_count": len(baseline),
            "fitted_comparator_instance_count": len(before),
            "key_relabel_prediction_mismatch_count": mismatch,
            "maximum_absolute_prediction_delta": max_delta,
        }
        status = AuditStatus.PASS if mismatch == 0 else AuditStatus.FAIL
        criteria = (
            (
                "Every available public-native comparator is exactly invariant to a copied key-only relabeling."
                if status is AuditStatus.PASS
                else "At least one available public-native comparator changed its prediction under a key-only relabeling."
            ),
        )
        reason = "Copied participant keys were permuted and all 18 sealed comparator instances were re-run on the same visible inputs."
        limitation = (
            "This checks the six registered RES-275 comparator families and their 18 fitted states, not unregistered participant models.",
        )
        data_conditions = (("key-relabelled", changed),)
    elif attack_slug == "target_identity_contamination":
        changed = _target_canary(baseline)
        extra_configuration = {"target_canary_value": 1_000_000}
        before = _prediction_matrix(m4, baseline)
        after = _prediction_matrix(m4, changed)
        mismatch = sum(not np.array_equal(before[key], after[key]) for key in before)
        max_delta = max(float(np.max(np.abs(before[key] - after[key]))) for key in before)
        diagnostics = {
            "audit_row_count": len(baseline),
            "fitted_comparator_instance_count": len(before),
            "target_canary_prediction_mismatch_count": mismatch,
            "maximum_absolute_prediction_delta": max_delta,
        }
        status = AuditStatus.PASS if mismatch == 0 else AuditStatus.FAIL
        criteria = (
            (
                "Changing only copied target fields leaves all available public-native comparator predictions exactly invariant."
                if status is AuditStatus.PASS
                else "At least one available public-native comparator changed its prediction after a target-only canary."
            ),
        )
        reason = "A target canary was injected into copied target values and all 18 sealed comparator instances were re-run."
        limitation = (
            "This verifies the repository inference adapter boundary; it does not establish leakage absence in external code.",
        )
        data_conditions = (("target-canary", changed),)
    elif attack_slug == "temporal_history_disruption":
        changed = _disrupt_history(baseline)
        extra_configuration = {"history_transform": "reverse values across fixed weekly day slots"}
        before = _prediction_matrix(m4, baseline)
        after = _prediction_matrix(m4, changed)
        diagnostics = _paired_diagnostics(baseline, changed, before, after, "reversed-history")
        diagnostics["audit_row_count"] = len(baseline)
        diagnostics["fitted_comparator_instance_count"] = len(before)
        status = AuditStatus.INCONCLUSIVE
        criteria = (
            "The disruption was executed, but RES-277 declares no practical margin for interpreting its paired metric deltas.",
        )
        reason = "Weekly history values were reversed across the fixed day slots and predictions were recomputed."
        limitation = (
            "This is an out-of-support chronology stress diagnostic, not ordinary benchmark performance.",
        )
        data_conditions = (("reversed-history", changed),)
    elif attack_slug == "training_plan_counterfactual_sensitivity":
        changed = _counterfactual_plans(baseline, profiles)
        extra_configuration = {
            "plan_swap_pairs": "continue:cessation,step_up:step_down",
            "targets_regenerated_under_native_world": True,
        }
        before = _prediction_matrix(m4, baseline)
        after = _prediction_matrix(m4, changed)
        diagnostics = _paired_diagnostics(baseline, changed, before, after, "supported-plan-swap")
        base_target = _targets(baseline)
        changed_target = _targets(changed)
        for index, target in enumerate(TARGETS):
            diagnostics[f"mean_abs_regenerated_target_delta::{target}"] = float(
                np.mean(np.abs(changed_target[:, index] - base_target[:, index]))
            )
        diagnostics["audit_row_count"] = len(baseline)
        diagnostics["fitted_comparator_instance_count"] = len(before)
        status = AuditStatus.INCONCLUSIVE
        criteria = (
            "Supported plans and regenerated native-world targets were used; no predeclared sensitivity margin resolves the response.",
        )
        reason = "Each declared plan was swapped to its supported paired alternative and its target was re-simulated under the same athlete parameters and history."
        limitation = (
            "Results describe paired interventions within this synthetic native world and do not estimate real-athlete training effects.",
        )
        data_conditions = (("supported-plan-counterfactual", changed),)
    elif attack_slug == "observation_noise_perturbation":
        before = _prediction_matrix(m4, baseline)
        noise_seeds = tuple(seed + 101 + replicate for replicate in range(3))
        changed_sets = tuple(
            _fresh_observation_rows(baseline, profiles, noise_seed) for noise_seed in noise_seeds
        )
        extra_seeds = tuple(
            (f"noise_replicate_{index + 1}", noise_seed)
            for index, noise_seed in enumerate(noise_seeds)
        )
        extra_configuration = {
            "noise_replicate_seeds": ",".join(str(item) for item in noise_seeds),
            "noise_replicate_count": len(noise_seeds),
        }
        diagnostics = {
            "audit_row_count": len(baseline),
            "fitted_comparator_instance_count": len(before),
        }
        draw_predictions = tuple(_prediction_matrix(m4, changed) for changed in changed_sets)
        for key, original in before.items():
            draws = [predictions[key] for predictions in draw_predictions]
            stacked = np.stack(draws)
            variance = np.mean(np.var(stacked, axis=0, ddof=0), axis=0)
            method, model_seed = key
            for index, target in enumerate(TARGETS):
                diagnostics[f"mean_prediction_variance::{method}::{model_seed}::{target}"] = float(
                    variance[index]
                )
                diagnostics[f"mean_abs_prediction_delta::{method}::{model_seed}::{target}"] = float(
                    np.mean(np.abs(stacked[:, :, index] - original[None, :, index]))
                )
        status = AuditStatus.INCONCLUSIVE
        criteria = (
            "Three fresh observation draws were scored with latent targets, plan, and horizon held fixed; no practical noise-response margin is predeclared.",
        )
        reason = "Three independent draws were generated under the native observation law for each fixed latent trajectory."
        limitation = (
            "The three noise replicates are descriptive and do not establish broad observation robustness.",
        )
        data_conditions = tuple(
            (f"noise-replicate-{index + 1}", rows) for index, rows in enumerate(changed_sets)
        )
    else:
        raise ValueError(f"no public-native intervention adapter for {attack_slug}")

    manifest, manifest_path, realization_refs = _write_audit_realization(
        root,
        staging,
        output_rel,
        attack_slug,
        seed,
        config,
        baseline,
        data_conditions,
        intervention,
        source_commit,
        extra_seeds,
    )
    refs = tuple({item.path: item for item in (*model_inputs, *realization_refs)}.values())
    return _record(
        benchmark_version=benchmark_version,
        attack_slug=attack_slug,
        status=status,
        reason=reason,
        input_artifacts=refs,
        diagnostics=diagnostics,
        source_commit=source_commit,
        seed=seed,
        intervention=intervention,
        audit_realization=manifest,
        audit_manifest_path=manifest_path,
        decision_criteria=criteria,
        limitations=limitation,
        extra_configuration={
            "audit_rows": AUDIT_ROW_COUNT,
            "model_methods": 6,
            "model_seeds": ",".join(str(item) for item in MODEL_SEEDS),
            "fit_performed": False,
            **extra_configuration,
        },
    )


def _frontier_diagnostics(m4: _M4Evidence) -> dict[str, DiagnosticValue]:
    import numpy as np

    models: dict[str, dict[str, dict[str, float]]] = {}
    by_method: dict[str, list[_ComparatorRun]] = {}
    for run in m4.comparator_runs:
        by_method.setdefault(run.method, []).append(run)
    for method, runs in by_method.items():
        models[f"public-native-{method}"] = {
            target: {
                metric: float(np.mean([run.metrics[target][metric] for run in runs]))
                for metric in runs[0].metrics[target]
            }
            for target in TARGETS
        }
    expert_seeds = {
        target: {
            metric: float(
                np.mean(
                    [
                        m4.expert_metrics[("public-native-temporal-expert", seed)][target][metric]
                        for seed in MODEL_SEEDS
                    ]
                )
            )
            for metric in m4.expert_ensemble_metrics[target]
        }
        for target in TARGETS
    }
    models["public-native-temporal-expert-seed-mean"] = expert_seeds
    models["public-native-temporal-expert-ensemble"] = m4.expert_ensemble_metrics
    output: dict[str, DiagnosticValue] = {}
    metric_names = (
        MetricName.RMSE.value,
        MetricName.MAE.value,
        MetricName.R2.value,
        MetricName.SRE.value,
    )
    for target in TARGETS:
        rows = {name: values[target] for name, values in models.items()}
        dominated: set[str] = set()
        for candidate, values in rows.items():
            vector = [
                values[name] * (-1.0 if name == MetricName.R2.value else 1.0)
                for name in metric_names
            ]
            for other, other_values in rows.items():
                if other == candidate:
                    continue
                other_vector = [
                    other_values[name] * (-1.0 if name == MetricName.R2.value else 1.0)
                    for name in metric_names
                ]
                if all(
                    left <= right for left, right in zip(other_vector, vector, strict=True)
                ) and any(left < right for left, right in zip(other_vector, vector, strict=True)):
                    dominated.add(candidate)
                    break
        frontier = sorted(set(rows) - dominated)
        output[f"pareto_nondominated_count::{target}"] = len(frontier)
        output[f"pareto_dominated_count::{target}"] = len(dominated)
        output[f"pareto_frontier::{target}"] = ",".join(frontier)
        for model, values in rows.items():
            for metric in metric_names:
                output[f"mean::{target}::{model}::{metric}"] = values[metric]
    return output


def _rank_diagnostics(m4: _M4Evidence) -> dict[str, DiagnosticValue]:
    import numpy as np

    model_metrics: dict[tuple[str, int], dict[str, dict[str, float]]] = {
        (f"public-native-{run.method}", run.seed): run.metrics for run in m4.comparator_runs
    }
    model_metrics.update(m4.expert_metrics)
    output: dict[str, DiagnosticValue] = {}
    for target in TARGETS:
        seed_ranks: dict[int, dict[str, float]] = {}
        for seed in MODEL_SEEDS:
            values = {
                name: metrics[target][MetricName.RMSE.value]
                for (name, current_seed), metrics in model_metrics.items()
                if current_seed == seed
            }
            ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
            ranks: dict[str, float] = {}
            offset = 0
            while offset < len(ordered):
                end = offset + 1
                while end < len(ordered) and ordered[end][1] == ordered[offset][1]:
                    end += 1
                rank = ((offset + 1) + end) / 2.0
                for name, _ in ordered[offset:end]:
                    ranks[name] = rank
                offset = end
            seed_ranks[seed] = ranks
        models = sorted(set.intersection(*(set(value) for value in seed_ranks.values())))
        for model in models:
            output[f"rank_sd::{target}::{model}"] = float(
                np.std([seed_ranks[seed][model] for seed in MODEL_SEEDS], ddof=0)
            )
        reversals = 0
        for left_index, left in enumerate(models):
            for right in models[left_index + 1 :]:
                signs = [
                    np.sign(seed_ranks[seed][left] - seed_ranks[seed][right])
                    for seed in MODEL_SEEDS
                ]
                reversals += sum(
                    signs[a] * signs[b] < 0
                    for a in range(len(signs))
                    for b in range(a + 1, len(signs))
                )
        output[f"pairwise_rank_reversal_count::{target}"] = int(reversals)
    output["fit_seed_count"] = len(MODEL_SEEDS)
    output["model_family_count"] = len(set(name for name, _ in model_metrics))
    return output


def _seed_diagnostics(m4: _M4Evidence) -> dict[str, DiagnosticValue]:
    import numpy as np

    output: dict[str, DiagnosticValue] = {"fit_seed_count": len(MODEL_SEEDS)}
    for method in sorted({run.method for run in m4.comparator_runs}):
        runs = [run for run in m4.comparator_runs if run.method == method]
        for target in TARGETS:
            for metric in (
                MetricName.RMSE.value,
                MetricName.MAE.value,
                MetricName.R2.value,
                MetricName.SRE.value,
            ):
                values = [run.metrics[target][metric] for run in runs]
                output[f"range::{method}::{target}::{metric}"] = float(max(values) - min(values))
                output[f"population_sd::{method}::{target}::{metric}"] = float(
                    np.std(values, ddof=0)
                )
    return output


def _coverage_record(
    root: Path,
    benchmark_version: str,
    source_commit: str,
    records: tuple[AuditExecutionRecord, ...],
    registry_refs: tuple[EvidenceArtifactReference, ...],
) -> AuditExecutionRecord:
    attack_records = [item for item in records if item.benchmark_version == benchmark_version]
    by_attack = {item.attack_spec_ref: item for item in attack_records}
    expected = {item.reference for item in ATTACK_SPECS}
    coverage_ref = "audit_coverage_accounting@1.0.0"
    if len(by_attack) != len(attack_records) or set(by_attack) != expected - {coverage_ref}:
        raise ValueError(f"coverage ledger is incomplete or duplicated for {benchmark_version}")
    counts = {status.value: 0 for status in AuditStatus}
    for result in attack_records:
        counts[result.status.value] += 1
    counts[AuditStatus.PASS.value] += 1
    applicable_count = (
        sum(item.status is not AuditStatus.NOT_APPLICABLE for item in attack_records) + 1
    )
    coverage_attack = _ATTACKS["audit_coverage_accounting@1.0.0"]
    applies = benchmark_version in coverage_attack.applicable_benchmark_versions
    if not applies:
        raise ValueError("coverage accounting must apply to every registered version")
    evidence = tuple(
        {
            item.path: item
            for item in (
                *registry_refs,
                *_refs_for_profile(
                    root,
                    next(
                        profile
                        for profile in VERSION_VALIDITY_PROFILES
                        if f"{profile.benchmark_slug}@{profile.benchmark_version}"
                        == benchmark_version
                    ),
                ),
            )
        }.values()
    )
    return _record(
        benchmark_version=benchmark_version,
        attack_slug="audit_coverage_accounting",
        status=AuditStatus.PASS,
        reason="Every registered attack has exactly one version-specific state, and the count reconciles to the typed contract and profile.",
        input_artifacts=evidence,
        diagnostics={
            "registered_attack_count": len(expected),
            "applicable_attack_count": applicable_count,
            "inapplicable_attack_count": len(expected) - applicable_count,
            "executed_attack_count": sum(counts[state.value] for state in _EXECUTED),
            "recorded_attack_count": len(by_attack) + 1,
            "state_count_match": int(len(expected) == len(by_attack) + 1),
            **{f"state_count::{key}": value for key, value in counts.items()},
        },
        source_commit=source_commit,
        seed=0,
        intervention=coverage_attack.permitted_interventions[0],
        decision_criteria=(
            "Exactly one explicit state is recorded for every registered attack contract in this benchmark version.",
        ),
        limitations=("Coverage is process metadata; it is not a benchmark validity score.",),
        extra_configuration={"profile_version": "1.0.0", "registered_attack_count": len(expected)},
    )


def _m4_integrity_record(
    root: Path,
    source_commit: str,
    m4: _M4Evidence,
    iid_raw: dict[str, Any],
) -> AuditExecutionRecord:
    raw_inputs, missing, raw_hash_mismatches = _native_data_artifacts(root, iid_raw)
    source_inputs = tuple(
        evidence_artifact(root, f"src/powerlifting_state_research/{path}")
        for path in native_dataset.GENERATOR_SOURCE_FILES
    )
    manifest_input = evidence_artifact(root, _IID_MANIFEST.as_posix())
    refs = tuple(
        {
            item.path: item
            for item in (*m4.artifact_refs, *raw_inputs, *source_inputs, manifest_input)
        }.values()
    )
    generator_digest = native_dataset.GENERATOR_SOURCE_SHA256
    declared = iid_raw["generator_identity"].split("generator-source-sha256=")[-1].split(";", 1)[0]
    config_digest = native_dataset.PUBLIC_GENERATION_CONFIGURATION_SHA256.removeprefix(_SHA256)
    declared_config = iid_raw["generator_identity"].split("config-sha256=")[-1]
    source_match = declared == generator_digest.removeprefix(_SHA256)
    config_match = declared_config == config_digest
    if missing:
        return _record(
            benchmark_version=_NATIVE_VERSION,
            attack_slug="reconstruction_provenance_gaps",
            status=AuditStatus.UNSUPPORTED_BY_EVIDENCE,
            reason="The public manifest and M4 artifacts are available, but canonical IID source realization bytes are absent in this checkout.",
            input_artifacts=refs,
            missing=tuple(
                f"Canonical public-native realization artifact is unavailable: {path}"
                for path in missing
            ),
            limitations=(
                "M4 predictions and fitted states remain verifiable, but this check cannot verify byte-level TRAIN/validation lineage without the ignored IID data files.",
            ),
        )
    status = (
        AuditStatus.PASS
        if not raw_hash_mismatches and source_match and config_match
        else AuditStatus.FAIL
    )
    reason = (
        "Public-native source data, generator identity, comparator registry, fit seal, fitted states, predictions, and EvaluationResults match their declared hashes and scientific identities."
        if status is AuditStatus.PASS
        else "A public-native source artifact hash or generator/configuration identity contradicts its declared provenance."
    )
    criteria = (
        "Every referenced public source and M4 artifact exists, has its declared hash and rights, and binds the same native benchmark, DatasetSpec, realization, model, and evaluation identities."
        if status is AuditStatus.PASS
        else "Every declared public source hash and generator/configuration identity must match the available bytes and manifest.",
    )
    return _record(
        benchmark_version=_NATIVE_VERSION,
        attack_slug="reconstruction_provenance_gaps",
        status=status,
        reason=reason,
        input_artifacts=refs,
        diagnostics={
            "m4_checksum_entry_count": len(m4.artifact_refs),
            "m4_identity_mismatch_count": 0,
            "source_dataset_artifact_count": len(raw_inputs),
            "source_dataset_hash_mismatch_count": raw_hash_mismatches,
            "generator_source_digest_match": int(source_match),
            "generation_configuration_digest_match": int(config_match),
        },
        source_commit=source_commit,
        seed=0,
        intervention=_ATTACKS["reconstruction_provenance_gaps@1.0.0"].permitted_interventions[0],
        decision_criteria=criteria,
        limitations=(
            "This is a public artifact-lineage and replay-identity check; it does not establish participant-only recovery of latent states or causal mechanisms.",
            "Historical private data, checkpoints, and proprietary implementations were not imported.",
        ),
    )


def build_audit_records(
    root: Path = ROOT,
    *,
    output_rel: Path = DEFAULT_OUTPUT,
    source_commit: str | None = None,
    staging: Path | None = None,
) -> tuple[AuditExecutionRecord, ...]:
    """Build the deterministic version-by-attack ledger and supported public-native runs."""
    commit = _git_commit(root) if source_commit is None else source_commit
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("source commit must be a full lowercase Git SHA-1")
    registry_refs = reconcile_registry_evidence(root)
    m4 = _load_m4_evidence(root)
    iid_raw, _ = _dataset_manifest(root)
    records: list[AuditExecutionRecord] = []
    for profile in VERSION_VALIDITY_PROFILES:
        version = f"{profile.benchmark_slug}@{profile.benchmark_version}"
        for attack in ATTACK_SPECS:
            if attack.slug == "audit_coverage_accounting":
                continue
            if version not in attack.applicable_benchmark_versions:
                paths = (
                    "artifacts/registries/attack-contract-registry.json",
                    _BENCHMARKS[version].docs_path,
                )
                records.append(
                    _nonexecuted_record(
                        root,
                        version,
                        attack.slug,
                        AuditStatus.NOT_APPLICABLE,
                        "This benchmark version is outside the attack contract's declared semantic scope.",
                        paths,
                    )
                )
                continue
            if attack.slug == "hidden_test_fairness" and version == _NATIVE_VERSION:
                records.append(
                    _nonexecuted_record(
                        root,
                        version,
                        attack.slug,
                        AuditStatus.NOT_APPLICABLE,
                        "The public-native evaluation is openly identified and makes no hidden-test claim.",
                        (
                            "docs/benchmarks/iid-latent-capacity-change-public-native-evaluation.md",
                            _IID_MANIFEST.as_posix(),
                        ),
                    )
                )
                continue
            if version != _NATIVE_VERSION:
                records.append(
                    _nonexecuted_record(
                        root,
                        version,
                        attack.slug,
                        AuditStatus.UNSUPPORTED_BY_EVIDENCE,
                        "The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence.",
                        (
                            _BENCHMARKS[version].docs_path,
                            "artifacts/registries/benchmark-registry.json",
                            "src/powerlifting_state_research/provenance/historical_sources.py",
                            "artifacts/registries/attack-contract-registry.json",
                        ),
                        (
                            "Rights-cleared historical participant rows and split identities.",
                            "Version-specific runnable adapter and fitted model/evaluation artifacts.",
                        ),
                    )
                )
                continue
            if attack.slug == "reconstruction_provenance_gaps":
                records.append(_m4_integrity_record(root, commit, m4, iid_raw))
            elif attack.slug in {
                "participant_input_leakage",
                "target_identity_contamination",
                "temporal_history_disruption",
                "training_plan_counterfactual_sensitivity",
                "observation_noise_perturbation",
            }:
                if staging is None:
                    raise ValueError("intervention execution requires an audit staging directory")
                records.append(
                    _native_intervention_record(
                        root,
                        staging,
                        output_rel,
                        m4,
                        version,
                        attack.slug,
                        commit,
                        _NATIVE_ATTACK_SEEDS[attack.slug],
                    )
                )
            elif attack.slug == "parameter_seed_sensitivity":
                records.append(
                    _record(
                        benchmark_version=version,
                        attack_slug=attack.slug,
                        status=AuditStatus.INCONCLUSIVE,
                        reason="Three predeclared M4 fit seeds were compared on the frozen evaluation artifacts; no practical stability margin was specified.",
                        input_artifacts=m4.artifact_refs,
                        diagnostics=_seed_diagnostics(m4),
                        source_commit=commit,
                        seed=0,
                        intervention=attack.permitted_interventions[0],
                        decision_criteria=(
                            "Per-target ranges and population spread are descriptive because the protocol declares three fit seeds but no decision margin or interval method.",
                        ),
                        limitations=(
                            "No retraining, tuning, or validation-driven selection was performed; three seeds do not establish stability beyond this protocol.",
                        ),
                        extra_configuration={
                            "fit_performed": False,
                            "fit_seeds": ",".join(map(str, MODEL_SEEDS)),
                        },
                    )
                )
            elif attack.slug == "baseline_domination":
                records.append(
                    _record(
                        benchmark_version=version,
                        attack_slug=attack.slug,
                        status=AuditStatus.INCONCLUSIVE,
                        reason="The existing M4 comparator and immutable expert results support a target-wise descriptive Pareto frontier, but no practical margin or paired uncertainty method resolves domination.",
                        input_artifacts=m4.artifact_refs,
                        diagnostics=_frontier_diagnostics(m4),
                        source_commit=commit,
                        seed=0,
                        intervention=attack.permitted_interventions[0],
                        decision_criteria=(
                            "Existing same-version RES-271 results are summarized target-wise; no winner is declared without the predeclared margin and uncertainty required by the contract.",
                        ),
                        limitations=(
                            "Finite comparator frontier only; no cross-version score comparison or universal optimum is claimed.",
                        ),
                        extra_configuration={
                            "fit_performed": False,
                            "scored_existing_results_only": True,
                        },
                    )
                )
            elif attack.slug == "model_ranking_instability":
                records.append(
                    _record(
                        benchmark_version=version,
                        attack_slug=attack.slug,
                        status=AuditStatus.INCONCLUSIVE,
                        reason="Existing per-seed EvaluationResults yield target-wise RMSE ranks, but three seeds and no predeclared rank-stability margin do not resolve stability.",
                        input_artifacts=m4.artifact_refs,
                        diagnostics=_rank_diagnostics(m4),
                        source_commit=commit,
                        seed=0,
                        intervention=attack.permitted_interventions[0],
                        decision_criteria=(
                            "Ranks use only aligned per-seed results from this version and remain target-wise; no cross-version scores are pooled.",
                        ),
                        limitations=(
                            "Three fit seeds are a descriptive sample and do not establish ranking stability outside the declared run.",
                        ),
                        extra_configuration={"fit_performed": False, "rank_metric": "RMSE"},
                    )
                )
            elif attack.slug == "audit_coverage_accounting":
                raise AssertionError("coverage is emitted after all other attack states")
            elif attack.slug == "shortcut_feature_dependence":
                _profile = next(
                    item
                    for item in profile.attack_results
                    if item.attack_spec_refs == (attack.reference,)
                )
                feature_paths = tuple(
                    dict.fromkeys(
                        (
                            *_profile.evidence_refs,
                            "artifacts/model-cards/public-native-comparator-suite.md",
                        )
                    )
                )
                records.append(
                    _nonexecuted_record(
                        root,
                        version,
                        attack.slug,
                        AuditStatus.NOT_RUN,
                        "No suspect feature was pre-identified before inspecting audit outcomes, as required by this contract.",
                        feature_paths,
                    )
                )
            elif attack.slug == "sparse_missing_history_sensitivity":
                records.append(
                    _nonexecuted_record(
                        root,
                        version,
                        attack.slug,
                        AuditStatus.UNSUPPORTED_BY_EVIDENCE,
                        "The native schema requires 32 complete weekly observations and the existing comparator input adapter has no missing-history mask; no missingness law is declared.",
                        (
                            "artifacts/schemas/public-forecast-row.schema.json",
                            "src/powerlifting_state_research/models/temporal_expert.py",
                            "artifacts/model-cards/public-native-comparator-suite.md",
                            _IID_MANIFEST.as_posix(),
                        ),
                        (
                            "A versioned missing-history representation and admissible mask/cadence protocol.",
                        ),
                    )
                )
            elif attack.slug == "distributional_shift_sensitivity":
                if _is_origin_shift_predeclared(version):
                    records.append(
                        _nonexecuted_record(
                            root,
                            version,
                            attack.slug,
                            AuditStatus.NOT_RUN,
                            "A shift is declared for this version, but no shift realization was executed in this run.",
                            (
                                "artifacts/registries/benchmark-registry.json",
                                "artifacts/registries/attack-contract-registry.json",
                            ),
                        )
                    )
                else:
                    records.append(
                        _nonexecuted_record(
                            root,
                            version,
                            attack.slug,
                            AuditStatus.UNSUPPORTED_BY_EVIDENCE,
                            "The attack applies, but this native version declares no supported shift relation to execute.",
                            (
                                "artifacts/registries/benchmark-registry.json",
                                "artifacts/registries/attack-contract-registry.json",
                            ),
                            (
                                "A predeclared native shift manifest with a supported generator transform.",
                            ),
                        )
                    )
            else:
                raise ValueError(f"no RES-278 resolver for applicable attack {attack.slug}")

    coverage_inputs = tuple(
        ref
        for ref in registry_refs
        if ref.path
        in {
            "artifacts/registries/validity-axis-registry.json",
            "artifacts/registries/attack-contract-registry.json",
            "artifacts/registries/version-validity-profiles.json",
        }
    )
    for benchmark in BENCHMARKS:
        version = f"{benchmark.slug}@{benchmark.version}"
        records.append(_coverage_record(root, version, commit, tuple(records), coverage_inputs))
    expected = {(version, attack.reference) for version in _BENCHMARKS for attack in ATTACK_SPECS}
    actual = {(item.benchmark_version, item.attack_spec_ref) for item in records}
    if actual != expected or len(records) != len(expected):
        raise ValueError(
            "audit result ledger does not have exactly one registered attack state per version"
        )
    return tuple(sorted(records, key=lambda item: (item.benchmark_version, item.attack_spec_ref)))


def _safe_output(root: Path, output: Path) -> tuple[Path, Path]:
    root = root.resolve()
    output_path = output if output.is_absolute() else root / output
    resolved = output_path.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("audit outputs must remain inside the repository") from error
    if relative.parts[:2] != ("results", "audits") or len(relative.parts) < 3:
        raise ValueError("audit outputs are restricted to results/audits/<run>")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"audit output already exists: {output_path}")
    staging = Path(tempfile.mkdtemp(prefix=f".{output_path.name}-", dir=output_path.parent))
    return resolved, staging


def execute_audit_suite(
    output: Path = DEFAULT_OUTPUT,
    *,
    root: Path = ROOT,
    source_commit: str | None = None,
) -> tuple[AuditExecutionRecord, ...]:
    """Run the supported subset and atomically write an immutable evidence bundle."""
    root = root.resolve()
    commit = _git_commit(root) if source_commit is None else source_commit
    resolved_output, staging = _safe_output(root, output)
    output_rel = resolved_output.relative_to(root)
    try:
        records = build_audit_records(
            root,
            output_rel=output_rel,
            source_commit=commit,
            staging=staging,
        )
        record_docs = [json.loads(canonical_json_bytes(item)) for item in records]
        if tuple(read_audit_execution_record(item) for item in record_docs) != records:
            raise ValueError("audit execution serialization is not replay-stable")
        bundle = canonical_json_bytes({"format": RESULT_FORMAT, "records": record_docs}) + b"\n"
        bundle_path = staging / "audit-results.json"
        bundle_path.write_bytes(bundle)
        file_entries: list[dict[str, Any]] = [
            {
                "path": (output_rel / "audit-results.json").as_posix(),
                "sha256": sha256_file_content(bundle_path),
                "media_type": "application/json",
                "rights": _RESULT_RIGHTS,
            }
        ]
        for path in sorted(staging.rglob("*")):
            if not path.is_file() or path == bundle_path:
                continue
            rel = (output_rel / path.relative_to(staging)).as_posix()
            rights = _PUBLIC_RIGHTS if "/realizations/" in f"/{rel}/" else _RESULT_RIGHTS
            file_entries.append(
                {
                    "path": rel,
                    "sha256": sha256_file_content(path),
                    "media_type": _media_type(rel),
                    "rights": rights,
                }
            )
        artifact_digest = sha256_file_content(bundle_path)
        manifest = {
            "format": "PSR_AUDIT_ARTIFACT_INDEX_V1",
            "rights": _RESULT_RIGHTS,
            "bundle_identity": f"psr:audit-bundle@{artifact_digest}",
            "bundle_path": (output_rel / "audit-results.json").as_posix(),
            "bundle_sha256": artifact_digest,
            "record_count": len(records),
            "record_artifacts": [
                {
                    "identity": item.result_artifact_identity,
                    "record_sha256": item.result_artifact_sha256,
                    "serialized_record_sha256": sha256_record(record_docs[index]),
                    "json_pointer": f"/records/{index}",
                }
                for index, item in enumerate(records)
            ],
            "files": file_entries,
        }
        (staging / "audit-results.manifest.json").write_bytes(
            canonical_json_bytes(manifest) + b"\n"
        )
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, resolved_output)
        return records
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="new results/audits run directory"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="reconcile registries, profiles, and M4 evidence without writing",
    )
    args = parser.parse_args(argv)
    if args.check:
        refs = reconcile_registry_evidence(args.root)
        _load_m4_evidence(args.root)
        print(
            f"PASS: reconciled {len(VERSION_VALIDITY_PROFILES)} profiles and {len(refs)} public evidence artifacts"
        )
        return 0
    records = execute_audit_suite(args.output, root=args.root)
    counts: dict[str, int] = {status.value: 0 for status in AuditStatus}
    for item in records:
        counts[item.status.value] += 1
    print(f"wrote {len(records)} audit states to {(args.root / args.output).resolve()}")
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
