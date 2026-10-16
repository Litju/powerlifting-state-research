import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESULTS = "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting"
PREDICTION_HASHES = {
    "ensemble": "f6fb260feac851845f584bcd96a290ec046234f78a7596221aba5453aecc006d",
    "383001": "eb1bf322ba1783d0c70f59d13016421736fd6447c2f6827079f713d31332f50c",
    "383002": "2373889b26646731eafc88907fada38aaf2982d0cfb464b7cfb4f728fb854e89",
    "383003": "472fe8e81648672af3d93e17caaabe433026ab0d1725e384c370eb35f6d45944",
}

sys.path.insert(0, str(ROOT / "scripts"))
from verify_gitleaks import (  # noqa: E402
    SecurityScanError,
    parse_gitleaks_report,
    require_clean_gitleaks_report,
)


def _json(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_prediction_hashes_match_the_res274_run_and_source_inventory() -> None:
    run = _json("results/manifests/public-native-temporal-expert.json")
    inventory = _json("results/manifests/public-native-temporal-expert-source-inventory.json")
    source_entries = {entry["path"]: entry["sha256"] for entry in inventory["entries"]}
    recorded: dict[str, str] = {}
    for checkpoint in run["checkpoints"]:
        prediction = checkpoint["prediction"]
        recorded[str(checkpoint["seed"])] = prediction["sha256"]
        assert source_entries[prediction["source_member"]] == prediction["sha256"]
    ensemble = run["ensemble"]["prediction"]
    recorded["ensemble"] = ensemble["sha256"]
    assert source_entries[ensemble["source_member"]] == ensemble["sha256"]

    assert recorded == PREDICTION_HASHES
    for seed, expected in PREDICTION_HASHES.items():
        name = "ensemble" if seed == "ensemble" else f"seed-{seed}"
        path = f"{RESULTS}/public-native-temporal-expert/{name}.predictions.jsonl"
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    for checkpoint in run["checkpoints"]:
        result = checkpoint["evaluation_result"]
        assert hashlib.sha256((ROOT / result["path"]).read_bytes()).hexdigest() == result["sha256"]
        assert source_entries[result["source_member"]] == result["sha256"]
    result = run["ensemble"]["evaluation_result"]
    assert hashlib.sha256((ROOT / result["path"]).read_bytes()).hexdigest() == result["sha256"]
    assert source_entries[result["source_member"]] == result["sha256"]


def test_prediction_rights_fallback_matches_the_origin_ledger() -> None:
    with (ROOT / "provenance/PUBLIC_FILE_ORIGINS.csv").open(newline="", encoding="utf-8") as file:
        origins = {row["path"]: row for row in csv.DictReader(file)}

    run = _json("results/manifests/public-native-temporal-expert.json")
    for seed, expected_hash in PREDICTION_HASHES.items():
        name = "ensemble" if seed == "ensemble" else f"seed-{seed}"
        prediction_path = f"{RESULTS}/public-native-temporal-expert/{name}.predictions.jsonl"
        result_path = prediction_path.removesuffix(".predictions.jsonl") + ".evaluation-result.json"
        result = _json(result_path)["result"]
        artifact = result["prediction_artifact"]
        assert artifact["content_sha256"] == f"sha256:{expected_hash}"
        assert artifact["rights"]["license_expression"] == "NOASSERTION"
        assert artifact["rights"]["copyright_holder"] == "Not asserted"
        assert result["rights"]["license_expression"] == "MIT"
        assert (
            result["dataset_realization_id"] == run["scientific_identity"]["dataset_realization_id"]
        )
        assert origins[prediction_path]["origin_class"] == "GENERATED_PUBLIC_ARTIFACT"
        assert origins[prediction_path]["license_expression"] == "MIT"
        assert origins[prediction_path]["owner"] == "Powerlifting State Research contributors"


def test_public_native_checkpoint_bytes_remain_excluded_from_git() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "*.pt", "*.pth", "*.ckpt", "*.safetensors"],
        cwd=ROOT,
    )
    assert not tracked
    checkpoints = [
        f"models/checkpoints/public-native-temporal-expert/seed-{seed}.pt"
        for seed in (383001, 383002, 383003)
    ]
    assert not any((ROOT / path).exists() for path in checkpoints)
    for path in checkpoints:
        assert (
            subprocess.check_output(["git", "check-ignore", path], cwd=ROOT, text=True).strip()
            == path
        )


def test_gitleaks_json_findings_fail_even_when_cli_exit_code_is_zero() -> None:
    assert parse_gitleaks_report("[]") == 0
    finding = '[{"RuleID":"test-rule","Secret":"[redacted]"}]'
    assert parse_gitleaks_report(finding) == 1
    with pytest.raises(SecurityScanError, match="finding"):
        require_clean_gitleaks_report(finding, 0)
    with pytest.raises(SecurityScanError, match="invalid JSON"):
        require_clean_gitleaks_report("not JSON", 0)
