import subprocess
import sys
from pathlib import Path


def test_result_packages_are_self_contained_and_match_their_integrity_indexes() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_repository_integrity.py")],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: RES-275 comparator registry, validation isolation, and artifact hashes" in (
        result.stdout
    )
