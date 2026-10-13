from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from powerlifting_state_research.studies.synthetic_pretraining_transfer import (
    ARMS,
    FIT_SEEDS,
    _decision_status,
    _make_bootstrap,
    _paired_rmse_deltas,
    _plan_bootstrap_indices,
    verify_design,
)
from powerlifting_state_research.studies.synthetic_pretraining_transfer_learner import (
    TARGETS,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/studies/synthetic_pretraining_transfer/public-native"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _fixture_fitting_rows() -> list[dict[str, Any]]:
    rows = []
    plans = ("cessation", "step_down", "continue", "step_up")
    for plan_index, plan in enumerate(plans):
        for horizon in (14, 28, 56):
            for donor in range(2):
                identifier = f"donor-{plan_index}-{horizon}-{donor}"
                rows.append(
                    {
                        "row_id": identifier,
                        "inputs": {
                            "entity_id": identifier,
                            "horizon_days": horizon,
                            "declared_future_plan": {"plan_id": plan},
                            "marker": float(donor + plan_index),
                        },
                        "targets": {
                            target: float(donor + plan_index + horizon / 100.0)
                            for target in TARGETS
                        },
                    }
                )
    return rows


def test_bootstrap_is_deterministic_and_keeps_donor_label_lineage() -> None:
    fitting = _fixture_fitting_rows()
    first, first_lineage = _make_bootstrap(fitting, 292180)
    second, second_lineage = _make_bootstrap(fitting, 292180)

    assert first == second
    assert first_lineage == second_lineage
    assert len(first) == len(fitting)
    donor_by_id = {row["row_id"]: row for row in fitting}
    assert all(item["label_provenance"] == "BOOTSTRAP_DUPLICATE_LABEL" for item in first_lineage)
    for row, item in zip(first, first_lineage, strict=True):
        donor = donor_by_id[item["donor_row_id"]]
        assert row["row_id"] != donor["row_id"]
        assert row["targets"] == donor["targets"]
        assert row["inputs"]["entity_id"] == row["row_id"]
        assert item["donor_record_sha256"].startswith("sha256:")


def test_paired_bootstrap_preserves_plan_clusters_and_arm_pairing() -> None:
    plans = ["cessation"] * 3 + ["step_down"] * 4 + ["continue"] * 5 + ["step_up"] * 6
    indices = _plan_bootstrap_indices(plans, np.random.default_rng(292170), 250)

    assert indices.shape == (250, len(plans))
    for draw in indices:
        assert [
            sum(plans[index] == plan for index in draw)
            for plan in (
                "cessation",
                "step_down",
                "continue",
                "step_up",
            )
        ] == [3, 4, 5, 6]
    errors = np.linspace(-5.0, 5.0, len(plans))
    assert np.all(_paired_rmse_deltas(errors, errors, plans, 292170, replicates=250) == 0.0)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ((-2.0, -1.1), "PRACTICAL_BENEFIT"),
        ((1.1, 2.0), "PRACTICAL_HARM"),
        ((-0.8, 0.9), "PRACTICAL_EQUIVALENCE"),
        ((-1.2, 0.1), "INCONCLUSIVE"),
        ((-0.2, 1.2), "INCONCLUSIVE"),
    ],
)
def test_practical_decision_keeps_inconclusive_states(
    interval: tuple[float, float], expected: str
) -> None:
    assert _decision_status(*interval) == expected


def test_frozen_m0_m5_g1_g3_and_g4_metadata_are_unchanged() -> None:
    protocol = verify_design(ROOT)
    frozen = json.loads(
        (ROOT / "studies/synthetic_pretraining_transfer/frozen-evidence.json").read_text()
    )
    assert protocol["starting_main"] == "0489029384af4503d175220e9a9a090845b38cc6"
    assert len(frozen["files"]) >= 100
    assert set(frozen["upstream_studies"]) >= {"RES-287", "RES-289", "RES-290"}
    assert frozen["historical_g4"]["registry_aliases"] == [
        "G4 / ALI-544",
        "pl_study_g4_synthetic_pretraining",
    ]
    assert len(frozen["historical_g4"]["baseline_homes"]) == 2


def test_published_learner_firewall_and_train_dev_test_disjointness() -> None:
    audit = json.loads((OUTPUT / "learner-input-audit.json").read_text())
    assert len(audit) == len(ARMS) * len(FIT_SEEDS)
    assert all(row["passed"] for row in audit)
    assert all(row["query_targets_in_payload"] == 0 for row in audit)
    assert all(row["authority_only_fields_in_payload"] == 0 for row in audit)

    split_ids = []
    for path in (
        "realizations/fitting.jsonl",
        "realizations/development-visible.jsonl",
        "realizations/test-population-a-visible.jsonl",
        "realizations/test-population-b-visible.jsonl",
    ):
        split_ids.append({row["row_id"] for row in _jsonl(OUTPUT / path)})
    for index, left in enumerate(split_ids):
        for right in split_ids[index + 1 :]:
            assert left.isdisjoint(right)

    by_arm = {(row["arm"], row["fit_seed"]): row for row in audit}
    for seed in FIT_SEEDS:
        assert by_arm[("SYNTHETIC_ONLY_BOOTSTRAP", seed)]["public_fitting_rows"] == 0
        assert by_arm[("SYNTHETIC_ONLY_PSEUDOLABEL", seed)]["public_fitting_rows"] == 0
        assert by_arm[("PUBLIC_ONLY", seed)]["synthetic_fitting_rows"] == 0
        assert by_arm[("PUBLIC_ONLY", seed)]["synthetic_label_provenance"] == "NONE"
        assert by_arm[("COMPUTE_MATCHED_PUBLIC_ONLY", seed)]["synthetic_label_provenance"] == "NONE"


def test_donor_copy_and_surrogate_pseudo_labels_remain_distinct() -> None:
    fitting = {row["row_id"]: row for row in _jsonl(OUTPUT / "realizations/fitting.jsonl")}
    bootstrap = _jsonl(OUTPUT / "synthetic/donor-copy-bootstrap.jsonl")
    bootstrap_lineage = _jsonl(OUTPUT / "synthetic/donor-lineage.jsonl")
    pseudo = _jsonl(OUTPUT / "synthetic/surrogate-pseudo-labels.jsonl")
    pseudo_lineage = _jsonl(OUTPUT / "synthetic/pseudo-label-lineage.jsonl")

    assert len(bootstrap) == len(bootstrap_lineage) == 384
    assert len(pseudo) == len(pseudo_lineage) == 384
    for row, lineage in zip(bootstrap, bootstrap_lineage, strict=True):
        donor = fitting[lineage["donor_row_id"]]
        assert lineage["label_provenance"] == "BOOTSTRAP_DUPLICATE_LABEL"
        assert row["targets"] == donor["targets"]
        copied_inputs = copy.deepcopy(row["inputs"])
        donor_inputs = copy.deepcopy(donor["inputs"])
        copied_inputs.pop("entity_id")
        donor_inputs.pop("entity_id")
        assert copied_inputs == donor_inputs
    for row, lineage in zip(pseudo, pseudo_lineage, strict=True):
        assert lineage["label_provenance"] == "SURROGATE_PSEUDO_LABEL"
        assert lineage["donor_original_label_copied"] is False
        assert lineage["teacher_fitted_instance"].startswith("psr:fitted-instance:")
        assert set(row["targets"]) == set(TARGETS)

    with (OUTPUT / "synthetic/training-label-provenance.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        provenance = list(csv.DictReader(stream))
    labels = {row["label_provenance"] for row in provenance}
    assert labels == {
        "ORIGINAL_PUBLIC_LABEL",
        "BOOTSTRAP_DUPLICATE_LABEL",
        "SURROGATE_PSEUDO_LABEL",
    }


def test_compute_budget_and_metric_units_are_explicit() -> None:
    accounting = list(csv.DictReader((OUTPUT / "compute-accounting.csv").open(newline="")))
    expected = {
        "PUBLIC_ONLY": (128, 128, 0, 4096, 0),
        "SYNTHETIC_ONLY_BOOTSTRAP": (128, 0, 128, 0, 4096),
        "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP": (256, 128, 128, 4096, 4096),
        "COMPUTE_MATCHED_PUBLIC_ONLY": (256, 256, 0, 8192, 0),
        "SYNTHETIC_ONLY_PSEUDOLABEL": (128, 0, 128, 0, 4096),
        "SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL": (256, 128, 128, 4096, 4096),
    }
    fits = [row for row in accounting if row["record_type"] == "learner_fit"]
    assert len(fits) == len(ARMS) * len(FIT_SEEDS)
    for row in fits:
        updates, public_updates, synthetic_updates, public_rows, synthetic_rows = expected[
            row["arm"]
        ]
        assert int(row["update_count"]) == updates
        assert int(row["public_updates"]) == public_updates
        assert int(row["synthetic_updates"]) == synthetic_updates
        assert int(row["public_label_presentations"]) == public_rows
        assert int(row["synthetic_label_presentations"]) == synthetic_rows
        assert int(row["parameter_count"]) == 177

    metrics = list(csv.DictReader((OUTPUT / "evaluation-results.csv").open(newline="")))
    assert metrics
    assert all(row["target"].endswith("_kg") for row in metrics)
    for row in metrics:
        if row["status"] == "COMPLETE":
            assert int(row["n_entities"]) == 128
            assert float(row["rmse_kg"]) >= float(row["mae_kg"]) >= 0.0
            assert row["model_id"].startswith("psr:fitted-instance:")


def test_duplicate_support_and_negative_or_inconclusive_states_are_preserved() -> None:
    support = json.loads((OUTPUT / "finite-support-summary.json").read_text())
    assert support["bootstrap_draws"] == 384
    assert 0 < support["unique_fitting_donors"] <= support["bootstrap_draws"]
    assert 0.0 <= support["duplicate_draw_fraction"] < 1.0
    assert support["donor_copy_fraction"] == 1.0
    assert support["genuinely_novel_synthetic_rows"] == 0
    assert support["independently_generated_synthetic_truth_labels"] == 0

    effects = list(csv.DictReader((OUTPUT / "paired-transfer-effects.csv").open(newline="")))
    allowed = {
        "PRACTICAL_BENEFIT",
        "PRACTICAL_HARM",
        "PRACTICAL_EQUIVALENCE",
        "INCONCLUSIVE",
        "MODEL_FIT_FAILED",
    }
    assert effects and {row["status"] for row in effects} <= allowed
    negatives = list(csv.DictReader((OUTPUT / "negative-results.csv").open(newline="")))
    assert any(row["status"] == "UNSUPPORTED_BY_EVIDENCE" for row in negatives)
    assert any(row["status"] == "NO_INDEPENDENT_INFORMATION_BY_CONSTRUCTION" for row in negatives)


def test_artifact_hashes_and_rights_are_bound() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    artifacts = json.loads((OUTPUT / "artifact-manifest.json").read_text())["artifacts"]
    recorded = {row["path"]: row for row in artifacts}
    for path, metadata in recorded.items():
        digest = hashlib.sha256((OUTPUT / path).read_bytes()).hexdigest()
        assert digest == metadata["sha256"]
        expected_license = "CC-BY-4.0" if path.endswith(".md") else "MIT"
        assert metadata["license_expression"] == expected_license
    checksums = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (OUTPUT / "SHA256SUMS.txt").read_text().splitlines()
    }
    assert all(
        hashlib.sha256((OUTPUT / path).read_bytes()).hexdigest() == digest
        for path, digest in checksums.items()
    )
    assert manifest["rights"]["historical_private_artifacts_used"] is False
    assert manifest["dataset_realization"]["evaluation_truth_separate_from_learner_payload"]
    assert manifest["learner"]["prediction_seal_sha256"].startswith("sha256:")
