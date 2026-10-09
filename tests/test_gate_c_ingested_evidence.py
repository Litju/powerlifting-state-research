import subprocess
import sys
from pathlib import Path


def test_res274_gate_c_package_is_self_contained_and_matches_source_inventory() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_repository_integrity.py")],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
