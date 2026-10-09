import json
from dataclasses import replace
from pathlib import Path

import pytest

from powerlifting_state_research.artifacts.hashes import sha256_file_content
from powerlifting_state_research.artifacts.manifests import RightsMetadata
from powerlifting_state_research.audits.runner import (
    _ATTACKS,
    _BENCHMARKS,
    AuditExecutionRecord,
    EvidenceArtifactReference,
    _nonexecuted_record,
    _record,
    _safe_output,
    evidence_artifact,
    read_audit_execution_record,
)
from powerlifting_state_research.audits.specifications import AuditStatus
from powerlifting_state_research.contracts.serialization import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[2]
NATIVE = "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0"
HISTORICAL = "class_normalized_cross_lift_five_target_performance_forecasting@1.0.0"
RIGHTS = RightsMetadata("MIT", "Test", "Test-only public evidence.")
SOURCE = EvidenceArtifactReference(
    "artifacts/test-evidence.json", "sha256:" + "a" * 64, "application/json", RIGHTS
)


def _executed(**changes: object) -> AuditExecutionRecord:
    values: dict[str, object] = {
        "benchmark_version": NATIVE,
        "attack_slug": "participant_input_leakage",
        "status": AuditStatus.INCONCLUSIVE,
        "reason": "A deterministic paired run completed without a predeclared practical margin.",
        "input_artifacts": (SOURCE,),
        "diagnostics": {"paired_prediction_delta": 0.0},
        "source_commit": "a" * 40,
        "seed": 281_101,
        "intervention": _ATTACKS["participant_input_leakage@1.0.0"].permitted_interventions[0],
        "decision_criteria": (
            "The paired diagnostic was executed; no decision margin was declared.",
        ),
        "limitations": ("Test-only record.",),
    }
    values.update(changes)
    return _record(**values)  # type: ignore[arg-type]


def test_wrong_benchmark_identity_is_rejected() -> None:
    record = _executed()
    with pytest.raises(ValueError, match="conflicting scientific identities"):
        replace(record, benchmark_id="wrong-benchmark-id")


def test_cross_version_dataset_realization_is_rejected() -> None:
    record = _executed()
    foreign_digest = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="registered IID DatasetRealization"):
        replace(
            record,
            dataset_realization_id=f"psr:dataset-realization:other-version@{foreign_digest}",
            dataset_realization_digest=foreign_digest,
        )


def test_mismatched_artifact_hash_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "source.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        evidence_artifact(
            tmp_path,
            "source.json",
            expected_sha256="0" * 64,
            rights=RIGHTS,
        )


def test_unknown_attack_specification_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown attack specification"):
        replace(_executed(), attack_spec_ref="unknown_attack@1.0.0")


def test_attack_cannot_execute_outside_its_declared_version_scope() -> None:
    record = _executed()
    historical = _BENCHMARKS[HISTORICAL]
    with pytest.raises(ValueError, match="inapplicable to this version"):
        replace(
            record,
            attack_spec_ref="baseline_domination@1.0.0",
            benchmark_version=HISTORICAL,
            axis_slug="simple_model_frontier",
            benchmark_id=historical.benchmark_id,
            semantic_digest=historical.semantic_digest,
        )


def test_inapplicable_intervention_is_rejected() -> None:
    with pytest.raises(ValueError, match="executed audit results need"):
        _executed(intervention="Replace predictions with arbitrary values.")


def test_historical_missing_evidence_stays_unsupported() -> None:
    record = _nonexecuted_record(
        ROOT,
        HISTORICAL,
        "participant_input_leakage",
        AuditStatus.UNSUPPORTED_BY_EVIDENCE,
        "Historical participant rows and executable fitted artifacts are not public.",
        (
            _BENCHMARKS[HISTORICAL].docs_path,
            "artifacts/registries/benchmark-registry.json",
            "src/powerlifting_state_research/provenance/historical_sources.py",
        ),
        ("Rights-cleared historical participant rows and split identities.",),
    )
    assert record.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE
    assert record.missing_evidence == (
        "Rights-cleared historical participant rows and split identities.",
    )
    assert record.run_id is None and record.source_commit is None and not record.diagnostics


def test_historical_attack_cannot_transition_to_executed_without_adapter() -> None:
    with pytest.raises(ValueError, match="version-specific rights-cleared adapter"):
        _record(
            benchmark_version=HISTORICAL,
            attack_slug="participant_input_leakage",
            status=AuditStatus.PASS,
            reason="Invalid attempted historical pass.",
            input_artifacts=(SOURCE,),
            diagnostics={"prediction_delta": 0.0},
            source_commit="a" * 40,
            seed=1,
            intervention=_ATTACKS["participant_input_leakage@1.0.0"].permitted_interventions[0],
            decision_criteria=("The claim passed.",),
        )


def test_schema_validation_alone_cannot_support_pass() -> None:
    with pytest.raises(ValueError, match="schema validation alone"):
        _executed(
            status=AuditStatus.PASS,
            reason="Invalid schema-only pass.",
            diagnostics={"schema_valid": 1},
            decision_criteria=("Schema validation passed.",),
        )


def test_audit_output_cannot_target_frozen_m4_artifacts() -> None:
    frozen = ROOT / "results/manifests/public-native-comparator-suite.json"
    before = sha256_file_content(frozen)
    with pytest.raises(ValueError, match="restricted to results/audits"):
        _safe_output(ROOT, Path("results/benchmarks/res278-test-output"))
    assert sha256_file_content(frozen) == before


def test_execution_serialization_round_trips_with_stable_hashes() -> None:
    record = _executed()
    replay = _executed()
    assert record.run_id is not None and record.run_id.startswith("res281-")
    assert record.audit_realization_id == replay.audit_realization_id
    assert canonical_json_bytes(replay) == canonical_json_bytes(record)
    content = canonical_json_bytes(record)
    replayed = read_audit_execution_record(json.loads(content))
    assert replayed == record
    assert canonical_json_bytes(replayed) == content
    assert replayed.result_artifact_identity == record.result_artifact_identity
    assert replayed.result_artifact_sha256 == record.result_artifact_sha256


def test_res278_audit_bundle_is_unchanged() -> None:
    manifest = json.loads(
        (ROOT / "results/audits/res278/audit-results.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["bundle_identity"] == (
        "psr:audit-bundle@sha256:0507c294ad33c5d0382fced64ef888a03d9e72c0f4065be3f084edf347d9531a"
    )
    for item in manifest["files"]:
        assert sha256_file_content(ROOT / item["path"]) == item["sha256"]
