import csv
import hashlib
import json
from pathlib import Path

from powerlifting_state_research.audits.analysis import build_analysis_documents
from powerlifting_state_research.audits.specifications import AuditStatus

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path("results/audits/res281")
ANALYSIS = ROOT / "results/audits/res281-analysis"


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_res281_tables_replay_deterministically_and_preserve_all_states() -> None:
    generated = build_analysis_documents(ROOT, BUNDLE)
    assert generated == build_analysis_documents(ROOT, BUNDLE)
    for name, content in generated.items():
        assert (ANALYSIS / name).read_bytes() == content

    attack_rows = _csv(ANALYSIS / "attack-by-version.csv")
    assert len(attack_rows) == 14
    versions = [name for name in attack_rows[0] if name not in {"axis_slug", "attack_spec_ref"}]
    assert len(versions) == 9
    assert all(
        row[version] in {state.value for state in AuditStatus}
        for row in attack_rows
        for version in versions
    )

    axis_rows = _csv(ANALYSIS / "version-by-axis-evidence.csv")
    assert len(axis_rows) == 90
    native = next(
        row
        for row in axis_rows
        if row["benchmark_version"].startswith("iid_") and row["axis_slug"] == "reproducibility"
    )
    assert json.loads(native["res281_direct_axis_states"]) == {"reproducibility": "PASS"}
    historical_provenance = [
        row
        for row in axis_rows
        if row["axis_slug"] == "reconstructability"
        and not row["benchmark_version"].startswith("iid_")
    ]
    assert len(historical_provenance) == 8
    assert all(
        json.loads(row["res281_attack_states_by_contract"])["reconstruction_provenance_gaps@1.0.0"]
        == "INCONCLUSIVE"
        for row in historical_provenance
    )

    comparisons = _csv(ANALYSIS / "cross-version-comparability.csv")
    assert len(comparisons) == 36
    assert {row["numerical_comparison_decision"] for row in comparisons} == {
        "REJECTED_FOR_NUMERICAL_COMPARISON"
    }
    capacity_pair = next(
        row
        for row in comparisons
        if {row["left_benchmark_version"], row["right_benchmark_version"]}
        == {
            "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0",
            "latent_capacity_change_with_transient_expression_forecasting@1.0.0",
        }
    )
    checks = json.loads(capacity_pair["declared_semantic_checks"])
    assert checks["task_match"] and checks["qoi_match"]
    assert not checks["dataset_spec_match"] and not checks["evaluation_match"]


def test_res281_artifact_indexes_bind_outputs_rights_and_execution_records() -> None:
    run_index = json.loads((ROOT / BUNDLE / "audit-results.manifest.json").read_bytes())
    run_records = json.loads((ROOT / BUNDLE / "audit-results.json").read_bytes())["records"]
    assert len(run_records) == 126
    assert all(record["result_rights"]["license_expression"] == "MIT" for record in run_records)
    executed = [record for record in run_records if record["run_id"] is not None]
    assert executed and all(record["run_id"].startswith("res281-") for record in executed)
    for entry in run_index["files"]:
        digest = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        assert entry["sha256"] == f"sha256:{digest}"

    analysis_index = json.loads((ANALYSIS / "analysis-results.manifest.json").read_bytes())
    for entry in analysis_index["files"]:
        digest = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        assert entry["sha256"] == f"sha256:{digest}"
        assert entry["rights"]["license_expression"] == "MIT"
    for source in analysis_index["source_files"]:
        digest = hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()
        assert source["sha256"] == f"sha256:{digest}"

    coverage = json.loads((ANALYSIS / "m5-coverage-summary.json").read_bytes())
    assert coverage["recorded_attack_state_count"] == 126
    assert coverage["all_version_attack_states_accounted"] is True
    assert set(coverage["state_counts"]) == {status.value for status in AuditStatus}
    assert coverage["scalar_validity_score"] is None
