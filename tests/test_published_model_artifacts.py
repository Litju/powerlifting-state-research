import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
