from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_res274_colab_notebook_is_generated_and_structurally_safe() -> None:
    for script, arguments in (
        ("build_res274_colab_notebook.py", ["--check"]),
        ("validate_res274_colab_notebook.py", []),
    ):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *arguments],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
