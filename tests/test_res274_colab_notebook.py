from __future__ import annotations

import json
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


def test_res274_source_checkout_cannot_collide_with_output_root() -> None:
    notebook = json.loads(
        (ROOT / "notebooks/public-native-temporal-expert-colab.ipynb").read_text(encoding="utf-8")
    )
    sources = ["".join(cell["source"]) for cell in notebook["cells"]]
    storage = sources[1]
    checkout = sources[2]

    assert 'REPO_DIR = Path("/content/psr-src")' in checkout
    assert 'DRIVE_PROJECT_ROOT = MY_DRIVE / "powerlifting-state-research"' in storage
    assert "RUN_OUTPUT = RUNS_ROOT / RUN_ID" in storage
    assert "RUN_OUTPUT.mkdir(" not in storage
    assert 'REPO_DIR = Path("/content/powerlifting-state-research")' not in checkout
    assert "REPO_DIR.resolve().is_relative_to(RES274_DRIVE_ROOT.resolve())" in checkout

    source_root = Path("/content/psr-src")
    project_run = Path("/content/drive/MyDrive/powerlifting-state-research/res274/runs/run-id")
    assert not source_root.is_relative_to(project_run)
    assert not project_run.is_relative_to(source_root)
