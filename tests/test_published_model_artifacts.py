import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "verify_published_model_artifacts", ROOT / "scripts/verify_published_model_artifacts.py"
)
assert _spec is not None and _spec.loader is not None
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)


def test_published_model_artifacts_hash_and_load() -> None:
    output = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/verify_published_model_artifacts.py")],
        cwd=ROOT,
        text=True,
    )
    result = json.loads(output)
    assert result["public_native_checkpoints"] == 3
    assert result["res293_states"] == 30
    assert len(result["binary_paths"]) == 33
    assert result["normalization_metadata"]["status"] == "KNOWN_FROZEN_METADATA_CONFLICT"


def test_published_model_artifact_verifier_rejects_corrupted_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = json.loads(
        (ROOT / "models/published/res293-definition-b/artifact-manifest.json").read_text()
    )
    record = copy.deepcopy(
        next(item for item in manifest["artifacts"] if item["kind"] == "original fitted state")
    )
    path = tmp_path / record["path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * record["bytes"])
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="hash, size, or rights mismatch"):
        verifier._verify_records({"artifacts": [record]})


def test_published_model_artifact_verifier_rejects_mismatched_model_identity() -> None:
    expert = {"model_id": "expected-model", "normalization": {"normalization_stats_id": "norm"}}
    record = {"path": "checkpoint.pt", "sha256": "digest"}
    identity = {"checkpoint_sha256": "digest"}
    source_manifest = {
        "checkpoint_sha256": "digest",
        "model_id": "different-model",
        "normalization_stats_id": "norm",
    }

    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        verifier._verify_checkpoint_identity(
            "expected-model", 118_571, identity, record, expert, source_manifest
        )


def test_normalization_discrepancy_rejects_unrecognized_metadata() -> None:
    expert = json.loads(
        (ROOT / "models/published/public-native-temporal-expert/artifact-manifest.json").read_text()
    )
    assert verifier._normalization_discrepancy(expert)["actual_file_sha256"] == (
        "f5aade7089c5bd962140501f842d9aacd39a34df45928077c1228fbbbf6d21ca"
    )
    expert["normalization"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="unrecognized normalization"):
        verifier._normalization_discrepancy(expert)
