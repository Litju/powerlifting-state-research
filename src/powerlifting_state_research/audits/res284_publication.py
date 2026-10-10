"""Build the RES-284 research publication from verified frozen artifacts."""

# Long evidence-bounded publication prose remains readable in generated documents.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, cast

from ..artifacts.hashes import sha256_record
from .analysis import _load_inputs
from .res283_analysis import METRIC_DIRECTIONS, METRICS, TARGETS, check_analysis
from .specifications import ATTACK_SPECS, VALIDITY_AXES, AuditStatus

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("results/audits/res284-publication")
RES278_DIR = Path("results/audits/res278")
RES281_DIR = Path("results/audits/res281")
RES281_ANALYSIS_DIR = Path("results/audits/res281-analysis")
RES283_ANALYSIS_DIR = Path("results/audits/res283-analysis")
EXPECTED_RES281_BUNDLE_SHA256 = (
    "sha256:0bbe5d58be59c8ba76fae1a9d6e4a116629b5c88fbdbfb32def6c4b9872bb597"
)
VALIDITY_STATES = (
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "NOT_APPLICABLE",
    "NOT_RUN",
    "UNSUPPORTED_BY_EVIDENCE",
)
STATE_SHORT = {
    "PASS": "P",
    "FAIL": "F",
    "INCONCLUSIVE": "I",
    "NOT_APPLICABLE": "NA",
    "NOT_RUN": "NR",
    "UNSUPPORTED_BY_EVIDENCE": "U",
}
STATE_COLORS = {
    "PASS": "#287d57",
    "FAIL": "#a63d40",
    "INCONCLUSIVE": "#b97812",
    "NOT_APPLICABLE": "#66717e",
    "NOT_RUN": "#366f9b",
    "UNSUPPORTED_BY_EVIDENCE": "#795a91",
}
FAMILY_COLORS = {
    "compact_neural": "#277da1",
    "context_mean": "#7f7f7f",
    "histogram_boosted_stumps": "#f3722c",
    "mechanistic_midpoint": "#43aa8b",
    "mechanistic_ridge_residual": "#577590",
    "public-native-temporal-expert": "#9b5de5",
    "ridge": "#f9c74f",
}
TARGET_LABELS = {
    "squat_delta_capacity_kg": "Squat capacity change",
    "bench_press_delta_capacity_kg": "Bench press capacity change",
    "deadlift_delta_capacity_kg": "Deadlift capacity change",
}
METRIC_UNITS = {"RMSE": "kg", "MAE": "kg", "R²": "unitless", "SRE(ddof=0)": "unitless"}
ATTACKS = (
    "audit_coverage_accounting@1.0.0",
    "baseline_domination@1.0.0",
    "distributional_shift_sensitivity@1.0.0",
    "hidden_test_fairness@1.0.0",
    "model_ranking_instability@1.0.0",
    "observation_noise_perturbation@1.0.0",
    "parameter_seed_sensitivity@1.0.0",
    "participant_input_leakage@1.0.0",
    "reconstruction_provenance_gaps@1.0.0",
    "shortcut_feature_dependence@1.0.0",
    "sparse_missing_history_sensitivity@1.0.0",
    "target_identity_contamination@1.0.0",
    "temporal_history_disruption@1.0.0",
    "training_plan_counterfactual_sensitivity@1.0.0",
)
STRESS_ATTACKS = {
    "observation_noise_perturbation@1.0.0",
    "temporal_history_disruption@1.0.0",
    "training_plan_counterfactual_sensitivity@1.0.0",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((root / relative).read_text(encoding="utf-8")))


def _read_csv(root: Path, relative: str) -> list[dict[str, str]]:
    with (root / relative).open(newline="", encoding="utf-8") as stream:
        return cast(list[dict[str, str]], list(csv.DictReader(stream)))


def _csv_bytes(rows: list[dict[str, Any]], fields: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _verify_file_entries(root: Path, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        path = root / str(entry["path"])
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise ValueError(f"source artifact checksum mismatch: {entry['path']}")


def _tracked_paths(root: Path) -> set[str]:
    entries = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    return {entry.decode("utf-8") for entry in entries if entry}


def _verify_audit_bundle(
    root: Path, directory: Path, tracked_paths: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_path = directory / "audit-results.manifest.json"
    manifest = _read_json(root, manifest_path.as_posix())
    if manifest.get("format") != "PSR_AUDIT_ARTIFACT_INDEX_V1":
        raise ValueError(f"unexpected audit artifact index: {manifest_path}")
    if manifest.get("bundle_path") != (directory / "audit-results.json").as_posix():
        raise ValueError(f"audit bundle path mismatch: {manifest_path}")
    bundle_path = root / str(manifest["bundle_path"])
    bundle_hash = _sha256(bundle_path)
    if bundle_hash != manifest.get("bundle_sha256"):
        raise ValueError(f"audit bundle hash mismatch: {bundle_path}")
    if manifest.get("bundle_identity") != f"psr:audit-bundle@{bundle_hash}":
        raise ValueError(f"audit bundle identity mismatch: {bundle_path}")
    _verify_file_entries(root, cast(list[dict[str, Any]], manifest["files"]))
    bundle = _read_json(root, manifest["bundle_path"])
    records = cast(list[dict[str, Any]], bundle["records"])
    artifacts = cast(list[dict[str, Any]], manifest["record_artifacts"])
    if len(records) != manifest.get("record_count") or len(artifacts) != len(records):
        raise ValueError(f"audit record count mismatch: {bundle_path}")
    if len(records) != 126:
        raise ValueError(f"expected 126 frozen audit records in {bundle_path}")
    input_status_by_path: dict[str, dict[str, Any]] = {}
    for index, (record, artifact) in enumerate(zip(records, artifacts, strict=True)):
        expected = f"/records/{index}"
        if artifact.get("json_pointer") != expected:
            raise ValueError(f"audit record pointer mismatch at {expected}")
        if artifact.get("identity") != record.get("result_artifact_identity"):
            raise ValueError(f"audit result identity mismatch at {expected}")
        if artifact.get("record_sha256") != record.get("result_artifact_sha256"):
            raise ValueError(f"audit record digest mismatch at {expected}")
        if artifact.get("serialized_record_sha256") != sha256_record(record):
            raise ValueError(f"serialized audit record hash mismatch at {expected}")
        if record.get("status") not in VALIDITY_STATES:
            raise ValueError(f"unknown audit status at {expected}")
        for input_artifact in cast(list[dict[str, Any]], record.get("input_artifacts", [])):
            source_path = str(input_artifact["path"])
            declared_sha256 = str(input_artifact["sha256"])
            if source_path in input_status_by_path:
                status_row = input_status_by_path[source_path]
                if status_row["declared_sha256"] != declared_sha256:
                    raise ValueError(f"conflicting audit input hashes: {source_path}")
                status_row["referring_record_count"] += 1
                continue
            if source_path in tracked_paths:
                input_path = root / source_path
                if not input_path.is_file() or _sha256(input_path) != declared_sha256:
                    raise ValueError(f"audit input artifact identity mismatch: {source_path}")
                observed_sha256 = _sha256(input_path)
                status = "VERIFIED_TRACKED_INPUT"
                reason = (
                    "Tracked source bytes match the SHA-256 declared by the frozen audit record."
                )
            elif source_path.startswith("data/synthetic/"):
                observed_sha256 = ""
                status = "UNAVAILABLE_UNTRACKED_GENERATED_INPUT"
                reason = (
                    "The generated IID source file is not tracked; its declared hash is retained, "
                    "but the file was not read or regenerated."
                )
            else:
                raise ValueError(
                    f"untracked audit input is outside the declared generated-data gap: {source_path}"
                )
            input_status_by_path[source_path] = {
                "execution": directory.name.upper(),
                "path": source_path,
                "declared_sha256": declared_sha256,
                "observed_sha256": observed_sha256,
                "source_evidence_status": status,
                "referring_record_count": 1,
                "rights_json": json.dumps(
                    input_artifact.get("rights", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "reason": reason,
            }
    return manifest, records, list(input_status_by_path.values())


def _verify_res281_analysis(root: Path) -> dict[str, Any]:
    path = RES281_ANALYSIS_DIR / "analysis-results.manifest.json"
    manifest = _read_json(root, path.as_posix())
    _verify_file_entries(root, cast(list[dict[str, Any]], manifest["files"]))
    _verify_file_entries(root, cast(list[dict[str, Any]], manifest["source_files"]))
    return manifest


def _verify_res283(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    index_path = RES283_ANALYSIS_DIR / "checksum-index.json"
    index = _read_json(root, index_path.as_posix())
    run_path = RES283_ANALYSIS_DIR / "run-manifest.json"
    run = _read_json(root, run_path.as_posix())
    if index.get("run_manifest_sha256") != _sha256(root / run_path):
        raise ValueError("RES-283 run-manifest checksum mismatch")
    for entry in cast(list[dict[str, Any]], index["files"]):
        artifact = root / str(entry["path"])
        if not artifact.is_file() or _sha256(artifact) != entry["sha256"]:
            raise ValueError(f"RES-283 checksum-index mismatch: {entry['path']}")
        if artifact.stat().st_size != entry.get("size_bytes"):
            raise ValueError(f"RES-283 artifact size mismatch: {entry['path']}")
    for entry in cast(list[dict[str, Any]], run["artifacts"]):
        if _sha256(root / str(entry["path"])) != entry["sha256"]:
            raise ValueError(f"RES-283 output identity mismatch: {entry['path']}")
    check_analysis(root)
    return index, run


def _input_paths(
    root: Path,
    res278_manifest: dict[str, Any],
    res281_manifest: dict[str, Any],
    res281_analysis: dict[str, Any],
    res283_index: dict[str, Any],
    tracked_paths: set[str],
    res278_records: list[dict[str, Any]],
    res281_records: list[dict[str, Any]],
) -> list[str]:
    paths = {
        "artifacts/registries/attack-contract-registry.json",
        "artifacts/registries/benchmark-registry.json",
        "artifacts/registries/validity-axis-registry.json",
        "artifacts/registries/version-validity-profiles.json",
        "docs/audits/index.md",
        "docs/benchmarks/comparability.md",
        "provenance/PUBLIC_FILE_ORIGINS.csv",
        "results/audits/res283-analysis/RES-284-handoff.md",
        "results/audits/res281-analysis/res281-validity-analysis.md",
        "results/audits/res281-analysis/m5-coverage-summary.json",
        "results/audits/res281-analysis/version-by-axis-evidence.csv",
        "results/audits/res281-analysis/attack-by-version.csv",
        "results/audits/res281-analysis/cross-version-comparability.csv",
        "results/audits/res281-analysis/design-change-evidence.csv",
        "results/audits/res281-analysis/unsupported-evidence.json",
        "results/audits/res281/reproducibility-execution.json",
        "tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py",
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
        "results/audits/res281-analysis/analysis-results.manifest.json",
        "results/audits/res283-analysis/run-manifest.json",
        "results/audits/res283-analysis/checksum-index.json",
        "results/audits/res283-analysis/res283-model-ranking-stability.md",
        "results/audits/res283-analysis/historical-evidence-gap-report.md",
        "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
        "results/audits/res283-analysis/fit-seed-rank-stability.csv",
        "results/audits/res283-analysis/fit-seed-pairwise-reversals.csv",
        "results/audits/res283-analysis/metric-dependent-ranking-summary.csv",
        "results/audits/res283-analysis/pairwise-ranking-reversals.csv",
        "results/audits/res283-analysis/pareto-comparison-summary.csv",
        "results/audits/res283-analysis/paired-uncertainty-evidence.csv",
        "results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        "results/audits/res283-analysis/version-by-model-evidence.csv",
        "src/powerlifting_state_research/audits/res283_analysis.py",
        "src/powerlifting_state_research/audits/res284_publication.py",
        "src/powerlifting_state_research/audits/runner.py",
        "src/powerlifting_state_research/audits/specifications.py",
    }
    for directory in (RES278_DIR, RES281_DIR):
        paths.add((directory / "audit-results.json").as_posix())
        paths.add((directory / "audit-results.manifest.json").as_posix())
    for entry in cast(list[dict[str, Any]], res278_manifest["files"]):
        paths.add(str(entry["path"]))
    for entry in cast(list[dict[str, Any]], res281_manifest["files"]):
        paths.add(str(entry["path"]))
    for entry in cast(list[dict[str, Any]], res281_analysis["files"]):
        paths.add(str(entry["path"]))
    for entry in cast(list[dict[str, Any]], res281_analysis["source_files"]):
        paths.add(str(entry["path"]))
    for entry in cast(list[dict[str, Any]], res283_index["files"]):
        paths.add(str(entry["path"]))
    for record in (*res278_records, *res281_records):
        for input_artifact in cast(list[dict[str, Any]], record.get("input_artifacts", [])):
            source_path = str(input_artifact["path"])
            if source_path in tracked_paths:
                paths.add(source_path)
    registry = _read_json(root, "artifacts/registries/benchmark-registry.json")
    for benchmark in cast(list[dict[str, Any]], registry["benchmarks"]):
        paths.add(f"docs/benchmarks/{str(benchmark['slug']).replace('_', '-')}.md")
    paths.add("docs/benchmarks/iid-latent-capacity-change-public-native-evaluation.md")
    for path in sorted(paths):
        if not (root / path).is_file():
            raise ValueError(f"publication input is missing: {path}")
    return sorted(paths)


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(record["status"]) for record in records)
    return {state: counts.get(state, 0) for state in VALIDITY_STATES}


def _evidence_claims() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "C01",
            "claim": "The RES-277 profile registry covers nine benchmark versions and keeps each registered axis state separate.",
            "evidence_class": "DESCRIPTIVE_COVERAGE",
            "evidence_state": "MEASURED",
            "scope_and_limit": "Coverage is process metadata, not a validity score.",
            "source_artifacts": "artifacts/registries/version-validity-profiles.json;results/audits/res281-analysis/version-by-axis-evidence.csv",
        },
        {
            "claim_id": "C02",
            "claim": "The RES-278 and RES-281 ledgers each preserve one of the six RES-277 states for every attack/version pair.",
            "evidence_class": "DESCRIPTIVE_COVERAGE",
            "evidence_state": "MEASURED",
            "scope_and_limit": "The two run bundles remain distinct and retain their original result identities.",
            "source_artifacts": "results/audits/res278/audit-results.json;results/audits/res281/audit-results.json",
        },
        {
            "claim_id": "C03",
            "claim": "The public-native IID comparison contains 22 candidate fitted-instance or ensemble identities over three targets and 3,072 prediction keys.",
            "evidence_class": "MEASURED_POINT_ESTIMATES",
            "evidence_state": "MEASURED",
            "scope_and_limit": "One DatasetRealization and one canonical RES-271 evaluation; no model was retrained or rescored.",
            "source_artifacts": "results/audits/res283-analysis/run-manifest.json;results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
        },
        {
            "claim_id": "C04",
            "claim": "The temporal-expert ensemble leads 11 of 12 target/metric point-estimate comparisons; squat MAE is led by temporal-expert seed 383003.",
            "evidence_class": "DESCRIPTIVE_POINT_ESTIMATE_ORDERING",
            "evidence_state": "DESCRIPTIVE",
            "scope_and_limit": "Point-estimate ordering only; it does not establish statistical significance or practical superiority.",
            "source_artifacts": "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
        },
        {
            "claim_id": "C05",
            "claim": "RMSE-versus-MAE model order reverses for 20 squat, 18 bench-press, and 19 deadlift candidate pairs.",
            "evidence_class": "DESCRIPTIVE_RANKING_SENSITIVITY",
            "evidence_state": "DESCRIPTIVE",
            "scope_and_limit": "Reversal counts describe this frozen candidate panel; they are not an inferential test.",
            "source_artifacts": "results/audits/res283-analysis/metric-dependent-ranking-summary.csv;results/audits/res283-analysis/pairwise-ranking-reversals.csv",
        },
        {
            "claim_id": "C06",
            "claim": "The saved three-seed panel has no observed pairwise rank reversals, but the RES-281 ranking-stability state remains INCONCLUSIVE.",
            "evidence_class": "DESCRIPTIVE_SMALL_SEED_PANEL",
            "evidence_state": "INCONCLUSIVE",
            "scope_and_limit": "Three stochastic fits are a small descriptive sample; deterministic repeats are not independent training replications.",
            "source_artifacts": "results/audits/res283-analysis/fit-seed-rank-stability.csv;results/audits/res283-analysis/fit-seed-pairwise-reversals.csv;results/audits/res281/audit-results.json",
        },
        {
            "claim_id": "C07",
            "claim": "The observed point-estimate Pareto front contains two squat candidates, one bench-press candidate, and one deadlift candidate.",
            "evidence_class": "DESCRIPTIVE_POINT_ESTIMATE_FRONTIER",
            "evidence_state": "DESCRIPTIVE",
            "scope_and_limit": "The finite frontier is descriptive; RES-281 baseline-domination remains INCONCLUSIVE without a margin or paired uncertainty.",
            "source_artifacts": "results/audits/res283-analysis/pareto-comparison-summary.csv;results/audits/res281/audit-results.json",
        },
        {
            "claim_id": "C08",
            "claim": "Participant-key relabeling produced no prediction mismatch in the registered comparator inference adapter.",
            "evidence_class": "BOUNDED_AUDIT_FINDING",
            "evidence_state": "PASS",
            "scope_and_limit": "The audit covers the six registered comparator families and 18 fitted states, not unregistered participant models.",
            "source_artifacts": "results/audits/res281/audit-results.json",
        },
        {
            "claim_id": "C09",
            "claim": "Copied target-canary rows produced no prediction mismatch in the registered comparator inference adapter.",
            "evidence_class": "BOUNDED_AUDIT_FINDING",
            "evidence_state": "PASS",
            "scope_and_limit": "This verifies the repository inference boundary; it does not establish leakage absence in external code.",
            "source_artifacts": "results/audits/res281/audit-results.json",
        },
        {
            "claim_id": "C10",
            "claim": "Plan swap, reversed-history, and fresh observation-noise diagnostics report prediction changes under their named synthetic interventions.",
            "evidence_class": "NAMED_SYNTHETIC_STRESS_DIAGNOSTICS",
            "evidence_state": "INCONCLUSIVE",
            "scope_and_limit": "All three outcomes remain INCONCLUSIVE; the observations do not establish broad OOD or real-athlete robustness.",
            "source_artifacts": "results/audits/res281/audit-results.json;results/audits/res281-analysis/attack-by-version.csv",
        },
        {
            "claim_id": "C11",
            "claim": "Paired IID uncertainty is unidentified because tracked validation target truth and row-to-entity mapping are unavailable.",
            "evidence_class": "MISSING_UNCERTAINTY_EVIDENCE",
            "evidence_state": "UNSUPPORTED_BY_EVIDENCE",
            "scope_and_limit": "All 264 target/candidate/metric uncertainty cells are unsupported; no bootstrap estimate is reported.",
            "source_artifacts": "results/audits/res283-analysis/paired-uncertainty-evidence.csv;results/audits/res283-analysis/run-manifest.json",
        },
        {
            "claim_id": "C12",
            "claim": "All 36 RES-281 cross-version numerical comparisons remain rejected; no cross-version ranking statistic is admissible.",
            "evidence_class": "HISTORICAL_COMPARABILITY_DECISION",
            "evidence_state": "UNSUPPORTED_BY_EVIDENCE",
            "scope_and_limit": "Unavailable matched evidence does not demonstrate ranking instability or stability.",
            "source_artifacts": "results/audits/res281-analysis/cross-version-comparability.csv;results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        },
        {
            "claim_id": "C13",
            "claim": "Eight historical versions lack a public matched fitted-model/evaluation panel, so their model rankings are not identifiable.",
            "evidence_class": "HISTORICAL_EVIDENCE_GAP",
            "evidence_state": "UNSUPPORTED_BY_EVIDENCE",
            "scope_and_limit": "The public-native IID panel is not substituted for the missing historical panels.",
            "source_artifacts": "results/audits/res283-analysis/historical-evidence-gap-report.md;results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        },
        {
            "claim_id": "C14",
            "claim": "Benchmark chronology and design changes do not establish validity improvement or an observed cross-version ranking effect.",
            "evidence_class": "HISTORICAL_INTERPRETATION_LIMIT",
            "evidence_state": "UNSUPPORTED_BY_EVIDENCE",
            "scope_and_limit": "Design changes are descriptive only; no causal effect or improvement statistic is estimated.",
            "source_artifacts": "results/audits/res281-analysis/design-change-evidence.csv;results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        },
        {
            "claim_id": "C15",
            "claim": "The temporal-expert source prediction-rights field remains NOASSERTION.",
            "evidence_class": "RIGHTS_PROVENANCE",
            "evidence_state": "MEASURED_METADATA",
            "scope_and_limit": "Only aggregate evaluation metadata is carried into the publication; raw predictions and checkpoints are not copied.",
            "source_artifacts": "results/audits/res283-analysis/version-by-model-evidence.csv;provenance/PUBLIC_FILE_ORIGINS.csv",
        },
        {
            "claim_id": "C16",
            "claim": "The RES-278/281 bundles, RES-281 analysis, and RES-283 outputs match their recorded checksums; all tracked audit inputs were byte-verified.",
            "evidence_class": "REPRODUCIBILITY_AND_PROVENANCE",
            "evidence_state": "INCONCLUSIVE",
            "scope_and_limit": "Two generated IID train/validation input files referenced by audit records are not tracked, so their declared hashes cannot be independently checked from this checkout.",
            "source_artifacts": "results/audits/res278/audit-results.manifest.json;results/audits/res281/audit-results.manifest.json;results/audits/res281-analysis/analysis-results.manifest.json;results/audits/res283-analysis/checksum-index.json",
        },
        {
            "claim_id": "C17",
            "claim": "The public-native IID realization reproduced twice with byte-identical train and validation files and matching manifests.",
            "evidence_class": "REPRODUCIBILITY_AND_PROVENANCE",
            "evidence_state": "PASS",
            "scope_and_limit": "This receipt covers only the public-native IID DatasetRealization and does not recreate historical scrambled-Sobol bytes.",
            "source_artifacts": "results/audits/res281/reproducibility-execution.json;data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
        },
        {
            "claim_id": "C18",
            "claim": "The RES-278/281 audit records retain hashes for two generated IID input files whose bytes are not tracked in Git.",
            "evidence_class": "SOURCE_BYTE_AVAILABILITY",
            "evidence_state": "UNSUPPORTED_BY_EVIDENCE",
            "scope_and_limit": "Declared hashes are preserved; no local ignored copy was read and no dataset was regenerated.",
            "source_artifacts": "results/audits/res278/audit-results.json;results/audits/res281/audit-results.json",
        },
    ]


def _limitations() -> list[dict[str, str]]:
    return [
        {
            "evidence_gap": "Paired IID uncertainty",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "No confidence interval, significance test, or practical superiority claim is supported.",
            "future_evidence_required": "Rights-cleared validation truth rows, row-to-entity mappings, and a predeclared paired uncertainty procedure with practical margins.",
            "source_artifacts": "results/audits/res283-analysis/paired-uncertainty-evidence.csv;results/audits/res283-analysis/run-manifest.json",
        },
        {
            "evidence_gap": "Seed stability beyond the saved panel",
            "current_state": "INCONCLUSIVE",
            "claim_boundary": "No observed reversals in three saved fit seeds do not establish stability across data seeds, split seeds, or future fits.",
            "future_evidence_required": "Additional independent fit, data, and split seeds under a predeclared protocol and rank-stability margin.",
            "source_artifacts": "results/audits/res283-analysis/fit-seed-rank-stability.csv;results/audits/res281/audit-results.json",
        },
        {
            "evidence_gap": "Historical model rankings",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "The eight historical rankings and all 36 cross-version comparisons are not identifiable from this public evidence.",
            "future_evidence_required": "Rights-cleared matched rows and evaluation truth, native adapters, one fixed fitted-model panel, and a common support/evaluation contract.",
            "source_artifacts": "results/audits/res283-analysis/historical-evidence-gap-report.md;results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        },
        {
            "evidence_gap": "Historical attack execution",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "Metadata-only provenance review cannot establish row-level leakage, reconstructability, or robustness.",
            "future_evidence_required": "Rights-cleared historical rows, split identities, supported version-specific adapters, and matching model/evaluation artifacts.",
            "source_artifacts": "results/audits/res281-analysis/unsupported-evidence.json;results/audits/res281-analysis/version-by-axis-evidence.csv",
        },
        {
            "evidence_gap": "Broad distribution-shift robustness",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "The named plan, history, and observation interventions do not establish broad out-of-distribution or real-athlete robustness.",
            "future_evidence_required": "A supported native shift declaration, preregistered targets and margins, and admissible paired evaluation evidence.",
            "source_artifacts": "results/audits/res281-analysis/attack-by-version.csv;results/audits/res281/audit-results.json",
        },
        {
            "evidence_gap": "Real-athlete validity",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "The available model and audit results concern synthetic benchmark worlds only.",
            "future_evidence_required": "A separate rights-cleared empirical validation design tied to a defined population and real-world estimand.",
            "source_artifacts": "docs/audits/index.md;results/audits/res283-analysis/RES-284-handoff.md",
        },
        {
            "evidence_gap": "Temporal-expert source prediction rights",
            "current_state": "NOASSERTION",
            "claim_boundary": "Repository presence does not establish rights to redistribute source predictions or checkpoints.",
            "future_evidence_required": "Explicit rights documentation before any source prediction or checkpoint redistribution.",
            "source_artifacts": "results/audits/res283-analysis/version-by-model-evidence.csv;provenance/PUBLIC_FILE_ORIGINS.csv",
        },
        {
            "evidence_gap": "Unavailable RES-278/281 IID input bytes",
            "current_state": "UNSUPPORTED_BY_EVIDENCE",
            "claim_boundary": "The records declare hashes for generated IID train and validation JSONL files that are not tracked, so those source bytes cannot be rechecked here.",
            "future_evidence_required": "A rights-cleared tracked copy or independent hash attestation for the declared files; no regeneration was performed for RES-284.",
            "source_artifacts": "results/audits/res278/audit-results.json;results/audits/res281/audit-results.json",
        },
    ]


def _wrap(value: str, limit: int) -> list[str]:
    words = value.replace("_", " ").split()
    lines: list[str] = []
    line = ""
    for word in words:
        if line and len(line) + len(word) + 1 > limit:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


def _svg_header(title: str, description: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        "<style>text{font-family:Arial,Helvetica,sans-serif;fill:#17212b}.title{font-size:22px;font-weight:700}.subtitle{font-size:13px;fill:#405161}.label{font-size:11px}.small{font-size:9px}.grid{stroke:#d8dde3;stroke-width:1}.axis{stroke:#344454;stroke-width:1.2}</style>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
    ]


def _svg_text(x: float, y: float, value: str, css: str = "label", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" text-anchor="{anchor}">'
        f"{html.escape(value)}</text>"
    )


def _svg_rect(
    x: float, y: float, width: float, height: float, fill: str, stroke: str = "#ffffff"
) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def _svg_bytes(parts: list[str]) -> bytes:
    content = "\n".join([*parts, "</svg>", ""])
    ET.fromstring(content)
    return content.encode("utf-8")


def _profile_figure(
    profiles: list[dict[str, Any]], axes: list[str], axis_evidence: dict[str, dict[str, str]]
) -> bytes:
    width = 1660
    left = 310
    top = 142
    cell_w = 128
    row_h = 31
    height = top + row_h * len(profiles) + 115
    parts = _svg_header(
        "Benchmark version by RES-277 validity axis",
        f"Categorical RES-277 baseline status for {len(profiles)} benchmark versions and {len(axes)} validity axes. A direct RES-281 axis state is shown separately in the cell when available; cells are not combined into a score.",
        width,
        height,
    )
    parts.extend([_svg_text(40, 38, "Version-by-axis validity profile", "title")])
    parts.append(
        _svg_text(
            40,
            64,
            "RES-277 profile snapshot; RES-281 executed evidence is shown in the attack matrix and version reports.",
            "subtitle",
        )
    )
    for column, axis in enumerate(axes):
        x = left + column * cell_w + cell_w / 2
        for line_idx, line in enumerate(_wrap(axis, 17)):
            parts.append(_svg_text(x, 103 + line_idx * 13, line, "small", "middle"))
    for row, profile in enumerate(profiles):
        y = top + row * row_h
        version = f"{profile['benchmark_slug']}@{profile['benchmark_version']}"
        for line_idx, line in enumerate(_wrap(str(profile["benchmark_slug"]), 38)[:2]):
            parts.append(_svg_text(left - 14, y + 14 + line_idx * 10, line, "small", "end"))
        states = {item["axis_slug"]: item["status"] for item in profile["axis_results"]}
        if set(states) != set(axes):
            raise ValueError(f"validity axis coverage mismatch for {version}")
        for column, axis in enumerate(axes):
            state = states[axis]
            x = left + column * cell_w
            direct_states = json.loads(
                axis_evidence[f"{version}::{axis}"]["res281_direct_axis_states"]
            )
            direct_label = ",".join(str(value) for value in direct_states.values()) or "—"
            parts.append(_svg_rect(x, y, cell_w - 2, row_h - 2, STATE_COLORS[state]))
            parts.append(
                _svg_text(x + (cell_w - 2) / 2, y + 12, STATE_SHORT[state], "small", "middle")
            )
            parts.append(
                _svg_text(x + (cell_w - 2) / 2, y + 24, f"direct {direct_label}", "small", "middle")
            )
    legend_x = 40
    legend_y = height - 54
    for state in VALIDITY_STATES:
        parts.append(_svg_rect(legend_x, legend_y - 13, 16, 14, STATE_COLORS[state]))
        parts.append(_svg_text(legend_x + 22, legend_y - 2, state, "small"))
        legend_x += 260
    parts.append(
        _svg_text(
            40,
            height - 15,
            f"All {len(axes)} axes remain separate; color and labels encode the exact six-state vocabulary.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _attack_figure(
    records_by_execution: dict[str, list[dict[str, Any]]], versions: list[str]
) -> bytes:
    width = 1660
    left = 460
    top = 98
    cell_w = 126
    row_h = 25
    panel_gap = 56
    panel_h = row_h * len(ATTACKS) + 38
    height = top + 2 * panel_h + panel_gap + 92
    parts = _svg_header(
        "Attack state coverage across RES-278 and RES-281",
        f"Two matrices show exact status for each of {len(ATTACKS)} registered attacks across {len(versions)} benchmark versions, separately for the RES-278 and RES-281 executions.",
        width,
        height,
    )
    parts.extend([_svg_text(40, 38, "Attack execution and evidence-state coverage", "title")])
    parts.append(
        _svg_text(
            40,
            63,
            "Each cell is one original audit state; run bundles and identities are kept separate.",
            "subtitle",
        )
    )
    for panel, execution in enumerate(("RES-278", "RES-281")):
        y0 = top + panel * (panel_h + panel_gap)
        parts.append(_svg_text(40, y0 + 19, execution, "label"))
        for column, version in enumerate(versions):
            x = left + column * cell_w + (cell_w - 4) / 2
            short = version.split("@", 1)[0]
            for line_idx, line in enumerate(_wrap(short, 18)[:2]):
                parts.append(_svg_text(x, y0 + 35 + line_idx * 10, line, "small", "middle"))
        lookup = {
            (str(record["benchmark_version"]), str(record["attack_spec_ref"])): record
            for record in records_by_execution[execution]
        }
        for row, attack in enumerate(ATTACKS):
            y = y0 + 60 + row * row_h
            parts.append(
                _svg_text(
                    left - 12,
                    y + 15,
                    attack.removesuffix("@1.0.0").replace("_", " "),
                    "small",
                    "end",
                )
            )
            for column, version in enumerate(versions):
                record = lookup[(version, attack)]
                state = str(record["status"])
                x = left + column * cell_w
                parts.append(_svg_rect(x, y, cell_w - 4, row_h - 2, STATE_COLORS[state]))
                parts.append(
                    _svg_text(x + (cell_w - 4) / 2, y + 15, STATE_SHORT[state], "small", "middle")
                )
    legend_x = 40
    legend_y = height - 45
    for state in VALIDITY_STATES:
        parts.append(_svg_rect(legend_x, legend_y - 13, 16, 14, STATE_COLORS[state]))
        parts.append(
            _svg_text(legend_x + 22, legend_y - 2, f"{STATE_SHORT[state]} = {state}", "small")
        )
        legend_x += 265
    parts.append(
        _svg_text(
            40,
            height - 15,
            "No state is weighted or converted into an overall validity score.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _model_metric_figure(rows: list[dict[str, str]], metric: str) -> bytes:
    panel_w = 490
    left_pad = 225
    plot_w = 215
    row_h = 19
    top = 102
    width = 3 * panel_w + 35
    height = top + 22 * row_h + 115
    direction = METRIC_DIRECTIONS[metric]
    candidate_count = len({row["candidate_id"] for row in rows})
    parts = _svg_header(
        f"Public-native target-wise {metric} comparison",
        f"Point estimates for all {candidate_count} candidate identities, faceted by target. {metric} is {direction}-is-better; no uncertainty intervals are shown.",
        width,
        height,
    )
    parts.extend([_svg_text(35, 38, f"Public-native IID model comparison — {metric}", "title")])
    parts.append(
        _svg_text(
            35,
            63,
            f"{metric}; {METRIC_UNITS[metric]}; {direction}-is-better. Candidate rows are ordered by the frozen target-wise rank.",
            "subtitle",
        )
    )
    for panel, target in enumerate(TARGETS):
        group = sorted(
            (row for row in rows if row["target"] == target),
            key=lambda row: (float(row[f"{metric}_rank"]), row["candidate_id"]),
        )
        if len(group) != 22:
            raise ValueError(f"expected 22 candidates for {target}")
        x0 = 20 + panel * panel_w
        plot_x = x0 + left_pad
        values = [float(row[metric]) for row in group]
        lo = min(values)
        hi = max(values)
        pad = (hi - lo) * 0.1 or max(abs(lo), 1.0) * 0.02
        axis_lo = lo - pad
        axis_hi = hi + pad
        parts.append(_svg_text(x0 + 6, 89, TARGET_LABELS[target], "label"))
        parts.append(
            f'<line x1="{plot_x}" y1="{top - 5}" x2="{plot_x}" y2="{top + 22 * row_h - 4}" class="axis"/>'
        )
        for tick in range(5):
            value = axis_lo + (axis_hi - axis_lo) * tick / 4
            x = plot_x + plot_w * tick / 4
            parts.append(
                f'<line x1="{x:.1f}" y1="{top - 5}" x2="{x:.1f}" y2="{top + 22 * row_h - 4}" class="grid"/>'
            )
            parts.append(_svg_text(x, top + 22 * row_h + 14, f"{value:.3f}", "small", "middle"))
        for index, row in enumerate(group):
            y = top + index * row_h
            family = row["model_family"]
            value = float(row[metric])
            x = plot_x + plot_w * (value - axis_lo) / (axis_hi - axis_lo)
            parts.append(_svg_text(plot_x - 8, y + 13, row["candidate_id"], "small", "end"))
            if row["candidate_role"] == "ensemble":
                parts.append(
                    f'<polygon points="{x:.1f},{y + 4:.1f} {x + 5:.1f},{y + 9:.1f} {x:.1f},{y + 14:.1f} {x - 5:.1f},{y + 9:.1f}" fill="{FAMILY_COLORS[family]}" stroke="#17212b" stroke-width="1"/>'
                )
            else:
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y + 9:.1f}" r="4" fill="{FAMILY_COLORS[family]}" stroke="#17212b" stroke-width="0.5"/>'
                )
            parts.append(_svg_text(plot_x + plot_w + 5, y + 13, f"{value:.4f}", "small"))
    legend_x = 35
    legend_y = height - 51
    for family, color in FAMILY_COLORS.items():
        parts.append(
            f'<circle cx="{legend_x + 5}" cy="{legend_y - 4}" r="5" fill="{color}" stroke="#17212b" stroke-width="0.5"/>'
        )
        parts.append(_svg_text(legend_x + 15, legend_y, family, "small"))
        legend_x += 190
    parts.append(
        _svg_text(
            35,
            height - 15,
            "These are point estimates from the frozen RES-283 table; exact values and rights fields are in public-native-target-wise-rankings.csv.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _metric_sensitivity_figure(rows: list[dict[str, str]]) -> bytes:
    pairs = list(dict.fromkeys((row["metric_a"], row["metric_b"]) for row in rows))
    width = 1280
    left = 330
    top = 120
    cell_w = 146
    row_h = 46
    height = top + 3 * row_h + 105
    parts = _svg_header(
        "Metric-dependent model ranking reversals",
        "Counts of pairwise rank reversals for each metric pair and target. Counts are descriptive and have no uncertainty or significance interpretation.",
        width,
        height,
    )
    parts.extend([_svg_text(35, 38, "Metric-dependent ranking sensitivity", "title")])
    parts.append(
        _svg_text(
            35,
            63,
            "Cell label: rank reversals / candidate pairs ordered on both metrics. Ties are retained in the table.",
            "subtitle",
        )
    )
    for column, pair in enumerate(pairs):
        label = f"{pair[0]} vs {pair[1]}"
        for line_idx, line in enumerate(_wrap(label, 17)):
            parts.append(
                _svg_text(
                    left + column * cell_w + cell_w / 2, 94 + line_idx * 12, line, "small", "middle"
                )
            )
    for row_index, target in enumerate(TARGETS):
        y = top + row_index * row_h
        parts.append(_svg_text(left - 12, y + 23, TARGET_LABELS[target], "label", "end"))
        for column, pair in enumerate(pairs):
            item = next(
                item
                for item in rows
                if item["target"] == target
                and item["metric_a"] == pair[0]
                and item["metric_b"] == pair[1]
            )
            x = left + column * cell_w
            reversals = int(item["rank_reversals"])
            ordered = int(item["pairs_ordered_on_both_metrics"])
            parts.append(
                _svg_rect(
                    x,
                    y,
                    cell_w - 3,
                    row_h - 3,
                    "#e8edf2" if reversals == 0 else "#f5d9ab",
                    "#aab5c0",
                )
            )
            parts.append(
                _svg_text(
                    x + (cell_w - 3) / 2, y + 19, f"{reversals} / {ordered}", "label", "middle"
                )
            )
    rmse_mae = [
        next(
            row
            for row in rows
            if row["target"] == target and row["metric_a"] == "RMSE" and row["metric_b"] == "MAE"
        )
        for target in TARGETS
    ]
    reversal_summary = "; ".join(
        f"{row['rank_reversals']}/{row['pairs_ordered_on_both_metrics']} {TARGET_LABELS[row['target']]}"
        for row in rmse_mae
    )
    parts.append(
        _svg_text(
            35,
            height - 55,
            "R² and SRE(ddof=0) are monotone transforms of RMSE for each fixed target; matching ranks are expected.",
            "small",
        )
    )
    parts.append(
        _svg_text(
            35,
            height - 34,
            f"RMSE-versus-MAE reversals from source table: {reversal_summary}.",
            "small",
        )
    )
    parts.append(
        _svg_text(
            35,
            height - 15,
            "No model is called universally best from these metric-dependent point rankings.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _seed_figure(rows: list[dict[str, str]]) -> bytes:
    families = list(dict.fromkeys(row["model_family"] for row in rows))
    columns = [(target, metric) for target in TARGETS for metric in METRICS]
    width = 1700
    left = 260
    top = 146
    cell_w = 116
    row_h = 34
    height = top + len(families) * row_h + 105
    seed_count = max(int(row["fit_seed_count"]) for row in rows)
    parts = _svg_header(
        "Fit-seed ranking ranges across the saved three-seed panel",
        f"Each cell gives the minimum and maximum ordinal rank observed across {seed_count} fit seeds for one family, target, and metric. Deterministic seed labels are not independent replications.",
        width,
        height,
    )
    parts.extend([_svg_text(35, 38, "Fit-seed ranking diagnostics", "title")])
    parts.append(
        _svg_text(
            35,
            63,
            "Each cell shows rank_min–rank_max across the saved seed labels; all ranges are descriptive.",
            "subtitle",
        )
    )
    for column, (target, metric) in enumerate(columns):
        x = left + column * cell_w + cell_w / 2
        target_label = {TARGETS[0]: "Squat", TARGETS[1]: "Bench", TARGETS[2]: "Deadlift"}[target]
        parts.append(_svg_text(x, 96, target_label, "small", "middle"))
        parts.append(_svg_text(x, 113, metric, "small", "middle"))
    lookup = {(row["model_family"], row["target"], row["metric"]): row for row in rows}
    for row_index, family in enumerate(families):
        y = top + row_index * row_h
        parts.append(_svg_text(left - 12, y + 19, family, "small", "end"))
        for column, (target, metric) in enumerate(columns):
            item = lookup[(family, target, metric)]
            x = left + column * cell_w
            parts.append(_svg_rect(x, y, cell_w - 2, row_h - 2, "#edf1f5", "#c8d0d8"))
            parts.append(
                _svg_text(
                    x + (cell_w - 2) / 2,
                    y + 19,
                    f"{float(item['rank_min']):g}–{float(item['rank_max']):g}",
                    "small",
                    "middle",
                )
            )
    parts.append(
        _svg_text(
            35,
            height - 52,
            "Temporal expert and compact neural rows have three distinct saved fits; other families repeat deterministic predictions across seed labels.",
            "small",
        )
    )
    parts.append(
        _svg_text(
            35,
            height - 31,
            "No pairwise rank reversals were observed within this three-seed panel; the RES-281 seed-stability status remains INCONCLUSIVE.",
            "small",
        )
    )
    parts.append(
        _svg_text(
            35,
            height - 12,
            "The full table keeps seed ranks, rank ranges, distinct prediction artifacts, and inference status by target and metric.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _pareto_figure(rows: list[dict[str, str]]) -> bytes:
    panel_w = 480
    panel_h = 430
    width = 3 * panel_w + 45
    height = panel_h + 220
    frontier_rows = {
        target: [row for row in rows if row["target"] == target and row["pareto_front"] == "True"]
        for target in TARGETS
    }
    parts = _svg_header(
        "Descriptive public-native IID Pareto frontiers",
        "RMSE versus MAE point estimates for all saved candidates by target. Dark rings mark candidates on the exact descriptive frontier; no uncertainty is shown.",
        width,
        height,
    )
    parts.extend([_svg_text(35, 38, "Public-native point-estimate Pareto summary", "title")])
    parts.append(
        _svg_text(
            35,
            63,
            "RMSE (kg) and MAE (kg), lower is better; a dark outline marks a non-dominated candidate.",
            "subtitle",
        )
    )
    for panel, target in enumerate(TARGETS):
        group = [row for row in rows if row["target"] == target]
        if len(group) != 22:
            raise ValueError(f"expected 22 Pareto candidates for {target}")
        x0 = 22 + panel * panel_w
        plot_x = x0 + 72
        plot_y = 110
        plot_w = 320
        plot_h = 290
        xs = [float(row["rmse_kg"]) for row in group]
        ys = [float(row["mae_kg"]) for row in group]
        xlo, xhi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        xpad = (xhi - xlo) * 0.08
        ypad = (yhi - ylo) * 0.08
        xlo -= xpad
        xhi += xpad
        ylo -= ypad
        yhi += ypad
        parts.append(_svg_text(x0 + 12, 91, TARGET_LABELS[target], "label"))
        parts.append(
            f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" class="axis"/>'
        )
        parts.append(
            f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" class="axis"/>'
        )
        for tick in range(5):
            xv = xlo + (xhi - xlo) * tick / 4
            yv = ylo + (yhi - ylo) * tick / 4
            x = plot_x + plot_w * tick / 4
            y = plot_y + plot_h - plot_h * tick / 4
            parts.append(
                f'<line x1="{x:.1f}" y1="{plot_y}" x2="{x:.1f}" y2="{plot_y + plot_h}" class="grid"/>'
            )
            parts.append(
                f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_w}" y2="{y:.1f}" class="grid"/>'
            )
            parts.append(_svg_text(x, plot_y + plot_h + 17, f"{xv:.2f}", "small", "middle"))
            parts.append(_svg_text(plot_x - 8, y + 3, f"{yv:.2f}", "small", "end"))
        for item in group:
            xv = float(item["rmse_kg"])
            yv = float(item["mae_kg"])
            x = plot_x + plot_w * (xv - xlo) / (xhi - xlo)
            y = plot_y + plot_h - plot_h * (yv - ylo) / (yhi - ylo)
            front = item["pareto_front"] == "True"
            family = item["model_family"]
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{6 if front else 4}" fill="{FAMILY_COLORS[family]}" stroke="{"#17212b" if front else "#ffffff"}" stroke-width="{2 if front else 0.8}"/>'
            )
            if front:
                parts.append(_svg_text(x + 8, y - 7, item["candidate_id"], "small"))
        parts.append(
            _svg_text(plot_x + plot_w / 2, plot_y + plot_h + 37, "RMSE (kg)", "small", "middle")
        )
    legend_x = 35
    legend_y = height - 120
    for family, color in FAMILY_COLORS.items():
        parts.append(
            f'<circle cx="{legend_x + 5}" cy="{legend_y - 4}" r="5" fill="{color}" stroke="#17212b" stroke-width="0.5"/>'
        )
        parts.append(_svg_text(legend_x + 15, legend_y, family, "small"))
        legend_x += 190
    for index, target in enumerate(TARGETS):
        frontier_candidates = frontier_rows[target]
        candidates = ", ".join(item["candidate_id"] for item in frontier_candidates) or "none"
        parts.append(
            _svg_text(
                35,
                height - 86 + 15 * index,
                f"{TARGET_LABELS[target]} frontier ({len(frontier_candidates)}): {candidates}.",
                "small",
            )
        )
    parts.append(
        _svg_text(
            35,
            height - 15,
            "R² and SRE(ddof=0) are monotone transforms of RMSE for a fixed target and add no independent ordering.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _historical_figure(
    versions: list[str], pairs: list[dict[str, str]], display_names: dict[str, str]
) -> bytes:
    label_w = 340
    cell_w = 102
    top = 198
    row_h = 38
    width = label_w + len(versions) * cell_w + 55
    height = top + len(versions) * row_h + 85
    parts = _svg_header(
        "Historical cross-version numerical admissibility matrix",
        f"{len(versions)}-version matrix with {len(pairs)} off-diagonal cross-version pairs, each rejected for numerical comparison. Diagonal cells are within-version and outside this matrix.",
        width,
        height,
    )
    parts.extend([_svg_text(35, 38, "Historical cross-version admissibility", "title")])
    parts.append(
        _svg_text(
            35,
            63,
            f"All {len(pairs)} cross-version pairs remain REJECTED_FOR_NUMERICAL_COMPARISON.",
            "subtitle",
        )
    )
    labels = [version.split("@", 1)[0] for version in versions]
    for column, version in enumerate(versions):
        x = label_w + column * cell_w + cell_w / 2
        for line_idx, line in enumerate(_wrap(display_names[version], 16)):
            parts.append(_svg_text(x, top - 76 + line_idx * 11, line, "small", "middle"))
    for row in range(len(versions)):
        y = top + row * row_h
        for line_idx, line in enumerate(_wrap(labels[row], 38)[:2]):
            parts.append(_svg_text(label_w - 12, y + 14 + line_idx * 10, line, "small", "end"))
        for column in range(len(versions)):
            x = label_w + column * cell_w
            if row == column:
                fill = "#f3f5f7"
                label = "—"
            else:
                fill = "#b85c5c"
                label = "REJ"
            parts.append(_svg_rect(x, y, cell_w - 2, row_h - 2, fill, "#ffffff"))
            parts.append(_svg_text(x + (cell_w - 2) / 2, y + 23, label, "small", "middle"))
    if len(pairs) != 36:
        raise ValueError("expected 36 rejected cross-version pairs")
    parts.append(
        _svg_text(
            35,
            height - 39,
            "REJ = rejected for numerical comparison; — = same-version diagonal, not a cross-version test.",
            "small",
        )
    )
    parts.append(
        _svg_text(
            35,
            height - 17,
            "No ranking coefficient, chronological improvement, or raw Sobol-versus-IID comparison is calculated.",
            "small",
        )
    )
    return _svg_bytes(parts)


def _analysis_data(root: Path) -> dict[str, Any]:
    tracked_paths = _tracked_paths(root)
    res278_manifest, res278_records, res278_input_status = _verify_audit_bundle(
        root, RES278_DIR, tracked_paths
    )
    res281_manifest, res281_records, res281_input_status = _verify_audit_bundle(
        root, RES281_DIR, tracked_paths
    )
    if res281_manifest.get("bundle_sha256") != EXPECTED_RES281_BUNDLE_SHA256:
        raise ValueError("RES-281 bundle does not match the verified RES-284 handoff hash")
    res281_analysis = _verify_res281_analysis(root)
    res283_index, res283_run = _verify_res283(root)
    if (
        res283_run.get("cross_version_pair_count") != 36
        or res283_run.get("admissible_cross_version_pair_count") != 0
    ):
        raise ValueError("RES-283 historical comparison counts do not match the handoff")
    reproducibility = _read_json(root, "results/audits/res281/reproducibility-execution.json")
    reproduction_result = reproducibility["result"]
    reproduction_execution = reproducibility["execution"]
    reproduction_record = next(
        (
            item
            for item in cast(list[dict[str, Any]], res281_manifest["axis_executions"])
            if item["axis_slug"] == "reproducibility"
        ),
        None,
    )
    if (
        reproduction_record is None
        or reproduction_result["status"] != "PASS"
        or reproduction_result["benchmark_version"]
        != "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0"
        or reproduction_result["run_id"] != reproduction_execution["run_id"]
        or reproduction_record["run_id"] != reproduction_execution["run_id"]
        or reproduction_record["result_sha256"] != _sha256(root / str(reproduction_record["path"]))
        or reproduction_result["diagnostics"]["repeat_count"] != 2
        or not reproduction_result["diagnostics"]["train_jsonl_byte_identical"]
        or not reproduction_result["diagnostics"]["validation_jsonl_byte_identical"]
    ):
        raise ValueError("RES-281 public-native reproduction receipt identity/status mismatch")
    _, _, verified_res281_source = _load_inputs(root, RES281_DIR)
    if (
        verified_res281_source["axis_result"].status is not AuditStatus.PASS
        or verified_res281_source["axis_result"].run_id != reproduction_execution["run_id"]
        or verified_res281_source["axis_execution_sha256"] != reproduction_record["result_sha256"]
    ):
        raise ValueError(
            "RES-281 typed reproduction receipt failed independent analysis validation"
        )

    registry = _read_json(root, "artifacts/registries/benchmark-registry.json")
    axes_doc = _read_json(root, "artifacts/registries/validity-axis-registry.json")
    base_profiles = _read_json(root, "artifacts/registries/version-validity-profiles.json")
    axis_registry = cast(list[dict[str, Any]], axes_doc.get("axes", []))
    axes = [str(item["slug"]) for item in axis_registry]
    typed_axes = [item.slug for item in VALIDITY_AXES]
    profiles = cast(list[dict[str, Any]], base_profiles["profiles"])
    versions = [f"{item['benchmark_slug']}@{item['benchmark_version']}" for item in profiles]
    if len(versions) != 9 or len(set(versions)) != 9 or axes != typed_axes or len(axes) != 10:
        raise ValueError("RES-277 version/axis coverage is not nine-by-ten")
    if set(VALIDITY_STATES) != {item.value for item in AuditStatus}:
        raise ValueError("publication status vocabulary differs from typed RES-277 contracts")
    typed_attacks = {item.reference for item in ATTACK_SPECS}
    if set(ATTACKS) != typed_attacks:
        raise ValueError("publication attack list differs from typed RES-277 contracts")
    if any(
        item.get("status") not in VALIDITY_STATES
        for profile in profiles
        for item in profile["axis_results"]
    ):
        raise ValueError("a RES-277 axis status is outside the six-state vocabulary")
    for family, expected in METRIC_DIRECTIONS.items():
        if expected not in {"lower", "higher"} or family not in METRIC_UNITS:
            raise ValueError(f"metric direction or unit missing for {family}")
    metric_ids = cast(list[str], res283_run["metric_ids"])
    metric_id_fragments = (
        "metric:rmse@",
        "metric:mae@",
        "metric:r-squared@",
        "metric:sre-population-sd-ddof-0@",
    )
    if len(metric_ids) != len(METRICS) or any(
        fragment not in metric_id
        for fragment, metric_id in zip(metric_id_fragments, metric_ids, strict=True)
    ):
        raise ValueError("RES-283 metric identities do not match the frozen metric order")
    metric_definitions = [
        {
            "metric": metric,
            "metric_identity": metric_id,
            "unit": METRIC_UNITS[metric],
            "preferred_direction": METRIC_DIRECTIONS[metric],
        }
        for metric, metric_id in zip(METRICS, metric_ids, strict=True)
    ]

    version_axis = _read_csv(root, "results/audits/res281-analysis/version-by-axis-evidence.csv")
    attack_by_version = _read_csv(root, "results/audits/res281-analysis/attack-by-version.csv")
    target_rows = _read_csv(
        root, "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv"
    )
    model_evidence = _read_csv(root, "results/audits/res283-analysis/version-by-model-evidence.csv")
    metric_rows = _read_csv(
        root, "results/audits/res283-analysis/metric-dependent-ranking-summary.csv"
    )
    seed_rows = _read_csv(root, "results/audits/res283-analysis/fit-seed-rank-stability.csv")
    seed_pair_rows = _read_csv(
        root, "results/audits/res283-analysis/fit-seed-pairwise-reversals.csv"
    )
    pareto_rows = _read_csv(root, "results/audits/res283-analysis/pareto-comparison-summary.csv")
    uncertainty_rows = _read_csv(
        root, "results/audits/res283-analysis/paired-uncertainty-evidence.csv"
    )
    historical_rows = _read_csv(
        root, "results/audits/res283-analysis/cross-version-ranking-admissibility.csv"
    )
    genealogy_rows = _read_csv(root, "results/audits/res281-analysis/design-change-evidence.csv")
    if len(target_rows) != 66 or len({row["candidate_id"] for row in target_rows}) != 22:
        raise ValueError("RES-283 public-native candidate panel does not match 22 identities")
    if set(row["target"] for row in target_rows) != set(TARGETS):
        raise ValueError("RES-283 target set does not match the frozen QOI")
    if any(row["within_version_comparison_status"] != "ADMISSIBLE" for row in target_rows):
        raise ValueError("RES-283 IID rows contain a non-admissible candidate comparison")
    winners: dict[tuple[str, str], dict[str, str]] = {}
    ensemble_wins = 0
    for target in TARGETS:
        for metric in METRICS:
            ranked = [
                row
                for row in target_rows
                if row["target"] == target and row[f"{metric}_rank"] == "1.0"
            ]
            if len(ranked) != 1:
                raise ValueError(
                    f"target/metric does not have one exact rank-1 candidate: {target} {metric}"
                )
            winners[(target, metric)] = ranked[0]
            ensemble_wins += ranked[0]["candidate_id"] == "public-native-temporal-expert:ensemble"
    if (
        ensemble_wins != 11
        or winners[(TARGETS[0], "MAE")]["candidate_id"] != "public-native-temporal-expert:383003"
    ):
        raise ValueError("RES-283 target/metric point-estimate winners differ from the handoff")
    if len(historical_rows) != 36 or any(
        row["original_res281_decision"] != "REJECTED_FOR_NUMERICAL_COMPARISON"
        for row in historical_rows
    ):
        raise ValueError("historical pairwise admissibility changed")
    if any(
        row["admissibility_classification"] != "REJECTED_FOR_NUMERICAL_COMPARISON"
        for row in historical_rows
    ):
        raise ValueError("RES-283 includes an admissible cross-version pair")
    if len(uncertainty_rows) != 264 or any(
        row["status"] != "UNSUPPORTED_BY_EVIDENCE" or row["inference_status"] != "INCONCLUSIVE"
        for row in uncertainty_rows
    ):
        raise ValueError("paired uncertainty states do not match the RES-283 handoff")
    if any(int(row["pairwise_seed_rank_reversals"]) != 0 for row in seed_pair_rows):
        raise ValueError("a saved three-seed pairwise rank reversal is present")
    if any(float(row["rank_range"]) != 0.0 for row in seed_rows):
        raise ValueError("a saved fit-family rank range is present")
    if any(int(row["pairs_ordered_on_both_metrics"]) != 216 for row in metric_rows):
        raise ValueError("metric reversal denominator differs from the frozen panel")

    records_by_execution = {"RES-278": res278_records, "RES-281": res281_records}
    for execution, records in records_by_execution.items():
        if (
            len(records) != 126
            or len({(item["benchmark_version"], item["attack_spec_ref"]) for item in records})
            != 126
        ):
            raise ValueError(f"{execution} does not contain exactly one result per version/attack")
        if {item["benchmark_version"] for item in records} != set(versions):
            raise ValueError(f"{execution} versions differ from the RES-277 profile registry")
    missing_input_paths = {
        row["path"]
        for row in (*res278_input_status, *res281_input_status)
        if row["source_evidence_status"] == "UNAVAILABLE_UNTRACKED_GENERATED_INPUT"
    }
    expected_missing_input_paths = {
        "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production/train.jsonl",
        "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production/validation.jsonl",
    }
    if missing_input_paths != expected_missing_input_paths:
        raise ValueError("frozen audit generated-input availability differs from its declared gap")
    for execution, input_rows in (
        ("RES-278", res278_input_status),
        ("RES-281", res281_input_status),
    ):
        missing_for_execution = {
            row["path"]
            for row in input_rows
            if row["source_evidence_status"] == "UNAVAILABLE_UNTRACKED_GENERATED_INPUT"
        }
        if missing_for_execution != expected_missing_input_paths:
            raise ValueError(f"{execution} source-byte gap differs from the frozen audit records")
    result_lookup = {
        (str(record["benchmark_version"]), str(record["attack_spec_ref"])): str(record["status"])
        for record in res281_records
    }
    for row in attack_by_version:
        attack = str(row["attack_spec_ref"])
        for version in versions:
            if result_lookup[(version, attack)] != row[version]:
                raise ValueError(
                    f"RES-281 attack matrix differs from its result record: {version} {attack}"
                )

    benchmark_by_version = {
        f"{item['slug']}@{item['version']}": item
        for item in cast(list[dict[str, Any]], registry["benchmarks"])
    }
    model_rights = {
        row["model_family"]: row["rights_access_constraints"]
        for row in model_evidence
        if row["benchmark_version"] == versions[3]
    }
    if "NOASSERTION" not in model_rights.get("public-native-temporal-expert", ""):
        raise ValueError(
            "temporal-expert source prediction rights are not preserved as NOASSERTION"
        )
    for target in TARGETS:
        target_panel = [row for row in pareto_rows if row["target"] == target]
        if len(target_panel) != 22:
            raise ValueError(f"Pareto panel candidate count changed for {target}")

    source_paths = _input_paths(
        root,
        res278_manifest,
        res281_manifest,
        res281_analysis,
        res283_index,
        tracked_paths,
        res278_records,
        res281_records,
    )
    return {
        "axes": axes,
        "attack_by_version": attack_by_version,
        "base_profiles": profiles,
        "benchmark_by_version": benchmark_by_version,
        "benchmark_registry": registry,
        "records_by_execution": records_by_execution,
        "source_paths": source_paths,
        "versions": versions,
        "version_axis": version_axis,
        "target_rows": target_rows,
        "model_evidence": model_evidence,
        "model_rights": model_rights,
        "metric_definitions": metric_definitions,
        "metric_rows": metric_rows,
        "seed_rows": seed_rows,
        "seed_pair_rows": seed_pair_rows,
        "pareto_rows": pareto_rows,
        "uncertainty_rows": uncertainty_rows,
        "historical_rows": historical_rows,
        "genealogy_rows": genealogy_rows,
        "winners": winners,
        "res278_manifest": res278_manifest,
        "res281_manifest": res281_manifest,
        "res281_analysis": res281_analysis,
        "res283_index": res283_index,
        "res283_run": res283_run,
        "reproducibility_execution": reproducibility,
        "res278_records": res278_records,
        "res281_records": res281_records,
        "audit_input_status": [*res278_input_status, *res281_input_status],
    }


def _profile_markdown(
    version: str,
    profile: dict[str, Any],
    benchmark: dict[str, Any],
    axis_rows: dict[str, dict[str, str]],
    records_by_execution: dict[str, list[dict[str, Any]]],
    axis_names: list[str],
    model_evidence: list[dict[str, str]],
    reproducibility_execution: dict[str, Any],
    root: Path,
) -> str:
    slug = str(benchmark["slug"])
    doc_path = f"docs/benchmarks/{slug.replace('_', '-')}.md"
    if slug.startswith("iid_"):
        doc_path = (
            "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md"
        )
    if not (root / doc_path).is_file():
        raise ValueError(f"version document missing: {doc_path}")
    references = benchmark["component_references"]
    component = {str(item["component_class"]): item for item in references}
    world_key = component.get("WORLD", {}).get("canonical_key") or "unresolved"
    dataset_key = component.get("DATASET_SPEC", {}).get("canonical_key") or "unresolved"
    task_key = component.get("TASK", {}).get("canonical_key") or "unresolved"
    qoi_key = component.get("QOI", {}).get("canonical_key") or "unresolved"
    worlds = {str(item["slug"]): item for item in benchmark.get("worlds", [])}
    world_text = worlds.get(str(world_key), {}).get("scientific_summary", "")
    registry_worlds = _read_json(root, "artifacts/registries/benchmark-registry.json").get(
        "worlds", []
    )
    world_text = next(
        (
            item.get("scientific_summary", "")
            for item in registry_worlds
            if item.get("slug") == world_key
        ),
        world_text,
    )
    research = benchmark["research"]
    design = next(
        (
            row
            for row in _read_csv(root, "results/audits/res281-analysis/design-change-evidence.csv")
            if row["benchmark_version"] == version
        ),
        None,
    )
    if design is None:
        raise ValueError(f"RES-281 genealogy row missing for {version}")
    profile_axes = {str(item["axis_slug"]): item for item in profile["axis_results"]}
    if set(profile_axes) != set(axis_names):
        raise ValueError(f"profile axis list incomplete for {version}")
    result_lookup = {
        (str(record["benchmark_version"]), str(record["attack_spec_ref"]), execution): record
        for execution, records in records_by_execution.items()
        for record in records
    }
    profile_attacks = {
        str(ref): item for item in profile["attack_results"] for ref in item["attack_spec_refs"]
    }
    model_rows = [item for item in model_evidence if item["benchmark_version"] == version]
    if not model_rows:
        raise ValueError(f"RES-283 model evidence row missing for {version}")
    model_statuses = {item["native_ranking_status"] for item in model_rows}
    if len(model_statuses) != 1:
        raise ValueError(f"RES-283 model evidence status differs within version {version}")
    reproduction_result = reproducibility_execution["result"]
    direct_reproduction = (
        f"{reproduction_result['status']} in run {reproduction_result['run_id']}"
        if reproduction_result["benchmark_version"] == version
        else "No direct RES-281 reproduction execution was recorded for this version."
    )
    provenance_records = {
        execution: result_lookup[(version, "reconstruction_provenance_gaps@1.0.0", execution)]
        for execution in ("RES-278", "RES-281")
    }
    parts = [
        f"# {benchmark['display_name']}",
        "",
        f"Benchmark version: {version}",
        "",
        "## Task, targets, and information boundary",
        "",
        f"Research question: {research['canonical_research_question']}",
        "",
        f"Task: {benchmark['task_type']} ({task_key}). QOI: {benchmark['target_ontology']} ({qoi_key}).",
        "",
        f"World: {world_key}. {world_text}",
        "",
        f"Sampling design: {dataset_key} ({component.get('DATASET_SPEC', {}).get('resolution', 'UNRESOLVED_DIRECT_ID')}).",
        "",
        f"Participant-visible boundary: {research.get('source_prediction_setting', 'No prediction-time boundary is documented.')}",
        "",
        "## Historical and identity context",
        "",
        f"Identity authority: {benchmark['identity_authority']}; historical specimen: {benchmark['historical_specimen_status']}; qualification: {benchmark['historical_qualification_state']}; completeness: {benchmark['completeness_status']}; public implementation: {benchmark['public_implementation_status']}.",
        "",
        f"Benchmark identity: {benchmark.get('benchmark_id') or 'not minted'}; semantic digest: {benchmark.get('semantic_digest') or 'not minted'}.",
        "",
        f"Design context (descriptive only): {design['primary_design_change_descriptive_only']}",
        "",
        f"Historical lineage fields: parent specimen {design['parent_specimen_id'] or 'not recorded'}; parentage status {design['parentage_status'] or 'not recorded'}.",
        "",
        f"Source version document: {doc_path}",
        "",
        "## Axis profile and applicability",
        "",
        "The state shown here is the RES-277 profile snapshot before RES-281. Direct RES-281 axis findings and attack states remain in separate columns/tables; no axis score is computed.",
        "",
        "| Axis | Applicable in profile | RES-277 profile state | RES-281 direct states | Missing evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for axis in axis_names:
        base = profile_axes[axis]
        row = axis_rows[axis]
        applicable = "No" if base["status"] == "NOT_APPLICABLE" else "Yes"
        parts.append(
            f"| {axis} | {applicable} | {base['status']} | {row['res281_direct_axis_states']} | {row['missing_evidence']} |"
        )
    parts.extend(
        [
            "",
            "## Executed audits and findings",
            "",
            "Both frozen run bundles are listed without merging their result identities. Full diagnostics, missing-evidence lists, evidence references, and run IDs are in tables/attack-evidence-states.csv.",
            "",
            "| Attack | RES-277 profile state | RES-278 state | RES-281 state | RES-281 finding |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for attack in ATTACKS:
        base = profile_attacks.get(attack, {})
        older = result_lookup[(version, attack, "RES-278")]
        current = result_lookup[(version, attack, "RES-281")]
        reason = str(current.get("status_reason") or "No execution was recorded.")
        if current.get("missing_evidence"):
            reason += " Missing: " + "; ".join(str(item) for item in current["missing_evidence"])
        if current.get("run_id"):
            reason += f" Diagnostics: see run {current['run_id']} and its result identity {current['result_artifact_identity']}."
        parts.append(
            f"| {attack} | {base.get('status', 'not recorded')} | {older['status']} | {current['status']} | {reason} |"
        )
    axis_evidence = sorted(
        {ref for row in axis_rows.values() for ref in json.loads(row["evidence_refs"])}
    )
    parts.extend(
        [
            "",
            "## Available evidence and provenance",
            "",
            f"RES-281 evidence references: {'; '.join(axis_evidence)}.",
            "",
            "RES-283 model/evaluation evidence status: " + next(iter(model_statuses)) + ".",
            "",
            "| Model family | Evidence status | Candidate count | Matched evidence | Source prediction-rights constraints |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for item in model_rows:
        parts.append(
            f"| {item['model_family']} | {item['model_family_evidence_status']} | {item['candidate_count']} | {item['row_level_matched_evidence']} | {item['rights_access_constraints']} |"
        )
    parts.extend(
        [
            "",
            f"RES-277 reproducibility profile state: {profile_axes['reproducibility']['status']}. RES-281 direct reproduction: {direct_reproduction}",
            "",
            f"RES-278 provenance-review state: {provenance_records['RES-278']['status']} ({provenance_records['RES-278'].get('run_id') or 'no run'}); RES-281 provenance-review state: {provenance_records['RES-281']['status']} ({provenance_records['RES-281'].get('run_id') or 'no run'}). These provenance-review states do not establish historical row-level reconstructability.",
            "",
            f"Reproducibility state and provenance are recorded independently. Public implementation status is {benchmark['public_implementation_status']}; the presence of a specification or audit record does not assert reconstruction of unavailable private rows, model outputs, or checkpoints.",
            "",
            "## Interpretation boundary",
            "",
            "The audit state is bounded by the named version and evidence listed above. Missing, unsupported, not-run, and not-applicable results are not converted to favorable or unfavorable validity scores.",
            "",
        ]
    )
    return "\n".join(parts)


def _profile_name(profile: dict[str, Any]) -> str:
    return f"{profile['benchmark_slug']}@{profile['benchmark_version']}"


def _report_markdown(data: dict[str, Any]) -> str:
    winners = data["winners"]
    winner_lines = [
        "| Target | Metric | Rank-1 candidate | Point estimate | Unit |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for target in TARGETS:
        for metric in METRICS:
            row = winners[(target, metric)]
            winner_lines.append(
                f"| {TARGET_LABELS[target]} | {metric} | {row['candidate_id']} | {row[metric]} | {METRIC_UNITS[metric]} |"
            )
    status_lines = []
    for execution, records in data["records_by_execution"].items():
        counts = _status_counts(records)
        status_lines.append(
            f"| {execution} | {len(records)} | "
            + " | ".join(str(counts[state]) for state in VALIDITY_STATES)
            + " |"
        )
    profile_links = [
        f"- [{data['benchmark_by_version'][version]['display_name']}](profiles/{version.split('@', 1)[0]}.md)"
        for version in data["versions"]
    ]
    sources = "results/audits/res283-analysis/run-manifest.json, results/audits/res283-analysis/checksum-index.json, and the per-target RES-283 analysis CSVs"
    return "\n".join(
        [
            "# Benchmark validity and historical ranking sensitivity",
            "",
            "RES-284 research-facing synthesis. All result states and scientific identities are inherited from the frozen RES-277/278/281/283 artifacts.",
            "",
            "## Findings in brief",
            "",
            "- The audit suite describes coverage across nine benchmark versions and ten validity axes. It does not produce a universal validity score.",
            "- One model panel is admissible for target-wise comparison: the public-native IID realization, seven families, 22 candidate fitted-instance/ensemble identities, three targets, and 3,072 shared prediction keys.",
            "- The temporal-expert ensemble leads 11/12 target-metric point-estimate comparisons. Squat MAE is led by temporal-expert seed 383003. These are descriptive point rankings, without statistical-significance or practical-superiority claims.",
            "- The saved three-seed panel has no observed fit-seed ranking reversal. This does not establish stability outside that panel; deterministic seed repeats are not independent fit replications.",
            "- Paired uncertainty remains unidentified because tracked validation target truth and row-to-entity mappings are absent. All 264 uncertainty cells remain UNSUPPORTED_BY_EVIDENCE with inference INCONCLUSIVE.",
            "- All 36 historical cross-version numerical comparisons remain rejected. Eight historical versions lack public matched fitted-model/evaluation panels, so their rankings are not identifiable.",
            "",
            "## Scope and identities",
            "",
            f"Public-native BenchmarkSpec: {data['res283_run']['benchmark_id']}",
            f"DatasetRealization: {data['res283_run']['dataset_realization_id']}",
            f"Evaluation: {data['res283_run']['evaluation_id']}",
            f"RES-283 analysis identity: {data['res283_run']['analysis_identity']}",
            f"RES-283 source commit: {data['res283_run']['source_commit']}",
            "",
            "The report uses saved EvaluationResult metrics and ranking diagnostics. It does not train models, generate datasets, regenerate predictions, execute new audit attacks, rescore predictions, or bootstrap uncertainty.",
            "",
            "## Version validity profiles",
            "",
            *profile_links,
            "",
            "The RES-277 profile snapshot remains distinct from the RES-278 and RES-281 execution outcomes. Figure 1 colors the original RES-277 state and labels a direct RES-281 axis state separately where available; audit coverage is process metadata, not established validity.",
            "",
            "![RES-277 baseline categorical validity states by benchmark version and axis](figures/figure-1-version-by-axis.svg)",
            "",
            "Figure 1. Color and the first cell label show the RES-277 profile state; a second label shows the direct RES-281 axis state where available. Attack states are shown in Figure 2. No values are combined into a validity score.",
            "",
            "### Audit execution and evidence states",
            "",
            "| Execution | Records | PASS | FAIL | INCONCLUSIVE | NOT_APPLICABLE | NOT_RUN | UNSUPPORTED_BY_EVIDENCE |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *status_lines,
            "",
            "![RES-278 and RES-281 attack states by version](figures/figure-2-attack-state-coverage.svg)",
            "",
            "Figure 2. Separate attack-by-version matrices for RES-278 and RES-281. Every cell retains its exact audit state. Full records, diagnostics, limitations, evidence references, and source identities are in tables/attack-evidence-states.csv.",
            "",
            "RES-281 public-native participant-key relabeling and target-canary tests each produced zero prediction mismatches and zero maximum absolute prediction delta across 96 audit rows and 18 registered fitted comparator states. The PASS scope is the repository inference adapter, not external participant models.",
            "",
            "## Reproducibility",
            "",
            "The RES-281 direct reproducibility receipt is PASS for the public-native IID realization: two complete generations produced byte-identical train and validation files, and both manifests matched the frozen manifest. This verifies that IID realization only; it does not reconstruct the historical scrambled-Sobol bytes. Historical versions retain their separate RES-277 reproducibility profile states and RES-278/281 provenance-review states in each profile.",
            "",
            "## Public-native IID model comparison",
            "",
            "The complete seven-family, 22-candidate target-wise table retains every exact saved RMSE, MAE, R², SRE(ddof=0), and rank value, with the original source-rights field by model family. Metric identities, units, and preferred directions are listed in tables/metric-definitions.csv: RMSE and MAE are kilograms; R² and SRE(ddof=0) are unitless; RMSE, MAE, and SRE minimize; R² maximizes.",
            "",
            *winner_lines,
            "",
            "| Metric | Figure |",
            "| --- | --- |",
            "| RMSE | ![Target-wise RMSE point estimates](figures/figure-3a-rmse.svg) |",
            "| MAE | ![Target-wise MAE point estimates](figures/figure-3b-mae.svg) |",
            "| R² | ![Target-wise R-squared point estimates](figures/figure-3c-r2.svg) |",
            "| SRE(ddof=0) | ![Target-wise normalized error point estimates](figures/figure-3d-sre.svg) |",
            "",
            "Figure 3a–d. Frozen target-wise point estimates, faceted by squat, bench press, and deadlift. The figures show no uncertainty intervals; exact source values and candidate identities are in tables/public-native-target-wise-rankings.csv.",
            "",
            "### Metric-dependent rankings",
            "",
            "RMSE-versus-MAE rankings reverse for 20 of 216 ordered candidate pairs on squat, 18/216 on bench press, and 19/216 on deadlift (15 ties per metric in each target panel). R² and SRE(ddof=0) share the RMSE ordering for each fixed target because they are monotone transforms of RMSE on that evaluation population.",
            "",
            "![Pairwise metric ranking reversals by target](figures/figure-4-metric-ranking-sensitivity.svg)",
            "",
            "Figure 4. Exact pairwise reversal counts from the saved metric sensitivity table. Reversals are descriptive and do not establish a universal best model.",
            "",
            "### Fit-seed diagnostics",
            "",
            "No pairwise ranking reversal was observed across the saved three-seed panel for any target/metric. The temporal-expert and compact-neural seeds are distinct fits; context mean, Ridge, boosted stumps, mechanistic midpoint, and mechanistic-plus-Ridge residual entries repeat deterministic predictions across seed labels. Dataset-seed, split-seed, and distribution-shift stability were not estimated. RES-281 model-ranking-instability remains INCONCLUSIVE.",
            "",
            "![Rank range by family, target, and metric across fit seeds](figures/figure-5-fit-seed-rank-stability.svg)",
            "",
            "Figure 5. Each cell gives the observed rank range across the saved fit-seed labels. A zero range in a deterministic-repeat family is not independent replication evidence.",
            "",
            "### Descriptive Pareto frontiers",
            "",
            "The exact point-estimate frontier has two squat candidates (expert seed 383003 and the expert ensemble), one bench-press candidate (ensemble), and one deadlift candidate (ensemble). R² and SRE add no independent ordering beyond RMSE for a fixed target. The frontier is descriptive; RES-281 baseline-domination remains INCONCLUSIVE without a practical margin or paired uncertainty method.",
            "",
            "![Descriptive RMSE and MAE Pareto comparison](figures/figure-6-pareto-summary.svg)",
            "",
            "Figure 6. Point estimates for the 22 candidate identities by target; outlined points lie on the exact descriptive frontier. No uncertainty is shown.",
            "",
            "### Named plan, history, and observation diagnostics",
            "",
            "RES-281 recorded 96 audit rows and 18 fitted comparator states for each of these interventions. The plan counterfactual, reversed-history, and three-replicate observation-noise outcomes remain INCONCLUSIVE. Their complete recorded scalar diagnostics are in tables/public-native-stress-diagnostics.csv; no real-athlete effect or broad robustness conclusion is drawn.",
            "",
            "## Historical cross-version sensitivity",
            "",
            "The RES-281 comparability decisions are binding: all 36 cross-version pairs remain REJECTED_FOR_NUMERICAL_COMPARISON. Eight historical versions lack rights-cleared public rows, matched fitted-model/prediction panels, and common-evaluation results. Their within-version rankings and cross-version ranking stability are therefore not identifiable. This missing evidence does not show either stability or instability.",
            "",
            "![Historical version-pair admissibility matrix](figures/figure-7-historical-admissibility.svg)",
            "",
            "Figure 7. All off-diagonal version pairs are rejected for numerical comparison; the diagonal is not a cross-version test.",
            "",
            "The genealogy table records design differences descriptively. Benchmark chronology does not establish validity improvement, and no design change is assigned a causal effect. Different designs could alter model rankings in principle, but no observed cross-version ranking effect is supported here. Scrambled-Sobol historical scores and public-native IID scores are not directly ranked, and no cross-version coefficient or improvement statistic is calculated.",
            "",
            "## Evidence-to-claim traceability",
            "",
            "Every published claim has a row in tables/evidence-to-claim.csv with its evidence class, exact source paths, and interpretation boundary. Output figure/table source hashes are recorded per artifact in checksum-index.json.",
            "",
            "## Rights and provenance",
            "",
            "The source prediction-rights field for public-native temporal expert remains NOASSERTION as recorded in the RES-283 evidence table. The publication includes aggregate EvaluationResult metadata and does not copy source prediction JSONL or checkpoint files. Private historical rows, checkpoints, and outputs remain outside this bundle. Repository presence alone is not treated as permission.",
            "",
            "RES-278 and RES-281 bundle manifests and record identities verify, and tracked record-level input hashes match. Both ledgers reference generated IID train/validation JSONLs under data/synthetic that are not tracked; their declared hashes are preserved as unavailable and no local copy was read or regenerated. The RES-281 bundle SHA-256 matches the handoff value. The RES-281 analysis source index and RES-283 output checksum index were verified.",
            "",
            "## Reproduction and companion tables",
            "",
            "Regenerate the publication from the repository root with: uv run --locked python -m powerlifting_state_research.audits.res284_publication",
            "Check deterministic report, table, and figure replay with: uv run --locked python -m powerlifting_state_research.audits.res284_publication --check",
            "",
            "| Artifact | Contents |",
            "| --- | --- |",
            "| tables/version-by-axis-evidence.csv | RES-277 baseline states plus RES-281 direct axis evidence |",
            "| tables/attack-evidence-states.csv | Both 126-record RES-278 and RES-281 attack ledgers, including exact identities and diagnostics |",
            "| tables/audit-input-artifact-status.csv | Tracked audit input hashes and generated inputs unavailable for byte recheck |",
            "| tables/attack-by-version-res281.csv | RES-281 attack-by-version state matrix |",
            "| tables/public-native-target-wise-rankings.csv | Exact target-wise metrics and ranks for all 22 candidates |",
            "| tables/metric-definitions.csv | Frozen metric identities, units, and directions |",
            "| tables/metric-ranking-sensitivity.csv | Reversal and tie counts by metric pair and target |",
            "| tables/fit-seed-rank-stability.csv and fit-seed-pairwise-reversals.csv | Per-seed ranks and reversal diagnostics |",
            "| tables/pareto-comparison-summary.csv | Exact point-estimate frontier membership |",
            "| tables/paired-uncertainty-evidence.csv | All unsupported uncertainty cells and their limits |",
            "| tables/historical-comparability.csv | All 36 rejected cross-version pairs |",
            "| tables/benchmark-genealogy.csv | Historical specimen identity and descriptive design changes |",
            "| tables/evidence-to-claim.csv | Claim/source/limitation traceability |",
            "| tables/scientific-limitations.csv | Evidence gaps and future evidence requirements |",
            "| tables/rights-provenance.csv | Model family rights constraints; NOASSERTION retained |",
            "| tables/public-native-stress-diagnostics.csv | Existing plan/history/noise diagnostic values only |",
            "",
            "## References",
            "",
            f"Frozen metric and ranking sources: {sources}.",
            "RES-277 axis and attack contracts: docs/audits/index.md and artifacts/registries/validity-axis-registry.json / attack-contract-registry.json.",
            "RES-281 report and evidence: results/audits/res281-analysis/res281-validity-analysis.md.",
            "RES-283 report and limitations: results/audits/res283-analysis/res283-model-ranking-stability.md and RES-284-handoff.md.",
            "",
        ]
    )


def _summary_markdown(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Executive summary",
            "",
            "RES-284 publishes a multidimensional validity synthesis and the admissible model-ranking evidence available for the Powerlifting State Research benchmark suite.",
            "",
            "## What the evidence supports",
            "",
            "- Nine version-specific profiles cover ten separate axes. Audit coverage is not an overall validity score.",
            "- One frozen public-native IID model panel is admissible: seven model families, 22 candidate fitted-instance/ensemble identities, three capacity-change targets, and 3,072 shared prediction keys.",
            "- The temporal-expert ensemble leads 11/12 target-metric point-estimate comparisons; temporal-expert seed 383003 leads squat MAE.",
            "- The RES-281 direct reproducibility receipt passes for the public-native IID realization: two full generations matched the frozen train/validation bytes and manifest. Historical scrambled-Sobol data are outside that reproduction claim.",
            "- Saved fit-seed ranks show no pairwise reversals in the three-seed panel. The stability finding remains inconclusive, and deterministic seed repeats are not independent fits.",
            "- Participant-key and target-canary tests pass for the registered comparator inference adapter. Named plan, history, and noise diagnostics remain inconclusive.",
            "",
            "## What remains unidentified",
            "",
            "- Paired uncertainty is unsupported because validation truth and row-to-entity mapping are absent; all 264 uncertainty cells remain unsupported and inferential status remains inconclusive.",
            "- All 36 historical cross-version comparisons remain rejected. Eight historical versions have no public matched fitted-model/evaluation panel, so historical model-ranking stability is not identifiable.",
            "- Frozen audit ledgers reference generated IID train/validation JSONLs that are not tracked. Their hashes remain recorded, but their bytes could not be independently rechecked without dataset generation.",
            "- Benchmark chronology does not establish validity improvement. The historical scrambled-Sobol and public-native IID scores are not directly ranked.",
            "- The temporal-expert source prediction-rights field remains NOASSERTION; this publication contains only aggregate evaluation metadata.",
            "",
            "No new training, data generation, attacks, rescoring, bootstrap, significance test, or practical superiority claim was used.",
            "",
            "Full report: report.md. Method and limitations: methods-limitations.md. Version profiles: profiles/.",
            "",
        ]
    )


def _methods_markdown() -> str:
    return "\n".join(
        [
            "# Methods and scientific limitations",
            "",
            "## Evidence qualification",
            "",
            "The starting checkout was clean and synchronized at main SHA 99a834721098d9953fd268dcdef5ce2177a490b0. The RES-278 and RES-281 bundle manifests were checked against every listed file, bundle digest, result-record pointer, result identity, and serialized-record digest. All tracked record-level input files match their declared hashes. Both ledgers also reference generated IID train/validation JSONLs that are not tracked; their declared hashes are retained as unavailable in tables/audit-input-artifact-status.csv, and no local ignored copy was read or regenerated. Each bundle contains 126 records over nine versions and fourteen attack contracts. The RES-281 bundle hash is 0bbe5d58be59c8ba76fae1a9d6e4a116629b5c88fbdbfb32def6c4b9872bb597.",
            "",
            "The RES-281 analysis manifest, source files, and output files were checksum-verified. RES-283 checksum-index and run-manifest hashes were verified, then its existing deterministic replay check was run. The audit runner read-only reconciliation and RES-283 deterministic replay both passed before publication. The publication index includes source hashes for every direct report, table, and figure dependency.",
            "",
            "## Frozen IID analysis",
            "",
            "Target-wise values and ranking order are carried from the RES-283 frozen CSV and existing EvaluationResult identities. The candidate unit is a fitted instance; expert seed instances and the separately identified ensemble are distinct candidates. The panel has seven model families, 22 candidate identities, three target QOIs, and 3,072 shared prediction keys under one IID DatasetRealization and one canonical RES-271 evaluation.",
            "",
            "RMSE and MAE are in kilograms; R² and SRE(ddof=0) are unitless. RMSE, MAE, and SRE(ddof=0) minimize; R² maximizes. Ranks are target- and metric-specific, with exact ties handled in the source analysis. No cross-target aggregate rank is created.",
            "",
            "Every chart is generated from a checksum-verified tracked table. Figures display point estimates, not uncertainty intervals. The target-wise table retains the source precision, fitted-instance/evaluation/prediction identities, ranks, and model-rights field. No target values or score values are entered by hand.",
            "",
            "## Audit interpretation",
            "",
            "RES-277 defines the six audit states: PASS, FAIL, INCONCLUSIVE, NOT_APPLICABLE, NOT_RUN, and UNSUPPORTED_BY_EVIDENCE. The RES-277 profile snapshot, RES-278 run, and RES-281 run are shown separately. Executed PASS/FAIL/INCONCLUSIVE states remain bounded to their named version, evidence, and protocol. NOT_RUN, NOT_APPLICABLE, and UNSUPPORTED_BY_EVIDENCE are not converted to negative or positive validity scores.",
            "",
            "The RES-281 paired key/canary results apply to the repository inference adapter and registered comparator states. Plan swap, reversed history, and observation-noise diagnostics are limited to named synthetic interventions; their states remain INCONCLUSIVE. Their diagnostics do not establish broad distribution-shift robustness or real-athlete validity.",
            "",
            "## Ranking and uncertainty limits",
            "",
            "The 11/12 expert-ensemble lead count, metric reversals, seed ranks, and Pareto frontier describe frozen point estimates. They do not imply statistical significance or practical superiority. R² and SRE(ddof=0) are monotone transforms of RMSE on a fixed target evaluation population, so they do not add independent candidate ordering.",
            "",
            "No observed pairwise ranking reversal occurs across the saved three-seed fit panel. The panel has only three distinct fits for temporal-expert and compact-neural; other families repeat deterministic outputs under seed labels. Dataset-seed, split-seed, distribution-shift, and out-of-sample ranking variability are not estimated. RES-281 model-ranking-instability and baseline-domination remain INCONCLUSIVE.",
            "",
            "Tracked public inputs do not include validation target truth rows or the row-to-entity mapping. The planned 2,000-resample entity bootstrap was not run. All 264 candidate/target/metric uncertainty cells remain UNSUPPORTED_BY_EVIDENCE and inference INCONCLUSIVE.",
            "",
            "## Historical comparison boundary",
            "",
            "All 36 cross-version numerical comparisons remain REJECTED_FOR_NUMERICAL_COMPARISON. Eight historical versions lack public matched fitted-model/evaluation panels and common-evaluation paired evidence. Their within-version rankings and cross-version rank stability cannot be identified. Missing evidence does not demonstrate either a ranking change or stable rankings.",
            "",
            "Design genealogy is descriptive. Chronology is not evidence of validity improvement, and this synthesis assigns no causal effect to a design change. The historical scrambled-Sobol and public-native IID DatasetSpecs differ; their raw scores are not directly ranked. Different benchmark designs could change model rankings in principle, but this report does not claim an observed cross-version effect.",
            "",
            "## Rights and provenance",
            "",
            "The repository public-file origin ledger and frozen result-manifest rights metadata were reviewed. The public-native temporal-expert source prediction-rights field remains NOASSERTION in the RES-283 model evidence. This publication retains that exact field and includes aggregate evaluation metadata only; source prediction JSONL and checkpoint bytes are not copied. Historical private rows, checkpoints, and outputs remain excluded. Repository presence is not treated as blanket redistribution permission.",
            "",
            "## Future evidence requirements",
            "",
            "The companion scientific-limitations table names the missing evidence needed for each stronger claim: validation truth and entity mapping for paired uncertainty; independent fit/data/split seeds and predeclared margins for broader stability; rights-cleared historical rows, adapters, common support, and the same fitted panel for historical comparisons; supported preregistered shift protocols for broader robustness; and a separate empirical validation design for real-athlete claims.",
            "",
            "## Reproduction",
            "",
            "Regenerate and verify this bundle with uv run --locked python -m powerlifting_state_research.audits.res284_publication and uv run --locked python -m powerlifting_state_research.audits.res284_publication --check. These commands only validate saved artifacts and create publication files.",
            "",
        ]
    )


def build_publication_artifacts(root: Path = ROOT) -> dict[str, bytes]:
    data = _analysis_data(root)
    source_paths = data["source_paths"]
    source_hashes = {path: _sha256(root / path) for path in source_paths}
    output: dict[str, bytes] = {}
    output_sources: dict[str, list[str]] = {}

    def add(path: str, content: bytes, sources: list[str]) -> None:
        if path in output:
            raise ValueError(f"duplicate publication output: {path}")
        if any(source not in source_hashes for source in sources):
            raise ValueError(f"unverified source listed for {path}")
        output[path] = content
        output_sources[path] = sources

    direct_tables = {
        "version-by-axis-evidence.csv": "results/audits/res281-analysis/version-by-axis-evidence.csv",
        "attack-by-version-res281.csv": "results/audits/res281-analysis/attack-by-version.csv",
        "metric-ranking-sensitivity.csv": "results/audits/res283-analysis/metric-dependent-ranking-summary.csv",
        "pairwise-ranking-reversals.csv": "results/audits/res283-analysis/pairwise-ranking-reversals.csv",
        "fit-seed-rank-stability.csv": "results/audits/res283-analysis/fit-seed-rank-stability.csv",
        "fit-seed-pairwise-reversals.csv": "results/audits/res283-analysis/fit-seed-pairwise-reversals.csv",
        "pareto-comparison-summary.csv": "results/audits/res283-analysis/pareto-comparison-summary.csv",
        "paired-uncertainty-evidence.csv": "results/audits/res283-analysis/paired-uncertainty-evidence.csv",
        "historical-comparability.csv": "results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        "benchmark-genealogy.csv": "results/audits/res281-analysis/design-change-evidence.csv",
    }
    for filename, source in direct_tables.items():
        path = f"{OUTPUT_DIR.as_posix()}/tables/{filename}"
        add(path, (root / source).read_bytes(), [source])

    metric_definition_rows = data["metric_definitions"]
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/metric-definitions.csv",
        _csv_bytes(metric_definition_rows, list(metric_definition_rows[0])),
        ["results/audits/res283-analysis/run-manifest.json"],
    )

    audit_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for execution, records in data["records_by_execution"].items():
        source = f"results/audits/{execution.lower()}/audit-results.json"
        for record in records:
            audit_rows.append(
                {
                    "execution": execution,
                    "benchmark_version": record["benchmark_version"],
                    "attack_spec_ref": record["attack_spec_ref"],
                    "axis_slug": record["axis_slug"],
                    "status": record["status"],
                    "run_id": record.get("run_id") or "",
                    "result_artifact_identity": record["result_artifact_identity"],
                    "result_artifact_sha256": record["result_artifact_sha256"],
                    "source_commit": record.get("source_commit") or "",
                    "status_reason": record.get("status_reason") or "",
                    "diagnostics_json": json.dumps(
                        record.get("diagnostics", {}),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "evidence_refs_json": json.dumps(
                        record.get("evidence_refs", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "missing_evidence_json": json.dumps(
                        record.get("missing_evidence", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "limitations_json": json.dumps(
                        record.get("limitations", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "input_artifacts_json": json.dumps(
                        record.get("input_artifacts", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "source_artifact": source,
                }
            )
            if record["attack_spec_ref"] in STRESS_ATTACKS:
                for key, value in sorted(record.get("diagnostics", {}).items()):
                    if isinstance(value, (int, float, str, bool)):
                        diagnostics.append(
                            {
                                "execution": execution,
                                "benchmark_version": record["benchmark_version"],
                                "attack_spec_ref": record["attack_spec_ref"],
                                "status": record["status"],
                                "run_id": record.get("run_id") or "",
                                "diagnostic": key,
                                "value": value,
                                "source_result_identity": record["result_artifact_identity"],
                            }
                        )
    audit_fields = list(audit_rows[0])
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/attack-evidence-states.csv",
        _csv_bytes(audit_rows, audit_fields),
        ["results/audits/res278/audit-results.json", "results/audits/res281/audit-results.json"],
    )
    input_status_rows = data["audit_input_status"]
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/audit-input-artifact-status.csv",
        _csv_bytes(input_status_rows, list(input_status_rows[0])),
        ["results/audits/res278/audit-results.json", "results/audits/res281/audit-results.json"],
    )
    diagnostic_fields = list(diagnostics[0])
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/public-native-stress-diagnostics.csv",
        _csv_bytes(diagnostics, diagnostic_fields),
        ["results/audits/res278/audit-results.json", "results/audits/res281/audit-results.json"],
    )

    target_rows = data["target_rows"]
    model_rights = data["model_rights"]
    target_fields = list(target_rows[0]) + ["rights_access_constraints"]
    enriched_targets = [
        {**row, "rights_access_constraints": model_rights[row["model_family"]]}
        for row in target_rows
    ]
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/public-native-target-wise-rankings.csv",
        _csv_bytes(enriched_targets, target_fields),
        [
            "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
            "results/audits/res283-analysis/version-by-model-evidence.csv",
        ],
    )
    rights_rows = [
        {
            "model_family": family,
            "rights_access_constraints": constraints,
            "source_prediction_files_copied": "NO",
            "source_checkpoint_files_copied": "NO",
        }
        for family, constraints in sorted(model_rights.items())
    ]
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/rights-provenance.csv",
        _csv_bytes(rights_rows, list(rights_rows[0])),
        [
            "results/audits/res283-analysis/version-by-model-evidence.csv",
            "provenance/PUBLIC_FILE_ORIGINS.csv",
        ],
    )

    registry_by_version = data["benchmark_by_version"]
    profiles = data["base_profiles"]
    axes = data["axes"]
    version_axis = {
        f"{row['benchmark_version']}::{row['axis_slug']}": row for row in data["version_axis"]
    }
    profile_sources = [
        "artifacts/registries/benchmark-registry.json",
        "artifacts/registries/version-validity-profiles.json",
        "artifacts/registries/validity-axis-registry.json",
        "results/audits/res281-analysis/version-by-axis-evidence.csv",
        "results/audits/res281-analysis/design-change-evidence.csv",
        "results/audits/res278/audit-results.json",
        "results/audits/res281/audit-results.json",
        "results/audits/res281/reproducibility-execution.json",
        "results/audits/res283-analysis/version-by-model-evidence.csv",
        "tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py",
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
    ]
    for profile in profiles:
        version = _profile_name(profile)
        benchmark = registry_by_version[version]
        axis_rows = {axis: version_axis[f"{version}::{axis}"] for axis in axes}
        profile_path = f"{OUTPUT_DIR.as_posix()}/profiles/{profile['benchmark_slug']}.md"
        add(
            profile_path,
            _profile_markdown(
                version,
                profile,
                benchmark,
                axis_rows,
                data["records_by_execution"],
                axes,
                data["model_evidence"],
                data["reproducibility_execution"],
                root,
            ).encode("utf-8"),
            profile_sources,
        )

    evidence_rows = _evidence_claims()
    evidence_fields = list(evidence_rows[0])
    for row in evidence_rows:
        for source in row["source_artifacts"].split(";"):
            if source not in source_hashes:
                raise ValueError(
                    f"traceability row {row['claim_id']} has an unverified source: {source}"
                )
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/evidence-to-claim.csv",
        _csv_bytes(evidence_rows, evidence_fields),
        sorted({source for row in evidence_rows for source in row["source_artifacts"].split(";")}),
    )
    limitation_rows = _limitations()
    for row in limitation_rows:
        for source in row["source_artifacts"].split(";"):
            if source not in source_hashes:
                raise ValueError(f"limitation table has an unverified source: {source}")
    add(
        f"{OUTPUT_DIR.as_posix()}/tables/scientific-limitations.csv",
        _csv_bytes(limitation_rows, list(limitation_rows[0])),
        sorted(
            {source for row in limitation_rows for source in row["source_artifacts"].split(";")}
        ),
    )

    direct_axis_source = "artifacts/registries/version-validity-profiles.json"
    attack_sources = [
        "results/audits/res278/audit-results.json",
        "results/audits/res281/audit-results.json",
    ]
    target_source = "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv"
    figures = {
        "figure-1-version-by-axis.svg": (
            _profile_figure(profiles, axes, version_axis),
            [direct_axis_source, "results/audits/res281-analysis/version-by-axis-evidence.csv"],
        ),
        "figure-2-attack-state-coverage.svg": (
            _attack_figure(data["records_by_execution"], data["versions"]),
            attack_sources,
        ),
        "figure-3a-rmse.svg": (_model_metric_figure(enriched_targets, "RMSE"), [target_source]),
        "figure-3b-mae.svg": (_model_metric_figure(enriched_targets, "MAE"), [target_source]),
        "figure-3c-r2.svg": (_model_metric_figure(enriched_targets, "R²"), [target_source]),
        "figure-3d-sre.svg": (
            _model_metric_figure(enriched_targets, "SRE(ddof=0)"),
            [target_source],
        ),
        "figure-4-metric-ranking-sensitivity.svg": (
            _metric_sensitivity_figure(data["metric_rows"]),
            ["results/audits/res283-analysis/metric-dependent-ranking-summary.csv"],
        ),
        "figure-5-fit-seed-rank-stability.svg": (
            _seed_figure(data["seed_rows"]),
            ["results/audits/res283-analysis/fit-seed-rank-stability.csv"],
        ),
        "figure-6-pareto-summary.svg": (
            _pareto_figure(data["pareto_rows"]),
            ["results/audits/res283-analysis/pareto-comparison-summary.csv"],
        ),
        "figure-7-historical-admissibility.svg": (
            _historical_figure(
                data["versions"],
                data["historical_rows"],
                {
                    version: data["benchmark_by_version"][version]["display_name"]
                    for version in data["versions"]
                },
            ),
            ["results/audits/res283-analysis/cross-version-ranking-admissibility.csv"],
        ),
    }
    for filename, (content, sources) in figures.items():
        add(f"{OUTPUT_DIR.as_posix()}/figures/{filename}", content, sources)

    for row in enriched_targets:
        if (
            row["model_family"] == "public-native-temporal-expert"
            and "NOASSERTION" not in row["rights_access_constraints"]
        ):
            raise ValueError("target-wise table overwrote temporal-expert NOASSERTION rights")
    report = _report_markdown(data)
    add(
        f"{OUTPUT_DIR.as_posix()}/report.md",
        report.encode("utf-8"),
        [
            "docs/audits/index.md",
            "results/audits/res283-analysis/RES-284-handoff.md",
            "results/audits/res283-analysis/run-manifest.json",
            "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
            "results/audits/res281-analysis/version-by-axis-evidence.csv",
        ],
    )
    add(
        f"{OUTPUT_DIR.as_posix()}/executive-summary.md",
        _summary_markdown(data).encode("utf-8"),
        [
            "results/audits/res283-analysis/run-manifest.json",
            "results/audits/res283-analysis/frozen-iid-target-wise-rankings.csv",
            "results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
            "results/audits/res283-analysis/paired-uncertainty-evidence.csv",
        ],
    )
    add(
        f"{OUTPUT_DIR.as_posix()}/methods-limitations.md",
        _methods_markdown().encode("utf-8"),
        [
            "docs/audits/index.md",
            "results/audits/res283-analysis/RES-284-handoff.md",
            "results/audits/res283-analysis/run-manifest.json",
            "results/audits/res283-analysis/checksum-index.json",
            "results/audits/res283-analysis/paired-uncertainty-evidence.csv",
            "results/audits/res283-analysis/cross-version-ranking-admissibility.csv",
        ],
    )
    add(
        f"{OUTPUT_DIR.as_posix()}/README.md",
        (
            b"# RES-284 publication bundle\n\n"
            b"Start with report.md and executive-summary.md. Nine version profiles are under profiles/. "
            b"Exact data tables and rights fields are under tables/; publication figures are under figures/. "
            b"Every output is linked to verified source hashes in checksum-index.json.\n\n"
            b"Regenerate with uv run --locked python -m powerlifting_state_research.audits.res284_publication. "
            b"Verify deterministic replay with uv run --locked python -m powerlifting_state_research.audits.res284_publication --check.\n"
        ),
        ["docs/audits/index.md", "results/audits/res283-analysis/RES-284-handoff.md"],
    )

    output_file_records = []
    for path, content in sorted(output.items()):
        mime = (
            "image/svg+xml"
            if path.endswith(".svg")
            else "text/csv"
            if path.endswith(".csv")
            else "text/markdown"
            if path.endswith(".md")
            else "application/json"
        )
        license_expression = "CC-BY-4.0" if path.endswith(".md") else "MIT"
        output_file_records.append(
            {
                "path": path,
                "sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                "media_type": mime,
                "rights": {
                    "copyright_holder": "Powerlifting State Research contributors",
                    "license_expression": license_expression,
                    "redistribution_status": "RES-284 publication artifact under the repository license; temporal-expert source prediction rights remain NOASSERTION.",
                },
                "sources": [
                    {"path": source, "sha256": source_hashes[source]}
                    for source in sorted(output_sources[path])
                ],
            }
        )
    identity_material = {
        "source_identities": {
            "res278_bundle": data["res278_manifest"]["bundle_identity"],
            "res281_bundle": data["res281_manifest"]["bundle_identity"],
            "res281_analysis": data["res281_analysis"]["analysis_identity"],
            "res283_analysis": data["res283_run"]["analysis_identity"],
            "benchmark_id": data["res283_run"]["benchmark_id"],
            "dataset_realization_id": data["res283_run"]["dataset_realization_id"],
            "evaluation_id": data["res283_run"]["evaluation_id"],
        },
        "source_files": [{"path": path, "sha256": source_hashes[path]} for path in source_paths],
        "files": output_file_records,
    }
    identity = "sha256:" + hashlib.sha256(_json_bytes(identity_material)).hexdigest()
    checksum_index = {
        "format": "PSR_RES284_PUBLICATION_INDEX_V1",
        "algorithm": "SHA-256",
        "publication_fingerprint": identity,
        **identity_material,
        "rights_note": "Aggregate evaluation metadata only; temporal-expert source prediction rights remain NOASSERTION; source predictions and checkpoints are not copied.",
    }
    output[f"{OUTPUT_DIR.as_posix()}/checksum-index.json"] = _json_bytes(checksum_index)
    return output


def write_publication(artifacts: dict[str, bytes], root: Path = ROOT) -> None:
    for relative, content in sorted(artifacts.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def check_publication(root: Path = ROOT) -> None:
    expected = build_publication_artifacts(root)
    directory = root / OUTPUT_DIR
    actual_paths = {
        path.relative_to(root).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    if actual_paths != set(expected):
        missing = sorted(set(expected) - actual_paths)
        extra = sorted(actual_paths - set(expected))
        raise ValueError(f"publication file set differs; missing={missing}; extra={extra}")
    for relative, content in expected.items():
        if (root / relative).read_bytes() != content:
            raise ValueError(f"publication replay differs at {relative}")
    index = json.loads(expected[f"{OUTPUT_DIR.as_posix()}/checksum-index.json"])
    sources = {item["path"] for item in index["source_files"]}
    for entry in index["files"]:
        if any(source["path"] not in sources for source in entry["sources"]):
            raise ValueError(f"output source hash missing from publication index: {entry['path']}")
    if any(row["evidence_state"] == "INFERENTIAL" for row in _evidence_claims()):
        raise ValueError("unsupported inferential claim class in traceability register")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--check", action="store_true", help="verify deterministic report replay")
    args = parser.parse_args(argv)
    if args.check:
        check_publication(args.root)
        print("RES-284 deterministic publication replay and provenance checks: PASS")
    else:
        artifacts = build_publication_artifacts(args.root)
        write_publication(artifacts, args.root)
        print(f"RES-284 publication written to {(args.root / OUTPUT_DIR).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
