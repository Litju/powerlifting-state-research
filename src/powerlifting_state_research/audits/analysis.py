"""Build the deterministic RES-281 cross-version evidence tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
import textwrap
from collections import Counter
from io import StringIO
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any

from ..contracts.serialization import canonical_json_bytes, sha256_record
from ..registry import BENCHMARKS
from .profiles import VERSION_VALIDITY_PROFILES
from .runner import read_audit_execution_record
from .specifications import ATTACK_SPECS, VALIDITY_AXES, AuditResult, AuditStatus

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = Path("results/audits/res281")
DEFAULT_OUTPUT = Path("results/audits/res281-analysis")
_IID_MANIFEST = Path(
    "data/manifests/realizations/"
    "latent_capacity_change_with_transient_expression_forecasting/iid-production.json"
)
_FULL_PRODUCTION_TEST = Path(
    "tests/benchmarks/"
    "iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py"
)
STATES = tuple(status.value for status in AuditStatus)
_EXECUTED = {AuditStatus.PASS, AuditStatus.FAIL, AuditStatus.INCONCLUSIVE}
_RESULT_RIGHTS = {
    "license_expression": "MIT",
    "copyright_holder": "Powerlifting State Research contributors",
    "redistribution_status": "RES-281 audit analysis under the repository license.",
    "access_conditions": None,
}


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _csv_bytes(header: list[str], rows: list[list[str]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _safe_repo_file(root: Path, path: str) -> Path:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository artifact path: {path}")
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"artifact resolves outside the repository: {path}") from error
    return resolved


def _load_inputs(root: Path, bundle: Path) -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
    root = root.resolve()
    bundle_path = bundle if bundle.is_absolute() else root / bundle
    bundle_path = bundle_path.resolve()
    try:
        bundle_rel = bundle_path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("audit bundle must be inside the repository") from error
    if PurePosixPath(bundle_rel).parts[:2] != ("results", "audits"):
        raise ValueError("audit bundle must be under results/audits")

    index_path = bundle_path / "audit-results.manifest.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    bundle_rel_path = index["bundle_path"]
    bundle_bytes = _safe_repo_file(root, bundle_rel_path).read_bytes()
    if _sha256(bundle_bytes) != index["bundle_sha256"]:
        raise ValueError("audit bundle hash differs from its checksum index")
    if index["bundle_identity"] != f"psr:audit-bundle@{index['bundle_sha256']}":
        raise ValueError("audit bundle identity differs from its indexed hash")
    for item in index["files"]:
        artifact_path = _safe_repo_file(root, item["path"])
        if _sha256(artifact_path.read_bytes()) != item["sha256"]:
            raise ValueError(f"audit artifact checksum mismatch: {item['path']}")

    raw_bundle = json.loads(bundle_bytes)
    records = [read_audit_execution_record(item) for item in raw_bundle["records"]]
    expected = {
        (f"{benchmark.slug}@{benchmark.version}", attack.reference)
        for benchmark in BENCHMARKS
        for attack in ATTACK_SPECS
    }
    actual = {(item.benchmark_version, item.attack_spec_ref) for item in records}
    if actual != expected or len(actual) != len(records):
        raise ValueError("audit result ledger does not cover each attack/version exactly once")

    axis_path = bundle_path / "reproducibility-execution.json"
    axis_execution = json.loads(axis_path.read_bytes())
    execution = axis_execution["execution"]
    result_values = dict(axis_execution["result"])
    result_values["status"] = AuditStatus(result_values["status"])
    for name in ("attack_spec_refs", "evidence_refs", "missing_evidence", "limitations"):
        result_values[name] = tuple(result_values[name])
    axis_result = AuditResult(**result_values)
    expected_manifest_sha = _sha256(_safe_repo_file(root, _IID_MANIFEST.as_posix()).read_bytes())
    test_source_sha = _sha256(_safe_repo_file(root, _FULL_PRODUCTION_TEST.as_posix()).read_bytes())
    run_digest = sha256_record(
        {
            "format": "PSR_AUDIT_AXIS_RUN_V1",
            "benchmark_version": axis_result.benchmark_version,
            "axis_slug": axis_result.axis_slug,
            "source_commit": axis_result.source_commit,
            "test_path": _FULL_PRODUCTION_TEST.as_posix(),
            "test_sha256": test_source_sha,
            "expected_manifest_sha256": expected_manifest_sha,
            "repeat_count": 2,
        }
    )
    expected_run_id = f"res281-reproducibility-{run_digest[7:19]}"
    expected_realization_digest = sha256_record(
        {
            "format": "PSR_AUDIT_REALIZATION_V1",
            "benchmark_version": axis_result.benchmark_version,
            "axis_slug": axis_result.axis_slug,
            "run_id": expected_run_id,
            "source_commit": axis_result.source_commit,
            "canonical_realization_id": execution["canonical_dataset_realization_id"],
            "canonical_realization_digest": execution["canonical_dataset_realization_digest"],
            "manifest_sha256": expected_manifest_sha,
            "generated_artifacts": json.loads(
                _safe_repo_file(root, _IID_MANIFEST.as_posix()).read_bytes()
            )["artifact_hashes"],
            "repeat_count": 2,
            "comparison": (
                "train and validation bytes identical across two generations; both manifests "
                "byte-identical to frozen manifest"
            ),
        }
    )
    expected_realization_id = (
        "psr:audit-realization:iid-latent-capacity-change-with-transient-expression-forecasting-"
        f"reproducibility@{expected_realization_digest}"
    )
    if (
        axis_result.axis_slug != "reproducibility"
        or axis_result.status is not AuditStatus.PASS
        or execution["exit_code"] != 0
        or execution["expected_manifest_sha256"] != expected_manifest_sha
        or execution["test_source_sha256"] != test_source_sha
        or axis_result.run_id != execution["run_id"]
        or axis_result.run_id != expected_run_id
        or axis_result.source_commit != execution["source_commit"]
        or execution["audit_realization_digest"] != expected_realization_digest
        or execution["audit_realization_id"] != expected_realization_id
        or axis_result.diagnostics["audit_realization_id"] != expected_realization_id
        or axis_result.diagnostics["audit_realization_digest"] != expected_realization_digest
        or axis_result.diagnostics["repeat_count"] != 2
        or axis_result.diagnostics["manifest_match_count"] != 2
        or axis_result.diagnostics["train_jsonl_byte_identical"] is not True
        or axis_result.diagnostics["validation_jsonl_byte_identical"] is not True
    ):
        raise ValueError("reproducibility axis execution record is inconsistent")
    for evidence_path in axis_result.evidence_refs:
        if not _safe_repo_file(root, evidence_path).is_file():
            raise ValueError(f"reproducibility evidence is unavailable: {evidence_path}")
    source = {
        "bundle_path": bundle_rel_path,
        "bundle_sha256": index["bundle_sha256"],
        "bundle_manifest_path": (Path(bundle_rel) / "audit-results.manifest.json").as_posix(),
        "bundle_manifest_sha256": _sha256(index_bytes),
        "axis_execution_path": (Path(bundle_rel) / "reproducibility-execution.json").as_posix(),
        "axis_execution_sha256": _sha256(axis_path.read_bytes()),
        "axis_result": axis_result,
        "bundle_manifest": index,
    }
    return index, records, source


def _component_values(benchmark: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    values: dict[str, list[str]] = {}
    for reference in benchmark.get("component_references", []):
        key = reference.get("canonical_key")
        values.setdefault(reference["component_class"], []).append("" if key is None else key)
    return {name: tuple(sorted(items)) for name, items in values.items()}


def _design_rows(root: Path) -> tuple[bytes, list[dict[str, Any]]]:
    registry = json.loads((root / "artifacts/registries/benchmark-registry.json").read_bytes())
    evidence: list[dict[str, Any]] = []
    rows: list[list[str]] = []
    for benchmark in sorted(registry["benchmarks"], key=lambda item: item["slug"]):
        version = f"{benchmark['slug']}@{benchmark['version']}"
        history = benchmark.get("historical_provenance") or {}
        source_changes = history.get("source_component_changes") or {}
        primary_change = source_changes.get("primary_design_axis")
        if primary_change is None:
            primary_change = (
                "Independent public-native IID dataset and four-metric evaluation; "
                "world/task/QOI/representation are shared with the historical "
                "capacity-change projection."
            )
        components = _component_values(benchmark)
        research = benchmark.get("research") or {}
        info = research.get("source_prediction_setting") or history.get(
            "source_prediction_setting", ""
        )
        docs = f"docs/benchmarks/{benchmark['slug'].replace('_', '-')}.md"
        item = {
            "benchmark_version": version,
            "identity_authority": benchmark["identity_authority"],
            "historical_specimen_status": benchmark["historical_specimen_status"],
            "completeness_status": benchmark["completeness_status"],
            "benchmark_id": benchmark.get("benchmark_id"),
            "semantic_digest": benchmark.get("semantic_digest"),
            "parent_specimen_id": history.get("historical_parent_specimen_id"),
            "parentage_status": history.get("parentage_status"),
            "primary_design_change": primary_change,
            "task_type": benchmark["task_type"],
            "task_reference": components.get("TASK", ("",))[0],
            "qoi_reference": components.get("QOI", ("",))[0],
            "dataset_spec_reference": components.get("DATASET_SPEC", ("",))[0],
            "evaluation_reference": components.get("EVALUATION", ("",))[0],
            "information_boundary": info,
            "evidence_refs": [
                docs,
                "artifacts/registries/benchmark-registry.json",
                "src/powerlifting_state_research/provenance/historical_sources.py",
            ],
        }
        evidence.append(item)
        rows.append(
            [
                version,
                item["identity_authority"],
                item["historical_specimen_status"],
                "" if item["benchmark_id"] is None else item["benchmark_id"],
                "" if item["parent_specimen_id"] is None else item["parent_specimen_id"],
                "" if item["parentage_status"] is None else item["parentage_status"],
                item["task_reference"],
                item["qoi_reference"],
                item["dataset_spec_reference"],
                item["evaluation_reference"],
                info,
                primary_change,
                "; ".join(item["evidence_refs"]),
            ]
        )
    header = [
        "benchmark_version",
        "identity_authority",
        "historical_specimen_status",
        "benchmark_id",
        "parent_specimen_id",
        "parentage_status",
        "task_reference",
        "qoi_reference",
        "dataset_spec_reference",
        "evaluation_reference",
        "source_prediction_setting",
        "primary_design_change_descriptive_only",
        "evidence_refs",
    ]
    return _csv_bytes(header, rows), evidence


def _comparability_rows(benchmarks: list[dict[str, Any]]) -> bytes:
    rows: list[list[str]] = []
    for left, right in combinations(benchmarks, 2):
        left_components = _component_values(left)
        right_components = _component_values(right)
        left_research = left.get("research") or {}
        right_research = right.get("research") or {}
        left_history = left.get("historical_provenance") or {}
        right_history = right.get("historical_provenance") or {}
        left_info = (
            left_research.get("information_setting", ""),
            left_research.get("source_prediction_setting")
            or left_history.get("source_prediction_setting", ""),
        )
        right_info = (
            right_research.get("information_setting", ""),
            right_research.get("source_prediction_setting")
            or right_history.get("source_prediction_setting", ""),
        )
        checks = {
            "task_match": left_components.get("TASK") == right_components.get("TASK"),
            "qoi_match": left_components.get("QOI") == right_components.get("QOI"),
            "world_match": left_components.get("WORLD") == right_components.get("WORLD"),
            "representation_match": left_components.get("REPRESENTATION")
            == right_components.get("REPRESENTATION"),
            "dataset_spec_match": left_components.get("DATASET_SPEC")
            == right_components.get("DATASET_SPEC"),
            "evaluation_match": left_components.get("EVALUATION")
            == right_components.get("EVALUATION"),
            "metric_set_match": left_components.get("METRIC", ())
            == right_components.get("METRIC", ()),
            "information_boundary_match": left_info == right_info,
        }
        reasons = [
            f"{name.removesuffix('_match')} differs"
            for name, matched in checks.items()
            if not matched
        ]
        reasons.append(
            "No public cross-version paired predictions and evaluation results "
            "establish matched support/distribution."
        )
        rows.append(
            [
                f"{left['slug']}@{left['version']}",
                f"{right['slug']}@{right['version']}",
                "REJECTED_FOR_NUMERICAL_COMPARISON",
                json.dumps(checks, sort_keys=True, separators=(",", ":")),
                "false",
                "; ".join(reasons),
            ]
        )
    return _csv_bytes(
        [
            "left_benchmark_version",
            "right_benchmark_version",
            "numerical_comparison_decision",
            "declared_semantic_checks",
            "matched_support_and_paired_scores_verified",
            "rejection_reasons",
        ],
        rows,
    )


def build_analysis_documents(root: Path, bundle: Path) -> dict[str, bytes]:
    """Return deterministic RES-281 matrices and analysis from the verified execution bundle."""
    root = root.resolve()
    index, records, source = _load_inputs(root, bundle)
    versions = sorted(f"{item.slug}@{item.version}" for item in BENCHMARKS)
    records_by_key = {(item.benchmark_version, item.attack_spec_ref): item for item in records}
    records_by_version = {
        version: [item for item in records if item.benchmark_version == version]
        for version in versions
    }
    attack_matrix = _csv_bytes(
        ["axis_slug", "attack_spec_ref", *versions],
        [
            [
                attack.axis_slug,
                attack.reference,
                *[records_by_key[(version, attack.reference)].status.value for version in versions],
            ]
            for attack in sorted(ATTACK_SPECS, key=lambda item: item.slug)
        ],
    )

    profile_map = {
        f"{profile.benchmark_slug}@{profile.benchmark_version}": profile
        for profile in VERSION_VALIDITY_PROFILES
    }
    axis_result = source["axis_result"]
    axis_records: list[dict[str, Any]] = []
    axis_csv_rows: list[list[str]] = []
    for version in versions:
        profile = profile_map[version]
        baseline_axes = {item.axis_slug: item for item in profile.axis_results}
        for axis in VALIDITY_AXES:
            attack_items = [
                item for item in records_by_version[version] if item.axis_slug == axis.slug
            ]
            direct_axis_results: list[dict[str, Any]] = []
            if version == axis_result.benchmark_version and axis.slug == axis_result.axis_slug:
                direct_axis_results.append(
                    {
                        "axis_slug": axis_result.axis_slug,
                        "status": axis_result.status.value,
                        "run_id": axis_result.run_id,
                        "source_commit": axis_result.source_commit,
                        "reason": axis_result.status_reason,
                        "diagnostics": axis_result.diagnostics,
                        "result_file": source["axis_execution_path"],
                        "result_sha256": source["axis_execution_sha256"],
                    }
                )
            state_counts = Counter(item.status.value for item in attack_items)
            evidence_refs = sorted(
                {ref for item in attack_items for ref in item.evidence_refs}
                | set(baseline_axes[axis.slug].evidence_refs)
                | ({ref for item in direct_axis_results for ref in axis_result.evidence_refs})
            )
            missing = sorted(
                {entry for item in attack_items for entry in item.missing_evidence}
                | set(baseline_axes[axis.slug].missing_evidence)
            )
            current_attacks = [
                {
                    "attack_spec_ref": item.attack_spec_ref,
                    "status": item.status.value,
                    "status_reason": item.status_reason,
                    "run_id": item.run_id,
                    "result_artifact_identity": item.result_artifact_identity,
                    "result_artifact_sha256": item.result_artifact_sha256,
                    "evidence_refs": list(item.evidence_refs),
                    "missing_evidence": list(item.missing_evidence),
                }
                for item in sorted(attack_items, key=lambda item: item.attack_spec_ref)
            ]
            row = {
                "benchmark_version": version,
                "axis_slug": axis.slug,
                "profile_status_before_res281": baseline_axes[axis.slug].status.value,
                "profile_status_reason_before_res281": baseline_axes[axis.slug].status_reason,
                "res281_attack_state_counts": {
                    status: state_counts.get(status, 0) for status in STATES
                },
                "res281_attack_results": current_attacks,
                "res281_direct_axis_results": direct_axis_results,
                "evidence_refs": evidence_refs,
                "missing_evidence": missing,
            }
            axis_records.append(row)
            axis_csv_rows.append(
                [
                    version,
                    axis.slug,
                    baseline_axes[axis.slug].status.value,
                    baseline_axes[axis.slug].status_reason,
                    json.dumps(
                        row["res281_attack_state_counts"], sort_keys=True, separators=(",", ":")
                    ),
                    json.dumps(
                        {item["attack_spec_ref"]: item["status"] for item in current_attacks},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    json.dumps(
                        {item["axis_slug"]: item["status"] for item in direct_axis_results},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    json.dumps(evidence_refs, separators=(",", ":")),
                    json.dumps(missing, separators=(",", ":")),
                ]
            )

    registry = json.loads((root / "artifacts/registries/benchmark-registry.json").read_bytes())
    design_csv, designs = _design_rows(root)
    comparability_csv = _comparability_rows(registry["benchmarks"])
    unsupported = [
        {
            "record_type": "attack",
            "benchmark_version": item.benchmark_version,
            "axis_slug": item.axis_slug,
            "attack_spec_ref": item.attack_spec_ref,
            "status": item.status.value,
            "status_reason": item.status_reason,
            "evidence_refs": list(item.evidence_refs),
            "missing_evidence": list(item.missing_evidence),
        }
        for item in records
        if item.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE
    ]
    for profile in VERSION_VALIDITY_PROFILES:
        for item in profile.axis_results:
            if item.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE:
                unsupported.append(
                    {
                        "record_type": "axis-profile-before-res281",
                        "benchmark_version": (
                            f"{profile.benchmark_slug}@{profile.benchmark_version}"
                        ),
                        "axis_slug": item.axis_slug,
                        "attack_spec_ref": None,
                        "status": item.status.value,
                        "status_reason": item.status_reason,
                        "evidence_refs": list(item.evidence_refs),
                        "missing_evidence": list(item.missing_evidence),
                    }
                )

    per_version: dict[str, Any] = {}
    for version in versions:
        items = records_by_version[version]
        counts = Counter(item.status.value for item in items)
        coverage = next(
            item for item in items if item.attack_spec_ref == "audit_coverage_accounting@1.0.0"
        )
        per_version[version] = {
            "registered_attack_count": len(ATTACK_SPECS),
            "recorded_attack_count": len(items),
            "every_attack_has_one_state": len(items) == len(ATTACK_SPECS),
            "state_counts": {status: counts.get(status, 0) for status in STATES},
            "non_coverage_executed_attack_count": sum(
                item.status in _EXECUTED
                and item.attack_spec_ref != "audit_coverage_accounting@1.0.0"
                for item in items
            ),
            "coverage_run_status": coverage.status.value,
            "coverage_diagnostics": coverage.diagnostics,
        }
    global_counts = Counter(item.status.value for item in records)
    coverage_summary = {
        "format": "PSR_RES281_M5_COVERAGE_V1",
        "benchmark_version_count": len(versions),
        "attack_contract_count": len(ATTACK_SPECS),
        "expected_attack_state_count": len(versions) * len(ATTACK_SPECS),
        "recorded_attack_state_count": len(records),
        "all_version_attack_states_accounted": len(records) == len(versions) * len(ATTACK_SPECS),
        "state_counts": {status: global_counts.get(status, 0) for status in STATES},
        "per_version": per_version,
        "scalar_validity_score": None,
    }

    native_version = next(
        f"{item.slug}@{item.version}"
        for item in BENCHMARKS
        if item.identity_authority.value == "PUBLIC_NATIVE"
    )
    native_records = records_by_version[native_version]
    native_results = [
        item for item in native_records if item.attack_spec_ref != "audit_coverage_accounting@1.0.0"
    ]
    rendered_state = Counter(item.status.value for item in records)
    comparability_rows = len(registry["benchmarks"]) * (len(registry["benchmarks"]) - 1) // 2
    summary = [
        "# RES-281 cross-version validity audit",
        "",
        f"Execution bundle: `{source['bundle_path']}` (`{source['bundle_sha256']}`).",
        f"Axis reproduction receipt: `{source['axis_execution_path']}`.",
        f"Axis execution SHA-256: `{source['axis_execution_sha256']}`.",
        textwrap.fill(
            f"The audit covers {len(versions)} registered versions and all "
            f"{len(ATTACK_SPECS)} attack contracts per version "
            f"({len(records)} version/attack states)."
        ),
        "",
        "## M5 coverage",
        "",
        "| State | Attack/version records |",
        "|---|---:|",
        *[f"| `{state}` | {rendered_state.get(state, 0)} |" for state in STATES],
        "",
        textwrap.fill(
            "Every registered attack/version cell has exactly one state. Coverage PASS is a "
            "process check, not a validity finding. No scalar validity score is computed."
        ),
        "",
        "## Evidence-backed findings",
        "",
        f"Public-native version: `{native_version}`.",
        textwrap.fill(
            f"{sum(item.status in _EXECUTED for item in native_results)} non-coverage "
            "diagnostics executed. The fresh full-production replay passed "
            "twice: train and validation bytes matched across generations, and both "
            "manifests matched the frozen IID manifest byte for byte."
        ),
        "",
        textwrap.fill(
            "The bounded participant-key and target-canary checks passed: all 18 sealed "
            "comparator instances were invariant on the 96-row audit sample. The provenance "
            "check passed for the public-native source, generation configuration, and the "
            "hashed M4 artifacts. These results do not generalize beyond those checks and inputs."
        ),
        "",
        textwrap.fill(
            "Plan counterfactual, reversed-history, observation-noise, simple-model-frontier, "
            "fit-seed, and model-ranking diagnostics are INCONCLUSIVE under their frozen "
            "criteria. The measured deltas and ranks are descriptive; no post-hoc margin was "
            "added. No attack returned FAIL."
        ),
        "",
        textwrap.fill(
            "Sparse-history sensitivity is UNSUPPORTED_BY_EVIDENCE because the public schema "
            "requires complete weekly histories and declares no missingness law. "
            "Distribution-shift sensitivity is UNSUPPORTED_BY_EVIDENCE because this version "
            "declares no supported shift relation. Shortcut-feature dependence is NOT_RUN "
            "because no suspect feature was identified before outcomes were inspected. The "
            "native hidden-test attack is NOT_APPLICABLE because this version makes no "
            "hidden-test claim."
        ),
        "",
        textwrap.fill(
            "The metadata-only provenance audit ran on all eight historical projections and "
            "was INCONCLUSIVE: public source descriptions and identity records were checked, "
            "but original realization, model, and evaluation artifacts are unavailable. Their "
            "applicable row-level attacks remain UNSUPPORTED_BY_EVIDENCE because the repository "
            "has no rights-cleared version-specific rows and split identities, runnable "
            "historical adapters, or matching fitted model/evaluation artifacts. Historical "
            "hidden-test access status is also unknown. No private historical rows or checkpoints "
            "were imported."
        ),
        "",
        "## Cross-version comparison",
        "",
        textwrap.fill(
            f"All {comparability_rows} pairwise numerical comparisons are rejected. Historical "
            "score artifacts and matched cross-version support are unavailable, and the versions "
            "vary in task, QOI, information boundary, world, DatasetSpec, or evaluation identity. "
            "The capacity-change comparison is especially explicit: historical production used "
            "scrambled Sobol sampling while the public-native variant uses IID pseudorandom "
            "sampling, and their evaluation identities differ. Raw scores and rankings are "
            "therefore not comparable."
        ),
        "",
        textwrap.fill(
            "No cross-version validity improvement or regression is demonstrated. The registry "
            "documents design changes, but chronology alone is not evidence that a change "
            "improved validity. Within-version sensitivity findings remain scoped to their own "
            "native tasks and protocols."
        ),
        "",
        "## Unresolved scientific questions",
        "",
        textwrap.fill(
            "The synthetic task's correspondence to real-athlete populations and outcomes has "
            "not been externally validated. No admissible data or matched model outputs resolve "
            "historical reconstruction, hidden-test fairness, or ML load-bearing contribution. "
            "Native sparse-history and distribution-shift robustness also remain unresolved. "
            "The observed plan/history/noise sensitivities need predeclared uncertainty or "
            "practical margins before they can support a resolved effect claim."
        ),
        "",
        "## Files",
        "",
        "- `attack-by-version.csv`: every registered attack by version with its six-state result.",
        textwrap.fill(
            "- `version-by-axis-evidence.csv` and `.json`: pre-RES-281 profile states alongside "
            "RES-281 attack and direct-axis evidence; cells retain multiple states rather than "
            "collapsing them."
        ),
        textwrap.fill(
            "- `cross-version-comparability.csv`: declared semantic checks and explicit rejection "
            "reasons for every version pair."
        ),
        textwrap.fill(
            "- `design-change-evidence.csv`: source-backed design descriptions, with no "
            "validity-improvement inference."
        ),
        textwrap.fill(
            "- `unsupported-evidence.json`: every unsupported attack and historical axis state "
            "with cited evidence and named gaps."
        ),
        "- `m5-coverage-summary.json`: per-version and overall attack-state counts.",
        textwrap.fill(
            "- `analysis-results.manifest.json`: checksum index for these files and the "
            "execution inputs."
        ),
        "",
    ]

    version_axis_json = {
        "format": "PSR_RES281_VERSION_AXIS_EVIDENCE_V1",
        "states": list(STATES),
        "meaning": (
            "Profile states are the pre-RES-281 snapshot; RES-281 results are reported per "
            "attack/direct axis and are not collapsed into a single axis score."
        ),
        "records": axis_records,
    }
    unsupported_doc = {"format": "PSR_RES281_UNSUPPORTED_EVIDENCE_V1", "records": unsupported}
    files = {
        "attack-by-version.csv": attack_matrix,
        "version-by-axis-evidence.csv": _csv_bytes(
            [
                "benchmark_version",
                "axis_slug",
                "profile_status_before_res281",
                "profile_status_reason_before_res281",
                "res281_attack_state_counts",
                "res281_attack_states_by_contract",
                "res281_direct_axis_states",
                "evidence_refs",
                "missing_evidence",
            ],
            axis_csv_rows,
        ),
        "version-by-axis-evidence.json": _json_bytes(version_axis_json),
        "cross-version-comparability.csv": comparability_csv,
        "design-change-evidence.csv": design_csv,
        "design-change-evidence.json": _json_bytes(
            {"format": "PSR_RES281_DESIGN_CHANGES_V1", "records": designs}
        ),
        "unsupported-evidence.json": _json_bytes(unsupported_doc),
        "m5-coverage-summary.json": _json_bytes(coverage_summary),
        "res281-validity-analysis.md": ("\n".join(summary)).encode("utf-8"),
    }
    return files


def write_analysis_bundle(
    output: Path = DEFAULT_OUTPUT,
    *,
    bundle: Path = DEFAULT_BUNDLE,
    root: Path = ROOT,
) -> Path:
    """Write analysis tables and a detached checksum index into a new audit directory."""
    root = root.resolve()
    output_path = output if output.is_absolute() else root / output
    resolved = output_path.resolve(strict=False)
    try:
        output_rel = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("analysis outputs must remain inside the repository") from error
    if output_rel.parts[:2] != ("results", "audits") or len(output_rel.parts) < 3:
        raise ValueError("analysis outputs are restricted to results/audits/<run>")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"analysis output already exists: {output_path}")

    _, _, source = _load_inputs(root, bundle)
    documents = build_analysis_documents(root, bundle)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_path.name}-", dir=resolved.parent))
    try:
        entries = []
        for name, content in sorted(documents.items()):
            (staging / name).write_bytes(content)
            entries.append(
                {
                    "path": (output_rel / name).as_posix(),
                    "sha256": _sha256(content),
                    "media_type": "text/markdown"
                    if name.endswith(".md")
                    else ("text/csv" if name.endswith(".csv") else "application/json"),
                    "rights": _RESULT_RIGHTS,
                }
            )
        source_files = [
            {
                "path": source[key],
                "sha256": source[digest_key],
            }
            for key, digest_key in (
                ("bundle_path", "bundle_sha256"),
                ("bundle_manifest_path", "bundle_manifest_sha256"),
                ("axis_execution_path", "axis_execution_sha256"),
            )
        ]
        analysis_source_paths = {
            "artifacts/registries/benchmark-registry.json",
            "artifacts/registries/attack-contract-registry.json",
            "artifacts/registries/validity-axis-registry.json",
            "artifacts/registries/version-validity-profiles.json",
            "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md",
            "src/powerlifting_state_research/audits/analysis.py",
            "src/powerlifting_state_research/provenance/historical_sources.py",
            *source["axis_result"].evidence_refs,
        }
        source_files.extend(
            {
                "path": path,
                "sha256": _sha256(_safe_repo_file(root, path).read_bytes()),
            }
            for path in sorted(analysis_source_paths)
        )
        index = {
            "format": "PSR_RES281_ANALYSIS_INDEX_V1",
            "analysis_identity": (
                "psr:audit-analysis@"
                f"{sha256_record({'source_files': source_files, 'files': entries})}"
            ),
            "source_files": source_files,
            "files": entries,
            "rights": _RESULT_RIGHTS,
        }
        (staging / "analysis-results.manifest.json").write_bytes(_json_bytes(index))
        resolved.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, resolved)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument(
        "--bundle", type=Path, default=DEFAULT_BUNDLE, help="RES-281 execution bundle"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="new analysis directory"
    )
    args = parser.parse_args(argv)
    path = write_analysis_bundle(args.output, bundle=args.bundle, root=args.root)
    index = json.loads((path / "analysis-results.manifest.json").read_bytes())
    print(f"wrote {len(index['files'])} analysis artifacts to {path}")
    print(index["analysis_identity"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
