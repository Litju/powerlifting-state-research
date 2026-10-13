from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from powerlifting_state_research.studies.public_surrogate_reconstruction import (
    _artifact_manifest_bytes,
    _authority_payload_audit,
    _claims_rows,
    _coverage_diagnostics,
    _generate_split,
    _history_coverage_rows,
    _run_learner,
    verify_design,
)

ROOT = Path(__file__).resolve().parents[2]


def _small_study_inputs() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    fitting, _, _ = _generate_split(
        {"population": 295101, "intervention": 295102, "observation": 295103, "split": 295104},
        "fitting",
        "train",
        24,
    )
    development, _, _ = _generate_split(
        {"population": 295111, "intervention": 295112, "observation": 295113, "split": 295114},
        "development",
        "validation",
        12,
    )
    test, _, _ = _generate_split(
        {"population": 295121, "intervention": 295122, "observation": 295123, "split": 295124},
        "test-a-test",
        "validation",
        12,
    )
    return (
        fitting,
        development,
        {
            "test_a": test,
            "test_b": [],
            "test_a_noise_replicate": [],
            "matched": [],
        },
    )


def test_frozen_protocol_and_public_lineage_hashes_verify() -> None:
    protocol = verify_design(ROOT)
    assert protocol["starting_main"] == "31ad65bdd4e19ef80243fbdbf507097d70f1776b"
    assert protocol["identities"]["study_id"].startswith(
        "psr:study:public-surrogate-reconstruction-public-native@"
    )
    historical = (
        ROOT / "studies/public_surrogate_reconstruction/historical-lineage.md"
    ).read_text()
    assert "UNSUPPORTED_BY_EVIDENCE" in historical
    assert "No historical G3 score is compared" in historical


def test_frozen_protocol_verifies_in_a_depth_one_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    import powerlifting_state_research.studies.public_surrogate_reconstruction as study

    def no_history(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=128)

    monkeypatch.setattr(study.subprocess, "run", no_history)
    assert verify_design(ROOT)["identities"]["protocol_digest"].startswith("sha256:")


def test_subprocess_boundary_disjointness_units_and_resampler_replay() -> None:
    fitting, development, datasets = _small_study_inputs()
    first, payload, first_stdout = _run_learner(ROOT, fitting, development, datasets, 295180)
    second, second_payload, second_stdout = _run_learner(
        ROOT, fitting, development, datasets, 295180
    )
    assert payload == second_payload
    assert first_stdout == second_stdout
    assert first["predictions"] == second["predictions"]
    assert first["method_failures"] == []
    assert {row["method"] for row in first["predictions"]} == {
        "empirical_finite_support_resampler_v1",
        "summary_ridge_v1",
        "sequence_rff_ridge_v1",
    }

    request = json.loads(payload)
    queries = [item["row"] for item in request["queries"]]
    assert all("targets" not in row for row in queries)
    fit_ids = {row["row_id"] for row in fitting}
    dev_ids = {row["row_id"] for row in development}
    test_ids = {row["row_id"] for row in datasets["test_a"]}
    assert not fit_ids & dev_ids
    assert not fit_ids & test_ids
    assert not dev_ids & test_ids

    source = (
        ROOT / "src/powerlifting_state_research/studies/public_surrogate_reconstruction_learner.py"
    ).read_bytes()
    audit = _authority_payload_audit(source, payload, datasets)
    assert audit["passed"]
    assert audit["evaluation_target_fields_in_payload"] == 0
    assert "numpy" in audit["allowed_imports"]
    assert "benchmarks" not in audit["allowed_imports"]

    fitting_by_id = {row["row_id"]: row for row in fitting}
    samples = first["empirical_sample"]
    assert len(samples) == len(fitting)
    assert all(row["donor_row_id"] in fitting_by_id for row in samples)
    for row in samples:
        donor = json.loads(json.dumps(fitting_by_id[row["donor_row_id"]]["inputs"]))
        sampled = dict(row["inputs"])
        sampled.pop("entity_id")
        expected = dict(donor)
        expected.pop("entity_id")
        assert sampled == expected


def test_visible_schema_and_sample_support_diagnostics_reject_invalid_fields() -> None:
    fitting, development, datasets = _small_study_inputs()
    query = copy.deepcopy(datasets["test_a"][0])
    request = {
        "protocol_id": "test",
        "fitting_rows": fitting,
        "development_rows": development,
        "queries": [{"evaluation_set": "test_a", "row": query}],
        "seeds": {"empirical_resampling": 1},
    }
    source = (
        ROOT / "src/powerlifting_state_research/studies/public_surrogate_reconstruction_learner.py"
    ).read_bytes()
    audit = _authority_payload_audit(source, json.dumps(request).encode(), {"test_a": [query]})
    assert audit["passed"]
    bad = copy.deepcopy(query)
    bad["inputs"]["declared_future_plan"]["dose"] = 1.8
    bad_datasets = {**datasets, "test_a": [bad, *datasets["test_a"][1:]]}
    with pytest.raises(RuntimeError, match="future plan fields"):
        _run_learner(ROOT, fitting, development, bad_datasets, 295180)

    coverage = _history_coverage_rows({"development": datasets["test_a"]}, fitting)
    assert len(coverage) == 12
    assert all(
        0 <= row["evaluation_combination_fraction_seen_in_training"] <= 1 for row in coverage
    )
    geometry, summary = _coverage_diagnostics(fitting, {"test_a": datasets["test_a"]})
    assert geometry[0]["evaluation_set"] == "test_a"
    assert summary["test_a"]["n_rows"] == 12.0
    assert summary["test_a"]["nearest_training_distance_median"] >= 0.0


def test_missing_historical_evidence_and_method_failure_states_are_explicit() -> None:
    metrics = b"""population,lift,horizon_days,method,rmse_kg,status
test_a,squat,14,empirical_finite_support_resampler_v1,2.0,COMPLETE
test_a,squat,14,summary_ridge_v1,1.8,COMPLETE
test_a,squat,14,sequence_rff_ridge_v1,,MODEL_FIT_FAILED
"""
    contrasts = b"""population,lift,horizon_days,contrast,status
test_a,squat,14,sequence_rff_minus_summary,MODEL_FIT_FAILED
"""
    matched = b"""method,lift,horizon_days,plan_contrast,status
"""
    result = _claims_rows(
        metrics,
        contrasts,
        [],
        matched,
        0,
        {"passed": True},
        [{"family": "sequence_rff_ridge_v1", "status": "MODEL_FIT_FAILED"}],
    )
    rows = list(csv.DictReader(io.StringIO(result.decode())))
    by_claim = {row["claim"]: row["status"] for row in rows}
    assert by_claim["Original historical G3 experiment was reproduced"] == "UNSUPPORTED_BY_EVIDENCE"
    assert (
        by_claim["A frozen surrogate family failed its declared fitting budget"]
        == "MODEL_FIT_FAILED"
    )


def test_artifact_rights_manifest_records_redistribution_scope() -> None:
    protocol = verify_design(ROOT)
    artifact_manifest = json.loads(
        _artifact_manifest_bytes(
            {"realizations/test-visible.jsonl": b"{}\n", "report.md": b"# report\n"},
            protocol,
            {"realization_id": "psr:dataset-realization:test@sha256:" + "a" * 64},
        )
    )
    artifacts = {row["path"]: row for row in artifact_manifest["artifacts"]}
    assert artifacts["realizations/test-visible.jsonl"]["license_expression"] == "MIT"
    assert artifacts["report.md"]["license_expression"] == "CC-BY-4.0"
    assert all(row["origin_class"] == "GENERATED_PUBLIC_ARTIFACT" for row in artifacts.values())
    assert all(row["access_conditions"] is None for row in artifacts.values())
